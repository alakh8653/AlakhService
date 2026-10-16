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
  providerId: string | null;
  serviceId: string;
  shopId: string | null;
  status: BookingStatus;
  scheduledAt: string; // ISO datetime
  durationMinutes: number;
  serviceMode: ServiceMode;
  /** Pickup & drop: what is being collected and what is wrong with it. */
  itemDescription: string | null;
  addressId: string | null;
  notes: string | null;
  totalAmount: number; // minor units (paise)
  createdAt: string;
  updatedAt: string;
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
  isActive: boolean;
  createdAt: string;
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
  createdAt: string;
}

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
