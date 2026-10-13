import { useEffect, useState } from "react";
import { api, formatDateTime, extractError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { History, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { LogDeleteToolbar } from "@/components/logs/LogDeleteToolbar";
import { ConfirmDeleteDialog } from "@/components/logs/ConfirmDeleteDialog";

const SECTIONS = ["", "Gelirler", "Giderler", "Faturalar", "Stok", "Harcamalar", "Yapılacaklar", "auth"];
const ACTION_COLORS = {
  create: "bg-emerald-100 text-emerald-700 border-emerald-200",
  update: "bg-amber-100 text-amber-700 border-amber-200",
  delete: "bg-rose-100 text-rose-700 border-rose-200",
  import: "bg-indigo-100 text-indigo-700 border-indigo-200",
  login: "bg-slate-100 text-slate-700 border-slate-200",
  logout: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function ActivityLog() {
  const [logs, setLogs] = useState([]);
  const [filterUser, setFilterUser] = useState("");
  const [filterSection, setFilterSection] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState([]);
  const [confirm, setConfirm] = useState(null);
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const load = async () => {
    try { const { data } = await api.get("/activity-logs"); setLogs(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

  const requestDelete = (payload, title, desc) => setConfirm({ payload, title, desc });
  const doDelete = async () => {
    try {
      const { data } = await api.post("/activity-logs/delete", confirm.payload);
      toast.success(`${data.deleted} kayıt silindi`);
      setSelected([]);
      load();
    } catch (e) { toast.error(extractError(e)); }
    setConfirm(null);
  };
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const users = [...new Set(logs.map((l) => l.user_name))].filter(Boolean);
  const filtered = logs.filter((l) => {
    if (filterUser && l.user_name !== filterUser) return false;
    if (filterSection && l.section !== filterSection) return false;
    if (search) {
      const s = search.toLowerCase();
      const hay = `${l.user_name} ${l.action} ${l.section} ${l.details}`.toLowerCase();
      if (!hay.includes(s)) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center">
          <History className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">İşlem Günlüğü</h2>
          <p className="text-sm text-slate-600 mt-1">Her kullanıcının tüm hareketleri tarih ve saat ile birlikte burada görüntülenir.</p>
        </div>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input placeholder="Arama (işlem veya detay)" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="log-search" />
            <Select value={filterUser || "all"} onValueChange={(v) => setFilterUser(v === "all" ? "" : v)}>
              <SelectTrigger data-testid="log-user-filter"><SelectValue placeholder="Kullanıcı" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm kullanıcılar</SelectItem>
                {users.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={filterSection || "all"} onValueChange={(v) => setFilterSection(v === "all" ? "" : v)}>
              <SelectTrigger data-testid="log-section-filter"><SelectValue placeholder="Bölüm" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tüm bölümler</SelectItem>
                {SECTIONS.filter(Boolean).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          {isAdmin && <LogDeleteToolbar selectedCount={selected.length} selectedIds={selected} onRequest={requestDelete} />}
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          {isAdmin && filtered.length > 0 && (
            <label className="flex items-center gap-3 px-4 py-3 bg-slate-50 border-b border-slate-100 text-sm text-slate-600 cursor-pointer">
              <Checkbox
                checked={filtered.every((l) => selected.includes(l.id))}
                onCheckedChange={(c) => setSelected(c ? filtered.map((l) => l.id) : [])}
                data-testid="log-select-all"
              />
              Listelenen tümünü seç ({filtered.length})
            </label>
          )}
          <div className="divide-y divide-slate-100">
            {filtered.length === 0 && <div className="text-center text-slate-500 py-12">Kayıt bulunamadı.</div>}
            {filtered.map((l) => (
              <div key={l.id} className="group p-4 flex items-start gap-4" data-testid={`log-row-${l.id}`}>
                {isAdmin && <Checkbox checked={selected.includes(l.id)} onCheckedChange={() => toggle(l.id)} data-testid={`log-select-${l.id}`} />}
                <div className="w-28 shrink-0 text-xs text-slate-500 font-mono">{formatDateTime(l.timestamp)}</div>
                <Badge variant="outline" className={`shrink-0 ${ACTION_COLORS[l.action] || ""}`}>
                  {l.action}
                </Badge>
                <div className="shrink-0 text-sm font-semibold text-slate-700">{l.section}</div>
                <div className="flex-1 min-w-0 text-sm text-slate-600 truncate">{l.details}</div>
                <div className="text-xs text-slate-500 font-medium">{l.user_name}</div>
                {isAdmin && (
                  <button
                    onClick={() => requestDelete({ mode: "ids", ids: [l.id] }, "Bu kayıt silinsin mi?", `"${l.details || l.section}" kaydı kalıcı olarak silinecek.`)}
                    className="text-slate-300 hover:text-rose-600 transition-colors"
                    data-testid={`log-delete-${l.id}`}
                  ><Trash2 className="w-4 h-4" /></button>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <ConfirmDeleteDialog confirm={confirm} onClose={() => setConfirm(null)} onConfirm={doDelete} />
    </div>
  );
}
