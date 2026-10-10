import type { BookingStatus } from '../types';
import { humanize } from '../services/format';

export const STATUS_COLORS: Record<BookingStatus, string> = {
  PENDING: 'bg-yellow-100 text-yellow-800',
  CONFIRMED: 'bg-blue-100 text-blue-800',
  ASSIGNED: 'bg-cyan-100 text-cyan-800',
  PROVIDER_EN_ROUTE: 'bg-sky-100 text-sky-800',
  IN_PROGRESS: 'bg-purple-100 text-purple-800',
  COMPLETED: 'bg-green-100 text-green-800',
  CANCELLED: 'bg-red-100 text-red-800',
  DISPUTED: 'bg-orange-100 text-orange-800',
  REFUNDED: 'bg-gray-100 text-gray-800',
};

export default function StatusBadge({ status }: { status: BookingStatus }) {
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-800'}`}>
      {humanize(status)}
    </span>
  );
}
