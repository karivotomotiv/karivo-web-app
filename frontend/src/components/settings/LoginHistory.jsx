import { useEffect, useState } from "react";
import { api, extractError, formatDateTime } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";

const REASONS = {
  ok: null,
  wrong_password: "Yanlış şifre",
  wrong_password_locked: "Yanlış şifre · hesap kilitlendi",
  locked: "Kilitli hesaba deneme",
};

export const LoginHistory = ({ userId }) => {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.get(`/admin/users/${userId}/login-history`).then(({ data }) => setRows(data)).catch((e) => setErr(extractError(e)));
  }, [userId]);

  if (err) return <div className="text-xs text-rose-700 px-3 py-2">{err}</div>;
  if (!rows) return <div className="text-xs text-slate-500 px-3 py-2"><Loader2 className="w-3 h-3 inline animate-spin mr-1" />Yükleniyor...</div>;
  if (!rows.length) return <div className="text-xs text-slate-500 px-3 py-2" data-testid={`login-history-empty-${userId}`}>Henüz giriş kaydı yok.</div>;

  return (
    <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 divide-y divide-slate-100" data-testid={`login-history-${userId}`}>
      {rows.map((r) => (
        <div key={r.id} className={`flex items-center justify-between gap-2 px-3 py-1.5 text-xs ${r.success ? "" : "bg-rose-50/60"}`} data-testid={`login-history-row-${r.id}`}>
          <div className="min-w-0">
            <div className="font-semibold text-slate-800">{formatDateTime(r.at)}</div>
            <div className="text-slate-500 truncate">{r.browser} · {r.os} · IP {r.ip}</div>
          </div>
          <div className="flex flex-col items-end gap-0.5 shrink-0">
            {r.success
              ? <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200">Başarılı</Badge>
              : <Badge variant="outline" className="text-[10px] bg-rose-100 text-rose-700 border-rose-300">Başarısız</Badge>}
            {!r.success && <span className="text-[10px] text-rose-700">{REASONS[r.reason] || r.reason}</span>}
            {r.new_device && <span className="text-[10px] font-semibold text-amber-700">Yeni cihaz</span>}
          </div>
        </div>
      ))}
    </div>
  );
};
