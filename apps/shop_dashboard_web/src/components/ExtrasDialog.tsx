import { useEffect, useState, type FormEvent } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import Dialog from './Dialog';
import { MAX_EXTRA_ITEMS, getExtras, requestExtras } from '../services/bookingService';
import { apiErrorMessage, formatMoney, toMinorUnits } from '../services/format';
import type { ExtrasQuote, QuoteStatus } from '../types';

interface ExtrasDialogProps {
  bookingId: string;
  bookingNumber: string;
  onSent: (quote: ExtrasQuote) => void;
  onClose: () => void;
}

interface Draft {
  description: string;
  amount: string;
}

const STATUS_TEXT: Record<QuoteStatus, string> = {
  PENDING: 'Waiting for the customer',
  APPROVED: 'Approved by the customer',
  DECLINED: 'Declined by the customer',
};
const STATUS_CLASS: Record<QuoteStatus, string> = {
  PENDING: 'text-amber-800',
  APPROVED: 'text-green-800',
  DECLINED: 'text-red-700',
};

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

/**
 * Asks the customer to approve extra charges found during the job: what each is for and how much, and a
 * note. Nothing is added to the bill until they approve; earlier requests are listed with their answer.
 */
export default function ExtrasDialog({ bookingId, bookingNumber, onSent, onClose }: ExtrasDialogProps) {
  const [items, setItems] = useState<Draft[]>([{ description: '', amount: '' }]);
  const [note, setNote] = useState('');
  const [earlier, setEarlier] = useState<ExtrasQuote[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getExtras(bookingId)
      .then((quotes) => {
        if (!cancelled) setEarlier(quotes);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [bookingId]);

  const update = (i: number, change: Partial<Draft>) =>
    setItems((all) => all.map((d, j) => (j === i ? { ...d, ...change } : d)));

  const total = items.reduce((sum, d) => sum + (Number(d.amount) > 0 ? toMinorUnits(Number(d.amount)) : 0), 0);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (items.some((d) => d.description.trim().length < 3)) {
      setError('Say what each charge is for (at least 3 letters).');
      return;
    }
    if (items.some((d) => !(Number(d.amount) > 0))) {
      setError('Enter an amount in rupees for each charge.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const quote = await requestExtras(
        bookingId,
        items.map((d) => ({ description: d.description.trim(), amountCents: toMinorUnits(Number(d.amount)) })),
        note,
      );
      onSent(quote);
      onClose();
    } catch (err) {
      // 409: one is already waiting, or the total is too high; the server says which.
      setError(apiErrorMessage(err, 'Could not send the extra charges'));
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={`Extra charges for #${bookingNumber}`}
      description="The customer must approve these in the app before they are added to the bill. If they decline, the price stays the same."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3" noValidate>
        {earlier.length > 0 && (
          <ul className="text-sm space-y-1 border-b border-gray-100 pb-3" aria-label="Earlier requests">
            {earlier.map((q) => (
              <li key={q.id} className={STATUS_CLASS[q.status]}>
                {formatMoney(q.totalCents)} · {STATUS_TEXT[q.status]}
              </li>
            ))}
          </ul>
        )}
        {items.map((d, i) => (
          <div key={i} className="flex gap-2 items-start">
            <label className="flex-[3] text-xs text-gray-700">
              What is it for?
              <input
                value={d.description}
                maxLength={120}
                onChange={(e) => update(i, { description: e.target.value })}
                className={`mt-1 ${inputClass}`}
                placeholder="New capacitor"
              />
            </label>
            <label className="flex-[2] text-xs text-gray-700">
              Amount (₹)
              <input
                value={d.amount}
                inputMode="decimal"
                onChange={(e) => update(i, { amount: e.target.value.replace(/[^0-9.]/g, '') })}
                className={`mt-1 ${inputClass}`}
                placeholder="350"
              />
            </label>
            {items.length > 1 && (
              <button
                type="button"
                aria-label={`Remove charge ${i + 1}`}
                onClick={() => setItems((all) => all.filter((_, j) => j !== i))}
                className="mt-6 p-2 text-gray-500 hover:text-red-700"
              >
                <Trash2 size={16} aria-hidden />
              </button>
            )}
          </div>
        ))}
        {items.length < MAX_EXTRA_ITEMS && (
          <button
            type="button"
            onClick={() => setItems((all) => [...all, { description: '', amount: '' }])}
            className="flex items-center gap-1 text-sm font-medium text-indigo-700 hover:underline"
          >
            <Plus size={14} aria-hidden /> Add another charge
          </button>
        )}
        <label className="block text-sm text-gray-700">
          Note for the customer <span className="text-gray-500">(optional)</span>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={300} className={`mt-1 ${inputClass}`} />
        </label>
        <p className="text-sm font-medium text-gray-900">Total asked: {formatMoney(total)}</p>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50">
            Not now
          </button>
          <button type="submit" disabled={busy} className="px-4 py-2.5 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50">
            {busy ? 'Sending…' : 'Send to customer'}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
