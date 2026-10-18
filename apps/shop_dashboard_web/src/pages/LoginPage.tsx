import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '../hooks/useAuth';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { apiErrorMessage } from '../services/format';
import PasswordInput from '../components/PasswordInput';

const schema = z.object({
  email: z.string().trim().email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
});
type FormData = z.infer<typeof schema>;

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState<string | null>(null);
  // Back to the page the owner was on before being asked to sign in.
  const from = (location.state as { from?: string } | null)?.from;

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormData) => {
    try {
      setServerError(null);
      await login({ email: values.email.trim().toLowerCase(), password: values.password });
      navigate(from && from !== '/login' ? from : '/dashboard', { replace: true });
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not sign in. Check your connection and try again.'));
    }
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-gray-100 px-4 py-8">
      <main className="bg-white rounded-2xl shadow-lg p-6 sm:p-8 w-full max-w-md">
        <p className="text-sm font-bold text-indigo-600 mb-1">AlakhService</p>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Sign in to your shop</h1>
        <p className="text-gray-500 mb-6">Manage bookings, walk-ins and staff.</p>

        {serverError && (
          <p role="alert" className="mb-4 text-sm text-red-700 bg-red-50 rounded px-3 py-2">
            {serverError}
          </p>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="username"
              inputMode="email"
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? 'login-email-error' : undefined}
              {...register('email')}
              className={inputClass}
              placeholder="you@example.com"
            />
            {errors.email && (
              <p id="login-email-error" className="mt-1 text-xs text-red-600">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-1">
              <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <Link to="/forgot-password" className="text-sm text-indigo-600 hover:underline">
                Forgot password?
              </Link>
            </div>
            <PasswordInput
              id="login-password"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              aria-describedby={errors.password ? 'login-password-error' : undefined}
              {...register('password')}
              className={inputClass}
            />
            {errors.password && (
              <p id="login-password-error" className="mt-1 text-xs text-red-600">
                {errors.password.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2.5 rounded-lg transition disabled:opacity-50"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 text-sm text-gray-600">
          New to AlakhService?{' '}
          <Link to="/register" className="text-indigo-600 font-medium hover:underline">
            List your shop
          </Link>
        </p>
      </main>
    </div>
  );
}
