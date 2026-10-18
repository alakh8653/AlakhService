import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { requestPasswordReset } from '../services/authService';
import { apiErrorMessage } from '../services/format';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not send the reset link'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-gray-100 px-4 py-8">
      <div className="bg-white rounded-2xl shadow-lg p-6 sm:p-8 w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Reset your password</h1>
        {sent ? (
          <p role="status" className="text-sm text-gray-600">
            If an account exists for <span className="font-medium">{email}</span>, we have emailed a link to
            reset its password. The link works once and expires soon.
          </p>
        ) : (
          <form onSubmit={onSubmit} className="space-y-4">
            <p className="text-sm text-gray-500">Enter your account email and we will send you a reset link.</p>
            {error && (
              <p role="alert" className="text-sm text-red-700 bg-red-50 rounded px-3 py-2">
                {error}
              </p>
            )}
            <label className="block text-sm font-medium text-gray-700">
              Email
              <input
                type="email"
                autoComplete="email"
                inputMode="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </label>
            <button type="submit" disabled={submitting} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-lg disabled:opacity-50">
              {submitting ? 'Sending…' : 'Send reset link'}
            </button>
          </form>
        )}
        <Link to="/login" className="block text-sm text-indigo-600 hover:underline">Back to sign in</Link>
      </div>
    </div>
  );
}
