import { useEffect, useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import type { Service } from '../types';
import { getServices } from '../services/shopService';
import { createPackage, getPackages, setPackageActive, type ServicePackage } from '../services/packageService';
import { apiErrorMessage, formatMoney } from '../services/format';
import { useToast } from '../components/Toast';

const card = 'bg-white rounded-xl border border-gray-200 p-4 md:p-6';
const inputClass = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

/** Prepaid packages: e.g. 5 haircuts for the price of 4, paid upfront and booked one visit at a time. */
export default function PackagesPage() {
  const shop = useSelector((state: RootState) => state.auth.shop);
  const toast = useToast();
  const [packages, setPackages] = useState<ServicePackage[] | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ serviceId: '', name: '', visits: '5', price: '', validDays: '90' });
  const [saving, setSaving] = useState(false);
  const shopId = shop?.id;

  useEffect(() => {
    if (!shopId) return;
    let live = true;
    getPackages(shopId)
      .then((p) => live && setPackages(p))
      .catch((e) => live && setError(apiErrorMessage(e, 'Could not load your packages.')));
    getServices(shopId)
      .then((s) => live && setServices(s.filter((x) => x.isActive)))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [shopId]);

  if (!shop) return null;
  const serviceName = (id: string) => services.find((s) => s.id === id)?.name ?? 'A service';
  const chosen = services.find((s) => s.id === form.serviceId);
  const visits = Number(form.visits);
  const priceCents = Math.round(Number(form.price) * 100);
  const fullPrice = chosen ? chosen.priceCents * visits : 0;
  const valid = !!chosen && form.name.trim().length >= 2 && visits >= 2 && visits <= 50 && priceCents >= 100 && Number(form.validDays) >= 7;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid || saving || !shopId) return;
    setSaving(true);
    try {
      const created = await createPackage(shopId, {
        serviceId: form.serviceId,
        name: form.name,
        visits,
        priceCents,
        validDays: Number(form.validDays),
      });
      setPackages((p) => [created, ...(p ?? [])]);
      setForm((f) => ({ ...f, name: '', price: '' }));
      toast(`${created.name} is on sale. Customers see it on the service's page.`);
    } catch (err) {
      toast(apiErrorMessage(err, 'Could not add the package'), 'error');
    } finally {
      setSaving(false);
    }
  }

  async function toggle(p: ServicePackage) {
    try {
      const updated = await setPackageActive(p.id, !p.isActive);
      setPackages((list) => (list ?? []).map((x) => (x.id === p.id ? updated : x)));
      toast(updated.isActive ? `${updated.name} is on sale again.` : `${updated.name} is off sale. Customers who bought it keep their visits.`);
    } catch (err) {
      toast(apiErrorMessage(err, 'Could not update the package'), 'error');
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Packages</h1>
        <p className="text-sm text-gray-500">
          Sell visits of a service together, paid upfront. You earn each visit&apos;s share (less commission) when it is completed.
        </p>
      </div>

      <form onSubmit={submit} className={`${card} grid gap-4 md:grid-cols-2 max-w-3xl`} aria-label="New package">
        <label className="text-sm text-gray-700">
          Service
          <select className={inputClass} value={form.serviceId} onChange={(e) => setForm({ ...form, serviceId: e.target.value })}>
            <option value="">Choose a service</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({formatMoney(s.priceCents)})
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-gray-700">
          Name customers see
          <input className={inputClass} value={form.name} maxLength={100} placeholder="5 haircuts" onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <label className="text-sm text-gray-700">
          Visits
          <input className={inputClass} type="number" min={2} max={50} value={form.visits} onChange={(e) => setForm({ ...form, visits: e.target.value })} />
        </label>
        <label className="text-sm text-gray-700">
          Price (₹)
          <input className={inputClass} type="number" min={1} step="1" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
        </label>
        <label className="text-sm text-gray-700">
          Valid for (days)
          <input className={inputClass} type="number" min={7} max={730} value={form.validDays} onChange={(e) => setForm({ ...form, validDays: e.target.value })} />
        </label>
        <div className="text-sm text-gray-600 self-end">
          {chosen && priceCents > 0 && fullPrice > priceCents && <>Customers save {formatMoney(fullPrice - priceCents)} against {formatMoney(fullPrice)}.</>}
        </div>
        <div className="md:col-span-2">
          <button type="submit" disabled={!valid || saving} className="bg-indigo-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50">
            {saving ? 'Adding…' : 'Add package'}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="text-sm text-gray-700 bg-gray-100 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      {packages && (
        <ul className={`${card} !p-0 divide-y divide-gray-100`} aria-label="Your packages">
          {packages.length === 0 ? (
            <li className="px-4 py-8 text-center text-sm text-gray-500">No packages yet.</li>
          ) : (
            packages.map((p) => (
              <li key={p.id} className="flex flex-col sm:flex-row sm:items-center gap-2 justify-between px-4 py-3">
                <div>
                  <p className="font-semibold text-gray-900">
                    {p.name} {!p.isActive && <span className="ml-2 text-xs font-medium text-gray-500">Off sale</span>}
                  </p>
                  <p className="text-sm text-gray-600">
                    {serviceName(p.serviceId)} · {p.visits} visits · {formatMoney(p.priceCents)} · valid {p.validDays} days
                  </p>
                </div>
                <button type="button" onClick={() => toggle(p)} className="text-sm font-medium text-indigo-700 hover:underline self-start sm:self-auto">
                  {p.isActive ? 'Take off sale' : 'Put on sale'}
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
