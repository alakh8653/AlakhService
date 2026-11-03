import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import { getExtras, needsStartCode, requestExtras, startCodeError, toBooking, updateBookingStatus } from '../bookingService';
import { toShop } from '../shopService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
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

  it('are sent in paise with an optional note', async () => {
    api.post.mockResolvedValue({
      data: {
        id: 'q1',
        booking_id: 'b1',
        status: 'PENDING',
        items: [{ description: 'New capacitor', amount_cents: 35000 }],
        total_cents: 35000,
        note: 'Old part burnt',
        created_at: '2026-10-10T11:00:00Z',
        decided_at: null,
      },
    });
    const quote = await requestExtras('b1', [{ description: 'New capacitor', amountCents: 35000 }], '  Old part burnt ');
    expect(api.post).toHaveBeenCalledWith('/bookings/b1/extras', {
      items: [{ description: 'New capacitor', amount_cents: 35000 }],
      note: 'Old part burnt',
    });
    expect(quote).toMatchObject({ id: 'q1', status: 'PENDING', totalCents: 35000, items: [{ amountCents: 35000 }] });
  });

  it('list as empty from a server without them', async () => {
    api.get.mockRejectedValue(httpError(404));
    expect(await getExtras('b1')).toEqual([]);
    api.get.mockRejectedValue(httpError(500));
    await expect(getExtras('b1')).rejects.toThrow();
  });

  it('and the free fix show on the booking', () => {
    const b = toBooking({ ...apiBooking, extras_cents: 20000, pending_quote_id: 'q2', rework_of: 'b0' });
    expect(b).toMatchObject({ extrasCents: 20000, pendingQuoteId: 'q2', reworkOf: 'b0' });
    expect(toBooking({ ...apiBooking, metadata: { rework_of: 'b0' } }).reworkOf).toBe('b0');
    expect(toBooking(apiBooking)).toMatchObject({ extrasCents: 0, pendingQuoteId: null, reworkOf: null });
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
