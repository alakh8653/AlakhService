import React, { useState } from 'react';
import { useBookings } from '../hooks/useBookings';
import BookingCard from '../components/BookingCard';
import type { BookingStatus } from '../types';

const STATUSES: BookingStatus[] = ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled'];

export default function BookingsPage() {
  const [activeStatus, setActiveStatus] = useState<BookingStatus | undefined>();
  const { bookings, isLoading, error, applyFilters, goToPage, page, totalPages, changeStatus, cancel } =
    useBookings();

  const handleFilter = (status?: BookingStatus) => {
    setActiveStatus(status);
    applyFilters(status ? { status } : {});
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Bookings</h1>
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => handleFilter(undefined)} className={`px-3 py-1 rounded-full text-sm font-medium ${!activeStatus ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}>All</button>
        {STATUSES.map((s) => (
          <button key={s} onClick={() => handleFilter(s)} className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${activeStatus === s ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}>{s.replace('_', ' ')}</button>
        ))}
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {isLoading ? (
        <p className="text-gray-500">Loading bookings…</p>
      ) : (
        <div className="grid gap-4">
          {bookings.map((b) => (
            <BookingCard key={b.id} booking={b} onChangeStatus={changeStatus} onCancel={cancel} />
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
