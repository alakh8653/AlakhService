import { describe, expect, it } from 'vitest';
import { RollingMetrics } from '../src/metrics.js';

describe('RollingMetrics', () => {
  it('reports zeros when idle', () => {
    expect(new RollingMetrics().snapshot()).toEqual({
      requests: 0,
      requestsPerMinute: 0,
      errorRate: 0,
      p50LatencyMs: 0,
      p95LatencyMs: 0,
    });
  });

  it('derives rate, error rate and latency percentiles', () => {
    const clock = { now: 0 };
    const m = new RollingMetrics(60_000, 10_000, () => clock.now);
    for (let i = 1; i <= 100; i++) m.record(i, i > 90); // latencies 1..100 ms, last 10 failed

    const snap = m.snapshot();
    expect(snap.requests).toBe(100);
    expect(snap.requestsPerMinute).toBe(100);
    expect(snap.errorRate).toBeCloseTo(0.1);
    expect(snap.p50LatencyMs).toBe(50);
    expect(snap.p95LatencyMs).toBe(95);
  });

  it('forgets samples older than the window', () => {
    const clock = { now: 0 };
    const m = new RollingMetrics(60_000, 10_000, () => clock.now);
    m.record(10, true);
    clock.now = 30_000;
    m.record(20, false);
    clock.now = 61_000;
    const snap = m.snapshot();
    expect(snap.requests).toBe(1);
    expect(snap.errorRate).toBe(0);
  });

  it('caps the number of stored samples', () => {
    const m = new RollingMetrics(60_000, 5);
    for (let i = 0; i < 20; i++) m.record(i, false);
    expect(m.snapshot().requests).toBe(5);
  });
});
