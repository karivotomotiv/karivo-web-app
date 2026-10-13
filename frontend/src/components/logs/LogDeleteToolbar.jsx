import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, CalendarX, ListX } from "lucide-react";

const dayStart = (d) => new Date(`${d}T00:00:00`).toISOString();
const nextDayStart = (d) => { const x = new Date(`${d}T00:00:00`); x.setDate(x.getDate() + 1); return x.toISOString(); };

export const LogDeleteToolbar = ({ selectedCount, selectedIds, onRequest }) => {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const requestRange = () => {
    const label = `${start || "en eski"} – ${end || "bugün"}`;
    onRequest(
      { mode: "range", start: start ? dayStart(start) : null, end: end ? nextDayStart(end) : null },
      "Tarih aralığındaki kayıtlar silinsin mi?",
      `${label} arasındaki tüm işlem günlüğü kayıtları kalıcı olarak silinecek.`,
    );
  };

  return (
    <div className="flex flex-col lg:flex-row lg:items-end gap-3 pt-4 mt-4 border-t border-slate-100" data-testid="log-delete-toolbar">
      <div className="flex items-end gap-2 flex-wrap">
        <div>
          <div className="text-xs text-slate-500 mb-1">Başlangıç</div>
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="w-40" data-testid="log-range-start" />
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-1">Bitiş</div>
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="w-40" data-testid="log-range-end" />
        </div>
        <Button variant="outline" disabled={!start && !end} onClick={requestRange} data-testid="log-delete-range-btn">
          <CalendarX className="w-4 h-4 mr-2" /> Aralığı Sil
        </Button>
      </div>
      <div className="flex gap-2 lg:ml-auto">
        <Button
          variant="outline"
          disabled={selectedCount === 0}
          onClick={() => onRequest({ mode: "ids", ids: selectedIds }, "Seçilen kayıtlar silinsin mi?", `${selectedCount} kayıt kalıcı olarak silinecek.`)}
          data-testid="log-delete-selected-btn"
        >
          <ListX className="w-4 h-4 mr-2" /> Seçilenleri Sil ({selectedCount})
        </Button>
        <Button
          variant="destructive"
          onClick={() => onRequest({ mode: "all" }, "Tüm işlem günlüğü silinsin mi?", "Bütün kayıtlar kalıcı olarak silinecek. Bu işlem geri alınamaz.")}
          data-testid="log-delete-all-btn"
        >
          <Trash2 className="w-4 h-4 mr-2" /> Tümünü Sil
        </Button>
      </div>
    </div>
  );
};
