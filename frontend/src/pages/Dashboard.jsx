import { useEffect, useState } from "react";
import { api, formatTRY } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, TrendingDown, FileText, Receipt, Package, ListChecks, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

const Stat = ({ label, value, Icon, tint, to, testId }) => (
  <Link to={to} data-testid={testId}>
    <Card className="hover:-translate-y-0.5 transition-transform duration-150 cursor-pointer border-slate-200 shadow-sm">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</div>
            <div className="mt-2 text-2xl font-extrabold tracking-tight text-slate-900">{value}</div>
          </div>
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${tint}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-4 inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-900">
          Detay <ArrowUpRight className="w-3 h-3 ml-1" />
        </div>
      </CardContent>
    </Card>
  </Link>
);

export default function Dashboard() {
  const [data, setData] = useState({ total_income: 0, total_expense: 0, total_invoices: 0, total_vat: 0, open_todos: 0 });
  const [inv, setInv] = useState([]);

  useEffect(() => {
    api.get("/summary").then((r) => setData(r.data));
    api.get("/inventory").then((r) => setInv(r.data));
  }, []);

  const lowStock = inv.filter((i) => Number(i.remaining_qty) > 0).slice(0, 5);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Özet</h2>
        <p className="text-sm text-slate-600 mt-1">Tüm finansal verilerinize ve stok durumunuza hızlı bir bakış.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" data-testid="dashboard-stats">
        <Stat label="Toplam Gelir" value={formatTRY(data.total_income)} Icon={TrendingUp} tint="bg-emerald-100 text-emerald-700" to="/gelirler" testId="stat-income" />
        <Stat label="Toplam Gider" value={formatTRY(data.total_expense)} Icon={TrendingDown} tint="bg-rose-100 text-rose-700" to="/giderler" testId="stat-expense" />
        <Stat label="Toplam Fatura" value={formatTRY(data.total_invoices)} Icon={FileText} tint="bg-indigo-100 text-indigo-700" to="/faturalar" testId="stat-invoice" />
        <Stat label="Toplam KDV" value={formatTRY(data.total_vat)} Icon={Receipt} tint="bg-amber-100 text-amber-700" to="/faturalar" testId="stat-vat" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Net Durum</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-slate-900" data-testid="dashboard-net">
              {formatTRY(Number(data.total_income) - Number(data.total_expense))}
            </div>
            <p className="text-sm text-slate-600 mt-2">Toplam gelir − toplam gider</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Açık Görevler</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center"><ListChecks className="w-5 h-5" /></div>
              <div>
                <div className="text-3xl font-extrabold text-slate-900" data-testid="dashboard-open-todos">{data.open_todos}</div>
                <Link to="/yapilacaklar" className="text-xs text-teal-700 hover:underline">Görevleri yönet</Link>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Stok Kayıt</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center"><Package className="w-5 h-5" /></div>
              <div>
                <div className="text-3xl font-extrabold text-slate-900">{inv.length}</div>
                <Link to="/stok" className="text-xs text-slate-600 hover:underline">Stoğu görüntüle</Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {lowStock.length > 0 && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-900">Kalan İhtiyaç Olan Ürünler</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-slate-100">
              {lowStock.map((p) => (
                <li key={p.id} className="py-3 flex items-center justify-between">
                  <span className="text-sm text-slate-800 font-medium">{p.product_name}</span>
                  <span className="text-sm font-semibold text-rose-600">Kalan: {p.remaining_qty}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
