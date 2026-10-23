import { useEffect, useState, type FormEvent } from 'react';
import { apiErrorMessage } from '../services/format';
import {
  getPayoutDetails,
  isValidAccountNumber,
  isValidIfsc,
  isValidUpi,
  savePayoutDetails,
  type PayoutDetails,
  type PayoutMethod,
} from '../services/kycService';
import { useToast } from './Toast';

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

/** Where the platform sends the shop's earnings: a bank account or a UPI id. */
export default function PayoutDetailsForm({ shopId, onSaved }: { shopId: string; onSaved?: (d: PayoutDetails) => void }) {
  const toast = useToast();
  const [current, setCurrent] = useState<PayoutDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [method, setMethod] = useState<PayoutMethod>('BANK');
  const [accountName, setAccountName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [confirmNumber, setConfirmNumber] = useState('');
  const [ifsc, setIfsc] = useState('');
  const [upiId, setUpiId] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getPayoutDetails(shopId)
      .then((d) => {
        if (!live || !d) return;
        setCurrent(d);
        setMethod(d.method);
        setAccountName(d.accountName ?? '');
        setIfsc(d.ifsc ?? '');
        setUpiId(d.upiId ?? '');
      })
      .catch((e) => live && setLoadError(apiErrorMessage(e, 'Could not load your payout details.')))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [shopId]);

  const errors: Record<string, string | undefined> =
    method === 'BANK'
      ? {
          accountName: accountName.trim().length < 2 ? 'Enter the name on the bank account' : undefined,
          accountNumber: !isValidAccountNumber(accountNumber) ? 'Enter 9 to 18 digits' : undefined,
          confirmNumber: accountNumber.replace(/\s/g, '') !== confirmNumber.replace(/\s/g, '') ? 'The account numbers do not match' : undefined,
          ifsc: !isValidIfsc(ifsc) ? 'IFSC is 11 characters, like HDFC0001234' : undefined,
        }
      : { upiId: !isValidUpi(upiId) ? 'Enter a UPI id like yourshop@okhdfcbank' : undefined };
  const hasErrors = Object.values(errors).some(Boolean);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    if (hasErrors || saving) return;
    setSaving(true);
    setServerError(null);
    try {
      const saved = await savePayoutDetails(shopId, { method, accountName, accountNumber, ifsc, upiId });
      setCurrent(saved);
      setAccountNumber('');
      setConfirmNumber('');
      setSubmitted(false);
      toast('Payout details saved');
      onSaved?.(saved);
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not save your payout details'));
    } finally {
      setSaving(false);
    }
  };

  const field = (id: string, label: string, value: string, set: (v: string) => void, props: Record<string, unknown> = {}) => {
    const error = submitted ? errors[id] : undefined;
    return (
      <div>
        <label htmlFor={`payout-${id}`} className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
        <input
          id={`payout-${id}`}
          value={value}
          onChange={(e) => set(e.target.value)}
          aria-invalid={!!error}
          aria-describedby={error ? `payout-${id}-error` : undefined}
          className={inputClass}
          {...props}
        />
        {error && (
          <p id={`payout-${id}-error`} className="mt-1 text-xs text-red-600">
            {error}
          </p>
        )}
      </div>
    );
  };

  if (loading) return <p role="status" className="text-sm text-gray-500">Loading payout details…</p>;

  return (
    <form onSubmit={(e) => void submit(e)} noValidate className="space-y-4" aria-label="Payout details">
      {loadError && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {loadError}
        </p>
      )}
      {current && (
        <p className="text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
          Payouts go to{' '}
          <span className="font-medium text-gray-900">
            {current.method === 'BANK' ? `account ${current.accountNumber} (${current.ifsc})` : `UPI ${current.upiId}`}
          </span>
          . Saving below replaces it.
        </p>
      )}
      <fieldset>
        <legend className="block text-sm font-medium text-gray-700 mb-2">Pay me by</legend>
        <div className="flex gap-4">
          {(['BANK', 'UPI'] as PayoutMethod[]).map((m) => (
            <label key={m} className="flex items-center gap-2 text-sm text-gray-700">
              <input type="radio" name="payout-method" value={m} checked={method === m} onChange={() => setMethod(m)} />
              {m === 'BANK' ? 'Bank transfer' : 'UPI'}
            </label>
          ))}
        </div>
      </fieldset>
      {method === 'BANK' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {field('accountName', 'Account holder name', accountName, setAccountName, { autoComplete: 'name' })}
          {field('ifsc', 'IFSC', ifsc, (v) => setIfsc(v.toUpperCase()), { autoComplete: 'off', maxLength: 11, spellCheck: false })}
          {field('accountNumber', 'Account number', accountNumber, setAccountNumber, { inputMode: 'numeric', autoComplete: 'off' })}
          {field('confirmNumber', 'Re-enter account number', confirmNumber, setConfirmNumber, { inputMode: 'numeric', autoComplete: 'off' })}
        </div>
      ) : (
        field('upiId', 'UPI id', upiId, setUpiId, { autoComplete: 'off', spellCheck: false, placeholder: 'yourshop@okhdfcbank' })
      )}
      {serverError && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {serverError}
        </p>
      )}
      <button type="submit" disabled={saving} className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50">
        {saving ? 'Saving…' : 'Save payout details'}
      </button>
    </form>
  );
}
