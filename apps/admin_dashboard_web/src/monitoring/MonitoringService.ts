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

export interface ServiceMetric {
  id: string;
  service: string;
  requestsPerMinute: number;
  errorRate: number;
  p95LatencyMs: number;
  cpuPercent: number;
  memoryMb: number;
}

export async function getSystemHealth(): Promise<ServiceHealth[]> {
  const { data } = await adminApiClient.get<{ data: ServiceHealth[] }>('/admin/monitoring/health');
  return data.data;
}

export async function getServiceMetrics(): Promise<ServiceMetric[]> {
  const { data } = await adminApiClient.get<{ data: ServiceMetric[] }>('/admin/monitoring/metrics');
  return data.data;
}
