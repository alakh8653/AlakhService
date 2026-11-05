import { useState, type FormEvent } from 'react';
import Dialog from './Dialog';

const REASONS = ['Spare parts', 'Extra work', 'Materials'];
const OTHER = 'Something else';

interface ExtraChargeDialogProps {
  bookingNumber: string;
  /** Resolves to false when it could not be sent, so that the dialog stays open. */
  onConfirm: (amountCents: number, reason: string) => Promise<unknown> | void;
  onClose: () => void;
}

/** Asks for more once the job has been seen: the customer must approve before the price changes. */
export default function ExtraChargeDialog({ bookingNumber, onConfirm, onClose }: ExtraChargeDialogProps) {
  const [choice, setChoice] = useState('');
  const [other, setOther] = useState('');
  const [amount, setAmount] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const reason = choice === OTHER ? other.trim() : choice;
    const rupees = Number(amount);
    if (!reason || reason.length < 3) {
      setError('Choose what it is for.');
      return;
    }
    if (!Number.isInteger(rupees) || rupees <= 0) {
      setError('Enter the amount in whole rupees.');
      return;
    }
    setSending(true);
    setError(null);
    let ok: boolean;
    try {
      ok = (await onConfirm(rupees * 100, reason)) !== false;
    } finally {
      setSending(false);
    }
    if (ok) onClose();
  };

  return (
    <Dialog
      title={`Add an extra charge to #${bookingNumber}`}
      description="The customer must approve this in the app before the price changes. If they decline, it stays as it was."
      onClose={onClose}
    >
      <form onSubmit={(e) => void submit(e)} className="space-y-3" noValidate>
        <fieldset>
          <legend className="text-sm font-medium text-gray-700 mb-2">What is it for?</legend>
          <div className="space-y-2">
            {[...REASONS, OTHER].map((r) => (
              <label key={r} className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2 text-sm">
                <input type="radio" name="extra-reason" value={r} checked={choice === r} onChange={() => setChoice(r)} />
                {r}
              </label>
            ))}
          </div>
        </fieldset>
        {choice === OTHER && (
          <label className="block text-sm font-medium text-gray-700">
            Reason for the customer
            <input
              maxLength={200}
              value={other}
              onChange={(e) => setOther(e.target.value)}
              className="mt-1 block w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </label>
        )}
        <label className="block text-sm font-medium text-gray-700">
          How much more (₹)
          <input
            type="number"
            min="1"
            step="1"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="mt-1 block w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="border border-gray-300 rounded-lg px-4 py-2 text-sm">
            Not now
          </button>
          <button type="submit" disabled={sending} className="bg-indigo-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50">
            Send to customer
          </button>
        </div>
      </form>
    </Dialog>
  );
}
