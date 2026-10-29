import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import authReducer, { setShop } from '../../state/authSlice';
import bookingReducer from '../../state/bookingSlice';
import { ToastProvider } from '../../components/Toast';
import LiveLinePage from '../LiveLinePage';
import BoardPage from '../BoardPage';
import * as live from '../../services/liveQueueService';
import * as shops from '../../services/shopService';
import type { Service, Shop } from '../../types';

const shop = { id: 's1', ownerId: 'u1', name: 'Asha Salon', isVerified: true } as Shop;
const haircut = { id: 'svc1', shopId: 's1', categoryId: null, name: 'Haircut', description: null, priceCents: 30000, durationMinutes: 30, isActive: true, createdAt: '' } as Service;

function entry(over: Partial<live.LineEntry>): live.LineEntry {
  return {
    bookingId: 'b1', bookingNumber: 'BK10000001', name: 'Ravi', state: 'WAITING', position: 1,
    scheduledAt: '2030-11-04T05:00:00Z', estimatedStart: '2030-11-04T05:00:00Z', estimatedEnd: '2030-11-04T05:30:00Z',
    etaMin: '2030-11-04T04:55:00Z', etaMax: '2030-11-04T05:10:00Z', confidence: 'HIGH', runningLateMinutes: 0,
    serviceId: 'svc1', source: 'BOOKED', priority: 'APPOINTMENT', checkedIn: false, staffId: 'st-a', staffName: 'Asha',
    reason: null, overrun: false, moved: false, canMarkNoShow: false, ...over,
  };
}

const asha: live.TeamMember = {
  staffId: 'st-a', name: 'Asha', serviceIds: ['svc1'], status: 'AVAILABLE', until: null, servingBookingId: null,
  servingName: null, servingSince: null, servingUntil: null, overrun: false, waiting: 2,
};

/** Stands in for the browser's WebSocket so a test can push frames. */
class FakeSocket {
  static last: FakeSocket | null = null;
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(url: string) {
    this.url = url;
    FakeSocket.last = this;
    setTimeout(() => this.onopen?.(), 0);
  }
  push(frame: unknown) {
    this.onmessage?.({ data: JSON.stringify(frame) });
  }
  close() {
    this.onclose = null;
  }
}

function renderAt(path: string) {
  const store = configureStore({ reducer: { auth: authReducer, bookings: bookingReducer } });
  store.dispatch(setShop(shop));
  render(
    <Provider store={store}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/line" element={<LiveLinePage />} />
            <Route path="/board/:shopId" element={<BoardPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </Provider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal('WebSocket', FakeSocket);
  vi.spyOn(shops, 'getServices').mockResolvedValue([haircut]);
  vi.spyOn(live, 'getTeam').mockResolvedValue([asha]);
  vi.spyOn(live, 'getSettings').mockResolvedValue({ bufferPct: 0, alpha: 0.2, graceMinutes: 10, agingMinutes: 20, checkInRequired: false, vipPerDay: 5 });
});

afterEach(() => vi.unstubAllGlobals());

describe('LiveLinePage', () => {
  it('shows the line with expected times and follows it live', async () => {
    vi.spyOn(live, 'getLine').mockResolvedValue([
      entry({ bookingId: 'b0', name: 'Meena', state: 'IN_PROGRESS', position: null }),
      entry({ bookingId: 'b1', name: 'Ravi', position: 1, runningLateMinutes: 12 }),
      entry({ bookingId: 'b2', name: 'Kiran', position: 2, source: 'WALK_IN', priority: 'WALK_IN', checkedIn: true, staffName: 'Bilal', reason: 'PREFERRED_UNAVAILABLE' }),
    ]);
    renderAt('/line');
    const line = await screen.findByRole('list', { name: 'Customers in line' });
    const ravi = within(line).getByRole('listitem', { name: 'Ravi' });
    expect(within(ravi).getByText('#1')).toBeInTheDocument();
    expect(within(ravi).getByText(/Haircut · Asha ·/)).toBeInTheDocument();
    expect(within(ravi).getByText(/12 min late/)).toBeInTheDocument();
    const kiran = within(line).getByRole('listitem', { name: 'Kiran' });
    expect(within(kiran).getByText('Walk-in')).toBeInTheDocument();
    expect(within(kiran).getByText(/chosen professional is away/)).toBeInTheDocument();
    expect(within(within(line).getByRole('listitem', { name: 'Meena' })).getByText('Now')).toBeInTheDocument();
    expect(screen.getByText('(2 waiting)')).toBeInTheDocument();
    expect(FakeSocket.last?.url).toContain('/ws/shops/s1/queue');

    // The shop's screen gets a new frame: Ravi has started.
    await waitFor(() => expect(screen.getByTestId('live-status')).toHaveTextContent('Live.'));
    act(() =>
      FakeSocket.last!.push({
        type: 'queue',
        entries: [
          { booking_id: 'b1', booking_number: 'BK1', customer_display_name: 'Ravi', state: 'IN_PROGRESS', scheduled_at: '2030-11-04T05:00:00Z', running_late_minutes: 0 },
        ],
      }),
    );
    expect(await screen.findByText('(0 waiting)')).toBeInTheDocument();
  });

  it('runs the line: walk-in, next customer, break, move up, VIP, no-show', async () => {
    vi.spyOn(live, 'getLine').mockResolvedValue([
      entry({ bookingId: 'b1', name: 'Ravi', position: 1 }),
      entry({ bookingId: 'b2', name: 'Kiran', position: 2, canMarkNoShow: true }),
    ]);
    const walk = vi.spyOn(live, 'addWalkIn').mockResolvedValue(entry({ bookingId: 'b3', name: 'Neha', position: 3 }));
    const next = vi.spyOn(live, 'callNext').mockResolvedValue(entry({ state: 'IN_PROGRESS' }));
    const status = vi.spyOn(live, 'setTeamStatus').mockResolvedValue([asha]);
    const move = vi.spyOn(live, 'reorder').mockResolvedValue([]);
    const vip = vi.spyOn(live, 'setVip').mockResolvedValue();
    const noShow = vi.spyOn(live, 'markNoShow').mockResolvedValue();
    renderAt('/line');
    await screen.findByRole('list', { name: 'Customers in line' });

    const form = screen.getByRole('form', { name: 'Add a walk-in' });
    await waitFor(() => expect(within(form).getByRole('option', { name: 'Haircut' })).toBeInTheDocument());
    fireEvent.change(within(form).getByLabelText('Service'), { target: { value: 'svc1' } });
    fireEvent.change(within(form).getByLabelText('Name to call out'), { target: { value: 'Neha' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Add walk-in' }));
    await waitFor(() => expect(walk).toHaveBeenCalledWith('s1', { serviceId: 'svc1', name: 'Neha', vip: false }));
    expect(await screen.findByText('Neha is #3 in line with Asha.')).toBeInTheDocument();

    const team = screen.getByRole('listitem', { name: 'Asha' });
    fireEvent.click(within(team).getByRole('button', { name: 'Next customer' }));
    await waitFor(() => expect(next).toHaveBeenCalledWith('s1', 'st-a'));
    fireEvent.click(within(team).getByRole('button', { name: 'Break 15 min' }));
    await waitFor(() => expect(status).toHaveBeenCalledWith('s1', 'st-a', 'BREAK', 15));

    fireEvent.click(screen.getByRole('button', { name: 'Move Kiran up' }));
    await waitFor(() => expect(move).toHaveBeenCalledWith('s1', ['b2', 'b1']));
    expect(screen.getByRole('button', { name: 'Move Ravi up' })).toBeDisabled();

    const kiran = screen.getByRole('listitem', { name: 'Kiran' });
    fireEvent.click(within(kiran).getByRole('button', { name: 'VIP' }));
    await waitFor(() => expect(vip).toHaveBeenCalledWith('b2', true));
    fireEvent.click(within(kiran).getByRole('button', { name: 'No-show' }));
    await waitFor(() => expect(noShow).toHaveBeenCalledWith('b2'));
    expect(within(screen.getByRole('listitem', { name: 'Ravi' })).queryByRole('button', { name: 'No-show' })).toBeNull();
  });

  it('saves the line settings', async () => {
    vi.spyOn(live, 'getLine').mockResolvedValue([]);
    const save = vi.spyOn(live, 'saveSettings').mockImplementation(async (_s, v) => v);
    renderAt('/line');
    expect(await screen.findByText('Nobody is in line right now.')).toBeInTheDocument();
    const form = await screen.findByRole('form', { name: 'Line settings' });
    fireEvent.change(within(form).getByLabelText(/Grace period/), { target: { value: '15' } });
    fireEvent.click(within(form).getByLabelText(/must check in/));
    fireEvent.click(within(form).getByRole('button', { name: 'Save settings' }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith('s1', { bufferPct: 0, alpha: 0.2, graceMinutes: 15, agingMinutes: 20, checkInRequired: true, vipPerDay: 5 }),
    );
  });
});

describe('BoardPage', () => {
  it('shows who is being served and who is next, masked, and follows the board live', async () => {
    vi.spyOn(live, 'getBoard').mockResolvedValue({
      version: 'v1',
      nowServing: [{ ticket: '0001', name: 'M•••', staffName: 'Asha', waitMinutes: null }],
      next: [{ ticket: '0002', name: 'R•••', staffName: null, waitMinutes: 12 }],
      waiting: 1,
    });
    renderAt('/board/s1');
    const serving = await screen.findByRole('region', { name: 'Now serving' });
    expect(within(serving).getByText('M•••')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Next' })).getByText('~12 min')).toBeInTheDocument();
    expect(FakeSocket.last?.url).toMatch(/\/ws\/shops\/s1\/board$/);
    act(() => FakeSocket.last!.push({ type: 'board', version: 'v2', now_serving: [], next: [], waiting: 0 }));
    expect(await screen.findByText('Nobody is waiting.')).toBeInTheDocument();
  });
});
