import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import * as kyc from '../kycService';
import { getEarnings, getPayouts, formatRupees } from '../earningsService';
import { getNotifications, getUnreadCount, markAllRead, markRead } from '../notificationService';
import { toShop, verificationOf } from '../shopService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

const api = vi.mocked(apiClient);

beforeEach(() => vi.clearAllMocks());

describe('identifier formats', () => {
  it('checks GSTIN format and check character like the server', () => {
    expect(kyc.isValidGstin('27AAPFU0939F1ZV')).toBe(true);
    expect(kyc.isValidGstin(' 27aapfu0939f1zv ')).toBe(true);
    expect(kyc.isValidGstin('27AAPFU0939F1ZW')).toBe(false);
    expect(kyc.isValidGstin('27AAPFU0939F1Z')).toBe(false);
  });

  it('checks IFSC, UPI and account numbers', () => {
    expect(kyc.isValidIfsc('hdfc0001234')).toBe(true);
    expect(kyc.isValidIfsc('HDFC1001234')).toBe(false);
    expect(kyc.isValidUpi('asha.salon@okhdfcbank')).toBe(true);
    expect(kyc.isValidUpi('asha')).toBe(false);
    expect(kyc.isValidAccountNumber('1234 5678 9012')).toBe(true);
    expect(kyc.isValidAccountNumber('12ab')).toBe(false);
  });

  it('refuses files of the wrong type or size before uploading', () => {
    expect(kyc.fileProblem(new File(['%PDF'], 'a.pdf', { type: 'application/pdf' }))).toBeNull();
    expect(kyc.fileProblem(new File(['x'], 'a.exe', { type: 'application/x-msdownload' }))).toMatch(/PDF, JPG/);
    const big = new File(['x'], 'big.pdf', { type: 'application/pdf' });
    Object.defineProperty(big, 'size', { value: kyc.MAX_FILE_BYTES + 1 });
    expect(kyc.fileProblem(big)).toMatch(/5 MB/);
  });
});

describe('kycService', () => {
  it('uploads the file as the body with its type', async () => {
    api.post.mockResolvedValueOnce({ data: { id: 'd1', type: 'PAN', url: '/x', uploaded: true, file_name: 'pan.pdf', is_verified: false } });
    const file = new File(['%PDF-1'], 'pan.pdf', { type: 'application/pdf' });
    const doc = await kyc.uploadDocument('s1', 'PAN', file);
    expect(api.post).toHaveBeenCalledWith('/shops/s1/documents/upload', file, {
      params: { type: 'PAN', file_name: 'pan.pdf' },
      headers: { 'Content-Type': 'application/pdf' },
      timeout: 60_000,
    });
    expect(doc).toMatchObject({ id: 'd1', uploaded: true, fileName: 'pan.pdf' });
  });

  it('lists, links and deletes documents and submits for review', async () => {
    api.get.mockResolvedValueOnce({ data: [{ id: 'd1', type: 'GST', url: 'https://x', is_verified: true }] });
    expect((await kyc.getDocuments('s1'))[0]).toMatchObject({ type: 'GST', uploaded: false, isVerified: true });
    api.post.mockResolvedValueOnce({ data: { id: 'd2', type: 'UDYAM', url: 'https://d', is_verified: false } });
    await kyc.addDocumentLink('s1', 'UDYAM', 'https://d');
    expect(api.post).toHaveBeenLastCalledWith('/shops/s1/documents', { type: 'UDYAM', url: 'https://d' });
    api.delete.mockResolvedValueOnce({});
    await kyc.deleteDocument('s1', 'd2');
    expect(api.delete).toHaveBeenCalledWith('/shops/s1/documents/d2');
    api.post.mockResolvedValueOnce({
      data: { id: 's1', owner_id: 'u', name: 'S', category: 'salon', rating_avg: 0, rating_count: 0, is_active: true, is_verified: false, created_at: '', verification_status: 'PENDING_REVIEW', submitted_at: '2026-10-22T00:00:00Z' },
    });
    const shop = await kyc.submitForReview('s1');
    expect(api.post).toHaveBeenLastCalledWith('/shops/s1/submit-for-review');
    expect(shop).toMatchObject({ verificationStatus: 'PENDING_REVIEW', submittedAt: '2026-10-22T00:00:00Z' });
  });

  it('reads payout details (none yet is null) and saves bank or UPI details', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 404 } });
    expect(await kyc.getPayoutDetails('s1')).toBeNull();
    api.get.mockRejectedValueOnce({ response: { status: 500 } });
    await expect(kyc.getPayoutDetails('s1')).rejects.toBeTruthy();

    api.put.mockResolvedValue({ data: { method: 'BANK', account_name: 'Asha', account_number: 'XXXXXXXX9012', ifsc: 'HDFC0001234', upi_id: null, updated_at: null } });
    const saved = await kyc.savePayoutDetails('s1', { method: 'BANK', accountName: ' Asha ', accountNumber: '1234 5678 9012', ifsc: 'hdfc0001234' });
    expect(api.put).toHaveBeenLastCalledWith('/shops/s1/payout-details', {
      method: 'BANK', account_name: 'Asha', account_number: '123456789012', ifsc: 'HDFC0001234',
    });
    expect(saved.accountNumber).toBe('XXXXXXXX9012');
    await kyc.savePayoutDetails('s1', { method: 'UPI', upiId: ' asha@okicici ' });
    expect(api.put).toHaveBeenLastCalledWith('/shops/s1/payout-details', { method: 'UPI', upi_id: 'asha@okicici', account_name: undefined });
  });
});

describe('shop verification status', () => {
  it('maps the status, falling back to is_verified for older responses', () => {
    const base = { id: 's', owner_id: 'u', name: 'S', category: 'c', description: null, city: null, address: null, phone: null, email: null, rating_avg: 0, rating_count: 0, is_active: true, created_at: '' };
    expect(toShop({ ...base, is_verified: true }).verificationStatus).toBe('APPROVED');
    expect(toShop({ ...base, is_verified: false, verification_status: 'REJECTED', rejection_reason: 'Blurred' })).toMatchObject({
      verificationStatus: 'REJECTED',
      rejectionReason: 'Blurred',
    });
    expect(verificationOf({ isVerified: false })).toBe('PENDING_REVIEW');
  });
});

describe('earningsService', () => {
  it('reads earnings for a date range and payouts', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        currency: 'INR', gross: 1000, commission: 100, gst_on_commission: 18, net: 882, pending_payout: 882, paid_out: 0,
        items: [{ booking_id: 'b1', payment_id: 'p1', completed_at: '2026-10-20T10:00:00Z', gross: 1000, commission: 100, gst_on_commission: 18, net: 882, payout_status: 'READY' }],
      },
    });
    const e = await getEarnings('s1', '2026-10-01', '2026-10-31');
    expect(api.get).toHaveBeenCalledWith('/payments/shops/s1/earnings', { params: { from: '2026-10-01', to: '2026-10-31' } });
    expect(e).toMatchObject({ net: 882, gstOnCommission: 18, pendingPayout: 882 });
    expect(e.items[0]).toMatchObject({ bookingId: 'b1', payoutStatus: 'READY' });

    api.get.mockResolvedValueOnce({ data: [{ id: 'po1', period_from: '2026-10-01', period_to: '2026-10-07', amount: 500.5, status: 'PAID', paid_at: '2026-10-08T00:00:00Z', reference: 'UTR123' }] });
    expect((await getPayouts('s1'))[0]).toMatchObject({ id: 'po1', amount: 500.5, reference: 'UTR123' });
    expect(api.get).toHaveBeenLastCalledWith('/payments/shops/s1/payouts');
    expect(formatRupees(123456.5)).toBe('₹1,23,456.50');
  });
});

describe('notificationService', () => {
  it('reads the unread count and notifications and marks them read', async () => {
    api.get.mockResolvedValueOnce({ data: { unread_count: 3 } });
    expect(await getUnreadCount()).toBe(3);
    expect(api.get).toHaveBeenLastCalledWith('/notifications/count/unread');
    api.get.mockResolvedValueOnce({
      data: { items: [{ id: 'n1', title: 'New booking', body: 'Haircut', is_read: false, created_at: '2026-10-20T10:00:00Z', data: '{"event":"booking.created","booking_id":"b1"}' }] },
    });
    const [n] = await getNotifications();
    expect(api.get).toHaveBeenLastCalledWith('/notifications/me', { params: { page: 1, per_page: 10 } });
    expect(n.data).toEqual({ event: 'booking.created', booking_id: 'b1' });
    api.post.mockResolvedValue({});
    await markRead('n1');
    expect(api.post).toHaveBeenLastCalledWith('/notifications/n1/read');
    await markAllRead();
    expect(api.post).toHaveBeenLastCalledWith('/notifications/read-all');
  });
});
