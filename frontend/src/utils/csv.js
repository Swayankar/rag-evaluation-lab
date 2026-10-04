const escapeCell = (value) => {
  if (value === null || value === undefined) return "";
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function toCsv(rows, columns) {
  const header = columns.map(escapeCell).join(",");
  const lines = rows.map((row) =>
    columns.map((c) => escapeCell(row[c])).join(","),
  );
  return [header, ...lines].join("\r\n");
}

export function downloadCsv(filename, rows, columns) {
  const blob = new Blob(["﻿" + toCsv(rows, columns)], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
