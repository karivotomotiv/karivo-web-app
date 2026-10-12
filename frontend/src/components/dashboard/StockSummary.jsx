import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api, extractError } from "@/lib/api";
import { Package, Settings2, Mail } from "lucide-react";
import { toast } from "sonner";

const Mini = ({ label, value, testId, tone = "text-slate-900" }) => (
  <div className="rounded-xl bg-slate-50 px-3 py-2.5">
    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
    <div className={`text-lg font-extrabold ${tone}`} data-testid={testId}>{value}</div>
  </div>
);

const TireRow = ({ t, out, onClick }) => (
  <button onClick={onClick} className="w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 text-left transition-colors" data-testid={`stock-item-${t.id}`}>
    <div className="min-w-0">
      <div className="text-sm font-semibold text-slate-900 truncate">{t.product_type === "diger" ? t.name : `${t.brand} ${t.model}`}</div>
      <div className="text-xs text-slate-500">{t.product_type === "diger" ? t.category || "Diğer" : t.size}</div>
    </div>
    <Badge variant="outline" className={out ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-amber-50 text-amber-800 border-amber-200"}>
      {out ? "Tükendi" : `${t.quantity} ${t.unit || "adet"}`}
    </Badge>
  </button>
);

const ThresholdEditor = ({ value, onSaved }) => {
  const [v, setV] = useState(value);
  const save = async () => {
    try { await api.put("/settings/stock", { critical_threshold: Number(v) }); toast.success("Kritik eşik güncellendi"); onSaved(); }
    catch (e) { toast.error(extractError(e)); }
  };
  return (
    <Popover onOpenChange={(o) => o && setV(value)}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-slate-500" data-testid="stock-threshold-btn">
          <Settings2 className="w-3.5 h-3.5 mr-1" /> Eşik: {value}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-60" align="end">
        <div className="text-xs text-slate-600 mb-2">Adedi bu sayıya eşit veya altında olan lastikler kritik sayılır.</div>
        <div className="flex gap-2">
          <Input type="number" min="0" value={v} onChange={(e) => setV(e.target.value)} className="h-9" data-testid="stock-threshold-input" />
          <Button size="sm" onClick={save} disabled={v === "" || Number(v) < 0} data-testid="stock-threshold-save">Kaydet</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
};

export const StockSummary = ({ s, onChanged }) => {
  const navigate = useNavigate();
  const [sending, setSending] = useState(false);
  const go = (id) => navigate(`/stok?tire=${id}`);
  const sendEmail = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/inventory/send-low-stock-email");
      if (data.sent.length) toast.success(`${data.sent.length} alıcıya uyarı gönderildi`);
      if (data.failed?.length) toast.error(`${data.failed.length} alıcıya gönderilemedi: ${data.failed[0]?.error || ""}`);
    } catch (e) { toast.error(extractError(e)); } finally { setSending(false); }
  };
  const empty = s.critical_count + s.out_of_stock_count === 0;
  return (
    <Card className="border-slate-200 shadow-sm h-full" data-testid="stock-summary">
      <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2"><Package className="w-4 h-4" /> Stok Durumu</CardTitle>
          <p className="text-[11px] text-slate-500 mt-0.5">Anlık durum (bugün itibarıyla)</p>
        </div>
        <ThresholdEditor value={s.threshold} onSaved={onChanged} />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-2">
          <Mini label="Ürün Çeşidi" value={s.product_count} testId="stock-product-count" />
          <Mini label="Toplam Adet" value={s.total_qty} testId="stock-total-qty" />
          <Mini label="Kritik" value={s.critical_count + s.out_of_stock_count} testId="stock-critical-count" tone={empty ? "text-emerald-700" : "text-rose-700"} />
        </div>
        {empty ? (
          <div className="text-sm text-slate-500 text-center py-6" data-testid="stock-empty">Kritik seviyede ürün bulunamadı.</div>
        ) : (
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {s.out_of_stock_count > 0 && (
              <div data-testid="stock-out-list">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-700 px-3 mb-1">Stokta Yok ({s.out_of_stock_count})</div>
                {s.out_of_stock.map((t) => <TireRow key={t.id} t={t} out onClick={() => go(t.id)} />)}
              </div>
            )}
            {s.critical_count > 0 && (
              <div data-testid="stock-critical-list">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-700 px-3 mb-1">Kritik Seviye — ≤ {s.threshold} adet ({s.critical_count})</div>
                {s.critical.map((t) => <TireRow key={t.id} t={t} onClick={() => go(t.id)} />)}
              </div>
            )}
          </div>
        )}
        {!empty && (
          <Button size="sm" variant="outline" onClick={sendEmail} disabled={sending} className="w-full" data-testid="low-stock-email-btn">
            <Mail className="w-4 h-4 mr-2" /> {sending ? "Gönderiliyor..." : "Uyarı E-postası Gönder"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
};
