import adminApiClient from '../../apiClient';
import { getAuditLogs, serviceLabel, summarizeUserAgent } from '../AuditService';

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
  user_agent: 'Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36',
  service: 'payment_service',
  created_at: '2026-10-10T09:00:00Z',
});

describe('getAuditLogs', () => {
  beforeEach(() => get.mockReset());

  it('maps admin_service records and translates paging to skip/limit', async () => {
    get.mockResolvedValue({ data: [record('a')] });

    const result = await getAuditLogs({ actorId: 'admin-1', page: 3, perPage: 10 });

    expect(get).toHaveBeenCalledWith('/admin/audit-logs', {
      params: { admin_id: 'admin-1', action: undefined, service: undefined, skip: 20, limit: 10 },
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
      userAgent: 'Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36',
      service: 'payment_service',
      createdAt: '2026-10-10T09:00:00Z',
    });
    expect(result.total).toBe(21); // partial page: nothing after it
  });

  it('allows a next page while pages come back full', async () => {
    get.mockResolvedValue({ data: [record('a'), record('b')] });
    const result = await getAuditLogs({ page: 1, perPage: 2 });
    expect(result.total).toBe(3);
  });

  it('filters by the service that recorded the entry', async () => {
    get.mockResolvedValue({ data: [] });
    await getAuditLogs({ service: 'dispute_service' });
    expect(get).toHaveBeenCalledWith('/admin/audit-logs', {
      params: { admin_id: undefined, action: undefined, service: 'dispute_service', skip: 0, limit: 25 },
    });
  });

  it('treats entries without a service or user agent as written by admin_service', async () => {
    const older: Partial<ReturnType<typeof record>> = record('old');
    delete older.user_agent;
    delete older.service;
    get.mockResolvedValue({ data: [older] });
    const [entry] = (await getAuditLogs()).data;
    expect(entry.service).toBe('admin_service');
    expect(entry.userAgent).toBeNull();
  });
});

describe('audit display helpers', () => {
  it('names the services that report admin actions', () => {
    expect(serviceLabel('payment_service')).toBe('Payments');
    expect(serviceLabel('pricing_engine')).toBe('Pricing');
    expect(serviceLabel('new_service')).toBe('new_service');
  });

  it('summarizes user agents as browser and OS', () => {
    expect(summarizeUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit Version/17.0 Safari/605.1')).toBe(
      'Safari on macOS',
    );
    expect(summarizeUserAgent('Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36 Edg/130.0')).toBe('Edge on Windows');
    expect(summarizeUserAgent('Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0')).toBe('Firefox on Linux');
    expect(summarizeUserAgent('curl/8.5.0')).toBe('curl/8.5.0');
    expect(summarizeUserAgent('x'.repeat(60))).toBe(`${'x'.repeat(40)}…`);
    expect(summarizeUserAgent(null)).toBe('—');
  });
});
