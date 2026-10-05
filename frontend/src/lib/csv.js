/**
 * Simple CSV export utility (RFC 4180). UTF-8 BOM so Excel opens Turkish chars correctly.
 */
function escapeCell(v) {
  if (v === null || v === undefined) return "";
  const s = String(v);
  if (/[",\n;]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function downloadCSV({ filename, headers, rows }) {
  const lines = [headers.map(escapeCell).join(";")];
  for (const r of rows) {
    lines.push(headers.map((h, i) => escapeCell(r[i] ?? r[h] ?? "")).join(";"));
  }
  const csv = "\uFEFF" + lines.join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
