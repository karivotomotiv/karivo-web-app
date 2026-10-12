"""Iter-14: Sales edit/delete + 'Diğer' product + oldest open debt (FIFO) tests."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TODAY = "2026-10-12"

MURAT = {"email": "murat@karivo.local", "password": "Murat2026!"}

created = {"tires": [], "cariler": [], "sales": []}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json=MURAT, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def mk_tire(H, **kw):
    data = {"product_type": "lastik", "brand": f"TEST_{uuid.uuid4().hex[:6]}",
            "model": "M1", "size": "205/55R16", "season": "4mevsim",
            "quantity": 20, "buy_price": 500, "sell_price": 1000, "kdv_rate": 20}
    data.update(kw)
    r = requests.post(f"{API}/tires", json=data, headers=H, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    created["tires"].append(d["id"])
    return d


def mk_cari(H, name=None):
    name = name or f"TEST_C_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/cariler", json={"name": name}, headers=H, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    created["cariler"].append(d["id"])
    return d


def mk_sale(H, items, payment, cari_id=None, date=TODAY, note=""):
    body = {"items": items, "payment_method": payment, "cari_id": cari_id,
            "overall_discount": 0, "date": date, "note": note}
    r = requests.post(f"{API}/sales", json=body, headers=H, timeout=15)
    assert r.status_code == 200, r.text
    s = r.json()
    created["sales"].append(s["id"])
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(H):
    yield
    # Delete sales first (they revert stock & remove incomes/cari_tx)
    for sid in list(created["sales"]):
        requests.delete(f"{API}/sales/{sid}", headers=H, timeout=15)
    for tid in list(created["tires"]):
        requests.delete(f"{API}/tires/{tid}", headers=H, timeout=15)
    for cid in list(created["cariler"]):
        requests.delete(f"{API}/cariler/{cid}", headers=H, timeout=15)


# ========== 1. 'Diğer' product validation / create / sell ==========
class TestDigerProduct:
    def test_create_diger_missing_name_400(self, H):
        r = requests.post(f"{API}/tires", json={"product_type": "diger", "name": "",
                                                "category": "Jant", "unit": "adet", "quantity": 5,
                                                "buy_price": 100, "sell_price": 200}, headers=H, timeout=15)
        assert r.status_code == 400

    def test_create_lastik_missing_brand_size_400(self, H):
        r = requests.post(f"{API}/tires", json={"product_type": "lastik", "brand": "", "size": "",
                                                "quantity": 5, "buy_price": 100, "sell_price": 200}, headers=H, timeout=15)
        assert r.status_code == 400

    def test_create_diger_ok(self, H):
        d = mk_tire(H, product_type="diger", name="TEST_Jant_X", category="Jant",
                    unit="takım", brand="TEST_BRND", model="M9", size="",
                    quantity=10, buy_price=800, sell_price=1500)
        assert d["product_type"] == "diger"
        # label = "Ad Marka Model (Kategori)"
        assert d["product_name"] == "TEST_Jant_X TEST_BRND M9 (Jant)"

    def test_put_diger_update(self, H):
        d = mk_tire(H, product_type="diger", name="TEST_Akü_A", category="Akü",
                    unit="adet", brand="VARTA", model="B100", size="",
                    quantity=5, buy_price=1000, sell_price=1800)
        r = requests.put(f"{API}/tires/{d['id']}",
                         json={"product_type": "diger", "name": "TEST_Akü_B", "category": "Akü",
                               "unit": "adet", "brand": "VARTA", "model": "B200",
                               "quantity": 7, "buy_price": 1100, "sell_price": 1900,
                               "kdv_rate": 20}, headers=H, timeout=15)
        assert r.status_code == 200
        assert r.json()["product_name"] == "TEST_Akü_B VARTA B200 (Akü)"
        assert r.json()["quantity"] == 7

    def test_sell_diger_mixed_with_lastik(self, H):
        tire = mk_tire(H, quantity=10)
        diger = mk_tire(H, product_type="diger", name="TEST_Yağ", category="Yağ",
                        unit="litre", brand="Shell", model="Helix", size="",
                        quantity=20, buy_price=50, sell_price=100)
        s = mk_sale(H, [
            {"tire_id": tire["id"], "quantity": 2, "unit_price": 1000, "discount": 0},
            {"tire_id": diger["id"], "quantity": 4, "unit_price": 100, "discount": 0},
        ], payment="nakit")
        assert s["total"] == 2400
        # Stock decreased
        t_after = requests.get(f"{API}/tires", headers=H, timeout=15).json()
        q_tire = next(t["quantity"] for t in t_after if t["id"] == tire["id"])
        q_diger = next(t["quantity"] for t in t_after if t["id"] == diger["id"])
        assert q_tire == 8 and q_diger == 16

    def test_overview_includes_diger_fields_and_threshold(self, H):
        # create a critical qty diger product (threshold=4, qty=3)
        d = mk_tire(H, product_type="diger", name="TEST_Lowstock", category="Yedek",
                    unit="adet", brand="X", model="Y", size="",
                    quantity=3, buy_price=10, sell_price=20)
        ov = requests.get(f"{API}/dashboard/overview", headers=H, timeout=20,
                          params={"start": "2026-10-01", "end": "2026-10-31"}).json()
        stock = ov["stock"]
        assert stock["threshold"] >= 1
        row = next((r for r in stock["critical"] if r["id"] == d["id"]), None)
        assert row is not None, f"diger product not in critical list: {stock['critical']}"
        for k in ("product_type", "name", "category", "unit", "label"):
            assert k in row
        assert row["product_type"] == "diger"
        assert row["category"] == "Yedek"


# ========== 2. Sales PUT (edit) ==========
class TestSaleEdit:
    def test_veresiye_to_nakit_and_back(self, H):
        tire = mk_tire(H, quantity=20)
        cari = mk_cari(H)
        s = mk_sale(H, [{"tire_id": tire["id"], "quantity": 2, "unit_price": 1000, "discount": 0}],
                    payment="veresiye", cari_id=cari["id"])
        assert s["cari_tx_id"] and not s["income_id"]
        old_total = s["total"]

        # Edit → nakit: cari_tx removed, income created
        r = requests.put(f"{API}/sales/{s['id']}", headers=H, timeout=15, json={
            "items": [{"tire_id": tire["id"], "quantity": 2, "unit_price": 1000, "discount": 0}],
            "payment_method": "nakit", "cari_id": None, "overall_discount": 0,
            "date": TODAY, "note": "edited"
        })
        assert r.status_code == 200, r.text
        new_s = r.json()
        assert new_s["income_id"] and not new_s["cari_tx_id"]
        assert new_s["created_by"] == s["created_by"]  # preserved
        assert new_s["updated_at"] and new_s["updated_by_name"]

        # cari_tx deleted → cari has no debt
        c = requests.get(f"{API}/cariler/{cari['id']}", headers=H, timeout=15).json()
        assert c["remaining_alacak"] == 0
        # income record present with description containing total/date
        incs = requests.get(f"{API}/incomes", headers=H, timeout=15).json()
        assert any(abs(i["amount"] - old_total) < 0.01 and i["date"] == TODAY
                   and "Satış" in (i.get("description") or "") for i in incs)

        # Back to veresiye
        r2 = requests.put(f"{API}/sales/{s['id']}", headers=H, timeout=15, json={
            "items": [{"tire_id": tire["id"], "quantity": 2, "unit_price": 1000, "discount": 0}],
            "payment_method": "veresiye", "cari_id": cari["id"], "overall_discount": 0,
            "date": TODAY, "note": "edited2"
        })
        assert r2.status_code == 200
        assert r2.json()["cari_tx_id"] and not r2.json()["income_id"]
        c2 = requests.get(f"{API}/cariler/{cari['id']}", headers=H, timeout=15).json()
        assert abs(c2["remaining_alacak"] - old_total) < 0.01

    def test_qty_increase_within_available(self, H):
        tire = mk_tire(H, quantity=10)  # start stock 10
        s = mk_sale(H, [{"tire_id": tire["id"], "quantity": 3, "unit_price": 500, "discount": 0}], payment="nakit")
        # stock now 7, available for edit = 7 + 3 = 10
        # Increase to 10 (max)
        r = requests.put(f"{API}/sales/{s['id']}", headers=H, timeout=15, json={
            "items": [{"tire_id": tire["id"], "quantity": 10, "unit_price": 500, "discount": 0}],
            "payment_method": "nakit", "cari_id": None, "overall_discount": 0,
            "date": TODAY, "note": ""
        })
        assert r.status_code == 200
        t = requests.get(f"{API}/tires", headers=H, timeout=15).json()
        assert next(x["quantity"] for x in t if x["id"] == tire["id"]) == 0

    def test_qty_exceeds_available_400(self, H):
        tire = mk_tire(H, quantity=5)
        s = mk_sale(H, [{"tire_id": tire["id"], "quantity": 2, "unit_price": 500, "discount": 0}], payment="nakit")
        # available = 3 + 2 = 5; try 6
        r = requests.put(f"{API}/sales/{s['id']}", headers=H, timeout=15, json={
            "items": [{"tire_id": tire["id"], "quantity": 6, "unit_price": 500, "discount": 0}],
            "payment_method": "nakit", "cari_id": None, "overall_discount": 0,
            "date": TODAY, "note": ""
        })
        assert r.status_code == 400

    def test_change_product(self, H):
        t1 = mk_tire(H, quantity=10)
        t2 = mk_tire(H, quantity=10)
        s = mk_sale(H, [{"tire_id": t1["id"], "quantity": 3, "unit_price": 500, "discount": 0}], payment="nakit")
        # Swap to t2
        r = requests.put(f"{API}/sales/{s['id']}", headers=H, timeout=15, json={
            "items": [{"tire_id": t2["id"], "quantity": 4, "unit_price": 600, "discount": 0}],
            "payment_method": "nakit", "cari_id": None, "overall_discount": 0,
            "date": TODAY, "note": ""
        })
        assert r.status_code == 200
        tires = {x["id"]: x["quantity"] for x in requests.get(f"{API}/tires", headers=H, timeout=15).json()}
        assert tires[t1["id"]] == 10  # restored
        assert tires[t2["id"]] == 6

    def test_404_on_missing(self, H):
        r = requests.put(f"{API}/sales/nonexistent-{uuid.uuid4()}", headers=H, timeout=15, json={
            "items": [], "payment_method": "nakit", "overall_discount": 0, "date": TODAY
        })
        assert r.status_code == 404


# ========== 3. Sales DELETE ==========
class TestSaleDelete:
    def test_delete_cash_sale(self, H):
        tire = mk_tire(H, quantity=10)
        s = mk_sale(H, [{"tire_id": tire["id"], "quantity": 2, "unit_price": 1000, "discount": 0}], payment="nakit")
        sid = s["id"]
        inc_id = s["income_id"]

        r = requests.delete(f"{API}/sales/{sid}", headers=H, timeout=15)
        assert r.status_code == 200
        created["sales"].remove(sid)

        # Fully gone from listing & 404 on GET
        assert requests.get(f"{API}/sales/{sid}", headers=H, timeout=15).status_code == 404
        lst = requests.get(f"{API}/sales", headers=H, timeout=15).json()
        assert not any(x["id"] == sid for x in lst)

        # Stock restored
        t = requests.get(f"{API}/tires", headers=H, timeout=15).json()
        assert next(x["quantity"] for x in t if x["id"] == tire["id"]) == 10

        # 'iade' movement present
        mv = requests.get(f"{API}/tires/{tire['id']}/movements", headers=H, timeout=15).json()
        assert any(m["reason"] == "iade" for m in mv)

        # Income gone
        incs = requests.get(f"{API}/incomes", headers=H, timeout=15).json()
        assert not any(i["id"] == inc_id for i in incs)

    def test_delete_veresiye_removes_cari_tx(self, H):
        tire = mk_tire(H, quantity=10)
        cari = mk_cari(H)
        s = mk_sale(H, [{"tire_id": tire["id"], "quantity": 3, "unit_price": 1000, "discount": 0}],
                    payment="veresiye", cari_id=cari["id"])
        sid = s["id"]
        c_before = requests.get(f"{API}/cariler/{cari['id']}", headers=H, timeout=15).json()
        assert c_before["remaining_alacak"] == 3000

        requests.delete(f"{API}/sales/{sid}", headers=H, timeout=15)
        created["sales"].remove(sid)

        c_after = requests.get(f"{API}/cariler/{cari['id']}", headers=H, timeout=15).json()
        assert c_after["remaining_alacak"] == 0


# ========== 4. Oldest open debt FIFO ==========
class TestOldestOpenDebt:
    def test_fifo_full_payment_moves_to_next(self, H):
        cari = mk_cari(H)
        # Create alacak txs directly
        for amt, date in [(3000, "2026-09-01"), (1000, "2026-09-20")]:
            requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
                "type": "alacak", "amount": amt, "date": date, "description": "t"
            })
        # Ödeme 3000 at 2026-09-25
        requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
            "type": "odeme", "amount": 3000, "date": "2026-09-25", "description": "p"
        })
        c = requests.get(f"{API}/cariler/{cari['id']}", headers=H, timeout=15).json()
        assert c["remaining_alacak"] == 1000
        assert c["oldest_open_date"] == "2026-09-20"
        # open_days = 2026-10-12 - 2026-09-20 = 22
        assert c["open_days"] == 22

    def test_fifo_partial_payment(self, H):
        cari = mk_cari(H)
        for amt, date in [(3000, "2026-09-01"), (1000, "2026-09-20")]:
            requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
                "type": "alacak", "amount": amt, "date": date, "description": "t"
            })
        requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
            "type": "odeme", "amount": 1000, "date": "2026-09-25", "description": "p"
        })
        c = requests.get(f"{API}/cariler/{cari['id']}", headers=H, timeout=15).json()
        assert c["remaining_alacak"] == 3000
        assert c["oldest_open_date"] == "2026-09-01"
        assert c["open_days"] == 41

    def test_fully_paid_returns_null(self, H):
        cari = mk_cari(H)
        requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
            "type": "alacak", "amount": 500, "date": "2026-09-01", "description": "t"
        })
        requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
            "type": "odeme", "amount": 500, "date": "2026-09-10", "description": "p"
        })
        c = requests.get(f"{API}/cariler/{cari['id']}", headers=H, timeout=15).json()
        assert c["remaining_alacak"] == 0
        assert c["oldest_open_date"] is None
        assert c["open_days"] is None

    def test_overview_receivables_items_include_oldest(self, H):
        cari = mk_cari(H)
        requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
            "type": "alacak", "amount": 777, "date": "2026-09-15", "description": "t"
        })
        ov = requests.get(f"{API}/dashboard/overview", headers=H, timeout=20,
                          params={"start": "2026-10-01", "end": "2026-10-31"}).json()
        row = next((r for r in ov["receivables"]["items"] if r["id"] == cari["id"]), None)
        assert row is not None
        assert row["oldest_open_date"] == "2026-09-15"
        assert isinstance(row["open_days"], int) and row["open_days"] >= 0

    def test_cariler_list_has_oldest_fields(self, H):
        cari = mk_cari(H)
        requests.post(f"{API}/cariler/{cari['id']}/transactions", headers=H, timeout=15, json={
            "type": "alacak", "amount": 100, "date": "2026-10-01", "description": "t"
        })
        lst = requests.get(f"{API}/cariler", headers=H, timeout=15).json()
        row = next(r for r in lst if r["id"] == cari["id"])
        assert row["oldest_open_date"] == "2026-10-01"
        assert row["open_days"] == 11
