import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import apiClient from '../services/apiClient';
import type { Shop } from '../types';

const schema = z.object({
  name: z.string().min(2),
  description: z.string(),
  address: z.string().min(5),
  phone: z.string().min(7),
  email: z.string().email(),
  timezone: z.string(),
  currency: z.string().length(3),
});
type FormData = z.infer<typeof schema>;

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({ resolver: zodResolver(schema) });

  useEffect(() => {
    apiClient.get<{ data: Shop }>('/shop').then(({ data }) => {
      const s = data.data;
      reset({ name: s.name, description: s.description, address: s.address, phone: s.phone, email: s.email, timezone: s.timezone, currency: s.currency });
    });
  }, [reset]);

  const onSubmit = async (values: FormData) => {
    await apiClient.patch('/shop', values);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">Shop Settings</h1>
      {saved && <p className="text-green-600 bg-green-50 rounded px-3 py-2 text-sm">Settings saved successfully.</p>}
      <form onSubmit={handleSubmit(onSubmit)} className="bg-white rounded-2xl shadow p-6 space-y-4">
        {([
          ['name', 'Shop Name', 'text'],
          ['description', 'Description', 'text'],
          ['address', 'Address', 'text'],
          ['phone', 'Phone', 'tel'],
          ['email', 'Email', 'email'],
          ['timezone', 'Timezone', 'text'],
          ['currency', 'Currency (ISO)', 'text'],
        ] as [keyof FormData, string, string][]).map(([field, label, type]) => (
          <div key={field}>
            <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
            <input type={type} {...register(field)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            {errors[field] && <p className="mt-1 text-xs text-red-500">{errors[field]?.message}</p>}
          </div>
        ))}
        <button type="submit" disabled={isSubmitting} className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50">
          {isSubmitting ? 'Saving…' : 'Save Settings'}
        </button>
      </form>
    </div>
  );
}
