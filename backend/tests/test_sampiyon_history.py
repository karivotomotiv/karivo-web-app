"""Iter-12: Şampiyon chat history persistence + user isolation.

Covers:
- GET /api/sampiyon/history: returns messages (role, content, created_at, tool_names)
  oldest→newest, limited to last 60.
- DELETE /api/sampiyon/history: wipes current user's history.
- POST /api/sampiyon/chat: writes user+assistant into db.sampiyon_messages.
- Context auto-load when body history is empty: 'Benim adım X' then
  'Az önce sana ne sordum?' should recall previous turn.
- User isolation: Murat's history must not appear in Özkan's GET response.
"""
import os
import time
import uuid

import pytest
import requests


def _base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE = _base()


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def murat_h():
    tok = _login("murat@karivo.local", "Murat2026!")
    h = {"Authorization": f"Bearer {tok}"}
    # Start clean
    requests.delete(f"{BASE}/api/sampiyon/history", headers=h, timeout=15)
    return h


@pytest.fixture(scope="module")
def ozkan_h():
    tok = _login("ozkan@karivo.local", "Ozkan2026!")
    h = {"Authorization": f"Bearer {tok}"}
    requests.delete(f"{BASE}/api/sampiyon/history", headers=h, timeout=15)
    return h


def test_history_empty_after_clear(murat_h):
    r = requests.get(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and data == []


def test_chat_persists_user_and_assistant(murat_h):
    marker = f"TEST_MARKER_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{BASE}/api/sampiyon/chat",
                      json={"message": f"Merhaba. Lütfen cevabında '{marker}' kelimesini aynen tekrar et."},
                      headers=murat_h, timeout=120)
    assert r.status_code == 200, r.text
    reply = r.json().get("reply", "")
    assert isinstance(reply, str) and len(reply) > 0

    # history should now have at least user+assistant
    time.sleep(0.3)
    h = requests.get(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15).json()
    assert len(h) >= 2
    # order: oldest → newest
    assert h[-2]["role"] == "user"
    assert h[-1]["role"] == "assistant"
    # schema fields present
    for m in h[-2:]:
        assert "content" in m and "role" in m and "created_at" in m
    assert "tool_names" in h[-1]


def test_context_autoload_from_db(murat_h):
    """Empty history in body ⇒ server loads last N from DB and model has context."""
    # Fresh start
    requests.delete(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15)
    # Turn 1: give a unique fact
    nonce = uuid.uuid4().hex[:8].upper()
    q1 = f"Lütfen bu sayıyı sadece aklında tut, cevap olarak kısaca onayla: {nonce}"
    r1 = requests.post(f"{BASE}/api/sampiyon/chat",
                       json={"message": q1}, headers=murat_h, timeout=120)
    assert r1.status_code == 200, r1.text

    # Turn 2: no history in body → must come from DB
    r2 = requests.post(f"{BASE}/api/sampiyon/chat",
                       json={"message": "Az önce sana hangi sayıyı/kodu söyledim? Sadece kodu söyle."},
                       headers=murat_h, timeout=120)
    assert r2.status_code == 200, r2.text
    reply2 = (r2.json().get("reply") or "").upper()
    assert nonce in reply2, f"Context not recalled from DB; reply={reply2!r}, expected {nonce}"


def test_user_isolation(murat_h, ozkan_h):
    """Murat's messages should NOT be visible in Özkan's history."""
    # Add a unique marker as Murat
    marker = f"TEST_ISOLATION_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/api/sampiyon/chat",
                      json={"message": f"Benim özel notum: {marker}"},
                      headers=murat_h, timeout=120)
    assert r.status_code == 200

    # Özkan should not see it
    o = requests.get(f"{BASE}/api/sampiyon/history", headers=ozkan_h, timeout=15).json()
    joined = " ".join((m.get("content") or "") for m in o)
    assert marker not in joined, "User isolation broken: Murat marker leaked to Özkan"

    # Murat should see it
    m = requests.get(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15).json()
    joined_m = " ".join((x.get("content") or "") for x in m)
    assert marker in joined_m


def test_delete_history(murat_h):
    r = requests.delete(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("deleted"), int)

    # Confirm empty
    h = requests.get(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15).json()
    assert h == []


def test_body_history_overrides_db(murat_h):
    """When history provided in body, DB-loaded history must be ignored."""
    # Seed DB with Murat
    requests.delete(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15)
    requests.post(f"{BASE}/api/sampiyon/chat",
                  json={"message": "Benim adım MURAT_DB"}, headers=murat_h, timeout=120)

    # Now send with explicit different history: model should rely on provided history,
    # which does not mention MURAT_DB, so answer about name should NOT include MURAT_DB.
    custom = [
        {"role": "user", "content": "Merhaba, benim adım FARUK."},
        {"role": "assistant", "content": "Merhaba Faruk, nasıl yardımcı olabilirim?"},
    ]
    r = requests.post(f"{BASE}/api/sampiyon/chat",
                      json={"message": "Benim adım ne?", "history": custom},
                      headers=murat_h, timeout=120)
    assert r.status_code == 200
    reply = (r.json().get("reply") or "").upper()
    assert "FARUK" in reply, f"Body-provided history ignored; reply={reply!r}"


def test_zz_cleanup(murat_h, ozkan_h):
    requests.delete(f"{BASE}/api/sampiyon/history", headers=murat_h, timeout=15)
    requests.delete(f"{BASE}/api/sampiyon/history", headers=ozkan_h, timeout=15)
