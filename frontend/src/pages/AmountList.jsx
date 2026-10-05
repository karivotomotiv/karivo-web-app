import { useEffect, useState } from "react";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { downloadCSV } from "@/lib/csv";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, TrendingUp, TrendingDown, Download } from "lucide-react";
import { toast } from "sonner";

/**
 * Shared component for Gelirler / Giderler - a list of items with description, amount, date.
 */
export default function AmountList({ title, subtitle, endpoint, color = "emerald", testIdPrefix }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ description: "", amount: "", date: "" });
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get(`/${endpoint}`);
      setItems(data);
    } catch (e) {
      toast.error(extractError(e));
    }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const openNew = () => {
    setEditing(null);
    setForm({ description: "", amount: "", date: new Date().toISOString().slice(0, 10) });
    setOpen(true);
  };
  const openEdit = (item) => {
    setEditing(item);
    setForm({ description: item.description, amount: String(item.amount), date: item.date });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.description.trim() || !form.amount) {
      toast.error("Açıklama ve tutar gereklidir");
      return;
    }
    setLoading(true);
    try {
      const payload = { description: form.description.trim(), amount: Number(form.amount), date: form.date || null };
      if (editing) {
        await api.put(`/${endpoint}/${editing.id}`, payload);
        toast.success("Kayıt güncellendi");
      } else {
        await api.post(`/${endpoint}`, payload);
        toast.success("Kayıt eklendi");
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
    if (!window.confirm("Bu kaydı silmek istediğinize emin misiniz?")) return;
    try {
      await api.delete(`/${endpoint}/${id}`);
      toast.success("Kayıt silindi");
      load();
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const exportCsv = () => {
    if (items.length === 0) {
      toast.info("Dışa aktarılacak kayıt yok");
      return;
    }
    const rows = items.map((i) => [i.date, i.description, i.amount, i.created_by_name, i.created_at]);
    const total = items.reduce((s, i) => s + Number(i.amount || 0), 0);
    rows.push(["", "TOPLAM", total, "", ""]);
    downloadCSV({
      filename: `${title.toLowerCase()}-${new Date().toISOString().slice(0, 10)}.csv`,
      headers: ["Tarih", "Açıklama", "Tutar (TL)", "Ekleyen", "Oluşturma Zamanı"],
      rows,
    });
    toast.success("CSV indirildi");
  };

  const total = items.reduce((s, i) => s + Number(i.amount || 0), 0);
  const Icon = color === "emerald" ? TrendingUp : TrendingDown;
  const tintBg = color === "emerald" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700";
  const totalColor = color === "emerald" ? "text-emerald-700" : "text-rose-700";

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${tintBg}`}>
            <Icon className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">{title}</h2>
            <p className="text-sm text-slate-600 mt-1">{subtitle}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportCsv} className="border-slate-300" data-testid={`${testIdPrefix}-export-csv`}>
            <Download className="w-4 h-4 mr-2" /> CSV
          </Button>
          <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid={`${testIdPrefix}-add-btn`}>
            <Plus className="w-4 h-4 mr-2" /> Yeni Kayıt
          </Button>
        </div>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs font-bold uppercase tracking-wider text-slate-500">Tarih</TableHead>
                <TableHead className="text-xs font-bold uppercase tracking-wider text-slate-500">Açıklama</TableHead>
                <TableHead className="text-xs font-bold uppercase tracking-wider text-slate-500">Ekleyen</TableHead>
                <TableHead className="text-xs font-bold uppercase tracking-wider text-slate-500 text-right">Tutar</TableHead>
                <TableHead className="text-xs font-bold uppercase tracking-wider text-slate-500 text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-slate-500 py-10">
                    Henüz kayıt yok. "Yeni Kayıt" ile ekleyin.
                  </TableCell>
                </TableRow>
              )}
              {items.map((it) => (
                <TableRow key={it.id} data-testid={`${testIdPrefix}-row-${it.id}`}>
                  <TableCell className="text-slate-700">{formatDate(it.date)}</TableCell>
                  <TableCell className="font-medium text-slate-900">{it.description}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{it.created_by_name}</TableCell>
                  <TableCell className="text-right font-semibold text-slate-900">{formatTRY(it.amount)}</TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(it)} data-testid={`${testIdPrefix}-edit-${it.id}`}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(it.id)} className="text-rose-600 hover:text-rose-700 hover:bg-rose-50" data-testid={`${testIdPrefix}-delete-${it.id}`}>
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
                  <TableCell className={`text-right font-extrabold text-lg ${totalColor}`} data-testid={`${testIdPrefix}-total`}>
                    {formatTRY(total)}
                  </TableCell>
                  <TableCell />
                </TableRow>
              </TableFooter>
            )}
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Kayıt Düzenle" : "Yeni Kayıt"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="desc">Açıklama</Label>
              <Input id="desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid={`${testIdPrefix}-form-desc`} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="amt">Tutar (₺)</Label>
                <Input id="amt" type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} data-testid={`${testIdPrefix}-form-amount`} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="date">Tarih</Label>
                <Input id="date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid={`${testIdPrefix}-form-date`} />
              </div>
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={loading} className="bg-slate-900 hover:bg-slate-800" data-testid={`${testIdPrefix}-form-save`}>
                {loading ? "Kaydediliyor..." : "Kaydet"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
