import { useState } from 'react';
import { format } from 'date-fns';
import { Link } from 'react-router-dom';
import { CalendarCheck, Clock, Home, MessageCircle, Package, Store, User, Scissors, UserCog } from 'lucide-react';
import type { Booking, BookingStatus, ServiceMode } from '../types';
import { READY_BY_STATUSES, bookingActions } from '../services/bookingService';
import { formatDayTime, formatMoney, formatWhen, shortId } from '../services/format';
import StatusBadge from './StatusBadge';
import CashDue from './CashDue';
import CancelBookingDialog from './CancelBookingDialog';
import BookingChat from './BookingChat';

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

type Result = Promise<unknown> | void;

interface BookingCardProps {
  booking: Booking;
  serviceName?: string;
  /** Staff who can take bookings (active, with a provider account). */
  providers?: ProviderOption[];
  onChangeStatus: (id: string, status: BookingStatus) => Result;
  onCancel: (id: string, reason: string) => Result;
  onAssign?: (id: string, providerId: string) => Result;
  /** Pickup & drop: promise (ISO datetime) or clear (null) when the item will be back. */
  onSetReadyBy?: (id: string, readyBy: string | null) => Result;
}

/** A datetime-local input's value (local time, to the minute) for an ISO datetime. */
const toLocalInput = (iso: string) => format(new Date(iso), "yyyy-MM-dd'T'HH:mm");

function ReadyByEditor({ booking, busy, onSave }: { booking: Booking; busy: boolean; onSave: (readyBy: string | null) => void }) {
  const [value, setValue] = useState(booking.readyBy ? toLocalInput(booking.readyBy) : '');
  const saved = booking.readyBy ? toLocalInput(booking.readyBy) : '';
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="datetime-local"
        aria-label="Expected back by"
        value={value}
        min={toLocalInput(booking.scheduledAt)}
        onChange={(e) => setValue(e.target.value)}
        className="text-sm border border-gray-300 rounded-lg px-2 py-1.5"
      />
      <button
        type="button"
        disabled={busy || !value || value === saved}
        onClick={() => onSave(new Date(value).toISOString())}
        className="text-sm bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-100 disabled:opacity-50"
      >
        {booking.readyBy ? 'Update' : 'Tell customer'}
      </button>
      {booking.readyBy && (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setValue('');
            onSave(null);
          }}
          className="text-sm text-gray-600 hover:text-gray-900 px-2 py-1.5 disabled:opacity-50"
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
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const actions = bookingActions(booking);
  const stepActions = actions.filter((a) => a.target !== 'CANCEL');
  const canCancel = actions.some((a) => a.target === 'CANCEL');
  const isPickup = booking.serviceMode === 'PICKUP_DROP';
  const canSetReadyBy = isPickup && onSetReadyBy && READY_BY_STATUSES.has(booking.status);
  const ModeIcon = MODE_ICONS[booking.serviceMode] ?? Store;
  const providerName = booking.providerId
    ? (providers.find((p) => p.userId === booking.providerId)?.name ?? `Staff ${shortId(booking.providerId)}`)
    : null;
  const isToday = new Date(booking.scheduledAt).toDateString() === new Date().toDateString();

  // One action at a time per booking: no double taps while the shop's phone is on a slow network.
  const run = async (action: () => Result): Promise<unknown> => {
    setBusy(true);
    try {
      return await action();
    } finally {
      setBusy(false);
    }
  };

  return (
    <article
      aria-label={`Booking #${booking.bookingNumber}`}
      className="bg-white rounded-2xl shadow p-4 flex flex-col sm:flex-row sm:items-start gap-3 sm:gap-4"
    >
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={booking.status} mode={booking.serviceMode} />
          <span className="flex items-center gap-1 text-xs text-gray-700 bg-gray-100 rounded-full px-2 py-0.5">
            <ModeIcon size={12} aria-hidden /> {MODE_LABELS[booking.serviceMode] ?? booking.serviceMode}
          </span>
          <span className="text-xs text-gray-500">#{booking.bookingNumber}</span>
        </div>
        <p className={`text-sm flex items-center gap-1.5 pt-1 ${isToday ? 'font-semibold text-indigo-700' : 'font-medium text-gray-900'}`}>
          <Clock size={14} className="flex-shrink-0" aria-hidden />
          {formatWhen(booking.scheduledAt)}
          <span className="font-normal text-gray-500">· {booking.durationMinutes} min</span>
        </p>
        <p className="font-semibold text-gray-900 flex items-center gap-1.5">
          <Scissors size={14} className="text-gray-400 flex-shrink-0" aria-hidden />
          {serviceName ?? `Service ${shortId(booking.serviceId)}`}
        </p>
        <p className="text-sm text-gray-600 flex items-center gap-1.5">
          <User size={14} className="text-gray-400 flex-shrink-0" aria-hidden /> {booking.customerDisplayName}
          <button
            type="button"
            aria-expanded={chatOpen}
            onClick={() => setChatOpen((open) => !open)}
            className="ml-2 flex items-center gap-1 text-xs font-medium text-indigo-700 hover:underline"
          >
            <MessageCircle size={12} aria-hidden /> {chatOpen ? 'Hide messages' : 'Messages'}
          </button>
        </p>
        {booking.itemDescription && (
          <p className="text-sm text-gray-700">
            <span className="text-gray-500">Item:</span> {booking.itemDescription}
          </p>
        )}
        {booking.serviceMode !== 'AT_SHOP' && booking.addressId && (
          <p className="text-xs text-gray-500">At the customer's saved address {shortId(booking.addressId)}</p>
        )}
        {isPickup && (booking.readyBy || canSetReadyBy) && (
          <div className="text-sm text-gray-600 space-y-1">
            <p className="flex items-center gap-1.5">
              <CalendarCheck size={14} className="text-gray-400" aria-hidden />
              {booking.readyBy ? `Expected back by ${formatDayTime(booking.readyBy)}` : 'No return time given yet'}
            </p>
            {canSetReadyBy && (
              <ReadyByEditor booking={booking} busy={busy} onSave={(at) => void run(() => onSetReadyBy(booking.id, at))} />
            )}
          </div>
        )}
        {providerName && (
          <p className="text-sm text-gray-600 flex items-center gap-1.5">
            <UserCog size={14} className="text-gray-400" aria-hidden /> Staff: {providerName}
          </p>
        )}
        {booking.notes && <p className="text-sm text-gray-600 italic">“{booking.notes}”</p>}
        {chatOpen && <BookingChat bookingId={booking.id} customerName={booking.customerDisplayName} />}
      </div>
      <div className="flex flex-col sm:items-end gap-2 sm:min-w-44">
        <p className="text-lg font-bold text-gray-900">{formatMoney(booking.totalAmount)}</p>
        {CASH_STATUSES.has(booking.status) && <CashDue bookingId={booking.id} />}
        {booking.status === 'CONFIRMED' && onAssign && (
          providers.length > 0 ? (
            <select
              aria-label="Assign to"
              value=""
              disabled={busy}
              onChange={(e) => {
                const providerId = e.target.value;
                if (providerId) void run(() => onAssign(booking.id, providerId));
              }}
              className="text-sm border border-gray-300 rounded-lg px-2 py-2 bg-white"
            >
              <option value="">Assign to staff…</option>
              {providers.map((p) => (
                <option key={p.userId} value={p.userId}>
                  {p.name}
                </option>
              ))}
            </select>
          ) : (
            <p className="text-xs text-gray-500">
              No staff can take bookings yet.{' '}
              <Link to="/staff" className="text-indigo-600 underline">
                Link a staff app account
              </Link>
            </p>
          )
        )}
        {(stepActions.length > 0 || canCancel) && (
          <div className="flex flex-wrap gap-2 sm:justify-end">
            {stepActions.map((action, i) => (
              <button
                type="button"
                key={action.label}
                disabled={busy}
                onClick={() => void run(() => onChangeStatus(booking.id, action.target as BookingStatus))}
                className={`text-sm font-medium rounded-lg px-3 py-2 disabled:opacity-50 ${
                  i === 0
                    ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                    : 'bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100'
                }`}
              >
                {action.label}
              </button>
            ))}
            {canCancel && (
              <button
                type="button"
                disabled={busy}
                onClick={() => setCancelling(true)}
                className="text-sm text-red-700 border border-red-200 rounded-lg px-3 py-2 hover:bg-red-50 disabled:opacity-50"
              >
                Cancel
              </button>
            )}
          </div>
        )}
      </div>
      {cancelling && (
        <CancelBookingDialog
          bookingNumber={booking.bookingNumber}
          onConfirm={(reason) => run(() => onCancel(booking.id, reason))}
          onClose={() => setCancelling(false)}
        />
      )}
    </article>
  );
}
