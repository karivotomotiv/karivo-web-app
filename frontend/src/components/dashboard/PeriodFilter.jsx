import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/api";
import { CalendarRange } from "lucide-react";

const PRESETS = [
  { value: "this_month", label: "Bu Ay" },
  { value: "last_month", label: "Geçen Ay" },
  { value: "custom", label: "Özel Aralık" },
];

export const PeriodFilter = ({ preset, onPreset, range, onRange }) => (
  <div className="flex flex-wrap items-center gap-2" data-testid="period-filter">
    <div className="inline-flex rounded-xl bg-slate-100 p-1">
      {PRESETS.map((p) => (
        <button
          key={p.value}
          onClick={() => onPreset(p.value)}
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
            preset === p.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-900"
          }`}
          data-testid={`period-${p.value}`}
        >
          {p.label}
        </button>
      ))}
    </div>
    {preset === "custom" ? (
      <div className="flex items-center gap-2">
        <Input type="date" value={range.start} max={range.end} onChange={(e) => e.target.value && onRange({ ...range, start: e.target.value })} className="h-9 w-[150px]" data-testid="period-start" />
        <span className="text-slate-400">—</span>
        <Input type="date" value={range.end} min={range.start} onChange={(e) => e.target.value && onRange({ ...range, end: e.target.value })} className="h-9 w-[150px]" data-testid="period-end" />
      </div>
    ) : (
      <span className="inline-flex items-center gap-1.5 text-xs text-slate-500" data-testid="period-label">
        <CalendarRange className="w-3.5 h-3.5" /> {formatDate(range.start)} – {formatDate(range.end)}
      </span>
    )}
  </div>
);
