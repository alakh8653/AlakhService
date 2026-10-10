import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import DataTable, { type Column } from '../components/DataTable';
import { DISPUTE_STATUSES, formatStatus, getDisputes, STATUS_COLORS, type Dispute, type DisputeStatus } from './DisputeService';

const PER_PAGE = 20;

const columns: Column<Dispute>[] = [
  { key: 'caseNumber', header: 'Case #', render: (r) => <span className="font-mono text-xs">{r.caseNumber}</span> },
  { key: 'type', header: 'Type', render: (r) => <span className="capitalize">{r.type.replace(/_/g, ' ')}</span> },
  { key: 'bookingId', header: 'Booking' },
  { key: 'raisedBy', header: 'Raised by' },
  {
    key: 'status',
    header: 'Status',
    render: (r) => (
      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[r.status]}`}>
        {formatStatus(r.status)}
      </span>
    ),
  },
  { key: 'createdAt', header: 'Opened', render: (r) => format(new Date(r.createdAt), 'MMM d, yyyy') },
];

export default function DisputeListPage() {
  const navigate = useNavigate();
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<DisputeStatus | undefined>();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    getDisputes({ status: statusFilter, page, perPage: PER_PAGE })
      .then((res) => {
        setDisputes(res.data);
        setTotal(res.total);
      })
      .catch(() => {
        setDisputes([]);
        setTotal(0);
        setError('Failed to load disputes.');
      })
      .finally(() => setIsLoading(false));
  }, [statusFilter, page]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Disputes</h1>
      <div className="flex gap-2 flex-wrap">
        {DISPUTE_STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setPage(1);
              setStatusFilter(s === statusFilter ? undefined : s);
            }}
            className={`px-3 py-1 rounded-full text-sm font-medium capitalize ${statusFilter === s ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          >
            {formatStatus(s)}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable
        columns={columns}
        rows={disputes}
        isLoading={isLoading}
        total={total}
        page={page}
        perPage={PER_PAGE}
        onPageChange={setPage}
        onRowClick={(row) => navigate(`/disputes/${row.id}`)}
      />
    </div>
  );
}
