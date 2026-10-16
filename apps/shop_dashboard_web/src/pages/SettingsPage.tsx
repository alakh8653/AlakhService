import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { AppDispatch, RootState } from '../state/store';
import { setShop } from '../state/authSlice';
import { updateShop } from '../services/shopService';
import { apiErrorMessage } from '../services/format';

const optional = z.string().trim();

/** A latitude (limit 90) or longitude (limit 180) typed into a text box, or blank. */
const coordinate = (limit: number) =>
  z
    .string()
    .trim()
    .refine((v) => v === '' || (Number.isFinite(Number(v)) && Math.abs(Number(v)) <= limit), `Between -${limit} and ${limit}`);

const schema = z.object({
  name: z.string().trim().min(2, 'At least 2 characters'),
  category: z.string().trim().min(2, 'At least 2 characters'),
  description: optional,
  city: optional,
  address: optional,
  phone: optional,
  email: z.union([z.literal(''), z.string().trim().email('Invalid email')]),
  // Where customers get directions to; both or neither.
  latitude: coordinate(90),
  longitude: coordinate(180),
}).refine((v) => (v.latitude === '') === (v.longitude === ''), {
  message: 'Enter both latitude and longitude, or neither',
  path: ['longitude'],
});
type FormData = z.infer<typeof schema>;

const FIELDS: [keyof FormData, string, string][] = [
  ['name', 'Shop Name', 'text'],
  ['category', 'Category', 'text'],
  ['description', 'Description', 'text'],
  ['city', 'City', 'text'],
  ['address', 'Address', 'text'],
  ['phone', 'Phone', 'tel'],
  ['email', 'Email', 'email'],
];

export default function SettingsPage() {
  const dispatch = useDispatch<AppDispatch>();
  const shop = useSelector((state: RootState) => state.auth.shop);
  const [saved, setSaved] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const { register, handleSubmit, reset, setValue, formState: { errors, isSubmitting } } = useForm<FormData>({ resolver: zodResolver(schema) });

  /** Fills in the map position from this device (the owner standing in the shop). */
  const useCurrentLocation = () => {
    if (!navigator.geolocation) return setServerError('This browser cannot share its location.');
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setValue('latitude', pos.coords.latitude.toFixed(6), { shouldValidate: true });
        setValue('longitude', pos.coords.longitude.toFixed(6), { shouldValidate: true });
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
        phone: values.phone || null,
        email: values.email || null,
        latitude: values.latitude === '' ? null : Number(values.latitude),
        longitude: values.longitude === '' ? null : Number(values.longitude),
      });
      dispatch(setShop(updated));
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not save settings'));
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">Shop Settings</h1>
      {saved && <p className="text-green-600 bg-green-50 rounded px-3 py-2 text-sm">Settings saved successfully.</p>}
      {serverError && <p className="text-red-600 bg-red-50 rounded px-3 py-2 text-sm">{serverError}</p>}
      <form onSubmit={handleSubmit(onSubmit)} className="bg-white rounded-2xl shadow p-6 space-y-4">
        {FIELDS.map(([field, label, type]) => (
          <div key={field}>
            <label htmlFor={field} className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
            <input id={field} type={type} {...register(field)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            {errors[field] && <p className="mt-1 text-xs text-red-500">{errors[field]?.message}</p>}
          </div>
        ))}
        <fieldset className="border-t border-gray-100 pt-4">
          <legend className="text-sm font-medium text-gray-700">Map location</legend>
          <p className="text-xs text-gray-500 mb-2">
            Customers get directions, public transport routes and a cab drop-off to this point. Without it they are sent to your address.
          </p>
          <div className="grid sm:grid-cols-2 gap-3">
            {(['latitude', 'longitude'] as const).map((field) => (
              <div key={field}>
                <label htmlFor={field} className="block text-xs text-gray-600 mb-1">{field === 'latitude' ? 'Latitude' : 'Longitude'}</label>
                <input id={field} inputMode="decimal" {...register(field)} placeholder={field === 'latitude' ? '18.5204' : '73.8567'} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                {errors[field] && <p className="mt-1 text-xs text-red-500">{errors[field]?.message}</p>}
              </div>
            ))}
          </div>
          <button type="button" onClick={useCurrentLocation} disabled={locating} className="mt-2 text-sm text-indigo-600 hover:underline disabled:opacity-50">
            {locating ? 'Finding you…' : 'Use my current location (stand in your shop)'}
          </button>
        </fieldset>
        <button type="submit" disabled={isSubmitting} className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50">
          {isSubmitting ? 'Saving…' : 'Save Settings'}
        </button>
      </form>
    </div>
  );
}
