import adminApiClient from '../apiClient';

export type HealthStatus = 'healthy' | 'degraded' | 'down';

export interface ServiceHealth {
  id: string;
  name: string;
  status: HealthStatus;
  version?: string;
  latencyMs?: number;
  checkedAt: string;
}

/** Traffic a service received through the API gateway over the last 5 minutes. */
export interface ServiceMetric {
  id: string;
  service: string;
  requests: number;
  requestsPerMinute: number;
  /** 0..1 share of failed requests (errors, timeouts, 5xx). */
  errorRate: number;
  p50LatencyMs: number;
  p95LatencyMs: number;
  circuit: 'closed' | 'open' | 'half-open';
}

export async function getSystemHealth(): Promise<ServiceHealth[]> {
  const { data } = await adminApiClient.get<{ data: ServiceHealth[] }>('/admin/monitoring/health');
  return data.data;
}

export async function getServiceMetrics(): Promise<ServiceMetric[]> {
  const { data } = await adminApiClient.get<{ data: ServiceMetric[] }>('/admin/monitoring/metrics');
  return data.data;
}
