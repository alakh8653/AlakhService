import adminApiClient from '../apiClient';

// Booking chat moderation (booking_service, through the gateway's /admin/chat). Messages in which
// someone wrote a phone number, email, UPI handle or messaging-app link had it hidden before delivery;
// admins see what was originally written, and who keeps trying.

export interface FlaggedMessage {
  id: string;
  bookingId: string;
  senderId: string;
  senderRole: string;
  /** As delivered, with contact details hidden. */
  body: string;
  /** What the sender actually wrote. */
  originalBody: string | null;
  reasons: string[];
  createdAt: string;
}

export interface FlaggedPage {
  data: FlaggedMessage[];
  total: number;
}

export interface RepeatOffender {
  id: string;
  userId: string;
  senderRole: string;
  attempts: number;
  bookings: number;
  lastAttemptAt: string;
}

interface FlaggedRecord {
  id: string;
  booking_id: string;
  sender_id: string;
  sender_role: string;
  body: string;
  original_body: string | null;
  flag_reasons: string[];
  created_at: string;
}

interface OffenderRecord {
  user_id: string;
  sender_role: string;
  attempts: number;
  bookings: number;
  last_attempt_at: string;
}

export const REASON_LABELS: Record<string, string> = {
  phone: 'Phone number',
  email: 'Email',
  upi: 'UPI handle',
  messaging_app: 'WhatsApp / Telegram',
};

export const reasonLabel = (reason: string) => REASON_LABELS[reason] ?? reason;

export async function getFlaggedMessages(
  filters: { senderId?: string; page?: number; perPage?: number } = {},
): Promise<FlaggedPage> {
  const page = filters.page ?? 1;
  const perPage = filters.perPage ?? 25;
  const { data } = await adminApiClient.get<{ items: FlaggedRecord[]; total: number }>('/admin/chat/flagged', {
    params: { sender_id: filters.senderId, skip: (page - 1) * perPage, limit: perPage },
  });
  return {
    data: data.items.map((r) => ({
      id: r.id,
      bookingId: r.booking_id,
      senderId: r.sender_id,
      senderRole: r.sender_role,
      body: r.body,
      originalBody: r.original_body,
      reasons: r.flag_reasons,
      createdAt: r.created_at,
    })),
    total: data.total,
  };
}

export async function getRepeatOffenders(minAttempts = 2, days = 30): Promise<RepeatOffender[]> {
  const { data } = await adminApiClient.get<{ items: OffenderRecord[] }>('/admin/chat/repeat-offenders', {
    params: { min_attempts: minAttempts, days },
  });
  return data.items.map((r) => ({
    id: r.user_id,
    userId: r.user_id,
    senderRole: r.sender_role,
    attempts: r.attempts,
    bookings: r.bookings,
    lastAttemptAt: r.last_attempt_at,
  }));
}
