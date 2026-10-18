import { describe, expect, it } from 'vitest';
import { formatElapsed, formatMoneyShort, formatWhen, isE164, normalizePhone } from '../format';

describe('formatWhen', () => {
  const now = new Date(2026, 9, 18, 9, 0); // Sun 18 Oct 2026, 9:00 local

  it('says today, tomorrow and yesterday in 12-hour time', () => {
    expect(formatWhen(new Date(2026, 9, 18, 10, 30).toISOString(), now)).toBe('Today, 10:30 AM');
    expect(formatWhen(new Date(2026, 9, 19, 16, 5).toISOString(), now)).toBe('Tomorrow, 4:05 PM');
    expect(formatWhen(new Date(2026, 9, 17, 9, 0).toISOString(), now)).toBe('Yesterday, 9:00 AM');
  });

  it('writes other days day-first, adding the year only when it differs', () => {
    expect(formatWhen(new Date(2026, 11, 1, 10, 30).toISOString(), now)).toBe('Tue 1 Dec, 10:30 AM');
    expect(formatWhen(new Date(2027, 0, 5, 10, 0).toISOString(), now)).toBe('Tue 5 Jan 2027, 10:00 AM');
  });
});

describe('formatElapsed', () => {
  const now = Date.UTC(2026, 9, 18, 12, 0);
  it('uses hours and days instead of thousands of minutes', () => {
    expect(formatElapsed(new Date(now - 4 * 60_000).toISOString(), now)).toBe('4 min');
    expect(formatElapsed(new Date(now - 130 * 60_000).toISOString(), now)).toBe('2 h 10 min');
    expect(formatElapsed(new Date(now - 1575 * 60_000).toISOString(), now)).toBe('1 day 2 h');
  });
});

describe('normalizePhone', () => {
  it('accepts Indian mobile numbers the way people type them', () => {
    expect(normalizePhone('98765 43210')).toBe('+919876543210');
    expect(normalizePhone('098765-43210')).toBe('+919876543210');
    expect(normalizePhone('91 98765 43210')).toBe('+919876543210');
    expect(normalizePhone('+44 20 7946 0958')).toBe('+442079460958');
    expect(isE164(normalizePhone('12345'))).toBe(false);
  });
});

describe('formatMoneyShort', () => {
  it('uses Indian units for chart axes', () => {
    expect(formatMoneyShort(95000)).toBe('₹950');
    expect(formatMoneyShort(450000)).toBe('₹4.5K');
    expect(formatMoneyShort(12000000)).toBe('₹1.2L');
    expect(formatMoneyShort(3400000000)).toBe('₹3.4Cr');
  });
});
