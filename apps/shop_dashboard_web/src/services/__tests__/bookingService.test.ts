import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import {
  BOOKING_ACTIONS,
  assignProvider,
  cancelBooking,
  getShopBookings,
  getShopSummary,
  updateBookingStatus,
} from '../bookingService';
import type { BookingStatus } from '../../types';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}));

const api = vi.mocked(apiClient);

const apiBooking = {
  id: 'b1',
  booking_number: 'BK-1',
  customer_id: 'c1',
  provider_id: null,
  service_id: 'svc1',
  shop_id: 's1',
  status: 'PENDING',
  scheduled_at: '2026-10-10T10:00:00Z',
  duration_minutes: 45,
  notes: null,
  total_amount: 49900,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
};

// booking_service's state machine (app/core/fsm.py).
const BACKEND_TRANSITIONS: Record<string, string[]> = {
  PENDING: ['CONFIRMED', 'CANCELLED'],
  CONFIRMED: ['ASSIGNED', 'CANCELLED'],
  ASSIGNED: ['PROVIDER_EN_ROUTE', 'CANCELLED'],
  PROVIDER_EN_ROUTE: ['IN_PROGRESS'],
  IN_PROGRESS: ['COMPLETED', 'DISPUTED'],
  COMPLETED: ['DISPUTED'],
  DISPUTED: ['REFUNDED', 'COMPLETED'],
};

describe('bookingService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists a shop’s bookings with snake_case filters and maps the page', async () => {
    api.get.mockResolvedValue({ data: { items: [apiBooking], total: 41, page: 2, per_page: 20 } });

    const page = await getShopBookings('s1', { status: 'PENDING', providerId: 'p1', dateFrom: '2026-10-01', page: 2 });

    expect(api.get).toHaveBeenCalledWith('/bookings/shop/s1', {
      params: { status: 'PENDING', provider_id: 'p1', date_from: '2026-10-01', date_to: undefined, page: 2, per_page: 20 },
    });
    expect(page.totalPages).toBe(3);
    expect(page.data[0]).toMatchObject({ bookingNumber: 'BK-1', customerId: 'c1', totalAmount: 49900, scheduledAt: '2026-10-10T10:00:00Z' });
  });

  it('changes status with PUT and cancels through the cancel endpoint', async () => {
    api.put.mockResolvedValue({ data: { ...apiBooking, status: 'CONFIRMED' } });
    api.post.mockResolvedValue({ data: { ...apiBooking, status: 'CANCELLED' } });

    expect((await updateBookingStatus('b1', 'CONFIRMED')).status).toBe('CONFIRMED');
    expect(api.put).toHaveBeenCalledWith('/bookings/b1/status', { status: 'CONFIRMED', reason: undefined });

    expect((await cancelBooking('b1', 'Closed today')).status).toBe('CANCELLED');
    expect(api.post).toHaveBeenCalledWith('/bookings/b1/cancel', { reason: 'Closed today' });
  });

  it('assigns a provider through the assign endpoint', async () => {
    api.post.mockResolvedValue({ data: { ...apiBooking, status: 'ASSIGNED', provider_id: 'u-ravi' } });
    const booking = await assignProvider('b1', 'u-ravi');
    expect(api.post).toHaveBeenCalledWith('/bookings/b1/assign', { provider_id: 'u-ravi' });
    expect(booking).toMatchObject({ status: 'ASSIGNED', providerId: 'u-ravi' });
  });

  it('maps the shop summary', async () => {
    api.get.mockResolvedValue({
      data: {
        shop_id: 's1',
        date_from: '2026-10-01',
        date_to: '2026-10-02',
        total_bookings: 3,
        total_revenue: 99800,
        unique_customers: 2,
        by_status: { COMPLETED: 2, PENDING: 1 },
        by_day: [{ day: '2026-10-01', revenue: 99800, bookings: 3 }],
        top_services: [{ service_id: 'svc1', bookings: 3, revenue: 99800 }],
      },
    });

    const summary = await getShopSummary('s1', '2026-10-01', '2026-10-02');

    expect(api.get).toHaveBeenCalledWith('/bookings/shop/s1/summary', {
      params: { date_from: '2026-10-01', date_to: '2026-10-02' },
    });
    expect(summary.uniqueCustomers).toBe(2);
    expect(summary.revenueByDay).toEqual([{ date: '2026-10-01', revenue: 99800, bookingCount: 3 }]);
    expect(summary.topServices).toEqual([{ serviceId: 'svc1', bookingCount: 3, revenue: 99800 }]);
  });

  it('only offers transitions the backend accepts', () => {
    for (const [from, actions] of Object.entries(BOOKING_ACTIONS)) {
      for (const action of actions ?? []) {
        const target: BookingStatus = action.target === 'CANCEL' ? 'CANCELLED' : action.target;
        expect(BACKEND_TRANSITIONS[from]).toContain(target);
      }
    }
  });
});
