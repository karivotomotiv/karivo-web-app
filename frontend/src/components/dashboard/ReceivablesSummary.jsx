import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatTRY, formatDate } from "@/lib/api";
import { Users, ChevronRight } from "lucide-react";

export const ReceivablesSummary = ({ r }) => {
  const max = r.items[0]?.remaining || 1;
  return (
    <Card className="border-slate-200 shadow-sm h-full" data-testid="receivables-summary">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2"><Users className="w-4 h-4" /> Cari Alacaklar</CardTitle>
        <p className="text-[11px] text-slate-500 mt-0.5">Anlık açık bakiye (alacak − gelen ödeme − borç)</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-xl bg-slate-50 px-3 py-2.5">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Toplam Açık Alacak</div>
            <div className="text-lg font-extrabold text-slate-900" data-testid="receivables-total">{formatTRY(r.total)}</div>
          </div>
          <div className="rounded-xl bg-slate-50 px-3 py-2.5">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Borçlu Müşteri</div>
            <div className="text-lg font-extrabold text-slate-900" data-testid="receivables-count">{r.debtor_count}</div>
          </div>
        </div>
        {r.items.length === 0 ? (
          <div className="text-sm text-slate-500 text-center py-6" data-testid="receivables-empty">Açık alacak bulunamadı.</div>
        ) : (
          <div className="space-y-1 max-h-72 overflow-y-auto pr-1" data-testid="receivables-list">
            {r.items.map((c) => (
              <Link key={c.id} to={`/cariler/${c.id}`} className="group block px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors" data-testid={`receivable-${c.id}`}>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-900 truncate">{c.name}</span>
                  <span className="flex items-center gap-1 text-sm font-bold text-slate-900 shrink-0" data-testid={`receivable-amount-${c.id}`}>
                    {formatTRY(c.remaining)} <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </div>
                <div className="mt-1.5 h-1 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${Math.max(4, (c.remaining / max) * 100)}%` }} />
                </div>
                {c.oldest_open_date && (
                  <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500" data-testid={`receivable-age-${c.id}`}>
                    <span>En eski borç: {formatDate(c.oldest_open_date)}</span>
                    <span className={`font-semibold ${c.open_days > 60 ? "text-rose-700" : c.open_days > 30 ? "text-amber-700" : "text-slate-600"}`}>
                      {c.open_days === 0 ? "bugün" : `${c.open_days} gündür ödenmedi`}
                    </span>
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
