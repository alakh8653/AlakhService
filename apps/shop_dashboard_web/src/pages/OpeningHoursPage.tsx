import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import { Plus, Trash2, Copy, CalendarOff, Users } from 'lucide-react';
import type { RootState } from '../state/store';
import type { OpenInterval, ShopHours } from '../types';
import { addHoliday, getShopHours, removeHoliday, saveCapacity, saveWeeklyHours } from '../services/shopService';
import { apiErrorMessage } from '../services/format';
import { DAY_NAMES, MAX_INTERVALS, dayProblem, normalizeDay, suggestedWeek, todayInIndia } from '../services/hours';
import Switch from '../components/Switch';
import { useToast } from '../components/Toast';

const input =
  'border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';
const card = 'bg-white rounded-2xl shadow p-4 md:p-6';
// Narrow enough that two times, "to" and a remove button fit one line on a 390px phone.
const timeInput =
  'w-28 border border-gray-300 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

/** A time box can't show 24:00, so a shop open till midnight closes at 00:00 in the editor. */
const forEditor = (week: OpenInterval[][]) => week.map((day) => day.map((i) => ({ ...i, end: i.end === '24:00' ? '00:00' : i.end })));

const holidayLabel = (date: string) =>
  new Date(`${date}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

function WeeklyHoursEditor({ hours, onSaved }: { hours: ShopHours; onSaved: (h: ShopHours) => void }) {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const toast = useToast();
  const initial = () => forEditor(hours.configured ? hours.weekly : suggestedWeek());
  const [week, setWeek] = useState<OpenInterval[][]>(initial);
  // Hours a day had before it was switched off, so switching it back on doesn't lose them.
  const [remembered, setRemembered] = useState<OpenInterval[][]>(initial);
  const [dirty, setDirty] = useState(!hours.configured);
  const [showErrors, setShowErrors] = useState(false);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const problems = week.map(dayProblem);

  const update = (day: number, intervals: OpenInterval[]) => {
    setWeek((w) => w.map((d, i) => (i === day ? intervals : d)));
    setDirty(true);
  };
  const toggle = (day: number) => {
    if (week[day].length) {
      setRemembered((r) => r.map((d, i) => (i === day ? week[day] : d)));
      update(day, []);
    } else {
      update(day, remembered[day].length ? remembered[day] : [{ start: '10:00', end: '20:00' }]);
    }
  };
  const setTime = (day: number, index: number, field: keyof OpenInterval, value: string) =>
    update(day, week[day].map((iv, i) => (i === index ? { ...iv, [field]: value } : iv)));
  const addInterval = (day: number) => {
    const last = week[day][week[day].length - 1];
    // A second shift usually starts a little after the first ends (after lunch).
    const after = last && last.end !== '00:00' && last.end < '22:00' ? last.end : '16:00';
    const [h, m] = after.split(':').map(Number);
    const start = `${String(Math.min(h + 1, 22)).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    const end = `${String(Math.min(h + 4, 23)).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    update(day, [...week[day], { start, end }]);
  };
  const copyMonday = () => {
    setWeek((w) => w.map((d, i) => (i >= 1 && i <= 4 ? w[0].map((iv) => ({ ...iv })) : d)));
    setDirty(true);
    toast("Monday's hours copied to Tuesday – Friday. Save to publish them.");
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!shopId) return;
    setShowErrors(true);
    if (problems.some(Boolean)) return;
    setSaving(true);
    setServerError(null);
    try {
      const saved = await saveWeeklyHours(shopId, week.map(normalizeDay));
      onSaved(saved);
      setWeek(forEditor(saved.weekly));
      setDirty(false);
      setShowErrors(false);
      toast('Opening hours saved. Customers can now book only when you are open.');
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not save opening hours'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className={`${card} space-y-4`} aria-labelledby="weekly-heading">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="weekly-heading" className="font-semibold text-gray-900">Weekly hours</h2>
          <p className="text-xs text-gray-600">India time (IST). A booking must finish before you close.</p>
        </div>
        <button type="button" onClick={copyMonday} className="inline-flex items-center gap-1.5 text-sm font-medium text-indigo-700 border border-indigo-200 bg-indigo-50 rounded-lg px-3 py-2 hover:bg-indigo-100">
          <Copy size={16} aria-hidden /> Copy Monday to all weekdays
        </button>
      </div>
      {serverError && (
        <p role="alert" className="text-red-700 bg-red-50 rounded px-3 py-2 text-sm">{serverError}</p>
      )}
      <ul className="divide-y divide-gray-100">
        {DAY_NAMES.map((name, day) => {
          const open = week[day].length > 0;
          const problem = showErrors ? problems[day] : null;
          return (
            <li key={name} className="py-3 flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4">
              <div className="flex items-center gap-3 sm:w-44 sm:pt-1.5">
                <Switch checked={open} onChange={() => toggle(day)} label={`Open on ${name}`} />
                <span className="font-medium text-sm text-gray-900 w-24">{name}</span>
                {!open && <span className="text-sm text-gray-500">Closed</span>}
              </div>
              {open && (
                <div className="flex-1 space-y-2">
                  {week[day].map((iv, index) => (
                    <div key={index} className="flex flex-wrap items-center gap-2">
                      <input
                        type="time"
                        step={900}
                        aria-label={`${name} opens${index ? ` (${index + 1})` : ''}`}
                        aria-invalid={!!problem}
                        value={iv.start}
                        onChange={(e) => setTime(day, index, 'start', e.target.value)}
                        className={timeInput}
                      />
                      <span className="text-sm text-gray-500" aria-hidden>to</span>
                      <input
                        type="time"
                        step={900}
                        aria-label={`${name} closes${index ? ` (${index + 1})` : ''}`}
                        aria-invalid={!!problem}
                        value={iv.end}
                        onChange={(e) => setTime(day, index, 'end', e.target.value)}
                        className={timeInput}
                      />
                      {index > 0 && (
                        <button
                          type="button"
                          onClick={() => update(day, week[day].filter((_, i) => i !== index))}
                          aria-label={`Remove ${name} hours ${index + 1}`}
                          className="p-2 rounded-lg text-gray-500 hover:bg-gray-100"
                        >
                          <Trash2 size={16} aria-hidden />
                        </button>
                      )}
                    </div>
                  ))}
                  {week[day].length < MAX_INTERVALS && (
                    <button
                      type="button"
                      onClick={() => addInterval(day)}
                      aria-label={`Add hours (e.g. after a lunch break) on ${name}`}
                      className="inline-flex items-center gap-1 text-sm text-indigo-700 hover:underline"
                    >
                      <Plus size={14} aria-hidden /> Add hours (e.g. after a lunch break)
                    </button>
                  )}
                  {problem && (
                    <p role="alert" className="text-xs text-red-600">{name}: {problem}</p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50">
          {saving ? 'Saving…' : 'Save hours'}
        </button>
        {dirty && !saving && <span className="text-sm text-amber-700">{hours.configured ? 'Unsaved changes' : 'Not published yet'}</span>}
      </div>
    </form>
  );
}

function Holidays({ hours, onChange }: { hours: ShopHours; onChange: (h: ShopHours) => void }) {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const toast = useToast();
  const [date, setDate] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const today = todayInIndia();

  const onAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!shopId) return;
    if (!date) return setError('Choose the date you will be closed');
    if (date < today) return setError('That date has already passed');
    if (hours.holidays.some((h) => h.date === date)) return setError('That date is already in the list');
    setBusy(true);
    setError(null);
    try {
      onChange(await addHoliday(shopId, date, note));
      toast(`Closed on ${holidayLabel(date)}. Customers can't book that day.`);
      setDate('');
      setNote('');
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not add the closure'));
    } finally {
      setBusy(false);
    }
  };

  const onRemove = async (day: string) => {
    if (!shopId) return;
    try {
      await removeHoliday(shopId, day);
      onChange({ ...hours, holidays: hours.holidays.filter((h) => h.date !== day) });
      toast(`Open again on ${holidayLabel(day)}.`);
    } catch (err) {
      toast(apiErrorMessage(err, 'Could not remove the closure'), 'error');
    }
  };

  return (
    <section className={`${card} space-y-4`} aria-labelledby="holidays-heading">
      <div>
        <h2 id="holidays-heading" className="font-semibold text-gray-900 flex items-center gap-1.5">
          <CalendarOff size={18} aria-hidden /> Holidays and closures
        </h2>
        <p className="text-xs text-gray-600">Days you are closed whatever your weekly hours say, such as festivals.</p>
      </div>
      <form onSubmit={onAdd} noValidate className="flex flex-col sm:flex-row sm:items-end gap-3">
        <div>
          <label htmlFor="holiday-date" className="block text-xs text-gray-700 mb-1">Date</label>
          <input
            id="holiday-date"
            type="date"
            min={today}
            value={date}
            aria-invalid={!!error}
            aria-describedby={error ? 'holiday-error' : undefined}
            onChange={(e) => setDate(e.target.value)}
            className={`${input} w-full sm:w-44`}
          />
        </div>
        <div className="flex-1">
          <label htmlFor="holiday-note" className="block text-xs text-gray-700 mb-1">Note (optional)</label>
          <input id="holiday-note" maxLength={120} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Diwali" className={`${input} w-full`} />
        </div>
        <button type="submit" disabled={busy} className="inline-flex items-center justify-center gap-1 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          <Plus size={16} aria-hidden /> {busy ? 'Adding…' : 'Add closure'}
        </button>
      </form>
      {error && <p id="holiday-error" role="alert" className="text-xs text-red-600">{error}</p>}
      {hours.holidays.length === 0 ? (
        <p className="text-sm text-gray-500">No upcoming closures.</p>
      ) : (
        <ul className="divide-y divide-gray-100" aria-label="Upcoming closures">
          {hours.holidays.map((h) => (
            <li key={h.date} className="py-2 flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">{holidayLabel(h.date)}</p>
                {h.note && <p className="text-xs text-gray-600 truncate">{h.note}</p>}
              </div>
              <button type="button" onClick={() => onRemove(h.date)} className="text-sm text-red-700 rounded-lg px-3 py-1.5 hover:bg-red-50">
                Remove<span className="sr-only"> closure on {holidayLabel(h.date)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Capacity({ hours, onChange }: { hours: ShopHours; onChange: (h: ShopHours) => void }) {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const toast = useToast();
  const staffDefault = Math.max(1, hours.activeStaff);
  const [value, setValue] = useState(String(hours.capacity));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async (capacity: number | null) => {
    if (!shopId) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await saveCapacity(shopId, capacity);
      onChange(saved);
      setValue(String(saved.capacity));
      toast(`Up to ${saved.capacity} ${saved.capacity === 1 ? 'customer' : 'customers'} can now book the same time.`);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save'));
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const n = Number(value);
    if (!Number.isInteger(n) || n < 1 || n > 100) return setError('Enter a whole number from 1 to 100');
    save(n);
  };

  return (
    <section className={`${card} space-y-3`} aria-labelledby="capacity-heading">
      <h2 id="capacity-heading" className="font-semibold text-gray-900 flex items-center gap-1.5">
        <Users size={18} aria-hidden /> Customers at the same time
      </h2>
      <p className="text-xs text-gray-600">
        How many bookings can overlap. Once this many customers are booked for a time, it is no longer offered in the app.
        {' '}By default it is one per active staff member ({hours.activeStaff === 1 ? '1 person' : `${hours.activeStaff} people`}
        {hours.activeStaff === 0 ? ', so 1' : ''}).
      </p>
      <form onSubmit={onSubmit} noValidate className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="capacity" className="block text-xs text-gray-700 mb-1">Customers at once</label>
          <input
            id="capacity"
            type="number"
            inputMode="numeric"
            min={1}
            max={100}
            value={value}
            aria-invalid={!!error}
            aria-describedby={error ? 'capacity-error' : undefined}
            onChange={(e) => setValue(e.target.value)}
            className={`${input} w-28`}
          />
        </div>
        <button type="submit" disabled={busy} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          Save
        </button>
        {hours.capacityOverride !== null && (
          <button type="button" disabled={busy} onClick={() => save(null)} className="text-sm text-indigo-700 rounded-lg px-3 py-2 hover:bg-indigo-50">
            Use staff count ({staffDefault})
          </button>
        )}
      </form>
      {error && <p id="capacity-error" role="alert" className="text-xs text-red-600">{error}</p>}
    </section>
  );
}

export default function OpeningHoursPage() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [hours, setHours] = useState<ShopHours | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!shopId) return;
    setError(null);
    getShopHours(shopId)
      .then(setHours)
      .catch((err: unknown) => setError(apiErrorMessage(err, 'Could not load your opening hours')));
  }, [shopId]);

  useEffect(load, [load]);

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Opening hours</h1>
        <p className="text-sm text-gray-500">When customers can book you in the app.</p>
      </div>
      {error && (
        <div role="alert" className="text-red-700 bg-red-50 rounded px-3 py-2 text-sm flex items-center gap-3">
          <span className="flex-1">{error}</span>
          <button type="button" onClick={load} className="font-medium underline">Try again</button>
        </div>
      )}
      {!hours && !error && <p role="status" className="text-sm text-gray-500">Loading…</p>}
      {hours && (
        <>
          {!hours.configured && (
            <p className="bg-amber-50 border border-amber-200 text-amber-900 rounded-2xl p-4 text-sm">
              You haven't published opening hours yet, so customers can ask for any time. Check the hours below and save
              them to take bookings only when you're open.
            </p>
          )}
          <WeeklyHoursEditor hours={hours} onSaved={setHours} />
          <Holidays hours={hours} onChange={setHours} />
          <Capacity key={hours.capacity} hours={hours} onChange={setHours} />
        </>
      )}
    </div>
  );
}
