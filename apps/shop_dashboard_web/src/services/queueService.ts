import apiClient from './apiClient';
import { shortId } from './format';

// Walk-in queues (queue_service). A queue belongs to one of the shop's services.

export interface WalkInQueue {
  id: string;
  serviceId: string;
  isAccepting: boolean;
  waiting: number;
  capacity: number;
  /** Staff serving this queue at the same time. */
  servers: number;
  /** Minutes per customer; it follows the real time between "called" and "done". */
  avgServiceMinutes: number;
}

export type EntryStatus = 'WAITING' | 'CALLED' | 'SERVED' | 'NO_SHOW' | 'LEFT';

export interface QueueEntry {
  id: string;
  customerId: string;
  /** First name and last initial ("Ravi S."); the shop never gets a customer's phone or email. */
  customerDisplayName?: string;
  /** 0 for a customer who has been called (being served). */
  position: number;
  status: EntryStatus;
  enteredAt: string;
  calledAt: string | null;
  estimatedWaitMinutes: number | null;
}

interface QueueRecord {
  id: string;
  service_id: string;
  is_accepting: boolean;
  current_size: number;
  max_capacity: number;
  servers: number;
  avg_service_minutes: number;
}

interface EntryRecord {
  id: string;
  customer_id: string;
  customer_display_name?: string;
  position: number;
  status: EntryStatus;
  entered_at: string;
  called_at?: string | null;
  estimated_wait_minutes: number | null;
}

const toQueue = (r: QueueRecord): WalkInQueue => ({
  id: r.id,
  serviceId: r.service_id,
  isAccepting: r.is_accepting,
  waiting: r.current_size,
  capacity: r.max_capacity,
  servers: r.servers,
  avgServiceMinutes: r.avg_service_minutes,
});

const toEntry = (r: EntryRecord): QueueEntry => ({
  id: r.id,
  customerId: r.customer_id,
  customerDisplayName: r.customer_display_name,
  position: r.position,
  status: r.status,
  enteredAt: r.entered_at,
  calledAt: r.called_at ?? null,
  estimatedWaitMinutes: r.estimated_wait_minutes,
});

/** How the shop refers to someone in the queue: their display name, or a short id when there is none. */
export function customerLabel(entry: Pick<QueueEntry, 'customerId' | 'customerDisplayName'>): string {
  const name = entry.customerDisplayName;
  return name && name !== 'Customer' ? name : `Customer ${shortId(entry.customerId)}`;
}

/** Every queue of a service, open or closed. */
export async function getQueues(serviceId: string): Promise<WalkInQueue[]> {
  const { data } = await apiClient.get<QueueRecord[]>('/queues', {
    params: { service_id: serviceId, include_closed: true },
  });
  return data.map(toQueue);
}

/**
 * Opens a service's walk-in queue. `avgServiceMinutes` seeds the wait estimates (use the service's
 * listed duration); the queue then learns from real service times.
 */
export async function openQueue(
  serviceId: string,
  options: { capacity?: number; servers?: number; avgServiceMinutes?: number | null } = {},
): Promise<WalkInQueue> {
  const body: Record<string, unknown> = { service_id: serviceId, max_capacity: options.capacity ?? 50 };
  if (options.servers) body.servers = options.servers;
  if (options.avgServiceMinutes) body.avg_service_minutes = options.avgServiceMinutes;
  const { data } = await apiClient.post<QueueRecord>('/queues', body);
  return toQueue(data);
}

export async function setAccepting(queueId: string, accepting: boolean): Promise<WalkInQueue> {
  const { data } = await apiClient.patch<QueueRecord>(`/queues/${queueId}`, { is_accepting: accepting });
  return toQueue(data);
}

/** How many staff are serving the queue right now; customers' wait estimates follow it. */
export async function setServers(queueId: string, servers: number): Promise<WalkInQueue> {
  const { data } = await apiClient.patch<QueueRecord>(`/queues/${queueId}`, { servers });
  return toQueue(data);
}

/** Customers being served (CALLED, position 0) followed by those waiting, in serving order. */
export async function getWaiting(queueId: string): Promise<QueueEntry[]> {
  const { data } = await apiClient.get<EntryRecord[]>(`/queues/${queueId}/entries`);
  return data.map(toEntry);
}

/** Calls the next customer (they get an "it's your turn" notification); null when nobody is waiting. */
export async function callNext(queueId: string): Promise<QueueEntry | null> {
  const { data } = await apiClient.post<EntryRecord | null>(`/queues/${queueId}/next`);
  return data ? toEntry(data) : null;
}

/** A called customer has been served; the time it took refines the queue's wait estimates. */
export async function completeEntry(queueId: string, entryId: string): Promise<QueueEntry> {
  const { data } = await apiClient.post<EntryRecord>(`/queues/${queueId}/entries/${entryId}/complete`);
  return toEntry(data);
}

/** A called customer did not turn up. */
export async function markNoShow(queueId: string, entryId: string): Promise<QueueEntry> {
  const { data } = await apiClient.post<EntryRecord>(`/queues/${queueId}/entries/${entryId}/no-show`);
  return toEntry(data);
}
