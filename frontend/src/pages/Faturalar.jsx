import { useEffect, useRef, useState } from "react";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { downloadCSV } from "@/lib/csv";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, FileText, Upload, Receipt, Download, Check, X } from "lucide-react";
import { toast } from "sonner";

export default function Faturalar() {
  const [items, setItems] = useState([]);
  const [vatRows, setVatRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ description: "", amount: "", date: "" });
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewItems, setPreviewItems] = useState([]);
  const [previewFilename, setPreviewFilename] = useState("");
  const [confirming, setConfirming] = useState(false);
  const fileRef = useRef(null);

  const load = async () => {
    try {
      const [a, b] = await Promise.all([api.get("/invoices"), api.get("/invoices/vat-summary")]);
      setItems(a.data);
      setVatRows(b.data);
    } catch (e) {
      toast.error(extractError(e));
    }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ description: "", amount: "", date: new Date().toISOString().slice(0, 10) });
    setOpen(true);
  };
  const openEdit = (it) => {
    setEditing(it);
    setForm({ description: it.description, amount: String(it.amount), date: it.date });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.description.trim() || !form.amount) {
      toast.error("Açıklama ve KDV dahil tutar gereklidir");
      return;
    }
    setLoading(true);
    try {
      const payload = { description: form.description.trim(), amount: Number(form.amount), date: form.date || null };
      if (editing) {
        await api.put(`/invoices/${editing.id}`, payload);
        toast.success("Fatura güncellendi");
      } else {
        await api.post("/invoices", payload);
        toast.success("Fatura eklendi");
      }
      setOpen(false);
      load();
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Bu faturayı silmek istediğinize emin misiniz?")) return;
    try {
      await api.delete(`/invoices/${id}`);
      toast.success("Fatura silindi");
      load();
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const onFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/invoices/import-preview", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setPreviewItems(data.items.map((x) => ({ ...x, selected: true })));
      setPreviewFilename(data.filename || file.name);
      setPreviewOpen(true);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const toggleRow = (idx) => {
    setPreviewItems((rows) => rows.map((r, i) => (i === idx ? { ...r, selected: !r.selected } : r)));
  };

  const updatePreviewField = (idx, key, value) => {
    setPreviewItems((rows) => rows.map((r, i) => {
      if (i !== idx) return r;
      const next = { ...r, [key]: value };
      if (key === "amount") {
        const amt = Number(value || 0);
        next.base_amount = Math.round((amt / 1.2) * 100) / 100;
        next.vat_amount = Math.round((amt - amt / 1.2) * 100) / 100;
      }
      return next;
    }));
  };

  const confirmImport = async () => {
    const chosen = previewItems.filter((p) => p.selected);
    if (chosen.length === 0) {
      toast.error("Kaydedilecek satır seçilmedi");
      return;
    }
    setConfirming(true);
    try {
      const { data } = await api.post("/invoices/import-confirm", {
        items: chosen.map((p) => ({ description: p.description, amount: Number(p.amount), date: p.date })),
      });
      toast.success(`${data.count} fatura kaydedildi`);
      setPreviewOpen(false);
      setPreviewItems([]);
      load();
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setConfirming(false);
    }
  };

  const exportCsv = () => {
    if (items.length === 0) {
      toast.info("Dışa aktarılacak fatura yok");
      return;
    }
    const rows = items.map((i) => [i.date, i.description, i.base_amount, i.vat_amount, i.amount, i.created_by_name]);
    rows.push(["", "TOPLAM", totalBase, totalVat, totalGross, ""]);
    downloadCSV({
      filename: `faturalar-${new Date().toISOString().slice(0, 10)}.csv`,
      headers: ["Tarih", "Açıklama", "KDV Hariç (TL)", "KDV %20 (TL)", "KDV Dahil (TL)", "Ekleyen"],
      rows,
    });
    toast.success("CSV indirildi");
  };

  const previewVat = form.amount ? Number(form.amount) - Number(form.amount) / 1.2 : 0;
  const totalGross = items.reduce((s, i) => s + Number(i.amount || 0), 0);
  const totalVat = items.reduce((s, i) => s + Number(i.vat_amount || 0), 0);
  const totalBase = items.reduce((s, i) => s + Number(i.base_amount || 0), 0);

  const previewTotals = {
    gross: previewItems.filter((p) => p.selected).reduce((s, i) => s + Number(i.amount || 0), 0),
    vat: previewItems.filter((p) => p.selected).reduce((s, i) => s + Number(i.vat_amount || 0), 0),
  };

  const monthLabel = (m) => {
    if (!m) return "-";
    const [y, mm] = m.split("-");
    return new Date(Number(y), Number(mm) - 1, 1).toLocaleDateString("tr-TR", { year: "numeric", month: "long" });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-100 text-indigo-700 flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Faturalar</h2>
            <p className="text-sm text-slate-600 mt-1">
              KDV dahil tutar girin, uygulama otomatik olarak %20 KDV'yi ayırır.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportCsv} className="border-slate-300" data-testid="invoice-export-csv">
            <Download className="w-4 h-4 mr-2" /> CSV
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm,.pdf"
            className="hidden"
            onChange={onFileSelect}
            data-testid="invoice-file-input"
          />
          <Button
            variant="outline"
            onClick={() => fileRef.current?.click()}
            disabled={importing}
            className="border-slate-300"
            data-testid="invoice-import-btn"
          >
            <Upload className="w-4 h-4 mr-2" />
            {importing ? "Okunuyor..." : "Excel/PDF Yükle"}
          </Button>
          <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="invoice-add-btn">
            <Plus className="w-4 h-4 mr-2" /> Yeni Fatura
          </Button>
        </div>
      </div>

      {/* VAT monthly summary */}
      {vatRows.length > 0 && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-bold uppercase tracking-wider text-slate-500 flex items-center gap-2">
              <Receipt className="w-4 h-4" /> Aylık KDV Özeti
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3" data-testid="vat-monthly-summary">
              {vatRows.map((r) => (
                <div key={r.month} className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">{monthLabel(r.month)}</div>
                  <div className="mt-1 flex items-baseline justify-between">
                    <span className="text-sm text-slate-600">KDV</span>
                    <span className="text-lg font-extrabold text-indigo-700">{formatTRY(r.vat_total)}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Brüt: {formatTRY(r.gross_total)} · {r.count} fatura
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Tarih</TableHead>
                <TableHead>Açıklama</TableHead>
                <TableHead>Ekleyen</TableHead>
                <TableHead className="text-right">KDV Hariç</TableHead>
                <TableHead className="text-right">KDV (%20)</TableHead>
                <TableHead className="text-right">KDV Dahil</TableHead>
                <TableHead className="text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-slate-500 py-10">
                    Henüz fatura yok. "Yeni Fatura" ekleyin veya Excel/PDF yükleyin.
                  </TableCell>
                </TableRow>
              )}
              {items.map((it) => (
                <TableRow key={it.id} data-testid={`invoice-row-${it.id}`}>
                  <TableCell className="text-slate-700">{formatDate(it.date)}</TableCell>
                  <TableCell className="font-medium text-slate-900">{it.description}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{it.created_by_name}</TableCell>
                  <TableCell className="text-right text-slate-700">{formatTRY(it.base_amount)}</TableCell>
                  <TableCell className="text-right text-indigo-700 font-semibold">{formatTRY(it.vat_amount)}</TableCell>
                  <TableCell className="text-right font-semibold text-slate-900">{formatTRY(it.amount)}</TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(it)} data-testid={`invoice-edit-${it.id}`}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(it.id)} className="text-rose-600 hover:text-rose-700 hover:bg-rose-50" data-testid={`invoice-delete-${it.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            {items.length > 0 && (
              <TableFooter>
                <TableRow className="bg-slate-50">
                  <TableCell colSpan={3} className="font-bold text-slate-900 uppercase text-xs tracking-wider">Toplam</TableCell>
                  <TableCell className="text-right font-bold text-slate-900">{formatTRY(totalBase)}</TableCell>
                  <TableCell className="text-right font-extrabold text-indigo-700" data-testid="invoice-total-vat">{formatTRY(totalVat)}</TableCell>
                  <TableCell className="text-right font-extrabold text-lg text-slate-900" data-testid="invoice-total-gross">{formatTRY(totalGross)}</TableCell>
                  <TableCell />
                </TableRow>
              </TableFooter>
            )}
          </Table>
        </CardContent>
      </Card>

      {/* Add/Edit dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Fatura Düzenle" : "Yeni Fatura"}</DialogTitle>
            <DialogDescription>Girdiğiniz tutar KDV dahil kabul edilir. %20 KDV otomatik ayrılır.</DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-2">
              <Label>Açıklama</Label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="invoice-form-desc" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>KDV Dahil Tutar (₺)</Label>
                <Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} data-testid="invoice-form-amount" />
              </div>
              <div className="space-y-2">
                <Label>Tarih</Label>
                <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="invoice-form-date" />
              </div>
            </div>
            {form.amount && (
              <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">KDV Hariç:</span>
                  <span className="font-semibold text-slate-900">{formatTRY(Number(form.amount) / 1.2)}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-slate-600">KDV (%20):</span>
                  <span className="font-semibold text-indigo-700" data-testid="invoice-form-vat-preview">{formatTRY(previewVat)}</span>
                </div>
              </div>
            )}
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={loading} className="bg-slate-900 hover:bg-slate-800" data-testid="invoice-form-save">
                {loading ? "Kaydediliyor..." : "Kaydet"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Import preview dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>İçe Aktarım Önizleme — {previewFilename}</DialogTitle>
            <DialogDescription>
              <span data-testid="preview-row-count">{previewItems.filter((p) => p.selected).length}</span>/{previewItems.length} satır seçili. Kayda geçmeden önce gözden geçirin, isterseniz düzenleyin.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="w-12"></TableHead>
                  <TableHead>Tarih</TableHead>
                  <TableHead>Açıklama</TableHead>
                  <TableHead className="text-right">KDV Dahil</TableHead>
                  <TableHead className="text-right">KDV</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewItems.map((p, idx) => (
                  <TableRow key={idx} className={!p.selected ? "opacity-40" : ""} data-testid={`preview-row-${idx}`}>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => toggleRow(idx)} data-testid={`preview-toggle-${idx}`}>
                        {p.selected ? <Check className="w-4 h-4 text-emerald-700" /> : <X className="w-4 h-4 text-slate-400" />}
                      </Button>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="date"
                        value={p.date}
                        onChange={(e) => updatePreviewField(idx, "date", e.target.value)}
                        className="h-8 w-36"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={p.description}
                        onChange={(e) => updatePreviewField(idx, "description", e.target.value)}
                        className="h-8"
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <Input
                        type="number"
                        step="0.01"
                        value={p.amount}
                        onChange={(e) => updatePreviewField(idx, "amount", e.target.value)}
                        className="h-8 w-28 text-right"
                      />
                    </TableCell>
                    <TableCell className="text-right text-indigo-700 font-semibold">{formatTRY(p.vat_amount)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow className="bg-slate-50">
                  <TableCell colSpan={3} className="font-bold text-xs uppercase tracking-wider">Seçili Toplam</TableCell>
                  <TableCell className="text-right font-extrabold text-slate-900">{formatTRY(previewTotals.gross)}</TableCell>
                  <TableCell className="text-right font-extrabold text-indigo-700">{formatTRY(previewTotals.vat)}</TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setPreviewOpen(false)}>İptal</Button>
            <Button
              onClick={confirmImport}
              disabled={confirming || previewItems.filter((p) => p.selected).length === 0}
              className="bg-slate-900 hover:bg-slate-800"
              data-testid="preview-confirm-btn"
            >
              <Check className="w-4 h-4 mr-2" />
              {confirming ? "Kaydediliyor..." : "Seçilenleri Kaydet"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
