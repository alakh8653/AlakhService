import { useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import { Plus, Edit2, ToggleLeft, ToggleRight } from 'lucide-react';
import type { RootState } from '../state/store';
import { useShopServices } from '../hooks/useShopServices';
import { createService, updateService } from '../services/shopService';
import { apiErrorMessage, formatMoney, toMinorUnits } from '../services/format';
import type { Service, ServiceMode } from '../types';

export interface ServiceValues {
  name: string;
  description: string;
  price: number;
  duration: number | null;
  modes: ServiceMode[];
  homeVisitFee: number;
  pickupFee: number;
}

interface ServiceFormProps {
  initial?: Service;
  onSubmit: (values: ServiceValues) => Promise<void>;
  onClose: () => void;
}

const MODE_CHOICES: { mode: ServiceMode; label: string; hint: string }[] = [
  { mode: 'AT_SHOP', label: 'At the shop', hint: 'The customer comes in' },
  { mode: 'AT_HOME', label: 'Home visit', hint: 'Your staff go to the customer' },
  { mode: 'PICKUP_DROP', label: 'Pickup & drop', hint: 'Collect the item (car, bike, phone, AC…) and bring it back' },
];

const MODE_SHORT: Record<ServiceMode, string> = { AT_SHOP: 'Shop', AT_HOME: 'Home', PICKUP_DROP: 'Pickup' };

function ServiceForm({ initial, onSubmit, onClose }: ServiceFormProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [price, setPrice] = useState(initial ? String(initial.priceCents / 100) : '');
  const [duration, setDuration] = useState(initial?.durationMinutes ? String(initial.durationMinutes) : '');
  const [modes, setModes] = useState<ServiceMode[]>(initial?.serviceModes ?? ['AT_SHOP']);
  const [homeFee, setHomeFee] = useState(initial?.homeVisitFeeCents ? String(initial.homeVisitFeeCents / 100) : '');
  const [pickupFee, setPickupFee] = useState(initial?.pickupFeeCents ? String(initial.pickupFeeCents / 100) : '');
  const toggleMode = (mode: ServiceMode) =>
    setModes((current) => (current.includes(mode) ? current.filter((m) => m !== mode) : [...current, mode]));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const priceValue = Number(price);
    const durationValue = duration ? Number(duration) : null;
    if (!name.trim()) return setError('Name is required');
    if (!Number.isFinite(priceValue) || priceValue <= 0) return setError('Price must be greater than 0');
    if (durationValue !== null && (!Number.isInteger(durationValue) || durationValue <= 0)) {
      return setError('Duration must be a whole number of minutes');
    }
    if (modes.length === 0) return setError('Choose at least one way to deliver the service');
    const homeFeeValue = modes.includes('AT_HOME') && homeFee ? Number(homeFee) : 0;
    const pickupFeeValue = modes.includes('PICKUP_DROP') && pickupFee ? Number(pickupFee) : 0;
    if (![homeFeeValue, pickupFeeValue].every((fee) => Number.isFinite(fee) && fee >= 0)) {
      return setError('Fees cannot be negative');
    }
    setSaving(true);
    setError(null);
    try {
      // Keep the shop's preferred order (shop, home, pickup).
      const ordered = MODE_CHOICES.map((c) => c.mode).filter((m) => modes.includes(m));
      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        price: priceValue,
        duration: durationValue,
        modes: ordered,
        homeVisitFee: homeFeeValue,
        pickupFee: pickupFeeValue,
      });
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save the service'));
    } finally {
      setSaving(false);
    }
  };

  const input = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';
  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow p-4 grid sm:grid-cols-2 gap-3">
      <h2 className="sm:col-span-2 font-semibold text-gray-900">{initial ? 'Edit service' : 'New service'}</h2>
      <label className="text-sm text-gray-700">Name<input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} className={input} /></label>
      <label className="text-sm text-gray-700">Price (₹)<input aria-label="Price" type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className={input} /></label>
      <label className="text-sm text-gray-700">Duration (min)<input aria-label="Duration" type="number" min="1" value={duration} onChange={(e) => setDuration(e.target.value)} className={input} /></label>
      <label className="text-sm text-gray-700">Description<input aria-label="Description" value={description} onChange={(e) => setDescription(e.target.value)} className={input} /></label>
      <fieldset className="sm:col-span-2">
        <legend className="text-sm text-gray-700 mb-1">How you deliver it</legend>
        <div className="grid sm:grid-cols-3 gap-2">
          {MODE_CHOICES.map((c) => (
            <label key={c.mode} className={`flex gap-2 items-start border rounded-lg p-2 text-sm ${modes.includes(c.mode) ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200'}`}>
              <input type="checkbox" checked={modes.includes(c.mode)} onChange={() => toggleMode(c.mode)} className="mt-1" />
              <span>
                <span className="font-medium text-gray-900">{c.label}</span>
                <span className="block text-xs text-gray-500">{c.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {modes.includes('AT_HOME') && (
        <label className="text-sm text-gray-700">Home visit fee (₹)<input aria-label="Home visit fee" type="number" min="0" step="0.01" value={homeFee} onChange={(e) => setHomeFee(e.target.value)} placeholder="0" className={input} /></label>
      )}
      {modes.includes('PICKUP_DROP') && (
        <label className="text-sm text-gray-700">Pickup & drop fee (₹)<input aria-label="Pickup fee" type="number" min="0" step="0.01" value={pickupFee} onChange={(e) => setPickupFee(e.target.value)} placeholder="0" className={input} /></label>
      )}
      {error && <p className="sm:col-span-2 text-xs text-red-500">{error}</p>}
      <div className="sm:col-span-2 flex gap-2 justify-end">
        <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">Cancel</button>
        <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  );
}

export default function ServicesPage() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const { services, setServices } = useShopServices();
  const [editing, setEditing] = useState<Service | 'new' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const replace = (service: Service) =>
    setServices((prev) => prev.map((s) => (s.id === service.id ? service : s)));

  const toggleActive = async (service: Service) => {
    try {
      setError(null);
      replace(await updateService(service.id, { isActive: !service.isActive }));
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not update the service'));
    }
  };

  const save = async (values: ServiceValues) => {
    const input = {
      name: values.name,
      description: values.description || null,
      priceCents: toMinorUnits(values.price),
      durationMinutes: values.duration,
      serviceModes: values.modes,
      homeVisitFeeCents: toMinorUnits(values.homeVisitFee),
      pickupFeeCents: toMinorUnits(values.pickupFee),
    };
    if (editing === 'new') {
      if (!shopId) return;
      const created = await createService(shopId, input);
      setServices((prev) => [...prev, created]);
    } else if (editing) {
      replace(await updateService(editing.id, input));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Services</h1>
        <button onClick={() => setEditing('new')} className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
          <Plus size={16} /> Add Service
        </button>
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {editing && (
        <ServiceForm
          key={editing === 'new' ? 'new' : editing.id}
          initial={editing === 'new' ? undefined : editing}
          onSubmit={save}
          onClose={() => setEditing(null)}
        />
      )}
      <div className="bg-white rounded-2xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">Service</th>
              <th className="px-4 py-3 text-right">Duration</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-center">Active</th>
              <th className="px-4 py-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {services.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">{s.name}</p>
                  {s.description && <p className="text-xs text-gray-400">{s.description}</p>}
                  <p className="text-xs text-gray-500 mt-0.5">{s.serviceModes.map((m) => MODE_SHORT[m]).join(' · ')}</p>
                </td>
                <td className="px-4 py-3 text-right text-gray-500">{s.durationMinutes ? `${s.durationMinutes} min` : '—'}</td>
                <td className="px-4 py-3 text-right font-medium">{formatMoney(s.priceCents)}</td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => toggleActive(s)} title={s.isActive ? 'Deactivate' : 'Activate'} className={s.isActive ? 'text-green-500' : 'text-gray-400'}>
                    {s.isActive ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
                  </button>
                </td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => setEditing(s)} title="Edit" className="text-indigo-500 hover:text-indigo-700"><Edit2 size={16} /></button>
                </td>
              </tr>
            ))}
            {services.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-gray-400">No services yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
