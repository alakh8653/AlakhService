import { useCallback, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../state/store';
import { fetchBookings, setFilters, clearBookingError, updateBookingInList } from '../state/bookingSlice';
import type { BookingFilters } from '../services/bookingService';
import type { Booking } from '../types';

export function useBookings(initialFilters: BookingFilters = {}) {
  const dispatch = useDispatch<AppDispatch>();
  const { bookings, total, page, perPage, totalPages, isLoading, error, activeFilters } =
    useSelector((state: RootState) => state.bookings);

  useEffect(() => {
    dispatch(setFilters(initialFilters));
    dispatch(fetchBookings(initialFilters));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyFilters = useCallback(
    (filters: BookingFilters) => {
      dispatch(setFilters(filters));
      dispatch(fetchBookings({ ...filters, page: 1 }));
    },
    [dispatch],
  );

  const goToPage = useCallback(
    (targetPage: number) => {
      dispatch(fetchBookings({ ...activeFilters, page: targetPage }));
    },
    [dispatch, activeFilters],
  );

  const reload = useCallback(() => dispatch(fetchBookings({ ...activeFilters, page })), [dispatch, activeFilters, page]);

  const replace = useCallback((booking: Booking) => dispatch(updateBookingInList(booking)), [dispatch]);

  const dismissError = useCallback(() => dispatch(clearBookingError()), [dispatch]);

  return {
    bookings,
    total,
    page,
    perPage,
    totalPages,
    isLoading,
    error,
    activeFilters,
    applyFilters,
    goToPage,
    reload,
    replace,
    dismissError,
  };
}
