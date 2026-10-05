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
