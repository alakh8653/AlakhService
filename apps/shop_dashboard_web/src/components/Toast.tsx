import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { CheckCircle2, AlertCircle, X } from 'lucide-react';

type ToastKind = 'success' | 'error';
interface ToastItem {
  id: number;
  message: string;
  kind: ToastKind;
}

type Notify = (message: string, kind?: ToastKind) => void;

const ToastContext = createContext<Notify>(() => undefined);

/** Short confirmation ("Booking confirmed") or failure after an action; read out by screen readers. */
export function useToast(): Notify {
  return useContext(ToastContext);
}

const DISMISS_MS = { success: 4000, error: 7000 };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id));
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
  }, []);

  const notify = useCallback<Notify>(
    (message, kind = 'success') => {
      const id = nextId.current++;
      // Keep at most three on screen.
      setToasts((list) => [...list.slice(-2), { id, message, kind }]);
      timers.current.set(id, setTimeout(() => dismiss(id), DISMISS_MS[kind]));
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((t) => clearTimeout(t));
  }, []);

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div
        aria-live="polite"
        role="status"
        // Top on phones (clear of a dialog's buttons and the thumb), bottom-right on larger screens.
        className="fixed z-[60] top-3 inset-x-3 sm:top-auto sm:bottom-4 sm:inset-x-auto sm:right-4 sm:w-96 flex flex-col gap-2 pointer-events-none"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-2 rounded-xl shadow-lg px-4 py-3 text-sm ${
              t.kind === 'success' ? 'bg-gray-900 text-white' : 'bg-red-600 text-white'
            }`}
          >
            {t.kind === 'success' ? (
              <CheckCircle2 size={18} className="flex-shrink-0 text-green-400" aria-hidden />
            ) : (
              <AlertCircle size={18} className="flex-shrink-0" aria-hidden />
            )}
            <span className="flex-1">{t.message}</span>
            <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="opacity-80 hover:opacity-100">
              <X size={16} aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
