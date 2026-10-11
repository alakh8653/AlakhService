import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import { callNext, getQueues, getWaiting, openQueue, setAccepting } from '../queueService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));
const api = vi.mocked(apiClient);

const record = { id: 'q1', service_id: 's1', is_accepting: true, current_size: 2, max_capacity: 50 };

describe('queueService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists a service\'s queues including closed ones', async () => {
    api.get.mockResolvedValueOnce({ data: [record] });
    const queues = await getQueues('s1');
    expect(api.get).toHaveBeenCalledWith('/queues', { params: { service_id: 's1', include_closed: true } });
    expect(queues).toEqual([{ id: 'q1', serviceId: 's1', isAccepting: true, waiting: 2, capacity: 50 }]);
  });

  it('opens, closes and calls the next customer', async () => {
    api.post.mockResolvedValueOnce({ data: record });
    await openQueue('s1');
    expect(api.post).toHaveBeenCalledWith('/queues', { service_id: 's1', max_capacity: 50 });

    api.patch.mockResolvedValueOnce({ data: { ...record, is_accepting: false } });
    expect((await setAccepting('q1', false)).isAccepting).toBe(false);
    expect(api.patch).toHaveBeenCalledWith('/queues/q1', { is_accepting: false });

    api.post.mockResolvedValueOnce({
      data: { id: 'e1', customer_id: 'c1', position: 0, entered_at: '2026-10-11T10:00:00Z', estimated_wait_minutes: 0 },
    });
    expect((await callNext('q1'))?.customerId).toBe('c1');
    api.post.mockResolvedValueOnce({ data: null });
    expect(await callNext('q1')).toBeNull();
  });

  it('reads the waiting list in serving order', async () => {
    api.get.mockResolvedValueOnce({
      data: [{ id: 'e2', customer_id: 'c2', position: 1, entered_at: '2026-10-11T10:05:00Z', estimated_wait_minutes: 0 }],
    });
    expect((await getWaiting('q1'))[0]).toMatchObject({ customerId: 'c2', position: 1 });
    expect(api.get).toHaveBeenCalledWith('/queues/q1/entries');
  });
});
