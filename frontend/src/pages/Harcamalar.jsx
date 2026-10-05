import { useEffect, useState } from "react";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, Wallet, Building, User, Users } from "lucide-react";
import { toast } from "sonner";

const CATS = [
  { key: "company", label: "Şirket Harcamaları", Icon: Building, color: "bg-slate-100 text-slate-700" },
  { key: "user1", label: "Kullanıcı 1 Harcamaları", Icon: User, color: "bg-teal-100 text-teal-700" },
  { key: "user2", label: "Kullanıcı 2 Harcamaları", Icon: Users, color: "bg-violet-100 text-violet-700" },
];

export default function Harcamalar() {
  const [all, setAll] = useState([]);
  const [tab, setTab] = useState("company");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", amount: "", date: "" });
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try { const { data } = await api.get("/spendings"); setAll(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ name: "", amount: "", date: new Date().toISOString().slice(0, 10) });
    setOpen(true);
  };
  const openEdit = (it) => {
    setEditing(it);
    setForm({ name: it.name, amount: String(it.amount), date: it.date });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.name.trim() || !form.amount) { toast.error("Ad ve tutar gereklidir"); return; }
    setLoading(true);
    try {
      const payload = { category: tab, name: form.name.trim(), amount: Number(form.amount), date: form.date || null };
      if (editing) {
        await api.put(`/spendings/${editing.id}`, payload);
        toast.success("Harcama güncellendi");
      } else {
        await api.post("/spendings", payload);
        toast.success("Harcama eklendi");
      }
      setOpen(false);
      load();
    } catch (e) {
      toast.error(extractError(e));
    } finally { setLoading(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Bu harcamayı silmek istiyor musunuz?")) return;
    try { await api.delete(`/spendings/${id}`); toast.success("Silindi"); load(); }
    catch (e) { toast.error(extractError(e)); }
  };

  const renderTable = (cat) => {
    const rows = all.filter((x) => x.category === cat);
    const total = rows.reduce((s, i) => s + Number(i.amount || 0), 0);
    return (
      <Card className="border-slate-200 shadow-sm mt-4">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Tarih</TableHead>
                <TableHead>Harcama Adı</TableHead>
                <TableHead>Ekleyen</TableHead>
                <TableHead className="text-right">Tutar</TableHead>
                <TableHead className="text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={5} className="text-center text-slate-500 py-10">Henüz harcama yok.</TableCell></TableRow>
              )}
              {rows.map((it) => (
                <TableRow key={it.id} data-testid={`spending-row-${it.id}`}>
                  <TableCell className="text-slate-700">{formatDate(it.date)}</TableCell>
                  <TableCell className="font-medium text-slate-900">{it.name}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{it.created_by_name}</TableCell>
                  <TableCell className="text-right font-semibold">{formatTRY(it.amount)}</TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(it)} data-testid={`spending-edit-${it.id}`}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(it.id)} className="text-rose-600 hover:bg-rose-50" data-testid={`spending-delete-${it.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            {rows.length > 0 && (
              <TableFooter>
                <TableRow className="bg-slate-50">
                  <TableCell colSpan={3} className="font-bold uppercase text-xs tracking-wider">Toplam</TableCell>
                  <TableCell className="text-right font-extrabold text-lg text-slate-900" data-testid={`spending-total-${cat}`}>
                    {formatTRY(total)}
                  </TableCell>
                  <TableCell />
                </TableRow>
              </TableFooter>
            )}
          </Table>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-violet-100 text-violet-700 flex items-center justify-center">
            <Wallet className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Harcamalar</h2>
            <p className="text-sm text-slate-600 mt-1">Şirket ve kullanıcı bazlı harcamaları ayrı sekmelerde takip edin.</p>
          </div>
        </div>
        <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="spending-add-btn">
          <Plus className="w-4 h-4 mr-2" /> Yeni Harcama
        </Button>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid grid-cols-3 w-full max-w-2xl">
          {CATS.map((c) => (
            <TabsTrigger key={c.key} value={c.key} data-testid={`spending-tab-${c.key}`}>
              <c.Icon className="w-4 h-4 mr-2" />
              {c.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {CATS.map((c) => (
          <TabsContent key={c.key} value={c.key}>
            {renderTable(c.key)}
          </TabsContent>
        ))}
      </Tabs>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Harcamayı Düzenle" : "Yeni Harcama"} — {CATS.find((c) => c.key === tab)?.label}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-2">
              <Label>Harcama Adı</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="spending-form-name" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Tutar (₺)</Label>
                <Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} data-testid="spending-form-amount" />
              </div>
              <div className="space-y-2">
                <Label>Tarih</Label>
                <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="spending-form-date" />
              </div>
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={loading} className="bg-slate-900 hover:bg-slate-800" data-testid="spending-form-save">Kaydet</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
