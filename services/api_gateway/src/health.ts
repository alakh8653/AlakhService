import type { Upstream } from './config.js';

export type HealthStatus = 'healthy' | 'degraded' | 'down';

/** Shape consumed by the admin dashboard's System Health page. */
export interface ServiceHealth {
  id: string;
  name: string;
  status: HealthStatus;
  latencyMs?: number;
  checkedAt: string;
}

export async function checkUpstream(upstream: Upstream, timeoutMs: number): Promise<ServiceHealth> {
  const started = performance.now();
  const result = (status: HealthStatus, measured = true): ServiceHealth => ({
    id: upstream.key,
    name: upstream.name,
    status,
    latencyMs: measured ? Math.round(performance.now() - started) : undefined,
    checkedAt: new Date().toISOString(),
  });

  try {
    const response = await fetch(`${upstream.url}/health`, { signal: AbortSignal.timeout(timeoutMs) });
    if (!response.ok) return result('degraded');
    const body = (await response.json().catch(() => ({}))) as { status?: unknown };
    return result(body.status === 'healthy' ? 'healthy' : 'degraded');
  } catch {
    return result('down', false);
  }
}

export function checkAll(upstreams: Upstream[], timeoutMs: number): Promise<ServiceHealth[]> {
  return Promise.all(upstreams.map((upstream) => checkUpstream(upstream, timeoutMs)));
}
