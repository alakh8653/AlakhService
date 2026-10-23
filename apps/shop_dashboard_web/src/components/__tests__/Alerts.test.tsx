import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { ToastProvider } from '../Toast';
import NotificationBell from '../NotificationBell';
import { POLL_MS, useNewBookingAlerts } from '../../hooks/useNewBookingAlerts';
import * as bookings from '../../services/bookingService';
import * as notifications from '../../services/notificationService';
import * as sound from '../../services/alertSound';
import type { Booking, PaginatedResponse } from '../../types';

const booking = (id: string, name = 'Ravi S.'): Booking =>
  ({ id, customerDisplayName: name, status: 'PENDING', scheduledAt: '2026-10-25T10:30:00Z' }) as Booking;
const page = (...items: Booking[]): PaginatedResponse<Booking> => ({ data: items, total: items.length, page: 1, perPage: 50, totalPages: 1 });

const wrapper = ({ children }: { children: ReactNode }) => <ToastProvider>{children}</ToastProvider>;

describe('alert sound', () => {
  beforeEach(() => {
    localStorage.clear();
    sound.resetAudioForTests();
  });

  it('stays silent until the browser allows sound, and when muted', () => {
    expect(sound.playChime()).toBe(false); // no user gesture yet: no audio context
    const osc = { type: '', frequency: { value: 0 }, connect: vi.fn(() => ({ connect: vi.fn() })), start: vi.fn(), stop: vi.fn() };
    const gain = { gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() }, connect: vi.fn() };
    osc.connect = vi.fn(() => gain) as never;
    const ctx = { state: 'running', currentTime: 0, destination: {}, createOscillator: () => osc, createGain: () => gain } as unknown as AudioContext;
    sound.resetAudioForTests(ctx);
    expect(sound.playChime()).toBe(true);
    sound.setMuted(true);
    expect(localStorage.getItem('shop_alerts_muted')).toBe('1');
    expect(sound.playChime()).toBe(false);
    sound.setMuted(false);
    expect(sound.playChime()).toBe(true);
  });

  it('creates the audio context only on the first user gesture', () => {
    const created = vi.fn();
    class FakeContext {
      state = 'running';
      constructor() {
        created();
      }
      resume() {
        return Promise.resolve();
      }
    }
    vi.stubGlobal('AudioContext', FakeContext);
    sound.installAudioUnlock();
    expect(created).not.toHaveBeenCalled();
    fireEvent.pointerDown(document);
    fireEvent.keyDown(document, { key: 'a' });
    expect(created).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });
});

describe('useNewBookingAlerts', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
  });
  afterEach(() => vi.useRealTimers());

  it('polls PENDING bookings every 30 s and announces only new ones', async () => {
    const get = vi.spyOn(bookings, 'getShopBookings');
    get.mockResolvedValueOnce(page(booking('b1')));
    const chime = vi.spyOn(sound, 'playChime').mockReturnValue(true);
    const onNew = vi.fn();
    renderHook(() => useNewBookingAlerts('s1', onNew), { wrapper });
    await act(async () => {
      await Promise.resolve();
    });
    expect(get).toHaveBeenCalledWith('s1', { status: 'PENDING', perPage: 50 });
    expect(chime).not.toHaveBeenCalled(); // bookings already waiting are not announced

    get.mockResolvedValueOnce(page(booking('b1'), booking('b2', 'Priya K.')));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(screen.getByText(/New booking from Priya K\./)).toBeInTheDocument();
    expect(chime).toHaveBeenCalledTimes(1);
    expect(onNew).toHaveBeenCalledTimes(1);

    // A failed check is quiet, and the next one carries on.
    get.mockRejectedValueOnce(new Error('offline'));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    get.mockResolvedValueOnce(page(booking('b1'), booking('b2'), booking('b3'), booking('b4')));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(screen.getByText('2 new bookings are waiting for you to confirm.')).toBeInTheDocument();
    expect(chime).toHaveBeenCalledTimes(2);
  });

  it('does nothing without a shop', () => {
    const get = vi.spyOn(bookings, 'getShopBookings');
    renderHook(() => useNewBookingAlerts(undefined), { wrapper });
    expect(get).not.toHaveBeenCalled();
  });
});

describe('NotificationBell', () => {
  beforeEach(() => vi.restoreAllMocks());

  const renderBell = () =>
    render(
      <MemoryRouter>
        <NotificationBell />
      </MemoryRouter>,
    );

  it('shows the unread count and the latest notifications, and marks them read', async () => {
    vi.spyOn(notifications, 'getUnreadCount').mockResolvedValue(2);
    vi.spyOn(notifications, 'getNotifications').mockResolvedValue([
      { id: 'n1', title: 'New booking', body: 'Haircut at 10:30', isRead: false, createdAt: new Date().toISOString(), data: { booking_id: 'b1' } },
      { id: 'n2', title: 'Payment received', body: '₹500', isRead: false, createdAt: new Date().toISOString(), data: null },
    ]);
    const read = vi.spyOn(notifications, 'markRead').mockResolvedValue();
    const readAll = vi.spyOn(notifications, 'markAllRead').mockResolvedValue();
    renderBell();
    const bell = await screen.findByRole('button', { name: 'Notifications, 2 unread' });
    fireEvent.click(bell);
    expect(bell).toHaveAttribute('aria-expanded', 'true');
    const panel = screen.getByRole('region', { name: 'Notifications' });
    fireEvent.click(await within(panel).findByRole('button', { name: /Payment received/ }));
    expect(read).toHaveBeenCalledWith('n2');
    expect(screen.getByRole('button', { name: 'Notifications, 1 unread' })).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: 'Mark all as read' }));
    await waitFor(() => expect(readAll).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('region', { name: 'Notifications' })).not.toBeInTheDocument();
  });

  it('copes with the notification service being down', async () => {
    vi.spyOn(notifications, 'getUnreadCount').mockRejectedValue(new Error('down'));
    vi.spyOn(notifications, 'getNotifications').mockRejectedValue(new Error('down'));
    renderBell();
    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load notifications.');
  });
});
