import { describe, expect, it } from 'vitest';
import { formatDuration, formatScore } from './format';
import { parseHash } from './useHashRoute';

describe('formatScore', () => {
  it('shows one decimal, or N/A for a null score', () => {
    expect(formatScore(62.2)).toBe('62.2');
    expect(formatScore(100)).toBe('100.0');
    expect(formatScore(0)).toBe('0.0');
    expect(formatScore(null)).toBe('N/A');
  });
});

describe('formatDuration', () => {
  it('formats seconds and minutes', () => {
    const start = '2026-11-19T10:00:00.000Z';
    expect(formatDuration(start, '2026-11-19T10:00:03.020Z')).toBe('3.0 s');
    expect(formatDuration(start, '2026-11-19T10:02:05.000Z')).toBe('2 min 05 s');
  });

  it('shows a dash while the scan is unfinished', () => {
    expect(formatDuration('2026-11-19T10:00:00Z', null)).toBe('-');
  });
});

describe('parseHash', () => {
  it('routes #/scans/<id> to a scan and everything else to the list', () => {
    expect(parseHash('#/scans/12')).toEqual({ page: 'scan', scanId: 12 });
    expect(parseHash('#/')).toEqual({ page: 'scans' });
    expect(parseHash('#/scans/abc')).toEqual({ page: 'scans' });
    expect(parseHash('')).toEqual({ page: 'scans' });
  });
});
