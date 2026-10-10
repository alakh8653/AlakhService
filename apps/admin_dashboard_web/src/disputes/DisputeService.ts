import adminApiClient from '../apiClient';

/** Lifecycle enforced by dispute_service: OPEN → UNDER_REVIEW → ESCALATED/RESOLVED, ESCALATED → RESOLVED. */
export type DisputeStatus = 'OPEN' | 'UNDER_REVIEW' | 'ESCALATED' | 'RESOLVED';

export const DISPUTE_STATUSES: DisputeStatus[] = ['OPEN', 'UNDER_REVIEW', 'ESCALATED', 'RESOLVED'];

export const STATUS_COLORS: Record<DisputeStatus, string> = {
  OPEN: 'bg-red-100 text-red-800',
  UNDER_REVIEW: 'bg-yellow-100 text-yellow-800',
  ESCALATED: 'bg-orange-100 text-orange-800',
  RESOLVED: 'bg-green-100 text-green-800',
};

export interface Dispute {
  id: string;
  /** Short, human-friendly reference derived from the id. */
  caseNumber: string;
  bookingId: string;
  raisedBy: string;
  type: string;
  description: string;
  status: DisputeStatus;
  resolution: string | null;
  evidenceUrls: string[];
  createdAt: string;
  resolvedAt: string | null;
}

export interface DisputeMessage {
  id: string;
  authorId: string;
  content: string;
  createdAt: string;
}

export interface PaginatedDisputes {
  data: Dispute[];
  total: number;
  page: number;
}

/** Records as returned by dispute_service. */
interface DisputeRecord {
  id: string;
  booking_id: string;
  raised_by: string;
  dispute_type: string;
  description: string;
  status: DisputeStatus;
  resolution: string | null;
  evidence_urls: string | null;
  created_at: string;
  resolved_at: string | null;
}

interface DisputeMessageRecord {
  id: string;
  author_id: string;
  content: string;
  created_at: string;
}

function parseEvidence(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((u): u is string => typeof u === 'string') : [];
  } catch {
    return [];
  }
}

export function toDispute(r: DisputeRecord): Dispute {
  return {
    id: r.id,
    caseNumber: r.id.slice(0, 8).toUpperCase(),
    bookingId: r.booking_id,
    raisedBy: r.raised_by,
    type: r.dispute_type,
    description: r.description,
    status: r.status,
    resolution: r.resolution,
    evidenceUrls: parseEvidence(r.evidence_urls),
    createdAt: r.created_at,
    resolvedAt: r.resolved_at,
  };
}

export function formatStatus(status: DisputeStatus): string {
  return status.replace('_', ' ').toLowerCase();
}

export async function getDisputes(
  filters: { status?: DisputeStatus; page?: number; perPage?: number } = {},
): Promise<PaginatedDisputes> {
  const { data } = await adminApiClient.get<{ data: DisputeRecord[]; total: number; page: number }>('/admin/disputes', {
    params: { status: filters.status, page: filters.page, per_page: filters.perPage },
  });
  return { data: data.data.map(toDispute), total: data.total, page: data.page };
}

export async function getDisputeById(id: string): Promise<Dispute> {
  const { data } = await adminApiClient.get<DisputeRecord>(`/admin/disputes/${id}`);
  return toDispute(data);
}

export async function getDisputeMessages(id: string): Promise<DisputeMessage[]> {
  const { data } = await adminApiClient.get<DisputeMessageRecord[]>(`/admin/disputes/${id}/messages`);
  return data.map((m) => ({ id: m.id, authorId: m.author_id, content: m.content, createdAt: m.created_at }));
}

export async function startReview(id: string): Promise<Dispute> {
  const { data } = await adminApiClient.post<DisputeRecord>(`/admin/disputes/${id}/review`);
  return toDispute(data);
}

export async function escalateDispute(id: string): Promise<Dispute> {
  const { data } = await adminApiClient.post<DisputeRecord>(`/admin/disputes/${id}/escalate`);
  return toDispute(data);
}

export async function resolveDispute(id: string, resolution: string): Promise<Dispute> {
  const { data } = await adminApiClient.post<DisputeRecord>(`/admin/disputes/${id}/resolve`, { resolution });
  return toDispute(data);
}

export async function addDisputeMessage(id: string, authorId: string, content: string): Promise<DisputeMessage> {
  const { data } = await adminApiClient.post<DisputeMessageRecord>(`/admin/disputes/${id}/messages`, {
    author_id: authorId,
    content,
  });
  return { id: data.id, authorId: data.author_id, content: data.content, createdAt: data.created_at };
}
