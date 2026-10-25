import { useEffect, useState, type FormEvent } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import ConfirmDialog from '../components/ConfirmDialog';
import { useToast } from '../components/Toast';
import { formatDate, formatNumber } from '../shared/format';
import { couponState, createCoupon, getCoupons, type Coupon, type NewCoupon } from './CouponService';

const STATE: Record<ReturnType<typeof couponState>, { label: string; className: string }> = {
  active: { label: 'Active', className: 'bg-green-100 text-green-800' },
  expired: { label: 'Expired', className: 'bg-gray-100 text-gray-700' },
  used_up: { label: 'Used up', className: 'bg-yellow-100 text-yellow-800' },
  inactive: { label: 'Inactive', className: 'bg-gray-100 text-gray-700' },
};

const columns: Column<Coupon>[] = [
  { key: 'code', header: 'Code', render: (c) => <span className="font-mono font-semibold">{c.code}</span> },
  { key: 'discountPct', header: 'Discount', render: (c) => `${c.discountPct}% off` },
  {
    key: 'usesCount',
    header: 'Used',
    render: (c) => (c.maxUses ? `${formatNumber(c.usesCount)} of ${formatNumber(c.maxUses)}` : `${formatNumber(c.usesCount)} (no limit)`),
  },
  { key: 'validTo', header: 'Expires', render: (c) => (c.validTo ? formatDate(c.validTo) : 'Never') },
  {
    key: 'isActive',
    header: 'Status',
    render: (c) => {
      const s = STATE[couponState(c)];
      return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${s.className}`}>{s.label}</span>;
    },
  },
];

const CODE_PATTERN = /^[A-Za-z0-9]{3,50}$/;
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date()); // yyyy-MM-dd

export default function CouponsPage() {
  const notify = useToast();
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [code, setCode] = useState('');
  const [discount, setDiscount] = useState('10');
  const [maxUses, setMaxUses] = useState('');
  const [validTo, setValidTo] = useState('');
  const [draft, setDraft] = useState<NewCoupon | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setLoadError(false);
    getCoupons()
      .then(setCoupons)
      .catch(() => setLoadError(true))
      .finally(() => setIsLoading(false));
  }, [reloadKey]);

  const codeInvalid = code.trim() !== '' && !CODE_PATTERN.test(code.trim());
  const pct = Number(discount);
  const discountInvalid = discount !== '' && (!Number.isFinite(pct) || pct < 1 || pct > 50);
  const duplicate = coupons.some((c) => c.code === code.trim().toUpperCase());

  const review = (e: FormEvent) => {
    e.preventDefault();
    if (codeInvalid || discountInvalid || duplicate || !code.trim()) return;
    setDraft({ code: code.trim().toUpperCase(), discountPct: pct, maxUses: maxUses ? Number(maxUses) : null, validTo: validTo || null });
  };

  const create = async () => {
    if (!draft) return;
    const created = await createCoupon(draft);
    setCoupons((list) => [...list, created].sort((a, b) => a.code.localeCompare(b.code)));
    setDraft(null);
    setCode('');
    setMaxUses('');
    setValidTo('');
    notify(`${created.code} is live - customers can use it now.`);
  };

  const field = 'mt-1 block border border-gray-300 rounded-lg px-3 py-2 text-sm';
  const fieldError = 'border-red-500 focus:ring-red-500';
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Coupons</h1>
        <p className="text-sm text-gray-600">Promo codes customers enter when booking. Each customer can use a code once.</p>
      </div>
      <form onSubmit={review} noValidate aria-labelledby="new-coupon" className="bg-white rounded-2xl shadow p-4 space-y-3">
        <h2 id="new-coupon" className="text-base font-semibold text-gray-900">
          New coupon
        </h2>
        <div className="flex flex-wrap gap-3 items-start">
          <label className="text-sm text-gray-700">
            Code
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              className={`${field} font-mono uppercase w-44 ${codeInvalid || duplicate ? fieldError : ''}`}
              placeholder="DIWALI25"
              maxLength={50}
              aria-invalid={codeInvalid || duplicate || undefined}
              aria-describedby="code-hint"
              autoComplete="off"
              spellCheck={false}
              required
            />
            <span id="code-hint" className={`block mt-1 text-xs ${codeInvalid || duplicate ? 'text-red-700' : 'text-gray-500'}`}>
              {duplicate ? 'This code already exists.' : '3–50 letters or digits'}
            </span>
          </label>
          <label className="text-sm text-gray-700">
            Discount %
            <input
              type="number"
              inputMode="numeric"
              min="1"
              max="50"
              value={discount}
              onChange={(e) => setDiscount(e.target.value)}
              className={`${field} w-24 ${discountInvalid ? fieldError : ''}`}
              aria-invalid={discountInvalid || undefined}
              aria-describedby="discount-hint"
              required
            />
            <span id="discount-hint" className={`block mt-1 text-xs ${discountInvalid ? 'text-red-700' : 'text-gray-500'}`}>
              1–50%
            </span>
          </label>
          <label className="text-sm text-gray-700">
            Max uses
            <input
              type="number"
              inputMode="numeric"
              min="1"
              value={maxUses}
              onChange={(e) => setMaxUses(e.target.value)}
              className={`${field} w-28`}
              placeholder="No limit"
            />
            <span className="block mt-1 text-xs text-gray-500">In total, all customers</span>
          </label>
          <label className="text-sm text-gray-700">
            Last day valid
            <input type="date" min={today()} value={validTo} onChange={(e) => setValidTo(e.target.value)} className={field} />
            <span className="block mt-1 text-xs text-gray-500">{validTo ? 'Until 11:59 pm IST' : 'Never expires'}</span>
          </label>
          <button
            type="submit"
            disabled={!code.trim() || codeInvalid || discountInvalid || duplicate || discount === ''}
            className="mt-6 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            Create coupon…
          </button>
        </div>
      </form>
      {loadError && (
        <p role="alert" className="text-sm text-red-700">
          Could not load coupons.{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      <DataTable label="Coupons" columns={columns} rows={coupons} isLoading={isLoading} emptyMessage="No coupons yet. Create one above." />
      {draft && (
        <ConfirmDialog title={`Create ${draft.code}?`} confirmLabel="Create and publish" onConfirm={create} onCancel={() => setDraft(null)}>
          <p>Customers can use it as soon as it is created:</p>
          <ul className="list-disc pl-5">
            <li>
              <strong>{draft.discountPct}% off</strong> a booking
            </li>
            <li>{draft.maxUses ? `Up to ${formatNumber(draft.maxUses)} uses in total` : 'No limit on total uses'} (once per customer)</li>
            <li>{draft.validTo ? `Valid until ${formatDate(`${draft.validTo}T12:00:00+05:30`)}, 11:59 pm IST` : 'Never expires'}</li>
          </ul>
        </ConfirmDialog>
      )}
    </div>
  );
}
