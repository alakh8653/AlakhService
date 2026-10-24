import { describe, expect, it, vi } from 'vitest';
import { dayProblem, displayTime, normalizeDay, todayInIndia, toMinutes } from '../hours';
import apiClient from '../apiClient';
import { addHoliday, getShopHours, removeHoliday, saveCapacity, saveWeeklyHours } from '../shopService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
const api = vi.mocked(apiClient);

const iv = (start: string, end: string) => ({ start, end });

describe('opening hours rules', () => {
  it('reads times, with 24:00 as the end of the day', () => {
    expect(toMinutes('09:30')).toBe(570);
    expect(toMinutes('24:00')).toBe(1440);
    expect(toMinutes('24:15')).toBeNull();
    expect(toMinutes('9:30')).toBeNull();
    expect(toMinutes('')).toBeNull();
  });

  it('shows times the way people say them', () => {
    expect(displayTime('16:30')).toBe('4:30 PM');
    expect(displayTime('12:00')).toBe('12:00 PM');
    expect(displayTime('00:00')).toBe('midnight');
    expect(displayTime('24:00')).toBe('midnight');
  });

  it('accepts a split shift and a day closing at midnight', () => {
    expect(dayProblem([iv('16:00', '20:00'), iv('10:00', '14:00')])).toBeNull();
    expect(dayProblem([iv('18:00', '00:00')])).toBeNull();
    expect(dayProblem([])).toBeNull();
  });

  it('refuses backwards, off-grid, blank, overlapping and touching hours', () => {
    expect(dayProblem([iv('14:00', '10:00')])).toMatch(/must be before closing time/);
    expect(dayProblem([iv('10:00', '10:00')])).toMatch(/must be before closing time/);
    expect(dayProblem([iv('10:05', '14:00')])).toMatch(/quarter hour/);
    expect(dayProblem([iv('', '14:00')])).toBe('Enter both an opening and a closing time');
    expect(dayProblem([iv('10:00', '14:00'), iv('13:00', '18:00')])).toMatch(/overlap/);
    expect(dayProblem([iv('10:00', '14:00'), iv('14:00', '18:00')])).toMatch(/merge them/);
  });

  it('sends the hours sorted, with a midnight close as 24:00', () => {
    expect(normalizeDay([iv('18:00', '00:00'), iv('09:00', '13:00')])).toEqual([iv('09:00', '13:00'), iv('18:00', '24:00')]);
  });

  it("knows today's date in India when it is still yesterday in UTC", () => {
    expect(todayInIndia(new Date('2026-10-18T19:00:00Z'))).toBe('2026-10-19');
    expect(todayInIndia(new Date('2026-10-18T18:00:00Z'))).toBe('2026-10-18');
  });
});

describe('opening hours API', () => {
  const response = {
    configured: true,
    timezone: 'Asia/Kolkata',
    weekly: [{ day: 0, intervals: [iv('10:00', '14:00')] }, { day: 6, intervals: [] }],
    holidays: [{ date: '2026-11-08', note: 'Diwali' }],
    capacity: 3,
    capacity_override: 3,
    active_staff: 2,
    updated_at: null,
  };

  it('maps the week Monday first, filling days the server left out as closed', async () => {
    api.get.mockResolvedValue({ data: response });
    const hours = await getShopHours('s1');
    expect(api.get).toHaveBeenCalledWith('/shops/s1/hours');
    expect(hours.weekly).toHaveLength(7);
    expect(hours.weekly[0]).toEqual([iv('10:00', '14:00')]);
    expect(hours.weekly[3]).toEqual([]);
    expect(hours).toMatchObject({ capacity: 3, capacityOverride: 3, activeStaff: 2, holidays: [{ date: '2026-11-08', note: 'Diwali' }] });
  });

  it('saves the week, capacity and closures to their own endpoints', async () => {
    api.put.mockResolvedValue({ data: response });
    api.post.mockResolvedValue({ data: response });
    api.delete.mockResolvedValue({ data: null });
    const week = [[iv('10:00', '14:00')], [], [], [], [], [], []];
    await saveWeeklyHours('s1', week);
    expect(api.put).toHaveBeenCalledWith('/shops/s1/hours', {
      weekly: week.map((intervals, day) => ({ day, intervals })),
    });
    await saveCapacity('s1', null);
    expect(api.put).toHaveBeenLastCalledWith('/shops/s1/capacity', { capacity: null });
    await addHoliday('s1', '2026-11-08', '  ');
    expect(api.post).toHaveBeenCalledWith('/shops/s1/holidays', { date: '2026-11-08', note: null });
    await removeHoliday('s1', '2026-11-08');
    expect(api.delete).toHaveBeenCalledWith('/shops/s1/holidays/2026-11-08');
  });
});
