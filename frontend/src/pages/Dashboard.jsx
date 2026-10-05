import { useEffect, useState } from "react";
import { api, formatTRY, extractError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  TrendingUp, TrendingDown, FileText, Receipt, Package, ListChecks, ArrowUpRight,
  AlertTriangle, Mail,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend,
  Line, ComposedChart,
} from "recharts";

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

const monthLabel = (m) => {
  if (!m) return "-";
  const [y, mm] = m.split("-");
  return new Date(Number(y), Number(mm) - 1, 1).toLocaleDateString("tr-TR", { month: "short", year: "2-digit" });
};

export default function Dashboard() {
  const [data, setData] = useState({ total_income: 0, total_expense: 0, total_invoices: 0, total_vat: 0, open_todos: 0 });
  const [trend, setTrend] = useState([]);
  const [alerts, setAlerts] = useState({ count: 0, items: [] });
  const [sending, setSending] = useState(false);

  const loadAll = async () => {
    try {
      const [s, t, a] = await Promise.all([
        api.get("/summary"),
        api.get("/dashboard/monthly-trend"),
        api.get("/inventory/alerts"),
      ]);
      setData(s.data);
      setTrend(t.data.map((r) => ({ ...r, label: monthLabel(r.month) })));
      setAlerts(a.data);
    } catch (e) {
      toast.error(extractError(e));
    }
  };
  useEffect(() => { loadAll(); }, []);

  const sendLowStockEmail = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/inventory/send-low-stock-email");
      toast.success(`${data.sent.length} alıcıya uyarı gönderildi (${data.low_stock_count} ürün)`);
      if (data.failed?.length) toast.warning(`${data.failed.length} alıcıya gönderilemedi`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSending(false);
    }
  };

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

      {/* Low stock alert banner */}
      {alerts.count > 0 && (
        <Alert className="border-amber-300 bg-amber-50" data-testid="low-stock-alert">
          <AlertTriangle className="h-4 w-4 text-amber-700" />
          <AlertTitle className="text-amber-900">{alerts.count} ürün için stok eksik</AlertTitle>
          <AlertDescription className="text-amber-800">
            <div className="flex items-center justify-between flex-wrap gap-3 mt-1">
              <div className="text-sm">
                İhtiyaç duyulan ürünler:{" "}
                <strong>{alerts.items.slice(0, 3).map((i) => i.product_name).join(", ")}</strong>
                {alerts.count > 3 && ` ve ${alerts.count - 3} ürün daha`}
              </div>
              <Button
                size="sm"
                onClick={sendLowStockEmail}
                disabled={sending}
                className="bg-amber-700 hover:bg-amber-800 text-white"
                data-testid="low-stock-email-btn"
              >
                <Mail className="w-4 h-4 mr-2" />
                {sending ? "Gönderiliyor..." : "E-posta Gönder"}
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

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
            <CardTitle className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Eksik Stok</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${alerts.count > 0 ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"}`}>
                <Package className="w-5 h-5" />
              </div>
              <div>
                <div className="text-3xl font-extrabold text-slate-900" data-testid="dashboard-low-stock-count">{alerts.count}</div>
                <Link to="/stok" className="text-xs text-slate-600 hover:underline">Stoğu görüntüle</Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Monthly trend chart */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base font-bold text-slate-900">Aylık Trend</CardTitle>
          <p className="text-sm text-slate-500">Gelir, gider ve kâr karşılaştırması (son 12 ay)</p>
        </CardHeader>
        <CardContent>
          <div className="h-80" data-testid="monthly-trend-chart">
            {trend.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                Yeterli veri yok. Gelir ve gider ekledikçe grafik burada görünecek.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={trend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v)} />
                  <Tooltip
                    formatter={(v, name) => [formatTRY(v), name]}
                    contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 13 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="income" name="Gelir" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="expense" name="Gider" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  <Line type="monotone" dataKey="profit" name="Kâr" stroke="#0f172a" strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </CardContent>
      </Card>

      {/* VAT trend */}
      {trend.length > 0 && trend.some((r) => r.vat > 0) && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-900">Aylık KDV Trendi</CardTitle>
            <p className="text-sm text-slate-500">Fatura %20 KDV tutarları</p>
          </CardHeader>
          <CardContent>
            <div className="h-64" data-testid="vat-trend-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v)} />
                  <Tooltip formatter={(v) => formatTRY(v)} contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 13 }} />
                  <Bar dataKey="vat" name="KDV" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
