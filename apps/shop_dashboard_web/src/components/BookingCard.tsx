import { format } from 'date-fns';
import { Clock, User, Scissors } from 'lucide-react';
import type { Booking, BookingStatus } from '../types';
import { BOOKING_ACTIONS } from '../services/bookingService';
import { formatMoney, shortId } from '../services/format';
import StatusBadge from './StatusBadge';
import CashDue from './CashDue';

// Bookings a customer may already have chosen to pay in cash for.
const CASH_STATUSES = new Set<BookingStatus>(['CONFIRMED', 'ASSIGNED', 'PROVIDER_EN_ROUTE', 'IN_PROGRESS', 'COMPLETED']);

export interface ProviderOption {
  userId: string;
  name: string;
}

interface BookingCardProps {
  booking: Booking;
  serviceName?: string;
  /** Staff who can take bookings (active, with a provider account). */
  providers?: ProviderOption[];
  onChangeStatus: (id: string, status: BookingStatus) => void;
  onCancel: (id: string, reason: string) => void;
  onAssign?: (id: string, providerId: string) => void;
}

export default function BookingCard({
  booking,
  serviceName,
  providers = [],
  onChangeStatus,
  onCancel,
  onAssign,
}: BookingCardProps) {
  const actions = BOOKING_ACTIONS[booking.status] ?? [];
  const providerName = booking.providerId
    ? (providers.find((p) => p.userId === booking.providerId)?.name ?? `Provider ${shortId(booking.providerId)}`)
    : null;

  const handleCancel = () => {
    const reason = window.prompt('Reason for cancellation:');
    if (reason) onCancel(booking.id, reason);
  };

  return (
    <div className="bg-white rounded-2xl shadow p-4 flex flex-col sm:flex-row sm:items-center gap-4">
      <div className="flex-1 space-y-1">
        <div className="flex items-center gap-2">
          <StatusBadge status={booking.status} />
          <span className="text-xs text-gray-400">#{booking.bookingNumber}</span>
        </div>
        <p className="font-semibold text-gray-900 flex items-center gap-1.5">
          <User size={14} className="text-gray-400" /> Customer {shortId(booking.customerId)}
        </p>
        <p className="text-sm text-gray-500 flex items-center gap-1.5">
          <Scissors size={14} className="text-gray-400" /> {serviceName ?? `Service ${shortId(booking.serviceId)}`} · {booking.durationMinutes} min
        </p>
        <p className="text-sm text-gray-500 flex items-center gap-1.5">
          <Clock size={14} className="text-gray-400" />
          {format(new Date(booking.scheduledAt), 'MMM d, yyyy h:mm a')}
        </p>
        {providerName && <p className="text-sm text-gray-500">Provider: {providerName}</p>}
        {booking.notes && <p className="text-xs text-gray-400 italic">{booking.notes}</p>}
      </div>
      <div className="flex flex-col sm:items-end gap-2">
        <p className="text-lg font-bold text-gray-900">{formatMoney(booking.totalAmount)}</p>
        {CASH_STATUSES.has(booking.status) && <CashDue bookingId={booking.id} />}
        {booking.status === 'CONFIRMED' && onAssign && (
          <select
            aria-label="Assign to"
            value=""
            onChange={(e) => e.target.value && onAssign(booking.id, e.target.value)}
            className="text-xs border border-gray-300 rounded-lg px-2 py-1.5"
          >
            <option value="">{providers.length ? 'Assign to…' : 'No staff with a provider account'}</option>
            {providers.map((p) => (
              <option key={p.userId} value={p.userId}>{p.name}</option>
            ))}
          </select>
        )}
        {actions.length > 0 && (
          <div className="flex gap-2">
            {actions.map((action) =>
              action.target === 'CANCEL' ? (
                <button key={action.label} onClick={handleCancel} className="text-xs bg-red-50 text-red-700 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-100">
                  {action.label}
                </button>
              ) : (
                <button key={action.label} onClick={() => onChangeStatus(booking.id, action.target as BookingStatus)} className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-100">
                  {action.label}
                </button>
              ),
            )}
          </div>
        )}
      </div>
    </div>
  );
}
