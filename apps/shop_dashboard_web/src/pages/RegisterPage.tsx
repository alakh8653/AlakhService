import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { register as registerAccount } from '../services/authService';
import { useAuth } from '../hooks/useAuth';
import { apiErrorMessage, isE164, normalizePhone } from '../services/format';
import PasswordInput from '../components/PasswordInput';
import { passwordProblem } from './ResetPasswordPage';

const schema = z.object({
  name: z.string().trim().min(2, 'Enter your name'),
  email: z.string().trim().email('Enter a valid email address'),
  phone: z
    .string()
    .trim()
    .refine((v) => v === '' || isE164(normalizePhone(v)), 'Enter a 10-digit mobile number, e.g. 98765 43210')
    .optional(),
  // The same rules as the server (and the reset-password page).
  password: z.string().superRefine((v, ctx) => {
    const problem = passwordProblem(v);
    if (problem) ctx.addIssue({ code: 'custom', message: problem });
  }),
});
type FormData = z.infer<typeof schema>;

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

const AUTOCOMPLETE: Record<keyof FormData, string> = { name: 'name', email: 'email', phone: 'tel', password: 'new-password' };

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
      const email = values.email.trim().toLowerCase();
      await registerAccount({ ...values, email, phone: values.phone ? normalizePhone(values.phone) : undefined });
      await login({ email, password: values.password });
      navigate('/dashboard');
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not create your account'));
    }
  };

  const field = (name: keyof FormData, label: string, type = 'text', placeholder = '', hint?: string) => {
    const describedBy = [errors[name] ? `${name}-error` : null, hint ? `${name}-hint` : null].filter(Boolean).join(' ') || undefined;
    const props = {
      id: name,
      autoComplete: AUTOCOMPLETE[name],
      'aria-invalid': !!errors[name],
      'aria-describedby': describedBy,
      className: inputClass,
      placeholder,
      ...register(name),
    };
    return (
      <div>
        <label htmlFor={name} className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
        {type === 'password' ? <PasswordInput {...props} /> : <input type={type} {...props} />}
        {hint && !errors[name] && (
          <p id={`${name}-hint`} className="mt-1 text-xs text-gray-500">
            {hint}
          </p>
        )}
        {errors[name] && (
          <p id={`${name}-error`} className="mt-1 text-xs text-red-600">
            {errors[name]?.message}
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-gray-100 px-4 py-8">
      <main className="bg-white rounded-2xl shadow-lg p-6 sm:p-8 w-full max-w-md">
        <p className="text-sm font-bold text-indigo-600 mb-1">AlakhService</p>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">List your shop</h1>
        <p className="text-gray-500 mb-6">Create your owner account. Setting up your shop takes about 2 minutes.</p>
        {serverError && (
          <p role="alert" className="mb-4 text-sm text-red-700 bg-red-50 rounded px-3 py-2">
            {serverError}
          </p>
        )}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {field('name', 'Your name', 'text', 'Asha Rao')}
          {field('email', 'Email', 'email', 'you@example.com')}
          {field('phone', 'Mobile (optional)', 'tel', '98765 43210')}
          {field('password', 'Password', 'password', '', 'At least 8 characters, with a capital letter and a number.')}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2.5 rounded-lg transition disabled:opacity-50"
          >
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        <p className="mt-6 text-sm text-gray-600">
          Already have an account?{' '}
          <Link to="/login" className="text-indigo-600 font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </main>
    </div>
  );
}
