import { useCallback, useEffect, useRef, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react';
import { formatTime } from '../shared/format';
import { getSystemHealth, type HealthStatus, type ServiceHealth } from './MonitoringService';

const STATUS_STYLES: Record<HealthStatus, string> = {
  healthy: 'bg-green-100 text-green-800',
  degraded: 'bg-yellow-100 text-yellow-800',
  down: 'bg-red-100 text-red-800',
};

const SEVERITY: Record<HealthStatus, number> = { down: 0, degraded: 1, healthy: 2 };

const REFRESH_INTERVAL_MS = 30_000;

export default function SystemHealthPage() {
  const [services, setServices] = useState<ServiceHealth[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const inFlight = useRef(false);

  const load = useCallback(() => {
    if (inFlight.current) return;
    inFlight.current = true;
    setIsLoading(true);
    getSystemHealth()
      .then((data) => {
        setServices(data);
        setUpdatedAt(new Date());
        setError(null);
      })
      .catch(() => setError('Could not check system health.'))
      .finally(() => {
        inFlight.current = false;
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  // Problems first, then by name.
  const sorted = [...services].sort((a, b) => SEVERITY[a.status] - SEVERITY[b.status] || a.name.localeCompare(b.name));
  const unhealthy = services.filter((s) => s.status !== 'healthy');

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">System Health</h1>
          <p className="text-sm text-gray-600">
            Checks every backend service; refreshes every 30 seconds{updatedAt ? ` · last checked ${formatTime(updatedAt)}` : ''}.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={isLoading}
          className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          <RefreshCw size={16} aria-hidden="true" className={isLoading ? 'animate-spin' : undefined} /> {isLoading ? 'Checking…' : 'Refresh'}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error} {services.length > 0 && 'Showing the last results.'}
        </p>
      )}
      {services.length > 0 && (
        <div
          role="status"
          className={`flex items-center gap-3 rounded-xl p-4 text-sm font-medium ${unhealthy.length ? 'bg-red-50 text-red-800' : 'bg-green-50 text-green-800'}`}
        >
          {unhealthy.length ? <AlertTriangle size={20} aria-hidden="true" /> : <CheckCircle2 size={20} aria-hidden="true" />}
          {unhealthy.length
            ? `${unhealthy.length} of ${services.length} services need attention: ${unhealthy.map((s) => s.name).join(', ')}`
            : `All ${services.length} services are healthy.`}
        </div>
      )}
      {isLoading && services.length === 0 && !error && <p className="text-sm text-gray-500">Checking services…</p>}
      <ul className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {sorted.map((svc) => (
          <li key={svc.id} className={`bg-white rounded-xl shadow p-5 ${svc.status !== 'healthy' ? 'ring-2 ring-red-200' : ''}`}>
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold text-gray-900 break-all">{svc.name}</h2>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[svc.status]}`}>{svc.status}</span>
            </div>
            <dl className="mt-3 text-sm text-gray-600 space-y-1">
              {svc.version && (
                <div className="flex gap-1">
                  <dt>Version:</dt>
                  <dd>{svc.version}</dd>
                </div>
              )}
              {svc.latencyMs !== undefined && (
                <div className="flex gap-1">
                  <dt>Latency:</dt>
                  <dd>{svc.latencyMs} ms</dd>
                </div>
              )}
              <div className="flex gap-1">
                <dt>Checked:</dt>
                <dd>{formatDistanceToNow(new Date(svc.checkedAt), { addSuffix: true })}</dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
