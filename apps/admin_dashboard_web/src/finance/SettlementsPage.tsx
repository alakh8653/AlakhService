import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import DataTable, { type Column } from '../components/DataTable';
import { formatMoney, getSettlements, SETTLEMENT_STATUSES, type Settlement, type SettlementStatus } from './FinanceService';

const STATUS_COLORS: Record<SettlementStatus, string> = {
  CREATED: 'bg-gray-100 text-gray-700',
  HELD: 'bg-yellow-100 text-yellow-800',
  RELEASED: 'bg-green-100 text-green-800',
  REFUNDED: 'bg-red-100 text-red-800',
};

const STATUS_LABELS: Record<SettlementStatus, string> = {
  CREATED: 'awaiting payment',
  HELD: 'held in escrow',
  RELEASED: 'paid out',
  REFUNDED: 'refunded',
};

const columns: Column<Settlement>[] = [
  { key: 'payeeId', header: 'Provider', render: (r) => <span className="font-mono text-xs">{r.payeeId}</span> },
  { key: 'bookingId', header: 'Booking', render: (r) => <span className="font-mono text-xs">{r.bookingId}</span> },
  { key: 'amount', header: 'Amount', render: (r) => formatMoney(r.amount, r.currency) },
  {
    key: 'status',
    header: 'Status',
    render: (r) => (
      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_COLORS[r.status]}`}>{STATUS_LABELS[r.status]}</span>
    ),
  },
  { key: 'heldAt', header: 'Held', render: (r) => format(new Date(r.heldAt), 'MMM d, yyyy') },
  { key: 'releasedAt', header: 'Paid out', render: (r) => (r.releasedAt ? format(new Date(r.releasedAt), 'MMM d, yyyy') : '—') },
];

export default function SettlementsPage() {
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<SettlementStatus | undefined>();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    getSettlements({ status: statusFilter, page, perPage: 20 })
      .then((res) => {
        setSettlements(res.data);
        setTotal(res.total);
      })
      .catch(() => setError('Failed to load settlements.'))
      .finally(() => setIsLoading(false));
  }, [statusFilter, page]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settlements</h1>
        <p className="text-sm text-gray-500">Customer payments held in escrow until released to the provider.</p>
      </div>
      <div className="flex gap-2 flex-wrap">
        {SETTLEMENT_STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setPage(1);
              setStatusFilter(s === statusFilter ? undefined : s);
            }}
            className={`px-3 py-1 rounded-full text-sm font-medium ${statusFilter === s ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          >
            {STATUS_LABELS[s]}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable
        columns={columns}
        rows={settlements}
        isLoading={isLoading}
        total={total}
        page={page}
        perPage={20}
        onPageChange={setPage}
      />
    </div>
  );
}
