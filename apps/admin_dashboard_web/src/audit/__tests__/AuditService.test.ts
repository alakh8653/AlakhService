import adminApiClient from '../../apiClient';
import { getAuditLogs } from '../AuditService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn() } }));
const get = vi.mocked(adminApiClient.get);

const record = (id: string) => ({
  id,
  admin_id: 'admin-1',
  action: 'ban_user',
  resource_type: 'user',
  resource_id: 'user-9',
  old_values: null,
  new_values: '{"banned": true}',
  ip_address: '10.0.0.1',
  created_at: '2026-10-10T09:00:00Z',
});

describe('getAuditLogs', () => {
  beforeEach(() => get.mockReset());

  it('maps admin_service records and translates paging to skip/limit', async () => {
    get.mockResolvedValue({ data: [record('a')] });

    const result = await getAuditLogs({ actorId: 'admin-1', page: 3, perPage: 10 });

    expect(get).toHaveBeenCalledWith('/admin/audit-logs', {
      params: { admin_id: 'admin-1', action: undefined, skip: 20, limit: 10 },
    });
    expect(result.data[0]).toEqual({
      id: 'a',
      actorId: 'admin-1',
      action: 'ban_user',
      resource: 'user',
      resourceId: 'user-9',
      oldValues: null,
      newValues: '{"banned": true}',
      ipAddress: '10.0.0.1',
      createdAt: '2026-10-10T09:00:00Z',
    });
    expect(result.total).toBe(21); // partial page: nothing after it
  });

  it('allows a next page while pages come back full', async () => {
    get.mockResolvedValue({ data: [record('a'), record('b')] });
    const result = await getAuditLogs({ page: 1, perPage: 2 });
    expect(result.total).toBe(3);
  });
});
