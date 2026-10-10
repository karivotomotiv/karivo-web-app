"""Iter-10: Şampiyon chat multi-turn regression (history with assistant)."""
import os
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-app-207.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "murat@karivo.local", "password": "Murat2026!"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


def test_sampiyon_chat_simple(h):
    r = requests.post(f"{BASE}/api/sampiyon/chat",
                      json={"message": "Stokta kaç çeşit lastik var?", "history": []},
                      headers=h, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "reply" in data
    assert isinstance(data["reply"], str) and len(data["reply"]) > 0
    assert not data["reply"].startswith("Hata")
    print("Reply1:", data["reply"][:200])
    return data["reply"]


def test_sampiyon_chat_multiturn_with_assistant_history(h):
    """Regression: previous bug - 2nd message with assistant in history → 500."""
    # Turn 1
    r1 = requests.post(f"{BASE}/api/sampiyon/chat",
                       json={"message": "Stokta kaç çeşit lastik var?", "history": []},
                       headers=h, timeout=120)
    assert r1.status_code == 200, r1.text
    reply1 = r1.json()["reply"]

    # Turn 2 with assistant in history
    history = [
        {"role": "user", "content": "Stokta kaç çeşit lastik var?"},
        {"role": "assistant", "content": reply1},
    ]
    r2 = requests.post(f"{BASE}/api/sampiyon/chat",
                       json={"message": "Peki bu ayki gelir gider özeti ne?", "history": history},
                       headers=h, timeout=120)
    assert r2.status_code == 200, r2.text
    reply2 = r2.json()["reply"]
    assert isinstance(reply2, str) and len(reply2) > 0
    assert not reply2.startswith("Hata")
    print("Reply2:", reply2[:200])


def test_sampiyon_tts(h):
    r = requests.post(f"{BASE}/api/sampiyon/tts",
                      json={"text": "Merhaba, test mesajıdır.", "voice": "onyx", "speed": 1.15},
                      headers=h, timeout=60)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/")
    assert len(r.content) > 500


def test_sampiyon_tts_speed_clamp(h):
    # extreme speed should be clamped silently (no 400)
    r = requests.post(f"{BASE}/api/sampiyon/tts",
                      json={"text": "Test", "speed": 10.0},
                      headers=h, timeout=60)
    assert r.status_code == 200, r.text
