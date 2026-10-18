import { useMemo } from 'react';
import { useToast } from '../components/Toast';
import { assignProvider, cancelBooking, setReadyBy, updateBookingStatus } from '../services/bookingService';
import { apiErrorMessage, formatDayTime } from '../services/format';
import type { Booking, BookingStatus } from '../types';

/** What the owner is told once a step is saved. */
export const STATUS_DONE: Partial<Record<BookingStatus, string>> = {
  CONFIRMED: 'confirmed. The customer has been told.',
  PROVIDER_EN_ROUTE: 'marked on the way.',
  PICKED_UP: 'marked as picked up.',
  IN_PROGRESS: 'started.',
  OUT_FOR_DELIVERY: 'on its way back to the customer.',
  COMPLETED: 'completed.',
};

/**
 * Booking actions with feedback: each resolves to true when saved (after a success toast and
 * [onUpdated] with the fresh booking) or false when it failed (after an error toast).
 */
export function useBookingActions(onUpdated: (booking: Booking) => void, providerName?: (id: string) => string | undefined) {
  const toast = useToast();

  return useMemo(() => {
    const perform = async (action: () => Promise<Booking>, success: (b: Booking) => string, failure: string) => {
      try {
        const updated = await action();
        onUpdated(updated);
        toast(success(updated));
        return true;
      } catch (err) {
        toast(apiErrorMessage(err, failure), 'error');
        return false;
      }
    };

    return {
      changeStatus: (id: string, status: BookingStatus) =>
        perform(
          () => updateBookingStatus(id, status),
          (b) => `Booking #${b.bookingNumber} ${STATUS_DONE[status] ?? 'updated.'}`,
          'Could not update the booking',
        ),
      assign: (id: string, providerId: string) =>
        perform(
          () => assignProvider(id, providerId),
          (b) => `Booking #${b.bookingNumber} assigned to ${providerName?.(providerId) ?? 'staff'}.`,
          'Could not assign the booking',
        ),
      cancel: (id: string, reason: string) =>
        perform(
          () => cancelBooking(id, reason),
          (b) => `Booking #${b.bookingNumber} cancelled. The customer has been told.`,
          'Could not cancel the booking',
        ),
      setReadyBy: (id: string, readyBy: string | null) =>
        perform(
          () => setReadyBy(id, readyBy),
          (b) =>
            b.readyBy
              ? `Customer told their item will be back by ${formatDayTime(b.readyBy)}.`
              : 'Return time cleared.',
          'Could not save the return time',
        ),
    };
  }, [onUpdated, providerName, toast]);
}
