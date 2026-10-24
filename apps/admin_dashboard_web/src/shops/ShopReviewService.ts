import axios from 'axios';
import adminApiClient from '../apiClient';

// Shop onboarding review (shop_service, through the gateway's /admin/shops). New shops stay hidden from
// customers until an admin has checked their KYC documents and approved them.

export type VerificationStatus = 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';

export const STATUS_LABELS: Record<VerificationStatus, string> = {
  PENDING_REVIEW: 'In review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
};

export const DOCUMENT_LABELS: Record<string, string> = {
  PAN: 'PAN card',
  GST: 'GST certificate',
  AADHAAR: 'Aadhaar',
  UDYAM: 'Udyam registration',
  BANK_PROOF: 'Bank proof',
  SHOP_PHOTO: 'Shop photo',
};

export const documentLabel = (type: string) => DOCUMENT_LABELS[type] ?? type;

export interface ShopDocument {
  id: string;
  type: string;
  url: string;
  /** Stored by shop_service: fetched with the admin's token rather than opened as a link. */
  uploaded: boolean;
  fileName: string | null;
  contentType: string | null;
  sizeBytes: number | null;
  isVerified: boolean;
  createdAt: string | null;
}

export interface AdminShop {
  id: string;
  ownerId: string;
  name: string;
  category: string;
  city: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  isActive: boolean;
  status: VerificationStatus;
  rejectionReason: string | null;
  legalName: string | null;
  legalAddress: string | null;
  gstin: string | null;
  createdAt: string;
  submittedAt: string | null;
  reviewedAt: string | null;
}

export interface ShopForReview extends AdminShop {
  documents: ShopDocument[];
  hasPayoutDetails: boolean;
}

interface DocumentRecord {
  id: string;
  type: string;
  url: string;
  uploaded?: boolean;
  file_name?: string | null;
  content_type?: string | null;
  size_bytes?: number | null;
  is_verified: boolean;
  created_at?: string | null;
}

interface ShopRecord {
  id: string;
  owner_id: string;
  name: string;
  category: string;
  city?: string | null;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  is_active: boolean;
  verification_status?: VerificationStatus;
  rejection_reason?: string | null;
  legal_name?: string | null;
  legal_address?: string | null;
  gstin?: string | null;
  created_at: string;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  documents?: DocumentRecord[];
  has_payout_details?: boolean;
}

const toDocument = (d: DocumentRecord): ShopDocument => ({
  id: d.id,
  type: d.type,
  url: d.url,
  uploaded: !!d.uploaded,
  fileName: d.file_name ?? null,
  contentType: d.content_type ?? null,
  sizeBytes: d.size_bytes ?? null,
  isVerified: d.is_verified,
  createdAt: d.created_at ?? null,
});

const toShop = (r: ShopRecord): AdminShop => ({
  id: r.id,
  ownerId: r.owner_id,
  name: r.name,
  category: r.category,
  city: r.city ?? null,
  address: r.address ?? null,
  phone: r.phone ?? null,
  email: r.email ?? null,
  isActive: r.is_active,
  status: r.verification_status ?? 'PENDING_REVIEW',
  rejectionReason: r.rejection_reason ?? null,
  legalName: r.legal_name ?? null,
  legalAddress: r.legal_address ?? null,
  gstin: r.gstin ?? null,
  createdAt: r.created_at,
  submittedAt: r.submitted_at ?? null,
  reviewedAt: r.reviewed_at ?? null,
});

const toReview = (r: ShopRecord): ShopForReview => ({
  ...toShop(r),
  documents: (r.documents ?? []).map(toDocument),
  hasPayoutDetails: !!r.has_payout_details,
});

/** Submitted shops waiting for a decision, oldest first, with their documents. */
export async function getReviewQueue(): Promise<ShopForReview[]> {
  const { data } = await adminApiClient.get<ShopRecord[]>('/admin/shops/review-queue', { params: { limit: 100 } });
  return data.map(toReview);
}

export async function listShops(
  filters: { status?: VerificationStatus; q?: string; page?: number; perPage?: number } = {},
): Promise<{ data: AdminShop[]; total: number }> {
  const page = filters.page ?? 1;
  const perPage = filters.perPage ?? 25;
  const { data } = await adminApiClient.get<{ items: ShopRecord[]; total: number }>('/admin/shops', {
    params: { status: filters.status, q: filters.q || undefined, skip: (page - 1) * perPage, limit: perPage },
  });
  return { data: data.items.map(toShop), total: data.total };
}

export async function getShopForReview(id: string): Promise<ShopForReview> {
  const { data } = await adminApiClient.get<ShopRecord>(`/admin/shops/${encodeURIComponent(id)}`);
  return toReview(data);
}

export async function approveShop(id: string): Promise<AdminShop> {
  const { data } = await adminApiClient.post<ShopRecord>(`/admin/shops/${encodeURIComponent(id)}/approve`);
  return toShop(data);
}

export async function rejectShop(id: string, reason: string): Promise<AdminShop> {
  const { data } = await adminApiClient.post<ShopRecord>(`/admin/shops/${encodeURIComponent(id)}/reject`, { reason });
  return toShop(data);
}

/**
 * An uploaded document's file, as a Blob. It needs the admin's token, so it cannot be a plain link; the
 * shared client only accepts JSON, so this one request is made directly.
 */
export async function fetchDocumentFile(shopId: string, doc: ShopDocument): Promise<Blob> {
  const token = localStorage.getItem('admin_token');
  const path = `/shops/${encodeURIComponent(shopId)}/documents/${encodeURIComponent(doc.id)}/file`;
  const { data } = await axios.get<Blob>(path, {
    baseURL: adminApiClient.defaults.baseURL,
    responseType: 'blob',
    timeout: 30_000,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  return data;
}
