import { useState } from 'react';
import { useBookings } from '../hooks/useBookings';
import { useShopServices } from '../hooks/useShopServices';
import BookingCard from '../components/BookingCard';
import { BOOKING_STATUSES } from '../services/bookingService';
import { humanize } from '../services/format';
import type { BookingStatus } from '../types';

export default function BookingsPage() {
  const [activeStatus, setActiveStatus] = useState<BookingStatus | undefined>();
  const { bookings, isLoading, error, applyFilters, goToPage, page, totalPages, changeStatus, cancel, dismissError } =
    useBookings();
  const { serviceNames } = useShopServices();

  const handleFilter = (status?: BookingStatus) => {
    setActiveStatus(status);
    applyFilters(status ? { status } : {});
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
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
            <BookingCard key={b.id} booking={b} serviceName={serviceNames[b.serviceId]} onChangeStatus={changeStatus} onCancel={cancel} />
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
