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
  userAgent: string | null;
  /** The service that carried out the action and recorded it (admin_service, payment_service, ...). */
  service: string;
  createdAt: string;
}

export interface AuditLogFilters {
  actorId?: string;
  action?: string;
  service?: string;
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
  user_agent?: string | null;
  // Entries written before other services reported their actions have no service: admin_service wrote them.
  service?: string | null;
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
    userAgent: r.user_agent ?? null,
    service: r.service || 'admin_service',
    createdAt: r.created_at,
  };
}

export async function getAuditLogs(filters: AuditLogFilters = {}): Promise<PaginatedAuditLogs> {
  const page = filters.page ?? 1;
  const perPage = filters.perPage ?? 25;
  const { data } = await adminApiClient.get<AuditLogRecord[]>('/admin/audit-logs', {
    params: {
      admin_id: filters.actorId,
      action: filters.action,
      service: filters.service,
      skip: (page - 1) * perPage,
      limit: perPage,
    },
  });
  const skipped = (page - 1) * perPage;
  return {
    data: data.map(toAuditLog),
    total: data.length === perPage ? skipped + perPage + 1 : skipped + data.length,
    page,
  };
}

/** The services that report admin actions, with the names the dashboard shows for them. */
export const AUDIT_SERVICES: Record<string, string> = {
  admin_service: 'Admin',
  payment_service: 'Payments',
  dispute_service: 'Disputes',
  pricing_engine: 'Pricing',
};

export function serviceLabel(service: string): string {
  return AUDIT_SERVICES[service] ?? service;
}

/** Actions services record, with readable names; the API's filter matches the exact action. */
export const AUDIT_ACTIONS: Record<string, string> = {
  ban: 'Ban account',
  unban: 'Unban account',
  refund_payment: 'Refund payment',
  update_dispute_status: 'Change dispute status',
  resolve_dispute: 'Resolve dispute',
  create_coupon: 'Create coupon',
  create_role: 'Create role',
  update_role_permissions: 'Change role permissions',
  delete_role: 'Delete role',
  update_system_config: 'Change system setting',
};

export function actionLabel(action: string): string {
  return AUDIT_ACTIONS[action] ?? action.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

/** Old/new values are stored as JSON text; pretty-print them when they parse. */
export function prettyValues(raw: string | null): string | null {
  if (!raw) return null;
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

// Checked in order: Edge and Opera also say "Chrome", and Chrome also says "Safari".
const BROWSERS: [RegExp, string][] = [
  [/Edg\//, 'Edge'],
  [/OPR\//, 'Opera'],
  [/Firefox\//, 'Firefox'],
  [/Chrome\//, 'Chrome'],
  [/Safari\//, 'Safari'],
];
const SYSTEMS: [RegExp, string][] = [
  [/Windows/, 'Windows'],
  [/Android/, 'Android'],
  [/iPhone|iPad/, 'iOS'],
  [/Mac OS X/, 'macOS'],
  [/Linux/, 'Linux'],
];

/** A short "Browser on OS" summary of a user agent; the page shows the full string as a tooltip. */
export function summarizeUserAgent(userAgent: string | null): string {
  if (!userAgent) return '—';
  const browser = BROWSERS.find(([re]) => re.test(userAgent))?.[1];
  const os = SYSTEMS.find(([re]) => re.test(userAgent))?.[1];
  if (!browser) return userAgent.length > 40 ? `${userAgent.slice(0, 40)}…` : userAgent;
  return os ? `${browser} on ${os}` : browser;
}
