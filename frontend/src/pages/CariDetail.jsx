import { useEffect, useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { ArrowLeft, Plus, Pencil, Trash2, TrendingUp, TrendingDown, Users, Phone, MapPin, HandCoins, Wallet } from "lucide-react";
import { toast } from "sonner";
import { StatementDialog } from "@/components/cari/StatementDialog";
import { askConfirm } from "@/components/ConfirmHost";

const TYPE_META = {
  alacak: { label: "Alacak", shortLabel: "ALACAK", color: "emerald", btnClass: "bg-emerald-600 hover:bg-emerald-700" },
  borc:   { label: "Borç", shortLabel: "BORÇ", color: "rose", btnClass: "bg-rose-600 hover:bg-rose-700" },
  odeme:  { label: "Gelen Ödeme", shortLabel: "ÖDEME", color: "sky", btnClass: "bg-sky-600 hover:bg-sky-700" },
};

const BADGE_CLASS = {
  alacak: "bg-emerald-100 text-emerald-700",
  borc: "bg-rose-100 text-rose-700",
  odeme: "bg-sky-100 text-sky-700",
};

export default function CariDetail() {
  const { id } = useParams();
  const [cari, setCari] = useState(null);
  const [txs, setTxs] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ type: "alacak", amount: "", description: "", date: "" });
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("all");

  const load = async () => {
    try {
      const [c, t] = await Promise.all([
        api.get(`/cariler/${id}`),
        api.get(`/cariler/${id}/transactions`),
      ]);
      setCari(c.data);
      setTxs(t.data);
    } catch (e) {
      toast.error(extractError(e));
    }
  };
  useEffect(() => { load(); }, [id]); // eslint-disable-line

  const openNew = (type = "alacak") => {
    setEditing(null);
    setForm({ type, amount: "", description: "", date: new Date().toISOString().slice(0, 10) });
    setOpen(true);
  };
  const openEdit = (tx) => {
    setEditing(tx);
    setForm({ type: tx.type, amount: String(tx.amount), description: tx.description || "", date: tx.date });
    setOpen(true);
  };

  const save = async (e) => {
    e?.preventDefault();
    if (!form.amount) { toast.error("Tutar gereklidir"); return; }
    setLoading(true);
    try {
      const payload = {
        type: form.type,
        amount: Number(form.amount),
        description: form.description,
        date: form.date || null,
      };
      if (editing) {
        await api.put(`/cariler/${id}/transactions/${editing.id}`, payload);
        toast.success("Hareket güncellendi");
      } else {
        await api.post(`/cariler/${id}/transactions`, payload);
        toast.success(`${TYPE_META[form.type].label} eklendi`);
      }
      setOpen(false);
      load();
    } catch (e) {
      toast.error(extractError(e));
    } finally { setLoading(false); }
  };

  const remove = async (tx) => {
    if (!(await askConfirm("Bu hareketi silmek istiyor musunuz?"))) return;
    try {
      await api.delete(`/cariler/${id}/transactions/${tx.id}`);
      toast.success("Silindi");
      load();
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const filtered = useMemo(() => {
    if (tab === "all") return txs;
    return txs.filter((t) => t.type === tab);
  }, [txs, tab]);

  if (!cari) {
    return <div className="text-slate-500">Yükleniyor...</div>;
  }

  const net = Number(cari.net || 0);
  const alacakCount = txs.filter((t) => t.type === "alacak").length;
  const borcCount = txs.filter((t) => t.type === "borc").length;
  const odemeCount = txs.filter((t) => t.type === "odeme").length;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <Link to="/cariler" className="w-10 h-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center hover:bg-slate-200" data-testid="cari-back-btn">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-sky-700" />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cari Detay</span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 mt-1" data-testid="cari-name">{cari.name}</h2>
            <div className="flex gap-4 text-xs text-slate-500 mt-1">
              {cari.phone && <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" />{cari.phone}</span>}
              {cari.address && <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" />{cari.address}</span>}
            </div>
            {cari.note && <p className="text-sm text-slate-600 mt-2 max-w-xl">{cari.note}</p>}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <StatementDialog cariId={id} cariName={cari.name} />
          <Button onClick={() => openNew("alacak")} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="cari-add-alacak">
            <Plus className="w-4 h-4 mr-2" /> Alacak Ekle
          </Button>
          <Button onClick={() => openNew("borc")} className="bg-rose-600 hover:bg-rose-700 text-white" data-testid="cari-add-borc">
            <Plus className="w-4 h-4 mr-2" /> Borç Ekle
          </Button>
          <Button onClick={() => openNew("odeme")} className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="cari-add-odeme">
            <HandCoins className="w-4 h-4 mr-2" /> Gelen Ödeme Gir
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-slate-200 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Toplam Alacak</div>
                <div className="mt-2 text-2xl font-extrabold text-emerald-700" data-testid="cari-detail-alacak">{formatTRY(cari.total_alacak)}</div>
              </div>
              <div className="w-11 h-11 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center"><TrendingUp className="w-5 h-5" /></div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Alınan Ödeme</div>
                <div className="mt-2 text-2xl font-extrabold text-sky-700" data-testid="cari-detail-odeme">{formatTRY(cari.total_odeme)}</div>
              </div>
              <div className="w-11 h-11 rounded-xl bg-sky-100 text-sky-700 flex items-center justify-center"><HandCoins className="w-5 h-5" /></div>
            </div>
          </CardContent>
        </Card>
        <Card className={`border-2 shadow-sm ${net >= 0 ? "border-emerald-200 bg-emerald-50/50" : "border-rose-200 bg-rose-50/50"}`}>
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Net Bakiye</div>
                <div className={`mt-2 text-2xl font-extrabold ${net >= 0 ? "text-emerald-700" : "text-rose-700"}`} data-testid="cari-detail-net">
                  {formatTRY(net)}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {net > 0 && <>Cari size borçlu</>}
                  {net < 0 && <>Siz cariye borçlusunuz</>}
                  {net === 0 && <>Hesap kapalı</>}
                </div>
              </div>
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center font-bold ${net >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>₺</div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid grid-cols-4 w-full max-w-2xl">
          <TabsTrigger value="all" data-testid="cari-tab-all">Tümü ({txs.length})</TabsTrigger>
          <TabsTrigger value="alacak" data-testid="cari-tab-alacak">Alacaklar ({alacakCount})</TabsTrigger>
          <TabsTrigger value="odeme" data-testid="cari-tab-odeme">Ödemeler ({odemeCount})</TabsTrigger>
          <TabsTrigger value="borc" data-testid="cari-tab-borc">Borçlar ({borcCount})</TabsTrigger>
        </TabsList>
      </Tabs>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Tarih</TableHead>
                <TableHead>Tür</TableHead>
                <TableHead>Açıklama</TableHead>
                <TableHead>Ekleyen</TableHead>
                <TableHead className="text-right">Alacak</TableHead>
                <TableHead className="text-right">Ödeme</TableHead>
                <TableHead className="text-right">Borç</TableHead>
                <TableHead className="text-right">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 && (
                <TableRow><TableCell colSpan={8} className="text-center text-slate-500 py-10">Hareket yok. Yukarıdan ekleyin.</TableCell></TableRow>
              )}
              {filtered.map((tx) => (
                <TableRow key={tx.id} data-testid={`cari-tx-row-${tx.id}`}>
                  <TableCell className="text-slate-700">{formatDate(tx.date)}</TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center text-xs font-bold px-2 py-1 rounded-full ${BADGE_CLASS[tx.type]}`}>
                      {TYPE_META[tx.type]?.shortLabel || tx.type.toUpperCase()}
                    </span>
                  </TableCell>
                  <TableCell className="font-medium text-slate-900">{tx.description || "-"}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{tx.created_by_name}</TableCell>
                  <TableCell className="text-right font-semibold text-emerald-700">
                    {tx.type === "alacak" ? formatTRY(tx.amount) : "-"}
                  </TableCell>
                  <TableCell className="text-right font-semibold text-sky-700">
                    {tx.type === "odeme" ? formatTRY(tx.amount) : "-"}
                  </TableCell>
                  <TableCell className="text-right font-semibold text-rose-700">
                    {tx.type === "borc" ? formatTRY(tx.amount) : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(tx)} data-testid={`cari-tx-edit-${tx.id}`}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(tx)} className="text-rose-600 hover:bg-rose-50" data-testid={`cari-tx-delete-${tx.id}`}>
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
                  <TableCell colSpan={4} className="font-bold uppercase text-xs tracking-wider">Toplam</TableCell>
                  <TableCell className="text-right font-extrabold text-emerald-700">
                    {formatTRY(filtered.filter((t) => t.type === "alacak").reduce((s, i) => s + Number(i.amount || 0), 0))}
                  </TableCell>
                  <TableCell className="text-right font-extrabold text-sky-700">
                    {formatTRY(filtered.filter((t) => t.type === "odeme").reduce((s, i) => s + Number(i.amount || 0), 0))}
                  </TableCell>
                  <TableCell className="text-right font-extrabold text-rose-700">
                    {formatTRY(filtered.filter((t) => t.type === "borc").reduce((s, i) => s + Number(i.amount || 0), 0))}
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
            <DialogTitle>
              {editing ? "Hareketi Düzenle" : `${TYPE_META[form.type].label} Ekle`}
            </DialogTitle>
            <DialogDescription>
              {cari.name} için {TYPE_META[form.type].label.toLowerCase()} hareketi oluşturun.
              {form.type === "odeme" && " Bu hareket toplam alacaktan düşülür."}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            {/* Type toggle - 3 button group */}
            <div className="grid grid-cols-3 gap-2 p-1 bg-slate-100 rounded-lg">
              <button
                type="button"
                onClick={() => setForm({ ...form, type: "alacak" })}
                className={`py-2 px-3 rounded-md text-sm font-semibold transition-colors ${form.type === "alacak" ? "bg-emerald-600 text-white" : "text-slate-600 hover:text-slate-900"}`}
                data-testid="cari-form-type-alacak"
              >
                Alacak
              </button>
              <button
                type="button"
                onClick={() => setForm({ ...form, type: "odeme" })}
                className={`py-2 px-3 rounded-md text-sm font-semibold transition-colors ${form.type === "odeme" ? "bg-sky-600 text-white" : "text-slate-600 hover:text-slate-900"}`}
                data-testid="cari-form-type-odeme"
              >
                Ödeme
              </button>
              <button
                type="button"
                onClick={() => setForm({ ...form, type: "borc" })}
                className={`py-2 px-3 rounded-md text-sm font-semibold transition-colors ${form.type === "borc" ? "bg-rose-600 text-white" : "text-slate-600 hover:text-slate-900"}`}
                data-testid="cari-form-type-borc"
              >
                Borç
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Tutar (₺)</Label>
                <Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} data-testid="cari-form-amount" />
              </div>
              <div className="space-y-2">
                <Label>Tarih</Label>
                <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="cari-form-date" />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Açıklama</Label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="cari-form-desc" />
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>İptal</Button>
              <Button type="submit" disabled={loading} className={`${TYPE_META[form.type].btnClass} text-white`} data-testid="cari-form-save">
                {loading ? "Kaydediliyor..." : "Kaydet"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
