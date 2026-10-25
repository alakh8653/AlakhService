import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import {
  callNext,
  completeEntry,
  customerLabel,
  getQueues,
  getWaiting,
  markNoShow,
  openQueue,
  setAccepting,
  setServers,
} from '../queueService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));
const api = vi.mocked(apiClient);

const record = {
  id: 'q1',
  service_id: 's1',
  is_accepting: true,
  current_size: 2,
  max_capacity: 50,
  servers: 1,
  avg_service_minutes: 30,
};
const entry = (over: Record<string, unknown> = {}) => ({
  id: 'e1',
  customer_id: 'c1',
  position: 0,
  status: 'CALLED',
  entered_at: '2026-10-11T10:00:00Z',
  called_at: '2026-10-11T10:20:00Z',
  estimated_wait_minutes: 0,
  ...over,
});

describe('queueService', () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists a service's queues including closed ones", async () => {
    api.get.mockResolvedValueOnce({ data: [record] });
    const queues = await getQueues('s1');
    expect(api.get).toHaveBeenCalledWith('/queues', { params: { service_id: 's1', include_closed: true } });
    expect(queues).toEqual([
      { id: 'q1', serviceId: 's1', isAccepting: true, waiting: 2, capacity: 50, servers: 1, avgServiceMinutes: 30 },
    ]);
  });

  it('opens a queue seeded with the service duration, closes it and calls the next customer', async () => {
    api.post.mockResolvedValueOnce({ data: record });
    await openQueue('s1', { avgServiceMinutes: 30 });
    expect(api.post).toHaveBeenCalledWith('/queues', { service_id: 's1', max_capacity: 50, avg_service_minutes: 30 });

    api.post.mockResolvedValueOnce({ data: record });
    await openQueue('s2');
    expect(api.post).toHaveBeenLastCalledWith('/queues', { service_id: 's2', max_capacity: 50 });

    api.patch.mockResolvedValueOnce({ data: { ...record, is_accepting: false } });
    expect((await setAccepting('q1', false)).isAccepting).toBe(false);
    expect(api.patch).toHaveBeenCalledWith('/queues/q1', { is_accepting: false });

    api.post.mockResolvedValueOnce({ data: entry() });
    expect(await callNext('q1')).toMatchObject({ customerId: 'c1', status: 'CALLED', calledAt: '2026-10-11T10:20:00Z' });
    api.post.mockResolvedValueOnce({ data: null });
    expect(await callNext('q1')).toBeNull();
  });

  it('changes how many staff serve the queue', async () => {
    api.patch.mockResolvedValueOnce({ data: { ...record, servers: 2 } });
    expect((await setServers('q1', 2)).servers).toBe(2);
    expect(api.patch).toHaveBeenCalledWith('/queues/q1', { servers: 2 });
  });

  it('marks a called customer done or a no-show', async () => {
    api.post.mockResolvedValueOnce({ data: entry({ status: 'SERVED' }) });
    expect((await completeEntry('q1', 'e1')).status).toBe('SERVED');
    expect(api.post).toHaveBeenCalledWith('/queues/q1/entries/e1/complete');

    api.post.mockResolvedValueOnce({ data: entry({ status: 'NO_SHOW' }) });
    expect((await markNoShow('q1', 'e1')).status).toBe('NO_SHOW');
    expect(api.post).toHaveBeenLastCalledWith('/queues/q1/entries/e1/no-show');
  });

  it('reads who is being served and who is waiting, in serving order', async () => {
    api.get.mockResolvedValueOnce({
      data: [entry(), entry({ id: 'e2', customer_id: 'c2', position: 1, status: 'WAITING', called_at: null })],
    });
    const list = await getWaiting('q1');
    expect(list.map((e) => [e.customerId, e.status, e.position])).toEqual([
      ['c1', 'CALLED', 0],
      ['c2', 'WAITING', 1],
    ]);
    expect(api.get).toHaveBeenCalledWith('/queues/q1/entries');
  });

  it('names people in the queue by display name, else by a short id', () => {
    expect(customerLabel({ customerId: 'abcdef123456', customerDisplayName: 'Ravi S.' })).toBe('Ravi S.');
    expect(customerLabel({ customerId: 'abcdef123456', customerDisplayName: 'Customer' })).toBe('Customer ABCDEF12');
    expect(customerLabel({ customerId: 'abcdef123456' })).toBe('Customer ABCDEF12');
  });
});
