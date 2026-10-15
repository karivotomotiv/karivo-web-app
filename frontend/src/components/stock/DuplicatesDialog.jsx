import { useEffect, useState } from "react";
import { api, formatTRY, extractError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertTriangle, Crown, GitMerge, Loader2, Pencil } from "lucide-react";
import { toast } from "sonner";
import { askConfirm } from "@/components/ConfirmHost";

const priceKey = (r) => `${r.buy_price}|${r.sell_price}|${r.kdv_rate}`;
const defaultTarget = (g) => [...g].sort((a, b) => b.sale_count - a.sale_count || b.quantity - a.quantity || a.created_at.localeCompare(b.created_at))[0].id;

const GroupCard = ({ group, kind, idx, onMerged, onEditTarget }) => {
  const [target, setTarget] = useState(defaultTarget(group));
  const [selected, setSelected] = useState(() => new Set(kind === "exact" ? group.map((r) => r.id) : []));
  const [busy, setBusy] = useState(false);
  const t = group.find((r) => r.id === target);
  const sources = group.filter((r) => r.id !== target && selected.has(r.id));
  const priceDiff = sources.some((r) => priceKey(r) !== priceKey(t));
  const total = sources.reduce((s, r) => s + Number(r.quantity), Number(t.quantity));

  const toggle = (id) => setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const merge = async () => {
    if (!(await askConfirm(`${sources.length} ürün "${t.label}" içine birleştirilecek. Toplam adet ${total} olacak ve diğer kayıtlar silinecek. Onaylıyor musunuz?`))) return;
    setBusy(true);
    try {
      await api.post("/tires/merge", { target_id: target, source_ids: sources.map((r) => r.id) });
      toast.success(`Birleştirildi: ${t.label} — ${total} ${t.unit || "adet"}`);
      onMerged();
    } catch (e) { toast.error(extractError(e)); } finally { setBusy(false); }
  };

  return (
    <div className="rounded-xl border border-slate-200 p-3 space-y-2" data-testid={`dup-group-${kind}-${idx}`}>
      {group.map((r) => {
        const isTarget = r.id === target;
        return (
          <div key={r.id} className={`flex items-center gap-3 rounded-lg px-2 py-1.5 ${isTarget ? "bg-amber-50" : ""}`} data-testid={`dup-row-${r.id}`}>
            <Checkbox checked={isTarget || selected.has(r.id)} disabled={isTarget} onCheckedChange={() => toggle(r.id)} data-testid={`dup-check-${r.id}`} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-slate-900 truncate">{r.label}{r.dot ? ` · DOT ${r.dot}` : ""}</div>
              <div className="text-[11px] text-slate-500">
                {r.quantity} {r.unit || "adet"} · Alış {formatTRY(r.buy_price)} · Satış {formatTRY(r.sell_price)} · {r.sale_count} satış · {r.movement_count} hareket
              </div>
            </div>
            {isTarget ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700" data-testid={`dup-target-badge-${r.id}`}><Crown className="w-3.5 h-3.5" /> Ana ürün</span>
            ) : (
              <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setTarget(r.id)} data-testid={`dup-set-target-${r.id}`}>Ana yap</Button>
            )}
          </div>
        );
      })}
      {priceDiff && (
        <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800" data-testid={`dup-price-warning-${kind}-${idx}`}>
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="flex-1">Fiyatlar farklı. Birleştirmede ana ürünün fiyatı (alış {formatTRY(t.buy_price)}, satış {formatTRY(t.sell_price)}) kalacak.</span>
          <button className="inline-flex items-center gap-1 font-semibold underline shrink-0" onClick={() => onEditTarget(t.id)} data-testid={`dup-edit-target-${kind}-${idx}`}>
            <Pencil className="w-3 h-3" /> Ana ürünü düzenle
          </button>
        </div>
      )}
      <div className="flex items-center justify-between gap-2 pt-1">
        <span className="text-xs text-slate-500">{sources.length ? `Birleşince: ${total} ${t.unit || "adet"}` : "Birleştirilecek ürünleri işaretleyin"}</span>
        <Button size="sm" onClick={merge} disabled={busy || !sources.length} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid={`dup-merge-${kind}-${idx}`}>
          {busy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <GitMerge className="w-4 h-4 mr-1" />} Birleştir
        </Button>
      </div>
    </div>
  );
};

export const DuplicatesDialog = ({ open, onOpenChange, onChanged, onEditProduct }) => {
  const [data, setData] = useState(null);
  const load = async () => {
    setData(null);
    try { const { data } = await api.get("/tires/duplicates"); setData(data); }
    catch (e) { toast.error(extractError(e)); }
  };
  useEffect(() => { if (open) load(); }, [open]);
  const onMerged = () => { load(); onChanged(); };
  const editTarget = (id) => { onOpenChange(false); onEditProduct(id); };
  const none = data && !data.exact_groups.length && !data.similar_groups.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="duplicates-dialog">
        <DialogHeader>
          <DialogTitle>Mükerrer Ürünler</DialogTitle>
          <DialogDescription>Ana ürünü seçin; işaretli ürünlerin adetleri, stok hareketleri ve satış geçmişi ana ürüne aktarılır, kayıtları silinir.</DialogDescription>
        </DialogHeader>
        {!data ? (
          <div className="py-10 text-center text-sm text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline mr-2" />Taranıyor...</div>
        ) : none ? (
          <div className="py-10 text-center text-sm text-slate-500" data-testid="duplicates-empty">Mükerrer ürün bulunamadı.</div>
        ) : (
          <div className="space-y-5">
            {data.exact_groups.length > 0 && (
              <section className="space-y-2" data-testid="duplicates-exact">
                <h4 className="text-xs font-bold uppercase tracking-wider text-rose-700">Aynı ürün ({data.exact_groups.length} grup)</h4>
                {data.exact_groups.map((g, i) => <GroupCard key={g.map((r) => r.id).join()} group={g} kind="exact" idx={i} onMerged={onMerged} onEditTarget={editTarget} />)}
              </section>
            )}
            {data.similar_groups.length > 0 && (
              <section className="space-y-2" data-testid="duplicates-similar">
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-700">Olası mükerrer ({data.similar_groups.length} grup)</h4>
                <p className="text-[11px] text-slate-500">Bunlar benzer görünüyor; gerçekten aynı ürünse işaretleyip birleştirin.</p>
                {data.similar_groups.map((g, i) => <GroupCard key={g.map((r) => r.id).join()} group={g} kind="similar" idx={i} onMerged={onMerged} onEditTarget={editTarget} />)}
              </section>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
