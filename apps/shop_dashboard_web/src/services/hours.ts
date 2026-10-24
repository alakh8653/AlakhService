import type { OpenInterval } from '../types';

export const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
/** The server takes up to four intervals a day; two (a lunch break) covers almost every shop. */
export const MAX_INTERVALS = 4;

/** What a shop that has never set its hours starts from: Monday to Saturday, 10 AM to 8 PM. */
export function suggestedWeek(): OpenInterval[][] {
  return DAY_NAMES.map((_, day) => (day < 6 ? [{ start: '10:00', end: '20:00' }] : []));
}

/** Minutes after midnight of "HH:MM", or null for anything else. "24:00" is the end of the day. */
export function toMinutes(value: string): number | null {
  const match = /^(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const minutes = Number(match[1]) * 60 + Number(match[2]);
  return Number(match[2]) < 60 && minutes <= 24 * 60 ? minutes : null;
}

/** "16:30" as "4:30 PM"; "24:00" as "midnight". */
export function displayTime(value: string): string {
  const minutes = toMinutes(value);
  if (minutes === null) return value;
  if (minutes === 24 * 60 || minutes === 0) return 'midnight';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
}

/** Why a day's intervals can't be saved, in words for the owner; null when they're fine. */
export function dayProblem(intervals: OpenInterval[]): string | null {
  const parsed: [number, number][] = [];
  for (const { start, end } of intervals) {
    // A time box cleared to blank, or "00:00" as a closing time (midnight is 24:00 here).
    const s = toMinutes(start);
    const e = end === '00:00' ? 24 * 60 : toMinutes(end);
    if (s === null || e === null) return 'Enter both an opening and a closing time';
    if (s % 15 || e % 15) return 'Use times on the quarter hour (:00, :15, :30 or :45)';
    if (s >= e) return `Opening time ${displayTime(start)} must be before closing time ${displayTime(end)}`;
    parsed.push([s, e]);
  }
  parsed.sort((a, b) => a[0] - b[0]);
  for (let i = 1; i < parsed.length; i++) {
    if (parsed[i][0] <= parsed[i - 1][1]) return 'These hours overlap or touch; merge them into one';
  }
  return null;
}

/** The intervals as the server stores them: sorted, and a closing time of 00:00 as 24:00. */
export function normalizeDay(intervals: OpenInterval[]): OpenInterval[] {
  return intervals
    .map(({ start, end }) => ({ start, end: end === '00:00' ? '24:00' : end }))
    .sort((a, b) => (toMinutes(a.start) ?? 0) - (toMinutes(b.start) ?? 0));
}

/** Today's date in India (YYYY-MM-DD), the earliest a closure can be added. */
export function todayInIndia(now: Date = new Date()): string {
  return new Date(now.getTime() + 330 * 60_000).toISOString().slice(0, 10);
}
