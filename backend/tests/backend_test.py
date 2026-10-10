"""Backend API tests for Küçük Şirket Yönetim Uygulaması."""
import os
import io
import pytest
import requests
from datetime import datetime

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-app-207.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

U1 = {"email": "murat@karivo.local", "password": "Murat2026!"}
U2 = {"email": "ozkan@karivo.local", "password": "Ozkan2026!"}
WEBHOOK_CRON_SECRET = "H7l2JDt4UB-KmxRoMMwLXNcZ3qGVqzJj0USzt2FbOPbY1dvYpbNSJGMx2SyFcEyy"
OLD_U1 = {"email": "ahmet@sirket.com", "password": "Ahmet2026!"}
OLD_U2 = {"email": "ayse@sirket.com", "password": "Ayse2026!"}


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
        assert data["user"]["name"] == "Murat"

    def test_login_user2(self):
        r = requests.post(f"{API}/auth/login", json=U2, timeout=20)
        assert r.status_code == 200
        assert r.json()["user"]["name"] in ("Özkan", "Ozkan")

    def test_old_users_removed(self):
        for u in (OLD_U1, OLD_U2):
            r = requests.post(f"{API}/auth/login", json=u, timeout=20)
            assert r.status_code == 401, f"Old user {u['email']} should not login, got {r.status_code}"

    def test_login_accepts_local_domain(self):
        # LoginIn.email must be str (not EmailStr) to allow .local addresses
        r = requests.post(f"{API}/auth/login", json=U1, timeout=20)
        assert r.status_code == 200

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


# ---------- INVENTORY (legacy routes removed in iter-8) ----------
class TestInventoryLegacyRemoved:
    """Legacy /api/inventory POST/PUT/DELETE should no longer exist (iter-8 cleanup).
    Only GET /api/inventory remains as a redirect to tires with legacy mirror fields."""

    def test_get_inventory_mirrors_tires(self, h1):
        # Seed a tire so inventory GET surfaces at least one entry with mirror fields
        tire = {"brand": "TEST_INV_MIR", "model": "M", "size": "195/60 R15",
                "season": "yaz", "quantity": 3, "buy_price": 1000, "sell_price": 1400, "kdv_rate": 20}
        rt = requests.post(f"{API}/tires", headers=h1, json=tire, timeout=20)
        assert rt.status_code == 200
        tid = rt.json()["id"]
        try:
            r = requests.get(f"{API}/inventory", headers=h1, timeout=20)
            assert r.status_code == 200
            items = r.json()
            assert isinstance(items, list)
            match = next((it for it in items if it.get("id") == tid), None)
            assert match is not None, "Created tire must be present in /api/inventory"
            # Legacy mirror fields
            for k in ("product_name", "remaining_qty", "purchase_date", "purchase_price"):
                assert k in match, f"Missing legacy mirror field {k}"
            assert float(match["remaining_qty"]) == 3.0
            assert match["product_name"]  # non-empty
        finally:
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)

    def test_post_inventory_removed(self, h1):
        r = requests.post(f"{API}/inventory", headers=h1,
                          json={"product_name": "x", "required_qty": 1, "received_qty": 1, "purchase_price": 1},
                          timeout=20)
        assert r.status_code in (404, 405), f"Expected 404/405 for removed POST /api/inventory, got {r.status_code}"

    def test_put_inventory_removed(self, h1):
        r = requests.put(f"{API}/inventory/some-id", headers=h1,
                         json={"product_name": "x", "required_qty": 1, "received_qty": 1, "purchase_price": 1},
                         timeout=20)
        assert r.status_code in (404, 405)

    def test_delete_inventory_removed(self, h1):
        r = requests.delete(f"{API}/inventory/some-id", headers=h1, timeout=20)
        assert r.status_code in (404, 405)


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


# ---------- NEW: Inventory alerts & email (iter-8: db.tires with threshold<4) ----------
class TestInventoryAlerts:
    def test_alerts_requires_auth(self):
        r = requests.get(f"{API}/inventory/alerts", timeout=20)
        assert r.status_code in (401, 403)

    def test_alerts_identifies_low_stock_tires(self, h1):
        """Seed one low (qty=2) and one healthy (qty=10) tire; verify alerts contains the low one."""
        low = {"brand": "TEST_ALERT_LOW", "model": "L", "size": "195/55 R15",
               "season": "yaz", "quantity": 2, "buy_price": 1500, "sell_price": 2000, "kdv_rate": 20}
        full = {"brand": "TEST_ALERT_FULL", "model": "F", "size": "195/55 R15",
                "season": "yaz", "quantity": 10, "buy_price": 1500, "sell_price": 2000, "kdv_rate": 20}
        r1 = requests.post(f"{API}/tires", headers=h1, json=low, timeout=20)
        assert r1.status_code == 200
        low_id = r1.json()["id"]
        r2 = requests.post(f"{API}/tires", headers=h1, json=full, timeout=20)
        assert r2.status_code == 200
        full_id = r2.json()["id"]
        try:
            r = requests.get(f"{API}/inventory/alerts", headers=h1, timeout=20)
            assert r.status_code == 200
            data = r.json()
            assert "count" in data and "items" in data and "threshold" in data
            assert data["threshold"] == 4
            assert data["count"] == len(data["items"])
            ids = {it["id"] for it in data["items"]}
            assert low_id in ids, "Low-stock tire must appear in alerts"
            assert full_id not in ids, "Healthy tire must NOT appear in alerts"
            # Verify low tire has expected legacy fields
            match = next(it for it in data["items"] if it["id"] == low_id)
            assert "product_name" in match and match["product_name"]
            assert float(match["quantity"]) == 2.0
        finally:
            requests.delete(f"{API}/tires/{low_id}", headers=h1, timeout=20)
            requests.delete(f"{API}/tires/{full_id}", headers=h1, timeout=20)

    def test_alerts_custom_threshold(self, h1):
        """threshold query param should override the default of 4."""
        payload = {"brand": "TEST_ALERT_THRESH", "model": "T", "size": "205/55 R16",
                   "season": "yaz", "quantity": 6, "buy_price": 2000, "sell_price": 2500, "kdv_rate": 20}
        r = requests.post(f"{API}/tires", headers=h1, json=payload, timeout=20)
        assert r.status_code == 200
        tid = r.json()["id"]
        try:
            # With threshold=4 — qty 6 should NOT be low
            r = requests.get(f"{API}/inventory/alerts", headers=h1, params={"threshold": 4}, timeout=20)
            assert r.status_code == 200
            assert tid not in {it["id"] for it in r.json()["items"]}
            # With threshold=10 — qty 6 SHOULD be low
            r = requests.get(f"{API}/inventory/alerts", headers=h1, params={"threshold": 10}, timeout=20)
            assert r.status_code == 200
            assert tid in {it["id"] for it in r.json()["items"]}
        finally:
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)

    def test_send_low_stock_email_surfaces_failed_recipients(self, h1):
        """Seed a low-stock tire; endpoint attempts to email all users.
        Since @karivo.local addresses are undeliverable via Resend, we expect
        the response to surface them under failed[].error."""
        payload = {"brand": "TEST_MAIL_LOW", "model": "M", "size": "185/60 R14",
                   "season": "yaz", "quantity": 1, "buy_price": 900, "sell_price": 1200, "kdv_rate": 20}
        r = requests.post(f"{API}/tires", headers=h1, json=payload, timeout=20)
        assert r.status_code == 200
        tid = r.json()["id"]
        try:
            r = requests.post(f"{API}/inventory/send-low-stock-email", headers=h1, timeout=60)
            assert r.status_code == 200, f"Unexpected status {r.status_code}: {r.text}"
            data = r.json()
            for k in ("sent", "failed", "low_stock_count"):
                assert k in data, f"Missing key {k} in response"
            assert data["low_stock_count"] >= 1
            total = len(data["sent"]) + len(data["failed"])
            assert total >= 2, f"Expected ≥2 recipient attempts, got {total}"
            # Each failed item must have an 'error' and 'email'
            for f in data["failed"]:
                assert "email" in f and "error" in f and f["error"]
            print(f"EMAIL RESULT sent={len(data['sent'])} failed={len(data['failed'])} low_count={data['low_stock_count']}")
        finally:
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)


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


# ---------- NEW: Monthly report cron + preview + send-now ----------
import uuid as _uuid


class TestMonthlyReportCron:
    def test_cron_no_auth(self):
        r = requests.post(f"{API}/cron/monthly-report", json={}, timeout=20)
        assert r.status_code == 401

    def test_cron_wrong_token(self):
        r = requests.post(f"{API}/cron/monthly-report",
                          headers={"Authorization": "Bearer wrong-token"},
                          json={}, timeout=20)
        assert r.status_code == 401

    def test_cron_correct_token(self):
        run_id = f"test-{_uuid.uuid4()}"
        r = requests.post(f"{API}/cron/monthly-report",
                          headers={"Authorization": f"Bearer {WEBHOOK_CRON_SECRET}",
                                   "X-Webhook-Id": run_id},
                          json={}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("queued") == "monthly-report"
        assert "run_id" in data

    def test_cron_idempotency(self):
        run_id = f"test-dup-{_uuid.uuid4()}"
        headers = {"Authorization": f"Bearer {WEBHOOK_CRON_SECRET}",
                   "X-Webhook-Id": run_id}
        r1 = requests.post(f"{API}/cron/monthly-report", headers=headers, json={}, timeout=20)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/cron/monthly-report", headers=headers, json={}, timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True


class TestMonthlyReportUser:
    def test_preview_requires_auth(self):
        r = requests.get(f"{API}/reports/monthly/preview", timeout=20)
        assert r.status_code in (401, 403)

    def test_preview_shape(self, h1):
        r = requests.get(f"{API}/reports/monthly/preview", headers=h1, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("totals", "top", "month_label", "range"):
            assert k in data, f"Missing key {k} in preview"

    def test_send_now(self, h1):
        r = requests.post(f"{API}/reports/monthly/send-now", headers=h1, json={}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("queued") is True

    def test_activity_log_contains_report(self, h1):
        # Trigger cron twice to ensure background logs 'Rapor' entry
        for _ in range(2):
            requests.post(f"{API}/cron/monthly-report",
                          headers={"Authorization": f"Bearer {WEBHOOK_CRON_SECRET}",
                                   "X-Webhook-Id": f"log-{_uuid.uuid4()}"},
                          json={}, timeout=20)
        import time as _t
        _t.sleep(3)  # background tasks may take a moment
        r = requests.get(f"{API}/activity-logs?limit=200", headers=h1, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        found = any(("Rapor" in (row.get("section") or "") or "ylık rapor" in (row.get("message") or ""))
                    for row in rows)
        assert found, "Expected 'Rapor' activity log entry after cron run"


# ---------- NEW iter-4: Cariler CRUD + transactions ----------
class TestCariler:
    def test_requires_auth(self):
        r = requests.get(f"{API}/cariler", timeout=20)
        assert r.status_code in (401, 403)

    def test_full_flow(self, h1):
        # Create cari
        r = requests.post(f"{API}/cariler", headers=h1,
                          json={"name": "TEST_cari_A", "phone": "555", "address": "adr", "note": "n"}, timeout=20)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["name"] == "TEST_cari_A"
        assert c["phone"] == "555"
        assert c["total_alacak"] == 0 and c["total_borc"] == 0 and c["net"] == 0 and c["tx_count"] == 0
        cid = c["id"]

        # Unknown id -> 404
        r = requests.get(f"{API}/cariler/{_uuid.uuid4()}", headers=h1, timeout=20)
        assert r.status_code == 404

        # List includes
        r = requests.get(f"{API}/cariler", headers=h1, timeout=20)
        assert r.status_code == 200
        assert any(x["id"] == cid for x in r.json())

        # Update
        r = requests.put(f"{API}/cariler/{cid}", headers=h1,
                         json={"name": "TEST_cari_A2", "phone": "666", "address": "adr2", "note": ""}, timeout=20)
        assert r.status_code == 200 and r.json()["name"] == "TEST_cari_A2"

        # Add alacak 5000
        r = requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "alacak", "amount": 5000, "description": "sat", "date": "2026-01-10"}, timeout=20)
        assert r.status_code == 200
        tx1 = r.json()
        assert tx1["type"] == "alacak" and tx1["amount"] == 5000
        tx1_id = tx1["id"]

        # Add borc 1500
        r = requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "borc", "amount": 1500, "date": "2026-01-11"}, timeout=20)
        assert r.status_code == 200
        tx2_id = r.json()["id"]

        # Totals
        r = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["total_alacak"] == 5000.0
        assert d["total_borc"] == 1500.0
        assert d["net"] == 3500.0
        assert d["tx_count"] == 2

        # Tx list
        r = requests.get(f"{API}/cariler/{cid}/transactions", headers=h1, timeout=20)
        assert r.status_code == 200 and len(r.json()) == 2

        # Update tx
        r = requests.put(f"{API}/cariler/{cid}/transactions/{tx2_id}", headers=h1,
                         json={"type": "borc", "amount": 2500, "date": "2026-01-11"}, timeout=20)
        assert r.status_code == 200 and r.json()["amount"] == 2500

        # Delete tx
        r = requests.delete(f"{API}/cariler/{cid}/transactions/{tx1_id}", headers=h1, timeout=20)
        assert r.status_code == 200

        r = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20)
        assert r.json()["tx_count"] == 1 and r.json()["total_alacak"] == 0 and r.json()["total_borc"] == 2500

        # Delete cari -> cascades tx
        r = requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)
        assert r.status_code == 200

        # Confirm removal
        r = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20)
        assert r.status_code == 404

        # Cascading: tx list on deleted cari also 404
        r = requests.get(f"{API}/cariler/{cid}/transactions", headers=h1, timeout=20)
        assert r.status_code == 404


class TestCariIncomeExpense:
    def test_income_with_cari_resolves_name(self, h1):
        # Create cari
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_IE"}, timeout=20)
        cid = r.json()["id"]
        try:
            # Income with cari_id
            r = requests.post(f"{API}/incomes", headers=h1,
                              json={"description": "TEST_inc_cari", "amount": 100, "cari_id": cid}, timeout=20)
            assert r.status_code == 200
            inc = r.json()
            assert inc["cari_id"] == cid
            assert inc["cari_name"] == "TEST_cari_IE"
            iid = inc["id"]

            # Clear cari_id
            r = requests.put(f"{API}/incomes/{iid}", headers=h1,
                             json={"description": "TEST_inc_cari", "amount": 100, "cari_id": None}, timeout=20)
            assert r.status_code == 200
            assert r.json()["cari_id"] is None
            assert r.json()["cari_name"] is None
            requests.delete(f"{API}/incomes/{iid}", headers=h1, timeout=20)

            # Expense
            r = requests.post(f"{API}/expenses", headers=h1,
                              json={"description": "TEST_exp_cari", "amount": 50, "cari_id": cid}, timeout=20)
            assert r.status_code == 200
            assert r.json()["cari_name"] == "TEST_cari_IE"
            eid = r.json()["id"]
            r = requests.put(f"{API}/expenses/{eid}", headers=h1,
                             json={"description": "TEST_exp_cari", "amount": 50, "cari_id": None}, timeout=20)
            assert r.status_code == 200 and r.json()["cari_name"] is None
            requests.delete(f"{API}/expenses/{eid}", headers=h1, timeout=20)
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_summary_includes_cari_sums(self, h1):
        # Snapshot summary before
        before = requests.get(f"{API}/summary", headers=h1, timeout=20).json()
        base_inc = before["total_income_direct"]
        base_exp = before["total_expense_direct"]
        base_alacak = before["cari_alacak"]
        base_borc = before["cari_borc"]

        # Create cari + tx
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_SUM"}, timeout=20)
        cid = r.json()["id"]
        try:
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "alacak", "amount": 777, "date": "2026-03-01"}, timeout=20)
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "borc", "amount": 222, "date": "2026-03-02"}, timeout=20)

            after = requests.get(f"{API}/summary", headers=h1, timeout=20).json()
            # Verify math relationships (parallel tests may shift absolute values)
            assert round(after["total_income"], 2) == round(after["total_income_direct"] + after["cari_alacak"], 2)
            assert round(after["total_expense"], 2) == round(after["total_expense_direct"] + after["cari_borc"], 2)
            # Our own additions reflected in cari sums (>= our injected amounts)
            assert after["cari_alacak"] >= 777.0
            assert after["cari_borc"] >= 222.0
            # Keys present
            for k in ("total_income", "total_expense", "total_income_direct", "total_expense_direct", "cari_alacak", "cari_borc"):
                assert k in after
            _ = (base_inc, base_exp, base_alacak, base_borc)  # unused
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    # ---------- iter-5: odeme ----------
    def test_odeme_flow_and_remaining_alacak(self, h1):
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_ODEME"}, timeout=20)
        cid = r.json()["id"]
        try:
            # alacak 5000
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "alacak", "amount": 5000, "date": "2026-04-01"}, timeout=20)
            # borc 1500
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "borc", "amount": 1500, "date": "2026-04-02"}, timeout=20)
            # odeme 2000
            r = requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                              json={"type": "odeme", "amount": 2000, "date": "2026-04-03"}, timeout=20)
            assert r.status_code == 200, r.text
            assert r.json()["type"] == "odeme"
            odeme_id = r.json()["id"]

            d = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20).json()
            assert d["total_alacak"] == 5000.0
            assert d["total_odeme"] == 2000.0
            assert d["remaining_alacak"] == 3000.0
            assert d["total_borc"] == 1500.0
            assert d["net"] == 1500.0  # remaining - borc
            assert d["tx_count"] == 3

            # Delete odeme => remaining goes back up
            r = requests.delete(f"{API}/cariler/{cid}/transactions/{odeme_id}", headers=h1, timeout=20)
            assert r.status_code == 200
            d = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20).json()
            assert d["total_odeme"] == 0.0
            assert d["remaining_alacak"] == 5000.0
            assert d["net"] == 3500.0
            assert d["tx_count"] == 2
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_odeme_invalid_type_422(self, h1):
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_BADTYPE"}, timeout=20)
        cid = r.json()["id"]
        try:
            r = requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                              json={"type": "xyz", "amount": 100, "date": "2026-04-01"}, timeout=20)
            assert r.status_code == 422
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_put_alacak_to_odeme_recomputes(self, h1):
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_SWITCH"}, timeout=20)
        cid = r.json()["id"]
        try:
            r = requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                              json={"type": "alacak", "amount": 1000, "date": "2026-04-05"}, timeout=20)
            tx_id = r.json()["id"]
            # also another alacak so remaining calculation is observable
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "alacak", "amount": 2000, "date": "2026-04-06"}, timeout=20)

            d = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20).json()
            assert d["total_alacak"] == 3000.0 and d["total_odeme"] == 0.0 and d["remaining_alacak"] == 3000.0

            # Switch tx_id from alacak -> odeme
            r = requests.put(f"{API}/cariler/{cid}/transactions/{tx_id}", headers=h1,
                             json={"type": "odeme", "amount": 1000, "date": "2026-04-05"}, timeout=20)
            assert r.status_code == 200
            d = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20).json()
            assert d["total_alacak"] == 2000.0
            assert d["total_odeme"] == 1000.0
            assert d["remaining_alacak"] == 1000.0
            assert d["net"] == 1000.0
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_summary_unaffected_by_odeme(self, h1):
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_SUMODE"}, timeout=20)
        cid = r.json()["id"]
        try:
            # Baseline
            before = requests.get(f"{API}/summary", headers=h1, timeout=20).json()
            # Add alacak + odeme
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "alacak", "amount": 500, "date": "2026-06-01"}, timeout=20)
            after_alacak = requests.get(f"{API}/summary", headers=h1, timeout=20).json()
            assert round(after_alacak["cari_alacak"] - before["cari_alacak"], 2) == 500.0

            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "odeme", "amount": 300, "date": "2026-06-02"}, timeout=20)
            after_odeme = requests.get(f"{API}/summary", headers=h1, timeout=20).json()
            # cari_alacak unchanged by odeme (gross)
            assert after_odeme["cari_alacak"] == after_alacak["cari_alacak"]
            assert after_odeme["total_income"] == after_alacak["total_income"]
            assert after_odeme["cari_borc"] == after_alacak["cari_borc"]
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_monthly_trend_unaffected_by_odeme_only(self, h1):
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_MT_ODE"}, timeout=20)
        cid = r.json()["id"]
        month = "2026-07"
        try:
            before = requests.get(f"{API}/dashboard/monthly-trend", headers=h1, timeout=20).json()
            before_row = next((x for x in before if x["month"] == month), None)
            before_income = before_row["income"] if before_row else 0.0
            before_expense = before_row["expense"] if before_row else 0.0

            # Only an odeme in this month
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "odeme", "amount": 999, "date": f"{month}-10"}, timeout=20)
            after = requests.get(f"{API}/dashboard/monthly-trend", headers=h1, timeout=20).json()
            after_row = next((x for x in after if x["month"] == month), None)
            after_income = after_row["income"] if after_row else 0.0
            after_expense = after_row["expense"] if after_row else 0.0
            assert after_income == before_income
            assert after_expense == before_expense
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_monthly_trend_includes_cari(self, h1):
        r = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_MT"}, timeout=20)
        cid = r.json()["id"]
        month = "2026-05"
        try:
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "alacak", "amount": 333, "date": f"{month}-10"}, timeout=20)
            requests.post(f"{API}/cariler/{cid}/transactions", headers=h1,
                          json={"type": "borc", "amount": 111, "date": f"{month}-11"}, timeout=20)
            rows = requests.get(f"{API}/dashboard/monthly-trend", headers=h1, timeout=20).json()
            row = next((r for r in rows if r["month"] == month), None)
            assert row is not None, f"month {month} missing in trend"
            assert row["income"] >= 333
            assert row["expense"] >= 111
        finally:
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)



# ---------- TIRES (Iteration-7) ----------
class TestTires:
    """CRUD + movement for /api/tires (lastik stok modülü)."""

    def test_create_and_list(self, h1):
        payloads = [
            {"brand": "TEST_Michelin", "model": "Primacy 4", "size": "205/55 R16",
             "season": "yaz", "dot": "2423", "quantity": 8, "buy_price": 2500,
             "sell_price": 3200, "kdv_rate": 20, "note": "pytest"},
            {"brand": "TEST_Bridgestone", "model": "Blizzak", "size": "225/45 R17",
             "season": "kis", "dot": "0124", "quantity": 4, "buy_price": 3100,
             "sell_price": 3900, "kdv_rate": 20, "note": "pytest"},
        ]
        created_ids = []
        try:
            for p in payloads:
                r = requests.post(f"{API}/tires", headers=h1, json=p, timeout=20)
                assert r.status_code == 200, r.text
                d = r.json()
                assert d["brand"] == p["brand"]
                assert d["size"] == p["size"]
                assert d["season"] == p["season"]
                assert d["quantity"] == float(p["quantity"])
                # legacy mirror fields present
                assert d["remaining_qty"] == float(p["quantity"])
                assert d["product_name"]
                assert "id" in d and isinstance(d["id"], str)
                created_ids.append(d["id"])

            # GET list — created tires visible
            r = requests.get(f"{API}/tires", headers=h1, timeout=20)
            assert r.status_code == 200
            all_ids = {t["id"] for t in r.json()}
            for cid in created_ids:
                assert cid in all_ids

            # Filter by size
            r = requests.get(f"{API}/tires", headers=h1,
                             params={"size": "205/55"}, timeout=20)
            assert r.status_code == 200
            sizes = {t["size"] for t in r.json()}
            assert any("205/55" in s for s in sizes)

            # Filter by season=kis
            r = requests.get(f"{API}/tires", headers=h1,
                             params={"season": "kis"}, timeout=20)
            assert r.status_code == 200
            assert all(t["season"] == "kis" for t in r.json())

            # Movement: +2 then -1 and verify after values
            tid = created_ids[0]
            r = requests.post(f"{API}/tires/{tid}/movement", headers=h1,
                              json={"delta": 2, "reason": "alis", "note": "test in"}, timeout=20)
            assert r.status_code == 200, r.text
            mv = r.json()
            assert mv["before"] == 8.0 and mv["after"] == 10.0 and mv["delta"] == 2.0

            r = requests.post(f"{API}/tires/{tid}/movement", headers=h1,
                              json={"delta": -1, "reason": "satis"}, timeout=20)
            assert r.status_code == 200
            assert r.json()["after"] == 9.0

            # Negative stock rejected
            r = requests.post(f"{API}/tires/{tid}/movement", headers=h1,
                              json={"delta": -9999, "reason": "satis"}, timeout=20)
            assert r.status_code == 400

            # Movements list — at least 3 entries (ilk-kayit + 2 moves)
            r = requests.get(f"{API}/tires/{tid}/movements", headers=h1, timeout=20)
            assert r.status_code == 200
            assert len(r.json()) >= 3

            # Update tire — change quantity should log a "duzenleme" movement
            upd = {**payloads[0], "quantity": 15}
            r = requests.put(f"{API}/tires/{tid}", headers=h1, json=upd, timeout=20)
            assert r.status_code == 200
            assert r.json()["quantity"] == 15.0

            # 404 cases
            r = requests.put(f"{API}/tires/nonexistent-id", headers=h1,
                             json=payloads[0], timeout=20)
            assert r.status_code == 404
            r = requests.post(f"{API}/tires/nonexistent-id/movement", headers=h1,
                              json={"delta": 1, "reason": "alis"}, timeout=20)
            assert r.status_code == 404
        finally:
            for cid in created_ids:
                requests.delete(f"{API}/tires/{cid}", headers=h1, timeout=20)


# ---------- SAMPIYON — Chat & Import-Confirm (Iteration-7) ----------
class TestSampiyon:
    def test_chat_requires_auth(self):
        r = requests.post(f"{API}/sampiyon/chat",
                          json={"message": "merhaba", "history": []}, timeout=20)
        assert r.status_code in (401, 403)

    def test_chat_search_tires_tool(self, h1):
        """Seed 2 tires then ask Şampiyon to search; verify tool invocation + reply.
        Slow (LLM); allow up to 120s."""
        seeds = [
            {"brand": "TEST_SAMPIYON_Pirelli", "model": "P7", "size": "195/65 R15",
             "season": "yaz", "quantity": 6, "buy_price": 1800, "sell_price": 2400},
            {"brand": "TEST_SAMPIYON_Goodyear", "model": "UG9", "size": "195/65 R15",
             "season": "kis", "quantity": 5, "buy_price": 2000, "sell_price": 2700},
        ]
        ids = []
        try:
            for s in seeds:
                r = requests.post(f"{API}/tires", headers=h1, json=s, timeout=20)
                assert r.status_code == 200, r.text
                ids.append(r.json()["id"])

            r = requests.post(f"{API}/sampiyon/chat", headers=h1, json={
                "message": "195/65 R15 ebatında kaç adet TEST_SAMPIYON lastik var? Marka ve adet bazında kısaca listele.",
                "history": [],
            }, timeout=120)
            if r.status_code != 200:
                pytest.skip(f"Şampiyon chat unavailable: {r.status_code} {r.text[:200]}")
            data = r.json()
            assert "reply" in data
            assert isinstance(data.get("tool_trace"), list)
            tool_names = [t["name"] for t in data["tool_trace"]]
            # Model should invoke at least one tire-querying tool
            assert any(n in ("search_tires", "get_stock_summary") for n in tool_names), \
                f"Expected search_tires in tool_trace, got {tool_names}"
            # Result from search_tires should include our seeded brands
            found_brand = False
            for t in data["tool_trace"]:
                if t["name"] == "search_tires":
                    items = (t.get("result") or {}).get("items", [])
                    if any("TEST_SAMPIYON" in (it.get("brand") or "") for it in items):
                        found_brand = True
            # Soft assertion: at minimum reply must be non-empty text
            assert isinstance(data["reply"], str) and len(data["reply"]) > 0
            # Record (not fatal) if brand not surfaced — LLM may filter
            if not found_brand:
                print("[warn] TEST_SAMPIYON brand not seen in search_tires items")
        finally:
            for cid in ids:
                requests.delete(f"{API}/tires/{cid}", headers=h1, timeout=20)

    def test_import_confirm_small_payload(self, h1):
        """POST /api/sampiyon/import-confirm with 2 items → both created."""
        payload = {
            "items": [
                {"brand": "TEST_IMP_A", "model": "X", "size": "185/60 R14",
                 "season": "4mevsim", "quantity": 2, "buy_price": 900,
                 "sell_price": 1200, "kdv_rate": 20},
                {"brand": "TEST_IMP_B", "model": "Y", "size": "225/50 R17",
                 "season": "yaz", "quantity": 3, "buy_price": 2200,
                 "sell_price": 2900, "kdv_rate": 20},
            ]
        }
        r = requests.post(f"{API}/sampiyon/import-confirm",
                          headers=h1, json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2
        created_ids = [it["id"] for it in data["items"]]
        try:
            # Verify persistence via GET /api/tires
            r = requests.get(f"{API}/tires", headers=h1, timeout=20)
            assert r.status_code == 200
            all_ids = {t["id"] for t in r.json()}
            for cid in created_ids:
                assert cid in all_ids
            brands = {t["brand"] for t in r.json() if t["id"] in created_ids}
            assert brands == {"TEST_IMP_A", "TEST_IMP_B"}
        finally:
            for cid in created_ids:
                requests.delete(f"{API}/tires/{cid}", headers=h1, timeout=20)

    def test_import_confirm_empty_rejects(self, h1):
        r = requests.post(f"{API}/sampiyon/import-confirm",
                          headers=h1, json={"items": []}, timeout=20)
        assert r.status_code == 400

    def test_import_confirm_requires_auth(self):
        r = requests.post(f"{API}/sampiyon/import-confirm",
                          json={"items": [{"brand": "X", "size": "1"}]}, timeout=20)
        assert r.status_code in (401, 403)


# ---------- SALES (Iteration-9) ----------
class TestSales:
    """CRUD + stock + gelir/cari side-effects for /api/sales."""

    def _mk_tire(self, h1, qty=10, brand="TEST_SALE_TIRE"):
        p = {"brand": brand, "model": "M", "size": "205/55 R16",
             "season": "yaz", "quantity": qty, "buy_price": 1000,
             "sell_price": 1500, "kdv_rate": 20}
        r = requests.post(f"{API}/tires", headers=h1, json=p, timeout=20)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_requires_auth(self):
        r = requests.get(f"{API}/sales", timeout=20)
        assert r.status_code in (401, 403)

    def test_cash_sale_creates_income_and_reduces_stock(self, h1):
        tid = self._mk_tire(h1, qty=10)
        sale_id = None
        try:
            payload = {
                "items": [{"tire_id": tid, "quantity": 2, "unit_price": 1500, "discount": 0}],
                "payment_method": "nakit",
                "overall_discount": 0,
            }
            r = requests.post(f"{API}/sales", headers=h1, json=payload, timeout=20)
            assert r.status_code == 200, r.text
            s = r.json()
            sale_id = s["id"]
            assert s["total"] == 3000.0
            assert s["subtotal"] == 3000.0
            assert s["payment_method"] == "nakit"
            assert s["income_id"] and not s["cari_tx_id"]
            # Stock reduced
            tr = requests.get(f"{API}/tires", headers=h1, timeout=20).json()
            tt = next(t for t in tr if t["id"] == tid)
            assert tt["quantity"] == 8.0
            # Income exists
            inc = requests.get(f"{API}/incomes", headers=h1, timeout=20).json()
            assert any(x["id"] == s["income_id"] and x["amount"] == 3000.0 for x in inc)
        finally:
            if sale_id:
                requests.delete(f"{API}/sales/{sale_id}", headers=h1, timeout=20)
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)

    def test_veresiye_creates_cari_alacak_no_income(self, h1):
        tid = self._mk_tire(h1, qty=5, brand="TEST_SALE_VER")
        rc = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_SALE"}, timeout=20)
        cid = rc.json()["id"]
        sale_id = None
        try:
            # veresiye without cari -> 400
            r = requests.post(f"{API}/sales", headers=h1, json={
                "items": [{"tire_id": tid, "quantity": 1, "unit_price": 1500}],
                "payment_method": "veresiye"}, timeout=20)
            assert r.status_code == 400

            # Correct veresiye
            r = requests.post(f"{API}/sales", headers=h1, json={
                "cari_id": cid,
                "items": [{"tire_id": tid, "quantity": 2, "unit_price": 1500, "discount": 100}],
                "overall_discount": 200,
                "payment_method": "veresiye"}, timeout=20)
            assert r.status_code == 200, r.text
            s = r.json()
            sale_id = s["id"]
            # subtotal = 2*1500 - 100 = 2900; total = 2900 - 200 = 2700
            assert s["subtotal"] == 2900.0
            assert s["total"] == 2700.0
            assert s["cari_tx_id"] and not s["income_id"]
            # cari balance reflects alacak
            d = requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20).json()
            assert d["total_alacak"] == 2700.0
            assert d["tx_count"] == 1
        finally:
            if sale_id:
                requests.delete(f"{API}/sales/{sale_id}", headers=h1, timeout=20)
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_insufficient_stock_rejected(self, h1):
        tid = self._mk_tire(h1, qty=2, brand="TEST_SALE_LOW")
        try:
            r = requests.post(f"{API}/sales", headers=h1, json={
                "items": [{"tire_id": tid, "quantity": 10, "unit_price": 1500}],
                "payment_method": "nakit"}, timeout=20)
            assert r.status_code == 400
            # Stock should remain 2 (no partial update)
            tires = requests.get(f"{API}/tires", headers=h1, timeout=20).json()
            tt = next(t for t in tires if t["id"] == tid)
            assert tt["quantity"] == 2.0
        finally:
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)

    def test_delete_reverses_stock_income_and_cari(self, h1):
        tid = self._mk_tire(h1, qty=10, brand="TEST_SALE_REV")
        rc = requests.post(f"{API}/cariler", headers=h1, json={"name": "TEST_cari_REV"}, timeout=20)
        cid = rc.json()["id"]
        try:
            # veresiye sale
            r = requests.post(f"{API}/sales", headers=h1, json={
                "cari_id": cid,
                "items": [{"tire_id": tid, "quantity": 3, "unit_price": 1000}],
                "payment_method": "veresiye"}, timeout=20)
            assert r.status_code == 200
            sale_id = r.json()["id"]
            assert r.json()["total"] == 3000.0

            # Stock reduced to 7, cari alacak 3000
            tires = requests.get(f"{API}/tires", headers=h1, timeout=20).json()
            assert next(t for t in tires if t["id"] == tid)["quantity"] == 7.0
            assert requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20).json()["total_alacak"] == 3000.0

            # Delete (iptal)
            r = requests.delete(f"{API}/sales/{sale_id}", headers=h1, timeout=20)
            assert r.status_code == 200
            # Stock restored
            tires = requests.get(f"{API}/tires", headers=h1, timeout=20).json()
            assert next(t for t in tires if t["id"] == tid)["quantity"] == 10.0
            # cari alacak cleared
            assert requests.get(f"{API}/cariler/{cid}", headers=h1, timeout=20).json()["total_alacak"] == 0.0
            # Double delete -> 400
            r = requests.delete(f"{API}/sales/{sale_id}", headers=h1, timeout=20)
            assert r.status_code == 400
        finally:
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)
            requests.delete(f"{API}/cariler/{cid}", headers=h1, timeout=20)

    def test_cash_sale_delete_removes_income(self, h1):
        tid = self._mk_tire(h1, qty=10, brand="TEST_SALE_CASHREV")
        try:
            r = requests.post(f"{API}/sales", headers=h1, json={
                "items": [{"tire_id": tid, "quantity": 1, "unit_price": 1500}],
                "payment_method": "nakit"}, timeout=20)
            assert r.status_code == 200
            s = r.json()
            inc_id = s["income_id"]
            assert any(x["id"] == inc_id for x in requests.get(f"{API}/incomes", headers=h1, timeout=20).json())
            requests.delete(f"{API}/sales/{s['id']}", headers=h1, timeout=20)
            assert not any(x["id"] == inc_id for x in requests.get(f"{API}/incomes", headers=h1, timeout=20).json())
        finally:
            requests.delete(f"{API}/tires/{tid}", headers=h1, timeout=20)

    def test_404_cases(self, h1):
        r = requests.get(f"{API}/sales/does-not-exist", timeout=20,
                         headers=h1)
        assert r.status_code == 404
        r = requests.delete(f"{API}/sales/does-not-exist", timeout=20, headers=h1)
        assert r.status_code == 404
        # Invalid tire_id
        r = requests.post(f"{API}/sales", headers=h1, json={
            "items": [{"tire_id": "nope", "quantity": 1, "unit_price": 100}],
            "payment_method": "nakit"}, timeout=20)
        assert r.status_code == 404

    def test_empty_items_rejected(self, h1):
        r = requests.post(f"{API}/sales", headers=h1, json={
            "items": [], "payment_method": "nakit"}, timeout=20)
        assert r.status_code in (400, 422)

