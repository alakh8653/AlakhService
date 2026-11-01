import { useState, type FormEvent } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import type { OpenInterval, StaffMember } from '../types';
import { apiErrorMessage } from '../services/format';
import { DAY_NAMES, MAX_INTERVALS, dayProblem, normalizeDay } from '../services/hours';
import Dialog from './Dialog';
import Switch from './Switch';

const timeInput =
  'w-28 border border-gray-300 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

/** Where an owner starts a team member's own week from: the shop's week, else Monday to Saturday 10–8. */
function startingWeek(member: StaffMember, shopWeek: OpenInterval[][] | null): OpenInterval[][] {
  const week = member.workingHours ?? shopWeek ?? DAY_NAMES.map((_, d) => (d < 6 ? [{ start: '10:00', end: '20:00' }] : []));
  // A time box can't show 24:00, so a day ending at midnight ends at 00:00 in the editor.
  return week.map((day) => day.map((i) => ({ ...i, end: i.end === '24:00' ? '00:00' : i.end })));
}

/**
 * When one team member works: the shop's opening hours, or their own week (split shifts, days off).
 * The live line plans their customers only within these hours, and customers who ask for them can book
 * only then.
 */
export default function WorkingHoursDialog({ member, shopWeek, onSave, onClose }: {
  member: StaffMember;
  /** The shop's week, to start their own from; null when the shop has not set hours. */
  shopWeek: OpenInterval[][] | null;
  onSave: (week: OpenInterval[][] | null) => Promise<void>;
  onClose: () => void;
}) {
  const [own, setOwn] = useState(member.workingHours !== null);
  const [week, setWeek] = useState<OpenInterval[][]>(() => startingWeek(member, shopWeek));
  const [showErrors, setShowErrors] = useState(false);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const problems = week.map(dayProblem);

  const update = (day: number, intervals: OpenInterval[]) => setWeek((w) => w.map((d, i) => (i === day ? intervals : d)));
  const setTime = (day: number, index: number, field: keyof OpenInterval, value: string) =>
    update(day, week[day].map((iv, i) => (i === index ? { ...iv, [field]: value } : iv)));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setShowErrors(true);
    if (own && problems.some(Boolean)) return;
    setSaving(true);
    setServerError(null);
    try {
      await onSave(own ? week.map(normalizeDay) : null);
      onClose();
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not save the working hours'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      title={`${member.name}'s working hours`}
      description="India time (IST). The live line gives them customers only while they work, and customers who ask for them can book only then."
      onClose={onClose}
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        <fieldset className="space-y-2">
          <legend className="sr-only">When they work</legend>
          <label className="flex items-center gap-2 text-sm text-gray-800">
            <input type="radio" name="hours-kind" checked={!own} onChange={() => setOwn(false)} />
            Whenever the shop is open
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-800">
            <input type="radio" name="hours-kind" checked={own} onChange={() => setOwn(true)} />
            Their own hours
          </label>
        </fieldset>
        {own && (
          <ul className="divide-y divide-gray-100">
            {DAY_NAMES.map((name, day) => {
              const working = week[day].length > 0;
              const problem = showErrors ? problems[day] : null;
              return (
                <li key={name} className="py-2 flex flex-col sm:flex-row sm:items-start gap-2">
                  <div className="flex items-center gap-3 sm:w-40 sm:pt-1.5">
                    <Switch
                      checked={working}
                      onChange={() => update(day, working ? [] : [{ start: '10:00', end: '18:00' }])}
                      label={`Works on ${name}`}
                    />
                    <span className="font-medium text-sm text-gray-900 w-24">{name}</span>
                    {!working && <span className="text-sm text-gray-500">Off</span>}
                  </div>
                  {working && (
                    <div className="flex-1 space-y-2">
                      {week[day].map((iv, index) => (
                        <div key={index} className="flex flex-wrap items-center gap-2">
                          <input
                            type="time"
                            step={900}
                            aria-label={`${name} starts${index ? ` (${index + 1})` : ''}`}
                            aria-invalid={!!problem}
                            value={iv.start}
                            onChange={(e) => setTime(day, index, 'start', e.target.value)}
                            className={timeInput}
                          />
                          <span className="text-sm text-gray-500" aria-hidden>to</span>
                          <input
                            type="time"
                            step={900}
                            aria-label={`${name} finishes${index ? ` (${index + 1})` : ''}`}
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
                          onClick={() => update(day, [...week[day], { start: '16:00', end: '20:00' }])}
                          aria-label={`Add hours on ${name}`}
                          className="inline-flex items-center gap-1 text-sm text-indigo-700 hover:underline"
                        >
                          <Plus size={14} aria-hidden /> Add hours (a split shift)
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
        )}
        {serverError && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 rounded px-3 py-2">{serverError}</p>
        )}
        <div className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {saving ? 'Saving…' : 'Save hours'}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
