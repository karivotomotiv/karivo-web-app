import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, formatTRY, formatDate, extractError } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { monthLabelFromKey } from "@/components/FilterBar";
import { METRICS, Delta } from "@/components/dashboard/MonthlySummary";
import { monthKey, shiftMonth } from "@/components/dashboard/period";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

const PAY = { nakit: "Nakit", kart: "Kart", havale: "Havale", veresiye: "Veresiye" };
const REASON = { alis: "Alış", satis: "Satış", iade: "İade", "sayim-duzeltme": "Sayım", fire: "Fire", diger: "Diğer", "ilk-kayit": "İlk kayıt", duzenleme: "Düzenleme", birlestirme: "Birleştirme" };

const SimpleTable = ({ rows, cols, testId }) => (
  rows.length === 0 ? (
    <div className="text-sm text-slate-500 text-center py-10" data-testid={`${testId}-empty`}>Bu ay kayıt bulunamadı.</div>
  ) : (
    <div className="overflow-x-auto">
      <Table data-testid={testId}>
        <TableHeader><TableRow>{cols.map((c) => <TableHead key={c.h} className={c.right ? "text-right" : ""}>{c.h}</TableHead>)}</TableRow></TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={r.id || i}>{cols.map((c) => <TableCell key={c.h} className={c.right ? "text-right font-semibold" : ""}>{c.v(r)}</TableCell>)}</TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
);

export default function AylikRapor() {
  const [params, setParams] = useSearchParams();
  const current = monthKey(new Date());
  const month = /^\d{4}-\d{2}$/.test(params.get("ay") || "") ? params.get("ay") : current;
  const [data, setData] = useState(null);

  useEffect(() => {
    setData(null);
    api.get("/reports/monthly", { params: { month, details: true } }).then(({ data }) => setData(data)).catch((e) => toast.error(extractError(e)));
  }, [month]);

  const go = (d) => setParams({ ay: shiftMonth(month, d) });
  const amount = { h: "Tutar", right: true, v: (r) => formatTRY(r.amount) };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Aylık Rapor</h2>
          <p className="text-sm text-slate-600 mt-1">Ay bazında gelir-gider, satış, tahsilat ve stok hareketleri.</p>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" onClick={() => go(-1)} data-testid="report-prev"><ChevronLeft className="w-4 h-4" /></Button>
          <span className="text-sm font-bold min-w-[130px] text-center" data-testid="report-month-label">{monthLabelFromKey(month)}</span>
          <Button variant="outline" size="icon" onClick={() => go(1)} disabled={month >= current} data-testid="report-next"><ChevronRight className="w-4 h-4" /></Button>
        </div>
      </div>

      {!data ? <div className="text-sm text-slate-500">Yükleniyor...</div> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="report-metrics">
            {METRICS.map((m) => (
              <Card key={m.key} className="border-slate-200 shadow-sm"><CardContent className="p-4">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{m.label}</div>
                <div className="text-lg font-extrabold text-slate-900" data-testid={`report-${m.key}`}>{m.money === false ? data.current[m.key] : formatTRY(data.current[m.key])}</div>
                <div className="text-[11px] text-slate-400">Önceki ay: {m.money === false ? data.previous[m.key] : formatTRY(data.previous[m.key])}</div>
                <Delta cur={data.current[m.key]} prev={data.previous[m.key]} money={m.money !== false} />
              </CardContent></Card>
            ))}
          </div>
          <p className="text-[11px] text-slate-500">
            Tahsilat = peşin satışlar ({formatTRY(data.current.collections_cash_sales)}) + cariden gelen ödemeler ({formatTRY(data.current.collections_cari_payments)}). Veresiye satışlar: {formatTRY(data.current.sales_by_payment.veresiye)}.
          </p>

          <Card className="border-slate-200 shadow-sm"><CardContent className="p-4">
            <Tabs defaultValue="sales">
              <TabsList className="flex-wrap h-auto">
                <TabsTrigger value="sales" data-testid="report-tab-sales">Satışlar ({data.sales.length})</TabsTrigger>
                <TabsTrigger value="collections" data-testid="report-tab-collections">Cari Tahsilatlar ({data.cari_payments.length})</TabsTrigger>
                <TabsTrigger value="incomes" data-testid="report-tab-incomes">Gelirler ({data.incomes.length})</TabsTrigger>
                <TabsTrigger value="expenses" data-testid="report-tab-expenses">Giderler ({data.expenses.length})</TabsTrigger>
                <TabsTrigger value="stock" data-testid="report-tab-stock">Stok Hareketleri ({data.stock_movements.length})</TabsTrigger>
              </TabsList>
              <TabsContent value="sales"><SimpleTable testId="report-sales" rows={data.sales} cols={[
                { h: "Tarih", v: (r) => formatDate(r.date) },
                { h: "Ürünler", v: (r) => r.items.map((i) => `${i.quantity}× ${i.tire_label}`).join(", ") },
                { h: "Cari", v: (r) => (r.cari_id ? <Link className="text-indigo-700 hover:underline" to={`/cariler/${r.cari_id}`}>{r.cari_name}</Link> : "—") },
                { h: "Ödeme", v: (r) => PAY[r.payment_method] || r.payment_method },
                { h: "Tutar", right: true, v: (r) => formatTRY(r.total) },
              ]} /></TabsContent>
              <TabsContent value="collections"><SimpleTable testId="report-collections" rows={data.cari_payments} cols={[
                { h: "Tarih", v: (r) => formatDate(r.date) },
                { h: "Cari", v: (r) => <Link className="text-indigo-700 hover:underline" to={`/cariler/${r.cari_id}`}>{r.cari_name}</Link> },
                { h: "Açıklama", v: (r) => r.description || "—" }, amount,
              ]} /></TabsContent>
              <TabsContent value="incomes"><SimpleTable testId="report-incomes" rows={data.incomes} cols={[
                { h: "Tarih", v: (r) => formatDate(r.date) }, { h: "Açıklama", v: (r) => r.description }, amount,
              ]} /></TabsContent>
              <TabsContent value="expenses"><SimpleTable testId="report-expenses" rows={data.expenses} cols={[
                { h: "Tarih", v: (r) => formatDate(r.date) }, { h: "Açıklama", v: (r) => r.description }, amount,
              ]} /></TabsContent>
              <TabsContent value="stock"><SimpleTable testId="report-stock" rows={data.stock_movements} cols={[
                { h: "Tarih", v: (r) => formatDate(r.date) },
                { h: "Ürün", v: (r) => <Link className="text-indigo-700 hover:underline" to={`/stok?tire=${r.tire_id}`}>{r.tire_label}</Link> },
                { h: "Tür", v: (r) => REASON[r.reason] || r.reason },
                { h: "Değişim", right: true, v: (r) => <span className={r.delta >= 0 ? "text-emerald-700" : "text-rose-700"}>{r.delta > 0 ? "+" : ""}{r.delta}</span> },
                { h: "Sonra", right: true, v: (r) => r.after },
              ]} /></TabsContent>
            </Tabs>
          </CardContent></Card>
        </>
      )}
    </div>
  );
}
