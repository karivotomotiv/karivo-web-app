import { useEffect, useState } from "react";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, Package } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

const empty = { product_name: "", required_qty: "", received_qty: "", purchase_date: "", purchase_price: "" };

export default function Stok() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/inventory");
      setItems(data);
    } catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ ...empty, purchase_date: new Date().toISOString().slice(0, 10) });
    setOpen(true);
  };
  const openEdit = (it) => {
    setEditing(it);
    setForm({
      product_name: it.product_name,
      required_qty: String(it.required_qty),
      received_qty: String(it.received_qty),
      purchase_date: it.purchase_date,
      purchase_price: String(it.purchase_price),
    });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.product_name.trim()) { toast.error("Ürün adı gereklidir"); return; }
    setLoading(true);
    try {
      const payload = {
        product_name: form.product_name.trim(),
        required_qty: Number(form.required_qty || 0),
        received_qty: Number(form.received_qty || 0),
        purchase_date: form.purchase_date || null,
        purchase_price: Number(form.purchase_price || 0),
      };
      if (editing) {
        await api.put(`/inventory/${editing.id}`, payload);
        toast.success("Stok güncellendi");
      } else {
        await api.post("/inventory", payload);
        toast.success("Stok eklendi");
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
    if (!window.confirm("Bu kaydı silmek istiyor musunuz?")) return;
    try { await api.delete(`/inventory/${id}`); toast.success("Silindi"); load(); }
    catch (e) { toast.error(extractError(e)); }
  };

  const previewRemaining = Number(form.required_qty || 0) - Number(form.received_qty || 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center">
            <Package className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Stok</h2>
            <p className="text-sm text-slate-600 mt-1">Ürün ihtiyaç ve alım kayıtları — kalan miktar otomatik hesaplanır.</p>
          </div>
        </div>
        <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="stock-add-btn">
          <Plus className="w-4 h-4 mr-2" /> Yeni Ürün
        </Button>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Ürün</TableHead>
                <TableHead className="text-right">İhtiyaç</TableHead>
                <TableHead className="text-right">Alınan</TableHead>
                <TableHead className="text-right">Kalan</TableHead>
                <TableHead>Alış Tarihi</TableHead>
                <TableHead className="text-right">Alış Fiyatı</TableHead>
                <TableHead className="text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-slate-500 py-10">Henüz stok kaydı yok.</TableCell></TableRow>
              )}
              {items.map((it) => {
                const rem = Number(it.remaining_qty);
                const status = rem <= 0 ? "ok" : "pending";
                return (
                  <TableRow key={it.id} data-testid={`stock-row-${it.id}`}>
                    <TableCell className="font-medium text-slate-900">{it.product_name}</TableCell>
                    <TableCell className="text-right">{it.required_qty}</TableCell>
                    <TableCell className="text-right">{it.received_qty}</TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant={status === "ok" ? "secondary" : "outline"}
                        className={status === "ok" ? "bg-emerald-100 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200"}
                        data-testid={`stock-remaining-${it.id}`}
                      >
                        {rem} {status === "ok" ? "✓" : "eksik"}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatDate(it.purchase_date)}</TableCell>
                    <TableCell className="text-right">{formatTRY(it.purchase_price)}</TableCell>
                    <TableCell className="text-right">
                      <div className="inline-flex gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openEdit(it)} data-testid={`stock-edit-${it.id}`}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => remove(it.id)} className="text-rose-600 hover:bg-rose-50" data-testid={`stock-delete-${it.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Ürünü Düzenle" : "Yeni Ürün"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-2">
              <Label>Ürün Adı</Label>
              <Input value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} data-testid="stock-form-name" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>İhtiyaç Miktarı</Label>
                <Input type="number" step="0.01" value={form.required_qty} onChange={(e) => setForm({ ...form, required_qty: e.target.value })} data-testid="stock-form-required" />
              </div>
              <div className="space-y-2">
                <Label>Alınan Miktar</Label>
                <Input type="number" step="0.01" value={form.received_qty} onChange={(e) => setForm({ ...form, received_qty: e.target.value })} data-testid="stock-form-received" />
              </div>
              <div className="space-y-2">
                <Label>Alış Tarihi</Label>
                <Input type="date" value={form.purchase_date} onChange={(e) => setForm({ ...form, purchase_date: e.target.value })} data-testid="stock-form-date" />
              </div>
              <div className="space-y-2">
                <Label>Alış Fiyatı (₺)</Label>
                <Input type="number" step="0.01" value={form.purchase_price} onChange={(e) => setForm({ ...form, purchase_price: e.target.value })} data-testid="stock-form-price" />
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-sm flex justify-between">
              <span className="text-slate-600">Kalan miktar (otomatik):</span>
              <span className={`font-extrabold ${previewRemaining <= 0 ? "text-emerald-700" : "text-rose-700"}`} data-testid="stock-form-remaining">
                {previewRemaining}
              </span>
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={loading} className="bg-slate-900 hover:bg-slate-800" data-testid="stock-form-save">Kaydet</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
