import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import { ArrowDown, ArrowUp, Monitor } from 'lucide-react';
import type { RootState } from '../state/store';
import { useShopServices } from '../hooks/useShopServices';
import { useLive } from '../hooks/useLive';
import { useToast } from '../components/Toast';
import { apiErrorMessage, formatClock } from '../services/format';
import {
  addWalkIn,
  callNext,
  checkIn,
  finish,
  getLine,
  getSettings,
  getTeam,
  liveUrl,
  markNoShow,
  reorder,
  saveSettings,
  setTeamStatus,
  setVip,
  start,
  toLineEntry,
  type LineEntry,
  type QueueSettings,
  type TeamMember,
} from '../services/liveQueueService';

const card = 'bg-white rounded-xl border border-gray-200 p-4 md:p-6';
const button = 'px-3 py-1.5 rounded-lg text-sm font-medium border border-gray-300 hover:bg-gray-50 disabled:opacity-50';
const primary = 'px-3 py-1.5 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50';
const input = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

const REASONS: Record<string, string> = {
  NO_ELIGIBLE_WORKER: 'Nobody working today does this service',
  BEYOND_SHIFT: 'Will not fit before closing',
  PREFERRED_UNAVAILABLE: 'Their chosen professional is away: given to someone else',
};

function waiting(e: LineEntry) {
  return e.state === 'WAITING' || e.state === 'YOUR_TURN';
}

function etaText(e: LineEntry): string | null {
  if (!e.estimatedStart) return null;
  if (e.etaMin && e.etaMax && formatClock(e.etaMin) !== formatClock(e.etaMax)) {
    return `${formatClock(e.etaMin)} – ${formatClock(e.etaMax)}`;
  }
  return `about ${formatClock(e.estimatedStart)}`;
}

/** For someone with their own hours who is not working right now: when they start, or that they are done. */
function offShift(m: TeamMember, now: Date = new Date()): string | null {
  if (!m.worksToday || m.servingBookingId) return null;
  if (m.worksToday.some((s) => new Date(s.start) <= now && now < new Date(s.end))) return null;
  const next = m.worksToday.find((s) => new Date(s.start) > now);
  if (next) return `Starts ${formatClock(next.start)}`;
  return m.worksToday.length ? 'Finished for today' : 'Not working today';
}

function statusText(m: TeamMember): string {
  if (m.status === 'AVAILABLE' && offShift(m)) return offShift(m)!;
  if (m.status === 'BREAK') return m.until ? `On a break until ${formatClock(m.until)}` : 'On a break';
  if (m.status === 'OFF') return 'Off today';
  return m.servingBookingId ? 'Serving' : 'Free';
}

/** "works 12:00 PM – 2:00 PM" for someone with their own hours today; "not working today" when none. */
function worksTodayText(shifts: { start: string; end: string }[]): string {
  if (shifts.length === 0) return 'not working today';
  return `works ${shifts.map((s) => `${formatClock(s.start)} – ${formatClock(s.end)}`).join(', ')}`;
}

/**
 * Today's line at the shop, live: the team (who is free, serving, on a break), every customer waiting in
 * order with their expected time, and what the shop does to it (walk-ins, next customer, move up, VIP,
 * check-in, no-show). Works for any kind of shop: the team's services decide who can take whom.
 */
export default function LiveLinePage() {
  const shop = useSelector((state: RootState) => state.auth.shop);
  const token = useSelector((state: RootState) => state.auth.accessToken);
  const shopId = shop?.id ?? '';
  const toast = useToast();
  const { services } = useShopServices();
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [busy, setBusy] = useState(false);
  const [walkIn, setWalkIn] = useState({ serviceId: '', name: '', vip: false });
  const [settings, setSettingsState] = useState<QueueSettings | null>(null);

  const parse = useCallback((frame: unknown) => {
    const f = frame as { type?: string; entries?: Record<string, unknown>[] };
    return f.type === 'queue' && Array.isArray(f.entries) ? f.entries.map(toLineEntry) : null;
  }, []);
  const load = useCallback(() => getLine(shopId), [shopId]);
  const live = useLive<LineEntry[]>(shopId ? liveUrl(shopId, 'queue', token) : null, parse, load);
  const line = live.data ?? [];

  const loadTeam = useCallback(() => {
    if (shopId) getTeam(shopId).then(setTeam).catch(() => undefined);
  }, [shopId]);
  // The team panel follows the line: whenever it changes, who serves whom may have too.
  useEffect(loadTeam, [loadTeam, live.data]);
  useEffect(() => {
    if (shopId) getSettings(shopId).then(setSettingsState).catch(() => undefined);
  }, [shopId]);

  if (!shop) return null;
  const serviceName = (id: string | null) => services.find((s) => s.id === id)?.name ?? 'A service';
  const queued = line.filter(waiting);

  async function run(action: () => Promise<unknown>, done?: string) {
    setBusy(true);
    try {
      await action();
      if (done) toast(done);
      await live.refresh();
      loadTeam();
    } catch (err) {
      toast(apiErrorMessage(err, 'That did not work'));
    } finally {
      setBusy(false);
    }
  }

  function move(entry: LineEntry, by: number) {
    const ids = queued.map((e) => e.bookingId);
    const from = ids.indexOf(entry.bookingId);
    const to = from + by;
    if (from < 0 || to < 0 || to >= ids.length) return;
    [ids[from], ids[to]] = [ids[to], ids[from]];
    void run(() => reorder(shopId, ids.slice(0, Math.max(from, to) + 1)), `${entry.name} moved ${by < 0 ? 'up' : 'down'}.`);
  }

  function submitWalkIn(e: FormEvent) {
    e.preventDefault();
    if (!walkIn.serviceId || !walkIn.name.trim()) return;
    void run(async () => {
      const added = await addWalkIn(shopId, walkIn);
      setWalkIn({ serviceId: walkIn.serviceId, name: '', vip: false });
      toast(`${added.name} is #${added.position ?? '–'} in line${added.staffName ? ` with ${added.staffName}` : ''}.`);
    });
  }

  function submitSettings(e: FormEvent) {
    e.preventDefault();
    if (!settings) return;
    void run(async () => setSettingsState(await saveSettings(shopId, settings)), 'Line settings saved.');
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Live line</h1>
          <p className="text-sm text-gray-500">
            Everyone at the shop today, in order, with the time each can expect.{' '}
            <span data-testid="live-status">{live.connected ? 'Live.' : 'Updating every 30 seconds.'}</span>
          </p>
        </div>
        <a href={`/board/${encodeURIComponent(shopId)}`} target="_blank" rel="noreferrer" className={`${button} inline-flex items-center gap-2`}>
          <Monitor size={16} aria-hidden /> Screen for the shop
        </a>
      </div>

      <section aria-label="Team" className={card}>
        <h2 className="font-medium text-gray-900 mb-3">Team today</h2>
        {team.length === 0 ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-gray-500">Add your team on the Staff page to share the line between them.</p>
            <button type="button" className={primary} disabled={busy || queued.length === 0} onClick={() => run(() => callNext(shopId), 'Next customer started.')}>
              Next customer
            </button>
          </div>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {team.map((m) => (
              <li key={m.staffId} aria-label={m.name ?? 'Team member'} className="rounded-lg border border-gray-200 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900">{m.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${m.status === 'AVAILABLE' && !offShift(m) ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>{statusText(m)}</span>
                </div>
                {m.servingBookingId && (
                  <p className="text-sm text-gray-700">
                    {m.servingName}
                    {m.servingUntil && ` · until about ${formatClock(m.servingUntil)}`}
                    {m.overrun && <span className="ml-1 text-red-700">· running over</span>}
                  </p>
                )}
                <p className="text-xs text-gray-500">
                  {m.waiting === 1 ? '1 customer planned' : `${m.waiting} customers planned`}
                  {m.worksToday && ` · ${worksTodayText(m.worksToday)}`}
                </p>
                <div className="flex flex-wrap gap-2">
                  {m.servingBookingId ? (
                    <button type="button" className={primary} disabled={busy} onClick={() => run(() => finish(m.servingBookingId!), `${m.servingName} done.`)}>
                      Done
                    </button>
                  ) : (
                    m.status === 'AVAILABLE' && !offShift(m) && (
                      <button type="button" className={primary} disabled={busy} onClick={() => run(() => callNext(shopId, m.staffId), `${m.name} has their next customer.`)}>
                        Next customer
                      </button>
                    )
                  )}
                  {m.status === 'AVAILABLE' ? (
                    <>
                      <button type="button" className={button} disabled={busy} onClick={() => run(() => setTeamStatus(shopId, m.staffId, 'BREAK', 15), `${m.name} is on a 15-minute break.`)}>
                        Break 15 min
                      </button>
                      <button type="button" className={button} disabled={busy} onClick={() => run(() => setTeamStatus(shopId, m.staffId, 'OFF'), `${m.name} is off today; their customers move to the others.`)}>
                        Off today
                      </button>
                    </>
                  ) : (
                    <button type="button" className={button} disabled={busy} onClick={() => run(() => setTeamStatus(shopId, m.staffId, 'AVAILABLE'), `${m.name} is back.`)}>
                      Back
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <form aria-label="Add a walk-in" onSubmit={submitWalkIn} className={`${card} grid gap-3 md:grid-cols-[1fr_1fr_auto_auto] items-end`}>
        <label className="text-sm text-gray-700">
          Service
          <select className={input} value={walkIn.serviceId} onChange={(e) => setWalkIn({ ...walkIn, serviceId: e.target.value })}>
            <option value="">Choose…</option>
            {services
              .filter((s) => s.isActive)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
        </label>
        <label className="text-sm text-gray-700">
          Name to call out
          <input className={input} value={walkIn.name} maxLength={80} onChange={(e) => setWalkIn({ ...walkIn, name: e.target.value })} />
        </label>
        <label className="text-sm text-gray-700 flex items-center gap-2 pb-2">
          <input type="checkbox" checked={walkIn.vip} onChange={(e) => setWalkIn({ ...walkIn, vip: e.target.checked })} /> VIP
        </label>
        <button type="submit" className={primary} disabled={busy || !walkIn.serviceId || !walkIn.name.trim()}>
          Add walk-in
        </button>
      </form>

      <section aria-label="Line" className={card}>
        <h2 className="font-medium text-gray-900 mb-3">
          In line today <span className="text-gray-500 font-normal">({queued.length} waiting)</span>
        </h2>
        {line.length === 0 ? (
          <p className="text-sm text-gray-500">{live.error ? apiErrorMessage(live.error, 'Could not load the line.') : 'Nobody is in line right now.'}</p>
        ) : (
          <ol className="divide-y divide-gray-100" aria-label="Customers in line">
            {line.map((e) => {
              const i = queued.indexOf(e);
              return (
                <li key={e.bookingId} aria-label={e.name} className="py-3 flex flex-wrap items-center gap-3">
                  <span className="w-14 text-sm font-semibold text-gray-900">{e.state === 'IN_PROGRESS' ? 'Now' : e.position ? `#${e.position}` : '–'}</span>
                  <div className="flex-1 min-w-[12rem]">
                    <p className="text-sm font-medium text-gray-900">
                      {e.name}
                      {e.priority === 'VIP' && <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-800">VIP</span>}
                      {e.source === 'WALK_IN' && <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-700">Walk-in</span>}
                      {e.checkedIn && e.source !== 'WALK_IN' && <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-800">Here</span>}
                      {e.moved && <span className="ml-2 text-xs text-gray-500">moved</span>}
                    </p>
                    <p className="text-xs text-gray-600">
                      {serviceName(e.serviceId)}
                      {e.staffName && ` · ${e.staffName}`}
                      {e.state === 'IN_PROGRESS'
                        ? e.estimatedEnd && ` · until about ${formatClock(e.estimatedEnd)}`
                        : etaText(e) && ` · ${etaText(e)}`}
                      {waiting(e) && e.runningLateMinutes > 0 && <span className="text-red-700"> · {e.runningLateMinutes} min late</span>}
                      {e.overrun && <span className="text-red-700"> · running over</span>}
                    </p>
                    {e.state === 'CHECK_IN_NEEDED' && <p className="text-xs text-amber-700">Late and not checked in: out of the line until they arrive.</p>}
                    {e.reason && REASONS[e.reason] && <p className="text-xs text-amber-700">{REASONS[e.reason]}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {waiting(e) && (
                      <>
                        <button type="button" className={button} aria-label={`Move ${e.name} up`} disabled={busy || i <= 0} onClick={() => move(e, -1)}>
                          <ArrowUp size={14} aria-hidden />
                        </button>
                        <button type="button" className={button} aria-label={`Move ${e.name} down`} disabled={busy || i < 0 || i >= queued.length - 1} onClick={() => move(e, 1)}>
                          <ArrowDown size={14} aria-hidden />
                        </button>
                        <button type="button" className={button} disabled={busy} onClick={() => run(() => start(e.bookingId, e.staffId), `${e.name} started.`)}>
                          Start
                        </button>
                        <button type="button" className={button} disabled={busy} onClick={() => run(() => setVip(e.bookingId, e.priority !== 'VIP'), e.priority === 'VIP' ? `${e.name} is a regular again.` : `${e.name} is a VIP.`)}>
                          {e.priority === 'VIP' ? 'Not VIP' : 'VIP'}
                        </button>
                      </>
                    )}
                    {(waiting(e) || e.state === 'CHECK_IN_NEEDED') && !e.checkedIn && (
                      <button type="button" className={button} disabled={busy} onClick={() => run(() => checkIn(e.bookingId), `${e.name} checked in.`)}>
                        Check in
                      </button>
                    )}
                    {e.canMarkNoShow && (
                      <button type="button" className={button} disabled={busy} onClick={() => run(() => markNoShow(e.bookingId), `${e.name} marked as a no-show.`)}>
                        No-show
                      </button>
                    )}
                    {e.state === 'IN_PROGRESS' && (
                      <button type="button" className={primary} disabled={busy} onClick={() => run(() => finish(e.bookingId), `${e.name} done.`)}>
                        Done
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {settings && (
        <details className={card}>
          <summary className="font-medium text-gray-900 cursor-pointer">Line settings</summary>
          <form aria-label="Line settings" onSubmit={submitSettings} className="mt-4 grid gap-3 md:grid-cols-3">
            <label className="text-sm text-gray-700">
              Grace period before a no-show (minutes)
              <input type="number" min={0} max={120} className={input} value={settings.graceMinutes} onChange={(e) => setSettingsState({ ...settings, graceMinutes: Number(e.target.value) })} />
            </label>
            <label className="text-sm text-gray-700">
              Walk-ins go with appointments after (minutes)
              <input type="number" min={1} max={480} className={input} value={settings.agingMinutes} onChange={(e) => setSettingsState({ ...settings, agingMinutes: Number(e.target.value) })} />
            </label>
            <label className="text-sm text-gray-700">
              VIPs a day at most
              <input type="number" min={0} max={100} className={input} value={settings.vipPerDay} onChange={(e) => setSettingsState({ ...settings, vipPerDay: Number(e.target.value) })} />
            </label>
            <label className="text-sm text-gray-700">
              Extra time on every service (%)
              <input type="number" min={0} max={100} className={input} value={Math.round(settings.bufferPct * 100)} onChange={(e) => setSettingsState({ ...settings, bufferPct: Number(e.target.value) / 100 })} />
            </label>
            <label className="text-sm text-gray-700 flex items-center gap-2 md:col-span-2">
              <input type="checkbox" checked={settings.checkInRequired} onChange={(e) => setSettingsState({ ...settings, checkInRequired: e.target.checked })} />
              Customers must check in when they arrive (late ones rejoin the line when they do)
            </label>
            <div className="md:col-span-3">
              <button type="submit" className={primary} disabled={busy}>
                Save settings
              </button>
            </div>
          </form>
        </details>
      )}
    </div>
  );
}
