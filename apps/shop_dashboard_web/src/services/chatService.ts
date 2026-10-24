import apiClient from './apiClient';

// ── Booking chat and masked calls (booking_service) ──────────────────────────
// The shop and its customer talk only through the platform: phone numbers, emails and UPI handles
// written in a message are replaced with "[hidden for your safety]" by the server.

export const MAX_MESSAGE_LENGTH = 1000;

export type SenderRole = 'customer' | 'shop' | 'provider';

export interface ChatMessage {
  id: string;
  senderRole: SenderRole;
  /** The customer's display name ("Ravi S."), or "Shop" / "Provider". */
  senderName: string;
  isMine: boolean;
  body: string;
  /** Contact details were hidden from it. */
  flagged: boolean;
  createdAt: string;
  readAt: string | null;
}

export interface ChatPage {
  /** Oldest first. */
  messages: ChatMessage[];
  total: number;
  unread: number;
  canSend: boolean;
  /** When a closed booking's chat turns read-only. */
  openUntil: string | null;
  callingEnabled: boolean;
}

interface MessageResponse {
  id: string;
  booking_id: string;
  sender_role: SenderRole;
  sender_name: string;
  is_mine: boolean;
  body: string;
  flagged: boolean;
  created_at: string;
  read_at: string | null;
}

interface MessagePageResponse {
  items: MessageResponse[];
  total: number;
  page: number;
  per_page: number;
  unread: number;
  can_send: boolean;
  open_until: string | null;
  calling_enabled: boolean;
}

export function toMessage(data: MessageResponse): ChatMessage {
  return {
    id: data.id,
    senderRole: data.sender_role,
    senderName: data.sender_name,
    isMine: data.is_mine,
    body: data.body,
    flagged: data.flagged,
    createdAt: data.created_at,
    readAt: data.read_at,
  };
}

const messagesPath = (bookingId: string) => `/bookings/${encodeURIComponent(bookingId)}/messages`;

/** The latest messages of a booking's chat (up to 100), oldest first. */
export async function getMessages(bookingId: string, perPage = 100): Promise<ChatPage> {
  const { data } = await apiClient.get<MessagePageResponse>(messagesPath(bookingId), { params: { page: 1, per_page: perPage } });
  return {
    messages: data.items.map(toMessage),
    total: data.total,
    unread: data.unread,
    canSend: data.can_send,
    openUntil: data.open_until,
    callingEnabled: data.calling_enabled,
  };
}

export async function sendMessage(bookingId: string, body: string): Promise<ChatMessage> {
  const { data } = await apiClient.post<MessageResponse>(messagesPath(bookingId), { body: body.trim() });
  return toMessage(data);
}

/** Marks the customer's messages as read (they see the read receipts). */
export async function markRead(bookingId: string): Promise<number> {
  const { data } = await apiClient.post<{ marked: number }>(`${messagesPath(bookingId)}/read`);
  return data.marked;
}

/** Asks the platform to ring the shop's phone and connect it to the customer; neither sees the other's number. */
export async function callCustomer(bookingId: string): Promise<string> {
  const { data } = await apiClient.post<{ message: string }>(`/bookings/${encodeURIComponent(bookingId)}/call`);
  return data.message;
}
