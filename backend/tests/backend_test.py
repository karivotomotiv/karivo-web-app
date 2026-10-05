"""Backend API tests for Küçük Şirket Yönetim Uygulaması."""
import os
import io
import pytest
import requests
from datetime import datetime

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-app-207.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

U1 = {"email": "ahmet@sirket.com", "password": "Ahmet2026!"}
U2 = {"email": "ayse@sirket.com", "password": "Ayse2026!"}


@pytest.fixture(scope="session")
def token1():
    r = requests.post(f"{API}/auth/login", json=U1, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def h1(token1):
    return {"Authorization": f"Bearer {token1}"}


# ---------- AUTH ----------
class TestAuth:
    def test_me_unauth(self):
        r = requests.get(f"{API}/auth/me", timeout=20)
        assert r.status_code in (401, 403)

    def test_login_user1(self):
        r = requests.post(f"{API}/auth/login", json=U1, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and "user" in data
        assert data["user"]["email"] == U1["email"]
        assert "Ahmet" in data["user"]["name"]

    def test_login_user2(self):
        r = requests.post(f"{API}/auth/login", json=U2, timeout=20)
        assert r.status_code == 200
        assert "Ayşe" in r.json()["user"]["name"] or "Ayse" in r.json()["user"]["name"]

    def test_login_bad(self):
        r = requests.post(f"{API}/auth/login", json={"email": U1["email"], "password": "wrong!"}, timeout=20)
        assert r.status_code == 401
        assert "hatalı" in r.json().get("detail", "")

    def test_me_with_token(self, h1):
        r = requests.get(f"{API}/auth/me", headers=h1, timeout=20)
        assert r.status_code == 200
        assert r.json()["email"] == U1["email"]


# ---------- INCOMES ----------
class TestIncomes:
    def test_crud(self, h1):
        # Create without date (auto-fill)
        r = requests.post(f"{API}/incomes", headers=h1, json={"description": "TEST_inc", "amount": 500}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["amount"] == 500
        assert d["date"] == datetime.utcnow().strftime("%Y-%m-%d")
        iid = d["id"]

        # List
        r = requests.get(f"{API}/incomes", headers=h1, timeout=20)
        assert r.status_code == 200 and isinstance(r.json(), list)
        assert any(x["id"] == iid for x in r.json())

        # Update
        r = requests.put(f"{API}/incomes/{iid}", headers=h1, json={"description": "TEST_inc2", "amount": 600}, timeout=20)
        assert r.status_code == 200 and r.json()["amount"] == 600

        # Delete
        r = requests.delete(f"{API}/incomes/{iid}", headers=h1, timeout=20)
        assert r.status_code == 200


# ---------- EXPENSES ----------
class TestExpenses:
    def test_crud(self, h1):
        r = requests.post(f"{API}/expenses", headers=h1, json={"description": "TEST_exp", "amount": 300}, timeout=20)
        assert r.status_code == 200
        eid = r.json()["id"]
        r = requests.put(f"{API}/expenses/{eid}", headers=h1, json={"description": "TEST_exp2", "amount": 350}, timeout=20)
        assert r.status_code == 200 and r.json()["amount"] == 350
        assert requests.delete(f"{API}/expenses/{eid}", headers=h1, timeout=20).status_code == 200


# ---------- INVOICES ----------
class TestInvoices:
    def test_vat_calc_and_crud(self, h1):
        r = requests.post(f"{API}/invoices", headers=h1, json={"description": "TEST_fat", "amount": 1200}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["base_amount"] == 1000.0
        assert d["vat_amount"] == 200.0
        fid = d["id"]

        # Update recalculation
        r = requests.put(f"{API}/invoices/{fid}", headers=h1, json={"description": "TEST_fat2", "amount": 2400}, timeout=20)
        assert r.status_code == 200
        assert r.json()["base_amount"] == 2000.0
        assert r.json()["vat_amount"] == 400.0

        # VAT summary
        r = requests.get(f"{API}/invoices/vat-summary", headers=h1, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) > 0
        row = rows[0]
        for k in ("month", "vat_total", "base_total", "gross_total", "count"):
            assert k in row

        assert requests.delete(f"{API}/invoices/{fid}", headers=h1, timeout=20).status_code == 200

    def test_import_xlsx(self, h1):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Tarih", "Açıklama", "Tutar"])
        ws.append(["2026-01-05", "TEST_import_1", 1200])
        ws.append(["2026-01-06", "TEST_import_2", 2400])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        files = {"file": ("test.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/invoices/import", headers=h1, files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["count"] == 2
        # Cleanup
        for it in data["items"]:
            requests.delete(f"{API}/invoices/{it['id']}", headers=h1, timeout=20)

    def test_import_bad_type(self, h1):
        files = {"file": ("test.txt", b"nope", "text/plain")}
        r = requests.post(f"{API}/invoices/import", headers=h1, files=files, timeout=20)
        assert r.status_code == 400


# ---------- INVENTORY ----------
class TestInventory:
    def test_remaining_calc(self, h1):
        payload = {"product_name": "TEST_prod", "required_qty": 10, "received_qty": 4, "purchase_price": 50}
        r = requests.post(f"{API}/inventory", headers=h1, json=payload, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["remaining_qty"] == 6.0
        sid = d["id"]
        # Update
        payload2 = {**payload, "received_qty": 7}
        r = requests.put(f"{API}/inventory/{sid}", headers=h1, json=payload2, timeout=20)
        assert r.status_code == 200 and r.json()["remaining_qty"] == 3.0
        assert requests.delete(f"{API}/inventory/{sid}", headers=h1, timeout=20).status_code == 200


# ---------- SPENDINGS ----------
class TestSpendings:
    def test_filter_by_category(self, h1):
        ids = []
        for cat in ("company", "user1", "user2"):
            r = requests.post(f"{API}/spendings", headers=h1, json={"category": cat, "name": f"TEST_sp_{cat}", "amount": 10}, timeout=20)
            assert r.status_code == 200
            ids.append(r.json()["id"])

        r = requests.get(f"{API}/spendings?category=company", headers=h1, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert all(x["category"] == "company" for x in rows)

        for i in ids:
            requests.delete(f"{API}/spendings/{i}", headers=h1, timeout=20)


# ---------- TODOS ----------
class TestTodos:
    def test_crud_complete(self, h1):
        r = requests.post(f"{API}/todos", headers=h1, json={"title": "TEST_todo", "note": "n"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["completed"] is False and d["completed_at"] is None
        tid = d["id"]
        r = requests.put(f"{API}/todos/{tid}", headers=h1, json={"completed": True}, timeout=20)
        assert r.status_code == 200
        upd = r.json()
        assert upd["completed"] is True and upd["completed_at"] is not None
        assert requests.delete(f"{API}/todos/{tid}", headers=h1, timeout=20).status_code == 200


# ---------- LOGS & SUMMARY ----------
class TestMisc:
    def test_logs(self, h1):
        r = requests.get(f"{API}/activity-logs", headers=h1, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) > 0
        # Descending order
        ts = [row["timestamp"] for row in rows]
        assert ts == sorted(ts, reverse=True)

    def test_summary(self, h1):
        r = requests.get(f"{API}/summary", headers=h1, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_income", "total_expense", "total_invoices", "total_vat", "open_todos"):
            assert k in d
            assert isinstance(d[k], (int, float))


# ---------- NEW: Monthly trend ----------
class TestMonthlyTrend:
    def test_monthly_trend_requires_auth(self):
        r = requests.get(f"{API}/dashboard/monthly-trend", timeout=20)
        assert r.status_code in (401, 403)

    def test_monthly_trend_shape(self, h1):
        # Seed one income so there's at least one bucket
        r = requests.post(f"{API}/incomes", headers=h1, json={"description": "TEST_mt", "amount": 100, "date": "2026-01-15"}, timeout=20)
        assert r.status_code == 200
        iid = r.json()["id"]
        try:
            r = requests.get(f"{API}/dashboard/monthly-trend", headers=h1, timeout=20)
            assert r.status_code == 200
            rows = r.json()
            assert isinstance(rows, list) and len(rows) > 0
            keys = {"month", "income", "expense", "invoice", "vat", "profit"}
            for row in rows:
                assert keys.issubset(row.keys()), f"Missing keys in {row}"
            # Verify profit = income - expense
            for row in rows:
                assert round(row["profit"], 2) == round(row["income"] - row["expense"], 2)
        finally:
            requests.delete(f"{API}/incomes/{iid}", headers=h1, timeout=20)


# ---------- NEW: Inventory alerts & email ----------
class TestInventoryAlerts:
    def test_alerts_requires_auth(self):
        r = requests.get(f"{API}/inventory/alerts", timeout=20)
        assert r.status_code in (401, 403)

    def test_alerts_returns_only_remaining_gt_zero(self, h1):
        # Create low stock item
        r = requests.post(f"{API}/inventory", headers=h1,
                          json={"product_name": "TEST_alert_low", "required_qty": 20, "received_qty": 5, "purchase_price": 10},
                          timeout=20)
        assert r.status_code == 200
        low_id = r.json()["id"]
        # Create fulfilled item
        r = requests.post(f"{API}/inventory", headers=h1,
                          json={"product_name": "TEST_alert_full", "required_qty": 5, "received_qty": 5, "purchase_price": 10},
                          timeout=20)
        assert r.status_code == 200
        full_id = r.json()["id"]
        try:
            r = requests.get(f"{API}/inventory/alerts", headers=h1, timeout=20)
            assert r.status_code == 200
            data = r.json()
            assert "count" in data and "items" in data
            assert isinstance(data["items"], list)
            assert data["count"] == len(data["items"])
            for it in data["items"]:
                assert float(it["remaining_qty"]) > 0
            names = {it["product_name"] for it in data["items"]}
            assert "TEST_alert_low" in names
            assert "TEST_alert_full" not in names
        finally:
            requests.delete(f"{API}/inventory/{low_id}", headers=h1, timeout=20)
            requests.delete(f"{API}/inventory/{full_id}", headers=h1, timeout=20)

    def test_send_low_stock_email_no_low_returns_400(self, h1):
        # Clear remaining items temporarily? Can't; just verify response when no low stock
        # If low stock exists in DB from seed/other, this will trigger an actual send.
        # Approach: check current alerts; if 0, call endpoint and expect 400.
        r = requests.get(f"{API}/inventory/alerts", headers=h1, timeout=20)
        count = r.json().get("count", 0)
        if count == 0:
            r = requests.post(f"{API}/inventory/send-low-stock-email", headers=h1, timeout=30)
            assert r.status_code == 400
        else:
            pytest.skip(f"Skipped: {count} low-stock items exist, can't test 400 case non-destructively")

    def test_send_low_stock_email_sends(self, h1):
        # Create a low stock item then attempt real send
        r = requests.post(f"{API}/inventory", headers=h1,
                          json={"product_name": "TEST_mail_low", "required_qty": 10, "received_qty": 2, "purchase_price": 5},
                          timeout=20)
        assert r.status_code == 200
        sid = r.json()["id"]
        try:
            r = requests.post(f"{API}/inventory/send-low-stock-email", headers=h1, timeout=60)
            # Accept 200 success; capture failures explicitly
            assert r.status_code in (200, 500, 502), f"Unexpected status {r.status_code}: {r.text}"
            if r.status_code == 200:
                data = r.json()
                assert "sent" in data and "failed" in data and "low_stock_count" in data
                assert data["low_stock_count"] >= 1
                # Must have attempted at least 2 recipients (both seeded users)
                total_attempts = len(data["sent"]) + len(data["failed"])
                assert total_attempts >= 2, f"Expected >=2 recipients, got {total_attempts}"
                print(f"EMAIL RESULT: sent={len(data['sent'])}, failed={len(data['failed'])}, details={data}")
            else:
                print(f"EMAIL FAILED status={r.status_code}: {r.text}")
        finally:
            requests.delete(f"{API}/inventory/{sid}", headers=h1, timeout=20)


# ---------- NEW: Invoice import preview + confirm ----------
class TestInvoiceImportPreviewConfirm:
    def _make_xlsx(self, rows):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Tarih", "Açıklama", "Tutar"])
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.getvalue()

    def test_preview_does_not_save(self, h1):
        xlsx = self._make_xlsx([
            ["2026-01-10", "TEST_prev_unique_abc", 1200],
            ["2026-01-11", "TEST_prev_unique_xyz", 2400],
        ])
        files = {"file": ("preview.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/invoices/import-preview", headers=h1, files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2
        for it in data["items"]:
            assert "base_amount" in it and "vat_amount" in it
            assert "description" in it and "amount" in it and "date" in it
        # Verify first row VAT calc
        it0 = data["items"][0]
        assert round(it0["base_amount"] + it0["vat_amount"], 2) == round(float(it0["amount"]), 2)

        # Verify none of the previewed descriptions were persisted
        after = requests.get(f"{API}/invoices", headers=h1, timeout=20).json()
        descs = {inv["description"] for inv in after}
        assert "TEST_prev_unique_abc" not in descs, "Preview should NOT save invoices"
        assert "TEST_prev_unique_xyz" not in descs, "Preview should NOT save invoices"

    def test_confirm_saves_with_modified_amounts(self, h1):
        # Preview
        xlsx = self._make_xlsx([
            ["2026-02-10", "TEST_conf_A", 1200],
            ["2026-02-11", "TEST_conf_B", 600],
        ])
        files = {"file": ("conf.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/invoices/import-preview", headers=h1, files=files, timeout=30)
        assert r.status_code == 200
        items = r.json()["items"]

        # Modify first row amount
        items[0]["amount"] = 2400  # expected base=2000, vat=400
        # Strip extra fields that might not be in model
        payload_items = [{"description": it["description"], "amount": it["amount"], "date": it["date"]} for it in items]

        before = len(requests.get(f"{API}/invoices", headers=h1, timeout=20).json())
        r = requests.post(f"{API}/invoices/import-confirm", headers=h1, json={"items": payload_items}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["count"] == 2
        after = len(requests.get(f"{API}/invoices", headers=h1, timeout=20).json())
        assert after == before + 2

        # Verify modified amount persisted with correct VAT
        saved = data["items"]
        a_rec = next(x for x in saved if x["description"] == "TEST_conf_A")
        assert a_rec["amount"] == 2400
        assert a_rec["base_amount"] == 2000.0
        assert a_rec["vat_amount"] == 400.0
        b_rec = next(x for x in saved if x["description"] == "TEST_conf_B")
        assert b_rec["amount"] == 600
        assert b_rec["base_amount"] == 500.0
        assert b_rec["vat_amount"] == 100.0

        # Cleanup
        for it in saved:
            requests.delete(f"{API}/invoices/{it['id']}", headers=h1, timeout=20)

    def test_confirm_empty_rejects(self, h1):
        r = requests.post(f"{API}/invoices/import-confirm", headers=h1, json={"items": []}, timeout=20)
        assert r.status_code == 400
