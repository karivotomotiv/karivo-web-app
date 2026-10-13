import { useEffect, useState } from "react";
import { api, extractError, formatDateTime } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ShieldAlert, Ban, Undo2 } from "lucide-react";
import { toast } from "sonner";

const SuspiciousRow = ({ r, currentIp, onBlock }) => (
  <div className="rounded-lg bg-slate-50 px-3 py-2 space-y-1" data-testid={`suspicious-ip-${r.ip}`}>
    <div className="flex items-center justify-between gap-2">
      <div className="min-w-0">
        <div className="text-sm font-bold text-slate-900 font-mono">{r.ip} {r.ip === currentIp && <Badge variant="outline" className="ml-1 text-[10px]">Sizin IP</Badge>}</div>
        <div className="text-[11px] text-slate-500">{r.fail_count} hatalı deneme · son: {formatDateTime(r.last_at)}</div>
      </div>
      {r.blocked ? (
        <Badge variant="outline" className="bg-rose-100 text-rose-700 border-rose-300 text-[10px]">Engelli</Badge>
      ) : r.ip !== currentIp && (
        <Button size="sm" variant="outline" className="h-7 text-xs text-rose-700 border-rose-200 hover:bg-rose-50" onClick={() => onBlock(r)} data-testid={`block-ip-${r.ip}`}>
          <Ban className="w-3.5 h-3.5 mr-1" /> Engelle
        </Button>
      )}
    </div>
    <div className="text-[11px] text-slate-600 break-all">Denenen: {r.emails.join(", ")}</div>
    <div className="text-[11px] text-slate-500">{r.agents.join(" | ")}</div>
    {r.recent_users.length > 0 && (
      <div className="text-[11px] font-semibold text-amber-700" data-testid={`suspicious-ip-users-${r.ip}`}>Bu IP'den son 30 günde başarılı giriş: {r.recent_users.join(", ")}</div>
    )}
  </div>
);

export const IpSecurity = () => {
  const [data, setData] = useState({ current_ip: "", items: [] });
  const [blocked, setBlocked] = useState([]);
  const load = () => {
    api.get("/admin/security/suspicious-ips").then(({ data }) => setData(data)).catch((e) => toast.error(extractError(e)));
    api.get("/admin/security/blocked-ips").then(({ data }) => setBlocked(data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const block = async (r) => {
    const warn = r.recent_users.length
      ? `\n\nDİKKAT: Bu IP'den son 30 günde başarılı giriş yapan kullanıcılar: ${r.recent_users.join(", ")}.\nAynı internet bağlantısını kullanan herkes uygulamaya erişemeyecek.`
      : "";
    if (!window.confirm(`${r.ip} adresi kalıcı olarak engellensin mi? Bu IP uygulamaya hiç erişemeyecek.${warn}`)) return;
    try { await api.post("/admin/security/blocked-ips", { ip: r.ip }); toast.success(`${r.ip} engellendi`); load(); }
    catch (e) { toast.error(extractError(e)); }
  };
  const unblock = async (ip) => {
    if (!window.confirm(`${ip} adresinin engeli kaldırılsın mı?`)) return;
    try { await api.delete(`/admin/security/blocked-ips/${encodeURIComponent(ip)}`); toast.success("Engel kaldırıldı"); load(); }
    catch (e) { toast.error(extractError(e)); }
  };

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 p-4" data-testid="ip-security">
      <div className="text-sm font-bold text-slate-900 flex items-center gap-2"><ShieldAlert className="w-4 h-4" /> Şüpheli IP'ler</div>
      <p className="text-[11px] text-slate-500">Son 7 günde hatalı giriş deneyen IP adresleri. Sizin IP'niz: <span className="font-mono">{data.current_ip}</span></p>
      {data.items.length === 0
        ? <div className="text-xs text-slate-500" data-testid="suspicious-empty">Hatalı deneme yapan IP yok.</div>
        : <div className="space-y-2 max-h-64 overflow-y-auto">{data.items.map((r) => <SuspiciousRow key={r.ip} r={r} currentIp={data.current_ip} onBlock={block} />)}</div>}
      <div className="text-xs font-bold text-slate-900 pt-1">Engellenen IP'ler ({blocked.length})</div>
      {blocked.length === 0 ? <div className="text-xs text-slate-500" data-testid="blocked-empty">Engelli IP yok.</div> : blocked.map((b) => (
        <div key={b.ip} className="flex items-center justify-between gap-2 rounded-lg bg-rose-50 px-3 py-2" data-testid={`blocked-ip-${b.ip}`}>
          <div className="text-xs"><span className="font-mono font-bold text-slate-900">{b.ip}</span><div className="text-slate-500">{b.blocked_by} · {formatDateTime(b.blocked_at)}</div></div>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => unblock(b.ip)} data-testid={`unblock-ip-${b.ip}`}><Undo2 className="w-3.5 h-3.5 mr-1" /> Engeli kaldır</Button>
        </div>
      ))}
    </div>
  );
};
