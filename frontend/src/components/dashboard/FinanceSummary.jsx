import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { formatTRY } from "@/lib/api";
import { TrendingUp, TrendingDown, Scale, ShoppingCart, HandCoins, ArrowUpRight } from "lucide-react";

const Kpi = ({ label, value, sub, Icon, tint, to, testId, valueClass = "text-slate-900" }) => (
  <Link to={to} data-testid={testId} className="group">
    <Card className="h-full border-slate-200 shadow-sm group-hover:-translate-y-0.5 group-hover:shadow-md transition-[transform,box-shadow] duration-150">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
            <div className={`mt-1.5 text-xl sm:text-2xl font-extrabold tracking-tight truncate ${valueClass}`} data-testid={`${testId}-value`}>{value}</div>
          </div>
          <div className={`w-10 h-10 shrink-0 rounded-xl flex items-center justify-center ${tint}`}><Icon className="w-5 h-5" /></div>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span className="truncate">{sub}</span>
          <ArrowUpRight className="w-3.5 h-3.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </CardContent>
    </Card>
  </Link>
);

export const FinanceSummary = ({ f }) => {
  const diff = f.income_expense_diff;
  return (
    <div className="space-y-3" data-testid="finance-summary">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Kpi label="Toplam Gelir" value={formatTRY(f.income_total)} sub={`${f.income_count} gelir kaydı`} Icon={TrendingUp} tint="bg-emerald-100 text-emerald-700" to="/gelir-gider" testId="kpi-income" />
        <Kpi label="Toplam Gider" value={formatTRY(f.expense_total)} sub={`${f.expense_count} gider kaydı`} Icon={TrendingDown} tint="bg-rose-100 text-rose-700" to="/gelir-gider" testId="kpi-expense" />
        <Kpi label="Gelir − Gider Farkı" value={formatTRY(diff)} sub="Kâr değildir; kayıtlı gelir eksi gider" Icon={Scale} tint="bg-slate-100 text-slate-700" to="/gelir-gider" testId="kpi-diff" valueClass={diff < 0 ? "text-rose-700" : "text-slate-900"} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Kpi label="Satış Cirosu" value={formatTRY(f.sales_revenue)} sub={`${f.sales_count} satış · ${f.sales_tire_qty} lastik · veresiye ${formatTRY(f.sales_by_payment.veresiye)}`} Icon={ShoppingCart} tint="bg-indigo-100 text-indigo-700" to="/satislar" testId="kpi-sales" />
        <Kpi label="Tahsilat" value={formatTRY(f.collections_total)} sub={`Peşin satış ${formatTRY(f.collections_cash_sales)} · Cari ödeme ${formatTRY(f.collections_cari_payments)}`} Icon={HandCoins} tint="bg-teal-100 text-teal-700" to="/cariler" testId="kpi-collections" />
      </div>
      <p className="text-[11px] text-slate-500 leading-relaxed" data-testid="finance-note">
        Gelir/gider yalnızca Gelir/Giderler sayfasındaki kayıtlardır. Satış cirosu iptal edilmemiş satışların toplamıdır; veresiye satış tahsil edilene kadar tahsilata girmez.
        {f.company_spending_count > 0 && ` Şirket harcamaları (${formatTRY(f.company_spending_total)}) gidere dahil değildir.`}
      </p>
    </div>
  );
};
