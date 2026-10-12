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
import { Plus, Pencil, Trash2, Package, Search, Upload, ArrowDown, ArrowUp, Sparkles, Check, X } from "lucide-react";
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

const emptyTire = { brand: "", model: "", size: "", season: "4mevsim", dot: "", quantity: 0, buy_price: 0, sell_price: 0, kdv_rate: 20, note: "" };

export default function Stok() {
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [seasonFilter, setSeasonFilter] = useState("all");
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
      if (seasonFilter !== "all" && t.season !== seasonFilter) return false;
      if (!s) return true;
      const hay = `${t.brand} ${t.model} ${t.size} ${t.dot} ${t.note}`.toLowerCase();
      return hay.includes(s);
    });
  }, [items, search, seasonFilter]);

  const openNew = () => { setEditing(null); setForm({ ...emptyTire }); setOpen(true); };
  const openEdit = (it) => {
    setEditing(it);
    setForm({
      brand: it.brand || "", model: it.model || "", size: it.size || "",
      season: it.season || "4mevsim", dot: it.dot || "", quantity: it.quantity || 0,
      buy_price: it.buy_price || 0, sell_price: it.sell_price || 0,
      kdv_rate: it.kdv_rate || 20, note: it.note || "",
    });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.brand.trim() || !form.size.trim()) { toast.error("Marka ve ebat zorunludur"); return; }
    setLoading(true);
    try {
      const payload = {
        ...form,
        brand: form.brand.trim(), model: form.model.trim(), size: form.size.trim(),
        dot: form.dot.trim(), note: form.note.trim(),
        quantity: Number(form.quantity), buy_price: Number(form.buy_price),
        sell_price: Number(form.sell_price), kdv_rate: Number(form.kdv_rate),
      };
      if (editing) {
        await api.put(`/tires/${editing.id}`, payload);
        toast.success("Lastik güncellendi");
      } else {
        await api.post("/tires", payload);
        toast.success("Lastik eklendi");
      }
      setOpen(false); load();
    } catch (e) { toast.error(extractError(e)); }
    finally { setLoading(false); }
  };

  const remove = async (it) => {
    if (!window.confirm(`"${it.brand} ${it.size}" lastiğini silmek istiyor musunuz?`)) return;
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
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Lastik Stok</h2>
            <p className="text-sm text-slate-600 mt-1">Marka, ebat, mevsim ve DOT bilgisiyle lastik envanterinizi yönetin.</p>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.pdf" className="hidden" onChange={onFileSelect} data-testid="tire-file-input" />
          <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={importing} className="border-slate-300" data-testid="tire-import-btn">
            <Sparkles className="w-4 h-4 mr-2 text-indigo-600" />
            {importing ? "Şampiyon okuyor..." : "AI ile Belge Yükle"}
          </Button>
          <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="tire-add-btn">
            <Plus className="w-4 h-4 mr-2" /> Yeni Lastik
          </Button>
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
            <Input placeholder="Marka, ebat, model, DOT ara..." className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="tire-search" />
          </div>
          <Select value={seasonFilter} onValueChange={setSeasonFilter}>
            <SelectTrigger className="w-44" data-testid="tire-season-filter"><SelectValue placeholder="Mevsim" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tüm Mevsimler</SelectItem>
              <SelectItem value="yaz">Yaz</SelectItem>
              <SelectItem value="kis">Kış</SelectItem>
              <SelectItem value="4mevsim">4 Mevsim</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Marka / Model</TableHead>
                <TableHead>Ebat</TableHead>
                <TableHead>Mevsim</TableHead>
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
                  {items.length === 0 ? 'Henüz lastik yok. "Yeni Lastik" ile ekleyin veya AI ile belge yükleyin.' : "Arama/filtre ile eşleşen lastik yok."}
                </TableCell></TableRow>
              )}
              {filtered.map((t) => {
                const low = Number(t.quantity) <= threshold;
                return (
                  <TableRow key={t.id} data-testid={`tire-row-${t.id}`} className={t.id === highlightId ? "bg-amber-50 ring-2 ring-inset ring-amber-300" : ""}>
                    <TableCell>
                      <div className="font-semibold text-slate-900">{t.brand}</div>
                      {t.model && <div className="text-xs text-slate-500">{t.model}</div>}
                    </TableCell>
                    <TableCell className="font-mono text-sm text-slate-700">{t.size}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={SEASON_META[t.season]?.color}>{SEASON_META[t.season]?.label || t.season}</Badge>
                    </TableCell>
                    <TableCell className="text-slate-500 text-xs">{t.dot || "-"}</TableCell>
                    <TableCell className="text-right">
                      <span className={`font-extrabold ${low ? "text-rose-700" : "text-slate-900"}`}>{t.quantity}</span>
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
            <DialogTitle>{editing ? "Lastiği Düzenle" : "Yeni Lastik"}</DialogTitle>
            <DialogDescription>Marka ve ebat zorunludur. İlk kayıtta girilen adet açılış stokudur.</DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="space-y-3">
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
              <div className="space-y-1.5"><Label>DOT / Üretim</Label><Input value={form.dot} onChange={(e) => setForm({ ...form, dot: e.target.value })} data-testid="tire-form-dot" placeholder="örn: 3523" /></div>
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

      {/* Movement Dialog */}
      <Dialog open={mvOpen} onOpenChange={setMvOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{mvForm.direction === "in" ? "Stok Girişi" : "Stok Çıkışı"}</DialogTitle>
            <DialogDescription>{mvTire && `${mvTire.brand} ${mvTire.size} — Mevcut: ${mvTire.quantity} adet`}</DialogDescription>
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
