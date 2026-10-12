import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatTRY } from "@/lib/api";
import { monthLabelFromKey } from "@/components/FilterBar";
import { pctChange } from "./period";
import { CalendarDays, ChevronLeft, ChevronRight, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

export const Delta = ({ cur, prev, money = true, testId }) => {
  const p = pctChange(cur, prev);
  const diff = cur - prev;
  if (diff === 0) return <span className="inline-flex items-center gap-0.5 text-[11px] text-slate-400" data-testid={testId}><Minus className="w-3 h-3" /> değişim yok</span>;
  const up = diff > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${up ? "text-emerald-700" : "text-rose-700"}`} data-testid={testId}>
      {up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
      {money ? formatTRY(Math.abs(diff)) : Math.abs(diff)}{p !== null && ` (%${Math.abs(p).toFixed(0)})`}
    </span>
  );
};

export const METRICS = [
  { key: "income_total", label: "Gelir" },
  { key: "expense_total", label: "Gider" },
  { key: "income_expense_diff", label: "Gelir − Gider" },
  { key: "sales_revenue", label: "Satış Tutarı" },
  { key: "sales_count", label: "Satış Adedi", money: false },
  { key: "collections_total", label: "Tahsilat" },
];

export const MonthlySummary = ({ month, onMonth, data, isCurrent }) => (
  <Card className="border-slate-200 shadow-sm" data-testid="monthly-summary">
    <CardHeader className="pb-3 flex flex-row flex-wrap items-center justify-between gap-2 space-y-0">
      <div>
        <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2"><CalendarDays className="w-4 h-4" /> Aylık Rapor</CardTitle>
        <p className="text-[11px] text-slate-500 mt-0.5">Önceki ayla karşılaştırma</p>
      </div>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onMonth(-1)} data-testid="monthly-prev"><ChevronLeft className="w-4 h-4" /></Button>
        <span className="text-sm font-semibold text-slate-900 min-w-[110px] text-center" data-testid="monthly-label">{monthLabelFromKey(month)}</span>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onMonth(1)} disabled={isCurrent} data-testid="monthly-next"><ChevronRight className="w-4 h-4" /></Button>
      </div>
    </CardHeader>
    <CardContent>
      {!data ? (
        <div className="text-sm text-slate-500 py-6 text-center">Yükleniyor...</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            {METRICS.map((m) => (
              <div key={m.key} className="rounded-xl bg-slate-50 px-3 py-2.5" data-testid={`monthly-${m.key}`}>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{m.label}</div>
                <div className="text-base font-extrabold text-slate-900">{m.money === false ? data.current[m.key] : formatTRY(data.current[m.key])}</div>
                <Delta cur={data.current[m.key]} prev={data.previous[m.key]} money={m.money !== false} />
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-slate-500" data-testid="monthly-stock-moves">
              Stok hareketleri: {data.stock_movements_summary.count} kayıt · giriş {data.stock_movements_summary.in_qty} · çıkış {data.stock_movements_summary.out_qty}
            </span>
            <Link to={`/aylik-rapor?ay=${month}`} className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700 hover:underline" data-testid="monthly-detail-link">
              Rapor detayı ve stok hareketleri <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </>
      )}
    </CardContent>
  </Card>
);
