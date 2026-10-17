import { timingSafeEqual } from 'node:crypto';
import type { Request, Response } from 'express';
import { collectDefaultMetrics, Counter, Gauge, Histogram, Registry } from 'prom-client';
import type { CircuitBreaker } from './circuitBreaker.js';

/**
 * Prometheus metrics for the gateway, scraped from GET /metrics.
 *
 * Every API request passes through here, so these show each service's traffic, errors and
 * latency, which circuits are open, and how often clients hit rate limits, in one place.
 * Labels are kept to a fixed set (service, method, status) so the number of series stays small.
 */
export class GatewayMetrics {
  readonly registry = new Registry();
  private readonly requests: Counter<'upstream' | 'method' | 'status'>;
  private readonly duration: Histogram<'upstream'>;
  readonly redisErrors: Counter;

  constructor(breakers: Map<string, CircuitBreaker>, names: Record<string, string>, collectProcess = false) {
    this.requests = new Counter({
      name: 'gateway_http_requests_total',
      help: 'Requests answered by the gateway, by service, method and status code',
      labelNames: ['upstream', 'method', 'status'],
      registers: [this.registry],
    });
    this.duration = new Histogram({
      name: 'gateway_http_request_duration_seconds',
      help: 'Time to answer a request, by service',
      labelNames: ['upstream'],
      buckets: [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 15],
      registers: [this.registry],
    });
    this.redisErrors = new Counter({
      name: 'gateway_redis_errors_total',
      help: 'Rate-limit or sign-out checks that could not reach Redis (requests were let through)',
      registers: [this.registry],
    });
    new Gauge({
      name: 'gateway_circuit_open',
      help: '1 while the gateway is refusing requests to a service after repeated failures',
      labelNames: ['upstream'],
      registers: [this.registry],
      collect() {
        for (const [key, breaker] of breakers) this.set({ upstream: names[key] ?? key }, breaker.currentState === 'open' ? 1 : 0);
      },
    });
    if (collectProcess) collectDefaultMetrics({ register: this.registry, prefix: 'gateway_' });
  }

  observe(upstream: string | undefined, method: string, status: number, durationMs: number): void {
    const service = upstream ?? 'gateway';
    this.requests.inc({ upstream: service, method, status: String(status) });
    this.duration.observe({ upstream: service }, durationMs / 1000);
  }

  /** GET /metrics: open in development; behind METRICS_TOKEN when one is set (required in production). */
  handler(token: string | undefined, production: boolean) {
    return async (req: Request, res: Response) => {
      if (production && !token) {
        res.status(404).json({ detail: 'Not found' });
        return;
      }
      if (token && !sameSecret(req.headers.authorization ?? '', `Bearer ${token}`)) {
        res.status(401).setHeader('WWW-Authenticate', 'Bearer').json({ detail: 'Metrics token required' });
        return;
      }
      res.setHeader('content-type', this.registry.contentType);
      res.end(await this.registry.metrics());
    };
  }
}

function sameSecret(given: string, expected: string): boolean {
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
