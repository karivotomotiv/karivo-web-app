import { useEffect, useState } from "react";
import { api, formatDateTime, extractError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { History } from "lucide-react";
import { toast } from "sonner";

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

  const load = async () => {
    try { const { data } = await api.get("/activity-logs"); setLogs(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { load(); }, []);

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
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <div className="divide-y divide-slate-100">
            {filtered.length === 0 && <div className="text-center text-slate-500 py-12">Kayıt bulunamadı.</div>}
            {filtered.map((l) => (
              <div key={l.id} className="p-4 flex items-start gap-4" data-testid={`log-row-${l.id}`}>
                <div className="w-28 shrink-0 text-xs text-slate-500 font-mono">{formatDateTime(l.timestamp)}</div>
                <Badge variant="outline" className={`shrink-0 ${ACTION_COLORS[l.action] || ""}`}>
                  {l.action}
                </Badge>
                <div className="shrink-0 text-sm font-semibold text-slate-700">{l.section}</div>
                <div className="flex-1 min-w-0 text-sm text-slate-600 truncate">{l.details}</div>
                <div className="text-xs text-slate-500 font-medium">{l.user_name}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
