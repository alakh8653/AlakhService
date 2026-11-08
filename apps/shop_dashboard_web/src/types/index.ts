// Shared TypeScript interfaces for the Shop Dashboard.
// Field names are camelCase; services/*.ts map them from the snake_case API.

/** Booking lifecycle, as enforced by booking_service's state machine. */
export type BookingStatus =
  | 'PENDING'
  | 'CONFIRMED'
  | 'ASSIGNED'
  | 'PROVIDER_EN_ROUTE'
  | 'PICKED_UP'
  | 'IN_PROGRESS'
  | 'OUT_FOR_DELIVERY'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'DISPUTED'
  | 'REFUNDED';

/** How a service is delivered: the customer visits, a provider visits, or the item is collected and returned. */
export type ServiceMode = 'AT_SHOP' | 'AT_HOME' | 'PICKUP_DROP';

export interface Booking {
  id: string;
  bookingNumber: string;
  customerId: string;
  /** First name and last initial ("Ravi S."), or "Customer": shops never get a customer's phone or email. */
  customerDisplayName: string;
  providerId: string | null;
  serviceId: string;
  shopId: string | null;
  status: BookingStatus;
  scheduledAt: string; // ISO datetime
  durationMinutes: number;
  serviceMode: ServiceMode;
  /** Pickup & drop: what is being collected and what is wrong with it. */
  itemDescription: string | null;
  /** Pickup & drop: when the shop expects the item to be back with the customer (ISO datetime). */
  readyBy: string | null;
  addressId: string | null;
  notes: string | null;
  totalAmount: number; // minor units (paise)
  /** How many times the customer has moved it to another time (they may twice). */
  rescheduleCount?: number;
  /** Paid by the customer's loyalty points (minor units): AlakhService pays it to the shop. */
  pointsDiscount?: number;
  /** The staff member the customer asked for (shop staff id and display name), if anyone. */
  preferredStaffId?: string | null;
  preferredStaffName?: string | null;
  /** Of totalAmount, what the customer agreed to pay on top after the job was seen (minor units). */
  extraAmount?: number;
  /** An extra charge waiting for the customer's answer: its id, amount (minor units) and reason. */
  pendingExtraId?: string | null;
  pendingExtraAmount?: number | null;
  pendingExtraReason?: string | null;
  /** A free fix: the earlier booking this one redoes at no cost (the shop's guarantee). */
  reworkOf?: string | null;
  createdAt: string;
  updatedAt: string;
}

export type ExtraChargeStatus = 'PENDING' | 'APPROVED' | 'DECLINED' | 'WITHDRAWN' | 'EXPIRED';

/** An extra charge asked for once the job was seen: it counts only if the customer approves it. */
export interface ExtraCharge {
  id: string;
  bookingId: string;
  amountCents: number;
  reason: string;
  status: ExtraChargeStatus;
  createdAt: string;
  decidedAt: string | null;
}

export interface Service {
  id: string;
  shopId: string;
  categoryId: string | null;
  name: string;
  description: string | null;
  priceCents: number;
  durationMinutes: number | null;
  isActive: boolean;
  createdAt: string;
  serviceModes: ServiceMode[];
  homeVisitFeeCents: number;
  pickupFeeCents: number;
}

export interface StaffMember {
  id: string;
  shopId: string;
  userId: string | null;
  name: string;
  email: string | null;
  phone: string | null;
  role: string;
  serviceIds: string[];
  /** Their own week (Monday first, an empty day is off); null means they work the shop's opening hours. */
  workingHours: OpenInterval[][] | null;
  isActive: boolean;
  createdAt: string;
}

/** One stretch of the day the shop is open, "HH:MM" in India time ("24:00" is midnight). */
export interface OpenInterval {
  start: string;
  end: string;
}

export interface ShopHoliday {
  date: string; // YYYY-MM-DD
  note: string | null;
}

/** Opening hours, closures and capacity (shop_service), as customers can book against them. */
export interface ShopHours {
  /** False until the owner saves a week; until then customers may request any time. */
  configured: boolean;
  timezone: string;
  /** Seven days, Monday first; an empty day is closed. */
  weekly: OpenInterval[][];
  /** Today and later, soonest first. */
  holidays: ShopHoliday[];
  /** How many customers can be served at the same time. */
  capacity: number;
  /** Set by the owner; null means one per active staff member. */
  capacityOverride: number | null;
  /** Each booking is confirmed at once while a place is free (needs opening hours). */
  autoConfirm: boolean;
  activeStaff: number;
  updatedAt: string | null;
}

export interface Shop {
  id: string;
  ownerId: string;
  name: string;
  category: string;
  description: string | null;
  city: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  /** Map position customers get directions to (and a cab drop-off at). */
  latitude: number | null;
  longitude: number | null;
  ratingAvg: number;
  ratingCount: number;
  isActive: boolean;
  isVerified: boolean;
  verifiedAt?: string | null;
  /** Days after a job in which the customer may ask for a free fix (0 to 90; 7 when not set). */
  guaranteeDays?: number;
  createdAt: string;
  /** KYC review: a new shop is hidden from customers until approved. Missing on older responses. */
  verificationStatus?: VerificationStatus;
  rejectionReason?: string | null;
  legalName?: string | null;
  legalAddress?: string | null;
  gstin?: string | null;
  submittedAt?: string | null;
}

export type VerificationStatus = 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';

export interface DailyRevenue {
  date: string; // 'YYYY-MM-DD'
  revenue: number; // minor units
  bookingCount: number;
}

export interface ServiceStats {
  serviceId: string;
  bookingCount: number;
  revenue: number; // minor units
}

export interface Analytics {
  dateFrom: string;
  dateTo: string;
  totalBookings: number;
  totalRevenue: number; // minor units, completed bookings
  uniqueCustomers: number;
  bookingsByStatus: Partial<Record<BookingStatus, number>>;
  revenueByDay: DailyRevenue[];
  topServices: ServiceStats[];
}

export interface User {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix timestamp (ms)
}

export interface LoginCredentials {
  email: string;
  password: string;
}
