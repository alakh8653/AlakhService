import apiClient from './apiClient';
import type { Analytics, Booking, BookingStatus, PaginatedResponse } from '../types';

export const BOOKING_STATUSES: BookingStatus[] = [
  'PENDING',
  'CONFIRMED',
  'ASSIGNED',
  'PROVIDER_EN_ROUTE',
  'IN_PROGRESS',
  'COMPLETED',
  'CANCELLED',
  'DISPUTED',
  'REFUNDED',
];

export interface BookingAction {
  label: string;
  /** Target status, or 'CANCEL' for the cancel endpoint (which needs a reason). */
  target: BookingStatus | 'CANCEL';
}

/**
 * Actions a shop can take from each status. Mirrors the transitions
 * booking_service accepts; assignment itself is done by dispatch_service.
 */
export const BOOKING_ACTIONS: Partial<Record<BookingStatus, BookingAction[]>> = {
  PENDING: [
    { label: 'Confirm', target: 'CONFIRMED' },
    { label: 'Cancel', target: 'CANCEL' },
  ],
  CONFIRMED: [{ label: 'Cancel', target: 'CANCEL' }],
  ASSIGNED: [
    { label: 'Provider en route', target: 'PROVIDER_EN_ROUTE' },
    { label: 'Cancel', target: 'CANCEL' },
  ],
  PROVIDER_EN_ROUTE: [{ label: 'Start service', target: 'IN_PROGRESS' }],
  IN_PROGRESS: [{ label: 'Mark complete', target: 'COMPLETED' }],
};

interface BookingResponse {
  id: string;
  booking_number: string;
  customer_id: string;
  provider_id: string | null;
  service_id: string;
  shop_id: string | null;
  status: BookingStatus;
  scheduled_at: string;
  duration_minutes: number;
  notes: string | null;
  total_amount: number;
  created_at: string;
  updated_at: string;
}

interface BookingListResponse {
  items: BookingResponse[];
  total: number;
  page: number;
  per_page: number;
}

export function toBooking(data: BookingResponse): Booking {
  return {
    id: data.id,
    bookingNumber: data.booking_number,
    customerId: data.customer_id,
    providerId: data.provider_id,
    serviceId: data.service_id,
    shopId: data.shop_id,
    status: data.status,
    scheduledAt: data.scheduled_at,
    durationMinutes: data.duration_minutes,
    notes: data.notes,
    totalAmount: data.total_amount,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  };
}

export interface BookingFilters {
  status?: BookingStatus;
  providerId?: string;
  dateFrom?: string; // YYYY-MM-DD, inclusive
  dateTo?: string; // YYYY-MM-DD, inclusive
  page?: number;
  perPage?: number;
}

export async function getShopBookings(
  shopId: string,
  filters: BookingFilters = {},
): Promise<PaginatedResponse<Booking>> {
  const { data } = await apiClient.get<BookingListResponse>(`/bookings/shop/${shopId}`, {
    params: {
      status: filters.status,
      provider_id: filters.providerId,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
      page: filters.page ?? 1,
      per_page: filters.perPage ?? 20,
    },
  });
  return {
    data: data.items.map(toBooking),
    total: data.total,
    page: data.page,
    perPage: data.per_page,
    totalPages: Math.ceil(data.total / data.per_page),
  };
}

export async function updateBookingStatus(
  id: string,
  status: BookingStatus,
  reason?: string,
): Promise<Booking> {
  const { data } = await apiClient.put<BookingResponse>(`/bookings/${id}/status`, {
    status,
    reason,
  });
  return toBooking(data);
}

export async function cancelBooking(id: string, reason: string): Promise<Booking> {
  const { data } = await apiClient.post<BookingResponse>(`/bookings/${id}/cancel`, { reason });
  return toBooking(data);
}

interface ShopBookingSummary {
  shop_id: string;
  date_from: string;
  date_to: string;
  total_bookings: number;
  total_revenue: number;
  unique_customers: number;
  by_status: Partial<Record<BookingStatus, number>>;
  by_day: Array<{ day: string; revenue: number; bookings: number }>;
  top_services: Array<{ service_id: string; bookings: number; revenue: number }>;
}

export function toAnalytics(data: ShopBookingSummary): Analytics {
  return {
    dateFrom: data.date_from,
    dateTo: data.date_to,
    totalBookings: data.total_bookings,
    totalRevenue: data.total_revenue,
    uniqueCustomers: data.unique_customers,
    bookingsByStatus: data.by_status,
    revenueByDay: data.by_day.map((d) => ({
      date: d.day,
      revenue: d.revenue,
      bookingCount: d.bookings,
    })),
    topServices: data.top_services.map((s) => ({
      serviceId: s.service_id,
      bookingCount: s.bookings,
      revenue: s.revenue,
    })),
  };
}

export async function getShopSummary(
  shopId: string,
  dateFrom?: string,
  dateTo?: string,
): Promise<Analytics> {
  const { data } = await apiClient.get<ShopBookingSummary>(`/bookings/shop/${shopId}/summary`, {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return toAnalytics(data);
}
