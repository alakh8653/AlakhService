import { useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import { Plus, Pencil, Home, Package, Store } from 'lucide-react';
import type { RootState } from '../state/store';
import { useShopServices } from '../hooks/useShopServices';
import { createService, updateService } from '../services/shopService';
import { apiErrorMessage, formatMoney, toMinorUnits } from '../services/format';
import Dialog from '../components/Dialog';
import Switch from '../components/Switch';
import { useToast } from '../components/Toast';
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

const MODE_ICONS = { AT_SHOP: Store, AT_HOME: Home, PICKUP_DROP: Package };

type Field = 'name' | 'price' | 'duration' | 'modes' | 'homeFee' | 'pickupFee';

const input =
  'mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

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
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const priceValue = Number(price);
    const durationValue = duration ? Number(duration) : null;
    const homeFeeValue = modes.includes('AT_HOME') && homeFee ? Number(homeFee) : 0;
    const pickupFeeValue = modes.includes('PICKUP_DROP') && pickupFee ? Number(pickupFee) : 0;
    const found: Partial<Record<Field, string>> = {};
    if (!name.trim()) found.name = 'Enter a name customers will recognise';
    if (!price || !Number.isFinite(priceValue) || priceValue <= 0) found.price = 'Enter a price above ₹0';
    if (durationValue !== null && (!Number.isInteger(durationValue) || durationValue <= 0)) {
      found.duration = 'Whole minutes, e.g. 30';
    }
    if (modes.length === 0) found.modes = 'Choose at least one way to deliver the service';
    if (!Number.isFinite(homeFeeValue) || homeFeeValue < 0) found.homeFee = 'Fee cannot be negative';
    if (!Number.isFinite(pickupFeeValue) || pickupFeeValue < 0) found.pickupFee = 'Fee cannot be negative';
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSaving(true);
    setServerError(null);
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
      setServerError(apiErrorMessage(err, 'Could not save the service'));
    } finally {
      setSaving(false);
    }
  };

  const err = (field: Field) =>
    errors[field] ? (
      <span id={`svc-${field}-error`} className="block mt-1 text-xs text-red-600">
        {errors[field]}
      </span>
    ) : null;
  const a11y = (field: Field) => ({
    'aria-invalid': !!errors[field],
    'aria-describedby': errors[field] ? `svc-${field}-error` : undefined,
  });

  return (
    <Dialog title={initial ? `Edit ${initial.name}` : 'New service'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="grid sm:grid-cols-2 gap-3" noValidate>
        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-gray-700">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} className={input} placeholder="e.g. Haircut" {...a11y('name')} />
          </label>
          {err('name')}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
          Price (₹)
          <input type="number" inputMode="decimal" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className={input} placeholder="300" {...a11y('price')} />
          </label>
          {err('price')}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">
          Duration (minutes)
          <input type="number" inputMode="numeric" min="1" value={duration} onChange={(e) => setDuration(e.target.value)} className={input} placeholder="30" {...a11y('duration')} />
          </label>
          {err('duration')}
        </div>
        <label className="sm:col-span-2 text-sm font-medium text-gray-700">
          Description <span className="font-normal text-gray-500">(optional)</span>
          <input value={description} onChange={(e) => setDescription(e.target.value)} className={input} placeholder="What is included" />
        </label>
        <fieldset className="sm:col-span-2" aria-describedby={errors.modes ? 'svc-modes-error' : undefined}>
          <legend className="text-sm font-medium text-gray-700 mb-1">How you deliver it</legend>
          <div className="grid gap-2">
            {MODE_CHOICES.map((c) => (
              <label key={c.mode} className={`flex gap-2 items-start border rounded-lg p-2.5 text-sm cursor-pointer ${modes.includes(c.mode) ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200'}`}>
                <input type="checkbox" checked={modes.includes(c.mode)} onChange={() => toggleMode(c.mode)} className="mt-1" />
                <span>
                  <span className="font-medium text-gray-900">{c.label}</span>
                  <span className="block text-xs text-gray-600">{c.hint}</span>
                </span>
              </label>
            ))}
          </div>
          {err('modes')}
        </fieldset>
        {modes.includes('AT_HOME') && (
          <div>
            <label className="block text-sm font-medium text-gray-700">
            Home visit fee (₹)
            <input type="number" inputMode="decimal" min="0" step="0.01" value={homeFee} onChange={(e) => setHomeFee(e.target.value)} placeholder="0" className={input} {...a11y('homeFee')} />
            </label>
            {err('homeFee')}
          </div>
        )}
        {modes.includes('PICKUP_DROP') && (
          <div>
            <label className="block text-sm font-medium text-gray-700">
            Pickup & drop fee (₹)
            <input type="number" inputMode="decimal" min="0" step="0.01" value={pickupFee} onChange={(e) => setPickupFee(e.target.value)} placeholder="0" className={input} {...a11y('pickupFee')} />
            </label>
            {err('pickupFee')}
          </div>
        )}
        {serverError && (
          <p role="alert" className="sm:col-span-2 text-sm text-red-700 bg-red-50 rounded px-3 py-2">
            {serverError}
          </p>
        )}
        <div className="sm:col-span-2 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {saving ? 'Saving…' : initial ? 'Save changes' : 'Add service'}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

/** "₹300 · Home visit +₹100 · Pickup free" */
function priceLine(s: Service) {
  const parts = [formatMoney(s.priceCents)];
  if (s.serviceModes.includes('AT_HOME')) parts.push(`home visit ${s.homeVisitFeeCents ? `+${formatMoney(s.homeVisitFeeCents)}` : 'no extra fee'}`);
  if (s.serviceModes.includes('PICKUP_DROP')) parts.push(`pickup ${s.pickupFeeCents ? `+${formatMoney(s.pickupFeeCents)}` : 'no extra fee'}`);
  return parts.join(' · ');
}

export default function ServicesPage() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const { services, setServices, isLoading, error: loadError } = useShopServices();
  const [editing, setEditing] = useState<Service | 'new' | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const toast = useToast();

  const replace = (service: Service) => setServices((prev) => prev.map((s) => (s.id === service.id ? service : s)));

  const toggleActive = async (service: Service) => {
    setToggling(service.id);
    try {
      const updated = await updateService(service.id, { isActive: !service.isActive });
      replace(updated);
      toast(updated.isActive ? `${updated.name} can be booked again.` : `${updated.name} is hidden from customers.`);
    } catch (err) {
      toast(apiErrorMessage(err, 'Could not update the service'), 'error');
    } finally {
      setToggling(null);
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
      toast(`${created.name} added. Customers can book it now.`);
    } else if (editing) {
      const updated = await updateService(editing.id, input);
      replace(updated);
      toast(`${updated.name} saved.`);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Services</h1>
          <p className="text-sm text-gray-500">What customers can book, and what it costs.</p>
        </div>
        <button type="button" onClick={() => setEditing('new')} className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 whitespace-nowrap">
          <Plus size={16} aria-hidden /> Add service
        </button>
      </div>
      {loadError && (
        <p role="alert" className="text-red-700 bg-red-50 rounded-lg px-3 py-2 text-sm">
          {loadError}
        </p>
      )}
      {editing && (
        <ServiceForm
          key={editing === 'new' ? 'new' : editing.id}
          initial={editing === 'new' ? undefined : editing}
          onSubmit={save}
          onClose={() => setEditing(null)}
        />
      )}
      {isLoading ? (
        <div className="bg-white rounded-2xl shadow h-40 animate-pulse" aria-label="Loading services" />
      ) : services.length === 0 ? (
        <div className="bg-white rounded-2xl shadow p-8 text-center space-y-3">
          <p className="text-gray-700 font-medium">No services yet</p>
          <p className="text-sm text-gray-500">Add what you offer so customers can find and book you.</p>
          <button type="button" onClick={() => setEditing('new')} className="text-sm font-medium text-indigo-600 hover:underline">
            Add your first service
          </button>
        </div>
      ) : (
        <ul className="bg-white rounded-2xl shadow divide-y divide-gray-100">
          {services.map((s) => (
            <li key={s.id} className={`flex items-start gap-3 px-4 py-3 ${s.isActive ? '' : 'bg-gray-50'}`}>
              <div className="flex-1 min-w-0">
                <p className={`font-medium ${s.isActive ? 'text-gray-900' : 'text-gray-500'}`}>
                  {s.name}
                  {!s.isActive && <span className="ml-2 text-xs font-normal bg-gray-200 text-gray-700 rounded-full px-2 py-0.5">Hidden</span>}
                </p>
                <p className="text-sm text-gray-700">
                  {priceLine(s)}
                  {s.durationMinutes ? <span className="text-gray-500"> · {s.durationMinutes} min</span> : null}
                </p>
                {s.description && <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>}
                <p className="flex flex-wrap gap-1.5 mt-1">
                  {s.serviceModes.map((m) => {
                    const Icon = MODE_ICONS[m];
                    return (
                      <span key={m} className="flex items-center gap-1 text-xs text-gray-700 bg-gray-100 rounded-full px-2 py-0.5">
                        <Icon size={12} aria-hidden /> {MODE_CHOICES.find((c) => c.mode === m)?.label}
                      </span>
                    );
                  })}
                </p>
              </div>
              <div className="flex items-center gap-3 pt-0.5">
                <label className="flex items-center gap-2 text-xs text-gray-600">
                  <span className="hidden sm:inline">{s.isActive ? 'Bookable' : 'Hidden'}</span>
                  <Switch checked={s.isActive} disabled={toggling === s.id} onChange={() => void toggleActive(s)} label={`${s.name} available to book`} />
                </label>
                <button type="button" onClick={() => setEditing(s)} aria-label={`Edit ${s.name}`} className="p-2 rounded-lg text-indigo-600 hover:bg-indigo-50">
                  <Pencil size={16} aria-hidden />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
