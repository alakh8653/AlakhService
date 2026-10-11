import apiClient from './apiClient';

// Walk-in queues (queue_service). A queue belongs to one of the shop's services.

export interface WalkInQueue {
  id: string;
  serviceId: string;
  isAccepting: boolean;
  waiting: number;
  capacity: number;
}

export interface QueueEntry {
  id: string;
  customerId: string;
  position: number;
  enteredAt: string;
  estimatedWaitMinutes: number | null;
}

interface QueueRecord {
  id: string;
  service_id: string;
  is_accepting: boolean;
  current_size: number;
  max_capacity: number;
}

interface EntryRecord {
  id: string;
  customer_id: string;
  position: number;
  entered_at: string;
  estimated_wait_minutes: number | null;
}

const toQueue = (r: QueueRecord): WalkInQueue => ({
  id: r.id,
  serviceId: r.service_id,
  isAccepting: r.is_accepting,
  waiting: r.current_size,
  capacity: r.max_capacity,
});

const toEntry = (r: EntryRecord): QueueEntry => ({
  id: r.id,
  customerId: r.customer_id,
  position: r.position,
  enteredAt: r.entered_at,
  estimatedWaitMinutes: r.estimated_wait_minutes,
});

/** Every queue of a service, open or closed. */
export async function getQueues(serviceId: string): Promise<WalkInQueue[]> {
  const { data } = await apiClient.get<QueueRecord[]>('/queues', {
    params: { service_id: serviceId, include_closed: true },
  });
  return data.map(toQueue);
}

export async function openQueue(serviceId: string, capacity = 50): Promise<WalkInQueue> {
  const { data } = await apiClient.post<QueueRecord>('/queues', { service_id: serviceId, max_capacity: capacity });
  return toQueue(data);
}

export async function setAccepting(queueId: string, accepting: boolean): Promise<WalkInQueue> {
  const { data } = await apiClient.patch<QueueRecord>(`/queues/${queueId}`, { is_accepting: accepting });
  return toQueue(data);
}

/** Who is waiting, in serving order. */
export async function getWaiting(queueId: string): Promise<QueueEntry[]> {
  const { data } = await apiClient.get<EntryRecord[]>(`/queues/${queueId}/entries`);
  return data.map(toEntry);
}

/** Calls the next customer (they get an "it's your turn" notification); null when nobody is waiting. */
export async function callNext(queueId: string): Promise<QueueEntry | null> {
  const { data } = await apiClient.post<EntryRecord | null>(`/queues/${queueId}/next`);
  return data ? toEntry(data) : null;
}
