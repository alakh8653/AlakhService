import apiClient from './apiClient';

// The owner's in-app notifications (notification_service, /notifications).

export interface AppNotification {
  id: string;
  title: string;
  body: string;
  isRead: boolean;
  createdAt: string;
  /** Event details (e.g. booking_id) when the notification came from a platform event. */
  data: Record<string, unknown> | null;
}

interface NotificationRecord {
  id: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
  data?: string | null;
}

function parseData(raw: string | null | undefined): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export async function getUnreadCount(): Promise<number> {
  const { data } = await apiClient.get<{ unread_count: number }>('/notifications/count/unread');
  return data.unread_count ?? 0;
}

export async function getNotifications(perPage = 10): Promise<AppNotification[]> {
  const { data } = await apiClient.get<{ items: NotificationRecord[] }>('/notifications/me', {
    params: { page: 1, per_page: perPage },
  });
  return data.items.map((n) => ({
    id: n.id,
    title: n.title,
    body: n.body,
    isRead: n.is_read,
    createdAt: n.created_at,
    data: parseData(n.data),
  }));
}

export async function markRead(id: string): Promise<void> {
  await apiClient.post(`/notifications/${encodeURIComponent(id)}/read`);
}

export async function markAllRead(): Promise<void> {
  await apiClient.post('/notifications/read-all');
}
