import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import {
  askExtraCharge,
  getExtraCharges,
  needsStartCode,
  startCodeError,
  toBooking,
  updateBookingStatus,
  withdrawExtraCharge,
} from '../bookingService';
import { toShop } from '../shopService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

const api = vi.mocked(apiClient);

const apiBooking = {
  id: 'b1',
  booking_number: 'BK-1',
  customer_id: 'c1',
  provider_id: 'p1',
  service_id: 'svc1',
  shop_id: 's1',
  status: 'PROVIDER_EN_ROUTE' as const,
  scheduled_at: '2026-10-10T10:00:00Z',
  duration_minutes: 45,
  service_mode: 'AT_HOME' as const,
  notes: null,
  total_amount: 49900,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
};

const httpError = (status: number, detail?: string) =>
  Object.assign(new Error(`Request failed with status code ${status}`), { response: { status, data: detail ? { detail } : {} } });

describe('start code', () => {
  beforeEach(() => vi.clearAllMocks());

  it('is needed only to start work at the customer', () => {
    expect(needsStartCode('AT_HOME', 'IN_PROGRESS')).toBe(true);
    expect(needsStartCode('PICKUP_DROP', 'PICKED_UP')).toBe(true);
    expect(needsStartCode('PICKUP_DROP', 'IN_PROGRESS')).toBe(false);
    expect(needsStartCode('AT_SHOP', 'IN_PROGRESS')).toBe(false);
    expect(needsStartCode('AT_HOME', 'PROVIDER_EN_ROUTE')).toBe(false);
  });

  it('goes with the status change, and only when given', async () => {
    api.put.mockResolvedValue({ data: { ...apiBooking, status: 'IN_PROGRESS' } });
    await updateBookingStatus('b1', 'IN_PROGRESS', undefined, '4821');
    expect(api.put).toHaveBeenCalledWith('/bookings/b1/status', { status: 'IN_PROGRESS', reason: undefined, start_code: '4821' });
    await updateBookingStatus('b1', 'COMPLETED');
    expect(api.put).toHaveBeenLastCalledWith('/bookings/b1/status', { status: 'COMPLETED', reason: undefined });
  });

  it('explains a wrong code (422) and too many tries (429)', () => {
    expect(startCodeError(httpError(422, 'Ask the customer for the 4-digit start code'))).toBe('Ask the customer for the 4-digit start code');
    expect(startCodeError(httpError(422))).toBe('Ask the customer for the 4-digit start code');
    expect(startCodeError(httpError(429, 'Too Many Requests'))).toBe('Too many wrong codes. Wait 15 minutes, then try again.');
  });
});

describe('extra charges', () => {
  beforeEach(() => vi.clearAllMocks());

  it("are asked for with booking_service's /extra-charges, in paise with a reason", async () => {
    api.post.mockResolvedValue({
      data: { ...apiBooking, status: 'IN_PROGRESS', pending_extra_id: 'x1', pending_extra_amount: 35000, pending_extra_reason: 'New capacitor' },
    });
    const booking = await askExtraCharge('b1', 35000, '  New capacitor ');
    expect(api.post).toHaveBeenCalledWith('/bookings/b1/extra-charges', { amount_cents: 35000, reason: 'New capacitor' });
    expect(booking).toMatchObject({ pendingExtraId: 'x1', pendingExtraAmount: 35000, pendingExtraReason: 'New capacitor' });
  });

  it('can be taken back before the customer answers', async () => {
    api.delete.mockResolvedValue({ data: { ...apiBooking, pending_extra_id: null } });
    const booking = await withdrawExtraCharge('b1', 'x1');
    expect(api.delete).toHaveBeenCalledWith('/bookings/b1/extra-charges/x1');
    expect(booking.pendingExtraId).toBeNull();
  });

  it('list as empty from a server without them', async () => {
    api.get.mockResolvedValue({
      data: [{ id: 'x0', booking_id: 'b1', amount_cents: 20000, reason: 'Wiring', status: 'DECLINED', created_at: '', decided_at: '' }],
    });
    expect(await getExtraCharges('b1')).toEqual([
      { id: 'x0', bookingId: 'b1', amountCents: 20000, reason: 'Wiring', status: 'DECLINED', createdAt: '', decidedAt: '' },
    ]);
    expect(api.get).toHaveBeenCalledWith('/bookings/b1/extra-charges');
    api.get.mockRejectedValue(httpError(404));
    expect(await getExtraCharges('b1')).toEqual([]);
    api.get.mockRejectedValue(httpError(500));
    await expect(getExtraCharges('b1')).rejects.toThrow();
  });

  it('and the free fix show on the booking', () => {
    const b = toBooking({ ...apiBooking, extra_amount: 20000, pending_extra_id: 'x2', pending_extra_amount: 5000, rework_of: 'b0' });
    expect(b).toMatchObject({ extraAmount: 20000, pendingExtraId: 'x2', pendingExtraAmount: 5000, reworkOf: 'b0' });
    expect(toBooking({ ...apiBooking, metadata: { rework_of: 'b0' } }).reworkOf).toBe('b0');
    expect(toBooking(apiBooking)).toMatchObject({ extraAmount: 0, pendingExtraId: null, reworkOf: null });
  });
});

describe('shop guarantee', () => {
  it('defaults to a week', () => {
    const shop = {
      id: 's1',
      owner_id: 'u1',
      name: 'Demo',
      category: 'salon',
      description: null,
      city: null,
      address: null,
      phone: null,
      email: null,
      rating_avg: 0,
      rating_count: 0,
      is_active: true,
      is_verified: true,
      created_at: '',
    };
    expect(toShop(shop).guaranteeDays).toBe(7);
    expect(toShop({ ...shop, guarantee_days: 30, verified_at: '2026-10-01T00:00:00Z' })).toMatchObject({
      guaranteeDays: 30,
      verifiedAt: '2026-10-01T00:00:00Z',
    });
  });
});
