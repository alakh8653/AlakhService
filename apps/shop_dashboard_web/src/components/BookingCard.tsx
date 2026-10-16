import { useState } from 'react';
import { format } from 'date-fns';
import { CalendarCheck, Clock, Home, Package, Store, User, Scissors } from 'lucide-react';
import type { Booking, BookingStatus, ServiceMode } from '../types';
import { READY_BY_STATUSES, bookingActions } from '../services/bookingService';
import { formatMoney, shortId } from '../services/format';
import StatusBadge from './StatusBadge';
import CashDue from './CashDue';

// Bookings a customer may already have chosen to pay in cash for.
const CASH_STATUSES = new Set<BookingStatus>([
  'CONFIRMED',
  'ASSIGNED',
  'PROVIDER_EN_ROUTE',
  'PICKED_UP',
  'IN_PROGRESS',
  'OUT_FOR_DELIVERY',
  'COMPLETED',
]);

export const MODE_LABELS: Record<ServiceMode, string> = {
  AT_SHOP: 'At the shop',
  AT_HOME: 'Home visit',
  PICKUP_DROP: 'Pickup & drop',
};
const MODE_ICONS = { AT_SHOP: Store, AT_HOME: Home, PICKUP_DROP: Package };

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
  /** Pickup & drop: promise (ISO datetime) or clear (null) when the item will be back. */
  onSetReadyBy?: (id: string, readyBy: string | null) => void;
}

/** A datetime-local input's value (local time, to the minute) for an ISO datetime. */
const toLocalInput = (iso: string) => format(new Date(iso), "yyyy-MM-dd'T'HH:mm");

function ReadyByEditor({ booking, onSave }: { booking: Booking; onSave: (readyBy: string | null) => void }) {
  const [value, setValue] = useState(booking.readyBy ? toLocalInput(booking.readyBy) : '');
  const saved = booking.readyBy ? toLocalInput(booking.readyBy) : '';
  return (
    <div className="flex items-center gap-1">
      <input
        type="datetime-local"
        aria-label="Expected back by"
        value={value}
        min={toLocalInput(booking.scheduledAt)}
        onChange={(e) => setValue(e.target.value)}
        className="text-xs border border-gray-300 rounded-lg px-2 py-1"
      />
      <button
        disabled={!value || value === saved}
        onClick={() => onSave(new Date(value).toISOString())}
        className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg px-2 py-1 hover:bg-indigo-100 disabled:opacity-50"
      >
        {booking.readyBy ? 'Update' : 'Tell customer'}
      </button>
      {booking.readyBy && (
        <button
          onClick={() => {
            setValue('');
            onSave(null);
          }}
          className="text-xs text-gray-500 hover:text-gray-700 px-1"
        >
          Clear
        </button>
      )}
    </div>
  );
}

export default function BookingCard({
  booking,
  serviceName,
  providers = [],
  onChangeStatus,
  onCancel,
  onAssign,
  onSetReadyBy,
}: BookingCardProps) {
  const actions = bookingActions(booking);
  const isPickup = booking.serviceMode === 'PICKUP_DROP';
  const canSetReadyBy = isPickup && onSetReadyBy && READY_BY_STATUSES.has(booking.status);
  const ModeIcon = MODE_ICONS[booking.serviceMode] ?? Store;
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
          <span className="flex items-center gap-1 text-xs text-gray-600 bg-gray-100 rounded-full px-2 py-0.5">
            <ModeIcon size={12} /> {MODE_LABELS[booking.serviceMode] ?? booking.serviceMode}
          </span>
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
        {booking.itemDescription && (
          <p className="text-sm text-gray-700">
            <span className="text-gray-500">Item:</span> {booking.itemDescription}
          </p>
        )}
        {booking.serviceMode !== 'AT_SHOP' && booking.addressId && (
          <p className="text-xs text-gray-400">At the customer's saved address {shortId(booking.addressId)}</p>
        )}
        {isPickup && (booking.readyBy || canSetReadyBy) && (
          <div className="text-sm text-gray-500 space-y-1">
            <p className="flex items-center gap-1.5">
              <CalendarCheck size={14} className="text-gray-400" />
              {booking.readyBy
                ? `Expected back by ${format(new Date(booking.readyBy), 'MMM d, h:mm a')}`
                : 'No return time given yet'}
            </p>
            {canSetReadyBy && <ReadyByEditor booking={booking} onSave={(at) => onSetReadyBy(booking.id, at)} />}
          </div>
        )}
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
