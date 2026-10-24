import { beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import adminApiClient from '../../apiClient';
import * as service from '../ShopReviewService';

const record = {
  id: 's1',
  owner_id: 'o1',
  name: 'Glow Salon',
  category: 'salon',
  city: 'Pune',
  is_active: true,
  verification_status: 'PENDING_REVIEW',
  legal_name: 'Glow Salon Pvt Ltd',
  gstin: '27AAPFU0939F1ZV',
  created_at: '2026-10-20T09:00:00Z',
  submitted_at: '2026-10-21T09:00:00Z',
  documents: [
    { id: 'd1', type: 'PAN', url: '/api/v1/shops/s1/documents/d1/file', uploaded: true, file_name: 'pan.pdf', content_type: 'application/pdf', size_bytes: 2048, is_verified: false },
  ],
  has_payout_details: true,
};

describe('ShopReviewService', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('reads the review queue and maps shops with their documents', async () => {
    const get = vi.spyOn(adminApiClient, 'get').mockResolvedValue({ data: [record] });
    const [shop] = await service.getReviewQueue();
    expect(get).toHaveBeenCalledWith('/admin/shops/review-queue', { params: { limit: 100 } });
    expect(shop).toMatchObject({ id: 's1', ownerId: 'o1', status: 'PENDING_REVIEW', legalName: 'Glow Salon Pvt Ltd', hasPayoutDetails: true });
    expect(shop.documents[0]).toMatchObject({ id: 'd1', type: 'PAN', uploaded: true, fileName: 'pan.pdf', sizeBytes: 2048 });
  });

  it('lists every shop with status and search filters, paged', async () => {
    const get = vi.spyOn(adminApiClient, 'get').mockResolvedValue({ data: { items: [record], total: 30 } });
    const res = await service.listShops({ status: 'REJECTED', q: 'glow', page: 2 });
    expect(get).toHaveBeenCalledWith('/admin/shops', { params: { status: 'REJECTED', q: 'glow', skip: 25, limit: 25 } });
    expect(res.total).toBe(30);
    expect(res.data[0].name).toBe('Glow Salon');
    await service.listShops();
    expect(get).toHaveBeenLastCalledWith('/admin/shops', { params: { status: undefined, q: undefined, skip: 0, limit: 25 } });
  });

  it('approves and rejects with a reason', async () => {
    const post = vi.spyOn(adminApiClient, 'post').mockResolvedValue({ data: { ...record, verification_status: 'REJECTED', rejection_reason: 'Blurred PAN' } });
    await service.approveShop('s1');
    expect(post).toHaveBeenCalledWith('/admin/shops/s1/approve');
    const rejected = await service.rejectShop('s1', 'Blurred PAN');
    expect(post).toHaveBeenLastCalledWith('/admin/shops/s1/reject', { reason: 'Blurred PAN' });
    expect(rejected).toMatchObject({ status: 'REJECTED', rejectionReason: 'Blurred PAN' });
  });

  it('downloads an uploaded file with the admin token', async () => {
    localStorage.setItem('admin_token', 'tok');
    const blob = new Blob(['%PDF']);
    const get = vi.spyOn(axios, 'get').mockResolvedValue({ data: blob });
    const doc = (await (async () => {
      vi.spyOn(adminApiClient, 'get').mockResolvedValue({ data: record });
      return service.getShopForReview('s1');
    })()).documents[0];
    expect(await service.fetchDocumentFile('s1', doc)).toBe(blob);
    expect(get).toHaveBeenCalledWith('/shops/s1/documents/d1/file', expect.objectContaining({ responseType: 'blob', headers: { Authorization: 'Bearer tok' } }));
    localStorage.removeItem('admin_token');
  });
});
