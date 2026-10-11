import apiClient from './apiClient';

// Payments for the shop's bookings (payment_service).

export interface BookingPayment {
  id: string;
  amountCents: number;
  method: string;
  status: string;
}

interface PaymentRecord {
  id: string;
  amount_cents: number;
  payment_method: string;
  status: string;
}

const toPayment = (p: PaymentRecord): BookingPayment => ({
  id: p.id,
  amountCents: p.amount_cents,
  method: p.payment_method,
  status: p.status,
});

export async function getBookingPayments(bookingId: string): Promise<BookingPayment[]> {
  const { data } = await apiClient.get<PaymentRecord[]>('/payments', { params: { booking_id: bookingId } });
  return data.map(toPayment);
}

/** Records that the customer handed over the cash for this payment. */
export async function confirmCashReceived(paymentId: string): Promise<BookingPayment> {
  const { data } = await apiClient.post<PaymentRecord>(`/payments/${paymentId}/cash-received`);
  return toPayment(data);
}
