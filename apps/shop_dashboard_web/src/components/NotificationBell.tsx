import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { formatElapsed } from '../services/format';
import { getNotifications, getUnreadCount, markAllRead, markRead, type AppNotification } from '../services/notificationService';

export const UNREAD_POLL_MS = 60_000;

/** The owner's notifications: an unread count on the bell, and the latest ones in a panel. */
export default function NotificationBell() {
  const navigate = useNavigate();
  const panelId = useId();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [error, setError] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  const refreshCount = useCallback(() => {
    getUnreadCount()
      .then(setUnread)
      .catch(() => undefined); // the bell just keeps its last count
  }, []);

  useEffect(() => {
    refreshCount();
    const timer = window.setInterval(refreshCount, UNREAD_POLL_MS);
    return () => window.clearInterval(timer);
  }, [refreshCount]);

  useEffect(() => {
    if (!open) return;
    let live = true;
    setError(false);
    getNotifications(10)
      .then((list) => live && setItems(list))
      .catch(() => live && setError(true));
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        button.current?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      live = false;
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  const openItem = async (n: AppNotification) => {
    if (!n.isRead) {
      setItems((list) => list?.map((x) => (x.id === n.id ? { ...x, isRead: true } : x)) ?? null);
      setUnread((c) => Math.max(0, c - 1));
      markRead(n.id).catch(() => refreshCount());
    }
    if (typeof n.data?.booking_id === 'string') {
      setOpen(false);
      navigate('/bookings');
    }
  };

  const readAll = async () => {
    setItems((list) => list?.map((x) => ({ ...x, isRead: true })) ?? null);
    setUnread(0);
    try {
      await markAllRead();
    } catch {
      refreshCount();
    }
  };

  const label = unread > 0 ? `Notifications, ${unread} unread` : 'Notifications';

  return (
    <div ref={wrapper} className="relative">
      <button
        ref={button}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 rounded-lg text-gray-500 hover:text-indigo-600 hover:bg-indigo-50"
      >
        <Bell size={18} aria-hidden />
        {unread > 0 && (
          <span aria-hidden className="absolute -top-0.5 -right-0.5 min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-red-600 text-white text-[10px] font-bold leading-[1.1rem] text-center">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          id={panelId}
          role="region"
          aria-label="Notifications"
          className="absolute right-0 mt-2 w-[calc(100vw-1.5rem)] max-w-sm z-50 rounded-xl border border-gray-200 bg-white shadow-xl"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900">Notifications</p>
            {items && items.some((n) => !n.isRead) && (
              <button type="button" onClick={() => void readAll()} className="text-xs font-medium text-indigo-600 hover:underline">
                Mark all as read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {error ? (
              <p role="alert" className="px-4 py-6 text-sm text-gray-600">
                Could not load notifications. Please try again.
              </p>
            ) : items === null ? (
              <p role="status" className="px-4 py-6 text-sm text-gray-500">
                Loading…
              </p>
            ) : items.length === 0 ? (
              <p className="px-4 py-6 text-sm text-gray-500">You are all caught up.</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {items.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => void openItem(n)}
                      className={`w-full text-left px-4 py-3 hover:bg-gray-50 ${n.isRead ? '' : 'bg-indigo-50/60'}`}
                    >
                      <span className="flex items-start gap-2">
                        {!n.isRead && <span className="mt-1.5 h-2 w-2 rounded-full bg-indigo-600 shrink-0" aria-hidden />}
                        <span className="min-w-0">
                          <span className="block text-sm font-medium text-gray-900">
                            {n.title}
                            {!n.isRead && <span className="sr-only"> (unread)</span>}
                          </span>
                          <span className="block text-sm text-gray-600 break-words">{n.body}</span>
                          <span className="block text-xs text-gray-400 mt-0.5">{formatElapsed(n.createdAt)} ago</span>
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
