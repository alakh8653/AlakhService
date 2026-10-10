import { useCallback, useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { RefreshCw } from 'lucide-react';
import { getSystemHealth, type HealthStatus, type ServiceHealth } from './MonitoringService';

const STATUS_STYLES: Record<HealthStatus, string> = {
  healthy: 'bg-green-100 text-green-800',
  degraded: 'bg-yellow-100 text-yellow-800',
  down: 'bg-red-100 text-red-800',
};

const REFRESH_INTERVAL_MS = 30_000;

export default function SystemHealthPage() {
  const [services, setServices] = useState<ServiceHealth[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setIsLoading(true);
    getSystemHealth()
      .then((data) => {
        setServices(data);
        setError(null);
      })
      .catch(() => setError('Failed to load system health.'))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">System Health</h1>
        <button type="button" onClick={load} disabled={isLoading} className="flex items-center gap-2 text-sm text-indigo-600 disabled:opacity-50">
          <RefreshCw size={16} className={isLoading ? 'animate-spin' : undefined} /> Refresh
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map((svc) => (
          <div key={svc.id} className="bg-white rounded-xl shadow p-5">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-gray-900">{svc.name}</p>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[svc.status]}`}>{svc.status}</span>
            </div>
            <dl className="mt-3 text-sm text-gray-600 space-y-1">
              {svc.version && <div>Version: {svc.version}</div>}
              {svc.latencyMs !== undefined && <div>Latency: {svc.latencyMs} ms</div>}
              <div>Checked {formatDistanceToNow(new Date(svc.checkedAt), { addSuffix: true })}</div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
