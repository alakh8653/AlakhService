import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { apiErrorMessage, isE164, normalizePhone } from '../services/format';
import { SHOP_CATEGORIES } from '../services/categories';

const schema = z.object({
  name: z.string().trim().min(2, 'Enter your shop name'),
  category: z.string().min(1, 'Choose a category'),
  city: z.string().trim().min(2, 'Enter your city'),
  address: z.string().trim().optional(),
  phone: z
    .string()
    .trim()
    .refine((v) => v === '' || isE164(normalizePhone(v)), 'Enter a 10-digit mobile number, e.g. 98765 43210')
    .optional(),
  description: z.string().trim().max(500).optional(),
});
type FormData = z.infer<typeof schema>;

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

/** Shown to a signed-in owner who has no shop yet. */
export default function ShopSetupPage() {
  const { user, createShop, logout } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema), defaultValues: { category: '' } });

  const onSubmit = async (values: FormData) => {
    try {
      setServerError(null);
      await createShop({ ...values, phone: values.phone ? normalizePhone(values.phone) : undefined });
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not create your shop'));
    }
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-gray-100 px-4 py-8">
      <main className="bg-white rounded-2xl shadow-lg p-6 sm:p-8 w-full max-w-lg">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Set up your shop</h1>
        <p className="text-gray-500 mb-6">
          Welcome{user ? `, ${user.name}` : ''}. Tell customers about your shop; you can add services and staff next.
        </p>
        {serverError && <p role="alert" className="mb-4 text-sm text-red-700 bg-red-50 rounded px-3 py-2">{serverError}</p>}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Shop name</label>
            <input id="name" aria-invalid={!!errors.name} {...register('name')} className={inputClass} placeholder="Asha Salon" />
            {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>}
          </div>
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select id="category" aria-invalid={!!errors.category} {...register('category')} className={inputClass}>
              <option value="">Choose…</option>
              {SHOP_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            {errors.category && <p className="mt-1 text-xs text-red-600">{errors.category.message}</p>}
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="city" className="block text-sm font-medium text-gray-700 mb-1">City</label>
              <input id="city" aria-invalid={!!errors.city} autoComplete="address-level2" {...register('city')} className={inputClass} placeholder="Pune" />
              {errors.city && <p className="mt-1 text-xs text-red-600">{errors.city.message}</p>}
            </div>
            <div>
              <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-1">Shop phone <span className="font-normal text-gray-500">(optional)</span></label>
              <input id="phone" type="tel" autoComplete="tel" aria-invalid={!!errors.phone} {...register('phone')} className={inputClass} placeholder="98765 43210" />
              {errors.phone && <p className="mt-1 text-xs text-red-600">{errors.phone.message}</p>}
            </div>
          </div>
          <div>
            <label htmlFor="address" className="block text-sm font-medium text-gray-700 mb-1">Address <span className="font-normal text-gray-500">(optional)</span></label>
            <input id="address" autoComplete="street-address" {...register('address')} className={inputClass} placeholder="12 MG Road" />
          </div>
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">About your shop <span className="font-normal text-gray-500">(optional)</span></label>
            <textarea id="description" rows={3} {...register('description')} className={inputClass} />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg transition disabled:opacity-50"
          >
            {isSubmitting ? 'Creating shop…' : 'Create shop'}
          </button>
        </form>
        <button type="button" onClick={() => void logout()} className="mt-4 text-sm text-gray-500 hover:underline">
          Sign out
        </button>
      </main>
    </div>
  );
}
