import { useEffect, useState, type FormEvent } from 'react';
import axios from 'axios';
import { format } from 'date-fns';
import DataTable, { type Column } from '../components/DataTable';
import { createCoupon, getCoupons, type Coupon } from './CouponService';

const columns: Column<Coupon>[] = [
  { key: 'code', header: 'Code', render: (c) => <span className="font-mono font-semibold">{c.code}</span> },
  { key: 'discountPct', header: 'Discount', render: (c) => `${c.discountPct}%` },
  { key: 'usesCount', header: 'Used', render: (c) => (c.maxUses ? `${c.usesCount} / ${c.maxUses}` : String(c.usesCount)) },
  { key: 'validTo', header: 'Expires', render: (c) => (c.validTo ? format(new Date(c.validTo), 'MMM d, yyyy') : 'Never') },
  { key: 'isActive', header: 'Status', render: (c) => (c.isActive ? 'Active' : 'Inactive') },
];

export default function CouponsPage() {
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [discount, setDiscount] = useState('10');
  const [maxUses, setMaxUses] = useState('');
  const [validTo, setValidTo] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getCoupons()
      .then(setCoupons)
      .catch(() => setError('Failed to load coupons.'))
      .finally(() => setIsLoading(false));
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await createCoupon({
        code,
        discountPct: Number(discount),
        maxUses: maxUses ? Number(maxUses) : null,
        validTo: validTo || null,
      });
      setCoupons((list) => [...list, created].sort((a, b) => a.code.localeCompare(b.code)));
      setCode('');
    } catch (err) {
      const detail = axios.isAxiosError(err) ? (err.response?.data as { detail?: unknown } | undefined)?.detail : null;
      setError(typeof detail === 'string' ? detail : 'Could not create the coupon. Codes are 3–50 letters/digits and discounts 1–50%.');
    } finally {
      setSaving(false);
    }
  };

  const input = 'border border-gray-300 rounded-lg px-3 py-2 text-sm';
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Coupons</h1>
      <form onSubmit={submit} className="bg-white rounded-2xl shadow p-4 flex flex-wrap gap-3 items-end">
        <label className="text-sm text-gray-700">Code<br /><input aria-label="Code" value={code} onChange={(e) => setCode(e.target.value)} className={input} placeholder="DIWALI25" required /></label>
        <label className="text-sm text-gray-700">Discount %<br /><input aria-label="Discount" type="number" min="1" max="50" value={discount} onChange={(e) => setDiscount(e.target.value)} className={`${input} w-24`} required /></label>
        <label className="text-sm text-gray-700">Max uses<br /><input aria-label="Max uses" type="number" min="1" value={maxUses} onChange={(e) => setMaxUses(e.target.value)} className={`${input} w-28`} placeholder="Unlimited" /></label>
        <label className="text-sm text-gray-700">Expires<br /><input aria-label="Expires" type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)} className={input} /></label>
        <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
          {saving ? 'Creating…' : 'Create coupon'}
        </button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable columns={columns} rows={coupons} isLoading={isLoading} emptyMessage="No coupons yet." />
    </div>
  );
}
