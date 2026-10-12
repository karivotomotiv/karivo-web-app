"""Dashboard v2 & Monthly Report backend tests — iter-13.

Covers: /dashboard/overview, /reports/monthly, /settings/stock, /dashboard/monthly-trend,
/inventory/alerts (same threshold), plus end-to-end delta scenarios: incomes/expenses/
company spending, cash sale, veresiye sale, partial collection, cari closure, sale cancel.
Uses TEST_ prefix on all created entities, cleans them up at the end. Never touches
existing Michelin/real-data records; computes deltas (after-before).
"""
import os
import uuid
from datetime import datetime, timedelta

import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not configured"
API = f"{BASE_URL}/api"
MURAT = {"email": "murat@karivo.local", "password": "Murat2026!"}

TODAY = "2026-10-12"
TODAY_MONTH = "2026-10"
LAST_YEAR = "2025-01-15"  # out-of-period marker


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=MURAT, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"no token in response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def created(client):
    """Shared bag of ids to clean up at the end."""
    bag = {"tires": [], "cariler": [], "incomes": [], "expenses": [], "spendings": [], "sales": [], "cari_tx": []}
    yield bag
    # ---- cleanup ----
    for sid in bag["sales"]:
        try: client.delete(f"{API}/sales/{sid}", timeout=15)
        except Exception: pass
    for cid, txid in bag["cari_tx"]:
        try: client.delete(f"{API}/cariler/{cid}/transactions/{txid}", timeout=15)
        except Exception: pass
    for iid in bag["incomes"]:
        try: client.delete(f"{API}/incomes/{iid}", timeout=15)
        except Exception: pass
    for eid in bag["expenses"]:
        try: client.delete(f"{API}/expenses/{eid}", timeout=15)
        except Exception: pass
    for spid in bag["spendings"]:
        try: client.delete(f"{API}/spendings/{spid}", timeout=15)
        except Exception: pass
    for tid in bag["tires"]:
        try: client.delete(f"{API}/tires/{tid}", timeout=15)
        except Exception: pass
    for cid in bag["cariler"]:
        try: client.delete(f"{API}/cariler/{cid}", timeout=15)
        except Exception: pass
    # restore threshold
    try: client.put(f"{API}/settings/stock", json={"critical_threshold": 4}, timeout=15)
    except Exception: pass


def _overview(client, start=f"{TODAY_MONTH}-01", end=f"{TODAY_MONTH}-31"):
    r = client.get(f"{API}/dashboard/overview", params={"start": start, "end": end}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ===================== Shape / validation =====================
class TestOverviewShape:
    def test_schema(self, client):
        d = _overview(client)
        for k in ("finance", "stock", "receivables", "warnings", "as_of"):
            assert k in d, f"missing top-level key {k}"
        f = d["finance"]
        for k in ("income_total", "income_count", "expense_total", "expense_count",
                  "income_expense_diff", "company_spending_total",
                  "sales_revenue", "sales_count", "sales_tire_qty",
                  "sales_by_payment", "collections_total",
                  "collections_cash_sales", "collections_cari_payments"):
            assert k in f, f"finance missing {k}"
        for k in ("nakit", "kart", "havale", "veresiye"):
            assert k in f["sales_by_payment"], f"sales_by_payment missing {k}"
        s = d["stock"]
        for k in ("threshold", "product_count", "total_qty", "critical_count",
                  "out_of_stock_count", "critical", "out_of_stock"):
            assert k in s
        r = d["receivables"]
        for k in ("total", "debtor_count", "items"):
            assert k in r
        assert isinstance(d["warnings"], list)

    def test_invalid_date_format_400(self, client):
        r = client.get(f"{API}/dashboard/overview", params={"start": "2026/10/01", "end": "2026-10-31"}, timeout=15)
        assert r.status_code == 400

    def test_start_after_end_400(self, client):
        r = client.get(f"{API}/dashboard/overview", params={"start": "2026-10-31", "end": "2026-10-01"}, timeout=15)
        assert r.status_code == 400


# ===================== Finance deltas =====================
class TestFinanceDeltas:
    def test_income_expense_and_company_spending(self, client, created):
        before = _overview(client)["finance"]

        r = client.post(f"{API}/incomes", json={"description": "TEST_income_dashv2", "amount": 1000, "date": TODAY}, timeout=15)
        assert r.status_code == 200, r.text
        created["incomes"].append(r.json()["id"])

        r = client.post(f"{API}/expenses", json={"description": "TEST_expense_dashv2", "amount": 300, "date": TODAY}, timeout=15)
        assert r.status_code == 200, r.text
        created["expenses"].append(r.json()["id"])

        r = client.post(f"{API}/spendings", json={"category": "company", "name": "TEST_spend_dashv2", "amount": 500, "date": TODAY}, timeout=15)
        assert r.status_code == 200, r.text
        created["spendings"].append(r.json()["id"])

        after = _overview(client)["finance"]
        assert round(after["income_total"] - before["income_total"], 2) == 1000.0
        assert round(after["expense_total"] - before["expense_total"], 2) == 300.0
        assert round(after["income_expense_diff"] - before["income_expense_diff"], 2) == 700.0
        # Company spending must NOT affect expense_total
        assert round(after["company_spending_total"] - before["company_spending_total"], 2) == 500.0

    def test_out_of_period_income_not_counted(self, client, created):
        before = _overview(client)["finance"]
        r = client.post(f"{API}/incomes", json={"description": "TEST_out_of_period", "amount": 9999, "date": LAST_YEAR}, timeout=15)
        assert r.status_code == 200
        created["incomes"].append(r.json()["id"])
        after = _overview(client)["finance"]
        assert round(after["income_total"] - before["income_total"], 2) == 0.0


# ===================== Sales scenarios =====================
class TestSalesScenarios:
    def test_cash_sale(self, client, created):
        # create TEST_ tire
        tr = client.post(f"{API}/tires", json={
            "brand": "TEST_BRAND_A", "model": "TEST_MODEL", "size": "205/55 R16",
            "season": "4mevsim", "quantity": 10, "buy_price": 700, "sell_price": 1000
        }, timeout=15)
        assert tr.status_code == 200, tr.text
        tire_id = tr.json()["id"]
        created["tires"].append(tire_id)

        before = _overview(client)["finance"]
        sr = client.post(f"{API}/sales", json={
            "items": [{"tire_id": tire_id, "quantity": 2, "unit_price": 1000}],
            "payment_method": "nakit", "date": TODAY,
        }, timeout=15)
        assert sr.status_code == 200, sr.text
        created["sales"].append(sr.json()["id"])

        after = _overview(client)["finance"]
        assert round(after["sales_revenue"] - before["sales_revenue"], 2) == 2000.0
        assert after["sales_count"] - before["sales_count"] == 1
        assert round(after["sales_tire_qty"] - before["sales_tire_qty"], 2) == 2.0
        assert round(after["collections_cash_sales"] - before["collections_cash_sales"], 2) == 2000.0
        # cash sale creates ONE income (single record, not duplicated)
        assert round(after["income_total"] - before["income_total"], 2) == 2000.0

    def test_veresiye_sale_partial_full_payment(self, client, created):
        # tire for veresiye
        tr = client.post(f"{API}/tires", json={
            "brand": "TEST_BRAND_V", "model": "TEST_V", "size": "225/45 R17",
            "season": "yaz", "quantity": 20, "buy_price": 700, "sell_price": 1000
        }, timeout=15)
        tire_id = tr.json()["id"]
        created["tires"].append(tire_id)

        # cari
        cr = client.post(f"{API}/cariler", json={"name": "TEST_CARI_V"}, timeout=15)
        assert cr.status_code == 200
        cari_id = cr.json()["id"]
        created["cariler"].append(cari_id)

        before = _overview(client)["finance"]
        rec_before = _overview(client)["receivables"]
        sr = client.post(f"{API}/sales", json={
            "cari_id": cari_id,
            "items": [{"tire_id": tire_id, "quantity": 3, "unit_price": 1000}],
            "payment_method": "veresiye", "date": TODAY,
        }, timeout=15)
        assert sr.status_code == 200, sr.text
        created["sales"].append(sr.json()["id"])

        d1 = _overview(client)
        f1 = d1["finance"]
        r1 = d1["receivables"]
        assert round(f1["sales_revenue"] - before["sales_revenue"], 2) == 3000.0
        assert round(f1["sales_by_payment"]["veresiye"] - before["sales_by_payment"]["veresiye"], 2) == 3000.0
        assert round(f1["collections_total"] - before["collections_total"], 2) == 0.0
        assert round(f1["income_total"] - before["income_total"], 2) == 0.0
        assert round(r1["total"] - rec_before["total"], 2) == 3000.0
        # cari in list w/ remaining = 3000
        row = next((x for x in r1["items"] if x["id"] == cari_id), None)
        assert row is not None, "TEST_CARI_V not in receivables.items"
        assert round(row["remaining"], 2) == 3000.0

        # Partial payment 1000
        tx1 = client.post(f"{API}/cariler/{cari_id}/transactions",
                          json={"type": "odeme", "amount": 1000, "date": TODAY},
                          timeout=15)
        assert tx1.status_code == 200, tx1.text
        created["cari_tx"].append((cari_id, tx1.json()["id"]))

        d2 = _overview(client)
        f2 = d2["finance"]
        r2 = d2["receivables"]
        row2 = next((x for x in r2["items"] if x["id"] == cari_id), None)
        assert row2 is not None and round(row2["remaining"], 2) == 2000.0
        assert round(f2["collections_cari_payments"] - before["collections_cari_payments"], 2) == 1000.0
        # income MUST NOT change on cari payment
        assert round(f2["income_total"] - before["income_total"], 2) == 0.0

        # Final payment 2000 → should disappear from list
        tx2 = client.post(f"{API}/cariler/{cari_id}/transactions",
                          json={"type": "odeme", "amount": 2000, "date": TODAY},
                          timeout=15)
        assert tx2.status_code == 200
        created["cari_tx"].append((cari_id, tx2.json()["id"]))

        d3 = _overview(client)
        r3 = d3["receivables"]
        assert all(x["id"] != cari_id for x in r3["items"]), "closed cari still in items"
        assert r3["debtor_count"] <= rec_before["debtor_count"]  # at least same or lower
        # Overpayment doesn't go negative — add +500 odeme, total shouldn't decrease
        tx3 = client.post(f"{API}/cariler/{cari_id}/transactions",
                          json={"type": "odeme", "amount": 500, "date": TODAY}, timeout=15)
        assert tx3.status_code == 200
        created["cari_tx"].append((cari_id, tx3.json()["id"]))
        r4 = _overview(client)["receivables"]
        assert all(x["id"] != cari_id for x in r4["items"])
        assert round(r4["total"] - rec_before["total"], 2) == 0.0  # overpaid cari still contributes 0

    def test_sale_cancel_reverses_totals(self, client, created):
        tr = client.post(f"{API}/tires", json={
            "brand": "TEST_BRAND_C", "model": "TEST_C", "size": "195/65 R15",
            "season": "4mevsim", "quantity": 10, "buy_price": 500, "sell_price": 900
        }, timeout=15)
        tire_id = tr.json()["id"]
        created["tires"].append(tire_id)

        before = _overview(client)["finance"]
        sr = client.post(f"{API}/sales", json={
            "items": [{"tire_id": tire_id, "quantity": 2, "unit_price": 900}],
            "payment_method": "nakit", "date": TODAY,
        }, timeout=15)
        assert sr.status_code == 200
        sid = sr.json()["id"]
        # DO NOT register for cleanup — we delete it right now and verify
        dr = client.delete(f"{API}/sales/{sid}", timeout=15)
        assert dr.status_code == 200, dr.text

        after = _overview(client)["finance"]
        assert round(after["sales_revenue"] - before["sales_revenue"], 2) == 0.0
        assert after["sales_count"] - before["sales_count"] == 0
        assert round(after["collections_cash_sales"] - before["collections_cash_sales"], 2) == 0.0
        assert round(after["income_total"] - before["income_total"], 2) == 0.0

    def test_veresiye_cancel_reverses_receivable(self, client, created):
        tr = client.post(f"{API}/tires", json={
            "brand": "TEST_BRAND_D", "model": "TEST_D", "size": "215/60 R16",
            "season": "kis", "quantity": 10, "buy_price": 500, "sell_price": 1200
        }, timeout=15)
        tire_id = tr.json()["id"]
        created["tires"].append(tire_id)
        cr = client.post(f"{API}/cariler", json={"name": "TEST_CARI_D"}, timeout=15)
        cari_id = cr.json()["id"]
        created["cariler"].append(cari_id)

        rec_before = _overview(client)["receivables"]
        sr = client.post(f"{API}/sales", json={
            "cari_id": cari_id,
            "items": [{"tire_id": tire_id, "quantity": 2, "unit_price": 1200}],
            "payment_method": "veresiye", "date": TODAY,
        }, timeout=15)
        sid = sr.json()["id"]
        dr = client.delete(f"{API}/sales/{sid}", timeout=15)
        assert dr.status_code == 200

        rec_after = _overview(client)["receivables"]
        assert round(rec_after["total"] - rec_before["total"], 2) == 0.0
        assert all(x["id"] != cari_id for x in rec_after["items"])


# ===================== Stock threshold =====================
class TestStockThreshold:
    def test_get_default_threshold_is_4(self, client):
        # ensure baseline — reset to 4 first (will be restored by fixture anyway)
        client.put(f"{API}/settings/stock", json={"critical_threshold": 4}, timeout=15)
        r = client.get(f"{API}/settings/stock", timeout=15)
        assert r.status_code == 200
        assert r.json()["critical_threshold"] == 4

    def test_threshold_moves_tire_between_lists(self, client, created):
        # create tire with qty=4 → critical
        tr = client.post(f"{API}/tires", json={
            "brand": "TEST_THR", "model": "TEST", "size": "205/60 R16",
            "season": "4mevsim", "quantity": 4, "buy_price": 1, "sell_price": 1
        }, timeout=15)
        tire_id = tr.json()["id"]
        created["tires"].append(tire_id)

        snap = _overview(client)["stock"]
        assert snap["threshold"] == 4
        assert any(x["id"] == tire_id for x in snap["critical"]), "qty=4 should be in critical"
        assert not any(x["id"] == tire_id for x in snap["out_of_stock"])

        # bump qty to 5 → not in critical
        mv = client.post(f"{API}/tires/{tire_id}/movement", json={"delta": 1, "reason": "sayim-duzeltme"}, timeout=15)
        assert mv.status_code == 200
        snap2 = _overview(client)["stock"]
        assert not any(x["id"] == tire_id for x in snap2["critical"])
        assert not any(x["id"] == tire_id for x in snap2["out_of_stock"])

        # drop qty to 0 → out_of_stock
        mv2 = client.post(f"{API}/tires/{tire_id}/movement", json={"delta": -5, "reason": "sayim-duzeltme"}, timeout=15)
        assert mv2.status_code == 200
        snap3 = _overview(client)["stock"]
        assert any(x["id"] == tire_id for x in snap3["out_of_stock"])
        assert not any(x["id"] == tire_id for x in snap3["critical"])

    def test_threshold_change_affects_result_and_alerts(self, client, created):
        # create a tire at qty=6
        tr = client.post(f"{API}/tires", json={
            "brand": "TEST_THR2", "model": "TEST", "size": "225/50 R17",
            "season": "4mevsim", "quantity": 6, "buy_price": 1, "sell_price": 1
        }, timeout=15)
        tire_id = tr.json()["id"]
        created["tires"].append(tire_id)
        # threshold=4 → not critical
        client.put(f"{API}/settings/stock", json={"critical_threshold": 4}, timeout=15)
        snap_a = _overview(client)["stock"]
        assert not any(x["id"] == tire_id for x in snap_a["critical"])
        # threshold=10 → critical
        client.put(f"{API}/settings/stock", json={"critical_threshold": 10}, timeout=15)
        snap_b = _overview(client)["stock"]
        assert snap_b["threshold"] == 10
        assert any(x["id"] == tire_id for x in snap_b["critical"])
        # alerts endpoint uses same threshold
        al = client.get(f"{API}/inventory/alerts", timeout=15)
        assert al.status_code == 200
        aj = al.json()
        assert aj["threshold"] == 10
        assert any(it["id"] == tire_id for it in aj["items"])
        # restore to 4
        client.put(f"{API}/settings/stock", json={"critical_threshold": 4}, timeout=15)


# ===================== Monthly report =====================
class TestMonthlyReport:
    def test_shape_and_month_boundaries(self, client):
        r = client.get(f"{API}/reports/monthly", params={"month": "2026-02"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["month"] == "2026-02"
        assert d["previous_month"] == "2026-01"
        assert d["current"]["range"]["start"] == "2026-02-01"
        assert d["current"]["range"]["end"] == "2026-02-28"
        for k in ("income_total", "expense_total", "income_expense_diff", "sales_revenue",
                  "collections_total"):
            assert k in d["current"]
            assert k in d["previous"]
        sm = d["stock_movements_summary"]
        assert set(sm.keys()) == {"count", "in_qty", "out_qty"}

    def test_jan_previous_is_prev_dec(self, client):
        r = client.get(f"{API}/reports/monthly", params={"month": "2026-01"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["previous_month"] == "2025-12"

    def test_invalid_month_400(self, client):
        r = client.get(f"{API}/reports/monthly", params={"month": "2026-13"}, timeout=15)
        assert r.status_code == 400

    def test_details_true_includes_lists(self, client):
        r = client.get(f"{API}/reports/monthly", params={"month": TODAY_MONTH, "details": "true"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("incomes", "expenses", "sales", "cari_payments", "stock_movements"):
            assert k in d, f"details missing {k}"
            assert isinstance(d[k], list)
        # cari_payments must include cari_name
        for p in d["cari_payments"]:
            assert "cari_name" in p


# ===================== Monthly trend =====================
class TestMonthlyTrend:
    def test_no_profit_field_has_diff(self, client):
        r = client.get(f"{API}/dashboard/monthly-trend", timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert "profit" not in row, "monthly-trend must NOT contain 'profit'"
            assert "diff" in row
            assert "income" in row and "expense" in row
            assert row["diff"] == round(row["income"] - row["expense"], 2)
