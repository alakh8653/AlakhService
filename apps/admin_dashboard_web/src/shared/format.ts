/**
 * Display formats for the dashboard. Staff work in India, so dates and times are always shown in IST
 * (whatever the browser's zone) and money and counts use Indian digit grouping (₹1,23,456.00).
 */

const IST = 'Asia/Kolkata';

const dateFmt = new Intl.DateTimeFormat('en-IN', { timeZone: IST, day: 'numeric', month: 'short', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});
const dateTimeSecondsFmt = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  second: '2-digit',
  hour12: true,
});
const timeFmt = new Intl.DateTimeFormat('en-IN', { timeZone: IST, hour: 'numeric', minute: '2-digit', hour12: true });

function parse(value: string | Date): Date | null {
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "17 Oct 2026" (IST). */
export function formatDate(value: string | Date): string {
  const d = parse(value);
  return d ? dateFmt.format(d) : '—';
}

/** "17 Oct 2026, 11:02 am IST". */
export function formatDateTime(value: string | Date, { seconds = false } = {}): string {
  const d = parse(value);
  return d ? `${(seconds ? dateTimeSecondsFmt : dateTimeFmt).format(d)} IST` : '—';
}

/** "11:02 am IST". */
export function formatTime(value: string | Date): string {
  const d = parse(value);
  return d ? `${timeFmt.format(d)} IST` : '—';
}

/** "₹1,23,456.00" for INR; other currencies get their own symbol. */
export function formatMoney(amount: number, currency = 'INR'): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(amount);
}

/** "₹1.2L", "₹3.4Cr", "₹950" - short labels for chart axes. */
export function formatMoneyCompact(amount: number, currency = 'INR'): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, notation: 'compact', maximumFractionDigits: 1 }).format(
    amount,
  );
}

/** "1,23,456" (Indian grouping). */
export function formatNumber(value: number, maximumFractionDigits = 2): string {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits }).format(value);
}

/** A shortened id for display ("3820d121…"); the full id belongs in a title/tooltip. */
export function shortId(id: string, length = 8): string {
  return id.length > length + 1 ? `${id.slice(0, length)}…` : id;
}
