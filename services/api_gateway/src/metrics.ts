/**
 * Rolling per-service traffic metrics, measured on the requests the gateway proxies.
 *
 * Keeps the samples of the last `windowMs` (bounded by `maxSamples`) and derives request
 * rate, error rate and latency percentiles from them on demand.
 */

interface Sample {
  at: number;
  latencyMs: number;
  failed: boolean;
}

export interface MetricsSnapshot {
  requests: number;
  requestsPerMinute: number;
  /** Share of requests that failed (network error, timeout or 5xx), 0..1. */
  errorRate: number;
  p50LatencyMs: number;
  p95LatencyMs: number;
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const index = Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1);
  return sorted[Math.max(0, index)];
}

export class RollingMetrics {
  private samples: Sample[] = [];

  constructor(
    private readonly windowMs = 5 * 60_000,
    private readonly maxSamples = 10_000,
    private readonly now: () => number = Date.now,
  ) {}

  record(latencyMs: number, failed: boolean): void {
    this.samples.push({ at: this.now(), latencyMs, failed });
    if (this.samples.length > this.maxSamples) this.samples.splice(0, this.samples.length - this.maxSamples);
  }

  snapshot(): MetricsSnapshot {
    const cutoff = this.now() - this.windowMs;
    this.samples = this.samples.filter((s) => s.at >= cutoff);
    const requests = this.samples.length;
    const latencies = this.samples.map((s) => s.latencyMs).sort((a, b) => a - b);
    const failures = this.samples.filter((s) => s.failed).length;
    return {
      requests,
      requestsPerMinute: Math.round((requests / (this.windowMs / 60_000)) * 100) / 100,
      errorRate: requests ? failures / requests : 0,
      p50LatencyMs: Math.round(percentile(latencies, 50)),
      p95LatencyMs: Math.round(percentile(latencies, 95)),
    };
  }
}
