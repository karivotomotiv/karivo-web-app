import { useEffect, useState, useMemo } from "react";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import FilterBar, { applyFilter, monthLabelFromKey } from "@/components/FilterBar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, Wallet, Building, User, Users } from "lucide-react";
import { toast } from "sonner";

// Kategori etiketleri — user1 = Murat, user2 = Özkan (env'den gelen isimler)
const CATS = [
  { key: "company", label: "Şirket Harcamaları", short: "Şirket", Icon: Building },
  { key: "user1", label: "Murat Harcamaları", short: "Murat", Icon: User },
  { key: "user2", label: "Özkan Harcamaları", short: "Özkan", Icon: Users },
];

export default function Harcamalar() {
  const [all, setAll] = useState([]);
  const [tab, setTab] = useState("company");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ category: "", name: "", amount: "", date: "" });
  const [loading, setLoading] = useState(false);
  // Filter state per tab
  const [filters, setFilters] = useState({
    company: { month: "all", search: "" },
    user1: { month: "all", search: "" },
    user2: { month: "all", search: "" },
  });

  const load = async () => {
    try { const { data } = await api.get("/spendings"); setAll(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ category: "", name: "", amount: "", date: new Date().toISOString().slice(0, 10) });
    setOpen(true);
  };
  const openEdit = (it) => {
    setEditing(it);
    setForm({ category: it.category, name: it.name, amount: String(it.amount), date: it.date });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.category) { toast.error("Lütfen harcamanın kime ait olduğunu seçin"); return; }
    if (!form.name.trim() || !form.amount) { toast.error("Ad ve tutar gereklidir"); return; }
    setLoading(true);
    try {
      const payload = { category: form.category, name: form.name.trim(), amount: Number(form.amount), date: form.date || null };
      if (editing) {
        await api.put(`/spendings/${editing.id}`, payload);
        const movedMsg = editing.category !== form.category
          ? ` ve ${CATS.find((c) => c.key === form.category)?.short} olarak taşındı`
          : "";
        toast.success(`Harcama güncellendi${movedMsg}`);
        // If moved, switch to the destination tab for visibility
        if (editing.category !== form.category) setTab(form.category);
      } else {
        await api.post("/spendings", payload);
        toast.success("Harcama eklendi");
        if (form.category !== tab) setTab(form.category);
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

  const setTabFilter = (cat, patch) => setFilters((prev) => ({ ...prev, [cat]: { ...prev[cat], ...patch } }));

  const renderTable = (cat) => {
    const rows = all.filter((x) => x.category === cat);
    const f = filters[cat];
    const filtered = applyFilter(rows, { month: f.month, search: f.search, searchKeys: ["name", "created_by_name"] });
    const total = filtered.reduce((s, i) => s + Number(i.amount || 0), 0);
    const grand = rows.reduce((s, i) => s + Number(i.amount || 0), 0);

    return (
      <>
        <Card className="border-slate-200 shadow-sm mt-4">
          <CardContent className="p-4 border-b border-slate-100">
            <FilterBar
              items={rows}
              month={f.month} setMonth={(m) => setTabFilter(cat, { month: m })}
              search={f.search} setSearch={(s) => setTabFilter(cat, { search: s })}
              searchKeys={["name", "created_by_name"]}
              testIdPrefix={`spending-${cat}`}
              placeholder="Harcama adında ara..."
            />
          </CardContent>
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
                {filtered.length === 0 && (
                  <TableRow><TableCell colSpan={5} className="text-center text-slate-500 py-10">
                    {rows.length === 0 ? "Henüz harcama yok." : "Filtreyle eşleşen kayıt yok."}
                  </TableCell></TableRow>
                )}
                {filtered.map((it) => (
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
              {filtered.length > 0 && (
                <TableFooter>
                  <TableRow className="bg-slate-50">
                    <TableCell colSpan={3} className="font-bold uppercase text-xs tracking-wider">
                      {f.month && f.month !== "all" ? `${monthLabelFromKey(f.month)} Toplamı` : "Toplam"}
                    </TableCell>
                    <TableCell className="text-right font-extrabold text-lg text-slate-900" data-testid={`spending-total-${cat}`}>
                      {formatTRY(total)}
                    </TableCell>
                    <TableCell />
                  </TableRow>
                  {f.month && f.month !== "all" && grand !== total && (
                    <TableRow className="bg-slate-50/50">
                      <TableCell colSpan={3} className="font-semibold text-slate-500 uppercase text-xs tracking-wider">Tüm Zamanlar Toplamı</TableCell>
                      <TableCell className="text-right font-bold text-slate-700">{formatTRY(grand)}</TableCell>
                      <TableCell />
                    </TableRow>
                  )}
                </TableFooter>
              )}
            </Table>
          </CardContent>
        </Card>
      </>
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
              {editing ? "Harcamayı Düzenle" : "Yeni Harcama"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Harcama kime ait? *
              </Label>
              <div className="grid grid-cols-3 gap-2" data-testid="spending-form-category-group">
                {CATS.map((c) => {
                  const active = form.category === c.key;
                  return (
                    <button
                      key={c.key}
                      type="button"
                      onClick={() => setForm({ ...form, category: c.key })}
                      className={`py-2.5 px-3 rounded-lg text-sm font-semibold border transition-colors flex items-center justify-center gap-2 ${
                        active
                          ? "bg-slate-900 text-white border-slate-900"
                          : "bg-white text-slate-700 border-slate-200 hover:border-slate-400 hover:bg-slate-50"
                      }`}
                      data-testid={`spending-form-category-${c.key}`}
                    >
                      <c.Icon className="w-4 h-4" />
                      {c.short}
                    </button>
                  );
                })}
              </div>
              {!form.category && (
                <p className="text-xs text-rose-600">Harcamanın kime ait olduğunu seçmelisiniz.</p>
              )}
              {editing && editing.category !== form.category && form.category && (
                <p className="text-xs text-amber-700">
                  Bu kayıt <strong>{CATS.find((c) => c.key === editing.category)?.short}</strong> sekmesinden{" "}
                  <strong>{CATS.find((c) => c.key === form.category)?.short}</strong> sekmesine taşınacak.
                </p>
              )}
            </div>
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
              <Button type="submit" disabled={loading || !form.category} className="bg-slate-900 hover:bg-slate-800" data-testid="spending-form-save">Kaydet</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
