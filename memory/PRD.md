# PRD — Karivo Otomotiv Lastik Satış Yönetim Sistemi

## Original Problem Statement (Pivot, 2026-10)
Orijinal genel küçük-işletme uygulamasından (gelir/gider/fatura/stok/harcama/yapılacaklar) **Karivo Otomotiv lastik satış sistemi**ne pivot edildi:
- **Lastik Stoku**: Marka, model, ebat (ör: 205/55 R16), mevsim (yaz/kis/4mevsim), DOT, adet, alış/satış fiyatı, KDV.
- **Satışlar**: Lastik + cari + adet + indirim; stoktan otomatik düşer, gelir kaydı atar, cari bakiyesini günceller.
- **Cariler**: Müşteri/tedarikçi alacak-borç takibi, "Gelen Ödeme Gir" özelliği.
- **Gelir / Giderler**: Tek sayfada sekmeli birleşik görünüm.
- **Şampiyon AI Asistan**: Yüzen widget; Claude Sonnet 5.5 (metin + tool-calling), OpenAI Whisper (STT), OpenAI TTS Onyx (erkek ses, speed 1.15). Lastik sorguları, finans özeti, araç çağırımı (search_tires, get_stock_summary, get_finance_summary, list_cariler, add_tire, update_tire_stock, add_income, add_expense, list_recent_sales). Yazıcı işlemler kullanıcı onayı (confirmed=true) ister.
- **Belge Yükleme (AI)**: Excel/PDF fatura yükle → LLM lastik verisi çıkarır → onay ekranı → stoğa işleme.
- **E-posta**: Resend ile düşük stok uyarısı + aylık rapor (`.emergent/crons.yml`, her ayın 1'i 09:00 UTC).

## Language
Tüm UI ve iletişim **Türkçe**.

## Architecture
- **Backend**: FastAPI + Motor (MongoDB) — `/app/backend/server.py` (~2490 satır). JWT (bcrypt + PyJWT). `emergentintegrations` + `openai` (Universal Key).
- **Frontend**: React 19 + React Router 7 + axios + shadcn/ui + sonner. Şampiyon widget: `/app/frontend/src/components/SampiyonWidget.jsx`.
- **Auth**: Startup'ta seed edilen 2 kullanıcı (Murat, Özkan). Token `localStorage["ks_token"]`.
- **Key API endpoints**: `/api/sampiyon/chat`, `/api/sampiyon/tts`, `/api/sampiyon/transcribe`, `/api/sampiyon/parse-tire-document`, `/api/sampiyon/import-confirm`, `/api/sales`, `/api/tires`, `/api/cariler`, `/api/invoices/import-preview|import-confirm`.

## DB Schema
- `users`: {email, password_hash, role, user_key}
- `tires`: {brand, model, size, season, dot, quantity, buy_price, sell_price, kdv_rate}
- `cariler`: {name, total_alacak, total_borc, total_odeme, net}
- `sales`: {tire_id, cari_id, qty, price, discount, payment_method}
- `incomes`, `expenses`, `invoices`, `activity_logs`

## Credentials
`/app/memory/test_credentials.md` — murat@karivo.local / Murat2026!, ozkan@karivo.local / Ozkan2026!

## Changelog
- **2026-10 (bu iterasyon)**: Şampiyon kritik hata düzeltmesi — `chat.add_assistant_message` AttributeError ile her takip mesajı 500 veriyordu; geçmiş artık sanitize edilip `LlmChat(initial_messages=...)` ile yükleniyor. Sesli komut stale-state düzeltildi (history snapshot + autoSpeak). TTS hızı 1.15 (backend clamp 0.5-2.0). Sesli komut yanıtı otomatik okunuyor (autoplay engellenirse toast). SEC-001: tüm upload endpoint'lerine limit (10MB, transcribe 25MB), Excel 2000 satır / PDF 100 sayfa limiti. Test: iter-10, backend 4/4 + e2e frontend PASS.
- Daha eski: iter 1-9 — pivot MVP (lastik stoku, cariler, satışlar, birleşik Gelir/Gider, Şampiyon widget, Resend crons).

## Prioritized Backlog
- **P1**: Belge yükleme onay ekranının UI akışını son kullanıcı ile doğrula (backend `/sampiyon/parse-tire-document` + `/import-confirm` hazır; UI iyileştirmesi gerekebilir).
- **P1**: Şampiyon sohbet geçmişinde tool_result eşleşmesi korunmuyor (model önceki araç sonuçlarını sadece metin özetiyle hatırlıyor) — ileride tool-pair persistence.
- **P2**: `SampiyonChatIn.history` için Pydantic alt modeli (şu an List[dict]).
- **P2**: `/sampiyon/chat` için kullanıcı başına rate limit (LLM bütçe koruması).
- **P2**: TTS'i bellekte toplamak yerine doğrudan passthrough stream (daha düşük gecikme).
- **P2**: server.py (~2490 satır) router'lara bölünebilir.

## Known Limitations
- Whisper STT headless ortamda test edilemiyor (getUserMedia yok); sadece buton varlığı doğrulandı.
- CORS `*` — preview same-origin ingress üzerinden çalışıyor.
