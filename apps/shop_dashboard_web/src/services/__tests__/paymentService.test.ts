import { describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import { confirmCashReceived, getBookingPayments } from '../paymentService';

vi.mock('../apiClient', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const api = vi.mocked(apiClient);

describe('paymentService', () => {
  it('reads a booking\'s payments and confirms cash', async () => {
    api.get.mockResolvedValueOnce({ data: [{ id: 'p1', amount_cents: 49900, payment_method: 'cash', status: 'PENDING' }] });
    expect(await getBookingPayments('b1')).toEqual([{ id: 'p1', amountCents: 49900, method: 'cash', status: 'PENDING' }]);
    expect(api.get).toHaveBeenCalledWith('/payments', { params: { booking_id: 'b1' } });

    api.post.mockResolvedValueOnce({ data: { id: 'p1', amount_cents: 49900, payment_method: 'cash', status: 'COMPLETED' } });
    expect((await confirmCashReceived('p1')).status).toBe('COMPLETED');
    expect(api.post).toHaveBeenCalledWith('/payments/p1/cash-received');
  });
});
