import { describe, expect, it } from 'vitest';
import { csvCell, toCsv } from '../csv';

describe('CSV export', () => {
  it('quotes commas, quotes and line breaks', () => {
    expect(csvCell('Dell XPS 13, cracked screen')).toBe('"Dell XPS 13, cracked screen"');
    expect(csvCell('6" screen')).toBe('"6"" screen"');
    expect(csvCell('two\nlines')).toBe('"two\nlines"');
    expect(csvCell(null)).toBe('');
    expect(csvCell(499.5)).toBe('499.5');
  });

  it('keeps text that a spreadsheet would run as a formula as plain text', () => {
    for (const evil of ['=HYPERLINK("http://x")', '+91 98765', '-2+3', '@SUM(A1)']) {
      expect(csvCell(evil).replace(/^"/, '')).toMatch(/^'/);
    }
  });

  it('writes a header row and one line per row', () => {
    expect(toCsv(['Date', 'Net'], [['2026-10-12', '499.00']])).toBe('Date,Net\r\n2026-10-12,499.00\r\n');
  });
});

