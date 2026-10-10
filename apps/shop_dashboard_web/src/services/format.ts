const CURRENCY = 'INR';

const moneyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: CURRENCY,
  maximumFractionDigits: 2,
});

/** Formats an amount in minor units (paise) as rupees. */
export function formatMoney(minorUnits: number): string {
  return moneyFormatter.format(minorUnits / 100);
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
