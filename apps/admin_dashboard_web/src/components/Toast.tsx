import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import { CheckCircle2, X, XCircle } from 'lucide-react';

type Tone = 'success' | 'error';
interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}

type Notify = (message: string, tone?: Tone) => void;

const ToastContext = createContext<Notify>(() => {});

/** Brief confirmations ("User banned") after an action, announced to screen readers. */
export function useToast(): Notify {
  return useContext(ToastContext);
}

const DURATION_MS = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  const notify = useCallback<Notify>(
    (message, tone = 'success') => {
      const id = nextId.current++;
      setToasts((list) => [...list.slice(-2), { id, message, tone }]);
      window.setTimeout(() => dismiss(id), DURATION_MS);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="fixed bottom-4 right-4 left-4 sm:left-auto z-[60] flex flex-col gap-2 items-stretch sm:items-end pointer-events-none"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-2 rounded-xl px-4 py-3 text-sm shadow-lg sm:max-w-sm ${
              t.tone === 'success' ? 'bg-gray-900 text-white' : 'bg-red-700 text-white'
            }`}
          >
            {t.tone === 'success' ? <CheckCircle2 size={18} className="shrink-0 text-green-400" aria-hidden="true" /> : <XCircle size={18} className="shrink-0" aria-hidden="true" />}
            <span className="flex-1">{t.message}</span>
            <button type="button" aria-label="Dismiss" onClick={() => dismiss(t.id)} className="shrink-0 opacity-80 hover:opacity-100">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
