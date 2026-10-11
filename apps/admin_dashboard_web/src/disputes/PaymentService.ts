import adminApiClient from '../apiClient';

export interface BookingPayment {
  id: string;
  amountCents: number;
  method: string;
  gateway: string | null;
  status: string;
  createdAt: string;
}

interface PaymentRecord {
  id: string;
  amount_cents: number;
  payment_method: string;
  gateway: string | null;
  status: string;
  created_at: string;
}

export interface RefundResult {
  id: string;
  amountCents: number;
  status: string;
}

/** Payments made for a booking (payment_service). */
export async function getBookingPayments(bookingId: string): Promise<BookingPayment[]> {
  const { data } = await adminApiClient.get<PaymentRecord[]>('/payments', { params: { booking_id: bookingId } });
  return data.map((p) => ({
    id: p.id,
    amountCents: p.amount_cents,
    method: p.payment_method,
    gateway: p.gateway,
    status: p.status,
    createdAt: p.created_at,
  }));
}

/** Refunds part or all of a payment: card/UPI through Razorpay, cash recorded as MANUAL. */
export async function refundPayment(paymentId: string, amountCents: number, reason: string): Promise<RefundResult> {
  const { data } = await adminApiClient.post<{ id: string; amount_cents: number; status: string }>(
    `/payments/${encodeURIComponent(paymentId)}/refund`,
    { amount_cents: amountCents, reason },
  );
  return { id: data.id, amountCents: data.amount_cents, status: data.status };
}
