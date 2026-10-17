import { useEffect, useMemo, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { getStaff } from '../services/shopService';
import { useBookings } from '../hooks/useBookings';
import { useShopServices } from '../hooks/useShopServices';
import BookingCard, { type ProviderOption } from '../components/BookingCard';
import { format } from 'date-fns';
import { BOOKING_STATUSES, getAllShopBookings } from '../services/bookingService';
import { downloadCsv } from '../services/csv';
import { humanize, shortId } from '../services/format';
import { MODE_LABELS } from '../components/BookingCard';
import type { BookingStatus, StaffMember } from '../types';

export default function BookingsPage() {
  const [activeStatus, setActiveStatus] = useState<BookingStatus | undefined>();
  const {
    bookings,
    isLoading,
    error,
    activeFilters,
    applyFilters,
    goToPage,
    page,
    totalPages,
    changeStatus,
    assign,
    cancel,
    setReadyBy,
    dismissError,
  } = useBookings();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const { serviceNames } = useShopServices();
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [staff, setStaff] = useState<StaffMember[]>([]);

  useEffect(() => {
    if (!shopId) return;
    getStaff(shopId).then(setStaff).catch(() => setStaff([]));
  }, [shopId]);

  // Bookings go to active staff who have a provider account to run them with.
  const providers = useMemo<ProviderOption[]>(
    () => staff.filter((m) => m.isActive && m.userId).map((m) => ({ userId: m.userId as string, name: m.name })),
    [staff],
  );

  // Everything matching the current filter, for accounts, GST returns or a spreadsheet.
  const exportCsv = async () => {
    if (!shopId) return;
    setExporting(true);
    setExportError(null);
    try {
      const all = await getAllShopBookings(shopId, activeFilters);
      const staffName = (id: string | null) =>
        id ? (staff.find((m) => m.userId === id)?.name ?? shortId(id)) : '';
      downloadCsv(
        `bookings-${format(new Date(), 'yyyy-MM-dd')}.csv`,
        ['Booking', 'Status', 'How', 'Service', 'Scheduled', 'Minutes', 'Customer', 'Provider', 'Item', 'Amount (INR)', 'Notes', 'Booked on'],
        all.map((b) => [
          b.bookingNumber,
          humanize(b.status),
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
    } catch {
      setExportError('Could not export bookings. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  const handleFilter = (status?: BookingStatus) => {
    setActiveStatus(status);
    applyFilters(status ? { status } : {});
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
        <button
          onClick={exportCsv}
          disabled={exporting || !shopId}
          className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>
      {exportError && <p className="text-red-600 text-sm">{exportError}</p>}
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => handleFilter(undefined)} className={`px-3 py-1 rounded-full text-sm font-medium ${!activeStatus ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}>All</button>
        {BOOKING_STATUSES.map((s) => (
          <button key={s} onClick={() => handleFilter(s)} className={`px-3 py-1 rounded-full text-sm font-medium ${activeStatus === s ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}>{humanize(s)}</button>
        ))}
      </div>
      {error && (
        <p className="text-red-600 bg-red-50 rounded px-3 py-2 text-sm flex justify-between">
          {error}
          <button onClick={dismissError} className="text-red-400 hover:text-red-600">Dismiss</button>
        </p>
      )}
      {isLoading ? (
        <p className="text-gray-500">Loading bookings…</p>
      ) : (
        <div className="grid gap-4">
          {bookings.map((b) => (
            <BookingCard key={b.id} booking={b} serviceName={serviceNames[b.serviceId]} providers={providers} onChangeStatus={changeStatus} onAssign={assign} onCancel={cancel} onSetReadyBy={setReadyBy} />
          ))}
          {bookings.length === 0 && <p className="text-gray-400 text-center py-10">No bookings found.</p>}
        </div>
      )}
      {totalPages > 1 && (
        <div className="flex gap-2 justify-center pt-4">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button key={p} onClick={() => goToPage(p)} className={`w-8 h-8 rounded-full text-sm ${p === page ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}>{p}</button>
          ))}
        </div>
      )}
    </div>
  );
}
