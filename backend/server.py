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

from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Request
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
    email: EmailStr
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

class IncomeOut(IncomeIn):
    id: str
    created_by: str
    created_by_name: str
    created_at: str

class ExpenseIn(BaseModel):
    description: str
    amount: float
    date: Optional[str] = None

class ExpenseOut(ExpenseIn):
    id: str
    created_by: str
    created_by_name: str
    created_at: str

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

# ---- Gelirler ----
@api_router.get("/incomes", response_model=List[IncomeOut])
async def list_incomes(user: dict = Depends(get_current_user)):
    docs = await db.incomes.find({}, {"_id": 0}).sort("date", -1).to_list(5000)
    return docs

@api_router.post("/incomes", response_model=IncomeOut)
async def create_income(data: IncomeIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "description": data.description,
        "amount": float(data.amount),
        "date": _resolve_date(data.date),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.incomes.insert_one(doc)
    await log_activity(user, "create", "Gelirler", f"{doc['description']} / {doc['amount']}₺")
    doc.pop("_id", None)
    return doc

@api_router.put("/incomes/{item_id}", response_model=IncomeOut)
async def update_income(item_id: str, data: IncomeIn, user: dict = Depends(get_current_user)):
    update = {"description": data.description, "amount": float(data.amount)}
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
    doc = {
        "id": str(uuid.uuid4()),
        "description": data.description,
        "amount": float(data.amount),
        "date": _resolve_date(data.date),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(doc)
    await log_activity(user, "create", "Giderler", f"{doc['description']} / {doc['amount']}₺")
    doc.pop("_id", None)
    return doc

@api_router.put("/expenses/{item_id}", response_model=ExpenseOut)
async def update_expense(item_id: str, data: ExpenseIn, user: dict = Depends(get_current_user)):
    update = {"description": data.description, "amount": float(data.amount)}
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
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail="E-posta gönderilemedi")
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise HTTPException(status_code=500, detail="E-posta gönderme hatası")


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
    """Düşük stok uyarısını iki kullanıcıya da e-posta ile gönderir."""
    all_items = await db.inventory.find({}, {"_id": 0}).to_list(5000)
    low = [i for i in all_items if float(i.get("remaining_qty", 0)) > 0]
    if not low:
        raise HTTPException(400, "Düşük stok bulunmuyor")

    # Alıcıları server-side records'tan al (G4 - caller recipient supply yok)
    recipients = await db.users.find({}, {"_id": 0, "email": 1, "name": 1}).to_list(10)
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
    inv = await db.invoices.find({}, {"_id": 0, "amount": 1, "vat_amount": 1}).to_list(5000)
    todos = await db.todos.find({"completed": False}, {"_id": 0, "id": 1}).to_list(5000)
    return {
        "total_income": round(sum(d["amount"] for d in inc), 2),
        "total_expense": round(sum(d["amount"] for d in exp), 2),
        "total_invoices": round(sum(d["amount"] for d in inv), 2),
        "total_vat": round(sum(d.get("vat_amount", 0) for d in inv), 2),
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

    # İki kullanıcıyı seed et
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
    for u in seed_users:
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
            # .env değişmişse hash'i güncelle
            if not verify_password(u["password"], existing["password_hash"]):
                await db.users.update_one(
                    {"email": u["email"]},
                    {"$set": {"password_hash": hash_password(u["password"]), "name": u["name"], "user_key": u["user_key"]}},
                )
                logger.info(f"Updated password/name for: {u['email']}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
