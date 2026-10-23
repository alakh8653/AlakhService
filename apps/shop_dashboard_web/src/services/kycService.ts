import apiClient from './apiClient';
import { toShop } from './shopService';
import type { Shop } from '../types';

// Onboarding (shop_service): KYC documents, payout details and submitting the shop for review.

export const DOCUMENT_TYPES = ['PAN', 'GST', 'AADHAAR', 'UDYAM', 'BANK_PROOF', 'SHOP_PHOTO'] as const;
export type DocumentType = (typeof DOCUMENT_TYPES)[number];

export const DOCUMENT_LABELS: Record<DocumentType, string> = {
  PAN: 'PAN card',
  GST: 'GST certificate',
  AADHAAR: 'Aadhaar',
  UDYAM: 'Udyam registration',
  BANK_PROOF: 'Bank proof (cancelled cheque or passbook)',
  SHOP_PHOTO: 'Shop photo',
};

/** What shop_service accepts (it checks the file's bytes too). */
export const ALLOWED_FILE_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
export const MAX_FILE_BYTES = 5 * 1024 * 1024;

export interface ShopDocument {
  id: string;
  type: string;
  url: string;
  uploaded: boolean;
  fileName: string | null;
  sizeBytes: number | null;
  isVerified: boolean;
  createdAt: string | null;
}

interface DocumentRecord {
  id: string;
  type: string;
  url: string;
  uploaded?: boolean;
  file_name?: string | null;
  size_bytes?: number | null;
  is_verified: boolean;
  created_at?: string | null;
}

const toDocument = (d: DocumentRecord): ShopDocument => ({
  id: d.id,
  type: d.type,
  url: d.url,
  uploaded: !!d.uploaded,
  fileName: d.file_name ?? null,
  sizeBytes: d.size_bytes ?? null,
  isVerified: d.is_verified,
  createdAt: d.created_at ?? null,
});

const shopPath = (shopId: string) => `/shops/${encodeURIComponent(shopId)}`;

export async function getDocuments(shopId: string): Promise<ShopDocument[]> {
  const { data } = await apiClient.get<DocumentRecord[]>(`${shopPath(shopId)}/documents`);
  return data.map(toDocument);
}

/** Problems with a file before it is sent, or null when it can be uploaded. */
export function fileProblem(file: File): string | null {
  if (!ALLOWED_FILE_TYPES.includes(file.type)) return 'Choose a PDF, JPG, PNG or WebP file.';
  if (file.size > MAX_FILE_BYTES) return 'The file is larger than 5 MB.';
  if (file.size === 0) return 'The file is empty.';
  return null;
}

/** Uploads the file itself as the request body (shop_service reads Content-Type and the bytes). */
export async function uploadDocument(shopId: string, type: DocumentType, file: File): Promise<ShopDocument> {
  const { data } = await apiClient.post<DocumentRecord>(`${shopPath(shopId)}/documents/upload`, file, {
    params: { type, file_name: file.name.slice(0, 255) },
    headers: { 'Content-Type': file.type },
    timeout: 60_000,
  });
  return toDocument(data);
}

/** A document kept elsewhere (DigiLocker, a drive link), by its https link. */
export async function addDocumentLink(shopId: string, type: DocumentType, url: string): Promise<ShopDocument> {
  const { data } = await apiClient.post<DocumentRecord>(`${shopPath(shopId)}/documents`, { type, url });
  return toDocument(data);
}

export async function deleteDocument(shopId: string, documentId: string): Promise<void> {
  await apiClient.delete(`${shopPath(shopId)}/documents/${encodeURIComponent(documentId)}`);
}

export async function downloadDocument(shopId: string, documentId: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`${shopPath(shopId)}/documents/${encodeURIComponent(documentId)}/file`, {
    responseType: 'blob',
  });
  return data;
}

export async function submitForReview(shopId: string): Promise<Shop> {
  const { data } = await apiClient.post(`${shopPath(shopId)}/submit-for-review`);
  return toShop(data);
}

// Payout details

export type PayoutMethod = 'BANK' | 'UPI';

export interface PayoutDetails {
  method: PayoutMethod;
  accountName: string | null;
  /** Masked by the API: only the last four digits are readable. */
  accountNumber: string | null;
  ifsc: string | null;
  upiId: string | null;
  updatedAt: string | null;
}

interface PayoutRecord {
  method: PayoutMethod;
  account_name: string | null;
  account_number: string | null;
  ifsc: string | null;
  upi_id: string | null;
  updated_at: string | null;
}

const toPayout = (r: PayoutRecord): PayoutDetails => ({
  method: r.method,
  accountName: r.account_name,
  accountNumber: r.account_number,
  ifsc: r.ifsc,
  upiId: r.upi_id,
  updatedAt: r.updated_at,
});

/** The shop's payout details, or null when none are saved yet. */
export async function getPayoutDetails(shopId: string): Promise<PayoutDetails | null> {
  try {
    const { data } = await apiClient.get<PayoutRecord>(`${shopPath(shopId)}/payout-details`);
    return toPayout(data);
  } catch (err) {
    if ((err as { response?: { status?: number } }).response?.status === 404) return null;
    throw err;
  }
}

export interface PayoutInput {
  method: PayoutMethod;
  accountName?: string;
  accountNumber?: string;
  ifsc?: string;
  upiId?: string;
}

export async function savePayoutDetails(shopId: string, input: PayoutInput): Promise<PayoutDetails> {
  const body =
    input.method === 'BANK'
      ? {
          method: 'BANK',
          account_name: input.accountName?.trim(),
          account_number: input.accountNumber?.replace(/\s/g, ''),
          ifsc: input.ifsc?.trim().toUpperCase(),
        }
      : { method: 'UPI', upi_id: input.upiId?.trim(), account_name: input.accountName?.trim() || undefined };
  const { data } = await apiClient.put<PayoutRecord>(`${shopPath(shopId)}/payout-details`, body);
  return toPayout(data);
}

// Formats (the same rules as shop_service)

const GSTIN_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const GSTIN_RE = /^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

export function isValidGstin(value: string): boolean {
  const v = value.trim().toUpperCase();
  if (!GSTIN_RE.test(v)) return false;
  let total = 0;
  for (let i = 0; i < 14; i++) {
    const product = GSTIN_CHARS.indexOf(v[i]) * (i % 2 ? 2 : 1);
    total += Math.floor(product / 36) + (product % 36);
  }
  return GSTIN_CHARS[(36 - (total % 36)) % 36] === v[14];
}

export const isValidIfsc = (value: string) => /^[A-Z]{4}0[A-Z0-9]{6}$/.test(value.trim().toUpperCase());
export const isValidUpi = (value: string) => /^[A-Za-z0-9][A-Za-z0-9._-]{1,255}@[A-Za-z][A-Za-z0-9]{1,63}$/.test(value.trim());
export const isValidAccountNumber = (value: string) => /^[0-9]{9,18}$/.test(value.replace(/\s/g, ''));
