import React from 'react';
import { format } from 'date-fns';
import type { Booking, BookingStatus } from '../types';
import { Clock, User, Scissors, CheckCircle, XCircle } from 'lucide-react';

interface BookingCardProps {
  booking: Booking;
  onChangeStatus: (id: string, status: BookingStatus) => void;
  onCancel: (id: string, reason: string) => void;
}

const STATUS_COLORS: Record<BookingStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  confirmed: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-purple-100 text-purple-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
  no_show: 'bg-gray-100 text-gray-800',
};

export default function BookingCard({ booking, onChangeStatus, onCancel }: BookingCardProps) {
  const handleCancel = () => {
    const reason = window.prompt('Reason for cancellation:');
    if (reason) onCancel(booking.id, reason);
  };

  return (
    <div className="bg-white rounded-2xl shadow p-4 flex flex-col sm:flex-row sm:items-center gap-4">
      <div className="flex-1 space-y-1">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[booking.status]}`}>
            {booking.status.replace('_', ' ')}
          </span>
          <span className="text-xs text-gray-400">#{booking.bookingNumber}</span>
        </div>
        <p className="font-semibold text-gray-900 flex items-center gap-1.5">
          <User size={14} className="text-gray-400" /> {booking.customer.name}
        </p>
        <p className="text-sm text-gray-500 flex items-center gap-1.5">
          <Scissors size={14} className="text-gray-400" /> {booking.service.name} · {booking.service.durationMinutes} min
        </p>
        <p className="text-sm text-gray-500 flex items-center gap-1.5">
          <Clock size={14} className="text-gray-400" />
          {format(new Date(booking.timeSlot.start), 'MMM d, yyyy h:mm a')}
        </p>
      </div>
      <div className="flex flex-col sm:items-end gap-2">
        <p className="text-lg font-bold text-gray-900">${booking.totalAmount}</p>
        {booking.status === 'pending' && (
          <div className="flex gap-2">
            <button onClick={() => onChangeStatus(booking.id, 'confirmed')} className="flex items-center gap-1 text-xs bg-green-50 text-green-700 border border-green-200 rounded-lg px-3 py-1.5 hover:bg-green-100">
              <CheckCircle size={14} /> Confirm
            </button>
            <button onClick={handleCancel} className="flex items-center gap-1 text-xs bg-red-50 text-red-700 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-100">
              <XCircle size={14} /> Cancel
            </button>
          </div>
        )}
        {booking.status === 'confirmed' && (
          <button onClick={() => onChangeStatus(booking.id, 'completed')} className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-100">
            Mark Complete
          </button>
        )}
      </div>
    </div>
  );
}
