import { apiClient } from './apiClient';

/** One customer in today's line at the shop (booking_service's live queue). */
export interface LineEntry {
  bookingId: string;
  bookingNumber: string;
  name: string;
  /** WAITING, YOUR_TURN, IN_PROGRESS, UNSERVABLE or CHECK_IN_NEEDED. */
  state: string;
  position: number | null;
  scheduledAt: string;
  estimatedStart: string | null;
  estimatedEnd: string | null;
  etaMin: string | null;
  etaMax: string | null;
  confidence: string | null;
  runningLateMinutes: number;
  serviceId: string | null;
  /** BOOKED or WALK_IN. */
  source: string;
  /** VIP, APPOINTMENT or WALK_IN. */
  priority: string;
  checkedIn: boolean;
  staffId: string | null;
  staffName: string | null;
  reason: string | null;
  overrun: boolean;
  moved: boolean;
  canMarkNoShow: boolean;
}

export interface TeamMember {
  staffId: string;
  name: string | null;
  serviceIds: string[];
  /** AVAILABLE, BREAK or OFF. */
  status: string;
  until: string | null;
  servingBookingId: string | null;
  servingName: string | null;
  servingSince: string | null;
  servingUntil: string | null;
  overrun: boolean;
  waiting: number;
}

export interface QueueSettings {
  bufferPct: number;
  alpha: number;
  graceMinutes: number;
  agingMinutes: number;
  checkInRequired: boolean;
  vipPerDay: number;
}

export interface BoardRow {
  ticket: string;
  name: string;
  staffName: string | null;
  waitMinutes: number | null;
}

export interface Board {
  version: string;
  nowServing: BoardRow[];
  next: BoardRow[];
  waiting: number;
}

type Raw = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

export function toLineEntry(e: Raw): LineEntry {
  return {
    bookingId: e.booking_id,
    bookingNumber: e.booking_number,
    name: e.customer_display_name,
    state: e.state,
    position: e.position ?? null,
    scheduledAt: e.scheduled_at,
    estimatedStart: e.estimated_start ?? null,
    estimatedEnd: e.estimated_end ?? null,
    etaMin: e.eta_min ?? null,
    etaMax: e.eta_max ?? null,
    confidence: e.confidence ?? null,
    runningLateMinutes: e.running_late_minutes ?? 0,
    serviceId: e.service_id ?? null,
    source: e.source ?? 'BOOKED',
    priority: e.priority ?? 'APPOINTMENT',
    checkedIn: !!e.checked_in,
    staffId: e.staff_id ?? null,
    staffName: e.staff_name ?? null,
    reason: e.reason ?? null,
    overrun: !!e.overrun,
    moved: !!e.moved,
    canMarkNoShow: !!e.can_mark_no_show,
  };
}

function toMember(m: Raw): TeamMember {
  return {
    staffId: m.staff_id,
    name: m.name ?? null,
    serviceIds: m.service_ids ?? [],
    status: m.status,
    until: m.until ?? null,
    servingBookingId: m.serving_booking_id ?? null,
    servingName: m.serving_name ?? null,
    servingSince: m.serving_since ?? null,
    servingUntil: m.serving_until ?? null,
    overrun: !!m.overrun,
    waiting: m.waiting ?? 0,
  };
}

function toSettings(s: Raw): QueueSettings {
  return {
    bufferPct: s.buffer_pct,
    alpha: s.alpha,
    graceMinutes: s.grace_minutes,
    agingMinutes: s.aging_minutes,
    checkInRequired: s.check_in_required,
    vipPerDay: s.vip_per_day,
  };
}

export function toBoard(b: Raw): Board {
  const row = (r: Raw): BoardRow => ({ ticket: r.ticket, name: r.name, staffName: r.staff_name ?? null, waitMinutes: r.wait_minutes ?? null });
  return { version: b.version, nowServing: (b.now_serving ?? []).map(row), next: (b.next ?? []).map(row), waiting: b.waiting ?? 0 };
}

const shopPath = (shopId: string) => `/bookings/shop/${encodeURIComponent(shopId)}`;
const bookingPath = (bookingId: string) => `/bookings/${encodeURIComponent(bookingId)}`;

export async function getLine(shopId: string): Promise<LineEntry[]> {
  const { data } = await apiClient.get<Raw[]>(`${shopPath(shopId)}/queue`);
  return data.map(toLineEntry);
}

export async function getTeam(shopId: string): Promise<TeamMember[]> {
  const { data } = await apiClient.get<Raw[]>(`${shopPath(shopId)}/queue/team`);
  return data.map(toMember);
}

/** A break for [minutes], off for the rest of today, or back (AVAILABLE). */
export async function setTeamStatus(shopId: string, staffId: string, status: 'AVAILABLE' | 'BREAK' | 'OFF', minutes?: number): Promise<TeamMember[]> {
  const { data } = await apiClient.put<Raw[]>(`${shopPath(shopId)}/queue/team/${encodeURIComponent(staffId)}`, { status, minutes });
  return data.map(toMember);
}

export async function addWalkIn(shopId: string, body: { serviceId: string; name: string; vip?: boolean; preferredStaffId?: string }): Promise<LineEntry> {
  const { data } = await apiClient.post<Raw>(`${shopPath(shopId)}/walk-ins`, {
    service_id: body.serviceId,
    name: body.name,
    vip: !!body.vip,
    preferred_staff_id: body.preferredStaffId || undefined,
  });
  return toLineEntry(data);
}

/** Starts the next customer for this team member (or the next anyone may take). */
export async function callNext(shopId: string, staffId?: string): Promise<LineEntry> {
  const { data } = await apiClient.post<Raw>(`${shopPath(shopId)}/queue/call-next`, { staff_id: staffId ?? null });
  return toLineEntry(data);
}

export async function reorder(shopId: string, bookingIds: string[]): Promise<LineEntry[]> {
  const { data } = await apiClient.post<Raw[]>(`${shopPath(shopId)}/queue/reorder`, { booking_ids: bookingIds });
  return data.map(toLineEntry);
}

export async function setVip(bookingId: string, vip: boolean): Promise<void> {
  await apiClient.put(`${bookingPath(bookingId)}/priority`, { vip });
}

export async function markNoShow(bookingId: string): Promise<void> {
  await apiClient.post(`${bookingPath(bookingId)}/no-show`);
}

export async function checkIn(bookingId: string): Promise<void> {
  await apiClient.post(`${bookingPath(bookingId)}/check-in`);
}

/** Starts this customer now, with [staffId] (else whoever the line planned, if free). */
export async function start(bookingId: string, staffId?: string | null): Promise<void> {
  await apiClient.put(`${bookingPath(bookingId)}/status`, { status: 'IN_PROGRESS', staff_id: staffId ?? null });
}

/** Finishes the service being done (learns how long it took). */
export async function finish(bookingId: string): Promise<void> {
  await apiClient.put(`${bookingPath(bookingId)}/status`, { status: 'COMPLETED' });
}

export async function getSettings(shopId: string): Promise<QueueSettings> {
  const { data } = await apiClient.get<Raw>(`${shopPath(shopId)}/queue/settings`);
  return toSettings(data);
}

export async function saveSettings(shopId: string, s: QueueSettings): Promise<QueueSettings> {
  const { data } = await apiClient.put<Raw>(`${shopPath(shopId)}/queue/settings`, {
    buffer_pct: s.bufferPct,
    alpha: s.alpha,
    grace_minutes: s.graceMinutes,
    aging_minutes: s.agingMinutes,
    check_in_required: s.checkInRequired,
    vip_per_day: s.vipPerDay,
  });
  return toSettings(data);
}

/** The public board (no account needed). */
export async function getBoard(shopId: string): Promise<Board> {
  const { data } = await apiClient.get<Raw>(`${shopPath(shopId)}/queue/board`);
  return toBoard(data);
}

/** The WebSocket URL for a shop's live line ([token]) or its public board (no token). */
export function liveUrl(shopId: string, view: 'queue' | 'board', token?: string | null): string {
  const base = new URL(apiClient.defaults.baseURL ?? '/api/v1', window.location.origin);
  base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
  base.pathname = `${base.pathname.replace(/\/$/, '')}/ws/shops/${encodeURIComponent(shopId)}/${view}`;
  if (token) base.searchParams.set('token', token);
  return base.toString();
}
