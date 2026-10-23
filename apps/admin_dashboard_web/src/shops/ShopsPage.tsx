import { useCallback, useEffect, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import FilterChips from '../components/FilterChips';
import Modal from '../components/Modal';
import { apiErrorMessage } from '../shared/apiError';
import { formatDate } from '../shared/format';
import { useDebouncedValue } from '../shared/useDebouncedValue';
import ShopReviewCard, { StatusBadge } from './ShopReviewCard';
import {
  STATUS_LABELS,
  getReviewQueue,
  getShopForReview,
  listShops,
  type AdminShop,
  type ShopForReview,
  type VerificationStatus,
} from './ShopReviewService';

const PER_PAGE = 25;
type Tab = 'queue' | 'all';

const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as VerificationStatus[]).map((value) => ({ value, label: STATUS_LABELS[value] }));

function ReviewQueue() {
  const [shops, setShops] = useState<ShopForReview[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReviewQueue()
      .then(setShops)
      .catch((e) => setError(apiErrorMessage(e, 'Could not load the review queue.')))
      .finally(() => setIsLoading(false));
  }, []);

  // A decided shop leaves the queue.
  const onDecided = useCallback((shop: AdminShop) => setShops((list) => list.filter((s) => s.id !== shop.id)), []);

  if (isLoading) return <p role="status" className="text-sm text-gray-500">Loading…</p>;
  if (error)
    return (
      <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
        {error}
      </p>
    );
  if (shops.length === 0) return <p className="bg-white rounded-xl shadow p-6 text-sm text-gray-600">No shops are waiting for review.</p>;
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600">
        {shops.length} {shops.length === 1 ? 'shop is' : 'shops are'} waiting, oldest submission first.
      </p>
      {shops.map((s) => (
        <ShopReviewCard key={s.id} shop={s} onDecided={onDecided} />
      ))}
    </div>
  );
}

function AllShops() {
  const [status, setStatus] = useState<VerificationStatus | undefined>();
  const [query, setQuery] = useState('');
  const q = useDebouncedValue(query.trim());
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<AdminShop[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [open, setOpen] = useState<ShopForReview | null>(null);

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError(null);
    listShops({ status, q, page, perPage: PER_PAGE })
      .then((res) => {
        if (!current) return;
        setRows(res.data);
        setTotal(res.total);
      })
      .catch((e) => current && setError(apiErrorMessage(e, 'Could not load shops.')))
      .finally(() => current && setIsLoading(false));
    return () => {
      current = false;
    };
  }, [status, q, page, reloadKey]);

  const openShop = async (shop: AdminShop) => {
    try {
      setOpen(await getShopForReview(shop.id));
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not open that shop.'));
    }
  };

  const columns: Column<AdminShop>[] = [
    { key: 'name', header: 'Shop', render: (s) => <span className="font-medium">{s.name}</span> },
    { key: 'legalName', header: 'Legal name', className: 'hidden md:table-cell', render: (s) => s.legalName ?? '—' },
    { key: 'city', header: 'City', className: 'hidden sm:table-cell', render: (s) => s.city ?? '—' },
    { key: 'status', header: 'Status', render: (s) => <StatusBadge status={s.status} /> },
    { key: 'isActive', header: 'Open', className: 'hidden lg:table-cell', render: (s) => (s.isActive ? 'Yes' : 'Closed') },
    { key: 'createdAt', header: 'Joined', className: 'hidden lg:table-cell', render: (s) => formatDate(s.createdAt) },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:justify-between">
        <FilterChips
          label="Filter by status"
          options={STATUS_OPTIONS}
          value={status}
          onChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
        />
        <label className="text-sm text-gray-700">
          <span className="sr-only">Search shops</span>
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Name, legal name, GSTIN or city"
            className="w-full sm:w-72 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </label>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <DataTable
        label="Shops"
        columns={columns}
        rows={rows}
        isLoading={isLoading}
        total={total}
        page={page}
        perPage={PER_PAGE}
        onPageChange={setPage}
        onRowClick={(s) => void openShop(s)}
        rowLabel={(s) => `Review ${s.name}`}
        emptyMessage="No shops match."
      />
      {open && (
        <Modal title="Shop review" onClose={() => setOpen(null)} size="lg">
          <ShopReviewCard
            shop={open}
            onDecided={() => {
              setOpen(null);
              setReloadKey((k) => k + 1);
            }}
          />
          <div className="flex justify-end">
            <button type="button" onClick={() => setOpen(null)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
              Close
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

/** Shop onboarding: the KYC review queue, and every shop by verification status. */
export default function ShopsPage() {
  const [tab, setTab] = useState<Tab>('queue');
  const tabClass = (selected: boolean) =>
    `px-4 py-2 text-sm font-medium border-b-2 -mb-px ${selected ? 'border-indigo-600 text-indigo-700' : 'border-transparent text-gray-600 hover:text-gray-900'}`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Shops</h1>
        <p className="text-sm text-gray-600">
          New shops stay hidden from customers until their KYC documents are checked and approved here.
        </p>
      </div>
      <div role="group" aria-label="View" className="flex gap-2 border-b border-gray-200">
        <button type="button" aria-pressed={tab === 'queue'} onClick={() => setTab('queue')} className={tabClass(tab === 'queue')}>
          Review queue
        </button>
        <button type="button" aria-pressed={tab === 'all'} onClick={() => setTab('all')} className={tabClass(tab === 'all')}>
          All shops
        </button>
      </div>
      {tab === 'queue' ? <ReviewQueue /> : <AllShops />}
    </div>
  );
}
