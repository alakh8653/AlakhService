import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import {
  AUDIT_SERVICES,
  getAuditLogs,
  serviceLabel,
  summarizeUserAgent,
  type AuditLog,
  type AuditLogFilters,
} from './AuditService';
import DataTable, { type Column } from '../components/DataTable';

const columns: Column<AuditLog>[] = [
  { key: 'createdAt', header: 'Timestamp', render: (r) => format(new Date(r.createdAt), 'MMM d, yyyy HH:mm:ss') },
  { key: 'actorId', header: 'Admin' },
  { key: 'service', header: 'Service', render: (r) => serviceLabel(r.service) },
  { key: 'action', header: 'Action' },
  { key: 'resource', header: 'Resource' },
  { key: 'resourceId', header: 'Resource ID' },
  { key: 'ipAddress', header: 'IP Address' },
  {
    key: 'userAgent',
    header: 'Client',
    render: (r) => <span title={r.userAgent ?? undefined}>{summarizeUserAgent(r.userAgent)}</span>,
  },
];

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<AuditLogFilters>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    getAuditLogs({ ...filters, page, perPage: 25 })
      .then((res) => { setLogs(res.data); setTotal(res.total); })
      .catch(() => { setLogs([]); setTotal(0); setError('Failed to load audit logs.'); })
      .finally(() => setIsLoading(false));
  }, [filters, page]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
      <div className="flex gap-3 flex-wrap bg-white rounded-xl shadow p-4">
        <input placeholder="Admin ID" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, actorId: e.target.value || undefined })); }} />
        <input placeholder="Action" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, action: e.target.value || undefined })); }} />
        <select aria-label="Service" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" defaultValue="" onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, service: e.target.value || undefined })); }}>
          <option value="">All services</option>
          {Object.entries(AUDIT_SERVICES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable columns={columns} rows={logs} isLoading={isLoading} total={total} page={page} perPage={25} onPageChange={setPage} />
    </div>
  );
}
