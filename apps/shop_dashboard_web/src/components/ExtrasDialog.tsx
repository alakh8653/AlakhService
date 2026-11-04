import { useEffect, useState, type FormEvent } from 'react';
import Dialog from './Dialog';
import { MAX_EXTRA_CENTS, askExtraCharge, getExtraCharges } from '../services/bookingService';
import { apiErrorMessage, formatMoney, toMinorUnits } from '../services/format';
import type { Booking, ExtraCharge, ExtraChargeStatus } from '../types';

interface ExtrasDialogProps {
  bookingId: string;
  bookingNumber: string;
  /** The booking as the server has it after the request (now waiting on the customer). */
  onSent: (booking: Booking) => void;
  onClose: () => void;
}

const STATUS_TEXT: Record<ExtraChargeStatus, string> = {
  PENDING: 'Waiting for the customer',
  APPROVED: 'Approved by the customer',
  DECLINED: 'Declined by the customer',
  WITHDRAWN: 'Taken back',
  EXPIRED: 'No longer applies',
};
const STATUS_CLASS: Record<ExtraChargeStatus, string> = {
  PENDING: 'text-amber-800',
  APPROVED: 'text-green-800',
  DECLINED: 'text-red-700',
  WITHDRAWN: 'text-gray-600',
  EXPIRED: 'text-gray-600',
};

const inputClass =
  'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

/**
 * Asks the customer to agree to an extra charge found once the job was seen: how much and why. Nothing is
 * added to the bill until they approve; earlier requests are listed with their answer.
 */
export default function ExtrasDialog({ bookingId, bookingNumber, onSent, onClose }: ExtrasDialogProps) {
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [earlier, setEarlier] = useState<ExtraCharge[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getExtraCharges(bookingId)
      .then((charges) => {
        if (!cancelled) setEarlier(charges);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [bookingId]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const cents = Number(amount) > 0 ? toMinorUnits(Number(amount)) : 0;
    if (reason.trim().length < 3) {
      setError('Say what the extra charge is for (at least 3 letters).');
      return;
    }
    if (cents <= 0 || cents > MAX_EXTRA_CENTS) {
      setError(`Enter an amount in rupees, up to ${formatMoney(MAX_EXTRA_CENTS)}.`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onSent(await askExtraCharge(bookingId, cents, reason));
      onClose();
    } catch (err) {
      // 409: already paid, a package or walk-in, or one still waiting; the server says which.
      setError(apiErrorMessage(err, 'Could not send the extra charge'));
      setBusy(false);
    }
  };

  return (
    <Dialog
      title={`Extra charge for #${bookingNumber}`}
      description="The customer must approve this in the app before it is added to the bill. If they decline, the price stays the same."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3" noValidate>
        {earlier.length > 0 && (
          <ul className="text-sm space-y-1 border-b border-gray-100 pb-3" aria-label="Earlier requests">
            {earlier.map((c) => (
              <li key={c.id} className={STATUS_CLASS[c.status]}>
                {formatMoney(c.amountCents)} for {c.reason} · {STATUS_TEXT[c.status]}
              </li>
            ))}
          </ul>
        )}
        <label className="block text-sm text-gray-700">
          What is it for?
          <input
            value={reason}
            maxLength={200}
            onChange={(e) => setReason(e.target.value)}
            className={`mt-1 ${inputClass}`}
            placeholder="New capacitor"
          />
        </label>
        <label className="block text-sm text-gray-700">
          Amount (₹)
          <input
            value={amount}
            inputMode="decimal"
            onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))}
            className={`mt-1 ${inputClass} max-w-40`}
            placeholder="350"
          />
        </label>
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
