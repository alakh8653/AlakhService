// Shared TypeScript interfaces for the Shop Dashboard

export type BookingStatus =
  | 'pending'
  | 'confirmed'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'no_show';

export type PaymentStatus = 'unpaid' | 'paid' | 'refunded' | 'partial';

export interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
  avatarUrl?: string;
}

export interface Service {
  id: string;
  name: string;
  description: string;
  durationMinutes: number;
  price: number;
  currency: string;
  category: string;
  isActive: boolean;
  imageUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export interface StaffMember {
  id: string;
  name: string;
  email: string;
  phone: string;
  role: string;
  avatarUrl?: string;
  assignedServiceIds: string[];
  isActive: boolean;
  joinedAt: string;
}

export interface TimeSlot {
  start: string; // ISO datetime
  end: string;   // ISO datetime
}

export interface Booking {
  id: string;
  bookingNumber: string;
  customer: Customer;
  service: Service;
  staff: StaffMember;
  timeSlot: TimeSlot;
  status: BookingStatus;
  paymentStatus: PaymentStatus;
  totalAmount: number;
  currency: string;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface DailyRevenue {
  date: string;   // 'YYYY-MM-DD'
  revenue: number;
  bookingCount: number;
}

export interface Analytics {
  totalBookings: number;
  totalRevenue: number;
  activeCustomers: number;
  averageRating: number;
  revenueByDay: DailyRevenue[];
  topServices: Array<{ service: Service; bookingCount: number; revenue: number }>;
  bookingsByStatus: Record<BookingStatus, number>;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'owner' | 'manager' | 'staff';
  shopId: string;
  avatarUrl?: string;
}

export interface Shop {
  id: string;
  name: string;
  description: string;
  address: string;
  phone: string;
  email: string;
  logoUrl?: string;
  coverImageUrl?: string;
  openingHours: Record<string, { open: string; close: string; closed: boolean }>;
  timezone: string;
  currency: string;
  createdAt: string;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
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
