import { useMemo } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

const TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

export function monthLabelFromKey(key) {
  if (!key || key === "all") return "Tüm Zamanlar";
  const [y, m] = key.split("-");
  return `${TR_MONTHS[Number(m) - 1]} ${y}`;
}

/**
 * Groups records by YYYY-MM; returns sorted keys desc and a count per month.
 */
export function groupByMonth(items, dateKey = "date") {
  const map = new Map();
  for (const it of items) {
    const d = it[dateKey] || "";
    const key = d.slice(0, 7);
    if (!key) continue;
    map.set(key, (map.get(key) || 0) + 1);
  }
  return Array.from(map.entries())
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([key, count]) => ({ key, count, label: monthLabelFromKey(key) }));
}

/**
 * Filter bar with month selector + text search.
 * Props: items (array), onChange(filteredItems), search, setSearch, month, setMonth, dateKey, searchKeys, testIdPrefix.
 */
export default function FilterBar({
  items,
  month, setMonth,
  search, setSearch,
  dateKey = "date",
  searchKeys = ["description"],
  testIdPrefix = "list",
  placeholder = "Açıklamada ara...",
}) {
  const monthOptions = useMemo(() => groupByMonth(items, dateKey), [items, dateKey]);

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="relative flex-1 min-w-[200px] max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <Input
          type="text"
          placeholder={placeholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
          data-testid={`${testIdPrefix}-search`}
        />
      </div>
      <Select value={month || "all"} onValueChange={setMonth}>
        <SelectTrigger className="w-56" data-testid={`${testIdPrefix}-month-filter`}>
          <SelectValue placeholder="Ay seçin" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Tüm Zamanlar ({items.length})</SelectItem>
          {monthOptions.map((o) => (
            <SelectItem key={o.key} value={o.key}>
              {o.label} ({o.count})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/**
 * Filter helper: returns items matching month (YYYY-MM) and search terms (across searchKeys).
 */
export function applyFilter(items, { month, search, dateKey = "date", searchKeys = ["description"] }) {
  const s = (search || "").trim().toLowerCase();
  return items.filter((it) => {
    if (month && month !== "all") {
      const d = (it[dateKey] || "").slice(0, 7);
      if (d !== month) return false;
    }
    if (s) {
      const hay = searchKeys.map((k) => String(it[k] ?? "")).join(" ").toLowerCase();
      if (!hay.includes(s)) return false;
    }
    return true;
  });
}
