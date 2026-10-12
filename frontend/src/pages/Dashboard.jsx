import { useCallback, useEffect, useState } from "react";
import { api, formatTRY, formatDateTime, extractError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from "recharts";
import { PeriodFilter } from "@/components/dashboard/PeriodFilter";
import { FinanceSummary } from "@/components/dashboard/FinanceSummary";
import { StockSummary } from "@/components/dashboard/StockSummary";
import { ReceivablesSummary } from "@/components/dashboard/ReceivablesSummary";
import { MonthlySummary } from "@/components/dashboard/MonthlySummary";
import { presetRange, monthKey, shiftMonth } from "@/components/dashboard/period";

const monthShort = (m) => {
  const [y, mm] = m.split("-");
  return new Date(Number(y), Number(mm) - 1, 1).toLocaleDateString("tr-TR", { month: "short", year: "2-digit" });
};

const TrendChart = ({ trend }) => (
  <Card className="border-slate-200 shadow-sm">
    <CardHeader className="pb-2">
      <CardTitle className="text-base font-bold text-slate-900">Aylık Gelir / Gider</CardTitle>
      <p className="text-[11px] text-slate-500">Gelir/Giderler kayıtları, son 12 ay</p>
    </CardHeader>
    <CardContent>
      <div className="h-64" data-testid="monthly-trend-chart">
        {trend.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500 text-sm">Kayıt bulunamadı.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="label" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v)} />
              <Tooltip formatter={(v, n) => [formatTRY(v), n]} contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 13 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="income" name="Gelir" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expense" name="Gider" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </CardContent>
  </Card>
);

export default function Dashboard() {
  const [preset, setPreset] = useState("this_month");
  const [range, setRange] = useState(presetRange("this_month"));
  const [overview, setOverview] = useState(null);
  const currentMonth = monthKey(new Date());
  const [month, setMonth] = useState(currentMonth);
  const [monthly, setMonthly] = useState(null);
  const [trend, setTrend] = useState([]);

  const loadOverview = useCallback(async () => {
    try { const { data } = await api.get("/dashboard/overview", { params: range }); setOverview(data); }
    catch (e) { toast.error(extractError(e)); }
  }, [range]);
  useEffect(() => { loadOverview(); }, [loadOverview]);

  useEffect(() => {
    setMonthly(null);
    api.get("/reports/monthly", { params: { month } }).then(({ data }) => setMonthly(data)).catch((e) => toast.error(extractError(e)));
  }, [month]);

  useEffect(() => {
    api.get("/dashboard/monthly-trend").then(({ data }) => setTrend(data.map((r) => ({ ...r, label: monthShort(r.month) })))).catch(() => {});
  }, []);

  const onPreset = (p) => {
    setPreset(p);
    if (p !== "custom") setRange(presetRange(p));
  };

  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Özet</h2>
          <p className="text-sm text-slate-600 mt-1">Finans, cari alacak ve stok durumuna hızlı bakış.</p>
        </div>
        <PeriodFilter preset={preset} onPreset={onPreset} range={range} onRange={setRange} />
      </div>

      {overview?.warnings?.map((w) => (
        <Alert key={w.type} className="border-amber-300 bg-amber-50" data-testid={`data-warning-${w.type}`}>
          <AlertTriangle className="h-4 w-4 text-amber-700" />
          <AlertTitle className="text-amber-900">Veri tutarsızlığı</AlertTitle>
          <AlertDescription className="text-amber-800 text-sm">{w.message} (Toplam {formatTRY(w.amount)})</AlertDescription>
        </Alert>
      ))}

      {!overview ? (
        <div className="text-sm text-slate-500" data-testid="dashboard-loading">Yükleniyor...</div>
      ) : (
        <>
          <FinanceSummary f={overview.finance} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ReceivablesSummary r={overview.receivables} />
            <StockSummary s={overview.stock} onChanged={loadOverview} />
          </div>
          <p className="text-[11px] text-slate-400 -mt-3" data-testid="snapshot-time">Anlık göstergeler: {formatDateTime(overview.as_of)}</p>
        </>
      )}

      <MonthlySummary month={month} onMonth={(d) => setMonth((m) => shiftMonth(m, d))} data={monthly} isCurrent={month >= currentMonth} />
      <TrendChart trend={trend} />
    </div>
  );
}
