/** Builds CSV text and hands it to the browser as a download. */

export type CsvValue = string | number | boolean | null | undefined;

/**
 * One CSV cell. Quotes are escaped, and text a spreadsheet would run as a formula (=, +, -, @,
 * tab, CR) is prefixed with an apostrophe: a booking note like =HYPERLINK(...) must stay text when
 * the file is opened in Excel or Sheets. Numbers are written as they are.
 */
export function csvCell(value: CsvValue): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  const text = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(headers: string[], rows: CsvValue[][]): string {
  return [headers, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

/** Saves the CSV; the byte-order mark makes Excel read ₹ and Indian names as UTF-8. */
export function downloadCsv(filename: string, headers: string[], rows: CsvValue[][]): void {
  const blob = new Blob(['﻿' + toCsv(headers, rows)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
