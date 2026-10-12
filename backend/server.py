"""
Küçük Şirket Yönetim Uygulaması - Backend
FastAPI + MongoDB + JWT Auth
"""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import io
import re
import uuid
import ipaddress
import logging
import jwt
import bcrypt
import httpx
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Request, BackgroundTasks, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# -----------------------------
# Setup
# -----------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 24 * 7  # 7 gün

app = FastAPI(title="Küçük Şirket Yönetim API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -----------------------------
# Helpers
# -----------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Yetkilendirme gerekli")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")

    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    return user

async def log_activity(user: dict, action: str, section: str, details: str = ""):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_name": user.get("name", user.get("email", "")),
        "action": action,  # create, update, delete, import, login, logout
        "section": section,
        "details": details,
        "timestamp": now_iso(),
    }
    await db.activity_logs.insert_one(doc)

# -----------------------------
# Models
# -----------------------------
class LoginIn(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str

class IncomeIn(BaseModel):
    description: str
    amount: float
    date: Optional[str] = None  # ISO date; auto if missing
    cari_id: Optional[str] = None

class IncomeOut(IncomeIn):
    id: str
    created_by: str
    created_by_name: str
    created_at: str
    cari_name: Optional[str] = None

class ExpenseIn(BaseModel):
    description: str
    amount: float
    date: Optional[str] = None
    cari_id: Optional[str] = None

class ExpenseOut(ExpenseIn):
    id: str
    created_by: str
    created_by_name: str
    created_at: str
    cari_name: Optional[str] = None

class InvoiceIn(BaseModel):
    description: str
    amount: float  # KDV dahil toplam
    date: Optional[str] = None

class InvoiceOut(BaseModel):
    id: str
    description: str
    amount: float          # KDV dahil
    base_amount: float     # KDV hariç
    vat_amount: float      # KDV tutarı (%20)
    date: str
    created_by: str
    created_by_name: str
    created_at: str

class InventoryIn(BaseModel):
    product_name: str
    required_qty: float
    received_qty: float
    purchase_date: Optional[str] = None
    purchase_price: float

class InventoryOut(BaseModel):
    id: str
    product_name: str
    required_qty: float
    received_qty: float
    remaining_qty: float
    purchase_date: str
    purchase_price: float
    created_by: str
    created_by_name: str
    created_at: str

SpendingCategory = Literal["company", "user1", "user2"]

class SpendingIn(BaseModel):
    category: SpendingCategory
    name: str
    amount: float
    date: Optional[str] = None

class SpendingOut(SpendingIn):
    id: str
    created_by: str
    created_by_name: str
    created_at: str

class TodoIn(BaseModel):
    title: str
    note: Optional[str] = ""

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None
    completed: Optional[bool] = None

class TodoOut(BaseModel):
    id: str
    title: str
    note: str
    completed: bool
    completed_at: Optional[str] = None
    created_by: str
    created_by_name: str
    created_at: str

# -----------------------------
# Auth routes
# -----------------------------
@api_router.post("/auth/login")
async def login(data: LoginIn):
    email = data.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı")
    token = create_token(user["id"], user["email"])
    await log_activity(user, "login", "auth", f"{user['name']} giriş yaptı")
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
    }

@api_router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return UserOut(id=user["id"], email=user["email"], name=user["name"], role=user["role"])

@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    await log_activity(user, "logout", "auth", f"{user['name']} çıkış yaptı")
    return {"ok": True}

# -----------------------------
# Generic CRUD factory (for Gelirler/Giderler)
# -----------------------------
def _resolve_date(d: Optional[str]) -> str:
    if d:
        return d
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

async def _resolve_cari_name(cari_id: Optional[str]) -> Optional[str]:
    if not cari_id:
        return None
    doc = await db.cariler.find_one({"id": cari_id}, {"_id": 0, "name": 1})
    return doc["name"] if doc else None


# ---- Gelirler ----
@api_router.get("/incomes", response_model=List[IncomeOut])
async def list_incomes(user: dict = Depends(get_current_user)):
    docs = await db.incomes.find({}, {"_id": 0}).sort("date", -1).to_list(5000)
    return docs

@api_router.post("/incomes", response_model=IncomeOut)
async def create_income(data: IncomeIn, user: dict = Depends(get_current_user)):
    cari_name = await _resolve_cari_name(data.cari_id)
    doc = {
        "id": str(uuid.uuid4()),
        "description": data.description,
        "amount": float(data.amount),
        "date": _resolve_date(data.date),
        "cari_id": data.cari_id,
        "cari_name": cari_name,
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.incomes.insert_one(doc)
    extra = f" ({cari_name})" if cari_name else ""
    await log_activity(user, "create", "Gelirler", f"{doc['description']} / {doc['amount']}₺{extra}")
    doc.pop("_id", None)
    return doc

@api_router.put("/incomes/{item_id}", response_model=IncomeOut)
async def update_income(item_id: str, data: IncomeIn, user: dict = Depends(get_current_user)):
    cari_name = await _resolve_cari_name(data.cari_id)
    update = {
        "description": data.description,
        "amount": float(data.amount),
        "cari_id": data.cari_id,
        "cari_name": cari_name,
    }
    if data.date:
        update["date"] = data.date
    res = await db.incomes.find_one_and_update({"id": item_id}, {"$set": update}, return_document=True)
    if not res:
        raise HTTPException(404, "Gelir kaydı bulunamadı")
    await log_activity(user, "update", "Gelirler", f"{data.description} / {data.amount}₺")
    updated = await db.incomes.find_one({"id": item_id}, {"_id": 0})
    return updated

@api_router.delete("/incomes/{item_id}")
async def delete_income(item_id: str, user: dict = Depends(get_current_user)):
    doc = await db.incomes.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Gelir kaydı bulunamadı")
    await db.incomes.delete_one({"id": item_id})
    await log_activity(user, "delete", "Gelirler", f"{doc.get('description','')} / {doc.get('amount',0)}₺")
    return {"ok": True}

# ---- Giderler ----
@api_router.get("/expenses", response_model=List[ExpenseOut])
async def list_expenses(user: dict = Depends(get_current_user)):
    return await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(5000)

@api_router.post("/expenses", response_model=ExpenseOut)
async def create_expense(data: ExpenseIn, user: dict = Depends(get_current_user)):
    cari_name = await _resolve_cari_name(data.cari_id)
    doc = {
        "id": str(uuid.uuid4()),
        "description": data.description,
        "amount": float(data.amount),
        "date": _resolve_date(data.date),
        "cari_id": data.cari_id,
        "cari_name": cari_name,
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(doc)
    extra = f" ({cari_name})" if cari_name else ""
    await log_activity(user, "create", "Giderler", f"{doc['description']} / {doc['amount']}₺{extra}")
    doc.pop("_id", None)
    return doc

@api_router.put("/expenses/{item_id}", response_model=ExpenseOut)
async def update_expense(item_id: str, data: ExpenseIn, user: dict = Depends(get_current_user)):
    cari_name = await _resolve_cari_name(data.cari_id)
    update = {
        "description": data.description,
        "amount": float(data.amount),
        "cari_id": data.cari_id,
        "cari_name": cari_name,
    }
    if data.date:
        update["date"] = data.date
    res = await db.expenses.find_one_and_update({"id": item_id}, {"$set": update})
    if not res:
        raise HTTPException(404, "Gider kaydı bulunamadı")
    await log_activity(user, "update", "Giderler", f"{data.description} / {data.amount}₺")
    return await db.expenses.find_one({"id": item_id}, {"_id": 0})

@api_router.delete("/expenses/{item_id}")
async def delete_expense(item_id: str, user: dict = Depends(get_current_user)):
    doc = await db.expenses.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Gider kaydı bulunamadı")
    await db.expenses.delete_one({"id": item_id})
    await log_activity(user, "delete", "Giderler", f"{doc.get('description','')} / {doc.get('amount',0)}₺")
    return {"ok": True}

# ---- Faturalar ----
def _invoice_breakdown(total_incl: float) -> dict:
    base = round(total_incl / 1.20, 2)
    vat = round(total_incl - base, 2)
    return {"base_amount": base, "vat_amount": vat}

@api_router.get("/invoices", response_model=List[InvoiceOut])
async def list_invoices(user: dict = Depends(get_current_user)):
    return await db.invoices.find({}, {"_id": 0}).sort("date", -1).to_list(5000)

@api_router.post("/invoices", response_model=InvoiceOut)
async def create_invoice(data: InvoiceIn, user: dict = Depends(get_current_user)):
    bd = _invoice_breakdown(float(data.amount))
    doc = {
        "id": str(uuid.uuid4()),
        "description": data.description,
        "amount": float(data.amount),
        "base_amount": bd["base_amount"],
        "vat_amount": bd["vat_amount"],
        "date": _resolve_date(data.date),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.invoices.insert_one(doc)
    await log_activity(user, "create", "Faturalar", f"{doc['description']} / {doc['amount']}₺ (KDV: {doc['vat_amount']}₺)")
    doc.pop("_id", None)
    return doc

@api_router.put("/invoices/{item_id}", response_model=InvoiceOut)
async def update_invoice(item_id: str, data: InvoiceIn, user: dict = Depends(get_current_user)):
    bd = _invoice_breakdown(float(data.amount))
    update = {
        "description": data.description,
        "amount": float(data.amount),
        "base_amount": bd["base_amount"],
        "vat_amount": bd["vat_amount"],
    }
    if data.date:
        update["date"] = data.date
    res = await db.invoices.find_one_and_update({"id": item_id}, {"$set": update})
    if not res:
        raise HTTPException(404, "Fatura bulunamadı")
    await log_activity(user, "update", "Faturalar", f"{data.description} / {data.amount}₺")
    return await db.invoices.find_one({"id": item_id}, {"_id": 0})

@api_router.delete("/invoices/{item_id}")
async def delete_invoice(item_id: str, user: dict = Depends(get_current_user)):
    doc = await db.invoices.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Fatura bulunamadı")
    await db.invoices.delete_one({"id": item_id})
    await log_activity(user, "delete", "Faturalar", f"{doc.get('description','')} / {doc.get('amount',0)}₺")
    return {"ok": True}

@api_router.get("/invoices/vat-summary")
async def vat_summary(user: dict = Depends(get_current_user)):
    """Aylık KDV toplamları."""
    docs = await db.invoices.find({}, {"_id": 0}).to_list(5000)
    summary: dict = {}
    for d in docs:
        month = (d.get("date") or "")[:7]  # YYYY-MM
        if not month:
            continue
        s = summary.setdefault(month, {"month": month, "vat_total": 0.0, "base_total": 0.0, "gross_total": 0.0, "count": 0})
        s["vat_total"] += d.get("vat_amount", 0)
        s["base_total"] += d.get("base_amount", 0)
        s["gross_total"] += d.get("amount", 0)
        s["count"] += 1
    rows = sorted(summary.values(), key=lambda x: x["month"], reverse=True)
    for r in rows:
        r["vat_total"] = round(r["vat_total"], 2)
        r["base_total"] = round(r["base_total"], 2)
        r["gross_total"] = round(r["gross_total"], 2)
    return rows

@api_router.post("/invoices/import")
async def import_invoices(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Excel (.xlsx) veya PDF dosyasından toplu fatura içe aktar.

    Excel beklenen başlıklar (sıra önemsiz): Tarih / Aciklama (veya Açıklama) / Tutar
    PDF: Her satırda tarih (YYYY-MM-DD veya DD.MM.YYYY), açıklama ve tutar bulunur.
    """
    raw = await _read_upload_limited(file)
    filename = (file.filename or "").lower()
    parsed: List[dict] = []

    try:
        if filename.endswith(".xlsx") or filename.endswith(".xlsm"):
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(raw), data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                raise HTTPException(400, "Excel dosyası boş")
            headers = [str(c or "").strip().lower() for c in rows[0]]

            def _find(cands):
                for cand in cands:
                    for i, h in enumerate(headers):
                        if cand in h:
                            return i
                return -1

            idx_date = _find(["tarih", "date"])
            idx_desc = _find(["aciklama", "açıklama", "description", "fatura"])
            idx_amt = _find(["tutar", "amount", "toplam"])
            if idx_amt == -1:
                raise HTTPException(400, "Excel başlıklarında 'Tutar' bulunamadı")

            for r in rows[1:]:
                if r is None:
                    continue
                try:
                    amt_raw = r[idx_amt]
                    if amt_raw in (None, ""):
                        continue
                    amount = float(str(amt_raw).replace(",", ".").replace(" ", ""))
                    desc = str(r[idx_desc]).strip() if idx_desc != -1 and r[idx_desc] is not None else "Fatura"
                    date_val = r[idx_date] if idx_date != -1 else None
                    if hasattr(date_val, "strftime"):
                        date = date_val.strftime("%Y-%m-%d")
                    elif date_val:
                        date = _normalize_date_str(str(date_val))
                    else:
                        date = _resolve_date(None)
                    parsed.append({"description": desc, "amount": amount, "date": date})
                except Exception as e:
                    logger.warning(f"Satır atlandı: {e}")
                    continue

        elif filename.endswith(".pdf"):
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text_all = "\n".join((p.extract_text() or "") for p in pdf.pages)
            # Satır başına: tarih + açıklama + tutar
            for line in text_all.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Tutar: son sayı
                amt_match = re.findall(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+[.,]\d{1,2}|\d+)", line)
                if not amt_match:
                    continue
                try:
                    amount = float(amt_match[-1].replace(".", "").replace(",", ".")) if "," in amt_match[-1] else float(amt_match[-1].replace(",", ""))
                except Exception:
                    continue
                # Tarih
                date_m = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4})", line)
                date = _normalize_date_str(date_m.group(1)) if date_m else _resolve_date(None)
                # Açıklama: satırdan tarih ve tutar çıkarıldıktan sonra
                desc = line
                if date_m:
                    desc = desc.replace(date_m.group(1), "")
                desc = desc.replace(amt_match[-1], "").strip(" -|:")
                if not desc:
                    desc = "Fatura"
                if amount <= 0 or amount > 100_000_000:
                    continue
                parsed.append({"description": desc[:200], "amount": amount, "date": date})
        else:
            raise HTTPException(400, "Yalnızca .xlsx veya .pdf dosyaları desteklenir")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("İçe aktarma hatası")
        raise HTTPException(400, f"Dosya okunamadı: {e}")

    if not parsed:
        raise HTTPException(400, "Dosyada geçerli fatura satırı bulunamadı")

    # Toplu insert
    created = []
    for p in parsed:
        bd = _invoice_breakdown(p["amount"])
        doc = {
            "id": str(uuid.uuid4()),
            "description": p["description"],
            "amount": round(float(p["amount"]), 2),
            "base_amount": bd["base_amount"],
            "vat_amount": bd["vat_amount"],
            "date": p["date"],
            "created_by": user["id"],
            "created_by_name": user["name"],
            "created_at": now_iso(),
        }
        await db.invoices.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)
    await log_activity(user, "import", "Faturalar", f"{len(created)} fatura içe aktarıldı ({file.filename})")
    return {"count": len(created), "items": created}

def _normalize_date_str(s: str) -> str:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return _resolve_date(None)

# ---- Stok (eski /api/inventory CRUD kaldırıldı — /api/tires kullanın) ----

# ---- Cariler ----
CariType = Literal["alacak", "borc", "odeme"]  # alacak = bize borçlu, borc = biz borçluyuz, odeme = gelen ödeme (alacaktan düşer)


class CariIn(BaseModel):
    name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    note: Optional[str] = ""


class CariOut(BaseModel):
    id: str
    name: str
    phone: str
    address: str
    note: str
    total_alacak: float = 0.0
    total_borc: float = 0.0
    total_odeme: float = 0.0
    remaining_alacak: float = 0.0
    net: float = 0.0
    tx_count: int = 0
    oldest_open_date: Optional[str] = None
    open_days: Optional[int] = None
    created_by: str
    created_by_name: str
    created_at: str


class CariTxIn(BaseModel):
    type: CariType
    amount: float
    description: Optional[str] = ""
    date: Optional[str] = None


class CariTxOut(CariTxIn):
    id: str
    cari_id: str
    created_by: str
    created_by_name: str
    created_at: str


def _oldest_open_debt(txs: list, total_odeme: float) -> tuple:
    """Ödemeleri en eski alacaktan başlayarak düşer (FIFO); kapanmamış ilk alacağın tarihi ve gün sayısı."""
    left = float(total_odeme)
    for t in sorted((x for x in txs if x["type"] == "alacak"), key=lambda x: (x.get("date") or "", x.get("created_at") or "")):
        left -= float(t["amount"])
        if left < -0.005:
            d = (t.get("date") or "")[:10]
            try:
                days = (datetime.now(timezone.utc).date() - datetime.strptime(d, "%Y-%m-%d").date()).days
            except ValueError:
                return d or None, None
            return d, max(0, days)
    return None, None


async def _attach_cari_totals(cari_doc: dict) -> dict:
    txs = await db.cari_transactions.find({"cari_id": cari_doc["id"]}, {"_id": 0, "type": 1, "amount": 1, "date": 1, "created_at": 1}).to_list(5000)
    alacak = sum(float(t["amount"]) for t in txs if t["type"] == "alacak")
    borc = sum(float(t["amount"]) for t in txs if t["type"] == "borc")
    odeme = sum(float(t["amount"]) for t in txs if t["type"] == "odeme")
    remaining_alacak = alacak - odeme
    cari_doc["total_alacak"] = round(alacak, 2)
    cari_doc["total_borc"] = round(borc, 2)
    cari_doc["total_odeme"] = round(odeme, 2)
    cari_doc["remaining_alacak"] = round(remaining_alacak, 2)
    cari_doc["net"] = round(remaining_alacak - borc, 2)
    cari_doc["tx_count"] = len(txs)
    cari_doc["oldest_open_date"], cari_doc["open_days"] = _oldest_open_debt(txs, odeme) if remaining_alacak > 0.005 else (None, None)
    return cari_doc


@api_router.get("/cariler", response_model=List[CariOut])
async def list_cariler(user: dict = Depends(get_current_user)):
    docs = await db.cariler.find({}, {"_id": 0}).sort("name", 1).to_list(5000)
    for d in docs:
        await _attach_cari_totals(d)
    return docs


@api_router.post("/cariler", response_model=CariOut)
async def create_cari(data: CariIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name.strip(),
        "phone": (data.phone or "").strip(),
        "address": (data.address or "").strip(),
        "note": (data.note or "").strip(),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.cariler.insert_one(doc)
    doc.pop("_id", None)
    await _attach_cari_totals(doc)
    await log_activity(user, "create", "Cariler", f"{doc['name']}")
    return doc


@api_router.get("/cariler/{cari_id}", response_model=CariOut)
async def get_cari(cari_id: str, user: dict = Depends(get_current_user)):
    doc = await db.cariler.find_one({"id": cari_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Cari bulunamadı")
    await _attach_cari_totals(doc)
    return doc


@api_router.put("/cariler/{cari_id}", response_model=CariOut)
async def update_cari(cari_id: str, data: CariIn, user: dict = Depends(get_current_user)):
    update = {
        "name": data.name.strip(),
        "phone": (data.phone or "").strip(),
        "address": (data.address or "").strip(),
        "note": (data.note or "").strip(),
    }
    res = await db.cariler.find_one_and_update({"id": cari_id}, {"$set": update})
    if not res:
        raise HTTPException(404, "Cari bulunamadı")
    await log_activity(user, "update", "Cariler", f"{update['name']}")
    doc = await db.cariler.find_one({"id": cari_id}, {"_id": 0})
    await _attach_cari_totals(doc)
    return doc


@api_router.delete("/cariler/{cari_id}")
async def delete_cari(cari_id: str, user: dict = Depends(get_current_user)):
    doc = await db.cariler.find_one({"id": cari_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Cari bulunamadı")
    await db.cariler.delete_one({"id": cari_id})
    await db.cari_transactions.delete_many({"cari_id": cari_id})
    await log_activity(user, "delete", "Cariler", f"{doc.get('name', '')}")
    return {"ok": True}


@api_router.get("/cariler/{cari_id}/transactions", response_model=List[CariTxOut])
async def list_cari_tx(cari_id: str, user: dict = Depends(get_current_user)):
    exists = await db.cariler.find_one({"id": cari_id}, {"_id": 0, "id": 1})
    if not exists:
        raise HTTPException(404, "Cari bulunamadı")
    return await db.cari_transactions.find({"cari_id": cari_id}, {"_id": 0}).sort("date", -1).to_list(5000)


@api_router.post("/cariler/{cari_id}/transactions", response_model=CariTxOut)
async def create_cari_tx(cari_id: str, data: CariTxIn, user: dict = Depends(get_current_user)):
    cari = await db.cariler.find_one({"id": cari_id}, {"_id": 0, "name": 1})
    if not cari:
        raise HTTPException(404, "Cari bulunamadı")
    doc = {
        "id": str(uuid.uuid4()),
        "cari_id": cari_id,
        "type": data.type,
        "amount": float(data.amount),
        "description": (data.description or "").strip(),
        "date": _resolve_date(data.date),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.cari_transactions.insert_one(doc)
    doc.pop("_id", None)
    tr_type_map = {"alacak": "Alacak", "borc": "Borç", "odeme": "Gelen Ödeme"}
    tr_type = tr_type_map.get(data.type, data.type)
    await log_activity(user, "create", "Cariler", f"{cari['name']} — {tr_type}: {doc['amount']}₺")
    return doc


@api_router.put("/cariler/{cari_id}/transactions/{tx_id}", response_model=CariTxOut)
async def update_cari_tx(cari_id: str, tx_id: str, data: CariTxIn, user: dict = Depends(get_current_user)):
    update = {
        "type": data.type,
        "amount": float(data.amount),
        "description": (data.description or "").strip(),
    }
    if data.date:
        update["date"] = data.date
    res = await db.cari_transactions.find_one_and_update({"id": tx_id, "cari_id": cari_id}, {"$set": update})
    if not res:
        raise HTTPException(404, "Hareket bulunamadı")
    cari = await db.cariler.find_one({"id": cari_id}, {"_id": 0, "name": 1})
    await log_activity(user, "update", "Cariler", f"{cari['name']} hareket güncellendi")
    return await db.cari_transactions.find_one({"id": tx_id}, {"_id": 0})


@api_router.delete("/cariler/{cari_id}/transactions/{tx_id}")
async def delete_cari_tx(cari_id: str, tx_id: str, user: dict = Depends(get_current_user)):
    doc = await db.cari_transactions.find_one({"id": tx_id, "cari_id": cari_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Hareket bulunamadı")
    await db.cari_transactions.delete_one({"id": tx_id})
    await log_activity(user, "delete", "Cariler", f"Hareket silindi: {doc.get('amount', 0)}₺")
    return {"ok": True}


# ---- Stok (Lastik) ----
TIRE_SEASONS = Literal["yaz", "kis", "4mevsim"]


PRODUCT_TYPES = Literal["lastik", "diger"]


class TireIn(BaseModel):
    product_type: PRODUCT_TYPES = "lastik"
    name: Optional[str] = ""  # diğer ürünler için ürün adı
    category: Optional[str] = ""  # diğer: jant, akü, yağ...
    unit: Optional[str] = "adet"
    brand: Optional[str] = ""
    model: Optional[str] = ""
    size: Optional[str] = ""  # lastik: 205/55 R16
    season: TIRE_SEASONS = "4mevsim"
    dot: Optional[str] = ""  # DOT / üretim yılı
    quantity: float = 0
    buy_price: float = 0
    sell_price: float = 0
    kdv_rate: float = 20
    note: Optional[str] = ""


class TireOut(TireIn):
    id: str
    created_by: str
    created_by_name: str
    created_at: str
    updated_at: Optional[str] = None
    # Legacy stok alanları — geriye dönük uyumluluk için otomatik türetilir
    product_name: Optional[str] = None
    required_qty: Optional[float] = None
    received_qty: Optional[float] = None
    remaining_qty: Optional[float] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None


class TireMovementIn(BaseModel):
    delta: float  # pozitif = giriş, negatif = çıkış
    reason: str  # "alis", "satis", "iade", "sayim-duzeltme", "fire", "diger"
    note: Optional[str] = ""
    date: Optional[str] = None


def _validate_product(data: "TireIn") -> None:
    if data.product_type == "diger":
        if not (data.name or "").strip():
            raise HTTPException(400, "Ürün adı zorunludur")
    elif not (data.brand or "").strip() or not (data.size or "").strip():
        raise HTTPException(400, "Lastik için marka ve ebat zorunludur")


def _product_fields(data: "TireIn") -> dict:
    return {
        "product_type": data.product_type,
        "name": (data.name or "").strip(),
        "category": (data.category or "").strip(),
        "unit": (data.unit or "adet").strip() or "adet",
        "brand": (data.brand or "").strip(),
        "model": (data.model or "").strip(),
        "size": (data.size or "").strip(),
        "season": data.season,
        "dot": (data.dot or "").strip(),
        "note": (data.note or "").strip(),
        "quantity": float(data.quantity),
        "buy_price": float(data.buy_price),
        "sell_price": float(data.sell_price),
        "kdv_rate": float(data.kdv_rate),
    }


def _tire_label(doc: dict) -> str:
    if doc.get("product_type") == "diger":
        parts = [doc.get("name", ""), doc.get("brand", ""), doc.get("model", "")]
        label = " ".join(p for p in parts if p).strip()
        return f"{label} ({doc['category']})" if doc.get("category") else label
    parts = [doc.get("brand", ""), doc.get("model", ""), doc.get("size", "")]
    season_map = {"yaz": "Yaz", "kis": "Kış", "4mevsim": "4 Mevsim"}
    s = season_map.get(doc.get("season"), "")
    if s:
        parts.append(s)
    if doc.get("dot"):
        parts.append(f"DOT:{doc['dot']}")
    return " ".join(p for p in parts if p).strip()


def _tire_as_legacy(doc: dict) -> dict:
    """Eski Stok UI'si ile uyum için ek alanlar."""
    doc["product_name"] = _tire_label(doc)
    doc["remaining_qty"] = float(doc.get("quantity", 0))
    doc["received_qty"] = float(doc.get("quantity", 0))
    doc["required_qty"] = float(doc.get("quantity", 0))
    doc["purchase_date"] = doc.get("created_at", "")[:10] if doc.get("created_at") else ""
    doc["purchase_price"] = float(doc.get("buy_price", 0))
    return doc


@api_router.get("/tires", response_model=List[TireOut])
async def list_tires(
    user: dict = Depends(get_current_user),
    size: Optional[str] = None,
    brand: Optional[str] = None,
    season: Optional[str] = None,
    search: Optional[str] = None,
):
    q: dict = {}
    if size:
        q["size"] = {"$regex": re.escape(size), "$options": "i"}
    if brand:
        q["brand"] = {"$regex": re.escape(brand), "$options": "i"}
    if season:
        q["season"] = season
    docs = await db.tires.find(q, {"_id": 0}).sort("brand", 1).to_list(5000)
    if search:
        s = search.lower()
        docs = [d for d in docs if s in _tire_label(d).lower() or s in (d.get("note") or "").lower()]
    for d in docs:
        _tire_as_legacy(d)
    return docs


@api_router.post("/tires", response_model=TireOut)
async def create_tire(data: TireIn, user: dict = Depends(get_current_user)):
    _validate_product(data)
    doc = _product_fields(data)
    doc.update({
        "id": str(uuid.uuid4()),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    await db.tires.insert_one(doc)
    doc.pop("_id", None)
    _tire_as_legacy(doc)
    await log_activity(user, "create", "Stok", f"{_tire_label(doc)} / {doc['quantity']} adet")
    # İlk kayıt bir "giriş" hareketidir
    await db.stock_movements.insert_one({
        "id": str(uuid.uuid4()),
        "tire_id": doc["id"],
        "tire_label": _tire_label(doc),
        "delta": float(doc["quantity"]),
        "before": 0.0,
        "after": float(doc["quantity"]),
        "reason": "ilk-kayit",
        "note": "Ürün kaydı oluşturuldu",
        "date": now_iso()[:10],
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    })
    return doc


@api_router.put("/tires/{tire_id}", response_model=TireOut)
async def update_tire(tire_id: str, data: TireIn, user: dict = Depends(get_current_user)):
    before = await db.tires.find_one({"id": tire_id}, {"_id": 0})
    if not before:
        raise HTTPException(404, "Ürün bulunamadı")
    _validate_product(data)
    update = {**_product_fields(data), "updated_at": now_iso()}
    await db.tires.update_one({"id": tire_id}, {"$set": update})
    doc = await db.tires.find_one({"id": tire_id}, {"_id": 0})
    _tire_as_legacy(doc)
    # Miktar değiştiyse hareket logu
    if float(before.get("quantity", 0)) != float(update["quantity"]):
        delta = float(update["quantity"]) - float(before.get("quantity", 0))
        await db.stock_movements.insert_one({
            "id": str(uuid.uuid4()),
            "tire_id": tire_id,
            "tire_label": _tire_label(doc),
            "delta": delta,
            "before": float(before.get("quantity", 0)),
            "after": float(update["quantity"]),
            "reason": "duzenleme",
            "note": "Düzenleme ile değişti",
            "date": now_iso()[:10],
            "created_by": user["id"],
            "created_by_name": user["name"],
            "created_at": now_iso(),
        })
    await log_activity(user, "update", "Stok", f"{_tire_label(doc)}")
    return doc


@api_router.delete("/tires/{tire_id}")
async def delete_tire(tire_id: str, user: dict = Depends(get_current_user)):
    doc = await db.tires.find_one({"id": tire_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Lastik bulunamadı")
    await db.tires.delete_one({"id": tire_id})
    await log_activity(user, "delete", "Stok", _tire_label(doc))
    return {"ok": True}


@api_router.post("/tires/{tire_id}/movement")
async def tire_movement(tire_id: str, data: TireMovementIn, user: dict = Depends(get_current_user)):
    doc = await db.tires.find_one({"id": tire_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Lastik bulunamadı")
    before = float(doc.get("quantity", 0))
    after = before + float(data.delta)
    if after < 0:
        raise HTTPException(400, f"Stok eksiye düşemez. Mevcut: {before}, denenen çıkış: {abs(data.delta)}")
    await db.tires.update_one({"id": tire_id}, {"$set": {"quantity": after, "updated_at": now_iso()}})
    mv = {
        "id": str(uuid.uuid4()),
        "tire_id": tire_id,
        "tire_label": _tire_label(doc),
        "delta": float(data.delta),
        "before": before,
        "after": after,
        "reason": data.reason,
        "note": (data.note or "").strip(),
        "date": data.date or now_iso()[:10],
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.stock_movements.insert_one(mv)
    await log_activity(user, "movement", "Stok",
                       f"{_tire_label(doc)}: {before} → {after} ({'+' if data.delta>0 else ''}{data.delta}, {data.reason})")
    mv.pop("_id", None)
    return mv


@api_router.get("/tires/{tire_id}/movements")
async def list_tire_movements(tire_id: str, user: dict = Depends(get_current_user)):
    return await db.stock_movements.find({"tire_id": tire_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


# ---- Satışlar ----
PaymentMethod = Literal["nakit", "kart", "havale", "veresiye"]


class SaleItemIn(BaseModel):
    tire_id: str
    quantity: float
    unit_price: float  # KDV dahil birim satış fiyatı
    discount: float = 0  # satır bazlı indirim TL (ürün toplamından düşer)


class SaleIn(BaseModel):
    cari_id: Optional[str] = None  # veresiye için zorunlu
    items: List[SaleItemIn]
    overall_discount: float = 0  # genel indirim TL
    payment_method: PaymentMethod = "nakit"
    note: Optional[str] = ""
    date: Optional[str] = None


@api_router.get("/sales")
async def list_sales(user: dict = Depends(get_current_user)):
    docs = await db.sales.find({}, {"_id": 0}).sort("date", -1).to_list(2000)
    return docs


@api_router.get("/sales/{sale_id}")
async def get_sale(sale_id: str, user: dict = Depends(get_current_user)):
    doc = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Satış bulunamadı")
    return doc


async def _validate_sale(data: SaleIn, credit: Optional[dict] = None) -> dict:
    """Satış girdisini doğrular. credit: düzenlemede eski satışın iade edilecek adetleri {tire_id: qty}."""
    credit = credit or {}
    if not data.items:
        raise HTTPException(400, "En az bir ürün eklemelisiniz")
    if data.payment_method == "veresiye" and not data.cari_id:
        raise HTTPException(400, "Veresiye satış için cari seçimi zorunludur")
    enriched, need = [], {}
    for it in data.items:
        if it.quantity <= 0 or it.unit_price < 0 or it.discount < 0:
            raise HTTPException(400, "Geçersiz miktar, fiyat veya indirim")
        tire = await db.tires.find_one({"id": it.tire_id}, {"_id": 0})
        if not tire:
            raise HTTPException(404, f"Ürün bulunamadı: {it.tire_id}")
        need[it.tire_id] = need.get(it.tire_id, 0.0) + float(it.quantity)
        available = float(tire.get("quantity", 0)) + float(credit.get(it.tire_id, 0))
        if available < need[it.tire_id]:
            raise HTTPException(400, f"{_tire_label(tire)} için yeterli stok yok (mevcut: {available:g})")
        line_gross = round(float(it.quantity) * float(it.unit_price), 2)
        enriched.append({
            "tire_id": it.tire_id, "tire_label": _tire_label(tire), "quantity": float(it.quantity),
            "unit_price": float(it.unit_price), "discount": float(it.discount),
            "line_total": round(max(0.0, line_gross - float(it.discount)), 2),
        })
    cari = None
    if data.cari_id:
        cari = await db.cariler.find_one({"id": data.cari_id}, {"_id": 0, "name": 1, "id": 1})
        if not cari:
            raise HTTPException(404, "Cari bulunamadı")
    subtotal = round(sum(e["line_total"] for e in enriched), 2)
    overall = round(min(float(data.overall_discount or 0), subtotal), 2)
    return {"enriched": enriched, "cari": cari, "subtotal": subtotal, "overall": overall, "total": round(subtotal - overall, 2)}


async def _revert_sale_effects(sale: dict, user: dict, note: str) -> None:
    """Satışın stok düşüşünü 'iade' hareketiyle geri alır; gelir ve cari alacak kaydını siler."""
    for mv_id in sale.get("movement_ids", []):
        mv = await db.stock_movements.find_one({"id": mv_id}, {"_id": 0})
        if not mv:
            continue
        tire = await db.tires.find_one({"id": mv["tire_id"]}, {"_id": 0, "quantity": 1})
        if not tire:
            continue
        before = float(tire.get("quantity", 0))
        after = before - float(mv["delta"])
        await db.tires.update_one({"id": mv["tire_id"]}, {"$set": {"quantity": after, "updated_at": now_iso()}})
        await db.stock_movements.insert_one({
            "id": str(uuid.uuid4()), "tire_id": mv["tire_id"], "tire_label": mv.get("tire_label", ""),
            "delta": -float(mv["delta"]), "before": before, "after": after,
            "reason": "iade", "note": note, "date": now_iso()[:10],
            "created_by": user["id"], "created_by_name": user["name"], "created_at": now_iso(),
        })
    if sale.get("income_id"):
        await db.incomes.delete_one({"id": sale["income_id"]})
    if sale.get("cari_tx_id"):
        await db.cari_transactions.delete_one({"id": sale["cari_tx_id"]})


async def _apply_sale(data: SaleIn, v: dict, user: dict, sale_id: str, meta: Optional[dict] = None) -> dict:
    """Doğrulanmış satışı uygular: stok düşer, peşinse gelir / veresiyede cari alacak yazar, satış kaydını kaydeder."""
    enriched, cari, total = v["enriched"], v["cari"], v["total"]
    sale_date = data.date or now_iso()[:10]
    done_movement_ids: list = []
    income_id: Optional[str] = None
    cari_tx_id: Optional[str] = None
    try:
        for e in enriched:
            tire = await db.tires.find_one({"id": e["tire_id"]}, {"_id": 0})
            before = float(tire.get("quantity", 0))
            after = before - float(e["quantity"])
            if after < 0:
                raise HTTPException(400, f"Stok yetersiz: {e['tire_label']}")
            await db.tires.update_one({"id": e["tire_id"]}, {"$set": {"quantity": after, "updated_at": now_iso()}})
            mv_id = str(uuid.uuid4())
            await db.stock_movements.insert_one({
                "id": mv_id, "tire_id": e["tire_id"], "tire_label": e["tire_label"],
                "delta": -float(e["quantity"]), "before": before, "after": after,
                "reason": "satis", "note": f"Satış: {sale_id}", "date": sale_date,
                "created_by": user["id"], "created_by_name": user["name"], "created_at": now_iso(),
                "sale_id": sale_id,
            })
            done_movement_ids.append(mv_id)

        parts = [f"{e['quantity']:.0f}× {e['tire_label']}" for e in enriched]
        desc = "Satış — " + ", ".join(parts[:3]) + (f" (+{len(parts)-3} ürün)" if len(parts) > 3 else "")
        if cari:
            desc = f"{cari['name']} — {desc}"
        if data.payment_method == "veresiye":
            cari_tx_id = str(uuid.uuid4())
            await db.cari_transactions.insert_one({
                "id": cari_tx_id, "cari_id": cari["id"], "type": "alacak",
                "amount": total, "description": f"Veresiye satış: {desc}",
                "date": sale_date, "created_by": user["id"], "created_by_name": user["name"],
                "created_at": now_iso(), "sale_id": sale_id,
            })
        else:
            income_id = str(uuid.uuid4())
            await db.incomes.insert_one({
                "id": income_id, "description": desc, "amount": total,
                "date": sale_date, "cari_id": cari["id"] if cari else None, "cari_name": cari["name"] if cari else None,
                "created_by": user["id"], "created_by_name": user["name"],
                "created_at": now_iso(), "sale_id": sale_id,
            })

        meta = meta or {"created_by": user["id"], "created_by_name": user["name"], "created_at": now_iso()}
        sale_doc = {
            "id": sale_id,
            "cari_id": cari["id"] if cari else None,
            "cari_name": cari["name"] if cari else None,
            "items": enriched,
            "subtotal": v["subtotal"],
            "overall_discount": v["overall"],
            "total": total,
            "payment_method": data.payment_method,
            "note": (data.note or "").strip(),
            "date": sale_date,
            "income_id": income_id,
            "cari_tx_id": cari_tx_id,
            "movement_ids": done_movement_ids,
            **meta,
        }
        await db.sales.replace_one({"id": sale_id}, sale_doc, upsert=True)
        sale_doc.pop("_id", None)
        return sale_doc
    except HTTPException:
        for mv_id in done_movement_ids:
            mv = await db.stock_movements.find_one({"id": mv_id}, {"_id": 0})
            if mv:
                await db.tires.update_one({"id": mv["tire_id"]}, {"$inc": {"quantity": -float(mv["delta"])}})
                await db.stock_movements.delete_one({"id": mv_id})
        if income_id:
            await db.incomes.delete_one({"id": income_id})
        if cari_tx_id:
            await db.cari_transactions.delete_one({"id": cari_tx_id})
        raise


@api_router.post("/sales")
async def create_sale(data: SaleIn, user: dict = Depends(get_current_user)):
    v = await _validate_sale(data)
    sale = await _apply_sale(data, v, user, str(uuid.uuid4()))
    await log_activity(user, "create", "Satış", f"{sale['cari_name'] or 'Müşterisiz'} — {sale['total']}₺ ({data.payment_method})")
    return sale


@api_router.put("/sales/{sale_id}")
async def update_sale(sale_id: str, data: SaleIn, user: dict = Depends(get_current_user)):
    old = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Satış bulunamadı")
    credit: dict = {}
    for it in old.get("items", []):
        credit[it["tire_id"]] = credit.get(it["tire_id"], 0.0) + float(it["quantity"])
    v = await _validate_sale(data, credit)
    await _revert_sale_effects(old, user, f"Satış düzenlendi: {sale_id}")
    meta = {"created_by": old["created_by"], "created_by_name": old["created_by_name"], "created_at": old["created_at"],
            "updated_at": now_iso(), "updated_by_name": user["name"]}
    try:
        sale = await _apply_sale(data, v, user, sale_id, meta)
    except HTTPException:
        await db.sales.delete_one({"id": sale_id})
        raise HTTPException(400, "Satış güncellenemedi; eski satış geri alındı, stok iade edildi. Lütfen satışı yeniden girin.")
    await log_activity(user, "update", "Satış", f"Düzenlendi: {old.get('total', 0)}₺ → {sale['total']}₺")
    return sale


@api_router.delete("/sales/{sale_id}")
async def delete_sale(sale_id: str, user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"id": sale_id}, {"_id": 0})
    if not sale:
        raise HTTPException(404, "Satış bulunamadı")
    if not sale.get("reversed"):
        await _revert_sale_effects(sale, user, f"Satış silindi: {sale_id}")
    await db.sales.delete_one({"id": sale_id})
    await log_activity(user, "delete", "Satış", f"Silindi: {sale.get('cari_name') or 'Müşterisiz'} — {sale.get('total', 0)}₺")
    return {"ok": True}


# ---- Legacy Stok uç noktaları (geriye dönük uyumluluk — artık lastik tablosuna yönlendirilir) ----
@api_router.get("/inventory")
async def list_inventory_legacy(user: dict = Depends(get_current_user)):
    docs = await db.tires.find({}, {"_id": 0}).sort("brand", 1).to_list(5000)
    for d in docs:
        _tire_as_legacy(d)
    return docs


# ---- Harcamalar ----
@api_router.get("/spendings", response_model=List[SpendingOut])
async def list_spendings(category: Optional[SpendingCategory] = None, user: dict = Depends(get_current_user)):
    q = {"category": category} if category else {}
    return await db.spendings.find(q, {"_id": 0}).sort("date", -1).to_list(5000)

@api_router.post("/spendings", response_model=SpendingOut)
async def create_spending(data: SpendingIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "category": data.category,
        "name": data.name,
        "amount": float(data.amount),
        "date": _resolve_date(data.date),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.spendings.insert_one(doc)
    await log_activity(user, "create", "Harcamalar", f"[{data.category}] {doc['name']} / {doc['amount']}₺")
    doc.pop("_id", None)
    return doc

@api_router.put("/spendings/{item_id}", response_model=SpendingOut)
async def update_spending(item_id: str, data: SpendingIn, user: dict = Depends(get_current_user)):
    update = {"category": data.category, "name": data.name, "amount": float(data.amount)}
    if data.date:
        update["date"] = data.date
    res = await db.spendings.find_one_and_update({"id": item_id}, {"$set": update})
    if not res:
        raise HTTPException(404, "Harcama bulunamadı")
    await log_activity(user, "update", "Harcamalar", f"[{data.category}] {data.name}")
    return await db.spendings.find_one({"id": item_id}, {"_id": 0})

@api_router.delete("/spendings/{item_id}")
async def delete_spending(item_id: str, user: dict = Depends(get_current_user)):
    doc = await db.spendings.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Harcama bulunamadı")
    await db.spendings.delete_one({"id": item_id})
    await log_activity(user, "delete", "Harcamalar", f"[{doc.get('category')}] {doc.get('name','')}")
    return {"ok": True}

# ---- Yapılacaklar ----
@api_router.get("/todos", response_model=List[TodoOut])
async def list_todos(user: dict = Depends(get_current_user)):
    return await db.todos.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)

@api_router.post("/todos", response_model=TodoOut)
async def create_todo(data: TodoIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "title": data.title,
        "note": data.note or "",
        "completed": False,
        "completed_at": None,
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.todos.insert_one(doc)
    await log_activity(user, "create", "Yapılacaklar", f"{doc['title']}")
    doc.pop("_id", None)
    return doc

@api_router.put("/todos/{item_id}", response_model=TodoOut)
async def update_todo(item_id: str, data: TodoUpdate, user: dict = Depends(get_current_user)):
    doc = await db.todos.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Görev bulunamadı")
    update = {}
    if data.title is not None:
        update["title"] = data.title
    if data.note is not None:
        update["note"] = data.note
    if data.completed is not None:
        update["completed"] = bool(data.completed)
        update["completed_at"] = now_iso() if data.completed else None
    if update:
        await db.todos.update_one({"id": item_id}, {"$set": update})
    action_detail = f"{doc['title']}" + (" (tamamlandı)" if data.completed else "")
    await log_activity(user, "update", "Yapılacaklar", action_detail)
    return await db.todos.find_one({"id": item_id}, {"_id": 0})

@api_router.delete("/todos/{item_id}")
async def delete_todo(item_id: str, user: dict = Depends(get_current_user)):
    doc = await db.todos.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Görev bulunamadı")
    await db.todos.delete_one({"id": item_id})
    await log_activity(user, "delete", "Yapılacaklar", f"{doc.get('title','')}")
    return {"ok": True}

# ---- Activity Log ----
# -----------------------------
# Email (Resend via Emergent proxy) + Guardrails
# -----------------------------
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Şirket Yönetim")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = (
    "reply with your password", "reply with the code", "send your password", "cvv",
    "send us your password", "enter your password below", "confirm your card number",
    "your full card number", "seed phrase", "recovery phrase", "verify your card",
    "social security number", "confirm your bank details",
)
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Unsafe URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor host mismatch (G3)")


async def send_email(*, to: str, subject: str, html: str) -> Optional[str]:
    if not EMAIL_KEY:
        raise HTTPException(status_code=500, detail="E-posta anahtarı yapılandırılmamış")
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        # Pass the real provider message up so the UI can show it
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        try:
            body = e.response.json()
            msg = body.get("message") or body.get("error") or e.response.text
        except Exception:
            msg = e.response.text
        raise HTTPException(status_code=502, detail=f"E-posta gönderilemedi: {msg}")
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise HTTPException(status_code=500, detail=f"E-posta gönderme hatası: {e}")


def _render_low_stock_email(user_name: str, items: list) -> str:
    rows = "".join(
        f'<tr><td style="padding:8px;border-bottom:1px solid #e2e8f0">{escape(str(it["product_name"]))}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right">{it["required_qty"]}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right">{it["received_qty"]}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #e2e8f0;text-align:right;color:#be123c;font-weight:600">{it["remaining_qty"]}</td></tr>'
        for it in items
    )
    return (
        f'<table role="presentation" width="100%" style="background:#f8fafc;padding:24px">'
        f'<tr><td align="center"><table role="presentation" width="600" style="background:#ffffff;border-radius:12px;padding:28px;font-family:Arial,sans-serif;color:#0f172a">'
        f'<tr><td><h2 style="margin:0 0 8px 0;color:#0f172a">Düşük Stok Uyarısı</h2>'
        f'<p style="color:#475569;margin:0 0 16px 0">Merhaba {escape(user_name)}, aşağıdaki ürünlerde eksik stok tespit edildi.</p>'
        f'<table role="presentation" width="100%" style="border-collapse:collapse;margin-top:12px">'
        f'<thead><tr style="background:#f1f5f9"><th align="left" style="padding:8px">Ürün</th><th align="right" style="padding:8px">İhtiyaç</th><th align="right" style="padding:8px">Alınan</th><th align="right" style="padding:8px">Kalan</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        f'<p style="color:#64748b;font-size:12px;margin-top:24px">Bu e-posta {escape(EMAIL_FROM_NAME)} tarafından otomatik gönderilmiştir. Hesap güvenliği için şifre, kart ya da OTP bilgilerinizi asla e-posta ile paylaşmayız.</p>'
        f'</td></tr></table></td></tr></table>'
    )


@api_router.get("/inventory/alerts")
async def inventory_alerts(user: dict = Depends(get_current_user), threshold: Optional[float] = None):
    """Stok adedi genel kritik eşiğe eşit/altında olan lastikler."""
    if threshold is None:
        threshold = await _get_critical_threshold()
    all_items = await db.tires.find({}, {"_id": 0}).to_list(5000)
    low = []
    for d in all_items:
        if float(d.get("quantity", 0)) <= threshold:
            _tire_as_legacy(d)
            # UI'nin low-stock banner'ı 'remaining_qty > 0' bekliyor, biz 'eksik miktarı' pozitif gösterelim
            d["remaining_qty"] = max(0.0, threshold - float(d.get("quantity", 0)))
            low.append(d)
    low.sort(key=lambda x: float(x.get("quantity", 0)))
    return {"count": len(low), "items": low, "threshold": threshold}


@api_router.post("/inventory/send-low-stock-email")
async def send_low_stock_email(user: dict = Depends(get_current_user)):
    """Düşük stok uyarısını kullanıcıların kayıtlı bildirim e-postalarına gönderir."""
    threshold = await _get_critical_threshold()
    all_items = await db.tires.find({}, {"_id": 0}).to_list(5000)
    low = []
    for d in all_items:
        if float(d.get("quantity", 0)) <= threshold:
            low.append({
                "product_name": _tire_label(d),
                "required_qty": threshold,
                "received_qty": float(d.get("quantity", 0)),
                "remaining_qty": max(0.0, threshold - float(d.get("quantity", 0))),
            })
    if not low:
        raise HTTPException(400, "Düşük stok bulunmuyor")

    # Alıcıları server-side records'tan al (G4). Varsa notification_email, yoksa login email.
    recipients = await db.users.find({}, {"_id": 0, "email": 1, "name": 1, "notification_email": 1}).to_list(10)
    recipients = [{"email": (u.get("notification_email") or u["email"]), "name": u["name"]} for u in recipients]
    if not recipients:
        raise HTTPException(500, "Alıcı bulunamadı")

    subject = f"Düşük Stok Uyarısı — {len(low)} ürün"
    sent = []
    failed = []
    for r in recipients:
        try:
            html = _render_low_stock_email(r.get("name", ""), low)
            email_id = await send_email(to=r["email"], subject=subject, html=html)
            sent.append({"email": r["email"], "id": email_id})
        except HTTPException as e:
            failed.append({"email": r["email"], "error": str(e.detail)})
        except Exception as e:
            failed.append({"email": r["email"], "error": str(e)})

    await log_activity(user, "email", "Stok", f"Düşük stok uyarısı gönderildi: {len(sent)} başarılı, {len(failed)} başarısız")
    return {"sent": sent, "failed": failed, "low_stock_count": len(low)}


class NotificationSettingsIn(BaseModel):
    notification_email: Optional[EmailStr] = None


@api_router.get("/auth/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    """Kullanıcının bildirim ayarlarını döner."""
    doc = await db.users.find_one({"id": user["id"]}, {"_id": 0, "email": 1, "notification_email": 1, "name": 1})
    return {
        "email": doc.get("email"),
        "name": doc.get("name"),
        "notification_email": doc.get("notification_email") or "",
    }


@api_router.put("/auth/settings")
async def update_settings(data: NotificationSettingsIn, user: dict = Depends(get_current_user)):
    """Kullanıcı bildirim e-posta adresini (gerçek adres) kaydeder."""
    val = (data.notification_email or "").strip().lower() or None
    await db.users.update_one({"id": user["id"]}, {"$set": {"notification_email": val}})
    await log_activity(user, "update", "Ayarlar", f"Bildirim e-postası güncellendi")
    return {"ok": True, "notification_email": val or ""}


@api_router.get("/auth/recipients")
async def list_recipients(user: dict = Depends(get_current_user)):
    """Düşük stok uyarısında kullanılacak alıcıları önizler."""
    users_ = await db.users.find({}, {"_id": 0, "email": 1, "name": 1, "notification_email": 1}).to_list(10)
    return [
        {
            "name": u["name"],
            "login_email": u["email"],
            "notification_email": u.get("notification_email") or "",
            "effective": u.get("notification_email") or u["email"],
        }
        for u in users_
    ]


# -----------------------------
# Monthly Report (Cron)
# -----------------------------
def _render_monthly_report_email(user_name: str, month_label: str, totals: dict, top_items: dict) -> str:
    tr = lambda n: f"₺{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    rows_inc = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{escape(x["description"])}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;text-align:right">{tr(x["amount"])}</td></tr>'
        for x in top_items["incomes"]
    ) or '<tr><td colspan="2" style="padding:12px;text-align:center;color:#94a3b8">Kayıt yok</td></tr>'
    rows_exp = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #e2e8f0">{escape(x["description"])}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;text-align:right">{tr(x["amount"])}</td></tr>'
        for x in top_items["expenses"]
    ) or '<tr><td colspan="2" style="padding:12px;text-align:center;color:#94a3b8">Kayıt yok</td></tr>'

    profit = totals["income"] - totals["expense"]
    profit_color = "#059669" if profit >= 0 else "#dc2626"
    return (
        f'<table role="presentation" width="100%" style="background:#f8fafc;padding:24px"><tr><td align="center">'
        f'<table role="presentation" width="640" style="background:#ffffff;border-radius:12px;padding:32px;font-family:Arial,sans-serif;color:#0f172a">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 4px 0">Aylık Rapor — {escape(month_label)}</h2>'
        f'<p style="color:#64748b;margin:0 0 24px 0">Merhaba {escape(user_name)}, önceki ayın finansal özeti aşağıdadır.</p>'
        # KPI cards
        f'<table role="presentation" width="100%" style="margin-bottom:24px"><tr>'
        f'<td style="padding:12px;background:#ecfdf5;border-radius:8px;width:33%"><div style="font-size:11px;color:#047857;text-transform:uppercase;letter-spacing:1px">Gelir</div><div style="font-size:20px;font-weight:800;color:#065f46">{tr(totals["income"])}</div></td>'
        f'<td style="width:8px"></td>'
        f'<td style="padding:12px;background:#fef2f2;border-radius:8px;width:33%"><div style="font-size:11px;color:#b91c1c;text-transform:uppercase;letter-spacing:1px">Gider</div><div style="font-size:20px;font-weight:800;color:#991b1b">{tr(totals["expense"])}</div></td>'
        f'<td style="width:8px"></td>'
        f'<td style="padding:12px;background:#eef2ff;border-radius:8px;width:33%"><div style="font-size:11px;color:#4338ca;text-transform:uppercase;letter-spacing:1px">KDV</div><div style="font-size:20px;font-weight:800;color:#3730a3">{tr(totals["vat"])}</div></td>'
        f'</tr></table>'
        f'<table role="presentation" width="100%" style="margin-bottom:24px"><tr>'
        f'<td style="padding:12px;background:#f1f5f9;border-radius:8px"><div style="font-size:11px;color:#475569;text-transform:uppercase;letter-spacing:1px">Fatura Toplamı (KDV Dahil)</div><div style="font-size:16px;font-weight:700">{tr(totals["invoice"])}</div></td>'
        f'<td style="width:8px"></td>'
        f'<td style="padding:12px;background:#f1f5f9;border-radius:8px"><div style="font-size:11px;color:#475569;text-transform:uppercase;letter-spacing:1px">Gelir − Gider Farkı</div><div style="font-size:16px;font-weight:800;color:{profit_color}">{tr(profit)}</div></td>'
        f'</tr></table>'
        # Top items
        f'<h3 style="margin:16px 0 8px 0;font-size:14px;text-transform:uppercase;letter-spacing:1px;color:#475569">En Büyük 5 Gelir</h3>'
        f'<table role="presentation" width="100%" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">{rows_inc}</table>'
        f'<h3 style="margin:20px 0 8px 0;font-size:14px;text-transform:uppercase;letter-spacing:1px;color:#475569">En Büyük 5 Gider</h3>'
        f'<table role="presentation" width="100%" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">{rows_exp}</table>'
        f'<p style="color:#64748b;font-size:12px;margin-top:28px">Bu rapor {escape(EMAIL_FROM_NAME)} tarafından otomatik olarak her ayın 1\'inde gönderilir. Detaylı veriler için uygulamanızda oturum açın.</p>'
        f'</td></tr></table></td></tr></table>'
    )


async def _previous_month_range() -> tuple[str, str, str]:
    """(start_iso, end_iso, label) tuple'ını döner — önceki ay."""
    now = datetime.now(timezone.utc)
    first_this_month = now.replace(day=1)
    last_prev = first_this_month - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    start = first_prev.strftime("%Y-%m-%d")
    end = last_prev.strftime("%Y-%m-%d")
    label = first_prev.strftime("%Y-%m")
    return start, end, label


async def _collect_monthly_report() -> dict:
    """Önceki ayın verilerini toplar."""
    start, end, label = await _previous_month_range()
    inc = await db.incomes.find({"date": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(10000)
    exp = await db.expenses.find({"date": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(10000)
    invs = await db.invoices.find({"date": {"$gte": start, "$lte": end}}, {"_id": 0}).to_list(10000)
    totals = {
        "income": round(sum(float(x.get("amount", 0)) for x in inc), 2),
        "expense": round(sum(float(x.get("amount", 0)) for x in exp), 2),
        "invoice": round(sum(float(x.get("amount", 0)) for x in invs), 2),
        "vat": round(sum(float(x.get("vat_amount", 0)) for x in invs), 2),
    }
    top = {
        "incomes": sorted(inc, key=lambda x: float(x.get("amount", 0)), reverse=True)[:5],
        "expenses": sorted(exp, key=lambda x: float(x.get("amount", 0)), reverse=True)[:5],
    }
    month_label = datetime.strptime(label, "%Y-%m").strftime("%B %Y")
    # Türkçe ay isimleri
    tr_months = {
        "January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan",
        "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos",
        "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık",
    }
    for en, tr in tr_months.items():
        month_label = month_label.replace(en, tr)
    return {"totals": totals, "top": top, "month_label": month_label, "range": {"start": start, "end": end}}


async def _run_monthly_report_task() -> None:
    """Background task: önceki ay raporunu toplar, her kullanıcıya e-posta gönderir."""
    try:
        report = await _collect_monthly_report()
        users_ = await db.users.find({}, {"_id": 0, "email": 1, "name": 1, "notification_email": 1}).to_list(10)
        subject = f"Aylık Rapor — {report['month_label']}"
        sent, failed = 0, 0
        for u in users_:
            to = u.get("notification_email") or u["email"]
            try:
                html = _render_monthly_report_email(u["name"], report["month_label"], report["totals"], report["top"])
                await send_email(to=to, subject=subject, html=html)
                sent += 1
            except Exception as e:
                logger.error(f"Monthly report send failed to {to}: {e}")
                failed += 1
        # Audit log (sistem olarak)
        await db.activity_logs.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": "system",
            "user_name": "Sistem (Cron)",
            "action": "email",
            "section": "Rapor",
            "details": f"Aylık rapor ({report['month_label']}) gönderildi: {sent} başarılı, {failed} başarısız",
            "timestamp": now_iso(),
        })
        logger.info(f"Monthly report done: sent={sent} failed={failed}")
    except Exception:
        logger.exception("Monthly report task error")


# Processed webhook ids (idempotency, in-memory for current pod)
_processed_webhooks: set = set()


@api_router.post("/cron/monthly-report")
async def cron_monthly_report(
    background: BackgroundTasks,
    request: Request,
    authorization: Optional[str] = Header(None),
    x_webhook_id: Optional[str] = Header(None),
):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    import hmac
    expected = os.environ.get("WEBHOOK_CRON_SECRET", "")
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization[7:]
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Parse envelope (best effort)
    try:
        envelope = await request.json()
    except Exception:
        envelope = {}
    run_id = x_webhook_id or envelope.get("run_id") or str(uuid.uuid4())

    # Idempotency
    if run_id in _processed_webhooks:
        return {"ok": True, "duplicate": True, "run_id": run_id}
    _processed_webhooks.add(run_id)
    if len(_processed_webhooks) > 500:
        _processed_webhooks.pop()

    # Hand off
    background.add_task(_run_monthly_report_task)
    return {"ok": True, "run_id": run_id, "queued": "monthly-report"}


@api_router.post("/reports/monthly/send-now")
async def send_monthly_report_now(background: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Kullanıcı tarafından tetiklenen aylık rapor gönderimi (test/anında gönderim)."""
    background.add_task(_run_monthly_report_task)
    await log_activity(user, "email", "Rapor", "Aylık rapor manuel olarak kuyruğa alındı")
    return {"ok": True, "queued": True}


@api_router.get("/reports/monthly/preview")
async def preview_monthly_report(user: dict = Depends(get_current_user)):
    """Aylık rapor önizlemesi (önceki ay)."""
    return await _collect_monthly_report()


# -----------------------------
# Monthly trend (dashboard chart)
# -----------------------------
@api_router.get("/dashboard/monthly-trend")
async def monthly_trend(user: dict = Depends(get_current_user)):
    """Son 12 ayın gelir/gider/fatura/kdv/kâr özetini döner."""
    def _month(d: str) -> str:
        return (d or "")[:7]

    incomes = await db.incomes.find({}, {"_id": 0, "date": 1, "amount": 1}).to_list(10000)
    expenses = await db.expenses.find({}, {"_id": 0, "date": 1, "amount": 1}).to_list(10000)
    invoices = await db.invoices.find({}, {"_id": 0, "date": 1, "amount": 1, "vat_amount": 1}).to_list(10000)

    buckets: dict = {}
    for row in incomes:
        m = _month(row.get("date"))
        if m:
            buckets.setdefault(m, {"month": m, "income": 0, "expense": 0, "invoice": 0, "vat": 0})["income"] += float(row.get("amount", 0))
    for row in expenses:
        m = _month(row.get("date"))
        if m:
            buckets.setdefault(m, {"month": m, "income": 0, "expense": 0, "invoice": 0, "vat": 0})["expense"] += float(row.get("amount", 0))
    for row in invoices:
        m = _month(row.get("date"))
        if m:
            b = buckets.setdefault(m, {"month": m, "income": 0, "expense": 0, "invoice": 0, "vat": 0})
            b["invoice"] += float(row.get("amount", 0))
            b["vat"] += float(row.get("vat_amount", 0))
    rows = []
    for m in sorted(buckets.keys()):
        b = buckets[m]
        rows.append({
            "month": m,
            "income": round(b["income"], 2),
            "expense": round(b["expense"], 2),
            "invoice": round(b["invoice"], 2),
            "vat": round(b["vat"], 2),
            "diff": round(b["income"] - b["expense"], 2),
        })
    return rows[-12:]  # son 12 ay


# -----------------------------
# Invoice import preview + confirm (replaces single-shot import for UI)
# -----------------------------
class ParsedInvoiceRow(BaseModel):
    description: str
    amount: float
    date: str


class ImportConfirmIn(BaseModel):
    items: List[ParsedInvoiceRow]


async def _parse_invoice_file(raw: bytes, filename: str) -> List[dict]:
    filename = (filename or "").lower()
    parsed: List[dict] = []
    if filename.endswith(".xlsx") or filename.endswith(".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise HTTPException(400, "Excel dosyası boş")
        headers = [str(c or "").strip().lower() for c in rows[0]]

        def _find(cands):
            for cand in cands:
                for i, h in enumerate(headers):
                    if cand in h:
                        return i
            return -1

        idx_date = _find(["tarih", "date"])
        idx_desc = _find(["aciklama", "açıklama", "description", "fatura"])
        idx_amt = _find(["tutar", "amount", "toplam"])
        if idx_amt == -1:
            raise HTTPException(400, "Excel başlıklarında 'Tutar' bulunamadı")

        for r in rows[1:]:
            if r is None:
                continue
            try:
                amt_raw = r[idx_amt]
                if amt_raw in (None, ""):
                    continue
                amount = float(str(amt_raw).replace(",", ".").replace(" ", ""))
                desc = str(r[idx_desc]).strip() if idx_desc != -1 and r[idx_desc] is not None else "Fatura"
                date_val = r[idx_date] if idx_date != -1 else None
                if hasattr(date_val, "strftime"):
                    date = date_val.strftime("%Y-%m-%d")
                elif date_val:
                    date = _normalize_date_str(str(date_val))
                else:
                    date = _resolve_date(None)
                parsed.append({"description": desc, "amount": amount, "date": date})
            except Exception as e:
                logger.warning(f"Satır atlandı: {e}")
                continue

    elif filename.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            text_all = "\n".join((p.extract_text() or "") for p in pdf.pages)
        for line in text_all.splitlines():
            line = line.strip()
            if not line:
                continue
            amt_match = re.findall(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+[.,]\d{1,2}|\d+)", line)
            if not amt_match:
                continue
            try:
                last = amt_match[-1]
                amount = float(last.replace(".", "").replace(",", ".")) if "," in last else float(last.replace(",", ""))
            except Exception:
                continue
            date_m = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4})", line)
            date = _normalize_date_str(date_m.group(1)) if date_m else _resolve_date(None)
            desc = line
            if date_m:
                desc = desc.replace(date_m.group(1), "")
            desc = desc.replace(amt_match[-1], "").strip(" -|:")
            if not desc:
                desc = "Fatura"
            if amount <= 0 or amount > 100_000_000:
                continue
            parsed.append({"description": desc[:200], "amount": amount, "date": date})
    else:
        raise HTTPException(400, "Yalnızca .xlsx veya .pdf dosyaları desteklenir")
    return parsed


@api_router.post("/invoices/import-preview")
async def import_invoices_preview(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Dosyayı ayrıştırır, kaydetmeden parsed satırları döner (önizleme)."""
    raw = await _read_upload_limited(file)
    try:
        parsed = await _parse_invoice_file(raw, file.filename or "")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Preview parse error")
        raise HTTPException(400, f"Dosya okunamadı: {e}")

    if not parsed:
        raise HTTPException(400, "Dosyada geçerli fatura satırı bulunamadı")

    # KDV önizleme bilgisi ekle
    for p in parsed:
        bd = _invoice_breakdown(float(p["amount"]))
        p["base_amount"] = bd["base_amount"]
        p["vat_amount"] = bd["vat_amount"]
    return {"count": len(parsed), "items": parsed, "filename": file.filename}


@api_router.post("/invoices/import-confirm")
async def import_invoices_confirm(data: ImportConfirmIn, user: dict = Depends(get_current_user)):
    """Önizlenen satırları toplu kaydet."""
    if not data.items:
        raise HTTPException(400, "Kaydedilecek satır yok")
    created = []
    for p in data.items:
        bd = _invoice_breakdown(float(p.amount))
        doc = {
            "id": str(uuid.uuid4()),
            "description": p.description,
            "amount": round(float(p.amount), 2),
            "base_amount": bd["base_amount"],
            "vat_amount": bd["vat_amount"],
            "date": p.date or _resolve_date(None),
            "created_by": user["id"],
            "created_by_name": user["name"],
            "created_at": now_iso(),
        }
        await db.invoices.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)
    await log_activity(user, "import", "Faturalar", f"{len(created)} fatura içe aktarıldı (önizleme ile)")
    return {"count": len(created), "items": created}


@api_router.get("/activity-logs")
async def list_logs(limit: int = 500, user: dict = Depends(get_current_user)):
    docs = await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return docs

# ---- Dashboard v2: dönem özeti, stok, cari alacak, aylık rapor ----
DEFAULT_CRITICAL_STOCK = 4.0


async def _get_critical_threshold() -> float:
    doc = await db.settings.find_one({"key": "stock"}, {"_id": 0})
    return float(doc["critical_threshold"]) if doc and doc.get("critical_threshold") is not None else DEFAULT_CRITICAL_STOCK


class StockSettingsIn(BaseModel):
    critical_threshold: float = Field(ge=0, le=10000)


@api_router.get("/settings/stock")
async def get_stock_settings(user: dict = Depends(get_current_user)):
    return {"critical_threshold": await _get_critical_threshold()}


@api_router.put("/settings/stock")
async def update_stock_settings(data: StockSettingsIn, user: dict = Depends(get_current_user)):
    await db.settings.update_one({"key": "stock"}, {"$set": {"key": "stock", "critical_threshold": float(data.critical_threshold)}}, upsert=True)
    await log_activity(user, "update", "Stok", f"Kritik stok eşiği: {data.critical_threshold}")
    return {"critical_threshold": float(data.critical_threshold)}


def _r2(x: float) -> float:
    return round(float(x or 0), 2)


async def _period_finance(start: str, end: str) -> dict:
    """Seçili tarih aralığı (YYYY-MM-DD, dahil) için finans, satış ve tahsilat özetleri."""
    rng = {"$gte": start, "$lte": end}
    inc = await db.incomes.find({"date": rng}, {"_id": 0, "amount": 1}).to_list(20000)
    exp = await db.expenses.find({"date": rng}, {"_id": 0, "amount": 1}).to_list(20000)
    sp = await db.spendings.find({"date": rng, "category": "company"}, {"_id": 0, "amount": 1}).to_list(20000)
    sales = await db.sales.find({"date": rng, "reversed": {"$ne": True}}, {"_id": 0, "total": 1, "payment_method": 1, "items": 1}).to_list(20000)
    pays = await db.cari_transactions.find({"date": rng, "type": "odeme"}, {"_id": 0, "amount": 1}).to_list(20000)

    by_pay = {k: 0.0 for k in ("nakit", "kart", "havale", "veresiye")}
    for s in sales:
        by_pay[s.get("payment_method", "nakit")] = by_pay.get(s.get("payment_method", "nakit"), 0) + float(s.get("total", 0))
    income_total = sum(float(x.get("amount", 0)) for x in inc)
    expense_total = sum(float(x.get("amount", 0)) for x in exp)
    cash_sales = by_pay["nakit"] + by_pay["kart"] + by_pay["havale"]
    cari_payments = sum(float(x.get("amount", 0)) for x in pays)
    return {
        "range": {"start": start, "end": end},
        "income_total": _r2(income_total), "income_count": len(inc),
        "expense_total": _r2(expense_total), "expense_count": len(exp),
        "income_expense_diff": _r2(income_total - expense_total),
        "company_spending_total": _r2(sum(float(x.get("amount", 0)) for x in sp)), "company_spending_count": len(sp),
        "sales_revenue": _r2(sum(float(s.get("total", 0)) for s in sales)),
        "sales_count": len(sales),
        "sales_tire_qty": _r2(sum(float(i.get("quantity", 0)) for s in sales for i in s.get("items", []))),
        "sales_by_payment": {k: _r2(v) for k, v in by_pay.items()},
        "collections_total": _r2(cash_sales + cari_payments),
        "collections_cash_sales": _r2(cash_sales),
        "collections_cari_payments": _r2(cari_payments), "cari_payment_count": len(pays),
    }


async def _stock_snapshot() -> dict:
    threshold = await _get_critical_threshold()
    tires = await db.tires.find({}, {"_id": 0}).to_list(10000)
    out, critical = [], []
    for t in tires:
        q = float(t.get("quantity", 0))
        row = {"id": t["id"], "brand": t.get("brand", ""), "model": t.get("model", ""), "size": t.get("size", ""),
               "season": t.get("season", ""), "quantity": q, "product_type": t.get("product_type", "lastik"),
               "name": t.get("name", ""), "category": t.get("category", ""), "unit": t.get("unit", "adet"), "label": _tire_label(t)}
        if q <= 0:
            out.append(row)
        elif q <= threshold:
            critical.append(row)
    critical.sort(key=lambda r: r["quantity"])
    return {
        "threshold": threshold,
        "product_count": len(tires),
        "total_qty": _r2(sum(max(0.0, float(t.get("quantity", 0))) for t in tires)),
        "critical_count": len(critical),
        "out_of_stock_count": len(out),
        "critical": critical,
        "out_of_stock": out,
    }


async def _receivables_snapshot() -> dict:
    """Müşterilerin açık alacak bakiyesi = alacak − gelen ödeme (sadece > 0 olanlar)."""
    txs = await db.cari_transactions.find({}, {"_id": 0, "cari_id": 1, "type": 1, "amount": 1, "date": 1, "created_at": 1}).to_list(50000)
    cariler = {c["id"]: c["name"] for c in await db.cariler.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(10000)}
    agg: dict = {}
    for t in txs:
        if t.get("cari_id") not in cariler:
            continue
        a = agg.setdefault(t["cari_id"], {"alacak": 0.0, "odeme": 0.0, "txs": []})
        if t["type"] in ("alacak", "odeme"):
            a[t["type"]] += float(t.get("amount", 0))
            a["txs"].append(t)
    rows = []
    for cid, a in agg.items():
        rem = round(a["alacak"] - a["odeme"], 2)
        if rem > 0.005:
            oldest, days = _oldest_open_debt(a["txs"], a["odeme"])
            rows.append({"id": cid, "name": cariler[cid], "total_alacak": _r2(a["alacak"]), "total_odeme": _r2(a["odeme"]),
                         "remaining": rem, "oldest_open_date": oldest, "open_days": days})
    rows.sort(key=lambda r: r["remaining"], reverse=True)
    return {"total": _r2(sum(r["remaining"] for r in rows)), "debtor_count": len(rows), "items": rows}


async def _integrity_warnings() -> list:
    warnings = []
    sales = await db.sales.find({"reversed": {"$ne": True}}, {"_id": 0, "id": 1, "date": 1, "total": 1, "payment_method": 1, "income_id": 1, "cari_tx_id": 1}).to_list(20000)
    inc_ids = {d["id"] for d in await db.incomes.find({"sale_id": {"$exists": True}}, {"_id": 0, "id": 1}).to_list(50000)}
    tx_ids = {d["id"] for d in await db.cari_transactions.find({"sale_id": {"$exists": True}}, {"_id": 0, "id": 1}).to_list(50000)}
    missing_inc = [s for s in sales if s.get("payment_method") != "veresiye" and s.get("income_id") and s["income_id"] not in inc_ids]
    missing_tx = [s for s in sales if s.get("payment_method") == "veresiye" and s.get("cari_tx_id") and s["cari_tx_id"] not in tx_ids]
    if missing_inc:
        warnings.append({"type": "sale_income_missing", "count": len(missing_inc), "amount": _r2(sum(s["total"] for s in missing_inc)),
                         "message": f"{len(missing_inc)} peşin satışın bağlı gelir kaydı silinmiş; bu satışlar satış cirosunda var, gelirde yok."})
    if missing_tx:
        warnings.append({"type": "sale_cari_tx_missing", "count": len(missing_tx), "amount": _r2(sum(s["total"] for s in missing_tx)),
                         "message": f"{len(missing_tx)} veresiye satışın cari alacak kaydı silinmiş; cari alacakta görünmüyor."})
    return warnings


def _valid_date(d: str) -> str:
    try:
        datetime.strptime(d, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise HTTPException(400, "Tarih formatı YYYY-MM-DD olmalı")
    return d


def _month_range(month: str) -> tuple:
    try:
        first = datetime.strptime(month, "%Y-%m")
    except (ValueError, TypeError):
        raise HTTPException(400, "Ay formatı YYYY-MM olmalı")
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    prev = (first - timedelta(days=1)).replace(day=1)
    return first.strftime("%Y-%m-%d"), (nxt - timedelta(days=1)).strftime("%Y-%m-%d"), prev.strftime("%Y-%m")


@api_router.get("/dashboard/overview")
async def dashboard_overview(start: str, end: str, user: dict = Depends(get_current_user)):
    start, end = _valid_date(start), _valid_date(end)
    if start > end:
        raise HTTPException(400, "Başlangıç tarihi bitişten sonra olamaz")
    return {
        "finance": await _period_finance(start, end),
        "stock": await _stock_snapshot(),
        "receivables": await _receivables_snapshot(),
        "warnings": await _integrity_warnings(),
        "as_of": now_iso(),
    }


@api_router.get("/reports/monthly")
async def monthly_report(month: str, details: bool = False, user: dict = Depends(get_current_user)):
    start, end, prev_month = _month_range(month)
    pstart, pend, _ = _month_range(prev_month)
    res = {"month": month, "previous_month": prev_month,
           "current": await _period_finance(start, end), "previous": await _period_finance(pstart, pend)}
    mvs = await db.stock_movements.find({"date": {"$gte": start, "$lte": end}}, {"_id": 0}).sort("created_at", -1).to_list(20000)
    res["stock_movements_summary"] = {
        "count": len(mvs),
        "in_qty": _r2(sum(m["delta"] for m in mvs if float(m.get("delta", 0)) > 0)),
        "out_qty": _r2(-sum(m["delta"] for m in mvs if float(m.get("delta", 0)) < 0)),
    }
    if details:
        rng = {"$gte": start, "$lte": end}
        res["incomes"] = await db.incomes.find({"date": rng}, {"_id": 0}).sort("date", -1).to_list(5000)
        res["expenses"] = await db.expenses.find({"date": rng}, {"_id": 0}).sort("date", -1).to_list(5000)
        res["sales"] = await db.sales.find({"date": rng, "reversed": {"$ne": True}}, {"_id": 0, "movement_ids": 0}).sort("date", -1).to_list(5000)
        pays = await db.cari_transactions.find({"date": rng, "type": "odeme"}, {"_id": 0}).sort("date", -1).to_list(5000)
        names = {c["id"]: c["name"] for c in await db.cariler.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(10000)}
        for p in pays:
            p["cari_name"] = names.get(p["cari_id"], "—")
        res["cari_payments"] = pays
        res["stock_movements"] = mvs[:1000]
    return res


# ---- Dashboard summary ----
@api_router.get("/summary")
async def summary(user: dict = Depends(get_current_user)):
    inc = await db.incomes.find({}, {"_id": 0, "amount": 1}).to_list(5000)
    exp = await db.expenses.find({}, {"_id": 0, "amount": 1}).to_list(5000)
    invs = await db.invoices.find({}, {"_id": 0, "amount": 1, "vat_amount": 1}).to_list(5000)
    todos = await db.todos.find({"completed": False}, {"_id": 0, "id": 1}).to_list(5000)
    cari_tx = await db.cari_transactions.find({}, {"_id": 0, "type": 1, "amount": 1}).to_list(10000)
    cari_alacak = sum(float(t["amount"]) for t in cari_tx if t["type"] == "alacak")
    cari_borc = sum(float(t["amount"]) for t in cari_tx if t["type"] == "borc")
    base_income = sum(d["amount"] for d in inc)
    base_expense = sum(d["amount"] for d in exp)
    return {
        "total_income": round(base_income + cari_alacak, 2),
        "total_expense": round(base_expense + cari_borc, 2),
        "total_income_direct": round(base_income, 2),
        "total_expense_direct": round(base_expense, 2),
        "cari_alacak": round(cari_alacak, 2),
        "cari_borc": round(cari_borc, 2),
        "total_invoices": round(sum(d["amount"] for d in invs), 2),
        "total_vat": round(sum(d.get("vat_amount", 0) for d in invs), 2),
        "open_todos": len(todos),
    }

# -----------------------------
# ŞAMPİYON — AI Asistanı (Claude Sonnet + Araçlar + Ses)
# -----------------------------
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
SAMPIYON_MODEL_PROVIDER = "gemini"
SAMPIYON_MODEL_NAME = "gemini-3-flash-preview"

SAMPIYON_SYSTEM_PROMPT = """Sen Karivo Otomotiv'in AI asistanı Şampiyon'sun. Uygulamadaki HER işlemi yapmaya tam yetkilisin.

Kişilik: Samimi, enerjik ekip arkadaşı. "selam patron", "tamamdır, yaptım", "bi bakıyorum" tarzı konuş. Emoji kullanma.
Rol: Lastik stoku, satışlar, cariler (alacak/borç/gelen ödeme), gelir, gider, faturalar, harcamalar (şirket ve kişisel), yapılacaklar. Araçlarla gerçek veriye bak, asla tahmin yürütme veya veri uydurma.
YETKİ: Kullanıcı bir şey yapmanı isterse (ekle, gir, kaydet, güncelle, tamamla) HEMEN ilgili aracı çağır ve yap — onay sorma, "yapabilir miyim" deme. Eksik zorunlu bilgi varsa (ör. tutar) sadece onu kısaca sor.
ONAY SADECE İKİ DURUMDA: (1) Satış oluşturma (create_sale), (2) Herhangi bir kaydı silme (delete_record). Bunlarda önce tek cümleyle özetle ve "onaylıyor musun?" diye sor; kullanıcı evet/tamam/olur derse confirmed=true ile çağır.
Kimlik çözme: Cari adı söylenirse cari_name ile gönder. Lastik için önce search_tires ile id bul. Silme/tamamlama için önce list_records ile id bul.
"Harcama" denirse add_spending kullan (kategori belirtilmezse company). "Gider" denirse add_expense kullan.
"X'ten ödeme geldi / tahsil ettim" → add_cari_transaction(type=odeme). "X'e borçlandık / X'ten mal aldık veresiye" → type=borc. "X bize borçlandı / X'e alacak yaz" → type=alacak.
Dil: Türkçe, ÇOK kısa ve net (1-3 cümle). Sayıları ₺ ile yaz. Markdown başlık/tablo kullanma; gerekirse kısa liste.
Hata: Ters giderse direkt söyle: "3 adet lazım ama stokta 2 var" gibi.
Uzun listelerde 'toplam X kayıt, ilk 10:' şeklinde özetle."""


SAMPIYON_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_tires",
            "description": "Lastik stokundan ebat, marka, mevsim veya serbest metin ile ara. Örn: '205/55 R16' lastikleri bulmak için size='205/55 R16'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "size": {"type": "string", "description": "Lastik ebadı, ör: 205/55 R16"},
                    "brand": {"type": "string", "description": "Marka adı, ör: Michelin"},
                    "season": {"type": "string", "enum": ["yaz", "kis", "4mevsim"]},
                    "search": {"type": "string", "description": "Serbest metin aramak için"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_summary",
            "description": "Toplam stok adedi, toplam alış ve satış değerini döner.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_finance_summary",
            "description": "Belirli tarih aralığı için gelir, gider, kâr, KDV ve fatura toplamlarını döner. Tarihler YYYY-MM-DD formatında. Varsayılan: tüm zamanlar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_cariler",
            "description": "Müşteri/tedarikçi (cari) kayıtlarını, bakiye özetleriyle birlikte listeler. Arama için 'search' kullanılabilir.",
            "parameters": {
                "type": "object",
                "properties": {"search": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_tire",
            "description": "YENİ bir lastik ürünü ekler (onay gerekmez, direkt yap). buy_price = KDV hariç alış fiyatı.",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string"},
                    "model": {"type": "string"},
                    "size": {"type": "string", "description": "Örn: 205/55 R16"},
                    "season": {"type": "string", "enum": ["yaz", "kis", "4mevsim"]},
                    "dot": {"type": "string"},
                    "quantity": {"type": "number"},
                    "buy_price": {"type": "number"},
                    "sell_price": {"type": "number"},
                    "kdv_rate": {"type": "number", "default": 20},
                },
                "required": ["brand", "size", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_tire_stock",
            "description": "Mevcut bir lastiğin stok adedini değiştirir (giriş/çıkış hareketi). Direkt yap. delta pozitif=giriş, negatif=çıkış.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tire_id": {"type": "string"},
                    "delta": {"type": "number"},
                    "reason": {"type": "string", "enum": ["alis", "satis", "iade", "sayim-duzeltme", "fire", "diger"]},
                    "note": {"type": "string"},
                },
                "required": ["tire_id", "delta", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_income",
            "description": "Gelir kaydı oluşturur. Direkt yap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount": {"type": "number"},
                    "date": {"type": "string", "description": "YYYY-MM-DD, boşsa bugün"},
                },
                "required": ["description", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Gelir/Giderler sayfasındaki Gider kaydı oluşturur. Direkt yap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount": {"type": "number"},
                    "date": {"type": "string"},
                },
                "required": ["description", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_sales",
            "description": "Son satış kayıtlarını listeler (varsayılan 20). Bugünkü satışları özetlemek için kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "number", "default": 20},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
            },
        },
    },
]


async def _tool_list_recent_sales(args: dict, user: dict) -> dict:
    q: dict = {"reversed": {"$ne": True}}
    if args.get("start_date") or args.get("end_date"):
        q["date"] = {}
        if args.get("start_date"):
            q["date"]["$gte"] = args["start_date"]
        if args.get("end_date"):
            q["date"]["$lte"] = args["end_date"]
    limit = int(args.get("limit") or 20)
    docs = await db.sales.find(q, {"_id": 0}).sort("date", -1).to_list(limit)
    total = sum(float(d.get("total", 0)) for d in docs)
    out = [{
        "id": d["id"], "date": d.get("date"), "cari_name": d.get("cari_name"),
        "total": d.get("total"), "payment_method": d.get("payment_method"),
        "item_count": len(d.get("items", [])),
    } for d in docs]
    return {"count": len(out), "total_amount": round(total, 2), "items": out[:50]}


async def _tool_search_tires(args: dict, user: dict) -> dict:
    q: dict = {}
    if args.get("size"):
        q["size"] = {"$regex": re.escape(args["size"]), "$options": "i"}
    if args.get("brand"):
        q["brand"] = {"$regex": re.escape(args["brand"]), "$options": "i"}
    if args.get("season"):
        q["season"] = args["season"]
    docs = await db.tires.find(q, {"_id": 0}).sort("brand", 1).to_list(500)
    if args.get("search"):
        s = args["search"].lower()
        docs = [d for d in docs if s in _tire_label(d).lower()]
    out = [{
        "id": d["id"], "brand": d["brand"], "model": d.get("model", ""), "size": d["size"],
        "season": d.get("season"), "dot": d.get("dot", ""), "quantity": d.get("quantity", 0),
        "buy_price": d.get("buy_price", 0), "sell_price": d.get("sell_price", 0),
    } for d in docs]
    return {"count": len(out), "items": out[:50]}


async def _tool_get_stock_summary(args: dict, user: dict) -> dict:
    docs = await db.tires.find({}, {"_id": 0}).to_list(5000)
    total_qty = sum(float(d.get("quantity", 0)) for d in docs)
    total_buy = sum(float(d.get("quantity", 0)) * float(d.get("buy_price", 0)) for d in docs)
    total_sell = sum(float(d.get("quantity", 0)) * float(d.get("sell_price", 0)) for d in docs)
    return {
        "sku_count": len(docs),
        "total_quantity": round(total_qty, 2),
        "total_buy_value_tl": round(total_buy, 2),
        "total_sell_value_tl": round(total_sell, 2),
        "potential_margin_tl": round(total_sell - total_buy, 2),
    }


async def _tool_get_finance_summary(args: dict, user: dict) -> dict:
    q: dict = {}
    if args.get("start_date") or args.get("end_date"):
        q["date"] = {}
        if args.get("start_date"):
            q["date"]["$gte"] = args["start_date"]
        if args.get("end_date"):
            q["date"]["$lte"] = args["end_date"]
    inc = await db.incomes.find(q, {"_id": 0, "amount": 1}).to_list(10000)
    exp = await db.expenses.find(q, {"_id": 0, "amount": 1}).to_list(10000)
    invs = await db.invoices.find(q, {"_id": 0, "amount": 1, "vat_amount": 1}).to_list(10000)
    return {
        "range": {"start": args.get("start_date"), "end": args.get("end_date")},
        "income_tl": round(sum(d["amount"] for d in inc), 2),
        "expense_tl": round(sum(d["amount"] for d in exp), 2),
        "profit_tl": round(sum(d["amount"] for d in inc) - sum(d["amount"] for d in exp), 2),
        "invoice_total_tl": round(sum(d["amount"] for d in invs), 2),
        "vat_total_tl": round(sum(d.get("vat_amount", 0) for d in invs), 2),
        "income_count": len(inc),
        "expense_count": len(exp),
    }


async def _tool_list_cariler(args: dict, user: dict) -> dict:
    docs = await db.cariler.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    for d in docs:
        await _attach_cari_totals(d)
    if args.get("search"):
        s = args["search"].lower()
        docs = [d for d in docs if s in d["name"].lower()]
    out = [{"id": d["id"], "name": d["name"], "phone": d.get("phone", ""),
            "total_alacak": d["total_alacak"], "total_odeme": d.get("total_odeme", 0),
            "remaining_alacak": d.get("remaining_alacak", 0), "total_borc": d["total_borc"], "net": d["net"]}
           for d in docs]
    return {"count": len(out), "items": out[:50]}


async def _tool_add_tire(args: dict, user: dict) -> dict:
    tire = TireIn(
        brand=args["brand"],
        model=args.get("model", ""),
        size=args["size"],
        season=args.get("season", "4mevsim"),
        dot=args.get("dot", ""),
        quantity=float(args.get("quantity", 0)),
        buy_price=float(args.get("buy_price", 0)),
        sell_price=float(args.get("sell_price", 0)),
        kdv_rate=float(args.get("kdv_rate", 20)),
    )
    doc = await create_tire(tire, user=user)  # type: ignore
    return {"ok": True, "tire_id": doc["id"], "label": _tire_label(doc), "quantity": doc["quantity"]}


async def _tool_update_tire_stock(args: dict, user: dict) -> dict:
    data = TireMovementIn(delta=float(args["delta"]), reason=args["reason"], note=args.get("note", ""))
    try:
        mv = await tire_movement(args["tire_id"], data, user=user)  # type: ignore
        return {"ok": True, "before": mv["before"], "after": mv["after"], "delta": mv["delta"]}
    except HTTPException as e:
        return {"error": str(e.detail)}


async def _tool_add_income(args: dict, user: dict) -> dict:
    doc = await create_income(IncomeIn(description=args["description"], amount=float(args["amount"]), date=args.get("date")), user=user)  # type: ignore
    return {"ok": True, "id": doc["id"], "amount": doc["amount"]}


async def _tool_add_expense(args: dict, user: dict) -> dict:
    doc = await create_expense(ExpenseIn(description=args["description"], amount=float(args["amount"]), date=args.get("date")), user=user)  # type: ignore
    return {"ok": True, "id": doc["id"], "amount": doc["amount"]}


async def _resolve_cari(args: dict) -> dict:
    if args.get("cari_id"):
        doc = await db.cariler.find_one({"id": args["cari_id"]}, {"_id": 0})
        if doc:
            return doc
    name = (args.get("cari_name") or "").strip()
    if not name:
        raise HTTPException(400, "Cari adı veya id gerekli")
    exact = await db.cariler.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"_id": 0})
    if exact:
        return exact
    matches = await db.cariler.find({"name": {"$regex": re.escape(name), "$options": "i"}}, {"_id": 0}).to_list(10)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise HTTPException(404, f"'{name}' adında cari bulunamadı")
    raise HTTPException(400, "Birden fazla cari eşleşti: " + ", ".join(m["name"] for m in matches))


def _need_confirm(args: dict, summary: str) -> Optional[dict]:
    if args.get("confirmed"):
        return None
    return {"error": "Onay gerekli", "hint": f"Kullanıcıya şunu sor ve onaylarsa confirmed=true ile tekrar çağır: {summary}"}


async def _tool_add_spending(args: dict, user: dict) -> dict:
    data = SpendingIn(category=args.get("category") or "company", name=args["name"],
                      amount=float(args["amount"]), date=args.get("date"))
    doc = await create_spending(data, user=user)  # type: ignore
    return {"ok": True, "id": doc["id"], "category": doc["category"], "amount": doc["amount"]}


async def _tool_add_todo(args: dict, user: dict) -> dict:
    doc = await create_todo(TodoIn(title=args["title"], note=args.get("note", "")), user=user)  # type: ignore
    return {"ok": True, "id": doc["id"], "title": doc["title"]}


async def _tool_complete_todo(args: dict, user: dict) -> dict:
    doc = await update_todo(args["todo_id"], TodoUpdate(completed=bool(args.get("completed", True))), user=user)  # type: ignore
    return {"ok": True, "title": doc["title"], "completed": doc["completed"]}


async def _tool_add_cari(args: dict, user: dict) -> dict:
    doc = await create_cari(CariIn(name=args["name"], phone=args.get("phone", ""), address=args.get("address", ""),
                                   note=args.get("note", "")), user=user)  # type: ignore
    return {"ok": True, "id": doc["id"], "name": doc["name"]}


async def _tool_add_cari_transaction(args: dict, user: dict) -> dict:
    cari = await _resolve_cari(args)
    data = CariTxIn(type=args["type"], amount=float(args["amount"]), description=args.get("description", ""), date=args.get("date"))
    doc = await create_cari_tx(cari["id"], data, user=user)  # type: ignore
    await _attach_cari_totals(cari)
    return {"ok": True, "cari": cari["name"], "type": doc["type"], "amount": doc["amount"],
            "remaining_alacak": cari["remaining_alacak"], "total_borc": cari["total_borc"], "net": cari["net"]}


async def _tool_add_invoice(args: dict, user: dict) -> dict:
    doc = await create_invoice(InvoiceIn(description=args["description"], amount=float(args["amount"]), date=args.get("date")), user=user)  # type: ignore
    return {"ok": True, "id": doc["id"], "amount": doc["amount"], "vat_amount": doc["vat_amount"]}


async def _tool_update_tire(args: dict, user: dict) -> dict:
    tire = await db.tires.find_one({"id": args["tire_id"]}, {"_id": 0})
    if not tire:
        return {"error": "Lastik bulunamadı"}
    fields = {k: tire.get(k) for k in TireIn.model_fields}
    for k in ("brand", "model", "size", "season", "dot", "buy_price", "sell_price", "kdv_rate", "note", "quantity"):
        if args.get(k) is not None:
            fields[k] = args[k]
    doc = await update_tire(args["tire_id"], TireIn(**{k: v for k, v in fields.items() if v is not None}), user=user)  # type: ignore
    return {"ok": True, "label": _tire_label(doc), "sell_price": doc.get("sell_price"), "buy_price": doc.get("buy_price"), "quantity": doc.get("quantity")}


async def _tool_create_sale(args: dict, user: dict) -> dict:
    items = []
    for it in args.get("items") or []:
        tire = await db.tires.find_one({"id": it.get("tire_id")}, {"_id": 0})
        if not tire:
            return {"error": f"Lastik bulunamadı: {it.get('tire_id')}"}
        price = it.get("unit_price")
        items.append(SaleItemIn(tire_id=tire["id"], quantity=float(it.get("quantity", 1)),
                                unit_price=float(price if price is not None else tire.get("sell_price", 0)),
                                discount=float(it.get("discount", 0) or 0)))
    if not items:
        return {"error": "En az bir lastik gerekli"}
    cari_id = None
    if args.get("cari_id") or args.get("cari_name"):
        cari_id = (await _resolve_cari(args))["id"]
    pay = args.get("payment_method") or "nakit"
    gross = sum(i.quantity * i.unit_price - i.discount for i in items) - float(args.get("overall_discount", 0) or 0)
    blocked = _need_confirm(args, f"{len(items)} kalem, toplam ~{round(gross, 2)}₺, ödeme: {pay}")
    if blocked:
        return blocked
    sale = await create_sale(SaleIn(cari_id=cari_id, items=items, overall_discount=float(args.get("overall_discount", 0) or 0),
                                    payment_method=pay, note=args.get("note", ""), date=args.get("date")), user=user)  # type: ignore
    return {"ok": True, "sale_id": sale["id"], "total": sale["total"], "payment_method": sale["payment_method"], "cari": sale.get("cari_name")}


RECORD_COLLECTIONS = {
    "income": "incomes", "expense": "expenses", "spending": "spendings", "todo": "todos",
    "invoice": "invoices", "cari_tx": "cari_transactions", "sale": "sales", "tire": "tires", "cari": "cariler",
}


async def _tool_list_records(args: dict, user: dict) -> dict:
    rtype = args["record_type"]
    q: dict = {}
    if rtype == "spending" and args.get("category"):
        q["category"] = args["category"]
    if rtype == "cari_tx":
        q["cari_id"] = (await _resolve_cari(args))["id"]
    if rtype == "todo" and args.get("only_open"):
        q["completed"] = False
    sort_key = "created_at" if rtype in ("todo", "tire", "cari") else "date"
    docs = await db[RECORD_COLLECTIONS[rtype]].find(q, {"_id": 0, "items": 0, "movement_ids": 0}).sort(sort_key, -1).to_list(500)
    if args.get("search"):
        s = args["search"].lower()
        docs = [d for d in docs if s in str(d).lower()]
    keep = ("id", "date", "description", "name", "title", "amount", "category", "completed", "type", "total",
            "cari_name", "payment_method", "brand", "size", "quantity", "note")
    out = [{k: d[k] for k in keep if k in d} for d in docs[: int(args.get("limit") or 20)]]
    return {"count": len(docs), "items": out}


async def _tool_delete_record(args: dict, user: dict) -> dict:
    rtype, rid = args["record_type"], args["record_id"]
    doc = await db[RECORD_COLLECTIONS[rtype]].find_one({"id": rid}, {"_id": 0})
    if not doc:
        return {"error": "Kayıt bulunamadı"}
    label = doc.get("description") or doc.get("name") or doc.get("title") or doc.get("cari_name") or rid
    blocked = _need_confirm(args, f"'{label}' kaydını ({rtype}) silmek")
    if blocked:
        return blocked
    if rtype == "cari_tx":
        await delete_cari_tx(doc["cari_id"], rid, user=user)  # type: ignore
    else:
        fn = {"income": delete_income, "expense": delete_expense, "spending": delete_spending, "todo": delete_todo,
              "invoice": delete_invoice, "sale": delete_sale, "tire": delete_tire, "cari": delete_cari}[rtype]
        await fn(rid, user=user)  # type: ignore
    return {"ok": True, "deleted": label}


_RECORD_TYPES = list(RECORD_COLLECTIONS.keys())
SAMPIYON_TOOLS += [
    {"type": "function", "function": {
        "name": "add_spending",
        "description": "Harcamalar sayfasına harcama ekler. category: company=Şirket, user1=1. kullanıcı, user2=2. kullanıcı (isimler sistem mesajında). Direkt yap.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Harcama adı"}, "amount": {"type": "number"},
            "category": {"type": "string", "enum": ["company", "user1", "user2"]}, "date": {"type": "string"}},
            "required": ["name", "amount"]}}},
    {"type": "function", "function": {
        "name": "add_todo", "description": "Yapılacaklar listesine görev ekler. Direkt yap.",
        "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "note": {"type": "string"}}, "required": ["title"]}}},
    {"type": "function", "function": {
        "name": "complete_todo", "description": "Görevi tamamlandı (veya completed=false ile geri al) işaretler. id için önce list_records(todo).",
        "parameters": {"type": "object", "properties": {"todo_id": {"type": "string"}, "completed": {"type": "boolean"}}, "required": ["todo_id"]}}},
    {"type": "function", "function": {
        "name": "add_cari", "description": "Yeni cari (müşteri/tedarikçi) ekler. Direkt yap.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "phone": {"type": "string"},
                                                        "address": {"type": "string"}, "note": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "add_cari_transaction",
        "description": "Cariye hareket ekler. type: alacak=cari bize borçlandı, borc=biz cariye borçlandık, odeme=cariden gelen ödeme (alacaktan düşer). Direkt yap.",
        "parameters": {"type": "object", "properties": {
            "cari_name": {"type": "string"}, "cari_id": {"type": "string"},
            "type": {"type": "string", "enum": ["alacak", "borc", "odeme"]}, "amount": {"type": "number"},
            "description": {"type": "string"}, "date": {"type": "string"}}, "required": ["type", "amount"]}}},
    {"type": "function", "function": {
        "name": "add_invoice", "description": "Fatura ekler (tutar KDV dahil, %20 KDV otomatik hesaplanır). Direkt yap.",
        "parameters": {"type": "object", "properties": {"description": {"type": "string"}, "amount": {"type": "number"},
                                                        "date": {"type": "string"}}, "required": ["description", "amount"]}}},
    {"type": "function", "function": {
        "name": "update_tire", "description": "Lastik bilgilerini (fiyat, marka, model, DOT, adet vb.) günceller. Sadece değişen alanları gönder. Direkt yap.",
        "parameters": {"type": "object", "properties": {
            "tire_id": {"type": "string"}, "brand": {"type": "string"}, "model": {"type": "string"}, "size": {"type": "string"},
            "season": {"type": "string", "enum": ["yaz", "kis", "4mevsim"]}, "dot": {"type": "string"},
            "buy_price": {"type": "number"}, "sell_price": {"type": "number"}, "kdv_rate": {"type": "number"},
            "quantity": {"type": "number"}, "note": {"type": "string"}}, "required": ["tire_id"]}}},
    {"type": "function", "function": {
        "name": "create_sale",
        "description": "Lastik satışı yapar: stoktan düşer, peşinse gelir yazar, veresiyede cariye alacak yazar. ONAY GEREKİR: önce özetle, kullanıcı onaylarsa confirmed=true. unit_price boşsa lastiğin satış fiyatı kullanılır. Veresiye için cari zorunlu.",
        "parameters": {"type": "object", "properties": {
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "tire_id": {"type": "string"}, "quantity": {"type": "number"}, "unit_price": {"type": "number"},
                "discount": {"type": "number"}}, "required": ["tire_id", "quantity"]}},
            "cari_name": {"type": "string"}, "cari_id": {"type": "string"},
            "payment_method": {"type": "string", "enum": ["nakit", "kart", "havale", "veresiye"]},
            "overall_discount": {"type": "number"}, "note": {"type": "string"}, "date": {"type": "string"},
            "confirmed": {"type": "boolean"}}, "required": ["items"]}}},
    {"type": "function", "function": {
        "name": "list_records",
        "description": "Kayıtları listeler (silme/tamamlama için id bulmak veya göstermek için). cari_tx için cari_name gerekli.",
        "parameters": {"type": "object", "properties": {
            "record_type": {"type": "string", "enum": _RECORD_TYPES}, "search": {"type": "string"},
            "category": {"type": "string", "enum": ["company", "user1", "user2"]}, "cari_name": {"type": "string"},
            "only_open": {"type": "boolean"}, "limit": {"type": "number"}}, "required": ["record_type"]}}},
    {"type": "function", "function": {
        "name": "delete_record",
        "description": "Bir kaydı siler (satış silinirse stok/gelir geri alınır). ONAY GEREKİR: önce kullanıcıya sor, onaylarsa confirmed=true.",
        "parameters": {"type": "object", "properties": {
            "record_type": {"type": "string", "enum": _RECORD_TYPES}, "record_id": {"type": "string"},
            "confirmed": {"type": "boolean"}}, "required": ["record_type", "record_id"]}}},
]


SAMPIYON_TOOL_HANDLERS = {
    "search_tires": _tool_search_tires,
    "get_stock_summary": _tool_get_stock_summary,
    "get_finance_summary": _tool_get_finance_summary,
    "list_cariler": _tool_list_cariler,
    "add_tire": _tool_add_tire,
    "update_tire_stock": _tool_update_tire_stock,
    "add_income": _tool_add_income,
    "add_expense": _tool_add_expense,
    "list_recent_sales": _tool_list_recent_sales,
    "add_spending": _tool_add_spending,
    "add_todo": _tool_add_todo,
    "complete_todo": _tool_complete_todo,
    "add_cari": _tool_add_cari,
    "add_cari_transaction": _tool_add_cari_transaction,
    "add_invoice": _tool_add_invoice,
    "update_tire": _tool_update_tire,
    "create_sale": _tool_create_sale,
    "list_records": _tool_list_records,
    "delete_record": _tool_delete_record,
}
SAMPIYON_WRITE_TOOLS = {"add_tire", "update_tire_stock", "add_income", "add_expense", "add_spending", "add_todo",
                        "complete_todo", "add_cari", "add_cari_transaction", "add_invoice", "update_tire",
                        "create_sale", "delete_record"}


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


async def _read_upload_limited(file: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    raw = await file.read()
    if len(raw) > max_bytes:
        raise HTTPException(400, f"Dosya {max_bytes // (1024 * 1024)}MB'ı aşamaz")
    return raw


class SampiyonChatIn(BaseModel):
    message: str
    history: List[dict] = []  # [{"role": "user"|"assistant", "content": "..."}]


async def _load_sampiyon_history(user_id: str, limit: int) -> List[dict]:
    docs = await db.sampiyon_messages.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return list(reversed(docs))


def _build_sampiyon_chat(data: "SampiyonChatIn", user: dict, raw_history: List[dict]):
    from emergentintegrations.llm.chat import LlmChat
    history: List[dict] = []
    for h in raw_history[-12:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            history.append({"role": role, "content": content})
    while history and history[0]["role"] != "user":
        history.pop(0)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system = (f"{SAMPIYON_SYSTEM_PROMPT}\n\nBugün: {today}. Konuştuğun kullanıcı: {user['name']}. "
              f"Harcama kategorileri: company=Şirket, user1={os.environ['USER1_NAME']}, user2={os.environ['USER2_NAME']}.")
    return (
        LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"sampiyon-{user['id']}", system_message=system,
                initial_messages=[{"role": "system", "content": system}] + history)
        .with_model(SAMPIYON_MODEL_PROVIDER, SAMPIYON_MODEL_NAME)
        .with_tools(SAMPIYON_TOOLS, tool_choice="auto")
    )


async def _run_sampiyon_tool(tc, user: dict) -> dict:
    handler = SAMPIYON_TOOL_HANDLERS.get(tc.name)
    if not handler:
        return {"error": f"Bilinmeyen araç: {tc.name}"}
    try:
        return await handler(tc.arguments or {}, user)
    except HTTPException as e:
        return {"error": str(e.detail)}
    except Exception as e:
        logger.exception(f"Şampiyon araç hatası: {tc.name}")
        return {"error": str(e)}


async def _sampiyon_events(data: "SampiyonChatIn", user: dict):
    from emergentintegrations.llm.chat import UserMessage, TextDelta, ToolCallStart, ToolCallReady, StreamDone
    import json as _json
    raw_history = data.history or await _load_sampiyon_history(user["id"], 12)
    chat = _build_sampiyon_chat(data, user, raw_history)
    await db.sampiyon_messages.insert_one({"id": str(uuid.uuid4()), "user_id": user["id"], "role": "user",
                                           "content": data.message, "created_at": now_iso()})
    msg = UserMessage(text=data.message)
    reply, trace = "", []
    for _ in range(8):
        pending = []
        async for ev in chat.stream_message(msg):
            if isinstance(ev, TextDelta):
                if ev.content:
                    reply += ev.content
                    yield {"type": "delta", "content": ev.content}
            elif isinstance(ev, ToolCallStart):
                yield {"type": "tool", "name": ev.name}
            elif isinstance(ev, ToolCallReady):
                pending.append(ev.tool_call)
            elif isinstance(ev, StreamDone):
                break
        if not pending:
            break
        for tc in pending:
            result = await _run_sampiyon_tool(tc, user)
            trace.append({"name": tc.name, "arguments": tc.arguments, "result": result})
            chat.add_tool_result(tc.id, _json.dumps(result, ensure_ascii=False, default=str))
        if reply and not reply.endswith(("\n", " ")):
            reply += "\n"
            yield {"type": "delta", "content": "\n"}
        msg = None
    changed = any(t["name"] in SAMPIYON_WRITE_TOOLS and isinstance(t["result"], dict) and t["result"].get("ok") for t in trace)
    await log_activity(user, "chat", "Sampiyon", f"Mesaj: {data.message[:120]}")
    await db.sampiyon_messages.insert_one({"id": str(uuid.uuid4()), "user_id": user["id"], "role": "assistant",
                                           "content": reply.strip() or "Tamamdır.", "tool_names": [t["name"] for t in trace],
                                           "created_at": now_iso()})
    yield {"type": "done", "reply": reply.strip(), "tool_trace": trace, "data_changed": changed}


@api_router.get("/sampiyon/history")
async def sampiyon_history(user: dict = Depends(get_current_user)):
    """Kullanıcının kayıtlı Şampiyon sohbeti (son 60 mesaj)."""
    return await _load_sampiyon_history(user["id"], 60)


@api_router.delete("/sampiyon/history")
async def clear_sampiyon_history(user: dict = Depends(get_current_user)):
    res = await db.sampiyon_messages.delete_many({"user_id": user["id"]})
    return {"ok": True, "deleted": res.deleted_count}


@api_router.post("/sampiyon/chat")
async def sampiyon_chat(data: SampiyonChatIn, user: dict = Depends(get_current_user)):
    """Şampiyon sohbet (non-stream)."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI anahtarı yapılandırılmamış")
    try:
        final = {}
        async for ev in _sampiyon_events(data, user):
            if ev["type"] == "done":
                final = ev
    except Exception as e:
        logger.exception("Şampiyon chat hatası")
        raise HTTPException(500, f"AI hatası: {e}")
    return {"reply": final.get("reply", ""), "tool_trace": final.get("tool_trace", []), "data_changed": final.get("data_changed", False)}


@api_router.post("/sampiyon/chat/stream")
async def sampiyon_chat_stream(data: SampiyonChatIn, user: dict = Depends(get_current_user)):
    """Şampiyon sohbet — SSE akışı (delta / tool / done / error)."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI anahtarı yapılandırılmamış")
    import json as _json
    from fastapi.responses import StreamingResponse

    async def gen():
        try:
            async for ev in _sampiyon_events(data, user):
                yield f"data: {_json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            logger.exception("Şampiyon stream hatası")
            yield f"data: {_json.dumps({'type': 'error', 'message': f'AI hatası: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api_router.post("/sampiyon/transcribe")
async def sampiyon_transcribe(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Ses dosyasını Whisper ile Türkçe metne çevirir."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI anahtarı yapılandırılmamış")
    raw = await _read_upload_limited(file, max_bytes=25 * 1024 * 1024)
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
        stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
        buf = io.BytesIO(raw)
        buf.name = file.filename or "voice.webm"
        resp = await stt.transcribe(file=buf, model="whisper-1", response_format="json", language="tr")
        text = getattr(resp, "text", "") or ""
    except Exception as e:
        logger.exception("STT hatası")
        raise HTTPException(500, f"Ses çevrilemedi: {e}")
    return {"text": text}


SAMPIYON_TTS_INSTRUCTIONS = (
    "Türkçe konuşan, 30'lu yaşlarda, samimi ve enerjik bir erkek oto lastik ustası gibi konuş. "
    "Doğal, sıcak ve akıcı bir tonla; robot gibi değil, arkadaşınla konuşur gibi. "
    "Çok hızlı ve kıpır kıpır bir tempoyla konuş; cümlelerin arasında neredeyse hiç duraklama olmasın, kekeleyen değil akıcı ama çabuk konuşan biri gibi ol. "
    "Sayıları ve para birimlerini doğal Türkçe oku."
)


class SampiyonTTSIn(BaseModel):
    text: str
    voice: Optional[str] = "ash"


@api_router.post("/sampiyon/tts")
async def sampiyon_tts(data: SampiyonTTSIn, user: dict = Depends(get_current_user)):
    """Metni OpenAI gpt-4o-mini-tts ile doğal sese çevirir (MP3)."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI anahtarı yapılandırılmamış")
    text = (data.text or "").strip()[:4000]
    if not text:
        raise HTTPException(400, "Metin boş")
    try:
        from openai import AsyncOpenAI
        from fastapi.responses import Response
        client = AsyncOpenAI(api_key=EMERGENT_LLM_KEY, base_url="https://integrations.emergentagent.com/llm")
        async with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=data.voice or "ash",
            input=text,
            instructions=SAMPIYON_TTS_INSTRUCTIONS,
            response_format="mp3",
        ) as resp:
            audio_bytes = b"".join([chunk async for chunk in resp.iter_bytes()])
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.exception("TTS hatası")
        raise HTTPException(500, f"Ses üretilemedi: {e}")


@api_router.post("/sampiyon/parse-tire-document")
async def parse_tire_document(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Yüklenen Excel/PDF belgesinden Şampiyon ile lastik ürünlerini çıkarır.
    Stok DEĞİŞTİRMEZ; önizleme için parsed listesini döner (frontend ayrıca import-confirm çağırır)."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI anahtarı yapılandırılmamış")
    raw = await _read_upload_limited(file)
    filename = (file.filename or "").lower()

    # 1) Metni çıkar
    text = ""
    MAX_SHEET_ROWS = 2000
    if filename.endswith(".xlsx") or filename.endswith(".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), data_only=True)
        row_count = 0
        for ws in wb.worksheets:
            for r in ws.iter_rows(values_only=True):
                row_count += 1
                if row_count > MAX_SHEET_ROWS:
                    break
                row = [str(c).strip() if c is not None else "" for c in r]
                if any(row):
                    text += " | ".join(row) + "\n"
            if row_count > MAX_SHEET_ROWS:
                break
    elif filename.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages[:100])
    else:
        raise HTTPException(400, "Yalnızca .xlsx veya .pdf dosyaları desteklenir")

    text = text.strip()
    if not text:
        raise HTTPException(400, "Dosyadan metin okunamadı. Taranmış PDF ise şimdilik desteklenmiyor.")
    if len(text) > 25000:
        text = text[:25000]

    # 2) LLM ile çıkarım
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json as _json
        extraction_prompt = """Aşağıdaki belge içeriğinden lastik ürünlerini çıkar. Her ürün için şu alanları doldur:
- brand: Marka (zorunlu, ör: Michelin, Bridgestone)
- model: Model adı (opsiyonel)
- size: Ebat (ör: 205/55 R16) — zorunlu
- season: "yaz", "kis" veya "4mevsim" (bilinmiyorsa "4mevsim")
- dot: DOT/üretim yılı (opsiyonel)
- quantity: Adet (sayı, bilinmiyorsa 1)
- buy_price: Birim alış fiyatı TL (sayı, KDV hariç, varsa)
- kdv_rate: KDV oranı (%20 varsayılan)
- confidence: 0.0-1.0 arası güven değeri

YANIT: Sadece geçerli JSON dizisi döndür. Başka hiçbir metin ekleme. Örnek:
[{"brand":"Michelin","size":"205/55 R16","season":"yaz","quantity":4,"buy_price":2800,"kdv_rate":20,"confidence":0.9}]"""

        chat = (
            LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"extract-{uuid.uuid4()}",
                    system_message=extraction_prompt)
            .with_model(SAMPIYON_MODEL_PROVIDER, SAMPIYON_MODEL_NAME)
        )
        resp = await chat.send_message(UserMessage(text=f"Belge:\n{text}"))
        reply = (getattr(resp, "content", None) or str(resp)).strip()

        # JSON diziyi yakala
        import re as _re
        m = _re.search(r"\[.*\]", reply, _re.DOTALL)
        if not m:
            raise ValueError("AI yanıtında JSON dizisi bulunamadı")
        items = _json.loads(m.group(0))
        if not isinstance(items, list):
            raise ValueError("Beklenen format: liste")

        # Normalize et
        clean = []
        for it in items:
            if not isinstance(it, dict):
                continue
            brand = str(it.get("brand", "")).strip()
            size = str(it.get("size", "")).strip()
            if not brand and not size:
                continue
            clean.append({
                "brand": brand or "Belirtilmemiş",
                "model": str(it.get("model", "") or "").strip(),
                "size": size or "Belirtilmemiş",
                "season": it.get("season") if it.get("season") in ("yaz", "kis", "4mevsim") else "4mevsim",
                "dot": str(it.get("dot", "") or "").strip(),
                "quantity": float(it.get("quantity", 1) or 1),
                "buy_price": float(it.get("buy_price", 0) or 0),
                "sell_price": float(it.get("sell_price", 0) or 0),
                "kdv_rate": float(it.get("kdv_rate", 20) or 20),
                "confidence": float(it.get("confidence", 0.5) or 0.5),
                "selected": True,
            })
        return {"count": len(clean), "items": clean, "filename": file.filename}
    except Exception as e:
        logger.exception("Belge AI çıkarımı hatası")
        raise HTTPException(500, f"Belge okunamadı: {e}")


class TireImportConfirmIn(BaseModel):
    items: List[TireIn]


@api_router.post("/sampiyon/import-confirm")
async def confirm_tire_import(data: TireImportConfirmIn, user: dict = Depends(get_current_user)):
    """Onaylanmış lastik listesini stoğa ekler."""
    if not data.items:
        raise HTTPException(400, "Eklenecek lastik yok")
    created = []
    for t in data.items:
        doc = await create_tire(t, user=user)  # type: ignore
        created.append(doc)
    await log_activity(user, "import", "Stok", f"{len(created)} lastik AI önizleme ile içe aktarıldı")
    return {"count": len(created), "items": created}


# -----------------------------
# App setup
# -----------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # İndeksler
    await db.users.create_index("email", unique=True)
    await db.activity_logs.create_index([("timestamp", -1)])
    await db.incomes.create_index("date")
    await db.expenses.create_index("date")
    await db.invoices.create_index("date")
    await db.sampiyon_messages.create_index([("user_id", 1), ("created_at", -1)])

    # İki kullanıcıyı seed et (user_key üzerinden migration)
    seed_users = [
        {
            "email": os.environ["USER1_EMAIL"].lower(),
            "password": os.environ["USER1_PASSWORD"],
            "name": os.environ["USER1_NAME"],
            "role": "user",
            "user_key": "user1",
        },
        {
            "email": os.environ["USER2_EMAIL"].lower(),
            "password": os.environ["USER2_PASSWORD"],
            "name": os.environ["USER2_NAME"],
            "role": "user",
            "user_key": "user2",
        },
    ]

    # Eski kullanıcıları temizle: user_key henüz yoksa bile email .env'dekiyle uyuşmayanları sil
    valid_emails = {u["email"] for u in seed_users}
    valid_keys = {u["user_key"] for u in seed_users}
    await db.users.delete_many({
        "email": {"$nin": list(valid_emails)},
        "user_key": {"$nin": list(valid_keys)},
    })

    for u in seed_users:
        existing = await db.users.find_one({"user_key": u["user_key"]})
        if existing is None:
            existing = await db.users.find_one({"email": u["email"]})
        if existing is None:
            doc = {
                "id": str(uuid.uuid4()),
                "email": u["email"],
                "name": u["name"],
                "role": u["role"],
                "user_key": u["user_key"],
                "password_hash": hash_password(u["password"]),
                "created_at": now_iso(),
            }
            await db.users.insert_one(doc)
            logger.info(f"Seeded user: {u['email']}")
        else:
            # Email/isim/şifre .env'den güncellenmişse eşitle
            update = {"user_key": u["user_key"], "email": u["email"], "name": u["name"], "role": u["role"]}
            if not verify_password(u["password"], existing.get("password_hash", "")):
                update["password_hash"] = hash_password(u["password"])
            await db.users.update_one({"id": existing["id"]}, {"$set": update})
            logger.info(f"Updated user ({u['user_key']}): {u['email']}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
