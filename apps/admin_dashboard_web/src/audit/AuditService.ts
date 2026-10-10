import adminApiClient from '../apiClient';

export interface AuditLog {
  id: string;
  actorId: string;
  action: string;
  resource: string;
  resourceId: string | null;
  oldValues: string | null;
  newValues: string | null;
  ipAddress: string | null;
  createdAt: string;
}

export interface AuditLogFilters {
  actorId?: string;
  action?: string;
  page?: number;
  perPage?: number;
}

export interface PaginatedAuditLogs {
  data: AuditLog[];
  /** Total known so far; admin_service does not report a count, so this allows one more page while pages are full. */
  total: number;
  page: number;
}

/** Record as returned by admin_service (GET /api/v1/audit-logs). */
interface AuditLogRecord {
  id: string;
  admin_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  old_values: string | null;
  new_values: string | null;
  ip_address: string | null;
  created_at: string;
}

function toAuditLog(r: AuditLogRecord): AuditLog {
  return {
    id: r.id,
    actorId: r.admin_id,
    action: r.action,
    resource: r.resource_type,
    resourceId: r.resource_id,
    oldValues: r.old_values,
    newValues: r.new_values,
    ipAddress: r.ip_address,
    createdAt: r.created_at,
  };
}

export async function getAuditLogs(filters: AuditLogFilters = {}): Promise<PaginatedAuditLogs> {
  const page = filters.page ?? 1;
  const perPage = filters.perPage ?? 25;
  const { data } = await adminApiClient.get<AuditLogRecord[]>('/admin/audit-logs', {
    params: { admin_id: filters.actorId, action: filters.action, skip: (page - 1) * perPage, limit: perPage },
  });
  const skipped = (page - 1) * perPage;
  return {
    data: data.map(toAuditLog),
    total: data.length === perPage ? skipped + perPage + 1 : skipped + data.length,
    page,
  };
}
