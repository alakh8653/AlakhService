import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import {
  actionLabel,
  AUDIT_ACTIONS,
  AUDIT_SERVICES,
  getAuditLogs,
  prettyValues,
  serviceLabel,
  summarizeUserAgent,
  type AuditLog,
} from './AuditService';
import DataTable, { type Column } from '../components/DataTable';
import Modal from '../components/Modal';
import { formatDateTime, shortId } from '../shared/format';
import { useDebouncedValue } from '../shared/useDebouncedValue';
import { useAccounts } from '../users/accountNames';
import type { Account } from '../users/UserService';

const PER_PAGE = 25;

function Values({ label, raw }: { label: string; raw: string | null }) {
  const text = prettyValues(raw);
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-700">{label}</h3>
      {text ? (
        <pre className="mt-1 max-h-60 overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-800 whitespace-pre-wrap break-all">{text}</pre>
      ) : (
        <p className="mt-1 text-sm text-gray-500">None</p>
      )}
    </div>
  );
}

function AuditDetails({ log, admin, onClose }: { log: AuditLog; admin?: Account; onClose: () => void }) {
  const fields: [string, string][] = [
    ['When', formatDateTime(log.createdAt, { seconds: true })],
    ['Admin', admin ? `${admin.name} (${admin.email ?? admin.phone ?? log.actorId})` : log.actorId],
    ['Service', serviceLabel(log.service)],
    ['Action', `${actionLabel(log.action)} (${log.action})`],
    ['Resource', `${log.resource}${log.resourceId ? ` · ${log.resourceId}` : ''}`],
    ['IP address', log.ipAddress ?? '—'],
    ['Client', log.userAgent ?? '—'],
  ];
  return (
    <Modal title="Audit entry" onClose={onClose} size="lg">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        {fields.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-gray-600">{k}</dt>
            <dd className="text-gray-900 break-all">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="grid sm:grid-cols-2 gap-4">
        <Values label="Before" raw={log.oldValues} />
        <Values label="After" raw={log.newValues} />
      </div>
      <div className="flex justify-end">
        <button type="button" onClick={onClose} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
          Close
        </button>
      </div>
    </Modal>
  );
}

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [actorInput, setActorInput] = useState('');
  const actorId = useDebouncedValue(actorInput.trim(), 400);
  const [action, setAction] = useState('');
  const [service, setService] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [open, setOpen] = useState<AuditLog | null>(null);
  const admins = useAccounts(logs.map((l) => l.actorId));
  const filtered = !!(actorId || action || service);

  // A new filter starts again from the first page.
  useEffect(() => setPage(1), [actorId, action, service]);

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError(null);
    getAuditLogs({ actorId: actorId || undefined, action: action || undefined, service: service || undefined, page, perPage: PER_PAGE })
      .then((res) => {
        if (!current) return;
        setLogs(res.data);
        setTotal(res.total);
      })
      .catch(() => {
        if (!current) return;
        setLogs([]);
        setTotal(0);
        setError('Could not load audit logs.');
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [actorId, action, service, page, reloadKey]);

  const columns: Column<AuditLog>[] = [
    { key: 'createdAt', header: 'When (IST)', render: (r) => formatDateTime(r.createdAt, { seconds: true }).replace(' IST', '') },
    {
      key: 'actorId',
      header: 'Admin',
      render: (r) => {
        const admin = admins[r.actorId];
        return admin ? (
          <span title={r.actorId}>{admin.name}</span>
        ) : (
          <span className="font-mono text-xs" title={r.actorId}>
            {shortId(r.actorId)}
          </span>
        );
      },
    },
    { key: 'action', header: 'Action', render: (r) => <span title={r.action}>{actionLabel(r.action)}</span> },
    {
      key: 'resource',
      header: 'Resource',
      render: (r) => (
        <span className="block leading-tight">
          <span className="capitalize">{r.resource}</span>
          {r.resourceId && (
            <span className="block font-mono text-xs text-gray-500" title={r.resourceId}>
              {shortId(r.resourceId)}
            </span>
          )}
        </span>
      ),
    },
    { key: 'service', header: 'Service', render: (r) => serviceLabel(r.service), className: 'hidden md:table-cell' },
    { key: 'ipAddress', header: 'IP address', className: 'hidden xl:table-cell', render: (r) => r.ipAddress ?? '—' },
    {
      key: 'userAgent',
      header: 'Client',
      className: 'hidden lg:table-cell',
      render: (r) => <span title={r.userAgent ?? undefined}>{summarizeUserAgent(r.userAgent)}</span>,
    },
  ];

  const field = 'border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 bg-white';
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
        <p className="text-sm text-gray-600">Every admin action across services, newest first. Select an entry to see what changed.</p>
      </div>
      <div role="search" aria-label="Filter audit logs" className="flex gap-3 flex-wrap items-end bg-white rounded-xl shadow p-4">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          Action
          <select value={action} onChange={(e) => setAction(e.target.value)} className={field}>
            <option value="">All actions</option>
            {Object.entries(AUDIT_ACTIONS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          Service
          <select value={service} onChange={(e) => setService(e.target.value)} className={field}>
            <option value="">All services</option>
            {Object.entries(AUDIT_SERVICES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700 flex-1 min-w-56">
          Admin user ID
          <input
            value={actorInput}
            onChange={(e) => setActorInput(e.target.value)}
            placeholder="Paste an admin's user ID"
            className={`${field} font-mono`}
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        {(filtered || actorInput) && (
          <button
            type="button"
            onClick={() => {
              setActorInput('');
              setAction('');
              setService('');
            }}
            className="flex items-center gap-1 text-sm font-medium text-indigo-700 hover:underline py-1.5"
          >
            <X size={14} aria-hidden="true" /> Clear filters
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      <DataTable
        label="Audit log entries"
        columns={columns}
        rows={logs}
        isLoading={isLoading}
        total={total}
        totalIsEstimate
        page={page}
        perPage={PER_PAGE}
        onPageChange={setPage}
        onRowClick={setOpen}
        rowLabel={(r) => `${actionLabel(r.action)} by ${admins[r.actorId]?.name ?? 'admin'}, ${formatDateTime(r.createdAt)} - show details`}
        emptyMessage={filtered ? 'No entries match these filters.' : 'No admin actions recorded yet.'}
      />
      {open && <AuditDetails log={open} admin={admins[open.actorId]} onClose={() => setOpen(null)} />}
    </div>
  );
}
