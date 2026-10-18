import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { apiErrorMessage } from '../shared/apiError';

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

const FOCUSABLE = 'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

/**
 * A modal confirmation for consequential actions: keyboard operable (Escape cancels, Tab stays inside,
 * focus returns to where it was), shows progress while the action runs and its error if it fails.
 */
export default function ConfirmDialog({
  title,
  children,
  confirmLabel,
  tone = 'primary',
  reason,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const bodyId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState(reason?.initial ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const missingReason = !!reason?.required && !text.trim();

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    // The reason box if there is one; otherwise Cancel, so Enter never confirms something destructive by accident.
    const first = dialogRef.current?.querySelector<HTMLElement>(reason ? 'textarea' : '[data-cancel]');
    first?.focus();
    return () => previous?.focus?.();
    // Only on open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      cancel();
      return;
    }
    if (e.key !== 'Tab') return;
    const nodes = [...(dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])];
    if (nodes.length === 0) return;
    const [firstNode, lastNode] = [nodes[0], nodes[nodes.length - 1]];
    if (e.shiftKey && document.activeElement === firstNode) {
      e.preventDefault();
      lastNode.focus();
    } else if (!e.shiftKey && document.activeElement === lastNode) {
      e.preventDefault();
      firstNode.focus();
    }
  };

  const confirmClass =
    tone === 'danger' ? 'bg-red-600 hover:bg-red-700 focus-visible:outline-red-600' : 'bg-indigo-600 hover:bg-indigo-700 focus-visible:outline-indigo-600';

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="absolute inset-0 bg-gray-900/50" aria-hidden="true" onClick={cancel} />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={children ? bodyId : undefined}
        onKeyDown={onKeyDown}
        className="relative w-full max-w-md rounded-2xl bg-white shadow-xl p-6 space-y-4"
      >
        <div className="flex gap-3">
          {tone === 'danger' && (
            <span className="shrink-0 grid place-items-center size-10 rounded-full bg-red-100 text-red-700" aria-hidden="true">
              <AlertTriangle size={20} />
            </span>
          )}
          <div className="space-y-1">
            <h2 id={titleId} className="text-lg font-semibold text-gray-900">
              {title}
            </h2>
            {children && (
              <div id={bodyId} className="text-sm text-gray-600 space-y-2">
                {children}
              </div>
            )}
          </div>
        </div>
        {reason && (
          <label className="block text-sm font-medium text-gray-700">
            {reason.label}
            {reason.required && <span className="text-red-600"> *</span>}
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
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
      </div>
    </div>
  );
}
