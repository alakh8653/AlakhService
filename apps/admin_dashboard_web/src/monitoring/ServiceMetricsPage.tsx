import { useEffect, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import { getServiceMetrics, type ServiceMetric } from './MonitoringService';

const CIRCUIT_STYLES: Record<ServiceMetric['circuit'], string> = {
  closed: 'bg-green-100 text-green-800',
  'half-open': 'bg-yellow-100 text-yellow-800',
  open: 'bg-red-100 text-red-800',
};

const columns: Column<ServiceMetric>[] = [
  { key: 'service', header: 'Service' },
  { key: 'requests', header: 'Requests (5 min)', render: (r) => r.requests.toLocaleString() },
  { key: 'requestsPerMinute', header: 'Req / min', render: (r) => r.requestsPerMinute.toLocaleString() },
  {
    key: 'errorRate',
    header: 'Error rate',
    render: (r) => <span className={r.errorRate > 0.05 ? 'text-red-600 font-semibold' : undefined}>{(r.errorRate * 100).toFixed(2)}%</span>,
  },
  { key: 'p50LatencyMs', header: 'p50 latency', render: (r) => `${r.p50LatencyMs} ms` },
  { key: 'p95LatencyMs', header: 'p95 latency', render: (r) => `${r.p95LatencyMs} ms` },
  {
    key: 'circuit',
    header: 'Circuit',
    render: (r) => <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${CIRCUIT_STYLES[r.circuit]}`}>{r.circuit}</span>,
  },
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
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Service Metrics</h1>
        <p className="text-sm text-gray-500">Traffic through the API gateway over the last 5 minutes.</p>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable columns={columns} rows={metrics} isLoading={isLoading} />
    </div>
  );
}
