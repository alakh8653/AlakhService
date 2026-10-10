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

export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(amount);
}
