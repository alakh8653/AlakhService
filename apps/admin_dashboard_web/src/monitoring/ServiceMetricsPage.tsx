import { useEffect, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import { getServiceMetrics, type ServiceMetric } from './MonitoringService';

const columns: Column<ServiceMetric>[] = [
  { key: 'service', header: 'Service' },
  { key: 'requestsPerMinute', header: 'Req / min', render: (r) => r.requestsPerMinute.toLocaleString() },
  {
    key: 'errorRate',
    header: 'Error rate',
    render: (r) => <span className={r.errorRate > 0.05 ? 'text-red-600 font-semibold' : undefined}>{(r.errorRate * 100).toFixed(2)}%</span>,
  },
  { key: 'p95LatencyMs', header: 'p95 latency', render: (r) => `${r.p95LatencyMs} ms` },
  { key: 'cpuPercent', header: 'CPU', render: (r) => `${r.cpuPercent.toFixed(1)}%` },
  { key: 'memoryMb', header: 'Memory', render: (r) => `${r.memoryMb} MB` },
];

export default function ServiceMetricsPage() {
  const [metrics, setMetrics] = useState<ServiceMetric[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getServiceMetrics()
      .then(setMetrics)
      .catch(() => setError('Failed to load service metrics.'))
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Service Metrics</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable columns={columns} rows={metrics} isLoading={isLoading} />
    </div>
  );
}
