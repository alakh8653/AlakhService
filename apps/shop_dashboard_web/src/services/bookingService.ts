import apiClient from './apiClient';
import { apiErrorMessage } from './format';
import type { Analytics, Booking, BookingStatus, ExtraCharge, ExtraChargeStatus, PaginatedResponse, ServiceMode } from '../types';

export const BOOKING_STATUSES: BookingStatus[] = [
  'PENDING',
  'CONFIRMED',
  'ASSIGNED',
  'PROVIDER_EN_ROUTE',
  'PICKED_UP',
  'IN_PROGRESS',
  'OUT_FOR_DELIVERY',
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

const CANCEL: BookingAction = { label: 'Cancel', target: 'CANCEL' };

/**
 * Actions a shop can take from each status, for each way a booking is delivered. Mirrors the
 * transitions booking_service accepts (app/core/fsm.py, including mode_problem); CONFIRMED bookings
 * away from the shop are also assigned to a provider (see assignProvider), which moves them to ASSIGNED.
 */
export const MODE_ACTIONS: Record<ServiceMode, Partial<Record<BookingStatus, BookingAction[]>>> = {
  // The customer comes in: no provider travels.
  AT_SHOP: {
    PENDING: [{ label: 'Confirm', target: 'CONFIRMED' }, CANCEL],
    CONFIRMED: [{ label: 'Customer arrived', target: 'IN_PROGRESS' }, CANCEL],
    ASSIGNED: [{ label: 'Customer arrived', target: 'PROVIDER_EN_ROUTE' }, CANCEL],
    PROVIDER_EN_ROUTE: [{ label: 'Start service', target: 'IN_PROGRESS' }],
    IN_PROGRESS: [{ label: 'Mark complete', target: 'COMPLETED' }],
  },
  // A provider visits the customer's address.
  AT_HOME: {
    PENDING: [{ label: 'Confirm', target: 'CONFIRMED' }, CANCEL],
    CONFIRMED: [CANCEL],
    ASSIGNED: [{ label: 'Staff on the way', target: 'PROVIDER_EN_ROUTE' }, CANCEL],
    PROVIDER_EN_ROUTE: [{ label: 'Start service', target: 'IN_PROGRESS' }],
    IN_PROGRESS: [{ label: 'Mark complete', target: 'COMPLETED' }],
  },
  // The item is collected from the customer, serviced at the shop and brought back.
  PICKUP_DROP: {
    PENDING: [{ label: 'Confirm', target: 'CONFIRMED' }, CANCEL],
    CONFIRMED: [CANCEL],
    ASSIGNED: [
      { label: 'On the way to collect', target: 'PROVIDER_EN_ROUTE' },
      { label: 'Item picked up', target: 'PICKED_UP' },
      CANCEL,
    ],
    PROVIDER_EN_ROUTE: [{ label: 'Item picked up', target: 'PICKED_UP' }],
    PICKED_UP: [{ label: 'Start work', target: 'IN_PROGRESS' }],
    IN_PROGRESS: [{ label: 'Send it back', target: 'OUT_FOR_DELIVERY' }],
    OUT_FOR_DELIVERY: [{ label: 'Delivered', target: 'COMPLETED' }],
  },
};

/** What the shop can do next with this booking. */
export function bookingActions(booking: Pick<Booking, 'status' | 'serviceMode'>): BookingAction[] {
  return MODE_ACTIONS[booking.serviceMode]?.[booking.status] ?? [];
}

interface BookingResponse {
  id: string;
  booking_number: string;
  customer_id: string;
  customer_display_name?: string;
  provider_id: string | null;
  service_id: string;
  shop_id: string | null;
  status: BookingStatus;
  scheduled_at: string;
  duration_minutes: number;
  service_mode?: ServiceMode;
  item_description?: string | null;
  ready_by?: string | null;
  address_id?: string | null;
  notes: string | null;
  total_amount: number;
  reschedule_count?: number;
  points_discount?: number;
  preferred_staff_id?: string | null;
  preferred_staff_name?: string | null;
  extra_amount?: number;
  pending_extra_id?: string | null;
  pending_extra_amount?: number | null;
  pending_extra_reason?: string | null;
  rework_of?: string | null;
  metadata?: { rework_of?: string | null } | null;
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
    customerDisplayName: data.customer_display_name || 'Customer',
    providerId: data.provider_id,
    serviceId: data.service_id,
    shopId: data.shop_id,
    status: data.status,
    scheduledAt: data.scheduled_at,
    durationMinutes: data.duration_minutes,
    serviceMode: data.service_mode ?? 'AT_SHOP',
    itemDescription: data.item_description ?? null,
    readyBy: data.ready_by ?? null,
    addressId: data.address_id ?? null,
    notes: data.notes,
    totalAmount: data.total_amount,
    rescheduleCount: data.reschedule_count ?? 0,
    pointsDiscount: data.points_discount ?? 0,
    preferredStaffId: data.preferred_staff_id ?? null,
    preferredStaffName: data.preferred_staff_name ?? null,
    extraAmount: data.extra_amount ?? 0,
    pendingExtraId: data.pending_extra_id ?? null,
    pendingExtraAmount: data.pending_extra_amount ?? null,
    pendingExtraReason: data.pending_extra_reason ?? null,
    reworkOf: data.rework_of ?? data.metadata?.rework_of ?? null,
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

/** Every booking matching the filters, page by page (up to [max]), for exports. */
export async function getAllShopBookings(
  shopId: string,
  filters: BookingFilters = {},
  max = 5000,
): Promise<Booking[]> {
  const all: Booking[] = [];
  for (let page = 1; all.length < max; page++) {
    const result = await getShopBookings(shopId, { ...filters, page, perPage: 100 });
    all.push(...result.data);
    if (page >= result.totalPages) break;
  }
  return all.slice(0, max);
}

/** A booking's place in today's queue at the shop (booking_service's live queue). */
export interface QueueEntry {
  bookingId: string;
  /** WAITING, YOUR_TURN (next, a place is free) or IN_PROGRESS. */
  state: string;
  /** 1 for the first customer waiting; null while being served. */
  position: number | null;
  estimatedStart: string;
  runningLateMinutes: number;
}

interface QueueEntryRecord {
  booking_id: string;
  state: string;
  position: number | null;
  estimated_start: string;
  running_late_minutes: number;
}

/** Today's queue at the shop, in order. */
export async function getShopQueue(shopId: string): Promise<QueueEntry[]> {
  const { data } = await apiClient.get<QueueEntryRecord[]>(`/bookings/shop/${encodeURIComponent(shopId)}/queue`);
  return data.map((e) => ({
    bookingId: e.booking_id,
    state: e.state,
    position: e.position,
    estimatedStart: e.estimated_start,
    runningLateMinutes: e.running_late_minutes,
  }));
}

export async function updateBookingStatus(
  id: string,
  status: BookingStatus,
  reason?: string,
  startCode?: string,
): Promise<Booking> {
  const { data } = await apiClient.put<BookingResponse>(`/bookings/${id}/status`, {
    status,
    reason,
    ...(startCode ? { start_code: startCode } : {}),
  });
  return toBooking(data);
}

/**
 * Starting work at the customer's (a home visit going IN_PROGRESS, a pickup PICKED_UP) needs the
 * customer's 4-digit start code: booking_service refuses it without (422), and after 5 wrong tries (429).
 */
export function needsStartCode(mode: ServiceMode, target: BookingStatus): boolean {
  return (mode === 'AT_HOME' && target === 'IN_PROGRESS') || (mode === 'PICKUP_DROP' && target === 'PICKED_UP');
}

/** What to tell the shop when the start code was refused. */
export function startCodeError(err: unknown): string {
  const status = (err as { response?: { status?: number } })?.response?.status;
  if (status === 429) return 'Too many wrong codes. Wait 15 minutes, then try again.';
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (status === 422) return typeof detail === 'string' && detail ? detail : 'Ask the customer for the 4-digit start code';
  return apiErrorMessage(err, 'Could not start the job');
}

/** Give a confirmed booking to one of the shop's staff (their provider account). */
export async function assignProvider(id: string, providerId: string): Promise<Booking> {
  const { data } = await apiClient.post<BookingResponse>(`/bookings/${id}/assign`, { provider_id: providerId });
  return toBooking(data);
}

/** Pickup & drop statuses in which the shop may still promise (or change) a return time. */
export const READY_BY_STATUSES = new Set<BookingStatus>([
  'PENDING',
  'CONFIRMED',
  'ASSIGNED',
  'PROVIDER_EN_ROUTE',
  'PICKED_UP',
  'IN_PROGRESS',
]);

/** Tells the customer when their item will be back (null clears it). */
export async function setReadyBy(id: string, readyBy: string | null): Promise<Booking> {
  const { data } = await apiClient.put<BookingResponse>(`/bookings/${id}/ready-by`, { ready_by: readyBy });
  return toBooking(data);
}

export async function cancelBooking(id: string, reason: string): Promise<Booking> {
  const { data } = await apiClient.post<BookingResponse>(`/bookings/${id}/cancel`, { reason });
  return toBooking(data);
}

// ── Extra charges (booking_service's /extra-charges: the customer approves before anything is added) ──

/** Statuses in which the shop may ask for an extra charge (booking_service's OPEN_STATUSES). */
export const EXTRA_CHARGE_STATUSES = new Set<BookingStatus>([
  'CONFIRMED',
  'ASSIGNED',
  'PROVIDER_EN_ROUTE',
  'PICKED_UP',
  'IN_PROGRESS',
  'OUT_FOR_DELIVERY',
]);
/** ₹5 lakh, booking_service's ceiling for one extra charge (minor units). */
export const MAX_EXTRA_CENTS = 50_000_000;

interface ExtraChargeResponse {
  id: string;
  booking_id: string;
  amount_cents: number;
  reason: string;
  status: ExtraChargeStatus;
  created_at: string;
  decided_at?: string | null;
}

export function toExtraCharge(data: ExtraChargeResponse): ExtraCharge {
  return {
    id: data.id,
    bookingId: data.booking_id,
    amountCents: data.amount_cents,
    reason: data.reason,
    status: data.status,
    createdAt: data.created_at,
    decidedAt: data.decided_at ?? null,
  };
}

const extraCharges = (bookingId: string) => `/bookings/${encodeURIComponent(bookingId)}/extra-charges`;

/** The booking's extra charges, newest first; empty from a server that has none (404). */
export async function getExtraCharges(bookingId: string): Promise<ExtraCharge[]> {
  try {
    const { data } = await apiClient.get<ExtraChargeResponse[]>(extraCharges(bookingId));
    return data.map(toExtraCharge);
  } catch (err) {
    if ((err as { response?: { status?: number } })?.response?.status === 404) return [];
    throw err;
  }
}

/**
 * Asks the customer to agree to [amountCents] more, saying why. Refused (409) once the booking is paid or
 * covered by a package, for a walk-in, or while an earlier request waits on the customer.
 */
export async function askExtraCharge(bookingId: string, amountCents: number, reason: string): Promise<Booking> {
  const { data } = await apiClient.post<BookingResponse>(extraCharges(bookingId), {
    amount_cents: amountCents,
    reason: reason.trim(),
  });
  return toBooking(data);
}

/** Takes back a request the customer has not answered. */
export async function withdrawExtraCharge(bookingId: string, chargeId: string): Promise<Booking> {
  const { data } = await apiClient.delete<BookingResponse>(`${extraCharges(bookingId)}/${encodeURIComponent(chargeId)}`);
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

/** The date windows the bookings list offers, in the shop's (browser's) local time. */
export type BookingWhen = 'all' | 'today' | 'week';

const WINDOW_DAYS: Record<Exclude<BookingWhen, 'all'>, number> = { today: 1, week: 7 };

/** Local start (inclusive) and end (exclusive) of a window. */
export function windowBounds(when: Exclude<BookingWhen, 'all'>, now: Date = new Date()): [Date, Date] {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + WINDOW_DAYS[when]);
  return [start, end];
}

const utcDate = (d: Date) => d.toISOString().slice(0, 10);

/**
 * API date filters covering a local window. The API filters by UTC calendar day, so the range is
 * the UTC days the local window touches; [inWindow] then trims to the exact local window.
 */
export function windowFilters(when: BookingWhen, now: Date = new Date()): Pick<BookingFilters, 'dateFrom' | 'dateTo'> {
  if (when === 'all') return {};
  const [start, end] = windowBounds(when, now);
  return { dateFrom: utcDate(start), dateTo: utcDate(new Date(end.getTime() - 1)) };
}

export function inWindow(booking: Pick<Booking, 'scheduledAt'>, when: BookingWhen, now: Date = new Date()): boolean {
  if (when === 'all') return true;
  const [start, end] = windowBounds(when, now);
  const at = new Date(booking.scheduledAt).getTime();
  return at >= start.getTime() && at < end.getTime();
}

/** Earliest first: the order a shop works through its day. */
export const byScheduledAt = (a: Pick<Booking, 'scheduledAt'>, b: Pick<Booking, 'scheduledAt'>) =>
  new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime();

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
