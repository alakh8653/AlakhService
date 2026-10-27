import { useEffect, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import FilterChips from '../components/FilterChips';
import { formatDate, shortId } from '../shared/format';
import { useAccounts } from '../users/accountNames';
import CommissionPanel from './CommissionPanel';
import { formatMoney, getSettlements, SETTLEMENT_STATUSES, type Settlement, type SettlementStatus } from './FinanceService';
import PayoutsPanel from './PayoutsPanel';

const PER_PAGE = 20;

const STATUS_COLORS: Record<SettlementStatus, string> = {
  CREATED: 'bg-gray-100 text-gray-700',
  HELD: 'bg-yellow-100 text-yellow-800',
  RELEASED: 'bg-green-100 text-green-800',
  REFUNDED: 'bg-red-100 text-red-800',
};

const STATUS_LABELS: Record<SettlementStatus, string> = {
  CREATED: 'Awaiting payment',
  HELD: 'Held in escrow',
  RELEASED: 'Released to shop',
  REFUNDED: 'Refunded',
};

const EMPTY: Record<SettlementStatus | 'ALL', string> = {
  ALL: 'No settlements yet. They appear here once customers pay for bookings.',
  CREATED: 'No settlements are awaiting payment.',
  HELD: 'Nothing is held in escrow right now.',
  RELEASED: 'Nothing has been released to shops yet.',
  REFUNDED: 'No settlements have been refunded.',
};

export default function SettlementsPage() {
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<SettlementStatus | undefined>();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const payees = useAccounts(settlements.map((s) => s.payeeId));

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError(null);
    getSettlements({ status: statusFilter, page, perPage: PER_PAGE })
      .then((res) => {
        if (!current) return;
        setSettlements(res.data);
        setTotal(res.total);
      })
      .catch(() => {
        if (!current) return;
        setSettlements([]);
        setTotal(0);
        setError('Could not load settlements.');
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [statusFilter, page, reloadKey]);

  const columns: Column<Settlement>[] = [
    {
      key: 'payeeId',
      header: 'Provider',
      render: (r) =>
        payees[r.payeeId] ? (
          <span title={r.payeeId}>{payees[r.payeeId].name}</span>
        ) : (
          <span className="font-mono text-xs" title={r.payeeId}>
            {shortId(r.payeeId)}
          </span>
        ),
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
    { key: 'amount', header: 'Amount', render: (r) => <span className="tabular-nums">{formatMoney(r.amount, r.currency)}</span> },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_COLORS[r.status]}`}>{STATUS_LABELS[r.status]}</span>,
    },
    { key: 'heldAt', header: 'Held since', render: (r) => formatDate(r.heldAt), className: 'hidden sm:table-cell' },
    { key: 'releasedAt', header: 'Released', render: (r) => (r.releasedAt ? formatDate(r.releasedAt) : '—'), className: 'hidden lg:table-cell' },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settlements</h1>
        <p className="text-sm text-gray-600">Customer payments held in escrow until the job is done, then released to the shop less commission and paid out in payout batches.</p>
      </div>
      <FilterChips
        label="Filter by status"
        options={SETTLEMENT_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
        value={statusFilter}
        onChange={(s) => {
          setPage(1);
          setStatusFilter(s);
        }}
      />
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      <DataTable failed={!!error}
        label="Settlements"
        columns={columns}
        rows={settlements}
        isLoading={isLoading}
        total={total}
        page={page}
        perPage={PER_PAGE}
        onPageChange={setPage}
        emptyMessage={EMPTY[statusFilter ?? 'ALL']}
      />
      <PayoutsPanel />
      <CommissionPanel />
    </div>
  );
}
