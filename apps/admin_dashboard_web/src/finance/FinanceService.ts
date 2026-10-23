import adminApiClient from '../apiClient';

/** Escrow state of a payment: funds are HELD until released to the provider or refunded. */
export type SettlementStatus = 'CREATED' | 'HELD' | 'RELEASED' | 'REFUNDED';

export const SETTLEMENT_STATUSES: SettlementStatus[] = ['HELD', 'RELEASED', 'REFUNDED', 'CREATED'];

export interface Settlement {
  id: string;
  paymentId: string;
  bookingId: string;
  payeeId: string;
  /** Major units (e.g. rupees). */
  amount: number;
  currency: string;
  status: SettlementStatus;
  heldAt: string;
  releasedAt: string | null;
}

export interface PaginatedSettlements {
  data: Settlement[];
  total: number;
  page: number;
}

export interface RevenuePoint {
  date: string;
  gross: number;
  refunds: number;
  net: number;
  payments: number;
}

export interface RevenueReport {
  currency: string;
  gross: number;
  refunds: number;
  net: number;
  payments: number;
  series: RevenuePoint[];
}

interface SettlementRecord {
  id: string;
  payment_id: string;
  booking_id: string;
  payee_id: string;
  amount_cents: number;
  currency: string;
  status: SettlementStatus;
  held_at: string;
  released_at: string | null;
}

interface RevenueRecord {
  currency: string;
  gross_cents: number;
  refunds_cents: number;
  net_cents: number;
  payments: number;
  series: { date: string; gross_cents: number; refunds_cents: number; net_cents: number; payments: number }[];
}

const fromCents = (cents: number) => cents / 100;

export async function getSettlements(
  filters: { status?: SettlementStatus; page?: number; perPage?: number } = {},
): Promise<PaginatedSettlements> {
  const { data } = await adminApiClient.get<{ data: SettlementRecord[]; total: number; page: number }>(
    '/admin/finance/settlements',
    { params: { status: filters.status, page: filters.page, per_page: filters.perPage } },
  );
  return {
    data: data.data.map((r) => ({
      id: r.id,
      paymentId: r.payment_id,
      bookingId: r.booking_id,
      payeeId: r.payee_id,
      amount: fromCents(r.amount_cents),
      currency: r.currency,
      status: r.status,
      heldAt: r.held_at,
      releasedAt: r.released_at,
    })),
    total: data.total,
    page: data.page,
  };
}

export async function getRevenueReport(params: { dateFrom?: string; dateTo?: string } = {}): Promise<RevenueReport> {
  const { data } = await adminApiClient.get<RevenueRecord>('/admin/finance/revenue', {
    params: { date_from: params.dateFrom, date_to: params.dateTo },
  });
  return {
    currency: data.currency,
    gross: fromCents(data.gross_cents),
    refunds: fromCents(data.refunds_cents),
    net: fromCents(data.net_cents),
    payments: data.payments,
    series: data.series.map((p) => ({
      date: p.date,
      gross: fromCents(p.gross_cents),
      refunds: fromCents(p.refunds_cents),
      net: fromCents(p.net_cents),
      payments: p.payments,
    })),
  };
}

// ---------------------------------------------------------------- shop payouts and commission

export type PayoutStatus = 'PENDING' | 'PAID';

export interface Payout {
  id: string;
  batchId: string;
  shopId: string;
  periodFrom: string | null;
  periodTo: string;
  /** Rupees. */
  amount: number;
  currency: string;
  status: PayoutStatus;
  paidAt: string | null;
  reference: string | null;
  createdAt: string;
}

interface PayoutRecord {
  id: string;
  batch_id: string;
  shop_id: string;
  period_from: string | null;
  period_to: string;
  amount_cents: number;
  currency: string;
  status: PayoutStatus;
  paid_at: string | null;
  reference: string | null;
  created_at: string;
}

const toPayout = (r: PayoutRecord): Payout => ({
  id: r.id,
  batchId: r.batch_id,
  shopId: r.shop_id,
  periodFrom: r.period_from,
  periodTo: r.period_to,
  amount: fromCents(r.amount_cents),
  currency: r.currency,
  status: r.status,
  paidAt: r.paid_at,
  reference: r.reference,
  createdAt: r.created_at,
});

export async function getPayouts(
  filters: { status?: PayoutStatus; batchId?: string; page?: number; perPage?: number } = {},
): Promise<{ data: Payout[]; total: number; page: number }> {
  const { data } = await adminApiClient.get<{ data: PayoutRecord[]; total: number; page: number }>('/admin/payments/payouts', {
    params: { status: filters.status, batch_id: filters.batchId, page: filters.page, per_page: filters.perPage },
  });
  return { data: data.data.map(toPayout), total: data.total, page: data.page };
}

/** One PENDING payout per shop owed money for bookings completed up to [periodTo] (YYYY-MM-DD). */
export async function createPayoutBatch(periodTo?: string): Promise<{ batchId: string; payouts: Payout[]; total: number }> {
  const { data } = await adminApiClient.post<{ batch_id: string; payouts: PayoutRecord[]; total_amount_cents: number }>(
    '/admin/payments/payouts/batches',
    periodTo ? { period_to: periodTo } : {},
  );
  return { batchId: data.batch_id, payouts: data.payouts.map(toPayout), total: fromCents(data.total_amount_cents) };
}

export async function markPayoutPaid(id: string, reference: string): Promise<Payout> {
  const { data } = await adminApiClient.post<PayoutRecord>(`/admin/payments/payouts/${id}/mark-paid`, { reference });
  return toPayout(data);
}

/** The bank upload file for pending payouts (or one batch). Fetched directly: the API client only takes JSON. */
export async function downloadPayoutsCsv(batchId?: string): Promise<Blob> {
  const base = String(adminApiClient.defaults?.baseURL ?? '').replace(/\/$/, '');
  const query = new URLSearchParams(batchId ? { batch_id: batchId } : { status: 'PENDING' });
  const token = localStorage.getItem('admin_token');
  const resp = await fetch(`${base}/admin/payments/payouts/export.csv?${query.toString()}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
  return resp.blob();
}

export interface CommissionSettings {
  defaultPercent: number;
  configuredDefaultPercent: number;
  gstPercent: number;
  overrides: { shopId: string; percent: number; updatedAt: string | null }[];
}

export async function getCommission(): Promise<CommissionSettings> {
  const { data } = await adminApiClient.get<{
    default_commission_percent: number;
    configured_default_percent: number;
    gst_on_commission_percent: number;
    overrides: { shop_id: string; commission_percent: number; updated_at: string | null }[];
  }>('/admin/payments/commission');
  return {
    defaultPercent: data.default_commission_percent,
    configuredDefaultPercent: data.configured_default_percent,
    gstPercent: data.gst_on_commission_percent,
    overrides: data.overrides.map((o) => ({ shopId: o.shop_id, percent: o.commission_percent, updatedAt: o.updated_at })),
  };
}

/** Sets a shop's own commission rate; null removes it so the default applies again. */
export async function setShopCommission(shopId: string, percent: number | null): Promise<void> {
  await adminApiClient.put(`/admin/payments/commission/${encodeURIComponent(shopId)}`, { commission_percent: percent });
}

/** Sets the default rate for shops without their own; null goes back to the configured one. */
export async function setDefaultCommission(percent: number | null): Promise<void> {
  await adminApiClient.put('/admin/payments/commission', { commission_percent: percent });
}

export { formatMoney } from '../shared/format';
