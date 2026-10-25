import { useState, type FormEvent } from 'react';
import Dialog from './Dialog';

/** Reasons a shop most often cancels; the customer sees the one chosen. */
export const CANCEL_REASONS = [
  'Customer asked to cancel',
  'Staff not available',
  'Shop closed at that time',
  'Customer did not turn up',
] as const;

const OTHER = 'Other';

interface CancelBookingDialogProps {
  bookingNumber: string;
  onConfirm: (reason: string) => Promise<unknown> | void;
  onClose: () => void;
}

/** Asks why before cancelling: the reason is shared with the customer and cannot be undone. */
export default function CancelBookingDialog({ bookingNumber, onConfirm, onClose }: CancelBookingDialogProps) {
  const [choice, setChoice] = useState<string>('');
  const [other, setOther] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const reason = choice === OTHER ? other.trim() : choice;
    if (!reason) {
      setError(choice === OTHER ? 'Write a short reason for the customer.' : 'Choose a reason.');
      return;
    }
    setBusy(true);
    let ok: boolean;
    try {
      ok = (await onConfirm(reason)) !== false;
    } catch {
      ok = false;
    }
    // On failure the page says why; the dialog stays open to try again.
    if (ok) onClose();
    else setBusy(false);
  };

  return (
    <Dialog
      title={`Cancel booking #${bookingNumber}?`}
      description="The customer is told straight away, with the reason you choose. This cannot be undone."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3" noValidate>
        <fieldset>
          <legend className="text-sm font-medium text-gray-700 mb-2">Reason</legend>
          <div className="space-y-2">
            {[...CANCEL_REASONS, OTHER].map((r) => (
              <label
                key={r}
                className={`flex items-center gap-3 border rounded-lg px-3 py-2.5 text-sm cursor-pointer ${
                  choice === r ? 'border-red-400 bg-red-50' : 'border-gray-200'
                }`}
              >
                <input
                  type="radio"
                  name="cancel-reason"
                  value={r}
                  checked={choice === r}
                  onChange={() => {
                    setChoice(r);
                    setError(null);
                  }}
                />
                {r}
              </label>
            ))}
          </div>
        </fieldset>
        {choice === OTHER && (
          <label className="block text-sm text-gray-700">
            Reason for the customer
            <textarea
              value={other}
              onChange={(e) => setOther(e.target.value)}
              rows={2}
              maxLength={300}
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </label>
        )}
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <div className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50">
            Keep booking
          </button>
          <button type="submit" disabled={busy} className="px-4 py-2.5 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50">
            {busy ? 'Cancelling…' : 'Cancel booking'}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
