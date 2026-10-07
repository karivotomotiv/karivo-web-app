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
    raw = await file.read()
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

# ---- Stok ----
@api_router.get("/inventory", response_model=List[InventoryOut])
async def list_inventory(user: dict = Depends(get_current_user)):
    return await db.inventory.find({}, {"_id": 0}).sort("product_name", 1).to_list(5000)

@api_router.post("/inventory", response_model=InventoryOut)
async def create_inventory(data: InventoryIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "product_name": data.product_name,
        "required_qty": float(data.required_qty),
        "received_qty": float(data.received_qty),
        "remaining_qty": round(float(data.required_qty) - float(data.received_qty), 2),
        "purchase_date": _resolve_date(data.purchase_date),
        "purchase_price": float(data.purchase_price),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.inventory.insert_one(doc)
    await log_activity(user, "create", "Stok", f"{doc['product_name']} / kalan: {doc['remaining_qty']}")
    doc.pop("_id", None)
    return doc

@api_router.put("/inventory/{item_id}", response_model=InventoryOut)
async def update_inventory(item_id: str, data: InventoryIn, user: dict = Depends(get_current_user)):
    update = {
        "product_name": data.product_name,
        "required_qty": float(data.required_qty),
        "received_qty": float(data.received_qty),
        "remaining_qty": round(float(data.required_qty) - float(data.received_qty), 2),
        "purchase_price": float(data.purchase_price),
    }
    if data.purchase_date:
        update["purchase_date"] = data.purchase_date
    res = await db.inventory.find_one_and_update({"id": item_id}, {"$set": update})
    if not res:
        raise HTTPException(404, "Stok kaydı bulunamadı")
    await log_activity(user, "update", "Stok", f"{data.product_name}")
    return await db.inventory.find_one({"id": item_id}, {"_id": 0})

@api_router.delete("/inventory/{item_id}")
async def delete_inventory(item_id: str, user: dict = Depends(get_current_user)):
    doc = await db.inventory.find_one({"id": item_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Stok kaydı bulunamadı")
    await db.inventory.delete_one({"id": item_id})
    await log_activity(user, "delete", "Stok", f"{doc.get('product_name','')}")
    return {"ok": True}

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


async def _attach_cari_totals(cari_doc: dict) -> dict:
    txs = await db.cari_transactions.find({"cari_id": cari_doc["id"]}, {"_id": 0, "type": 1, "amount": 1}).to_list(5000)
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
async def inventory_alerts(user: dict = Depends(get_current_user)):
    """Kalan miktarı > 0 olan (eksik) ürünler."""
    all_items = await db.inventory.find({}, {"_id": 0}).to_list(5000)
    low = [i for i in all_items if float(i.get("remaining_qty", 0)) > 0]
    low.sort(key=lambda x: float(x.get("remaining_qty", 0)), reverse=True)
    return {"count": len(low), "items": low}


@api_router.post("/inventory/send-low-stock-email")
async def send_low_stock_email(user: dict = Depends(get_current_user)):
    """Düşük stok uyarısını kullanıcıların kayıtlı bildirim e-postalarına gönderir."""
    all_items = await db.inventory.find({}, {"_id": 0}).to_list(5000)
    low = [i for i in all_items if float(i.get("remaining_qty", 0)) > 0]
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
        f'<td style="padding:12px;background:#f1f5f9;border-radius:8px"><div style="font-size:11px;color:#475569;text-transform:uppercase;letter-spacing:1px">Net Kâr</div><div style="font-size:16px;font-weight:800;color:{profit_color}">{tr(profit)}</div></td>'
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
    cari_txs = await db.cari_transactions.find({}, {"_id": 0, "date": 1, "type": 1, "amount": 1}).to_list(10000)

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
    for row in cari_txs:
        m = _month(row.get("date"))
        if not m:
            continue
        b = buckets.setdefault(m, {"month": m, "income": 0, "expense": 0, "invoice": 0, "vat": 0})
        if row.get("type") == "alacak":
            b["income"] += float(row.get("amount", 0))
        elif row.get("type") == "borc":
            b["expense"] += float(row.get("amount", 0))
        # odeme: not reflected in dashboard income/expense (only affects per-cari remaining)

    rows = []
    for m in sorted(buckets.keys()):
        b = buckets[m]
        rows.append({
            "month": m,
            "income": round(b["income"], 2),
            "expense": round(b["expense"], 2),
            "invoice": round(b["invoice"], 2),
            "vat": round(b["vat"], 2),
            "profit": round(b["income"] - b["expense"], 2),
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
    raw = await file.read()
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
