import { useEffect, useRef, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, Package, Search, Upload, ArrowDown, ArrowUp, Sparkles, Check, X, CircleDot, Boxes, ChevronDown, GitMerge } from "lucide-react";
import { DuplicatesDialog } from "@/components/stock/DuplicatesDialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

const SEASON_META = {
  yaz: { label: "Yaz", color: "bg-amber-100 text-amber-700 border-amber-200" },
  kis: { label: "Kış", color: "bg-sky-100 text-sky-700 border-sky-200" },
  "4mevsim": { label: "4 Mevsim", color: "bg-emerald-100 text-emerald-700 border-emerald-200" },
};

const MOVEMENT_REASONS = [
  { value: "alis", label: "Alış" },
  { value: "satis", label: "Satış" },
  { value: "iade", label: "İade" },
  { value: "sayim-duzeltme", label: "Sayım Düzeltme" },
  { value: "fire", label: "Fire" },
  { value: "diger", label: "Diğer" },
];

const emptyTire = { product_type: "lastik", name: "", category: "", unit: "adet", brand: "", model: "", size: "", season: "4mevsim", dot: "", quantity: 0, buy_price: 0, sell_price: 0, kdv_rate: 20, note: "" };
const UNITS = ["adet", "takım", "litre", "kutu", "paket", "metre"];
const isOther = (t) => t.product_type === "diger";
const NO_CAT = "Kategorisiz";
const catOf = (t) => (t.category || "").trim() || NO_CAT;

export default function Stok() {
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [seasonFilter, setSeasonFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [dup, setDup] = useState(null);
  const [dupsOpen, setDupsOpen] = useState(false);
  const [catFilter, setCatFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyTire);
  const [loading, setLoading] = useState(false);
  // movement dialog
  const [mvOpen, setMvOpen] = useState(false);
  const [mvTire, setMvTire] = useState(null);
  const [mvForm, setMvForm] = useState({ delta: 1, reason: "alis", note: "", direction: "in" });
  // AI import
  const [importOpen, setImportOpen] = useState(false);
  const [importItems, setImportItems] = useState([]);
  const [importName, setImportName] = useState("");
  const [importing, setImporting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const fileRef = useRef(null);
  const [params] = useSearchParams();
  const highlightId = params.get("tire");
  const [threshold, setThreshold] = useState(4);

  const load = async () => {
    try { const { data } = await api.get("/tires"); setItems(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); api.get("/settings/stock").then(({ data }) => setThreshold(data.critical_threshold)).catch(() => {}); }, []);
  useEffect(() => {
    if (!highlightId || !items.length) return;
    const t = items.find((x) => x.id === highlightId);
    if (!t) { toast.info("Ürün bulunamadı"); return; }
    setSearch("");
    setSeasonFilter("all");
    setTimeout(() => document.querySelector(`[data-testid="tire-row-${highlightId}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 150);
  }, [highlightId, items]);

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    return items.filter((t) => {
      const type = isOther(t) ? "diger" : "lastik";
      if (typeFilter !== "all" && type !== typeFilter) return false;
      if (typeFilter === "diger" && catFilter !== "all" && catOf(t) !== catFilter) return false;
      if (seasonFilter !== "all" && (isOther(t) || t.season !== seasonFilter)) return false;
      if (!s) return true;
      const hay = `${t.name || ""} ${t.category || ""} ${t.brand} ${t.model} ${t.size} ${t.dot} ${t.note}`.toLowerCase();
      return hay.includes(s);
    });
  }, [items, search, seasonFilter, typeFilter, catFilter]);

  const categoryStats = useMemo(() => {
    const map = new Map();
    for (const t of items.filter(isOther)) {
      const k = catOf(t);
      const r = map.get(k) || { name: k, count: 0, qty: 0, buyVal: 0, sellVal: 0 };
      const q = Number(t.quantity || 0);
      r.count += 1; r.qty += q; r.buyVal += q * Number(t.buy_price || 0); r.sellVal += q * Number(t.sell_price || 0);
      map.set(k, r);
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name, "tr"));
  }, [items]);

  const openNew = (product_type = "lastik") => { setEditing(null); setForm({ ...emptyTire, product_type }); setOpen(true); };
  const openEdit = (it) => {
    setEditing(it);
    setForm({
      product_type: it.product_type || "lastik", name: it.name || "", category: it.category || "", unit: it.unit || "adet",
      brand: it.brand || "", model: it.model || "", size: it.size || "",
      season: it.season || "4mevsim", dot: it.dot || "", quantity: it.quantity || 0,
      buy_price: it.buy_price || 0, sell_price: it.sell_price || 0,
      kdv_rate: it.kdv_rate || 20, note: it.note || "",
    });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    const other = form.product_type === "diger";
    if (other ? !form.name.trim() : !form.brand.trim() || !form.size.trim()) { toast.error(other ? "Ürün adı zorunludur" : "Marka ve ebat zorunludur"); return; }
    setLoading(true);
    try {
      const payload = {
        ...form,
        name: form.name.trim(), category: form.category.trim(),
        brand: form.brand.trim(), model: form.model.trim(), size: other ? "" : form.size.trim(),
        dot: form.dot.trim(), note: form.note.trim(),
        quantity: Number(form.quantity), buy_price: Number(form.buy_price),
        sell_price: Number(form.sell_price), kdv_rate: Number(form.kdv_rate),
      };
      if (editing) {
        await api.put(`/tires/${editing.id}`, payload);
        toast.success("Ürün güncellendi");
      } else {
        if (other) {
          const { data: m } = await api.get("/tires/similar", { params: { name: payload.name, brand: payload.brand, model: payload.model } });
          const matches = [...(m.exact ? [{ ...m.exact, exact: true }] : []), ...m.similar];
          if (matches.length) { setDup({ matches, payload }); return; }
        }
        await api.post("/tires", payload);
        toast.success(other ? "Ürün eklendi" : "Lastik eklendi");
      }
      setOpen(false); load();
    } catch (e) { toast.error(extractError(e)); }
    finally { setLoading(false); }
  };

  const dupCreateNew = async () => {
    try { await api.post("/tires", dup.payload); toast.success("Yeni ürün eklendi"); setDup(null); setOpen(false); load(); }
    catch (e) { toast.error(extractError(e)); }
  };
  const dupStockIn = async (match) => {
    const qty = Number(dup.payload.quantity);
    try {
      if (qty > 0) {
        await api.post(`/tires/${match.id}/movement`, { delta: qty, reason: "alis", note: "Benzer ürün eşleştirmesiyle stok girişi" });
        toast.success(`${match.label}: +${qty} ${match.unit || "adet"} stok girişi yapıldı`);
      } else toast.info("Adet 0 olduğu için stok değişmedi");
      setDup(null); setOpen(false); load();
    } catch (e) { toast.error(extractError(e)); }
  };

  const remove = async (it) => {
    if (!window.confirm(`"${isOther(it) ? it.name : `${it.brand} ${it.size}`}" ürününü silmek istiyor musunuz?`)) return;
    try { await api.delete(`/tires/${it.id}`); toast.success("Silindi"); load(); }
    catch (e) { toast.error(extractError(e)); }
  };

  const openMovement = (tire, direction) => {
    setMvTire(tire);
    setMvForm({ delta: 1, reason: direction === "in" ? "alis" : "satis", note: "", direction });
    setMvOpen(true);
  };
  const saveMovement = async (e) => {
    e?.preventDefault();
    const d = Math.abs(Number(mvForm.delta));
    if (!d) { toast.error("Miktar girin"); return; }
    const signed = mvForm.direction === "in" ? d : -d;
    try {
      await api.post(`/tires/${mvTire.id}/movement`, { delta: signed, reason: mvForm.reason, note: mvForm.note });
      toast.success(`Stok ${mvForm.direction === "in" ? "arttırıldı" : "düşürüldü"}`);
      setMvOpen(false); load();
    } catch (e) { toast.error(extractError(e)); }
  };

  // AI import
  const onFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/sampiyon/parse-tire-document", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setImportItems(data.items.map((x) => ({ ...x })));
      setImportName(data.filename || file.name);
      setImportOpen(true);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };
  const toggleImport = (i) => setImportItems((r) => r.map((x, idx) => idx === i ? { ...x, selected: !x.selected } : x));
  const updateImportField = (i, k, v) => setImportItems((r) => r.map((x, idx) => idx === i ? { ...x, [k]: v } : x));
  const confirmImport = async () => {
    const chosen = importItems.filter((p) => p.selected).map((p) => ({
      brand: p.brand, model: p.model, size: p.size, season: p.season, dot: p.dot,
      quantity: Number(p.quantity), buy_price: Number(p.buy_price), sell_price: Number(p.sell_price),
      kdv_rate: Number(p.kdv_rate), note: "",
    }));
    if (!chosen.length) { toast.error("Lütfen en az bir lastik seçin"); return; }
    setConfirming(true);
    try {
      const { data } = await api.post("/sampiyon/import-confirm", { items: chosen });
      toast.success(`${data.count} lastik stoğa eklendi`);
      setImportOpen(false); setImportItems([]); load();
    } catch (e) { toast.error(extractError(e)); }
    finally { setConfirming(false); }
  };

  const totals = useMemo(() => {
    const qty = filtered.reduce((s, t) => s + Number(t.quantity || 0), 0);
    const buyVal = filtered.reduce((s, t) => s + Number(t.quantity || 0) * Number(t.buy_price || 0), 0);
    const sellVal = filtered.reduce((s, t) => s + Number(t.quantity || 0) * Number(t.sell_price || 0), 0);
    return { qty, buyVal, sellVal, margin: sellVal - buyVal };
  }, [filtered]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center">
            <Package className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Stok</h2>
            <p className="text-sm text-slate-600 mt-1">Lastik ve diğer ürün envanterinizi tek yerden yönetin.</p>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.pdf" className="hidden" onChange={onFileSelect} data-testid="tire-file-input" />
          <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={importing} className="border-slate-300" data-testid="tire-import-btn">
            <Sparkles className="w-4 h-4 mr-2 text-indigo-600" />
            {importing ? "Şampiyon okuyor..." : "AI ile Belge Yükle"}
          </Button>
          <Button variant="outline" onClick={() => setDupsOpen(true)} data-testid="find-duplicates-btn">
            <GitMerge className="w-4 h-4 mr-2" /> Mükerrerleri Bul
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="tire-add-btn">
                <Plus className="w-4 h-4 mr-2" /> Stok Ekle <ChevronDown className="w-4 h-4 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem onClick={() => openNew("lastik")} data-testid="stock-add-tire">
                <CircleDot className="w-4 h-4 mr-2" /> Lastik Stok <span className="ml-auto text-[10px] text-slate-400">standart</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => openNew("diger")} data-testid="stock-add-other">
                <Boxes className="w-4 h-4 mr-2" /> Diğer
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><div className="text-xs font-semibold uppercase tracking-wider text-slate-500">SKU</div><div className="mt-1 text-xl font-extrabold text-slate-900">{filtered.length}</div></CardContent></Card>
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Toplam Adet</div><div className="mt-1 text-xl font-extrabold text-slate-900" data-testid="tire-total-qty">{totals.qty}</div></CardContent></Card>
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Alış Değeri</div><div className="mt-1 text-xl font-extrabold text-rose-700">{formatTRY(totals.buyVal)}</div></CardContent></Card>
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Satış Değeri</div><div className="mt-1 text-xl font-extrabold text-emerald-700">{formatTRY(totals.sellVal)}</div></CardContent></Card>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-4 border-b border-slate-100 flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[220px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input placeholder="Ürün adı, marka, ebat, DOT ara..." className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="tire-search" />
          </div>
          <div className="inline-flex rounded-lg bg-slate-100 p-1" data-testid="stock-type-filter">
            {[["all", "Tümü"], ["lastik", "Lastik"], ["diger", "Diğer"]].map(([v, l]) => (
              <button key={v} onClick={() => { setTypeFilter(v); setCatFilter("all"); if (v === "diger") setSeasonFilter("all"); }} className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${typeFilter === v ? "bg-white shadow-sm text-slate-900" : "text-slate-500 hover:text-slate-900"}`} data-testid={`stock-type-${v}`}>{l}</button>
            ))}
          </div>
          {typeFilter !== "diger" && <Select value={seasonFilter} onValueChange={setSeasonFilter}>
            <SelectTrigger className="w-44" data-testid="tire-season-filter"><SelectValue placeholder="Mevsim" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tüm Mevsimler</SelectItem>
              <SelectItem value="yaz">Yaz</SelectItem>
              <SelectItem value="kis">Kış</SelectItem>
              <SelectItem value="4mevsim">4 Mevsim</SelectItem>
            </SelectContent>
          </Select>}
        </CardContent>
        {typeFilter === "diger" && (
          <CardContent className="p-4 border-b border-slate-100 space-y-3" data-testid="category-panel">
            {categoryStats.length === 0 ? (
              <div className="text-sm text-slate-500" data-testid="category-empty">Henüz "Diğer" ürün yok.</div>
            ) : (
              <>
                <div className="flex flex-wrap gap-2" data-testid="category-chips">
                  {[{ name: "all", label: "Tümü" }, ...categoryStats.map((c) => ({ name: c.name, label: `${c.name} (${c.count})` }))].map((c) => (
                    <button key={c.name} onClick={() => setCatFilter(c.name)}
                      className={`px-3 py-1 rounded-full text-xs font-semibold border transition-colors ${catFilter === c.name ? "bg-violet-600 text-white border-violet-600" : "bg-white text-slate-600 border-slate-200 hover:border-violet-300 hover:text-violet-700"}`}
                      data-testid={`category-chip-${c.name}`}>{c.label}</button>
                  ))}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {categoryStats.map((c) => (
                    <button key={c.name} onClick={() => setCatFilter(c.name)}
                      className={`text-left rounded-xl border p-3 transition-colors ${catFilter === c.name ? "border-violet-400 bg-violet-50" : "border-slate-200 hover:border-violet-300"}`}
                      data-testid={`category-card-${c.name}`}>
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-slate-900">{c.name}</span>
                        <span className="text-[11px] text-slate-500">{c.count} çeşit</span>
                      </div>
                      <div className="mt-1 text-lg font-extrabold text-slate-900" data-testid={`category-qty-${c.name}`}>{c.qty} <span className="text-xs font-medium text-slate-500">toplam adet</span></div>
                      <div className="mt-1 flex justify-between text-[11px]">
                        <span className="text-rose-700">Alış {formatTRY(c.buyVal)}</span>
                        <span className="text-emerald-700">Satış {formatTRY(c.sellVal)}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        )}
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Ürün</TableHead>
                <TableHead>Ebat</TableHead>
                <TableHead>Tür / Mevsim</TableHead>
                <TableHead>DOT</TableHead>
                <TableHead className="text-right">Adet</TableHead>
                <TableHead className="text-right">Alış</TableHead>
                <TableHead className="text-right">Satış</TableHead>
                <TableHead className="text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 && (
                <TableRow><TableCell colSpan={8} className="text-center text-slate-500 py-12">
                  {items.length === 0 ? 'Henüz ürün yok. "Stok Ekle" ile ekleyin veya AI ile belge yükleyin.' : "Arama/filtre ile eşleşen ürün yok."}
                </TableCell></TableRow>
              )}
              {filtered.map((t) => {
                const low = Number(t.quantity) <= threshold;
                return (
                  <TableRow key={t.id} data-testid={`tire-row-${t.id}`} className={t.id === highlightId ? "bg-amber-50 ring-2 ring-inset ring-amber-300" : ""}>
                    <TableCell>
                      <div className="font-semibold text-slate-900">{isOther(t) ? t.name : t.brand}</div>
                      {(isOther(t) ? [t.brand, t.model].filter(Boolean).join(" ") : t.model) && <div className="text-xs text-slate-500">{isOther(t) ? [t.brand, t.model].filter(Boolean).join(" ") : t.model}</div>}
                    </TableCell>
                    <TableCell className="font-mono text-sm text-slate-700">{isOther(t) ? "—" : t.size}</TableCell>
                    <TableCell>
                      {isOther(t) ? (
                        <Badge variant="outline" className="bg-violet-50 text-violet-700 border-violet-200">{t.category || "Diğer"}</Badge>
                      ) : (
                        <Badge variant="outline" className={SEASON_META[t.season]?.color}>{SEASON_META[t.season]?.label || t.season}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-slate-500 text-xs">{t.dot || "-"}</TableCell>
                    <TableCell className="text-right">
                      <span className={`font-extrabold ${low ? "text-rose-700" : "text-slate-900"}`}>{t.quantity}</span>
                      {isOther(t) && t.unit && t.unit !== "adet" && <span className="text-xs text-slate-500 ml-1">{t.unit}</span>}
                      {low && <div className="text-xs text-rose-500">Düşük</div>}
                    </TableCell>
                    <TableCell className="text-right text-slate-700">{formatTRY(t.buy_price)}</TableCell>
                    <TableCell className="text-right font-semibold text-emerald-700">{formatTRY(t.sell_price)}</TableCell>
                    <TableCell className="text-right">
                      <div className="inline-flex gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openMovement(t, "in")} title="Stok Girişi" className="text-emerald-700 hover:bg-emerald-50" data-testid={`tire-in-${t.id}`}>
                          <ArrowDown className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => openMovement(t, "out")} title="Stok Çıkışı" className="text-rose-700 hover:bg-rose-50" data-testid={`tire-out-${t.id}`}>
                          <ArrowUp className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(t)} data-testid={`tire-edit-${t.id}`}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => remove(t)} className="text-rose-600 hover:bg-rose-50" data-testid={`tire-delete-${t.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
            {filtered.length > 0 && (
              <TableFooter>
                <TableRow className="bg-slate-50">
                  <TableCell colSpan={4} className="font-bold uppercase text-xs tracking-wider">Toplam ({filtered.length} SKU)</TableCell>
                  <TableCell className="text-right font-extrabold text-slate-900">{totals.qty}</TableCell>
                  <TableCell className="text-right font-bold text-rose-700">{formatTRY(totals.buyVal)}</TableCell>
                  <TableCell className="text-right font-bold text-emerald-700">{formatTRY(totals.sellVal)}</TableCell>
                  <TableCell />
                </TableRow>
              </TableFooter>
            )}
          </Table>
        </CardContent>
      </Card>

      {/* New/Edit Dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {form.product_type === "diger" ? (editing ? "Ürünü Düzenle" : "Yeni Ürün — Diğer") : (editing ? "Lastiği Düzenle" : "Yeni Lastik")}
            </DialogTitle>
            <DialogDescription>
              {form.product_type === "diger" ? "Ürün adı zorunludur." : "Marka ve ebat zorunludur."} İlk kayıtta girilen adet açılış stokudur.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="space-y-3">
            {form.product_type === "diger" ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5 col-span-2"><Label>Ürün Adı *</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="örn: Akü 72Ah" data-testid="other-form-name" /></div>
                <div className="space-y-1.5"><Label>Kategori</Label><Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="örn: Akü, Jant, Yağ" data-testid="other-form-category" /></div>
                <div className="space-y-1.5">
                  <Label>Birim</Label>
                  <Select value={form.unit} onValueChange={(v) => setForm({ ...form, unit: v })}>
                    <SelectTrigger data-testid="other-form-unit"><SelectValue /></SelectTrigger>
                    <SelectContent>{UNITS.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5"><Label>Marka</Label><Input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} data-testid="other-form-brand" /></div>
                <div className="space-y-1.5"><Label>Model</Label><Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} data-testid="other-form-model" /></div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5"><Label>Marka *</Label><Input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} data-testid="tire-form-brand" /></div>
                <div className="space-y-1.5"><Label>Model</Label><Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} data-testid="tire-form-model" /></div>
                <div className="space-y-1.5"><Label>Ebat * (ör: 205/55 R16)</Label><Input value={form.size} onChange={(e) => setForm({ ...form, size: e.target.value })} data-testid="tire-form-size" /></div>
                <div className="space-y-1.5">
                  <Label>Mevsim</Label>
                  <Select value={form.season} onValueChange={(v) => setForm({ ...form, season: v })}>
                    <SelectTrigger data-testid="tire-form-season"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="yaz">Yaz</SelectItem><SelectItem value="kis">Kış</SelectItem><SelectItem value="4mevsim">4 Mevsim</SelectItem></SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5 col-span-2"><Label>DOT / Üretim</Label><Input value={form.dot} onChange={(e) => setForm({ ...form, dot: e.target.value })} data-testid="tire-form-dot" placeholder="örn: 3523" /></div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Adet</Label><Input type="number" step="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="tire-form-qty" /></div>
              <div className="space-y-1.5"><Label>Alış Fiyatı (₺)</Label><Input type="number" step="0.01" value={form.buy_price} onChange={(e) => setForm({ ...form, buy_price: e.target.value })} data-testid="tire-form-buy" /></div>
              <div className="space-y-1.5"><Label>Satış Fiyatı (₺)</Label><Input type="number" step="0.01" value={form.sell_price} onChange={(e) => setForm({ ...form, sell_price: e.target.value })} data-testid="tire-form-sell" /></div>
              <div className="space-y-1.5"><Label>KDV %</Label><Input type="number" step="1" value={form.kdv_rate} onChange={(e) => setForm({ ...form, kdv_rate: e.target.value })} data-testid="tire-form-kdv" /></div>
            </div>
            <div className="space-y-1.5"><Label>Not</Label><Textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={loading} className="bg-slate-900 hover:bg-slate-800" data-testid="tire-form-save">{loading ? "Kaydediliyor..." : "Kaydet"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <DuplicatesDialog
        open={dupsOpen}
        onOpenChange={setDupsOpen}
        onChanged={load}
        onEditProduct={(id) => { const it = items.find((x) => x.id === id); if (it) openEdit(it); }}
      />

      {/* Similar product dialog */}
      <Dialog open={!!dup} onOpenChange={(o) => !o && setDup(null)}>
        <DialogContent className="sm:max-w-lg" data-testid="similar-dialog">
          <DialogHeader>
            <DialogTitle>Benzer ürün var</DialogTitle>
            <DialogDescription>
              "{dup?.payload.name}" stokta zaten var gibi görünüyor. Mevcut ürüne stok girişi yapabilir veya yine de yeni ürün oluşturabilirsiniz.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {dup?.matches.map((m) => (
              <div key={m.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2" data-testid={`similar-item-${m.id}`}>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-slate-900 truncate">{m.label}</div>
                  <div className="text-xs text-slate-500">
                    {m.exact ? <span className="text-emerald-700 font-semibold">Aynı ürün · </span> : "Benzer · "}Mevcut: {m.quantity} {m.unit || "adet"}
                  </div>
                </div>
                <Button size="sm" onClick={() => dupStockIn(m)} className="bg-emerald-600 hover:bg-emerald-700 text-white shrink-0" data-testid={`similar-stockin-${m.id}`}>
                  <ArrowDown className="w-4 h-4 mr-1" /> Stok girişi (+{Number(dup.payload.quantity) || 0})
                </Button>
              </div>
            ))}
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setDup(null)} data-testid="similar-cancel">Vazgeç</Button>
            <Button variant="outline" onClick={dupCreateNew} data-testid="similar-create-new">Yine de yeni ürün oluştur</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Movement Dialog */}
      <Dialog open={mvOpen} onOpenChange={setMvOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{mvForm.direction === "in" ? "Stok Girişi" : "Stok Çıkışı"}</DialogTitle>
            <DialogDescription>{mvTire && `${mvTire.product_name} — Mevcut: ${mvTire.quantity} ${isOther(mvTire) ? mvTire.unit || "adet" : "adet"}`}</DialogDescription>
          </DialogHeader>
          <form onSubmit={saveMovement} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Miktar</Label><Input type="number" min="1" step="1" value={mvForm.delta} onChange={(e) => setMvForm({ ...mvForm, delta: e.target.value })} data-testid="tire-mv-qty" /></div>
              <div className="space-y-1.5">
                <Label>Neden</Label>
                <Select value={mvForm.reason} onValueChange={(v) => setMvForm({ ...mvForm, reason: v })}>
                  <SelectTrigger data-testid="tire-mv-reason"><SelectValue /></SelectTrigger>
                  <SelectContent>{MOVEMENT_REASONS.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5"><Label>Not</Label><Input value={mvForm.note} onChange={(e) => setMvForm({ ...mvForm, note: e.target.value })} /></div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setMvOpen(false)}>İptal</Button>
              <Button type="submit" className={mvForm.direction === "in" ? "bg-emerald-600 hover:bg-emerald-700" : "bg-rose-600 hover:bg-rose-700"} data-testid="tire-mv-save">Kaydet</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* AI Import Dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-5xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Sparkles className="w-5 h-5 text-indigo-600" /> Şampiyon AI Çıkarımı — {importName}</DialogTitle>
            <DialogDescription>
              Şampiyon belgeden <strong data-testid="import-row-count">{importItems.filter((p) => p.selected).length}</strong>/{importItems.length} ürün buldu. Kayda geçmeden gözden geçirin.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="w-10"></TableHead>
                  <TableHead>Marka</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Ebat</TableHead>
                  <TableHead>Mevsim</TableHead>
                  <TableHead>DOT</TableHead>
                  <TableHead className="text-right">Adet</TableHead>
                  <TableHead className="text-right">Alış</TableHead>
                  <TableHead>Güven</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {importItems.map((p, idx) => (
                  <TableRow key={idx} className={!p.selected ? "opacity-40" : ""} data-testid={`import-row-${idx}`}>
                    <TableCell><Button variant="ghost" size="sm" onClick={() => toggleImport(idx)}>{p.selected ? <Check className="w-4 h-4 text-emerald-700" /> : <X className="w-4 h-4 text-slate-400" />}</Button></TableCell>
                    <TableCell><Input value={p.brand} onChange={(e) => updateImportField(idx, "brand", e.target.value)} className="h-8" /></TableCell>
                    <TableCell><Input value={p.model} onChange={(e) => updateImportField(idx, "model", e.target.value)} className="h-8" /></TableCell>
                    <TableCell><Input value={p.size} onChange={(e) => updateImportField(idx, "size", e.target.value)} className="h-8 w-28" /></TableCell>
                    <TableCell>
                      <Select value={p.season} onValueChange={(v) => updateImportField(idx, "season", v)}>
                        <SelectTrigger className="h-8 w-28"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="yaz">Yaz</SelectItem><SelectItem value="kis">Kış</SelectItem><SelectItem value="4mevsim">4 Mevsim</SelectItem></SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell><Input value={p.dot} onChange={(e) => updateImportField(idx, "dot", e.target.value)} className="h-8 w-20" /></TableCell>
                    <TableCell><Input type="number" value={p.quantity} onChange={(e) => updateImportField(idx, "quantity", e.target.value)} className="h-8 w-16 text-right" /></TableCell>
                    <TableCell><Input type="number" value={p.buy_price} onChange={(e) => updateImportField(idx, "buy_price", e.target.value)} className="h-8 w-24 text-right" /></TableCell>
                    <TableCell>
                      <Badge variant="outline" className={p.confidence >= 0.8 ? "bg-emerald-100 text-emerald-700 border-emerald-200" : p.confidence >= 0.5 ? "bg-amber-100 text-amber-700 border-amber-200" : "bg-rose-100 text-rose-700 border-rose-200"}>
                        {Math.round((p.confidence || 0) * 100)}%
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setImportOpen(false)}>İptal</Button>
            <Button onClick={confirmImport} disabled={confirming || !importItems.some((p) => p.selected)} className="bg-slate-900 hover:bg-slate-800" data-testid="import-confirm-btn">
              <Check className="w-4 h-4 mr-2" />{confirming ? "Ekleniyor..." : "Seçilenleri Stoğa Ekle"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
