import { beforeEach, describe, expect, it, vi } from 'vitest';
// The store first: it loads the booking services that the mocks below wrap.
import { store } from '../../state/store';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import BookingsPage from '../BookingsPage';
import { ToastProvider } from '../../components/Toast';
import { setCredentials } from '../../state/authSlice';
import type { Booking, Shop } from '../../types';

const api = vi.hoisted(() => ({
  getShopBookings: vi.fn(),
  updateBookingStatus: vi.fn(),
  cancelBooking: vi.fn(),
}));
vi.mock('../../services/bookingService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/bookingService')>()),
  getShopBookings: api.getShopBookings,
  updateBookingStatus: api.updateBookingStatus,
  cancelBooking: api.cancelBooking,
}));
vi.mock('../../services/shopService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/shopService')>()),
  getServices: vi.fn().mockResolvedValue([]),
  getStaff: vi.fn().mockResolvedValue([]),
}));
vi.mock('../../services/paymentService', () => ({ getBookingPayments: vi.fn().mockResolvedValue([]), confirmCashReceived: vi.fn() }));

const shop = { id: 's1', name: 'Asha Salon', isVerified: true } as Shop;
const today = new Date();
const at = (hours: number) => new Date(today.getFullYear(), today.getMonth(), today.getDate(), hours).toISOString();
const booking = (id: string, scheduledAt: string, status: Booking['status'] = 'PENDING'): Booking => ({
  id, bookingNumber: `BK-${id}`, customerId: 'cust0001', providerId: null, serviceId: 'svc', shopId: 's1', status,
  scheduledAt, durationMinutes: 30, serviceMode: 'AT_SHOP', itemDescription: null, readyBy: null, addressId: null,
  notes: null, totalAmount: 30000, createdAt: '', updatedAt: '',
});
const page = (data: Booking[]) => ({ data, total: data.length, page: 1, perPage: 20, totalPages: 1 });

const renderAt = (path: string) =>
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <BookingsPage />
        </ToastProvider>
      </MemoryRouter>
    </Provider>,
  );

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset());
  store.dispatch(setCredentials({ tokens: { accessToken: 'a', refreshToken: 'r', expiresAt: 0 }, user: { id: 'u', name: 'A', email: null, phone: null, role: 'shop_owner' }, shop }));
});

describe('BookingsPage', () => {
  it('opens on a status from the address (e.g. from the dashboard) and lists today earliest first', async () => {
    api.getShopBookings.mockResolvedValue(page([booking('late', at(17)), booking('early', at(9))]));
    renderAt('/bookings?when=today&status=PENDING');
    const cards = await screen.findAllByRole('article');
    expect(cards.map((c) => c.getAttribute('aria-label'))).toEqual(['Booking #BK-early', 'Booking #BK-late']);
    const filters = api.getShopBookings.mock.calls[0][1];
    expect(filters).toMatchObject({ status: 'PENDING', perPage: 100 });
    expect(filters.dateFrom).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Today' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'To confirm' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('says so when a filter has nothing, with a way back to everything', async () => {
    api.getShopBookings.mockResolvedValue(page([]));
    renderAt('/bookings?when=today');
    expect(await screen.findByText('No bookings today.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Show all bookings' }));
    await waitFor(() => expect(api.getShopBookings).toHaveBeenLastCalledWith('s1', { page: 1 }));
  });

  it('confirms a booking and says it worked', async () => {
    const pending = booking('1', at(11));
    api.getShopBookings.mockResolvedValue(page([pending]));
    api.updateBookingStatus.mockResolvedValue({ ...pending, status: 'CONFIRMED' });
    renderAt('/bookings');
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));
    expect(await screen.findByText('Booking #BK-1 confirmed. The customer has been told.')).toBeInTheDocument();
    expect(screen.getByRole('article')).toHaveTextContent('Confirmed');
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument();
  });

  it('reports a failed step instead of failing silently', async () => {
    api.getShopBookings.mockResolvedValue(page([booking('1', at(11))]));
    api.updateBookingStatus.mockRejectedValue({ response: { data: { detail: 'Booking already cancelled' } } });
    renderAt('/bookings');
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));
    expect(await screen.findByText('Booking already cancelled')).toBeInTheDocument();
  });
});
