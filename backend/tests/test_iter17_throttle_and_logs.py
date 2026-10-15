"""Iter-17: Smart login throttling (per device+IP) and activity-log export/delete."""
import io
import os
import re
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pathlib import Path
from openpyxl import load_workbook
from pymongo import MongoClient
from dotenv import dotenv_values

ENV = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-app-207.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = ENV.get("MONGO_URL") or os.environ.get("MONGO_URL")
DB_NAME = ENV.get("DB_NAME") or os.environ.get("DB_NAME")
ADMIN_EMAIL = ENV.get("USER2_EMAIL")
ADMIN_PASSWORD = ENV.get("USER2_PASSWORD")
MURAT_EMAIL = ENV.get("USER1_EMAIL")
MURAT_PASSWORD = ENV.get("USER1_PASSWORD")

NOBODY = "qa-nobody@example.com"
DEV1 = "qaDev1"
DEV2 = "qaDev2"
DEV3 = "qaDev3"  # clean device used for real-account logins (never used for wrong-password tests)


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    yield db
    cli.close()


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo):
    # Pre-clean throttle and failed logs for the non-existent email
    mongo.login_throttle.delete_many({})
    mongo.login_attempts.delete_many({"email": NOBODY})
    mongo.failed_logins.delete_many({"email": NOBODY})
    # Pre-register qaDev1 and qaDev2 for admin + murat silently to avoid new-device emails
    for email in (ADMIN_EMAIL, MURAT_EMAIL):
        u = mongo.users.find_one({"email": email})
        if not u:
            continue
        for dev in (DEV1, DEV2, DEV3):
            if not mongo.user_devices.find_one({"user_id": u["id"], "device_id": dev}):
                mongo.user_devices.insert_one({
                    "id": str(uuid.uuid4()), "user_id": u["id"], "device_id": dev,
                    "browser": "Chrome", "os": "Linux", "ip": "127.0.0.1",
                    "user_agent": "pytest", "first_seen": datetime.now(timezone.utc).isoformat(),
                    "last_seen": datetime.now(timezone.utc).isoformat(), "last_login_at": None,
                })
    yield
    # Teardown
    mongo.login_throttle.delete_many({})
    mongo.login_attempts.delete_many({"email": NOBODY})
    mongo.failed_logins.delete_many({"email": NOBODY})
    mongo.failed_logins.delete_many({"email": {"$in": [ADMIN_EMAIL, MURAT_EMAIL]}})
    for email in (ADMIN_EMAIL, MURAT_EMAIL):
        u = mongo.users.find_one({"email": email})
        if not u:
            continue
        mongo.user_devices.delete_many({"user_id": u["id"], "device_id": {"$in": [DEV1, DEV2, DEV3]}})
    mongo.activity_logs.delete_many({"id": {"$regex": "^QA-"}})
    mongo.activity_logs.delete_many({"user_name": "QA-TEST"})


def _login(email, password, device_id):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": password, "device_id": device_id})


# ----------------- Throttle tests -----------------

def test_throttle_wrong_email_dev1(mongo):
    # 1st wrong -> 401 (no wait message yet since wait<4)
    r1 = _login(NOBODY, "whatever1", DEV1)
    assert r1.status_code == 401, r1.text

    # Immediate retry -> 429 "saniye sonra"
    r2 = _login(NOBODY, "whatever2", DEV1)
    assert r2.status_code == 429, r2.text
    detail = r2.json()["detail"]
    assert "saniye" in detail or "dakika" in detail
    m = re.search(r"(\d+)\s*saniye", detail)
    assert m, f"Could not parse wait seconds from: {detail}"
    wait_sec = int(m.group(1))
    assert 1 <= wait_sec <= 5, f"Expected ~2s wait on first retry, got {wait_sec}"

    # Wait slightly longer than suggested
    time.sleep(wait_sec + 1)

    # 2nd wrong attempt -> 401, detail should mention 4 saniye
    r3 = _login(NOBODY, "whatever3", DEV1)
    assert r3.status_code == 401, r3.text
    detail3 = r3.json()["detail"]
    assert "4 saniye" in detail3, f"Expected '4 saniye' in: {detail3}"


def test_throttle_different_device_not_blocked(mongo):
    # qaDev1 is now throttled (just failed in previous test). qaDev2 should NOT be throttled.
    r = _login(NOBODY, "nope", DEV2)
    # Expect 401, NOT 429
    assert r.status_code == 401, f"Different device should not be throttled: {r.status_code} {r.text}"


def test_admin_correct_login_bypasses_throttle_on_other_device(mongo):
    # qaDev1 and qaDev2 may still be in throttle window; admin logging in with DEV3 (never used for wrong attempts) should succeed
    # (DEV3 is pre-registered silently, so no new-device email).
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD, DEV3)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and data["user"]["email"] == ADMIN_EMAIL


# ----------------- Export tests -----------------

@pytest.fixture(scope="module")
def admin_token():
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD, DEV3)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def murat_token():
    r = _login(MURAT_EMAIL, MURAT_PASSWORD, DEV3)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def seeded_logs(mongo):
    """Insert fake QA activity-log docs to use in delete/export tests."""
    ids = []
    for i in range(3):
        lid = f"QA-{uuid.uuid4()}"
        ids.append(lid)
        mongo.activity_logs.insert_one({
            "id": lid, "user_id": "qa", "user_name": "QA-TEST",
            "action": "create", "section": "Stok",
            "details": f"QA log #{i}", "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    yield ids
    mongo.activity_logs.delete_many({"id": {"$in": ids}})


def _hdr(tok): return {"Authorization": f"Bearer {tok}"}


EXPECTED_HEADER = ["Tarih / Saat (TSİ)", "Kullanıcı", "İşlem", "Bölüm", "Detay"]


def _parse_xlsx(content: bytes):
    wb = load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    return rows


def test_export_mode_ids(admin_token, seeded_logs):
    r = requests.post(f"{API}/activity-logs/export",
                      json={"mode": "ids", "ids": seeded_logs},
                      headers=_hdr(admin_token))
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/vnd.openxmlformats")
    rows = _parse_xlsx(r.content)
    assert list(rows[0]) == EXPECTED_HEADER
    assert len(rows) - 1 == len(seeded_logs), f"Expected {len(seeded_logs)} data rows, got {len(rows)-1}"


def test_export_mode_all(murat_token):
    r = requests.post(f"{API}/activity-logs/export",
                      json={"mode": "all"},
                      headers=_hdr(murat_token))
    assert r.status_code == 200, r.text
    rows = _parse_xlsx(r.content)
    assert list(rows[0]) == EXPECTED_HEADER
    assert len(rows) >= 1  # at least header


def test_export_mode_range_ok(admin_token):
    start = "2020-01-01T00:00:00+00:00"
    end = datetime.now(timezone.utc).isoformat()
    r = requests.post(f"{API}/activity-logs/export",
                      json={"mode": "range", "start": start, "end": end},
                      headers=_hdr(admin_token))
    assert r.status_code == 200, r.text
    rows = _parse_xlsx(r.content)
    assert list(rows[0]) == EXPECTED_HEADER


def test_export_mode_range_missing_dates_400(admin_token):
    r = requests.post(f"{API}/activity-logs/export",
                      json={"mode": "range"},
                      headers=_hdr(admin_token))
    assert r.status_code == 400, r.text


# ----------------- Delete tests -----------------

def test_delete_non_admin_forbidden(murat_token, seeded_logs):
    r = requests.post(f"{API}/activity-logs/delete",
                      json={"mode": "ids", "ids": seeded_logs},
                      headers=_hdr(murat_token))
    assert r.status_code == 403, r.text


def test_delete_admin_ids_on_test_logs(admin_token, mongo):
    # Insert a fresh pair of QA logs to delete via API
    doomed = []
    for i in range(2):
        lid = f"QA-{uuid.uuid4()}"
        doomed.append(lid)
        mongo.activity_logs.insert_one({
            "id": lid, "user_id": "qa", "user_name": "QA-TEST",
            "action": "delete", "section": "Stok",
            "details": f"QA doomed #{i}", "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    r = requests.post(f"{API}/activity-logs/delete",
                      json={"mode": "ids", "ids": doomed},
                      headers=_hdr(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 2
    # Verify persistence
    remaining = mongo.activity_logs.count_documents({"id": {"$in": doomed}})
    assert remaining == 0
