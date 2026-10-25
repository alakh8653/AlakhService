import adminApiClient from '../../apiClient';
import { getDisputes, resolveDispute, toDispute } from '../DisputeService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const get = vi.mocked(adminApiClient.get);
const post = vi.mocked(adminApiClient.post);

const record = {
  id: '3f2a9c1e-0000-4000-8000-000000000000',
  booking_id: 'b-1',
  raised_by: 'cust-1',
  dispute_type: 'service_quality',
  description: 'Late',
  status: 'OPEN' as const,
  resolution: null,
  evidence_urls: '["https://cdn.example/1.jpg", 7]',
  created_at: '2026-10-10T09:00:00Z',
  resolved_at: null,
};

describe('DisputeService', () => {
  it('maps dispute_service records and keeps only string evidence URLs', () => {
    expect(toDispute(record)).toMatchObject({
      caseNumber: '3F2A9C1E',
      bookingId: 'b-1',
      raisedBy: 'cust-1',
      type: 'service_quality',
      evidenceUrls: ['https://cdn.example/1.jpg'],
    });
    expect(toDispute({ ...record, evidence_urls: 'not json' }).evidenceUrls).toEqual([]);
  });

  it('requests a filtered page and maps the result', async () => {
    get.mockResolvedValue({ data: { data: [record], total: 41, page: 3 } });
    const result = await getDisputes({ status: 'OPEN', page: 3, perPage: 20 });
    expect(get).toHaveBeenCalledWith('/admin/disputes', { params: { status: 'OPEN', page: 3, per_page: 20 } });
    expect(result.total).toBe(41);
    expect(result.data[0].id).toBe(record.id);
  });

  it('sends the outcome, with an amount only for a partial refund', async () => {
    post.mockResolvedValue({ data: { ...record, status: 'RESOLVED', outcome: 'REFUND_PARTIAL', refund_amount_cents: 500 } });
    const resolved = await resolveDispute(record.id, 'Half', 'REFUND_PARTIAL', 500);
    expect(post).toHaveBeenLastCalledWith(`/admin/disputes/${record.id}/resolve`, {
      resolution: 'Half',
      outcome: 'REFUND_PARTIAL',
      amount_cents: 500,
    });
    expect([resolved.outcome, resolved.refundAmountCents]).toEqual(['REFUND_PARTIAL', 500]);
    await resolveDispute(record.id, 'Shop wins', 'RELEASE_TO_SHOP', 999);
    expect(post).toHaveBeenLastCalledWith(`/admin/disputes/${record.id}/resolve`, { resolution: 'Shop wins', outcome: 'RELEASE_TO_SHOP' });
    await resolveDispute(record.id, 'Note');
    expect(post).toHaveBeenLastCalledWith(`/admin/disputes/${record.id}/resolve`, { resolution: 'Note', outcome: 'NO_ACTION' });
  });
});
