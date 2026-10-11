import adminApiClient from '../../apiClient';
import { getBookingPayments, refundPayment } from '../PaymentService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const get = vi.mocked(adminApiClient.get);
const post = vi.mocked(adminApiClient.post);

describe('PaymentService', () => {
  it('lists a booking\'s payments', async () => {
    get.mockResolvedValue({
      data: [{ id: 'p1', amount_cents: 49900, payment_method: 'upi', gateway: 'razorpay', status: 'COMPLETED', created_at: '2026-10-11T00:00:00Z' }],
    });
    const payments = await getBookingPayments('b1');
    expect(get).toHaveBeenCalledWith('/payments', { params: { booking_id: 'b1' } });
    expect(payments[0]).toMatchObject({ id: 'p1', amountCents: 49900, method: 'upi', gateway: 'razorpay' });
  });

  it('refunds an amount in paise with a reason', async () => {
    post.mockResolvedValue({ data: { id: 'r1', amount_cents: 10000, status: 'PROCESSED' } });
    const r = await refundPayment('p1', 10000, 'late');
    expect(post).toHaveBeenCalledWith('/payments/p1/refund', { amount_cents: 10000, reason: 'late' });
    expect(r).toEqual({ id: 'r1', amountCents: 10000, status: 'PROCESSED' });
  });
});
