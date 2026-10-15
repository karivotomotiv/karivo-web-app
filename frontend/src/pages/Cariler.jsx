import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, Users, Search, ChevronRight, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { CariMobileList } from "@/components/cari/CariMobileList";
import { askConfirm } from "@/components/ConfirmHost";

const empty = { name: "", phone: "", address: "", note: "" };

export default function Cariler() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try { const { data } = await api.get("/cariler"); setItems(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    if (!s) return items;
    return items.filter((c) =>
      [c.name, c.phone, c.address, c.note].some((f) => String(f || "").toLowerCase().includes(s))
    );
  }, [items, search]);

  const openNew = () => { setEditing(null); setForm(empty); setOpen(true); };
  const openEdit = (it) => {
    setEditing(it);
    setForm({ name: it.name, phone: it.phone || "", address: it.address || "", note: it.note || "" });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.name.trim()) { toast.error("Cari adı gereklidir"); return; }
    setLoading(true);
    try {
      if (editing) {
        await api.put(`/cariler/${editing.id}`, form);
        toast.success("Cari güncellendi");
      } else {
        await api.post("/cariler", form);
        toast.success("Cari eklendi");
      }
      setOpen(false);
      load();
    } catch (e) { toast.error(extractError(e)); }
    finally { setLoading(false); }
  };

  const remove = async (it, e) => {
    e?.stopPropagation();
    if (!(await askConfirm(`"${it.name}" carisini ve tüm hareketlerini silmek istiyor musunuz?`))) return;
    try { await api.delete(`/cariler/${it.id}`); toast.success("Cari silindi"); load(); }
    catch (e) { toast.error(extractError(e)); }
  };

  const totalAlacak = filtered.reduce((s, i) => s + Number(i.total_alacak || 0), 0);
  const totalBorc = filtered.reduce((s, i) => s + Number(i.total_borc || 0), 0);
  const totalNet = filtered.reduce((s, i) => s + Number(i.net || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-sky-100 text-sky-700 flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Cariler</h2>
            <p className="text-sm text-slate-600 mt-1">
              Müşteri ve tedarikçi kayıtlarınızı yönetin; her birinin borç/alacak hareketlerini satır üzerine tıklayarak takip edin.
            </p>
          </div>
        </div>
        <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="cari-add-btn">
          <UserPlus className="w-4 h-4 mr-2" /> Yeni Cari
        </Button>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-4 border-b border-slate-100">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="Cari ara (ad, telefon, adres, not)..."
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              data-testid="cari-search"
            />
          </div>
        </CardContent>
        <CardContent className="p-0">
          <CariMobileList
            items={filtered}
            emptyText={items.length === 0 ? 'Henüz cari yok. "Yeni Cari" ile ekleyin.' : "Aramayla eşleşen cari yok."}
            onOpen={(it) => nav(`/cariler/${it.id}`)}
            onEdit={openEdit}
            onDelete={(it) => remove(it)}
            totalNet={totalNet}
          />
          <div className="hidden md:block">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Cari Adı</TableHead>
                <TableHead>Telefon</TableHead>
                <TableHead className="text-right">Toplam Alacak</TableHead>
                <TableHead className="text-right">Toplam Borç</TableHead>
                <TableHead className="text-right">Net</TableHead>
                <TableHead>En Eski Açık Borç</TableHead>
                <TableHead className="text-right">Hareket</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-slate-500 py-12">
                    {items.length === 0 ? 'Henüz cari yok. "Yeni Cari" ile ekleyin.' : "Aramayla eşleşen cari yok."}
                  </TableCell>
                </TableRow>
              )}
              {filtered.map((it) => {
                const net = Number(it.net || 0);
                return (
                  <TableRow
                    key={it.id}
                    className="cursor-pointer hover:bg-slate-50/80"
                    onClick={() => nav(`/cariler/${it.id}`)}
                    data-testid={`cari-row-${it.id}`}
                  >
                    <TableCell className="font-semibold text-slate-900">
                      <div className="flex items-center gap-2">
                        {it.name}
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      </div>
                      {it.address && <div className="text-xs text-slate-500 mt-0.5">{it.address}</div>}
                    </TableCell>
                    <TableCell className="text-slate-700">{it.phone || "-"}</TableCell>
                    <TableCell className="text-right font-semibold text-emerald-700">{formatTRY(it.total_alacak)}</TableCell>
                    <TableCell className="text-right font-semibold text-rose-700">{formatTRY(it.total_borc)}</TableCell>
                    <TableCell className={`text-right font-extrabold ${net >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                      {formatTRY(net)}
                    </TableCell>
                    <TableCell className="text-sm" data-testid={`cari-oldest-${it.id}`}>
                      {it.oldest_open_date ? (
                        <>
                          <div className="text-slate-700">{formatDate(it.oldest_open_date)}</div>
                          <div className={`text-xs font-semibold ${it.open_days > 60 ? "text-rose-700" : it.open_days > 30 ? "text-amber-700" : "text-slate-500"}`}>
                            {it.open_days === 0 ? "bugün" : `${it.open_days} gündür ödenmedi`}
                          </div>
                        </>
                      ) : <span className="text-slate-400">—</span>}
                    </TableCell>
                    <TableCell className="text-right text-slate-500 text-sm">{it.tx_count}</TableCell>
                    <TableCell className="text-right">
                      <div className="inline-flex gap-1" onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(it)} data-testid={`cari-edit-${it.id}`}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={(e) => remove(it, e)} className="text-rose-600 hover:bg-rose-50" data-testid={`cari-delete-${it.id}`}>
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
                  <TableCell colSpan={2} className="font-bold text-xs uppercase tracking-wider">Genel Toplam</TableCell>
                  <TableCell className="text-right font-extrabold text-emerald-700" data-testid="cari-total-alacak">{formatTRY(totalAlacak)}</TableCell>
                  <TableCell className="text-right font-extrabold text-rose-700" data-testid="cari-total-borc">{formatTRY(totalBorc)}</TableCell>
                  <TableCell className={`text-right font-extrabold ${totalNet >= 0 ? "text-emerald-700" : "text-rose-700"}`} data-testid="cari-total-net">
                    {formatTRY(totalNet)}
                  </TableCell>
                  <TableCell colSpan={2} />
                </TableRow>
              </TableFooter>
            )}
          </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editing ? "Cari Düzenle" : "Yeni Cari"}</DialogTitle>
            <DialogDescription>Müşteri veya tedarikçi bilgilerini girin.</DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-2">
              <Label>Cari Adı *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="cari-form-name" />
            </div>
            <div className="space-y-2">
              <Label>Telefon</Label>
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="cari-form-phone" />
            </div>
            <div className="space-y-2">
              <Label>Adres</Label>
              <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} data-testid="cari-form-address" />
            </div>
            <div className="space-y-2">
              <Label>Not</Label>
              <Textarea rows={3} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} data-testid="cari-form-note" />
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={loading} className="bg-slate-900 hover:bg-slate-800" data-testid="cari-form-save">
                {loading ? "Kaydediliyor..." : "Kaydet"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
