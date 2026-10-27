import { useEffect, useState } from 'react';
import { format, subDays } from 'date-fns';
import ConfirmDialog from '../components/ConfirmDialog';
import DataTable, { type Column } from '../components/DataTable';
import FilterChips from '../components/FilterChips';
import { useToast } from '../components/Toast';
import { apiErrorMessage } from '../shared/apiError';
import { formatDate, shortId } from '../shared/format';
import { createPayoutBatch, downloadPayoutsCsv, formatMoney, getPayouts, markPayoutPaid, type Payout, type PayoutStatus } from './FinanceService';

const PER_PAGE = 20;

const STATUS_STYLES: Record<PayoutStatus, string> = {
  PENDING: 'bg-yellow-100 text-yellow-800',
  PAID: 'bg-green-100 text-green-800',
};

function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Payouts to shops: make a batch, download it for the bank, then mark each payout paid with its UTR. */
export default function PayoutsPanel() {
  const notify = useToast();
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<PayoutStatus | undefined>('PENDING');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [periodTo, setPeriodTo] = useState(() => format(subDays(new Date(), 1), 'yyyy-MM-dd'));
  const [creating, setCreating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [paying, setPaying] = useState<Payout | null>(null);

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError(null);
    getPayouts({ status, page, perPage: PER_PAGE })
      .then((res) => {
        if (!current) return;
        setPayouts(res.data);
        setTotal(res.total);
      })
      .catch(() => {
        if (!current) return;
        setPayouts([]);
        setTotal(0);
        setError('Could not load payouts.');
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [status, page, reloadKey]);

  const createBatch = async () => {
    setCreating(true);
    try {
      const batch = await createPayoutBatch(periodTo);
      notify(
        batch.payouts.length
          ? `${batch.payouts.length} payout${batch.payouts.length === 1 ? '' : 's'} created, ${formatMoney(batch.total)} in all.`
          : 'No shop is owed anything for that period.',
      );
      setStatus('PENDING');
      setPage(1);
      setReloadKey((k) => k + 1);
    } catch (e) {
      notify(apiErrorMessage(e, 'Could not create the payouts.'));
    } finally {
      setCreating(false);
    }
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      saveBlob(await downloadPayoutsCsv(), `payouts-${format(new Date(), 'yyyy-MM-dd')}.csv`);
    } catch {
      notify('Could not download the payouts file.');
    } finally {
      setExporting(false);
    }
  };

  const columns: Column<Payout>[] = [
    {
      key: 'shopId',
      header: 'Shop',
      render: (r) => (
        <span className="font-mono text-xs" title={r.shopId}>
          {shortId(r.shopId)}
        </span>
      ),
    },
    { key: 'amount', header: 'Amount', render: (r) => <span className="tabular-nums">{formatMoney(r.amount, r.currency)}</span> },
    {
      key: 'periodTo',
      header: 'Period',
      render: (r) => `${r.periodFrom ? formatDate(r.periodFrom) : '…'} – ${formatDate(r.periodTo)}`,
      className: 'hidden md:table-cell',
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_STYLES[r.status]}`}>{r.status === 'PAID' ? 'Paid' : 'Pending'}</span>,
    },
    {
      key: 'reference',
      header: 'Reference',
      render: (r) =>
        r.status === 'PAID' ? (
          <span className="text-xs">
            {r.reference} {r.paidAt && <span className="text-gray-500">· {formatDate(r.paidAt)}</span>}
          </span>
        ) : (
          <button type="button" onClick={() => setPaying(r)} className="text-sm font-medium text-indigo-700 hover:underline">
            Mark paid…
          </button>
        ),
    },
  ];

  return (
    <section aria-labelledby="payouts-title" className="space-y-3">
      <div>
        <h2 id="payouts-title" className="text-lg font-semibold text-gray-900">
          Shop payouts
        </h2>
        <p className="text-sm text-gray-600">
          What completed bookings earned each shop after commission and GST. Commission a shop owes for cash bookings is taken off its next payout.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-sm">
          <span className="block text-gray-700">Completed up to</span>
          <input
            type="date"
            value={periodTo}
            onChange={(e) => setPeriodTo(e.target.value)}
            className="mt-1 border border-gray-300 rounded-lg px-3 py-1.5"
          />
        </label>
        <button
          type="button"
          onClick={() => void createBatch()}
          disabled={creating || !periodTo}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {creating ? 'Creating…' : 'Create payouts'}
        </button>
        <button
          type="button"
          onClick={() => void exportCsv()}
          disabled={exporting}
          className="border border-gray-300 bg-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
        >
          {exporting ? 'Downloading…' : 'Download pending (CSV)'}
        </button>
      </div>
      <FilterChips
        label="Filter payouts by status"
        allLabel="All payouts"
        options={[
          { value: 'PENDING' as PayoutStatus, label: 'Pending' },
          { value: 'PAID' as PayoutStatus, label: 'Paid' },
        ]}
        value={status}
        onChange={(s) => {
          setPage(1);
          setStatus(s);
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
        label="Payouts"
        columns={columns}
        rows={payouts}
        isLoading={isLoading}
        total={total}
        page={page}
        perPage={PER_PAGE}
        onPageChange={setPage}
        emptyMessage={status === 'PAID' ? 'No payouts have been paid yet.' : 'No payouts are waiting. Create payouts for a period above.'}
      />
      {paying && (
        <ConfirmDialog
          title={`Mark ${formatMoney(paying.amount, paying.currency)} as paid?`}
          confirmLabel="Mark paid"
          reason={{ label: 'Bank reference (UTR)', required: true, placeholder: 'e.g. HDFC0000123456' }}
          onConfirm={async (reference) => {
            await markPayoutPaid(paying.id, reference);
            setPaying(null);
            notify('Payout marked paid.');
            setReloadKey((k) => k + 1);
          }}
          onCancel={() => setPaying(null)}
        >
          <p>Only after the money has reached the shop's account. The shop sees the reference in its payouts.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
