import { formatTRY } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2, Phone, ChevronRight } from "lucide-react";

export const CariMobileList = ({ items, emptyText, onOpen, onEdit, onDelete, totalNet }) => (
  <div className="md:hidden divide-y divide-slate-100" data-testid="cari-mobile-list">
    {items.length === 0 && <div className="text-center text-slate-500 py-10 px-4 text-sm">{emptyText}</div>}
    {items.map((it) => {
      const net = Number(it.net || 0);
      return (
        <div key={it.id} className="p-4 flex items-center gap-3" data-testid={`cari-card-${it.id}`}>
          <button type="button" className="flex-1 min-w-0 text-left" onClick={() => onOpen(it)} data-testid={`cari-card-open-${it.id}`}>
            <div className="flex items-center gap-1 font-semibold text-slate-900 truncate">
              {it.name} <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />
            </div>
            {it.phone && <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5"><Phone className="w-3 h-3" />{it.phone}</div>}
            <div className={`text-base font-extrabold mt-1 ${net >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{formatTRY(net)}</div>
            <div className="text-[11px] text-slate-500">{net > 0.005 ? "Cari bize borçlu" : net < -0.005 ? "Biz borçluyuz" : "Hesap kapalı"} · {it.tx_count} hareket</div>
          </button>
          <Button variant="outline" size="icon" className="h-11 w-11 shrink-0" onClick={() => onEdit(it)} data-testid={`cari-card-edit-${it.id}`}>
            <Pencil className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" className="h-11 w-11 shrink-0 text-rose-600 border-rose-200" onClick={() => onDelete(it)} data-testid={`cari-card-delete-${it.id}`}>
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      );
    })}
    {items.length > 0 && (
      <div className="p-4 bg-slate-50 flex justify-between text-sm font-bold">
        <span className="uppercase text-xs tracking-wider text-slate-600">Genel Net</span>
        <span className={totalNet >= 0 ? "text-emerald-700" : "text-rose-700"} data-testid="cari-mobile-total-net">{formatTRY(totalNet)}</span>
      </div>
    )}
  </div>
);
