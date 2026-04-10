import React, { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { getAuditLogs, type AuditLog, type AuditLogFilters } from './AuditService';
import DataTable, { type Column } from '../components/DataTable';

const columns: Column<AuditLog>[] = [
  { key: 'createdAt', header: 'Timestamp', render: (r) => format(new Date(r.createdAt), 'MMM d, yyyy HH:mm:ss') },
  { key: 'actorName', header: 'Actor' },
  { key: 'action', header: 'Action' },
  { key: 'resource', header: 'Resource' },
  { key: 'resourceId', header: 'Resource ID' },
  { key: 'ipAddress', header: 'IP Address' },
];

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [filters, setFilters] = useState<AuditLogFilters>({});

  useEffect(() => {
    setIsLoading(true);
    getAuditLogs({ ...filters, page, perPage: 25 })
      .then((res) => { setLogs(res.data); setTotal(res.total); })
      .finally(() => setIsLoading(false));
  }, [filters, page]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
      <div className="flex gap-3 flex-wrap bg-white rounded-xl shadow p-4">
        <input placeholder="Actor ID" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" onChange={(e) => setFilters((f) => ({ ...f, actorId: e.target.value || undefined }))} />
        <input placeholder="Action" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value || undefined }))} />
        <input placeholder="Resource" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" onChange={(e) => setFilters((f) => ({ ...f, resource: e.target.value || undefined }))} />
        <input type="date" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" onChange={(e) => setFilters((f) => ({ ...f, dateFrom: e.target.value || undefined }))} />
        <input type="date" className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" onChange={(e) => setFilters((f) => ({ ...f, dateTo: e.target.value || undefined }))} />
      </div>
      <DataTable columns={columns} rows={logs} isLoading={isLoading} total={total} page={page} perPage={25} onPageChange={setPage} />
    </div>
  );
}
