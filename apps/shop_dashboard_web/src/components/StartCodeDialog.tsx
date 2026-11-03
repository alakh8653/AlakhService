import { useState, type FormEvent } from 'react';
import Dialog from './Dialog';

interface StartCodeDialogProps {
  bookingNumber: string;
  /** Starts the job with the code: resolves to null once started, or the reason it was refused. */
  onSubmit: (code: string) => Promise<string | null>;
  onClose: () => void;
}

/** Asks for the customer's 4-digit start code; the job does not start without it. */
export default function StartCodeDialog({ bookingNumber, onSubmit, onClose }: StartCodeDialogProps) {
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!/^\d{4}$/.test(code)) {
      setError('Enter the 4-digit code the customer has.');
      return;
    }
    setBusy(true);
    setError(null);
    const refused = await onSubmit(code);
    if (refused === null) {
      onClose();
      return;
    }
    setError(refused);
    setBusy(false);
  };

  return (
    <Dialog
      title={`Start booking #${bookingNumber}`}
      description="Ask the customer for their 4-digit start code. They see it in the app and share it only once your staff has arrived."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3" noValidate>
        <label className="block text-sm font-medium text-gray-700">
          Start code
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 4))}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={4}
            aria-invalid={!!error}
            className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-2xl tracking-[0.5em] text-center focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
            {busy ? 'Starting…' : 'Start job'}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
