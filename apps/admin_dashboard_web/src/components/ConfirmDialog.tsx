import { useId, useState, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { apiErrorMessage } from '../shared/apiError';
import Modal from './Modal';

export interface ConfirmDialogProps {
  title: string;
  /** What will happen, in plain words. */
  children?: ReactNode;
  confirmLabel: string;
  /** `danger` for actions that take something away or cannot be undone. */
  tone?: 'danger' | 'primary';
  /** Asks for a reason (or note) before confirming; it is passed to [onConfirm]. */
  reason?: { label: string; placeholder?: string; required?: boolean; initial?: string };
  /** Runs the action. If it throws, the dialog stays open and shows the API's message. */
  onConfirm: (reason: string) => Promise<void> | void;
  onCancel: () => void;
}

/**
 * A modal confirmation for consequential actions: keyboard operable (Escape cancels, Tab stays inside,
 * focus returns to where it was), shows progress while the action runs and its error if it fails.
 */
export default function ConfirmDialog({ title, children, confirmLabel, tone = 'primary', reason, onConfirm, onCancel }: ConfirmDialogProps) {
  const bodyId = useId();
  const [text, setText] = useState(reason?.initial ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const missingReason = !!reason?.required && !text.trim();

  const cancel = () => {
    if (!busy) onCancel();
  };

  const confirm = async () => {
    if (busy || missingReason) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm(text.trim());
    } catch (e) {
      setError(apiErrorMessage(e, 'That did not work. Please try again.'));
      setBusy(false);
    }
  };

  const confirmClass =
    tone === 'danger' ? 'bg-red-600 hover:bg-red-700 focus-visible:outline-red-600' : 'bg-indigo-600 hover:bg-indigo-700 focus-visible:outline-indigo-600';

  return (
    <Modal
      title={
        <span className="flex items-center gap-3">
          {tone === 'danger' && (
            <span className="shrink-0 grid place-items-center size-9 rounded-full bg-red-100 text-red-700" aria-hidden="true">
              <AlertTriangle size={18} />
            </span>
          )}
          {title}
        </span>
      }
      onClose={cancel}
      // The reason box if there is one; otherwise Cancel, so Enter never confirms something destructive by accident.
      initialFocus={reason ? 'textarea' : '[data-cancel]'}
      describedBy={children ? bodyId : undefined}
    >
      {children && (
        <div id={bodyId} className="text-sm text-gray-700 space-y-2">
          {children}
        </div>
      )}
      {reason && (
        <label className="block text-sm font-medium text-gray-700">
          {reason.label}
          {reason.required && <span className="text-red-700"> *</span>}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void confirm();
            }}
            rows={3}
            placeholder={reason.placeholder}
            aria-required={reason.required || undefined}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-normal focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </label>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
        <button
          type="button"
          data-cancel
          onClick={cancel}
          disabled={busy}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => void confirm()}
          disabled={busy || missingReason}
          className={`rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 ${confirmClass}`}
        >
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
