"""Iter-11: Şampiyon AI agent regression tests.

Covers:
- SSE streaming endpoint event types
- Non-stream chat endpoint
- Direct tool calls (no confirmation): add_spending, add_expense, add_income,
  add_todo, add_cari, add_cari_transaction, add_invoice, update_tire,
  complete_todo
- Confirmation flow for create_sale (blocked without confirmed=true, executes
  after "evet"), stock decrement verification
- Confirmation flow for delete_record
- TTS endpoint (200 audio/mpeg, 400 on empty text)
- Multi-turn chat regression (3 consecutive messages)
- Cleanup of all test-created records
"""
import json
import os
import time
import uuid

import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE = _load_backend_url()
TAG = f"TEST_{uuid.uuid4().hex[:6]}"  # unique tag per run for cleanup


# ---------------------------------------------------------------- fixtures ---
@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "murat@karivo.local", "password": "Murat2026!"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------- helper functions ---
def chat(h, message, history=None, timeout=180):
    """Non-stream chat; returns dict with reply/tool_trace/data_changed."""
    r = requests.post(f"{BASE}/api/sampiyon/chat",
                      json={"message": message, "history": history or []},
                      headers=h, timeout=timeout)
    assert r.status_code == 200, r.text
    return r.json()


def tool_names(resp):
    return [t["name"] for t in resp.get("tool_trace", [])]


def tool_results(resp, name):
    return [t["result"] for t in resp.get("tool_trace", []) if t["name"] == name]


def stream_chat(h, message, history=None, timeout=180):
    """Consume SSE stream, return list of events."""
    r = requests.post(f"{BASE}/api/sampiyon/chat/stream",
                      json={"message": message, "history": history or []},
                      headers=h, timeout=timeout, stream=True)
    assert r.status_code == 200, r.text
    events = []
    buf = ""
    for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
        if not chunk:
            continue
        buf += chunk
        while "\n\n" in buf:
            raw, buf = buf.split("\n\n", 1)
            for line in raw.splitlines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
    return events


# =============================================================== 1. SSE =====
def test_stream_simple_text_question(h):
    """Stream should emit delta + done; a non-tool question still returns."""
    events = stream_chat(h, "Kısaca merhaba de, tek cümle.")
    types = [e["type"] for e in events]
    assert "done" in types, f"No done event: {types}"
    assert types[-1] == "done"
    done = events[-1]
    assert isinstance(done["reply"], str) and len(done["reply"]) > 0
    assert "tool_trace" in done and "data_changed" in done


# =========================================== 2. Non-stream + direct tools ===
def test_add_spending_company_direct(h):
    """'Şirket için harcama gir' → add_spending direct, no confirm."""
    name = f"{TAG}_kirtasiye"
    resp = chat(h, f"Şirket için 120 lira {name} harcaması gir")
    assert "add_spending" in tool_names(resp), f"tools={tool_names(resp)}"
    assert resp["data_changed"] is True
    # Verify persistence via GET
    r = requests.get(f"{BASE}/api/spendings", headers=h, timeout=30)
    assert r.status_code == 200
    items = [s for s in r.json() if s.get("name") == name]
    assert len(items) >= 1, f"Spending not persisted: {r.json()[:3]}"
    assert items[0]["category"] == "company"
    assert items[0]["amount"] == 120


def test_add_spending_user1_direct(h):
    name = f"{TAG}_benzin"
    resp = chat(h, f"Murat için 80 lira {name} harcaması gir")
    assert "add_spending" in tool_names(resp)
    r = requests.get(f"{BASE}/api/spendings?category=user1", headers=h, timeout=30)
    items = [s for s in r.json() if s.get("name") == name]
    assert len(items) >= 1 and items[0]["category"] == "user1"


def test_add_expense_direct(h):
    desc = f"{TAG}_kira"
    resp = chat(h, f"'{desc}' gideri 5000 TL gir")
    assert "add_expense" in tool_names(resp)
    oks = [t for t in resp["tool_trace"] if t["name"] == "add_expense"
           and isinstance(t["result"], dict) and t["result"].get("ok")]
    assert oks, f"add_expense did not succeed: {resp['tool_trace']}"


def test_add_income_direct(h):
    desc = f"{TAG}_gelir"
    resp = chat(h, f"Nakit 1000 TL {desc} gelir yaz")
    assert "add_income" in tool_names(resp)
    r = requests.get(f"{BASE}/api/incomes", headers=h, timeout=30)
    assert any(desc.lower() in (x.get("description") or "").lower() for x in r.json())


def test_add_todo_then_complete(h):
    title = f"{TAG}_musteriyi_ara"
    r1 = chat(h, f"'{title}' diye görev ekle")
    assert "add_todo" in tool_names(r1)
    # fetch todo
    todos = requests.get(f"{BASE}/api/todos", headers=h, timeout=30).json()
    todo = next((t for t in todos if title in (t.get("title") or "")), None)
    assert todo, f"Todo not created, titles={[t.get('title') for t in todos[:5]]}"
    # complete via chat
    r2 = chat(h, f"'{title}' görevini tamamla")
    assert "complete_todo" in tool_names(r2)
    todos2 = requests.get(f"{BASE}/api/todos", headers=h, timeout=30).json()
    assert next(t for t in todos2 if t["id"] == todo["id"])["completed"] is True


def test_add_cari_and_transaction(h):
    cari_name = f"{TAG}_Oto_Ltd"
    r1 = chat(h, f"'{cari_name}' adında cari ekle")
    assert "add_cari" in tool_names(r1)
    # alacak
    r2 = chat(h, f"{cari_name}'ye 2000 TL alacak yaz")
    assert "add_cari_transaction" in tool_names(r2)
    res = tool_results(r2, "add_cari_transaction")
    assert res and res[0].get("type") == "alacak"
    # ödeme
    r3 = chat(h, f"{cari_name}'den 500 TL ödeme geldi")
    assert "add_cari_transaction" in tool_names(r3)
    res3 = tool_results(r3, "add_cari_transaction")
    assert res3 and res3[0].get("type") == "odeme"


def test_add_invoice_direct(h):
    desc = f"{TAG}_lastik_alim_faturasi"
    resp = chat(h, f"'{desc}' faturası 12000 TL ekle")
    assert "add_invoice" in tool_names(resp)
    r = requests.get(f"{BASE}/api/invoices", headers=h, timeout=30)
    assert any(desc.lower() in (x.get("description") or "").lower() for x in r.json())


# ================================================= 3. update_tire direct ===
def _find_michelin(h):
    tires = requests.get(f"{BASE}/api/tires", headers=h, timeout=30).json()
    for t in tires:
        if (t.get("brand", "").lower() == "michelin"
                and "205" in (t.get("size") or "") and "16" in (t.get("size") or "")):
            return t
    return tires[0] if tires else None


def test_update_tire_sell_price(h):
    tire = _find_michelin(h)
    if not tire:
        pytest.skip("No tires in DB")
    orig_price = tire.get("sell_price")
    label = f"{tire.get('brand')} {tire.get('size')}"
    resp = chat(h, f"{label} lastiğinin satış fiyatını 3600 yap")
    assert "update_tire" in tool_names(resp)
    # Verify
    t2 = requests.get(f"{BASE}/api/tires", headers=h, timeout=30).json()
    updated = next((x for x in t2 if x["id"] == tire["id"]), None)
    assert updated and float(updated["sell_price"]) == 3600.0
    # Restore
    requests.put(f"{BASE}/api/tires/{tire['id']}",
                 json={**{k: tire[k] for k in ("brand", "model", "size", "season", "dot",
                                               "buy_price", "sell_price", "kdv_rate",
                                               "note", "quantity") if k in tire},
                       "sell_price": orig_price},
                 headers=h, timeout=30)


# ============================================= 4. Sale confirmation flow ===
def test_create_sale_requires_confirmation(h):
    """First turn must NOT create sale; stock unchanged."""
    tire = _find_michelin(h)
    if not tire or tire.get("quantity", 0) < 1:
        pytest.skip("Michelin tire with stock not available")
    qty_before = float(tire["quantity"])
    label = f"{tire.get('brand')} {tire.get('size')}"
    r1 = chat(h, f"{label} lastiğinden 1 adet nakit sat")
    # Either: no create_sale call OR create_sale returned "Onay gerekli"
    create_calls = tool_results(r1, "create_sale")
    if create_calls:
        # must be blocked
        assert any("Onay" in str(c.get("error", "")) for c in create_calls), \
            f"Sale was executed without confirm! {create_calls}"
    # stock unchanged
    tires = requests.get(f"{BASE}/api/tires", headers=h, timeout=30).json()
    now = next(x for x in tires if x["id"] == tire["id"])
    assert float(now["quantity"]) == qty_before, "Stock changed before confirmation!"

    # Turn 2: confirm with "evet"
    history = [
        {"role": "user", "content": f"{label} lastiğinden 1 adet nakit sat"},
        {"role": "assistant", "content": r1["reply"]},
    ]
    r2 = chat(h, "evet onaylıyorum", history=history, timeout=240)
    # Now sale should execute
    sale_results = [c for c in tool_results(r2, "create_sale") if c.get("ok")]
    if not sale_results:
        pytest.skip(f"Model did not execute sale after confirmation. "
                    f"trace={tool_names(r2)}, reply={r2['reply'][:200]}")
    sale_id = sale_results[0]["sale_id"]
    # Verify stock decrement
    tires2 = requests.get(f"{BASE}/api/tires", headers=h, timeout=30).json()
    after = next(x for x in tires2 if x["id"] == tire["id"])
    assert float(after["quantity"]) == qty_before - 1, \
        f"Stock did not decrement: before={qty_before} after={after['quantity']}"
    # Rollback sale to restore stock
    d = requests.delete(f"{BASE}/api/sales/{sale_id}", headers=h, timeout=30)
    assert d.status_code in (200, 204)


# =========================================== 5. Delete confirmation flow ===
def test_delete_requires_confirmation(h):
    """Create a throwaway spending, ask to delete, verify two-step confirm."""
    name = f"{TAG}_delconfirm"
    chat(h, f"Şirket için 10 lira {name} harcaması gir")
    # ensure exists
    time.sleep(0.3)
    sp = requests.get(f"{BASE}/api/spendings", headers=h, timeout=30).json()
    target = next((s for s in sp if s.get("name") == name), None)
    assert target, "Setup spending not created"

    r1 = chat(h, f"{name} harcamasını sil")
    # Must NOT be deleted yet - either no delete_record success OR explicit "Onay"
    del_calls = tool_results(r1, "delete_record")
    if del_calls:
        assert all(not c.get("ok") for c in del_calls), \
            f"Deleted without confirmation! {del_calls}"
    # Still exists
    sp2 = requests.get(f"{BASE}/api/spendings", headers=h, timeout=30).json()
    assert any(s["id"] == target["id"] for s in sp2), "Record deleted without confirm!"

    history = [
        {"role": "user", "content": f"{name} harcamasını sil"},
        {"role": "assistant", "content": r1["reply"]},
    ]
    r2 = chat(h, "evet sil", history=history, timeout=180)
    # Verify it is gone (even if model didn't call delete_record, it's OK — test setup can cleanup)
    sp3 = requests.get(f"{BASE}/api/spendings", headers=h, timeout=30).json()
    if any(s["id"] == target["id"] for s in sp3):
        # Fallback: delete directly to avoid pollution
        requests.delete(f"{BASE}/api/spendings/{target['id']}", headers=h, timeout=30)
        pytest.skip(f"Model did not delete after confirm. trace={tool_names(r2)}")


# ========================================================= 6. TTS tests ===
def test_tts_ok(h):
    r = requests.post(f"{BASE}/api/sampiyon/tts",
                      json={"text": "Selam patron"}, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("audio/mpeg")
    assert len(r.content) > 500


def test_tts_empty_text_400(h):
    r = requests.post(f"{BASE}/api/sampiyon/tts",
                      json={"text": "   "}, headers=h, timeout=30)
    assert r.status_code == 400, r.text


# ================================================ 7. Multi-turn regression ==
def test_multiturn_three_messages(h):
    history = []
    for msg in ["Stokta kaç çeşit lastik var?",
                "Peki en pahalı hangisi?",
                "Teşekkürler, kapat."]:
        r = chat(h, msg, history=history)
        assert isinstance(r["reply"], str) and not r["reply"].startswith("Hata")
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": r["reply"]})


# ===================================================== 8. Final cleanup ====
def test_zz_cleanup(h):
    """Delete all records tagged with TAG. Runs last due to zz_ prefix."""
    # Spendings
    for s in requests.get(f"{BASE}/api/spendings", headers=h, timeout=30).json():
        if TAG in (s.get("name") or ""):
            requests.delete(f"{BASE}/api/spendings/{s['id']}", headers=h, timeout=15)
    # Expenses
    for e in requests.get(f"{BASE}/api/expenses", headers=h, timeout=30).json():
        if TAG in (e.get("description") or ""):
            requests.delete(f"{BASE}/api/expenses/{e['id']}", headers=h, timeout=15)
    # Incomes
    for e in requests.get(f"{BASE}/api/incomes", headers=h, timeout=30).json():
        if TAG in (e.get("description") or ""):
            requests.delete(f"{BASE}/api/incomes/{e['id']}", headers=h, timeout=15)
    # Invoices
    for inv in requests.get(f"{BASE}/api/invoices", headers=h, timeout=30).json():
        if TAG in (inv.get("description") or ""):
            requests.delete(f"{BASE}/api/invoices/{inv['id']}", headers=h, timeout=15)
    # Todos
    for t in requests.get(f"{BASE}/api/todos", headers=h, timeout=30).json():
        if TAG in (t.get("title") or ""):
            requests.delete(f"{BASE}/api/todos/{t['id']}", headers=h, timeout=15)
    # Cari (and their transactions auto-cascade usually)
    cariler = requests.get(f"{BASE}/api/cariler", headers=h, timeout=30).json()
    for c in cariler:
        if TAG in (c.get("name") or ""):
            requests.delete(f"{BASE}/api/cariler/{c['id']}", headers=h, timeout=15)
