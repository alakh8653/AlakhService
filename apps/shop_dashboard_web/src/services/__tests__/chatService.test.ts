import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../apiClient';
import { callCustomer, getMessages, markRead, sendMessage } from '../chatService';

vi.mock('../apiClient', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const api = vi.mocked(apiClient);

const apiMessage = {
  id: 'm1',
  booking_id: 'b1',
  sender_role: 'customer',
  sender_name: 'Ravi S.',
  is_mine: false,
  body: 'Is 10 fine?',
  flagged: false,
  created_at: '2026-10-19T10:00:00Z',
  read_at: null,
};

describe('chatService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('reads the chat page and maps it', async () => {
    api.get.mockResolvedValue({
      data: { items: [apiMessage], total: 1, page: 1, per_page: 100, unread: 1, can_send: true, open_until: null, calling_enabled: false },
    });
    const chat = await getMessages('b/1');
    expect(api.get).toHaveBeenCalledWith('/bookings/b%2F1/messages', { params: { page: 1, per_page: 100 } });
    expect(chat).toEqual({
      messages: [
        {
          id: 'm1', senderRole: 'customer', senderName: 'Ravi S.', isMine: false, body: 'Is 10 fine?', flagged: false,
          createdAt: '2026-10-19T10:00:00Z', readAt: null,
        },
      ],
      total: 1,
      unread: 1,
      canSend: true,
      openUntil: null,
      callingEnabled: false,
    });
  });

  it('sends trimmed messages, marks them read and asks for a masked call', async () => {
    api.post
      .mockResolvedValueOnce({ data: { ...apiMessage, is_mine: true, sender_role: 'shop', sender_name: 'Shop' } })
      .mockResolvedValueOnce({ data: { marked: 2 } })
      .mockResolvedValueOnce({ data: { status: 'queued', call_id: 'c1', callee: 'customer', message: 'We are calling you now.' } });

    expect((await sendMessage('b1', '  Yes  ')).isMine).toBe(true);
    expect(api.post).toHaveBeenNthCalledWith(1, '/bookings/b1/messages', { body: 'Yes' });
    expect(await markRead('b1')).toBe(2);
    expect(api.post).toHaveBeenNthCalledWith(2, '/bookings/b1/messages/read');
    expect(await callCustomer('b1')).toBe('We are calling you now.');
    expect(api.post).toHaveBeenNthCalledWith(3, '/bookings/b1/call');
  });
});
