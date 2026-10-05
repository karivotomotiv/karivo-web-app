# PRD — Küçük Şirket Yönetim Uygulaması

## Original Problem Statement
"Küçük bir şirket için gelir-gider, stok, harcama ve görev takip uygulaması yap. İki kullanıcı hesabı olsun, her birinin ayrı giriş ID ve şifresi olsun. Altı ana bölüm olsun: Gelirler, Giderler, Faturalar, Stok, Harcamalar ve Yapılacaklar. Gelirler, Giderler ve Faturalar bölümünde yeni kayıt eklendiğinde tarih otomatik yazılsın ve en alta toplam otomatik hesaplansın. Kayıtlar listelensin, silinebilsin ve düzenlenebilsin. Fatura eklerken tutar girilsin, uygulama %20 KDV'yi otomatik hesaplayıp o aya ait toplam KDV tutarını ayrıca göstersin. Excel veya PDF dosyası yükleyerek faturaları toplu içe aktarma özelliği olsun. Stok bölümünde ürün adı, ihtiyaç miktarı, alınan miktar, alış tarihi, alış fiyatı ve kalan miktar takip edilsin, kalan miktar otomatik hesaplansın. Harcamalar bölümünde üç ayrı sekme olsun: Şirket Harcamaları, Kullanıcı 1 Harcamaları ve Kullanıcı 2 Harcamaları. Her sekmede harcama adı, tutar ve tarih girilsin, en alta toplam otomatik hesaplansın. Yapılacaklar bölümünde görev adı ve not eklenebilsin, yapıldığında tamamlanma tarihi yazılabilsin veya silinebilsin. Her kullanıcının yaptığı tüm işlemler tarih ve saat ile birlikte kayıt altına alınsın ve görüntülenebilsin."

## Architecture
- **Backend**: FastAPI + Motor (MongoDB), JWT (bcrypt + PyJWT), file parsing via `openpyxl` and `pdfplumber`.
- **Frontend**: React 19 + React Router 7 + axios + shadcn/ui + lucide-react + sonner.
- **Auth**: Fixed 2 seeded users (startup event), Bearer token in `Authorization` header. Token stored in `localStorage` under key `ks_token`.

## User Personas
- **Kullanıcı 1 (Ahmet)** and **Kullanıcı 2 (Ayşe)** — small-business co-owners with identical full access across all sections.

## Core Requirements (static)
1. 2 fixed users, separate login IDs/passwords.
2. 6 sections + activity log.
3. Auto date + auto totals for Gelirler, Giderler, Faturalar.
4. Invoice VAT (20%, inclusive): `VAT = amount - amount/1.20`; monthly VAT summary.
5. Excel (.xlsx) and PDF bulk invoice import.
6. Inventory remaining = required − received (auto).
7. 3-tab Spendings (company / user1 / user2).
8. Todos with completed_at timestamp.
9. Full activity audit (user + timestamp per action).

## What's Been Implemented (2026-02-05)
- JWT auth with 2 seeded users (bcrypt).
- All CRUD endpoints for 6 sections + `/api/summary`, `/api/invoices/vat-summary`, `/api/activity-logs`.
- Excel/PDF bulk invoice import (`/api/invoices/import`).
- Dashboard with 4 stat cards + net balance + inventory highlights.
- Full frontend with sidebar navigation, data tables, dialogs, Turkish localization.
- Activity log filtering by user, section, free-text search.
- Testing: 15/15 backend pytest + core frontend flows passed.

## Prioritized Backlog
- **P1**: CSV export (gelir/gider/fatura dışa aktarım), bar/line chart on dashboard, aylık karşılaştırma raporu.
- **P1**: Fatura PDF önizleme (import sırasında satırları onaylama diyaloğu).
- **P2**: KDV oranını yapılandırılabilir yap (bazı ürünler %10, %1).
- **P2**: E-posta ile aylık rapor (Resend entegrasyonu).
- **P2**: Çoklu şirket desteği, kullanıcı yönetimi UI.

## Known Limitations
- Login brute-force lockout eklenmedi (sadece 2 sabit kullanıcı olduğu için düşük risk).
- CORS varsayılan `*` — preview ortamında same-origin ingress üzerinden çalışıyor.
