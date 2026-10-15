import { useEffect, useState, useMemo } from "react";
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
import { Plus, Trash2, ShoppingCart, Receipt, X, Check, AlertCircle, Pencil } from "lucide-react";
import { toast } from "sonner";
import { askConfirm } from "@/components/ConfirmHost";

const PAYMENT_META = {
  nakit:    { label: "Nakit",   color: "bg-emerald-100 text-emerald-700 border-emerald-200" },
  kart:     { label: "Kart",    color: "bg-indigo-100 text-indigo-700 border-indigo-200" },
  havale:   { label: "Havale",  color: "bg-sky-100 text-sky-700 border-sky-200" },
  veresiye: { label: "Veresiye",color: "bg-amber-100 text-amber-700 border-amber-200" },
};

const emptyLine = () => ({ tire_id: "", quantity: 1, unit_price: 0, discount: 0 });
const emptySale = () => ({
  cari_id: "",
  payment_method: "nakit",
  overall_discount: 0,
  note: "",
  date: new Date().toISOString().slice(0, 10),
  items: [emptyLine()],
});

export default function Satislar() {
  const [sales, setSales] = useState([]);
  const [tires, setTires] = useState([]);
  const [cariler, setCariler] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptySale());
  const [saving, setSaving] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [editing, setEditing] = useState(null);

  const load = async () => {
    try {
      const [s, t, c] = await Promise.all([
        api.get("/sales"),
        api.get("/tires"),
        api.get("/cariler"),
      ]);
      setSales(s.data);
      setTires(t.data);
      setCariler(c.data);
    } catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(emptySale()); setOpen(true); };
  const openEdit = (sale) => {
    setEditing(sale);
    setForm({
      cari_id: sale.cari_id || "",
      payment_method: sale.payment_method,
      overall_discount: sale.overall_discount || 0,
      note: sale.note || "",
      date: sale.date,
      items: sale.items.map((i) => ({ tire_id: i.tire_id, quantity: i.quantity, unit_price: i.unit_price, discount: i.discount || 0 })),
    });
    setDetailOpen(false);
    setOpen(true);
  };
  const oldQty = (tireId) => (editing ? editing.items.filter((i) => i.tire_id === tireId).reduce((s, i) => s + Number(i.quantity), 0) : 0);

  const setLine = (idx, patch) => {
    setForm((f) => {
      const items = f.items.map((it, i) => (i === idx ? { ...it, ...patch } : it));
      return { ...f, items };
    });
  };
  const onTireChange = (idx, tire_id) => {
    const tire = tires.find((t) => t.id === tire_id);
    setLine(idx, { tire_id, unit_price: tire ? Number(tire.sell_price || 0) : 0 });
  };
  const addLine = () => setForm((f) => ({ ...f, items: [...f.items, emptyLine()] }));
  const removeLine = (idx) => setForm((f) => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));

  const totals = useMemo(() => {
    const lines = form.items.map((l) => {
      const gross = Number(l.quantity || 0) * Number(l.unit_price || 0);
      const line = Math.max(0, gross - Number(l.discount || 0));
      return { gross, line };
    });
    const subtotal = lines.reduce((s, l) => s + l.line, 0);
    const total = Math.max(0, subtotal - Number(form.overall_discount || 0));
    return { subtotal, total, lines };
  }, [form]);

  const canSave = useMemo(() => {
    if (!form.items.length) return false;
    if (form.payment_method === "veresiye" && !form.cari_id) return false;
    return form.items.every((l) => l.tire_id && Number(l.quantity) > 0 && Number(l.unit_price) >= 0);
  }, [form]);

  const save = async (e) => {
    e?.preventDefault();
    if (!canSave) {
      toast.error(form.payment_method === "veresiye" && !form.cari_id
        ? "Veresiye satış için cari seçin"
        : "Lütfen satırları eksiksiz doldurun");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        cari_id: form.cari_id || null,
        items: form.items.map((l) => ({
          tire_id: l.tire_id,
          quantity: Number(l.quantity),
          unit_price: Number(l.unit_price),
          discount: Number(l.discount || 0),
        })),
        overall_discount: Number(form.overall_discount || 0),
        payment_method: form.payment_method,
        note: form.note,
        date: form.date || null,
      };
      const { data } = editing ? await api.put(`/sales/${editing.id}`, payload) : await api.post("/sales", payload);
      toast.success(editing ? `Satış güncellendi: ${formatTRY(data.total)}` : `Satış kaydedildi: ${formatTRY(data.total)}`);
      setOpen(false);
      load();
    } catch (e) { toast.error(extractError(e)); }
    finally { setSaving(false); }
  };

  const openDetail = async (sale) => {
    setDetail(sale);
    setDetailOpen(true);
  };

  const deleteSale = async (sale) => {
    if (!(await askConfirm(`Bu satışı kalıcı olarak silmek istiyor musunuz?\n\nStoklar geri eklenecek (stok hareketlerinde "iade" kaydı kalır), varsa gelir ve cari alacak kaydı silinecek.`))) return;
    try {
      await api.delete(`/sales/${sale.id}`);
      toast.success("Satış silindi, stoklar geri eklendi");
      setDetailOpen(false);
      load();
    } catch (e) { toast.error(extractError(e)); }
  };

  const totalSales = sales.reduce((s, i) => s + Number(i.total || 0), 0);
  const veresiyeTotal = sales.filter((s) => s.payment_method === "veresiye").reduce((s, i) => s + Number(i.total || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
            <ShoppingCart className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Satışlar</h2>
            <p className="text-sm text-slate-600 mt-1">
              Ürün + müşteri + ödeme — stok, gelir ve cari bakiyesi otomatik güncellenir.
            </p>
          </div>
        </div>
        <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="sale-add-btn">
          <Plus className="w-4 h-4 mr-2" /> Yeni Satış
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Toplam Satış</div><div className="mt-1 text-xl font-extrabold text-slate-900" data-testid="sale-count">{sales.length}</div></CardContent></Card>
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Toplam Ciro</div><div className="mt-1 text-xl font-extrabold text-emerald-700" data-testid="sale-total-ciro">{formatTRY(totalSales)}</div></CardContent></Card>
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Veresiye</div><div className="mt-1 text-xl font-extrabold text-amber-700" data-testid="sale-veresiye-total">{formatTRY(veresiyeTotal)}</div></CardContent></Card>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Tarih</TableHead>
                <TableHead>Müşteri</TableHead>
                <TableHead>Ürünler</TableHead>
                <TableHead>Ödeme</TableHead>
                <TableHead className="text-right">Tutar</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sales.length === 0 && (
                <TableRow><TableCell colSpan={6} className="text-center text-slate-500 py-12">Henüz satış yok. "Yeni Satış" ile başlayın.</TableCell></TableRow>
              )}
              {sales.map((s) => (
                <TableRow key={s.id} className="cursor-pointer hover:bg-slate-50/80" onClick={() => openDetail(s)} data-testid={`sale-row-${s.id}`}>
                  <TableCell className="text-slate-700">{formatDate(s.date)}</TableCell>
                  <TableCell className="font-medium text-slate-900">{s.cari_name || <span className="text-slate-400">— müşteri yok —</span>}</TableCell>
                  <TableCell className="text-sm text-slate-600">
                    {s.items.slice(0, 2).map((it) => it.tire_label).join(" · ")}
                    {s.items.length > 2 && ` +${s.items.length - 2}`}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={PAYMENT_META[s.payment_method]?.color}>{PAYMENT_META[s.payment_method]?.label}</Badge>
                  </TableCell>
                  <TableCell className="text-right font-extrabold text-emerald-700">{formatTRY(s.total)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                    <Button variant="ghost" size="sm" onClick={() => openEdit(s)} data-testid={`sale-edit-${s.id}`}><Pencil className="w-4 h-4" /></Button>
                    <Button variant="ghost" size="sm" onClick={() => deleteSale(s)} className="text-rose-600 hover:bg-rose-50" data-testid={`sale-delete-${s.id}`}><Trash2 className="w-4 h-4" /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* New sale dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Satışı Düzenle" : "Yeni Satış"}</DialogTitle>
            <DialogDescription>{editing && "Kaydettiğinizde eski satışın stok, gelir ve cari etkileri geri alınıp yeni değerlerle yeniden işlenir. "}Ürün satırları ekleyin, müşteri ve ödeme yöntemi seçin. Onayladığınızda stoktan düşer, gelir ve cari bakiyesi otomatik işlenir.</DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Müşteri (Cari)</Label>
                <Select value={form.cari_id || "none"} onValueChange={(v) => setForm({ ...form, cari_id: v === "none" ? "" : v })}>
                  <SelectTrigger data-testid="sale-form-cari"><SelectValue placeholder="Müşteri seçin..." /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— Müşteri yok —</SelectItem>
                    {cariler.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Ödeme Yöntemi</Label>
                <Select value={form.payment_method} onValueChange={(v) => setForm({ ...form, payment_method: v })}>
                  <SelectTrigger data-testid="sale-form-payment"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="nakit">Nakit (peşin → gelir)</SelectItem>
                    <SelectItem value="kart">Kart (peşin → gelir)</SelectItem>
                    <SelectItem value="havale">Havale (peşin → gelir)</SelectItem>
                    <SelectItem value="veresiye">Veresiye (cariye alacak)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Tarih</Label>
                <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="sale-form-date" />
              </div>
            </div>

            {form.payment_method === "veresiye" && !form.cari_id && (
              <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                <AlertCircle className="w-4 h-4" /> Veresiye satış için müşteri seçmelisiniz.
              </div>
            )}

            {/* Line items */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Ürünler</Label>
                <Button type="button" size="sm" variant="outline" onClick={addLine} data-testid="sale-add-line"><Plus className="w-3 h-3 mr-1" /> Satır Ekle</Button>
              </div>
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead className="min-w-[260px]">Ürün</TableHead>
                      <TableHead className="w-24 text-right">Adet</TableHead>
                      <TableHead className="w-32 text-right">Birim Fiyat</TableHead>
                      <TableHead className="w-28 text-right">İndirim</TableHead>
                      <TableHead className="w-32 text-right">Satır Toplam</TableHead>
                      <TableHead className="w-10"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {form.items.map((l, idx) => {
                      const tire = tires.find((t) => t.id === l.tire_id);
                      const stock = tire ? Number(tire.quantity) + oldQty(l.tire_id) : 0;
                      const over = tire && Number(l.quantity) > stock;
                      return (
                        <TableRow key={idx} data-testid={`sale-line-${idx}`}>
                          <TableCell>
                            <Select value={l.tire_id || ""} onValueChange={(v) => onTireChange(idx, v)}>
                              <SelectTrigger className="h-9" data-testid={`sale-line-tire-${idx}`}><SelectValue placeholder="Ürün seçin..." /></SelectTrigger>
                              <SelectContent>
                                {tires.map((t) => {
                                  const avail = Number(t.quantity) + oldQty(t.id);
                                  return (
                                    <SelectItem key={t.id} value={t.id} disabled={avail <= 0}>
                                      {t.product_name} ({avail} {t.unit || "adet"}) — {formatTRY(t.sell_price)}
                                    </SelectItem>
                                  );
                                })}
                              </SelectContent>
                            </Select>
                            {over && <div className="text-xs text-rose-600 mt-1">⚠ Stok yetersiz — mevcut: {stock}</div>}
                          </TableCell>
                          <TableCell><Input type="number" min="1" step="1" value={l.quantity} onChange={(e) => setLine(idx, { quantity: e.target.value })} className="h-9 text-right" data-testid={`sale-line-qty-${idx}`} /></TableCell>
                          <TableCell><Input type="number" step="0.01" value={l.unit_price} onChange={(e) => setLine(idx, { unit_price: e.target.value })} className="h-9 text-right" /></TableCell>
                          <TableCell><Input type="number" step="0.01" value={l.discount} onChange={(e) => setLine(idx, { discount: e.target.value })} className="h-9 text-right" /></TableCell>
                          <TableCell className="text-right font-semibold text-slate-900">{formatTRY(totals.lines[idx]?.line || 0)}</TableCell>
                          <TableCell>
                            {form.items.length > 1 && (
                              <Button type="button" variant="ghost" size="sm" onClick={() => removeLine(idx)} className="text-rose-600 hover:bg-rose-50">
                                <X className="w-4 h-4" />
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Not</Label>
                <Textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Genel İndirim (₺)</Label>
                <Input type="number" step="0.01" value={form.overall_discount} onChange={(e) => setForm({ ...form, overall_discount: e.target.value })} data-testid="sale-form-overall-discount" />
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-1.5">
              <div className="flex justify-between text-sm text-slate-600"><span>Ara Toplam</span><span className="font-semibold">{formatTRY(totals.subtotal)}</span></div>
              <div className="flex justify-between text-sm text-slate-600"><span>Genel İndirim</span><span className="font-semibold text-rose-600">− {formatTRY(form.overall_discount || 0)}</span></div>
              <div className="border-t border-slate-200 pt-1.5 flex justify-between text-base">
                <span className="font-bold text-slate-900">Genel Toplam</span>
                <span className="font-extrabold text-xl text-emerald-700" data-testid="sale-form-total">{formatTRY(totals.total)}</span>
              </div>
            </div>

            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={saving || !canSave} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="sale-form-save">
                <Check className="w-4 h-4 mr-2" />
                {saving ? "Kaydediliyor..." : `${editing ? "Değişiklikleri Kaydet" : "Satışı Onayla"} — ${formatTRY(totals.total)}`}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Detail dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Receipt className="w-5 h-5 text-indigo-700" /> Satış Detayı</DialogTitle>
            <DialogDescription>
              {detail && `${formatDate(detail.date)} · ${detail.cari_name || "— müşteri yok —"} · ${PAYMENT_META[detail.payment_method]?.label}`}
            </DialogDescription>
          </DialogHeader>
          {detail && (
            <div className="space-y-3">
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead>Ürün</TableHead>
                      <TableHead className="text-right">Adet</TableHead>
                      <TableHead className="text-right">Birim</TableHead>
                      <TableHead className="text-right">Toplam</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detail.items.map((it, i) => (
                      <TableRow key={i}>
                        <TableCell>{it.tire_label}</TableCell>
                        <TableCell className="text-right">{it.quantity}</TableCell>
                        <TableCell className="text-right">{formatTRY(it.unit_price)}</TableCell>
                        <TableCell className="text-right font-semibold">{formatTRY(it.line_total)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                  <TableFooter>
                    <TableRow className="bg-slate-50">
                      <TableCell colSpan={3} className="font-semibold">Ara Toplam</TableCell>
                      <TableCell className="text-right">{formatTRY(detail.subtotal)}</TableCell>
                    </TableRow>
                    {detail.overall_discount > 0 && (
                      <TableRow>
                        <TableCell colSpan={3} className="text-rose-600">Genel İndirim</TableCell>
                        <TableCell className="text-right text-rose-600">− {formatTRY(detail.overall_discount)}</TableCell>
                      </TableRow>
                    )}
                    <TableRow className="bg-slate-50">
                      <TableCell colSpan={3} className="font-bold">Genel Toplam</TableCell>
                      <TableCell className="text-right font-extrabold text-emerald-700 text-lg">{formatTRY(detail.total)}</TableCell>
                    </TableRow>
                  </TableFooter>
                </Table>
              </div>
              {detail.note && <div className="text-sm text-slate-600"><strong>Not:</strong> {detail.note}</div>}
              <div className="text-xs text-slate-500">
                Oluşturan: {detail.created_by_name} · {formatDate(detail.created_at)}
                {detail.updated_at && ` · Son düzenleme: ${detail.updated_by_name || ""} ${formatDate(detail.updated_at)}`}
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            {detail && (
              <>
                <Button variant="outline" onClick={() => deleteSale(detail)} className="text-rose-600 hover:text-rose-700 hover:bg-rose-50" data-testid="sale-delete-btn">
                  <Trash2 className="w-4 h-4 mr-2" /> Sil
                </Button>
                <Button variant="outline" onClick={() => openEdit(detail)} data-testid="sale-edit-btn">
                  <Pencil className="w-4 h-4 mr-2" /> Düzenle
                </Button>
              </>
            )}
            <Button onClick={() => setDetailOpen(false)}>Kapat</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
