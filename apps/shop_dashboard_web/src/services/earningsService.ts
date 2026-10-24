import apiClient from './apiClient';

// What the shop earned on completed bookings after the platform's commission, and what has been paid
// out (payment_service). Amounts are rupees with two decimals, as the API sends them.

export type PayoutItemStatus = 'HELD' | 'READY' | 'PAID' | 'REFUNDED';

export interface EarningItem {
  bookingId: string;
  paymentId: string;
  completedAt: string | null;
  gross: number;
  commission: number;
  gstOnCommission: number;
  net: number;
  payoutStatus: PayoutItemStatus;
}

export interface Earnings {
  currency: string;
  gross: number;
  commission: number;
  gstOnCommission: number;
  net: number;
  pendingPayout: number;
  paidOut: number;
  items: EarningItem[];
}

export interface Payout {
  id: string;
  periodFrom: string;
  periodTo: string;
  amount: number;
  status: 'PENDING' | 'PAID';
  paidAt: string | null;
  reference: string | null;
}

interface EarningsRecord {
  currency?: string;
  gross: number;
  commission: number;
  gst_on_commission: number;
  net: number;
  pending_payout: number;
  paid_out: number;
  items?: {
    booking_id: string;
    payment_id: string;
    completed_at: string | null;
    gross: number;
    commission: number;
    gst_on_commission: number;
    net: number;
    payout_status: PayoutItemStatus;
  }[];
}

interface PayoutRecord {
  id: string;
  period_from: string;
  period_to: string;
  amount: number;
  status: 'PENDING' | 'PAID';
  paid_at: string | null;
  reference: string | null;
}

const num = (v: unknown) => (typeof v === 'number' ? v : Number(v ?? 0) || 0);

export async function getEarnings(shopId: string, from: string, to: string): Promise<Earnings> {
  const { data } = await apiClient.get<EarningsRecord>(`/payments/shops/${encodeURIComponent(shopId)}/earnings`, {
    params: { from, to },
  });
  return {
    currency: data.currency ?? 'INR',
    gross: num(data.gross),
    commission: num(data.commission),
    gstOnCommission: num(data.gst_on_commission),
    net: num(data.net),
    pendingPayout: num(data.pending_payout),
    paidOut: num(data.paid_out),
    items: (data.items ?? []).map((i) => ({
      bookingId: i.booking_id,
      paymentId: i.payment_id,
      completedAt: i.completed_at,
      gross: num(i.gross),
      commission: num(i.commission),
      gstOnCommission: num(i.gst_on_commission),
      net: num(i.net),
      payoutStatus: i.payout_status,
    })),
  };
}

export async function getPayouts(shopId: string): Promise<Payout[]> {
  const { data } = await apiClient.get<PayoutRecord[]>(`/payments/shops/${encodeURIComponent(shopId)}/payouts`);
  return data.map((p) => ({
    id: p.id,
    periodFrom: p.period_from,
    periodTo: p.period_to,
    amount: num(p.amount),
    status: p.status,
    paidAt: p.paid_at,
    reference: p.reference,
  }));
}

const rupees = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "₹1,23,456.50" from an amount in rupees. */
export const formatRupees = (amount: number) => rupees.format(amount);
