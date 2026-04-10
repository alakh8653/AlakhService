import adminApiClient from '../apiClient';

export type DisputeStatus = 'open' | 'under_review' | 'resolved' | 'closed';

export interface DisputeEvidence {
  id: string;
  type: 'image' | 'document' | 'text';
  url?: string;
  content?: string;
  submittedBy: string;
  createdAt: string;
}

export interface Dispute {
  id: string;
  caseNumber: string;
  bookingId: string;
  customerId: string;
  customerName: string;
  shopId: string;
  shopName: string;
  status: DisputeStatus;
  reason: string;
  description: string;
  evidence: DisputeEvidence[];
  assignedAdminId?: string;
  resolution?: string;
  createdAt: string;
  updatedAt: string;
}

export interface PaginatedDisputes {
  data: Dispute[];
  total: number;
  page: number;
  totalPages: number;
}

export async function getDisputes(filters: { status?: DisputeStatus; page?: number; perPage?: number } = {}): Promise<PaginatedDisputes> {
  const { data } = await adminApiClient.get<PaginatedDisputes>('/admin/disputes', { params: filters });
  return data;
}

export async function getDisputeById(id: string): Promise<Dispute> {
  const { data } = await adminApiClient.get<{ data: Dispute }>(`/admin/disputes/${id}`);
  return data.data;
}

export async function updateDisputeStatus(id: string, status: DisputeStatus, resolution?: string): Promise<Dispute> {
  const { data } = await adminApiClient.patch<{ data: Dispute }>(`/admin/disputes/${id}`, { status, resolution });
  return data.data;
}

export async function assignDispute(id: string, adminId: string): Promise<Dispute> {
  const { data } = await adminApiClient.post<{ data: Dispute }>(`/admin/disputes/${id}/assign`, { adminId });
  return data.data;
}
