import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { MapPin, ExternalLink } from 'lucide-react';
import type { AppDispatch, RootState } from '../state/store';
import { setShop } from '../state/authSlice';
import { updateShop } from '../services/shopService';
import { apiErrorMessage, isE164, normalizePhone } from '../services/format';
import { useToast } from '../components/Toast';
import { SHOP_CATEGORIES } from '../services/categories';

const optional = z.string().trim();

/** A latitude (limit 90) or longitude (limit 180) typed into a text box, or blank. */
const coordinate = (limit: number) =>
  z
    .string()
    .trim()
    .refine((v) => v === '' || (Number.isFinite(Number(v)) && Math.abs(Number(v)) <= limit), `Between -${limit} and ${limit}`);

const schema = z.object({
  name: z.string().trim().min(2, 'At least 2 characters'),
  category: z.string().trim().min(2, 'Choose a category'),
  description: optional,
  city: optional,
  address: optional,
  phone: optional.refine((v) => v === '' || isE164(normalizePhone(v)), 'Enter a 10-digit mobile number, e.g. 98765 43210'),
  email: z.union([z.literal(''), z.string().trim().email('Enter a valid email address')]),
  // Where customers get directions to; both or neither.
  latitude: coordinate(90),
  longitude: coordinate(180),
}).refine((v) => (v.latitude === '') === (v.longitude === ''), {
  message: 'Enter both latitude and longitude, or neither',
  path: ['longitude'],
});
type FormData = z.infer<typeof schema>;

const FIELDS: [keyof FormData, string, string, string][] = [
  ['name', 'Shop name', 'text', 'organization'],
  ['description', 'About your shop', 'text', 'off'],
  ['city', 'City', 'text', 'address-level2'],
  ['address', 'Address', 'text', 'street-address'],
  ['phone', 'Shop phone', 'tel', 'tel'],
  ['email', 'Email', 'email', 'email'],
];

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

export default function SettingsPage() {
  const dispatch = useDispatch<AppDispatch>();
  const shop = useSelector((state: RootState) => state.auth.shop);
  const [saved, setSaved] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const toast = useToast();
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormData>({ resolver: zodResolver(schema) });
  const [lat, lng, category] = watch(['latitude', 'longitude', 'category']);
  const hasPin = !!lat && !!lng && !errors.latitude && !errors.longitude;
  // Shops created before the list existed may have a category of their own; keep it selectable.
  const categories =
    category && !SHOP_CATEGORIES.some((c) => c.value === category)
      ? [...SHOP_CATEGORIES, { value: category, label: category }]
      : SHOP_CATEGORIES;

  /** Fills in the map position from this device (the owner standing in the shop). */
  const useCurrentLocation = () => {
    if (!navigator.geolocation) return setServerError('This browser cannot share its location.');
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setValue('latitude', pos.coords.latitude.toFixed(6), { shouldValidate: true, shouldDirty: true });
        setValue('longitude', pos.coords.longitude.toFixed(6), { shouldValidate: true, shouldDirty: true });
        setLocating(false);
      },
      () => {
        setServerError('Could not get your location. Allow location access, or type the coordinates.');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  };

  useEffect(() => {
    if (!shop) return;
    reset({
      name: shop.name,
      category: shop.category,
      description: shop.description ?? '',
      city: shop.city ?? '',
      address: shop.address ?? '',
      phone: shop.phone ?? '',
      email: shop.email ?? '',
      latitude: shop.latitude === null ? '' : String(shop.latitude),
      longitude: shop.longitude === null ? '' : String(shop.longitude),
    });
  }, [shop, reset]);

  const onSubmit = async (values: FormData) => {
    if (!shop) return;
    setServerError(null);
    try {
      const updated = await updateShop(shop.id, {
        name: values.name,
        category: values.category,
        description: values.description || null,
        city: values.city || null,
        address: values.address || null,
        phone: values.phone ? normalizePhone(values.phone) : null,
        email: values.email || null,
        latitude: values.latitude === '' ? null : Number(values.latitude),
        longitude: values.longitude === '' ? null : Number(values.longitude),
      });
      dispatch(setShop(updated));
      toast('Shop details saved.');
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not save settings'));
    }
  };

  const fieldError = (field: keyof FormData) =>
    errors[field] ? (
      <p id={`${field}-error`} className="mt-1 text-xs text-red-600">
        {errors[field]?.message}
      </p>
    ) : null;
  const a11y = (field: keyof FormData) => ({
    'aria-invalid': !!errors[field],
    'aria-describedby': errors[field] ? `${field}-error` : undefined,
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Shop settings</h1>
        <p className="text-sm text-gray-500">What customers see about your shop in the app.</p>
      </div>
      {saved && (
        <p role="status" className="text-green-800 bg-green-50 rounded px-3 py-2 text-sm">
          Settings saved successfully.
        </p>
      )}
      {serverError && (
        <p role="alert" className="text-red-700 bg-red-50 rounded px-3 py-2 text-sm">
          {serverError}
        </p>
      )}
      <form onSubmit={handleSubmit(onSubmit)} className="bg-white rounded-2xl shadow p-4 md:p-6 space-y-4" noValidate>
        {FIELDS.slice(0, 1).map(([field, label, type, autoComplete]) => (
          <div key={field}>
            <label htmlFor={field} className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
            <input id={field} type={type} autoComplete={autoComplete} {...a11y(field)} {...register(field)} className={inputClass} />
            {fieldError(field)}
          </div>
        ))}
        <div>
          <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">Category</label>
          <select id="category" {...a11y('category')} {...register('category')} className={`${inputClass} bg-white`}>
            {categories.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          {fieldError('category')}
        </div>
        {FIELDS.slice(1).map(([field, label, type, autoComplete]) => (
          <div key={field}>
            <label htmlFor={field} className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
            <input id={field} type={type} autoComplete={autoComplete} {...a11y(field)} {...register(field)} className={inputClass} />
            {fieldError(field)}
          </div>
        ))}
        <fieldset className="border-t border-gray-100 pt-4">
          <legend className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
            <MapPin size={16} aria-hidden /> Map location
          </legend>
          <p className="text-xs text-gray-600 mb-2">
            Customers get directions, public transport routes and a cab drop-off to this point. Without it they are sent to your address.
          </p>
          <button type="button" onClick={useCurrentLocation} disabled={locating} className="mb-3 text-sm font-medium border border-indigo-200 text-indigo-700 bg-indigo-50 rounded-lg px-3 py-2 hover:bg-indigo-100 disabled:opacity-50">
            {locating ? 'Finding you…' : 'Use my current location (stand in your shop)'}
          </button>
          <div className="grid sm:grid-cols-2 gap-3">
            {(['latitude', 'longitude'] as const).map((field) => (
              <div key={field}>
                <label htmlFor={field} className="block text-xs text-gray-700 mb-1">{field === 'latitude' ? 'Latitude' : 'Longitude'}</label>
                <input id={field} inputMode="decimal" {...a11y(field)} {...register(field)} placeholder={field === 'latitude' ? '18.5204' : '73.8567'} className={inputClass} />
                {fieldError(field)}
              </div>
            ))}
          </div>
          {hasPin && (
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${lat},${lng}`)}`}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm text-indigo-600 hover:underline"
            >
              Check this pin on Google Maps <ExternalLink size={14} aria-hidden />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          )}
        </fieldset>
        <div className="flex items-center gap-3">
          <button type="submit" disabled={isSubmitting} className="bg-indigo-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50">
            {isSubmitting ? 'Saving…' : 'Save Settings'}
          </button>
          {isDirty && !isSubmitting && <span className="text-sm text-amber-700">Unsaved changes</span>}
        </div>
      </form>
    </div>
  );
}
