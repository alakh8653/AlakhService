import type { BookingStatus, ServiceMode } from '../types';
import { humanize } from '../services/format';

export const STATUS_COLORS: Record<BookingStatus, string> = {
  PENDING: 'bg-yellow-100 text-yellow-800',
  CONFIRMED: 'bg-blue-100 text-blue-800',
  ASSIGNED: 'bg-cyan-100 text-cyan-800',
  PROVIDER_EN_ROUTE: 'bg-sky-100 text-sky-800',
  PICKED_UP: 'bg-teal-100 text-teal-800',
  IN_PROGRESS: 'bg-purple-100 text-purple-800',
  OUT_FOR_DELIVERY: 'bg-indigo-100 text-indigo-800',
  COMPLETED: 'bg-green-100 text-green-800',
  CANCELLED: 'bg-red-100 text-red-800',
  DISPUTED: 'bg-orange-100 text-orange-800',
  REFUNDED: 'bg-gray-100 text-gray-800',
};

/** Status names in the owner's words; some depend on how the service is delivered. */
export function statusLabel(status: BookingStatus, mode?: ServiceMode): string {
  if (status === 'PENDING') return 'To confirm';
  if (status === 'PROVIDER_EN_ROUTE') return mode === 'AT_SHOP' ? 'Customer arrived' : 'On the way';
  if (status === 'OUT_FOR_DELIVERY') return 'On the way back';
  return humanize(status);
}

export default function StatusBadge({ status, mode }: { status: BookingStatus; mode?: ServiceMode }) {
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-800'}`}>
      {statusLabel(status, mode)}
    </span>
  );
}
