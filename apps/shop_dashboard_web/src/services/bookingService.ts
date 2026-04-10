import apiClient from './apiClient';
import type {
  ApiResponse,
  Booking,
  BookingStatus,
  PaginatedResponse,
} from '../types';

export interface BookingFilters {
  status?: BookingStatus;
  staffId?: string;
  serviceId?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  perPage?: number;
}

export async function getBookings(
  filters: BookingFilters = {},
): Promise<PaginatedResponse<Booking>> {
  const { data } = await apiClient.get<PaginatedResponse<Booking>>('/bookings', {
    params: filters,
  });
  return data;
}

export async function getBookingById(id: string): Promise<Booking> {
  const { data } = await apiClient.get<ApiResponse<Booking>>(`/bookings/${id}`);
  return data.data;
}

export async function updateBookingStatus(
  id: string,
  status: BookingStatus,
  reason?: string,
): Promise<Booking> {
  const { data } = await apiClient.patch<ApiResponse<Booking>>(
    `/bookings/${id}/status`,
    { status, reason },
  );
  return data.data;
}

export async function cancelBooking(id: string, reason: string): Promise<Booking> {
  return updateBookingStatus(id, 'cancelled', reason);
}

export async function confirmBooking(id: string): Promise<Booking> {
  return updateBookingStatus(id, 'confirmed');
}

export async function completeBooking(id: string): Promise<Booking> {
  return updateBookingStatus(id, 'completed');
}

export async function rescheduleBooking(
  id: string,
  newStart: string,
  newEnd: string,
): Promise<Booking> {
  const { data } = await apiClient.patch<ApiResponse<Booking>>(
    `/bookings/${id}/reschedule`,
    { newStart, newEnd },
  );
  return data.data;
}
