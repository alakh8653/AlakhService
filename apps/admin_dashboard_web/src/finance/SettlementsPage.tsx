import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import DataTable, { type Column } from '../components/DataTable';
import { formatMoney, getSettlements, type Settlement, type SettlementStatus } from './FinanceService';

const STATUS_COLORS: Record<SettlementStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

const columns: Column<Settlement>[] = [
  { key: 'shopName', header: 'Shop' },
  { key: 'amount', header: 'Amount', render: (r) => formatMoney(r.amount, r.currency) },
  {
    key: 'periodStart',
    header: 'Period',
    render: (r) => `${format(new Date(r.periodStart), 'MMM d')} – ${format(new Date(r.periodEnd), 'MMM d, yyyy')}`,
  },
  {
    key: 'status',
    header: 'Status',
    render: (r) => (
      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[r.status]}`}>{r.status}</span>
    ),
  },
  { key: 'createdAt', header: 'Created', render: (r) => format(new Date(r.createdAt), 'MMM d, yyyy') },
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
      <h1 className="text-2xl font-bold text-gray-900">Settlements</h1>
      <div className="flex gap-2 flex-wrap">
        {(Object.keys(STATUS_COLORS) as SettlementStatus[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setPage(1);
              setStatusFilter(s === statusFilter ? undefined : s);
            }}
            className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${statusFilter === s ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          >
            {s}
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
