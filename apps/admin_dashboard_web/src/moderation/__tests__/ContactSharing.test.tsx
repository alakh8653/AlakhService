import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import adminApiClient from '../../apiClient';
import ContactSharingPage from '../ContactSharingPage';
import * as service from '../ChatModerationService';

vi.mock('../../users/accountNames', () => ({
  useAccounts: () => ({ 'user-1': { id: 'user-1', name: 'Ravi Kumar', email: null, phone: null } }),
}));

const flagged: service.FlaggedMessage = {
  id: 'm1',
  bookingId: 'booking-123456789',
  senderId: 'user-1',
  senderRole: 'customer',
  body: 'call [hidden for your safety]',
  originalBody: 'call 9876543210',
  reasons: ['phone'],
  createdAt: '2026-10-19T09:00:00Z',
};

describe('ChatModerationService', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('reads flagged messages and repeat offenders through /admin/chat', async () => {
    const get = vi.spyOn(adminApiClient, 'get');
    get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 'm1', booking_id: 'b1', sender_id: 'u1', sender_role: 'shop', body: 'x', original_body: 'y',
            flag_reasons: ['email'], created_at: '2026-10-19T09:00:00Z',
          },
        ],
        total: 30,
      },
    });
    const page = await service.getFlaggedMessages({ senderId: 'u1', page: 2 });
    expect(get).toHaveBeenLastCalledWith('/admin/chat/flagged', { params: { sender_id: 'u1', skip: 25, limit: 25 } });
    expect(page).toEqual({
      data: [{ id: 'm1', bookingId: 'b1', senderId: 'u1', senderRole: 'shop', body: 'x', originalBody: 'y', reasons: ['email'], createdAt: '2026-10-19T09:00:00Z' }],
      total: 30,
    });

    get.mockResolvedValueOnce({
      data: { min_attempts: 2, items: [{ user_id: 'u1', sender_role: 'customer', attempts: 4, bookings: 2, last_attempt_at: '2026-10-19T09:00:00Z' }] },
    });
    expect(await service.getRepeatOffenders()).toEqual([
      { id: 'u1', userId: 'u1', senderRole: 'customer', attempts: 4, bookings: 2, lastAttemptAt: '2026-10-19T09:00:00Z' },
    ]);
    expect(get).toHaveBeenLastCalledWith('/admin/chat/repeat-offenders', { params: { min_attempts: 2, days: 30 } });
    expect(service.reasonLabel('upi')).toBe('UPI handle');
  });
});

describe('ContactSharingPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(service, 'getRepeatOffenders').mockResolvedValue([
      { id: 'user-1', userId: 'user-1', senderRole: 'customer', attempts: 3, bookings: 2, lastAttemptAt: '2026-10-19T09:00:00Z' },
    ]);
  });

  it('lists repeat offenders and what they tried to share, filtering by person', async () => {
    const messages = vi.spyOn(service, 'getFlaggedMessages').mockResolvedValue({ data: [flagged], total: 1 });
    render(<ContactSharingPage />);

    const offenders = await screen.findByRole('table', { name: 'Repeated attempts' });
    expect(await within(offenders).findByText('3')).toBeInTheDocument();
    const table = screen.getByRole('table', { name: 'Flagged messages' });
    expect(await within(table).findByText('call 9876543210')).toBeInTheDocument();
    expect(within(table).getByText('Phone number')).toBeInTheDocument();

    fireEvent.click(within(offenders).getByRole('row', { name: 'Show messages from Ravi Kumar' }));
    await waitFor(() => expect(messages).toHaveBeenLastCalledWith({ senderId: 'user-1', page: 1, perPage: 25 }));
    expect(screen.getByRole('heading', { name: 'Messages from Ravi Kumar' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Show everyone' }));
    await waitFor(() => expect(messages).toHaveBeenLastCalledWith({ senderId: undefined, page: 1, perPage: 25 }));
  });

  it('says when it could not load', async () => {
    vi.spyOn(service, 'getFlaggedMessages').mockRejectedValue(new Error('down'));
    render(<ContactSharingPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load contact-sharing attempts.');
  });
});
