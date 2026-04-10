import adminApiClient from '../apiClient';

export interface AuditLog {
  id: string;
  actorId: string;
  actorName: string;
  action: string;
  resource: string;
  resourceId: string;
  metadata: Record<string, unknown>;
  ipAddress: string;
  createdAt: string;
}

export interface AuditLogFilters {
  actorId?: string;
  action?: string;
  resource?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  perPage?: number;
}

export interface PaginatedAuditLogs {
  data: AuditLog[];
  total: number;
  page: number;
  totalPages: number;
}

export async function getAuditLogs(filters: AuditLogFilters = {}): Promise<PaginatedAuditLogs> {
  const { data } = await adminApiClient.get<PaginatedAuditLogs>('/admin/audit-logs', { params: filters });
  return data;
}

export async function getAuditLogById(id: string): Promise<AuditLog> {
  const { data } = await adminApiClient.get<{ data: AuditLog }>(`/admin/audit-logs/${id}`);
  return data.data;
}
