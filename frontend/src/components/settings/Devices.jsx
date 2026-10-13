import { useEffect, useState } from "react";
import { api, extractError, formatDateTime } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { MonitorSmartphone, Trash2, LogOut } from "lucide-react";
import { toast } from "sonner";

export const Devices = () => {
  const { logout } = useAuth();
  const [devices, setDevices] = useState([]);
  const load = () => api.get("/auth/devices").then(({ data }) => setDevices(data)).catch((e) => toast.error(extractError(e)));
  useEffect(() => { load(); }, []);

  const remove = async (d) => {
    if (!window.confirm(`"${d.browser} · ${d.os}" tanınan cihazlardan kaldırılsın mı? Bu cihazdan bir sonraki girişte bildirim e-postası gönderilir.`)) return;
    try { await api.delete(`/auth/devices/${d.id}`); toast.success("Cihaz kaldırıldı"); load(); } catch (e) { toast.error(extractError(e)); }
  };
  const logoutAll = async () => {
    if (!window.confirm("Bu cihaz dahil tüm cihazlardaki oturumlarınız kapatılacak. Devam edilsin mi?")) return;
    try { await api.post("/auth/logout-all"); toast.success("Tüm cihazlardan çıkış yapıldı"); localStorage.removeItem("ks_token"); logout(); }
    catch (e) { toast.error(extractError(e)); }
  };

  return (
    <div className="space-y-2 rounded-xl border border-slate-200 p-4" data-testid="devices-section">
      <div className="text-sm font-bold text-slate-900 flex items-center gap-2"><MonitorSmartphone className="w-4 h-4" /> Tanınan Cihazlar</div>
      <p className="text-[11px] text-slate-500">Listede olmayan bir cihazdan giriş yapılınca size ve yöneticiye e-posta gönderilir.</p>
      {devices.length === 0 ? (
        <div className="text-xs text-slate-500" data-testid="devices-empty">Kayıtlı cihaz yok.</div>
      ) : devices.map((d) => (
        <div key={d.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2" data-testid={`device-${d.id}`}>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-900">{d.browser} · {d.os} {d.current && <Badge variant="outline" className="ml-1 text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200">Bu cihaz</Badge>}</div>
            <div className="text-[11px] text-slate-500">IP {d.ip} · Son görülme {formatDateTime(d.last_seen)}</div>
          </div>
          {!d.current && (
            <Button size="sm" variant="ghost" className="text-rose-600 hover:bg-rose-50" onClick={() => remove(d)} data-testid={`device-remove-${d.id}`}><Trash2 className="w-4 h-4" /></Button>
          )}
        </div>
      ))}
      <Button size="sm" variant="outline" onClick={logoutAll} className="text-rose-700 border-rose-200 hover:bg-rose-50" data-testid="logout-all-btn">
        <LogOut className="w-4 h-4 mr-2" /> Tüm cihazlardan çıkış yap
      </Button>
    </div>
  );
};
