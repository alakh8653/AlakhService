import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import DataTable, { type Column } from '../components/DataTable';
import FilterChips from '../components/FilterChips';
import { formatDate, shortId } from '../shared/format';
import { useAccounts } from '../users/accountNames';
import { DISPUTE_STATUSES, formatStatus, getDisputes, STATUS_COLORS, type Dispute, type DisputeStatus } from './DisputeService';

const PER_PAGE = 20;

const EMPTY: Record<DisputeStatus | 'ALL', string> = {
  ALL: 'No disputes have been raised yet.',
  OPEN: 'No open disputes - nothing is waiting for review.',
  UNDER_REVIEW: 'No disputes are under review.',
  ESCALATED: 'No escalated disputes.',
  RESOLVED: 'No resolved disputes yet.',
};

const isStatus = (s: string | null): s is DisputeStatus => !!s && (DISPUTE_STATUSES as string[]).includes(s);

export default function DisputeListPage() {
  const navigate = useNavigate();
  // Filter and page live in the URL, so "Back" from a case returns to the same view.
  const [params, setParams] = useSearchParams();
  const rawStatus = params.get('status');
  const statusFilter = isStatus(rawStatus) ? rawStatus : undefined;
  const page = Math.max(1, Number(params.get('page')) || 1);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const people = useAccounts(disputes.map((d) => d.raisedBy));

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError(null);
    getDisputes({ status: statusFilter, page, perPage: PER_PAGE })
      .then((res) => {
        if (!current) return;
        setDisputes(res.data);
        setTotal(res.total);
      })
      .catch(() => {
        if (!current) return;
        setDisputes([]);
        setTotal(0);
        setError('Could not load disputes.');
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [statusFilter, page, reloadKey]);

  const update = (status: DisputeStatus | undefined, nextPage: number) => {
    const next = new URLSearchParams();
    if (status) next.set('status', status);
    if (nextPage > 1) next.set('page', String(nextPage));
    setParams(next);
  };

  const columns: Column<Dispute>[] = [
    {
      key: 'caseNumber',
      header: 'Case',
      render: (r) => (
        <Link
          to={`/disputes/${r.id}`}
          tabIndex={-1}
          onClick={(e) => e.stopPropagation()}
          className="font-mono text-xs font-semibold text-indigo-700 hover:underline"
        >
          #{r.caseNumber}
        </Link>
      ),
    },
    { key: 'type', header: 'Type', render: (r) => <span className="capitalize">{r.type.replace(/_/g, ' ')}</span>, className: 'hidden sm:table-cell' },
    {
      key: 'raisedBy',
      header: 'Raised by',
      render: (r) => {
        const person = people[r.raisedBy];
        return person ? (
          <span className="block leading-tight">
            {person.name}
            <span className="block text-xs text-gray-500">{person.email ?? person.phone}</span>
          </span>
        ) : (
          <span className="font-mono text-xs" title={r.raisedBy}>
            {shortId(r.raisedBy)}
          </span>
        );
      },
    },
    {
      key: 'bookingId',
      header: 'Booking',
      render: (r) => (
        <span className="font-mono text-xs" title={r.bookingId}>
          {shortId(r.bookingId)}
        </span>
      ),
      className: 'hidden md:table-cell',
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[r.status]}`}>{formatStatus(r.status)}</span>
      ),
    },
    { key: 'createdAt', header: 'Opened', render: (r) => formatDate(r.createdAt), className: 'hidden sm:table-cell' },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Disputes</h1>
        <p className="text-sm text-gray-600">Open a case to review it, message the parties, refund or resolve it.</p>
      </div>
      <FilterChips
        label="Filter by status"
        options={DISPUTE_STATUSES.map((s) => ({ value: s, label: formatStatus(s).replace(/^\w/, (c) => c.toUpperCase()) }))}
        value={statusFilter}
        onChange={(s) => update(s, 1)}
      />
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      <DataTable
        label="Disputes"
        columns={columns}
        rows={disputes}
        isLoading={isLoading}
        total={total}
        page={page}
        perPage={PER_PAGE}
        onPageChange={(p) => update(statusFilter, p)}
        onRowClick={(row) => navigate(`/disputes/${row.id}`)}
        rowLabel={(row) => `Open case ${row.caseNumber}, ${formatStatus(row.status)}`}
        emptyMessage={EMPTY[statusFilter ?? 'ALL']}
      />
    </div>
  );
}
