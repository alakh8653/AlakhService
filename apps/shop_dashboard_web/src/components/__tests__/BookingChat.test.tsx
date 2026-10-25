import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import BookingChat from '../BookingChat';
import * as chat from '../../services/chatService';
import type { ChatMessage, ChatPage } from '../../services/chatService';

vi.mock('../../services/chatService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/chatService')>()),
  getMessages: vi.fn(),
  sendMessage: vi.fn(),
  markRead: vi.fn(),
  callCustomer: vi.fn(),
}));

const api = vi.mocked(chat);

const message = (over: Partial<ChatMessage> = {}): ChatMessage => ({
  id: 'm1',
  senderRole: 'customer',
  senderName: 'Ravi S.',
  isMine: false,
  body: 'Is 10 fine?',
  flagged: false,
  createdAt: '2026-10-19T10:00:00Z',
  readAt: null,
  ...over,
});

const page = (over: Partial<ChatPage> = {}): ChatPage => ({
  messages: [message()],
  total: 1,
  unread: 1,
  canSend: true,
  openUntil: null,
  callingEnabled: false,
  ...over,
});

describe('BookingChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.markRead.mockResolvedValue(1);
  });

  it('shows the conversation, marks it read and sends a reply', async () => {
    api.getMessages.mockResolvedValue(page());
    api.sendMessage.mockResolvedValue(message({ id: 'm2', isMine: true, senderRole: 'shop', senderName: 'Shop', body: 'Yes' }));
    render(<BookingChat bookingId="b1" customerName="Ravi S." />);

    expect(await screen.findByText('Is 10 fine?')).toBeInTheDocument();
    expect(screen.getByText('Ravi S.')).toBeInTheDocument();
    expect(api.markRead).toHaveBeenCalledWith('b1');
    // Calling is off: only the chat is offered.
    expect(screen.queryByRole('button', { name: /Call customer/ })).not.toBeInTheDocument();

    const box = screen.getByLabelText('Message Ravi S.');
    expect(box).toHaveAttribute('maxLength', '1000');
    fireEvent.change(box, { target: { value: 'Yes' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText('Yes')).toBeInTheDocument();
    expect(api.sendMessage).toHaveBeenCalledWith('b1', 'Yes');
    expect(screen.getByText(/· Sent/)).toBeInTheDocument();
  });

  it('explains when contact details were hidden', async () => {
    api.getMessages.mockResolvedValue(page({ messages: [], total: 0, unread: 0 }));
    api.sendMessage.mockResolvedValue(message({ id: 'm2', isMine: true, body: 'call [hidden for your safety]', flagged: true }));
    render(<BookingChat bookingId="b1" customerName="Ravi S." />);
    expect(await screen.findByText('No messages yet.')).toBeInTheDocument();
    expect(api.markRead).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Message Ravi S.'), { target: { value: 'call 9876543210' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText('call [hidden for your safety]')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Contact details were hidden.');
  });

  it('is read-only once the booking has closed', async () => {
    api.getMessages.mockResolvedValue(page({ canSend: false, unread: 0 }));
    render(<BookingChat bookingId="b1" customerName="Ravi S." />);
    expect(await screen.findByText('This booking is closed, so its chat is read-only.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Message Ravi S.')).not.toBeInTheDocument();
  });

  it('offers a masked call when the platform has calling enabled', async () => {
    api.getMessages.mockResolvedValue(page({ callingEnabled: true }));
    api.callCustomer.mockResolvedValue("We're calling you now.");
    render(<BookingChat bookingId="b1" customerName="Ravi S." />);
    fireEvent.click(await screen.findByRole('button', { name: /Call customer/ }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent("We're calling you now."));
    expect(api.callCustomer).toHaveBeenCalledWith('b1');
  });

  it('shows why a message could not be sent', async () => {
    api.getMessages.mockResolvedValue(page());
    api.sendMessage.mockRejectedValue({ response: { data: { detail: "You're sending messages too quickly." } } });
    render(<BookingChat bookingId="b1" customerName="Ravi S." />);
    fireEvent.change(await screen.findByLabelText('Message Ravi S.'), { target: { value: 'hi' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByRole('status')).toHaveTextContent("You're sending messages too quickly.");
  });

  it('reports a failed load', async () => {
    api.getMessages.mockRejectedValue(new Error('Network Error'));
    render(<BookingChat bookingId="b1" customerName="Ravi S." />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Network Error');
  });
});
