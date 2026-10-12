# PRD — Karivo Otomotiv Lastik Satış Yönetim Sistemi

## Original Problem Statement (Pivot, 2026-10)
Orijinal genel küçük-işletme uygulamasından (gelir/gider/fatura/stok/harcama/yapılacaklar) **Karivo Otomotiv lastik satış sistemi**ne pivot edildi:
- **Lastik Stoku**: Marka, model, ebat (ör: 205/55 R16), mevsim (yaz/kis/4mevsim), DOT, adet, alış/satış fiyatı, KDV.
- **Satışlar**: Lastik + cari + adet + indirim; stoktan otomatik düşer, gelir kaydı atar, cari bakiyesini günceller.
- **Cariler**: Müşteri/tedarikçi alacak-borç takibi, "Gelen Ödeme Gir" özelliği.
- **Gelir / Giderler**: Tek sayfada sekmeli birleşik görünüm.
- **Şampiyon AI Asistan**: Yüzen widget; Gemini 3 Flash (metin + tool-calling + streaming), OpenAI Whisper (STT), gpt-4o-mini-tts (ash, doğal Türkçe erkek ton). Lastik sorguları, finans özeti, araç çağırımı (search_tires, get_stock_summary, get_finance_summary, list_cariler, add_tire, update_tire_stock, add_income, add_expense, list_recent_sales). Yazıcı işlemler kullanıcı onayı (confirmed=true) ister.
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
- **2026-10-12 (iter-17)**: Mükerrer birleştirme: `GET /api/tires/duplicates` (exact: diğer → normalize kelime kümesi eşit, lastik → marka+model+ebat+mevsim+DOT normalize eşit; similar: diğer alt küme/Jaccard≥0.6, lastik aynı marka+ebat), `POST /api/tires/merge` (adet toplanır, stok hareketleri + satış kalemleri `tire_id` ana ürüne taşınır, 0 adetli 'birlestirme' notu, kaynaklar silinir; lastik↔diğer birleşmez). Stok sayfasında "Mükerrerleri Bul" diyaloğu (`components/stock/DuplicatesDialog.jsx`): ana ürün seçimi, işaretleme, fiyat farkı uyarısı + "Ana ürünü düzenle". Self-test PASS (birleştirme sonrası satış düzenleme dahil).
- **2026-10-12 (iter-16)**: Akıllı ürün eşleştirme: `_norm_tokens` (Türkçe karakter, büyük/küçük harf, kelime sırası, birim normalizasyonu amper/A/Ah→Ah, litre/lt/l→lt, inç/jant→inc, mm) + `_find_similar_products` (exact = aynı kelime kümesi; similar = alt küme veya Jaccard ≥ 0.6). `GET /api/tires/similar`. Şampiyon `add_other_product`: exact → stok girişi; similar → `needs_choice` ile kullanıcıya sorar (target_id / force_new). Stok sayfasında yeni "Diğer" ürün kaydında "Benzer ürün var" diyaloğu (stok girişi / yine de yeni ürün). Self-test (curl + screenshot) PASS.
- **2026-10-12 (iter-15)**: Stok "Diğer" sekmesinde kategori çipleri (mevcut ürünlerden otomatik, "Kategorisiz" dahil) + kategori özet kartları (çeşit, toplam adet, alış/satış değeri); mevsim filtresi Diğer'de gizli. Şampiyon `add_other_product` aracı: aynı isimde Diğer ürün varsa stok girişi (alış hareketi), yoksa yeni ürün; fiyat sorulmaz (0). search_tires artık diğer ürünleri de label ile döner. Self-test (curl + screenshot) PASS.
- **2026-10-12 (iter-14)**: Satışlar: düzenleme (PUT /api/sales/{id}: eski etkiler 'iade' hareketiyle geri alınır, yeni değerler uygulanır; stok kontrolü eski adet dahil) ve kalıcı silme (DELETE: satış kaydı silinir, stok iade hareketiyle geri eklenir, gelir/cari alacak silinir). Pasif `reversed` satışlar temizlendi, artık oluşmuyor. Ürün türü: `product_type` lastik|diger (diğer: name, category, unit), menü/başlık "Stok", "Stok Ekle" menüsü (Lastik Stok / Diğer), tür filtresi; diğer ürünler satılabilir; kritik eşik tüm ürünlere. Cari en eski açık borç (FIFO): `oldest_open_date`, `open_days` → Cariler listesi + Dashboard alacak listesi. Test iter-14: backend 18/18 + frontend PASS.
- **2026-10-12 (iter-13)**: Dashboard v2. Backend: `/api/dashboard/overview?start&end` (dönem finans: gelir/gider/fark [sadece Gelir/Gider kayıtları], satış cirosu [iptal edilmemiş satışlar], tahsilat [peşin satış + cari ödeme], şirket harcaması bilgi amaçlı; anlık stok ve cari alacak [alacak−ödeme>0]; veri tutarlılık uyarıları), `/api/settings/stock` (genel kritik eşik, varsayılan 4, adet ≤ eşik kritik, ≤0 tükendi; alerts + e-posta + Stok sayfası aynı eşiği kullanır), `/api/reports/monthly?month&details`. monthly-trend artık cari alacak eklemiyor, `profit`→`diff`. Aylık e-postada "Net Kâr" → "Gelir − Gider Farkı". Frontend: yeni Dashboard (dönem filtresi Bu ay/Geçen ay/Özel), `components/dashboard/*`, yeni `/aylik-rapor` sayfası, Stok `?tire=` vurgulama, mobil hamburger menü. Kâr gösterilmiyor (kullanıcı kararı). Test iter-13: backend 17/17 + frontend PASS. İşlem günlüğü kullanıcı isteğiyle sıfırlandı; TEST_ önekli iptal edilmiş test satışları ve yetim test stok hareketleri temizlendi.
- **2026-10 (iter-13)**: Şampiyon sohbet geçmişi sunucuda kullanıcı başına (`sampiyon_messages`, GET/DELETE `/api/sampiyon/history`), LLM bağlamı DB'den son 12 mesaj; "Yeni" butonu. Eller Serbest Mod (`hooks/useHandsFree.js`): RMS VAD, 1.2 sn sessizlikte otomatik gönderir, Şampiyon konuşurken kullanıcı konuşursa susar (barge-in), panel kapanınca/düğmeyle kapanır; Whisper halüsinasyon filtresi. Test iter-12: backend 7/7 + frontend PASS.
- **2026-10 (iter-12)**: TTS daha hızlı (talimat "çok hızlı tempo" + oynatma 1.25x). Panel dışına tıklayınca Şampiyon paneli kapanıyor, konuşma korunuyor (beklemede).
- **2026-10 (iter-11)**: Şampiyon tam yetkili + hızlı: Model Gemini 3 Flash (`gemini-3-flash-preview`), SSE streaming (`/api/sampiyon/chat/stream`). Yeni araçlar: add_spending, add_todo, complete_todo, add_cari, add_cari_transaction (cari_name çözümleme), add_invoice, update_tire, create_sale, list_records, delete_record. Ekleme/güncelleme onaysız; sadece satış + silme onay ister. TTS: gpt-4o-mini-tts (voice ash, Türkçe samimi erkek talimatı). Konuşurken tıklama/tuş/yazma → anında susar. Sesli komutta otomatik okuma, yazılıda yok. Şampiyon veri değiştirince açık sayfa otomatik yenilenir (`karivo:data-changed`). Test: backend 15/15 + frontend PASS.
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
