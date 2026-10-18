/** The API's error message (`detail`) for a failed request, or [fallback] when it sent none. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } } | null)?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors: [{ msg: "..." }, ...]
  if (Array.isArray(detail) && typeof (detail[0] as { msg?: unknown } | undefined)?.msg === 'string') {
    return (detail[0] as { msg: string }).msg;
  }
  return fallback;
}
