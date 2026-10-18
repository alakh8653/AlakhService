import { format } from 'date-fns';

const CURRENCY = 'INR';

const moneyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: CURRENCY,
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const wholeRupeeFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: CURRENCY,
  maximumFractionDigits: 0,
});

/** Formats an amount in minor units (paise) as rupees, Indian grouping: ₹1,20,000 or ₹499.50. */
export function formatMoney(minorUnits: number): string {
  return minorUnits % 100 === 0 ? wholeRupeeFormatter.format(minorUnits / 100) : moneyFormatter.format(minorUnits / 100);
}

/** Short rupee amount for chart axes: ₹950, ₹4.5K, ₹1.2L, ₹3.4Cr. */
export function formatMoneyShort(minorUnits: number): string {
  const rupees = minorUnits / 100;
  const abs = Math.abs(rupees);
  const trim = (n: number) => String(Number(n.toFixed(1)));
  if (abs >= 1e7) return `₹${trim(rupees / 1e7)}Cr`;
  if (abs >= 1e5) return `₹${trim(rupees / 1e5)}L`;
  if (abs >= 1e3) return `₹${trim(rupees / 1e3)}K`;
  return `₹${Math.round(rupees)}`;
}

const sameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

/** When a booking happens, the way an owner says it: "Today, 10:30 AM", "Tomorrow, 9:00 AM", "Sat 1 Nov 2026, 4:15 PM". */
export function formatWhen(iso: string, now: Date = new Date()): string {
  const at = new Date(iso);
  const time = format(at, 'h:mm a');
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  if (sameDay(at, now)) return `Today, ${time}`;
  if (sameDay(at, tomorrow)) return `Tomorrow, ${time}`;
  if (sameDay(at, yesterday)) return `Yesterday, ${time}`;
  return `${format(at, at.getFullYear() === now.getFullYear() ? 'EEE d MMM' : 'EEE d MMM yyyy')}, ${time}`;
}

/** A date and time without the weekday: "12 Oct, 5:00 PM". */
export function formatDayTime(iso: string): string {
  return format(new Date(iso), 'd MMM, h:mm a');
}

/** "5 min", "2 h 10 min", "1 day 3 h" since a moment. */
export function formatElapsed(iso: string, now: number = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  const days = Math.floor(hours / 24);
  return hours % 24 ? `${days} day${days > 1 ? 's' : ''} ${hours % 24} h` : `${days} day${days > 1 ? 's' : ''}`;
}

/** A clock time in 12-hour format: "4:05 PM". */
export function formatClock(iso: string): string {
  return format(new Date(iso), 'h:mm a');
}

/** Converts a major-unit amount typed by a user (rupees) to minor units. */
export function toMinorUnits(major: number): number {
  return Math.round(major * 100);
}

export function shortId(id: string): string {
  return id.slice(0, 8).toUpperCase();
}

export function humanize(value: string): string {
  const words = value.toLowerCase().replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Best-effort message from an API error (FastAPI `detail` or axios message). */
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    if (first?.msg) return first.msg;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
