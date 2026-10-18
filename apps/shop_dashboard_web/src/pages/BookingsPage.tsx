import { useCallback, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import { useSearchParams } from 'react-router-dom';
import { format } from 'date-fns';
import { Download, RefreshCw } from 'lucide-react';
import type { RootState } from '../state/store';
import { useBookings } from '../hooks/useBookings';
import { useBookingActions } from '../hooks/useBookingActions';
import { useShopServices } from '../hooks/useShopServices';
import { useStaff } from '../hooks/useStaff';
import BookingCard, { MODE_LABELS } from '../components/BookingCard';
import { useToast } from '../components/Toast';
import {
  BOOKING_STATUSES,
  byScheduledAt,
  getAllShopBookings,
  inWindow,
  windowFilters,
  type BookingFilters,
  type BookingWhen,
} from '../services/bookingService';
import { downloadCsv } from '../services/csv';
import { shortId } from '../services/format';
import { statusLabel as labelFor } from '../components/StatusBadge';
import type { BookingStatus } from '../types';

const WHEN_CHOICES: { value: BookingWhen; label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'Next 7 days' },
  { value: 'all', label: 'All dates' },
];

const EMPTY_TEXT: Record<BookingWhen, string> = {
  today: 'No bookings today.',
  week: 'No bookings in the next 7 days.',
  all: 'No bookings yet. They will appear here as soon as customers book.',
};

const parseWhen = (v: string | null): BookingWhen => (v === 'today' || v === 'week' ? v : 'all');
const parseStatus = (v: string | null): BookingStatus | undefined =>
  BOOKING_STATUSES.includes(v as BookingStatus) ? (v as BookingStatus) : undefined;

/** API filters for a window and status; a window is fetched whole (up to 100) and sorted locally. */
const filtersFor = (when: BookingWhen, status?: BookingStatus): BookingFilters => ({
  ...(status ? { status } : {}),
  ...windowFilters(when),
  ...(when === 'all' ? {} : { perPage: 100 }),
});

function chipClass(active: boolean) {
  return `px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap border ${
    active ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
  }`;
}

export default function BookingsPage() {
  const [params, setParams] = useSearchParams();
  const when = parseWhen(params.get('when'));
  const status = parseStatus(params.get('status'));
  const { bookings, isLoading, error, activeFilters, applyFilters, goToPage, reload, replace, page, totalPages, total } =
    useBookings(filtersFor(when, status));
  const [exporting, setExporting] = useState(false);
  const { serviceNames } = useShopServices();
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const { staff, providers, providerName } = useStaff();
  const actions = useBookingActions(replace, providerName);
  const toast = useToast();

  const shown = useMemo(
    () => (when === 'all' ? bookings : bookings.filter((b) => inWindow(b, when)).sort(byScheduledAt)),
    [bookings, when],
  );

  const statusLabel = status ? labelFor(status) : null;
  const emptyMessage = statusLabel
    ? `No “${statusLabel}” bookings${when === 'today' ? ' today' : when === 'week' ? ' in the next 7 days' : ''}.`
    : EMPTY_TEXT[when];

  const setFilter = useCallback(
    (nextWhen: BookingWhen, nextStatus?: BookingStatus) => {
      const next = new URLSearchParams();
      if (nextWhen !== 'all') next.set('when', nextWhen);
      if (nextStatus) next.set('status', nextStatus);
      setParams(next, { replace: true });
      applyFilters(filtersFor(nextWhen, nextStatus));
    },
    [applyFilters, setParams],
  );

  // Everything matching the current filter, for accounts, GST returns or a spreadsheet.
  const exportCsv = async () => {
    if (!shopId) return;
    setExporting(true);
    try {
      const all = (await getAllShopBookings(shopId, { ...activeFilters, page: undefined, perPage: undefined }))
        .filter((b) => inWindow(b, when));
      const staffName = (id: string | null) => (id ? (staff.find((m) => m.userId === id)?.name ?? shortId(id)) : '');
      downloadCsv(
        `bookings-${format(new Date(), 'yyyy-MM-dd')}.csv`,
        ['Booking', 'Status', 'How', 'Service', 'Scheduled', 'Minutes', 'Customer', 'Staff', 'Item', 'Amount (INR)', 'Notes', 'Booked on'],
        all.map((b) => [
          b.bookingNumber,
          labelFor(b.status, b.serviceMode),
          MODE_LABELS[b.serviceMode] ?? b.serviceMode,
          serviceNames[b.serviceId] ?? shortId(b.serviceId),
          format(new Date(b.scheduledAt), 'yyyy-MM-dd HH:mm'),
          b.durationMinutes,
          shortId(b.customerId),
          staffName(b.providerId),
          b.itemDescription,
          (b.totalAmount / 100).toFixed(2),
          b.notes,
          b.createdAt ? format(new Date(b.createdAt), 'yyyy-MM-dd HH:mm') : '',
        ]),
      );
      toast(all.length === 1 ? 'Downloaded 1 booking.' : `Downloaded ${all.length} bookings.`);
    } catch {
      toast('Could not export bookings. Please try again.', 'error');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
          {!isLoading && (
            <p className="text-sm text-gray-500" aria-live="polite">
              {when === 'all' ? `${total} booking${total === 1 ? '' : 's'}` : `${shown.length} booking${shown.length === 1 ? '' : 's'}`}
              {statusLabel ? ` · ${statusLabel}` : ''}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void reload()}
            disabled={isLoading}
            aria-label="Refresh bookings"
            title="Refresh"
            className="p-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => void exportCsv()}
            disabled={exporting || !shopId}
            className="flex items-center gap-1.5 text-sm border border-gray-300 rounded-lg px-3 py-2 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <Download size={16} aria-hidden />
            {exporting ? 'Exporting…' : <span>Export<span className="hidden sm:inline"> CSV</span></span>}
          </button>
        </div>
      </div>

      <div role="group" aria-label="Dates" className="inline-flex rounded-xl bg-gray-100 p-1">
        {WHEN_CHOICES.map((c) => (
          <button
            type="button"
            key={c.value}
            aria-pressed={when === c.value}
            onClick={() => setFilter(c.value, status)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium ${when === c.value ? 'bg-white shadow text-indigo-700' : 'text-gray-600 hover:text-gray-900'}`}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div role="group" aria-label="Status" className="-mx-4 px-4 md:mx-0 md:px-0 flex gap-2 overflow-x-auto md:flex-wrap pb-1">
        <button type="button" aria-pressed={!status} onClick={() => setFilter(when, undefined)} className={chipClass(!status)}>
          All statuses
        </button>
        {BOOKING_STATUSES.map((s) => (
          <button type="button" key={s} aria-pressed={status === s} onClick={() => setFilter(when, s)} className={chipClass(status === s)}>
            {labelFor(s)}
          </button>
        ))}
      </div>

      {error && (
        <div role="alert" className="text-red-700 bg-red-50 rounded-lg px-3 py-2 text-sm flex items-center justify-between gap-2">
          {error}
          <button type="button" onClick={() => void reload()} className="font-medium underline">
            Try again
          </button>
        </div>
      )}

      {isLoading && shown.length === 0 ? (
        <div className="grid gap-4" aria-busy="true" aria-label="Loading bookings">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bg-white rounded-2xl shadow p-4 h-32 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className={`grid gap-4 ${isLoading ? 'opacity-60' : ''}`} aria-busy={isLoading}>
          {shown.map((b) => (
            <BookingCard
              key={b.id}
              booking={b}
              serviceName={serviceNames[b.serviceId]}
              providers={providers}
              onChangeStatus={actions.changeStatus}
              onAssign={actions.assign}
              onCancel={actions.cancel}
              onSetReadyBy={actions.setReadyBy}
            />
          ))}
          {!error && shown.length === 0 && (
            <div className="bg-white rounded-2xl shadow p-8 text-center space-y-3">
              <p className="text-gray-600">{emptyMessage}</p>
              {(when !== 'all' || status) && (
                <button type="button" onClick={() => setFilter('all')} className="text-sm font-medium text-indigo-600 hover:underline">
                  Show all bookings
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {totalPages > 1 && (
        <nav aria-label="Pages" className="flex items-center gap-3 justify-center pt-2">
          <button
            type="button"
            onClick={() => goToPage(page - 1)}
            disabled={page <= 1 || isLoading}
            className="px-3 py-2 rounded-lg text-sm border border-gray-300 bg-white disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => goToPage(page + 1)}
            disabled={page >= totalPages || isLoading}
            className="px-3 py-2 rounded-lg text-sm border border-gray-300 bg-white disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      )}
    </div>
  );
}
