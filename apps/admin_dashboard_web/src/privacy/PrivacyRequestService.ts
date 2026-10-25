import adminApiClient from '../apiClient';

// Data export and account erasure requests (compliance_service, /gdpr/admin/...). Nothing processes them
// automatically: an operator does the work and records the outcome here.

export type RequestStatus = 'PENDING' | 'COMPLETED' | 'REJECTED';
export type RequestKind = 'export' | 'erasure';

export interface PrivacyRequest {
  id: string;
  kind: RequestKind;
  userId: string;
  status: RequestStatus;
  reason: string | null;
  exportUrl: string | null;
  requestedAt: string;
  completedAt: string | null;
  resolutionNote: string | null;
}

interface RequestRecord {
  id: string;
  user_id: string;
  status: RequestStatus;
  reason?: string | null;
  export_url?: string | null;
  requested_at: string;
  completed_at?: string | null;
  resolution_note?: string | null;
}

const toRequest =
  (kind: RequestKind) =>
  (r: RequestRecord): PrivacyRequest => ({
    id: r.id,
    kind,
    userId: r.user_id,
    status: r.status,
    reason: r.reason ?? null,
    exportUrl: r.export_url ?? null,
    requestedAt: r.requested_at,
    completedAt: r.completed_at ?? null,
    resolutionNote: r.resolution_note ?? null,
  });

export async function getPrivacyRequests(
  status: RequestStatus = 'PENDING',
): Promise<{ exports: PrivacyRequest[]; erasures: PrivacyRequest[] }> {
  const { data } = await adminApiClient.get<{ exports: RequestRecord[]; erasures: RequestRecord[] }>('/gdpr/admin/requests', {
    params: { status, limit: 200 },
  });
  return { exports: data.exports.map(toRequest('export')), erasures: data.erasures.map(toRequest('erasure')) };
}

export async function decideRequest(
  request: Pick<PrivacyRequest, 'id' | 'kind'>,
  decision: { status: 'COMPLETED' | 'REJECTED'; note?: string; exportUrl?: string },
): Promise<PrivacyRequest> {
  const { data } = await adminApiClient.post<RequestRecord>(
    `/gdpr/admin/${request.kind}/${encodeURIComponent(request.id)}/decision`,
    {
      status: decision.status,
      note: decision.note || undefined,
      export_url: request.kind === 'export' ? decision.exportUrl || undefined : undefined,
    },
  );
  return toRequest(request.kind)(data);
}
