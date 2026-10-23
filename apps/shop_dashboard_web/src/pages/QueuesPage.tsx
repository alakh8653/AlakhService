import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Minus, Plus, UserCheck, UserX } from 'lucide-react';
import { useShopServices } from '../hooks/useShopServices';
import {
  callNext,
  completeEntry,
  customerLabel,
  getQueues,
  getWaiting,
  markNoShow,
  openQueue,
  setAccepting,
  setServers,
  type QueueEntry,
  type WalkInQueue,
} from '../services/queueService';
import { apiErrorMessage, formatClock as clock, formatElapsed } from '../services/format';
import { useToast } from '../components/Toast';

const REFRESH_MS = 15_000;

function QueueCard({ queue, serviceName, onChange }: { queue: WalkInQueue; serviceName: string; onChange: (q: WalkInQueue) => void }) {
  const [entries, setEntries] = useState<QueueEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const toast = useToast();

  const load = useCallback(() => {
    getWaiting(queue.id)
      .then(setEntries)
      .catch(() => setMessage('Could not load the waiting list.'));
  }, [queue.id]);

  useEffect(() => {
    load();
    // Refresh while the page is on screen; catch up as soon as the owner comes back to it.
    const timer = setInterval(() => !document.hidden && load(), REFRESH_MS);
    const onVisible = () => !document.hidden && load();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load]);

  const serving = entries.filter((e) => e.status === 'CALLED');
  const waiting = entries.filter((e) => e.status === 'WAITING');

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
      toast(called ? `Called ${customerLabel(called)}. They have been notified.` : 'Nobody is waiting.');
      load();
      onChange({ ...queue, waiting: Math.max(0, queue.waiting - (called ? 1 : 0)) });
    });

  const finish = (entry: QueueEntry, noShow: boolean) =>
    run(async () => {
      await (noShow ? markNoShow(queue.id, entry.id) : completeEntry(queue.id, entry.id));
      toast(noShow ? `${customerLabel(entry)} marked as a no-show.` : `${customerLabel(entry)} served.`);
      load();
      // Done updates the queue's average service time; pick it up.
      if (!noShow) {
        const fresh = (await getQueues(queue.serviceId)).find((q) => q.id === queue.id);
        if (fresh) onChange(fresh);
      }
    });

  const staff = (delta: number) => run(async () => onChange(await setServers(queue.id, queue.servers + delta)));
  const toggle = () =>
    run(async () => {
      const updated = await setAccepting(queue.id, !queue.isAccepting);
      onChange(updated);
      toast(updated.isAccepting ? `${serviceName} queue reopened to walk-ins.` : `${serviceName} queue closed to new customers. People already waiting stay in line.`);
    });

  return (
    <div className="bg-white rounded-2xl shadow p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            {serviceName}
            <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${queue.isAccepting ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-700'}`}>
              {queue.isAccepting ? 'Open' : 'Closed'}
            </span>
          </h2>
          <p className="text-sm text-gray-600">
            {waiting.length} waiting · about {Math.round(queue.avgServiceMinutes)} min per customer
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" className="flex items-center gap-1 text-sm text-gray-700" aria-label="Staff serving">
            <button
              type="button"
              aria-label="One fewer staff"
              onClick={() => void staff(-1)}
              disabled={busy || queue.servers <= 1}
              className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
            >
              <Minus size={14} aria-hidden />
            </button>
            <span className="w-16 text-center" aria-live="polite">
              {queue.servers} staff
            </span>
            <button
              type="button"
              aria-label="One more staff"
              onClick={() => void staff(1)}
              disabled={busy}
              className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
            >
              <Plus size={14} aria-hidden />
            </button>
          </div>
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
            <UserCheck size={16} aria-hidden /> Call next
          </button>
        </div>
      </div>
      {message && (
        <p role="alert" className="text-sm text-red-700">
          {message}
        </p>
      )}

      {serving.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">Serving now</h3>
          <ul className="divide-y divide-gray-100 text-sm">
            {serving.map((e) => (
              <li key={e.id} className="py-2 flex flex-wrap items-center justify-between gap-2">
                <span>
                  {customerLabel(e)}
                  {e.calledAt && (
                    <span className="text-gray-500">
                      {' '}
                      · called {clock(e.calledAt)} ({formatElapsed(e.calledAt)} ago)
                    </span>
                  )}
                </span>
                <span className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => void finish(e, false)}
                    disabled={busy}
                    className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    <Check size={14} aria-hidden /> Served
                  </button>
                  <button
                    type="button"
                    onClick={() => void finish(e, true)}
                    disabled={busy}
                    className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
                  >
                    <UserX size={14} aria-hidden /> No-show
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {waiting.length > 0 ? (
        <div>
          {serving.length > 0 && (
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1">Waiting</h3>
          )}
          <ol className="divide-y divide-gray-100 text-sm">
            {waiting.map((e) => (
              <li key={e.id} className="py-2 flex flex-wrap justify-between gap-x-3">
                <span>
                  #{e.position} · {customerLabel(e)}
                </span>
                <span className="text-gray-600">
                  joined {clock(e.enteredAt)}
                  {e.estimatedWaitMinutes !== null && ` · ~${e.estimatedWaitMinutes} min`}
                </span>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <p className="text-sm text-gray-500">Nobody is waiting right now.</p>
      )}
    </div>
  );
}

/** Walk-in queues for the shop's services: open one, call customers in turn, close it for the day. */
export default function QueuesPage() {
  const { services, isLoading: servicesLoading } = useShopServices();
  const [queues, setQueues] = useState<WalkInQueue[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (servicesLoading) return;
    const active = services.filter((s) => s.isActive);
    if (active.length === 0) {
      setQueues([]);
      return;
    }
    Promise.all(active.map((s) => getQueues(s.id)))
      .then((lists) => setQueues(lists.flat()))
      .catch(() => setError('Could not load queues. Check your connection and refresh.'));
  }, [services, servicesLoading]);

  const replace = (q: WalkInQueue) => setQueues((list) => (list ?? []).map((x) => (x.id === q.id ? q : x)));

  const open = async (serviceId: string) => {
    try {
      setError(null);
      // Start the wait estimates from the service's listed duration.
      const duration = services.find((s) => s.id === serviceId)?.durationMinutes;
      const created = await openQueue(serviceId, { avgServiceMinutes: duration });
      setQueues((list) => [...(list ?? []), created]);
      toast(`${name(serviceId)} queue is open. Customers can join from the app.`);
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
      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      {queues === null ? (
        <div className="bg-white rounded-2xl shadow h-32 animate-pulse" aria-label="Loading queues" />
      ) : (
        queues.map((q) => <QueueCard key={q.id} queue={q} serviceName={name(q.serviceId)} onChange={replace} />)
      )}
      {withoutQueue.length > 0 && (
        <div className="bg-white rounded-2xl shadow p-5">
          <h2 className="font-semibold text-gray-900">Open a walk-in queue</h2>
          <p className="text-sm text-gray-600 mb-3">Pick a service. Customers can then join the line from the app.</p>
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
        <p className="text-sm text-gray-600">
          Add a service first; queues are opened per service.{' '}
          <Link to="/services" className="text-indigo-600 font-medium underline">
            Go to Services
          </Link>
        </p>
      )}
    </div>
  );
}
