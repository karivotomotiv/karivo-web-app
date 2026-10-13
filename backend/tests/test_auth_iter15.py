"""Iter-15 auth tests: new creds, forgot/verify/reset flows, lockout, admin endpoints, change-password.
Uses direct DB manipulation for reset-code to avoid real emails."""
import os
import hashlib
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
JWT_SECRET = os.environ["JWT_SECRET"]

MURAT_EMAIL = "muratcaliskan8585@gmail.com"
MURAT_PW = "Adalina.2026"
OZKAN_EMAIL = "ozkannkaymaz2@gmail.com"
OZKAN_PW = "Ozkan.25"

mongo = MongoClient(os.environ["MONGO_URL"])
db = mongo[os.environ["DB_NAME"]]


def _hash_code(code: str) -> str:
    return hashlib.sha256(f"{JWT_SECRET}:{code}".encode()).hexdigest()


def _insert_reset_token(user_id: str, code: str, *, minutes_ago: int = 2,
                         expires_in_min: int = 60, used: bool = False, attempts: int = 0) -> str:
    now = datetime.now(timezone.utc)
    # invalidate any existing unused tokens
    db.password_reset_tokens.update_many({"user_id": user_id, "used": False}, {"$set": {"used": True}})
    tok_id = str(uuid.uuid4())
    db.password_reset_tokens.insert_one({
        "id": tok_id,
        "user_id": user_id,
        "code_hash": _hash_code(code),
        "attempts": attempts,
        "used": used,
        "created_at": (now - timedelta(minutes=minutes_ago)).isoformat(),
        "expires_at": now + timedelta(minutes=expires_in_min),
    })
    return tok_id


def _login(email, pw):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw})


def _get_user(email):
    return db.users.find_one({"email": email}, {"_id": 0})


# ---------- cleanup fixture ----------
@pytest.fixture(scope="module", autouse=True)
def _cleanup_module():
    yield
    # ensure accounts restored to defaults
    db.login_attempts.delete_many({})
    db.password_reset_tokens.delete_many({})


# ---------- login ----------
class TestLogin:
    def test_murat_login_new_creds(self):
        r = _login(MURAT_EMAIL, MURAT_PW)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["email"] == MURAT_EMAIL
        assert data["user"]["name"] == "Murat"
        assert "token" in data

    def test_ozkan_login_new_creds_admin(self):
        r = _login(OZKAN_EMAIL, OZKAN_PW)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "admin"

    def test_old_demo_creds_rejected(self):
        r = _login("murat@karivo.local", "Murat2026!")
        assert r.status_code in (401, 429)
        r = _login("ozkan@karivo.local", "Ozkan2026!")
        assert r.status_code in (401, 429)
        # cleanup login_attempts for these fake emails
        db.login_attempts.delete_one({"email": "murat@karivo.local"})
        db.login_attempts.delete_one({"email": "ozkan@karivo.local"})

    def test_logout(self):
        tok = _login(MURAT_EMAIL, MURAT_PW).json()["token"]
        r = requests.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200


# ---------- forgot/verify/reset ----------
class TestForgotPassword:
    def test_unregistered_email_returns_404(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "yok12345@gmail.com"})
        assert r.status_code == 404
        assert "kayıtlı değil" in r.json().get("detail", "").lower()

    def test_verify_wrong_code_decrements_attempts(self):
        user = _get_user(MURAT_EMAIL)
        _insert_reset_token(user["id"], "123456")
        # wrong attempt
        r = requests.post(f"{API}/auth/verify-reset-code", json={"email": MURAT_EMAIL, "code": "000000"})
        assert r.status_code == 400
        assert "deneme hakkınız kaldı" in r.json()["detail"]
        # cleanup
        db.password_reset_tokens.delete_many({"user_id": user["id"]})

    def test_verify_correct_code(self):
        user = _get_user(MURAT_EMAIL)
        _insert_reset_token(user["id"], "654321")
        r = requests.post(f"{API}/auth/verify-reset-code", json={"email": MURAT_EMAIL, "code": "654321"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        db.password_reset_tokens.delete_many({"user_id": user["id"]})

    def test_expired_code_rejected(self):
        user = _get_user(MURAT_EMAIL)
        _insert_reset_token(user["id"], "222222", expires_in_min=-5)
        r = requests.post(f"{API}/auth/verify-reset-code", json={"email": MURAT_EMAIL, "code": "222222"})
        assert r.status_code == 400
        assert "süresi doldu" in r.json()["detail"].lower() or "geçerli" in r.json()["detail"].lower()
        db.password_reset_tokens.delete_many({"user_id": user["id"]})

    def test_five_wrong_attempts_invalidates(self):
        user = _get_user(MURAT_EMAIL)
        _insert_reset_token(user["id"], "999999", attempts=4)
        # 5th wrong attempt -> after this attempts==5 -> next call rejected
        r = requests.post(f"{API}/auth/verify-reset-code", json={"email": MURAT_EMAIL, "code": "111111"})
        assert r.status_code == 400
        r2 = requests.post(f"{API}/auth/verify-reset-code", json={"email": MURAT_EMAIL, "code": "999999"})
        assert r2.status_code == 400
        assert "fazla hatalı" in r2.json()["detail"].lower() or "yeni kod" in r2.json()["detail"].lower()
        db.password_reset_tokens.delete_many({"user_id": user["id"]})

    def test_reset_password_and_restore_and_token_invalidation(self):
        user = _get_user(MURAT_EMAIL)
        # login first to get token A
        tokA = _login(MURAT_EMAIL, MURAT_PW).json()["token"]
        # verify tokA works
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tokA}"})
        assert me.status_code == 200
        # insert reset code and reset to temp pw
        _insert_reset_token(user["id"], "424242")
        temp_pw = "TempPass123!"
        r = requests.post(f"{API}/auth/reset-password",
                           json={"email": MURAT_EMAIL, "code": "424242", "new_password": temp_pw})
        assert r.status_code == 200, r.text
        # tokA should now be invalid (token_version bumped)
        me2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tokA}"})
        assert me2.status_code == 401
        # login with new temp pw
        r2 = _login(MURAT_EMAIL, temp_pw)
        assert r2.status_code == 200
        # code cannot be reused
        _insert_reset_token(user["id"], "424242", used=True)  # mark used
        r3 = requests.post(f"{API}/auth/reset-password",
                           json={"email": MURAT_EMAIL, "code": "424242", "new_password": "AnotherPass9!"})
        assert r3.status_code == 400
        # restore original password via reset
        _insert_reset_token(user["id"], "515151")
        r4 = requests.post(f"{API}/auth/reset-password",
                           json={"email": MURAT_EMAIL, "code": "515151", "new_password": MURAT_PW})
        assert r4.status_code == 200
        # cleanup
        db.password_reset_tokens.delete_many({"user_id": user["id"]})
        db.login_attempts.delete_many({"email": MURAT_EMAIL})
        # confirm restored
        assert _login(MURAT_EMAIL, MURAT_PW).status_code == 200


# ---------- lockout ----------
class TestLockout:
    def test_fake_email_lockout_after_5_fails(self):
        fake = "kilittest@example.com"
        db.login_attempts.delete_one({"email": fake})
        for i in range(4):
            r = _login(fake, "wrong")
            assert r.status_code == 401, f"attempt {i+1}: {r.status_code}"
        # 5th -> 429
        r5 = _login(fake, "wrong")
        assert r5.status_code == 429
        # subsequent -> still 429
        r6 = _login(fake, "whatever")
        assert r6.status_code == 429
        db.login_attempts.delete_one({"email": fake})


# ---------- admin ----------
class TestAdmin:
    def _tokens(self):
        o = _login(OZKAN_EMAIL, OZKAN_PW).json()["token"]
        m = _login(MURAT_EMAIL, MURAT_PW).json()["token"]
        return o, m

    def test_admin_list_requires_admin(self):
        o, m = self._tokens()
        r_admin = requests.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {o}"})
        assert r_admin.status_code == 200
        emails = [u["email"] for u in r_admin.json()]
        assert OZKAN_EMAIL in emails and MURAT_EMAIL in emails
        r_user = requests.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {m}"})
        assert r_user.status_code == 403

    def test_admin_cannot_change_to_existing_email(self):
        o, _ = self._tokens()
        murat = _get_user(MURAT_EMAIL)
        # try to change Murat's email to Ozkan's
        r = requests.put(f"{API}/admin/users/{murat['id']}",
                         headers={"Authorization": f"Bearer {o}"},
                         json={"name": "Murat", "email": OZKAN_EMAIL})
        assert r.status_code == 400

    def test_admin_updates_murat_name_email_password_then_restores(self):
        o, _ = self._tokens()
        murat = _get_user(MURAT_EMAIL)
        # login murat to get tokA; will be invalidated after admin changes pw
        tokA = _login(MURAT_EMAIL, MURAT_PW).json()["token"]
        new_email = "muratcaliskan8585+alt@gmail.com"
        temp_pw = "TempAdmin9!"
        r = requests.put(f"{API}/admin/users/{murat['id']}",
                         headers={"Authorization": f"Bearer {o}"},
                         json={"name": "MuratX", "email": new_email, "password": temp_pw})
        assert r.status_code == 200, r.text
        # token A invalid
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tokA}"})
        assert me.status_code == 401
        # login with new creds
        assert _login(new_email, temp_pw).status_code == 200
        # RESTORE
        r2 = requests.put(f"{API}/admin/users/{murat['id']}",
                          headers={"Authorization": f"Bearer {o}"},
                          json={"name": "Murat", "email": MURAT_EMAIL, "password": MURAT_PW})
        assert r2.status_code == 200
        db.login_attempts.delete_many({"email": {"$in": [MURAT_EMAIL, new_email]}})
        # confirm restored
        assert _login(MURAT_EMAIL, MURAT_PW).status_code == 200


# ---------- change-password ----------
class TestChangePassword:
    def test_wrong_current_rejected(self):
        tok = _login(MURAT_EMAIL, MURAT_PW).json()["token"]
        r = requests.post(f"{API}/auth/change-password",
                          headers={"Authorization": f"Bearer {tok}"},
                          json={"current_password": "wrongpass!!", "new_password": "NewPass123!"})
        assert r.status_code == 400
        assert "mevcut şifre hatalı" in r.json()["detail"].lower()

    def test_correct_change_returns_new_token_then_restore(self):
        tok = _login(MURAT_EMAIL, MURAT_PW).json()["token"]
        temp = "ChangePass9!"
        r = requests.post(f"{API}/auth/change-password",
                          headers={"Authorization": f"Bearer {tok}"},
                          json={"current_password": MURAT_PW, "new_password": temp})
        assert r.status_code == 200
        new_tok = r.json()["token"]
        # new token works
        assert requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {new_tok}"}).status_code == 200
        # old token invalid
        assert requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
        # RESTORE
        r2 = requests.post(f"{API}/auth/change-password",
                           headers={"Authorization": f"Bearer {new_tok}"},
                           json={"current_password": temp, "new_password": MURAT_PW})
        assert r2.status_code == 200
        db.login_attempts.delete_many({"email": MURAT_EMAIL})
        assert _login(MURAT_EMAIL, MURAT_PW).status_code == 200


# ---------- regression ----------
class TestRegression:
    def test_core_endpoints_accessible(self):
        tok = _login(MURAT_EMAIL, MURAT_PW).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        for ep in ["/sales", "/tires", "/cariler", "/incomes", "/expenses"]:
            r = requests.get(f"{API}{ep}", headers=h)
            assert r.status_code == 200, f"{ep}: {r.status_code}"
