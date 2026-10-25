import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react';

const FOCUSABLE = 'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  title: ReactNode;
  children: ReactNode;
  onClose: () => void;
  /** Selector for the element to focus first; defaults to the first focusable one. */
  initialFocus?: string;
  /** Element ids describing the dialog. */
  describedBy?: string;
  size?: 'md' | 'lg';
}

/**
 * An accessible modal dialog: Escape and the backdrop close it, Tab stays inside, and focus goes
 * back to where it was when it closes.
 */
export default function Modal({ title, children, onClose, initialFocus, describedBy, size = 'md' }: ModalProps) {
  const titleId = useId();
  const ref = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const target = initialFocus ? ref.current?.querySelector<HTMLElement>(initialFocus) : ref.current?.querySelector<HTMLElement>(FOCUSABLE);
    (target ?? ref.current)?.focus();
    return () => previous?.focus?.();
    // Only when it opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onCloseRef.current();
      return;
    }
    if (e.key !== 'Tab') return;
    const nodes = [...(ref.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])];
    if (nodes.length === 0) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="absolute inset-0 bg-gray-900/50" aria-hidden="true" onClick={() => onCloseRef.current()} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={describedBy}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className={`relative w-full ${size === 'lg' ? 'max-w-2xl' : 'max-w-md'} max-h-[90dvh] overflow-y-auto rounded-2xl bg-white shadow-xl p-6 space-y-4 focus:outline-none`}
      >
        <h2 id={titleId} className="text-lg font-semibold text-gray-900">
          {title}
        </h2>
        {children}
      </div>
    </div>
  );
}
