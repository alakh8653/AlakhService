import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { register as registerAccount } from '../services/authService';
import { useAuth } from '../hooks/useAuth';
import { apiErrorMessage } from '../services/format';

const schema = z.object({
  name: z.string().trim().min(2, 'Enter your name'),
  email: z.string().email('Invalid email'),
  phone: z
    .string()
    .trim()
    .regex(/^(\+\d{10,15})?$/, 'Use international format, e.g. +919876543210')
    .optional(),
  password: z
    .string()
    .min(8, 'At least 8 characters')
    .regex(/[A-Z]/, 'Include an uppercase letter')
    .regex(/[a-z]/, 'Include a lowercase letter')
    .regex(/\d/, 'Include a number'),
});
type FormData = z.infer<typeof schema>;

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

/** Sign-up for shop owners; after creating the account they are signed in and set up their shop. */
export default function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormData) => {
    try {
      setServerError(null);
      await registerAccount(values);
      await login({ email: values.email.trim().toLowerCase(), password: values.password });
      navigate('/dashboard');
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not create your account'));
    }
  };

  const field = (name: keyof FormData, label: string, type = 'text', placeholder = '') => (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <input id={name} type={type} {...register(name)} className={inputClass} placeholder={placeholder} />
      {errors[name] && <p className="mt-1 text-xs text-red-500">{errors[name]?.message}</p>}
    </div>
  );

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">List your shop</h1>
        <p className="text-gray-500 mb-6">Create your AlakhService owner account</p>
        {serverError && <p className="mb-4 text-sm text-red-600 bg-red-50 rounded px-3 py-2">{serverError}</p>}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {field('name', 'Your name', 'text', 'Asha Rao')}
          {field('email', 'Email', 'email', 'you@example.com')}
          {field('phone', 'Phone (optional)', 'tel', '+919876543210')}
          {field('password', 'Password', 'password', '••••••••')}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg transition disabled:opacity-50"
          >
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="mt-4 text-sm text-gray-600">
          Already have an account?{' '}
          <Link to="/login" className="text-indigo-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
