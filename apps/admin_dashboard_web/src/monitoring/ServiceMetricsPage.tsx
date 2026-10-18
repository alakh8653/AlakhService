import { useCallback, useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import { formatNumber, formatTime } from '../shared/format';
import { getServiceMetrics, type ServiceMetric } from './MonitoringService';

const CIRCUIT_STYLES: Record<ServiceMetric['circuit'], string> = {
  closed: 'bg-green-100 text-green-800',
  'half-open': 'bg-yellow-100 text-yellow-800',
  open: 'bg-red-100 text-red-800',
};

const CIRCUIT_LABELS: Record<ServiceMetric['circuit'], string> = {
  closed: 'Closed (normal)',
  'half-open': 'Half-open (recovering)',
  open: 'Open (requests blocked)',
};

const ERROR_ALERT = 0.05;
const REFRESH_MS = 30_000;

const columns: Column<ServiceMetric>[] = [
  { key: 'service', header: 'Service', render: (r) => <span className="font-medium text-gray-900">{r.service}</span> },
  { key: 'requests', header: 'Requests (5 min)', render: (r) => formatNumber(r.requests), className: 'hidden sm:table-cell text-right tabular-nums' },
  { key: 'requestsPerMinute', header: 'Req / min', render: (r) => formatNumber(r.requestsPerMinute, 1), className: 'text-right tabular-nums' },
  {
    key: 'errorRate',
    header: 'Error rate',
    className: 'text-right tabular-nums',
    render: (r) => (
      <span className={r.errorRate > ERROR_ALERT ? 'text-red-700 font-semibold' : undefined}>
        {(r.errorRate * 100).toFixed(2)}%{r.errorRate > ERROR_ALERT && <span className="sr-only"> (above 5%)</span>}
      </span>
    ),
  },
  { key: 'p50LatencyMs', header: 'p50', render: (r) => `${formatNumber(r.p50LatencyMs, 0)} ms`, className: 'hidden md:table-cell text-right tabular-nums' },
  { key: 'p95LatencyMs', header: 'p95', render: (r) => `${formatNumber(r.p95LatencyMs, 0)} ms`, className: 'text-right tabular-nums' },
  {
    key: 'circuit',
    header: 'Circuit',
    render: (r) => (
      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${CIRCUIT_STYLES[r.circuit]}`} title={CIRCUIT_LABELS[r.circuit]}>
        {r.circuit}
      </span>
    ),
  },
];

export default function ServiceMetricsPage() {
  const [metrics, setMetrics] = useState<ServiceMetric[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const inFlight = useRef(false);

  const load = useCallback(() => {
    if (inFlight.current) return;
    inFlight.current = true;
    setIsLoading(true);
    getServiceMetrics()
      .then((m) => {
        setMetrics(m);
        setUpdatedAt(new Date());
        setError(null);
      })
      .catch(() => setError('Could not load service metrics.'))
      .finally(() => {
        inFlight.current = false;
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  // Services in trouble first: open circuits, then high error rates, then busiest.
  const rank = (m: ServiceMetric) => (m.circuit === 'open' ? 0 : m.circuit === 'half-open' ? 1 : m.errorRate > ERROR_ALERT ? 2 : 3);
  const rows = [...metrics].sort((a, b) => rank(a) - rank(b) || b.requests - a.requests);
  const troubled = metrics.filter((m) => rank(m) < 3).length;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Service Metrics</h1>
          <p className="text-sm text-gray-600">
            Traffic through the API gateway over the last 5 minutes; refreshes every 30 seconds
            {updatedAt ? ` · updated ${formatTime(updatedAt)}` : ''}.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={isLoading}
          className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          <RefreshCw size={16} aria-hidden="true" className={isLoading ? 'animate-spin' : undefined} /> {isLoading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      {metrics.length > 0 && (
        <p role="status" className={`text-sm font-medium ${troubled ? 'text-red-700' : 'text-green-800'}`}>
          {troubled
            ? `${troubled} ${troubled === 1 ? 'service has' : 'services have'} errors above 5% or a tripped circuit - listed first.`
            : 'No service has errors above 5% and every circuit is closed.'}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <DataTable label="Service metrics" columns={columns} rows={rows} isLoading={isLoading} emptyMessage="No traffic recorded yet." />
    </div>
  );
}
