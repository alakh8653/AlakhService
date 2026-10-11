import { useCallback, useEffect, useState } from 'react';
import { UserCheck } from 'lucide-react';
import { useShopServices } from '../hooks/useShopServices';
import {
  callNext,
  getQueues,
  getWaiting,
  openQueue,
  setAccepting,
  type QueueEntry,
  type WalkInQueue,
} from '../services/queueService';
import { apiErrorMessage, shortId } from '../services/format';

const REFRESH_MS = 15_000;

function QueueCard({ queue, serviceName, onChange }: { queue: WalkInQueue; serviceName: string; onChange: (q: WalkInQueue) => void }) {
  const [waiting, setWaiting] = useState<QueueEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    getWaiting(queue.id)
      .then(setWaiting)
      .catch(() => setMessage('Could not load the waiting list.'));
  }, [queue.id]);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setMessage(null);
    try {
      await action();
    } catch (err) {
      setMessage(apiErrorMessage(err, 'That did not work'));
    } finally {
      setBusy(false);
    }
  };

  const next = () =>
    run(async () => {
      const called = await callNext(queue.id);
      setMessage(called ? `Called customer ${shortId(called.customerId)}. They have been notified.` : 'Nobody is waiting.');
      load();
      onChange({ ...queue, waiting: Math.max(0, queue.waiting - (called ? 1 : 0)) });
    });

  const toggle = () => run(async () => onChange(await setAccepting(queue.id, !queue.isAccepting)));

  return (
    <div className="bg-white rounded-2xl shadow p-5 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-gray-900">{serviceName}</h2>
          <p className="text-sm text-gray-500">
            {waiting.length} waiting · {queue.isAccepting ? 'Open to walk-ins' : 'Closed to new customers'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void toggle()}
            disabled={busy}
            className="px-3 py-2 rounded-lg text-sm border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
          >
            {queue.isAccepting ? 'Close queue' : 'Reopen queue'}
          </button>
          <button
            type="button"
            onClick={() => void next()}
            disabled={busy || waiting.length === 0}
            className="flex items-center gap-1 bg-indigo-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            <UserCheck size={16} /> Call next
          </button>
        </div>
      </div>
      {message && <p className="text-sm text-gray-700">{message}</p>}
      {waiting.length > 0 ? (
        <ol className="divide-y divide-gray-100 text-sm">
          {waiting.map((e) => (
            <li key={e.id} className="py-2 flex justify-between">
              <span>
                #{e.position} · Customer {shortId(e.customerId)}
              </span>
              <span className="text-gray-500">
                joined {new Date(e.enteredAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-gray-500">Nobody is waiting right now.</p>
      )}
    </div>
  );
}

/** Walk-in queues for the shop's services: open one, call customers in turn, close it for the day. */
export default function QueuesPage() {
  const { services } = useShopServices();
  const [queues, setQueues] = useState<WalkInQueue[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const active = services.filter((s) => s.isActive);
    if (active.length === 0) {
      setQueues([]);
      return;
    }
    Promise.all(active.map((s) => getQueues(s.id)))
      .then((lists) => setQueues(lists.flat()))
      .catch(() => setError('Could not load queues.'));
  }, [services]);

  const replace = (q: WalkInQueue) => setQueues((list) => (list ?? []).map((x) => (x.id === q.id ? q : x)));

  const open = async (serviceId: string) => {
    try {
      setError(null);
      const created = await openQueue(serviceId);
      setQueues((list) => [...(list ?? []), created]);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not open the queue'));
    }
  };

  const withoutQueue = services.filter((s) => s.isActive && !queues?.some((q) => q.serviceId === s.id));
  const name = (serviceId: string) => services.find((s) => s.id === serviceId)?.name ?? 'Service';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Walk-in queues</h1>
        <p className="text-gray-500 text-sm">Customers join from the app and see their place update as you call them.</p>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {queues === null ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : (
        queues.map((q) => <QueueCard key={q.id} queue={q} serviceName={name(q.serviceId)} onChange={replace} />)
      )}
      {withoutQueue.length > 0 && (
        <div className="bg-white rounded-2xl shadow p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Open a queue</h2>
          <div className="flex flex-wrap gap-2">
            {withoutQueue.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => void open(s.id)}
                className="px-3 py-2 rounded-lg text-sm border border-indigo-300 text-indigo-700 hover:bg-indigo-50"
              >
                + {s.name}
              </button>
            ))}
          </div>
        </div>
      )}
      {queues !== null && services.length === 0 && (
        <p className="text-sm text-gray-500">Add a service first; queues are opened per service.</p>
      )}
    </div>
  );
}
