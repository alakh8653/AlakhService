import { useCallback, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../state/store';
import {
  fetchBookings,
  changeBookingStatus,
  cancelBookingThunk,
  setFilters,
  clearBookingError,
} from '../state/bookingSlice';
import type { BookingFilters } from '../services/bookingService';
import type { BookingStatus } from '../types';

export function useBookings(initialFilters: BookingFilters = {}) {
  const dispatch = useDispatch<AppDispatch>();
  const { bookings, total, page, perPage, totalPages, isLoading, error, activeFilters } =
    useSelector((state: RootState) => state.bookings);

  useEffect(() => {
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

  const changeStatus = useCallback(
    (id: string, status: BookingStatus, reason?: string) =>
      dispatch(changeBookingStatus({ id, status, reason })),
    [dispatch],
  );

  const cancel = useCallback(
    (id: string, reason: string) => dispatch(cancelBookingThunk({ id, reason })),
    [dispatch],
  );

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
    changeStatus,
    cancel,
    dismissError,
  };
}
