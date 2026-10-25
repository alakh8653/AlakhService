import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { confirmPasswordReset } from '../services/authService';
import { apiErrorMessage } from '../services/format';
import PasswordInput from '../components/PasswordInput';

/** Same rules as auth_service, checked here first for quicker feedback. */
export function passwordProblem(password: string): string | null {
  if (password.length < 8) return 'Use at least 8 characters.';
  if (!/[A-Z]/.test(password)) return 'Include an uppercase letter.';
  if (!/\d/.test(password)) return 'Include a digit.';
  return null;
}

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const problem = passwordProblem(password) ?? (password !== confirm ? 'The passwords do not match.' : null);
    if (problem) return setError(problem);
    setSubmitting(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError(apiErrorMessage(err, 'This link is invalid or has expired. Request a new one.'));
    } finally {
      setSubmitting(false);
    }
  };

  const input = 'mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';
  return (
    <div className="min-h-dvh flex items-center justify-center bg-gray-100 px-4 py-8">
      <div className="bg-white rounded-2xl shadow-lg p-6 sm:p-8 w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Choose a new password</h1>
        {!token ? (
          <p className="text-sm text-red-600">This reset link is incomplete. Request a new one.</p>
        ) : done ? (
          <p className="text-sm text-gray-600">Your password has been changed and other sessions were signed out.</p>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4">
            {error && (
              <p role="alert" className="text-sm text-red-700 bg-red-50 rounded px-3 py-2">
                {error}
              </p>
            )}
            <div>
              <label htmlFor="new-password" className="block text-sm font-medium text-gray-700">
                New password
              </label>
              <PasswordInput id="new-password" autoComplete="new-password" aria-describedby="new-password-hint" value={password} onChange={(e) => setPassword(e.target.value)} className={input} />
              <p id="new-password-hint" className="mt-1 text-xs text-gray-500">
                At least 8 characters, with a capital letter and a number.
              </p>
            </div>
            <div>
              <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700">
                Confirm new password
              </label>
              <PasswordInput id="confirm-password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={input} />
            </div>
            <button type="submit" disabled={submitting} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg disabled:opacity-50">
              {submitting ? 'Saving…' : 'Change password'}
            </button>
          </form>
        )}
        <Link to={done ? '/login' : '/forgot-password'} className="block text-sm text-indigo-600 hover:underline">
          {done ? 'Sign in' : 'Request a new link'}
        </Link>
      </div>
    </div>
  );
}
