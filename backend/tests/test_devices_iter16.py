"""Iter-16: device recognition + admin force-logout tests.

Fixed device_ids:
  qa-device-1  -> primary (used almost everywhere, pre-registered as known)
  qa-device-2  -> SINGLE new-device test for Murat (sends 1 email each to Murat + Özkan)

Cleanup at the end: db.user_devices with device_id starting with 'qa-', login_attempts for the test accounts.
"""
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

MURAT = {"email": "muratcaliskan8585@gmail.com", "password": "Adalina.2026"}
OZKAN = {"email": "ozkannkaymaz2@gmail.com", "password": "Ozkan.25"}

DEV1 = "qa-device-1"
DEV2 = "qa-device-2"

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


def _login(creds, device_id=DEV1):
    r = requests.post(f"{BASE}/auth/login",
                      json={**creds, "device_id": device_id},
                      headers={"X-Device-Id": device_id})
    r.raise_for_status()
    return r.json()


def _h(token, device_id=DEV1):
    return {"Authorization": f"Bearer {token}", "X-Device-Id": device_id}


# ---- Pre-register qa-device-1 for BOTH users via /auth/device/touch -------
# This guarantees qa-device-1 is treated as known on every subsequent login
# (no spurious emails during the whole suite).

@pytest.fixture(scope="module", autouse=True)
def preregister_devices():
    for creds in (MURAT, OZKAN):
        d = _login(creds, DEV1)
        tok = d["token"]
        # device/touch silently registers device if missing (no email)
        r = requests.post(f"{BASE}/auth/device/touch",
                          json={"device_id": DEV1},
                          headers=_h(tok, DEV1))
        assert r.status_code == 200
    yield
    # cleanup
    db.user_devices.delete_many({"device_id": {"$regex": "^qa-"}})
    db.login_attempts.delete_many({"email": {"$in": [MURAT["email"], OZKAN["email"], "nobody@example.com"]}})


# ---- Basic login/me on known device: no email trigger (device existed) ----

def test_known_device_login_me_ok():
    d = _login(MURAT, DEV1)
    assert "token" in d and d["user"]["email"] == MURAT["email"]
    r = requests.get(f"{BASE}/auth/me", headers=_h(d["token"], DEV1))
    assert r.status_code == 200
    assert r.json()["email"] == MURAT["email"]


# ---- GET /auth/devices: returns only own devices; current=true for header match
def test_devices_list_current_flag():
    d = _login(MURAT, DEV1)
    r = requests.get(f"{BASE}/auth/devices", headers=_h(d["token"], DEV1))
    assert r.status_code == 200
    devs = r.json()
    assert len(devs) >= 1
    current_rows = [x for x in devs if x.get("current")]
    assert len(current_rows) == 1, f"expected exactly one current device, got {current_rows}"
    # device_id must be stripped from response
    assert "device_id" not in devs[0]
    # only Murat's devices -> all belong to Murat (we can't see user_id, but count against DB)
    murat = db.users.find_one({"email": MURAT["email"]})
    db_count = db.user_devices.count_documents({"user_id": murat["id"]})
    assert len(devs) == db_count


# ---- DELETE /auth/devices/{id}: own ok, other -> 404 --------------------
def test_devices_delete_own_and_cross_user_404():
    # create an extra qa device for Murat via touch
    extra = f"qa-tempdel-{uuid.uuid4().hex[:8]}"
    tok = _login(MURAT, DEV1)["token"]
    assert requests.post(f"{BASE}/auth/device/touch",
                        json={"device_id": extra}, headers=_h(tok, DEV1)).status_code == 200
    murat = db.users.find_one({"email": MURAT["email"]})
    row = db.user_devices.find_one({"user_id": murat["id"], "device_id": extra})
    assert row
    # Özkan tries to delete Murat's device -> 404
    oz_tok = _login(OZKAN, DEV1)["token"]
    r = requests.delete(f"{BASE}/auth/devices/{row['id']}", headers=_h(oz_tok, DEV1))
    assert r.status_code == 404
    # Murat deletes own -> ok
    r = requests.delete(f"{BASE}/auth/devices/{row['id']}", headers=_h(tok, DEV1))
    assert r.status_code == 200
    assert db.user_devices.find_one({"id": row["id"]}) is None


# ---- POST /auth/device/touch adds unknown device silently (no email path)
def test_device_touch_adds_silently():
    tok = _login(MURAT, DEV1)["token"]
    newdev = f"qa-touch-{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/auth/device/touch",
                      json={"device_id": newdev}, headers=_h(tok, DEV1))
    assert r.status_code == 200
    murat = db.users.find_one({"email": MURAT["email"]})
    assert db.user_devices.find_one({"user_id": murat["id"], "device_id": newdev}) is not None


# ---- POST /auth/logout-all invalidates old token --------------------------
def test_logout_all_invalidates_token():
    d = _login(MURAT, DEV1)
    tok = d["token"]
    r = requests.post(f"{BASE}/auth/logout-all", headers=_h(tok, DEV1))
    assert r.status_code == 200
    # old token should now 401
    r2 = requests.get(f"{BASE}/auth/me", headers=_h(tok, DEV1))
    assert r2.status_code == 401
    # re-login works
    d2 = _login(MURAT, DEV1)
    r3 = requests.get(f"{BASE}/auth/me", headers=_h(d2["token"], DEV1))
    assert r3.status_code == 200


# ---- Admin force logout ---------------------------------------------------
def test_admin_force_logout_matrix():
    murat_tok = _login(MURAT, DEV1)["token"]
    ozkan_tok = _login(OZKAN, DEV1)["token"]
    murat = db.users.find_one({"email": MURAT["email"]})
    ozkan = db.users.find_one({"email": OZKAN["email"]})

    # Murat (non-admin) tries -> 403
    r = requests.post(f"{BASE}/admin/users/{murat['id']}/logout", headers=_h(murat_tok, DEV1))
    assert r.status_code == 403

    # Özkan on self -> 400
    r = requests.post(f"{BASE}/admin/users/{ozkan['id']}/logout", headers=_h(ozkan_tok, DEV1))
    assert r.status_code == 400

    # Özkan on Murat -> 200, and Murat's old token 401 afterwards
    r = requests.post(f"{BASE}/admin/users/{murat['id']}/logout", headers=_h(ozkan_tok, DEV1))
    assert r.status_code == 200
    r2 = requests.get(f"{BASE}/auth/me", headers=_h(murat_tok, DEV1))
    assert r2.status_code == 401


# ---- admin_list_users returns new activity fields ------------------------
def test_admin_list_users_fields():
    _login(MURAT, DEV1)  # bumps last_active_at
    ozkan_tok = _login(OZKAN, DEV1)["token"]
    r = requests.get(f"{BASE}/admin/users", headers=_h(ozkan_tok, DEV1))
    assert r.status_code == 200
    users = r.json()
    assert len(users) >= 2
    for u in users:
        assert "device_count" in u and isinstance(u["device_count"], int)
        assert "last_active_at" in u
        assert "last_device" in u  # may be None but key present
    murat_row = next(u for u in users if u["email"] == MURAT["email"])
    assert murat_row["device_count"] >= 1
    assert murat_row["last_device"] is not None
    assert "browser" in murat_row["last_device"] and "os" in murat_row["last_device"]


# ---- SINGLE new-device login => real email to Murat + Özkan --------------
# Spec allows exactly this one new-device test. Perform it only ONCE.
def test_new_device_email_sent_once(caplog):
    import logging
    caplog.set_level(logging.ERROR)
    # Ensure qa-device-2 is NOT in DB (clean prior)
    db.user_devices.delete_many({"device_id": DEV2})
    # Login Murat with qa-device-2
    r = requests.post(f"{BASE}/auth/login",
                      json={**MURAT, "device_id": DEV2},
                      headers={"X-Device-Id": DEV2})
    assert r.status_code == 200
    # qa-device-2 registered
    murat = db.users.find_one({"email": MURAT["email"]})
    row = db.user_devices.find_one({"user_id": murat["id"], "device_id": DEV2})
    assert row is not None
    # Give the background email task a chance
    time.sleep(3)
    # No error log for "Yeni cihaz e-postası gönderilemedi" acceptable.
    # We cannot capture backend's own logger via caplog across process boundary,
    # so instead we check: supervisor backend log file.
    import subprocess
    log = subprocess.run(["tail", "-n", "80", "/var/log/supervisor/backend.err.log"],
                        capture_output=True, text=True).stdout + \
          subprocess.run(["tail", "-n", "80", "/var/log/supervisor/backend.out.log"],
                        capture_output=True, text=True).stdout
    assert "Yeni cihaz e-postası gönderilemedi" not in log, log


# ---- Regression: core endpoints still 200 with new get_current_user sig --
@pytest.mark.parametrize("path", ["/sales", "/tires", "/cariler", "/incomes", "/expenses", "/sampiyon/history"])
def test_regression_endpoints(path):
    tok = _login(MURAT, DEV1)["token"]
    r = requests.get(f"{BASE}{path}", headers=_h(tok, DEV1))
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


# ---- forgot-password error on unregistered email still works ------------
def test_forgot_password_unregistered():
    r = requests.post(f"{BASE}/auth/forgot-password", json={"email": "nobody-qa-xyz@example.com"})
    assert r.status_code == 404
