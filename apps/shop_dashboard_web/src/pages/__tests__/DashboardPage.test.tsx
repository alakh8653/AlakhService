import { beforeEach, describe, expect, it, vi } from 'vitest';
// The store first: it loads the booking services that the mocks below wrap.
import { store } from '../../state/store';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '../DashboardPage';
import AnalyticsPage from '../AnalyticsPage';
import { ToastProvider } from '../../components/Toast';
import { setCredentials } from '../../state/authSlice';
import type { Booking, Shop } from '../../types';

vi.mock('recharts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const api = vi.hoisted(() => ({
  getShopBookings: vi.fn(),
  getShopSummary: vi.fn(),
  getServices: vi.fn(),
  getStaff: vi.fn(),
  getReviewSummary: vi.fn(),
  getReviews: vi.fn(),
  getShopHours: vi.fn(),
}));
vi.mock('../../services/reviewService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/reviewService')>()),
  getReviewSummary: api.getReviewSummary,
  getReviews: api.getReviews,
}));
vi.mock('../../services/bookingService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/bookingService')>()),
  getShopBookings: api.getShopBookings,
  getShopSummary: api.getShopSummary,
}));
vi.mock('../../services/shopService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/shopService')>()),
  getServices: api.getServices,
  getStaff: api.getStaff,
  getShopHours: api.getShopHours,
}));
vi.mock('../../services/paymentService', () => ({ getBookingPayments: vi.fn().mockResolvedValue([]), confirmCashReceived: vi.fn() }));

const shop = { id: 's1', name: 'Asha Salon', isVerified: true, latitude: null, ratingAvg: 0, ratingCount: 0 } as unknown as Shop;
const now = new Date();
const at = (hours: number) => new Date(now.getFullYear(), now.getMonth(), now.getDate(), hours).toISOString();
const booking = (id: string, scheduledAt: string): Booking => ({
  id, bookingNumber: `BK-${id}`, customerId: 'cust0001', customerDisplayName: 'Ravi S.', providerId: null, serviceId: 'svc', shopId: 's1', status: 'CONFIRMED',
  scheduledAt, durationMinutes: 30, serviceMode: 'AT_SHOP', itemDescription: null, readyBy: null, addressId: null,
  notes: null, totalAmount: 30000, createdAt: '', updatedAt: '',
});
const summary = (from = '2026-10-01', to = '2026-10-18') => ({
  dateFrom: from, dateTo: to, totalBookings: 4, totalRevenue: 459900, uniqueCustomers: 2,
  bookingsByStatus: { COMPLETED: 2, PENDING: 2 }, revenueByDay: [], topServices: [],
});

const renderPage = (page: React.ReactNode) =>
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ToastProvider>{page}</ToastProvider>
      </MemoryRouter>
    </Provider>,
  );

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset());
  api.getShopSummary.mockResolvedValue(summary());
  api.getReviewSummary.mockResolvedValue({ averageRating: 0, reviewCount: 0, distribution: [] });
  api.getReviews.mockResolvedValue({ items: [], total: 0 });
  api.getShopHours.mockResolvedValue({ configured: true });
  store.dispatch(setCredentials({ tokens: { accessToken: 'a', refreshToken: 'r', expiresAt: 0 }, user: { id: 'u', name: 'Asha Rao', email: null, phone: null, role: 'shop_owner' }, shop }));
});

describe('DashboardPage', () => {
  it("leads with today's bookings, earliest first, and what needs confirming", async () => {
    api.getShopBookings.mockImplementation((_shop: string, filters: { status?: string }) =>
      Promise.resolve(
        filters.status === 'PENDING'
          ? { data: [], total: 3, page: 1, perPage: 1, totalPages: 3 }
          : { data: [booking('pm', at(16)), booking('am', at(9))], total: 2, page: 1, perPage: 100, totalPages: 1 },
      ),
    );
    api.getServices.mockResolvedValue([{ id: 'svc', name: 'Haircut' }]);
    api.getStaff.mockResolvedValue([{ id: 'st', name: 'Ravi', userId: null, isActive: true }]);
    renderPage(<DashboardPage />);

    const cards = await screen.findAllByRole('article');
    expect(cards.map((c) => c.getAttribute('aria-label'))).toEqual(['Booking #BK-am', 'Booking #BK-pm']);
    expect(screen.getByRole('heading', { name: 'Today · 2 to go' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /3 bookings are waiting for you to confirm/ })).toHaveAttribute('href', '/bookings?status=PENDING');
    expect(screen.getByRole('heading', { name: /, Asha$/ })).toBeInTheDocument();
    // Services and staff exist; only the map pin is left to do.
    expect(await screen.findByRole('link', { name: 'Pin your shop on the map so customers find you' })).toHaveAttribute('href', '/settings');
    expect(screen.queryByRole('link', { name: /Add the services/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Set opening hours/ })).not.toBeInTheDocument(); // already published
  });

  it('walks a new shop through setup and says when today is empty', async () => {
    api.getShopBookings.mockResolvedValue({ data: [], total: 0, page: 1, perPage: 100, totalPages: 0 });
    api.getServices.mockResolvedValue([]);
    api.getStaff.mockResolvedValue([]);
    api.getShopHours.mockResolvedValue({ configured: false });
    renderPage(<DashboardPage />);
    expect(await screen.findByText('No bookings today.')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Add the services you offer, with prices' })).toHaveAttribute('href', '/services');
    expect(screen.getByRole('link', { name: "Set opening hours so customers book only when you're open" })).toHaveAttribute('href', '/hours');
    expect(screen.getByText('No reviews yet')).toBeInTheDocument();
    expect(screen.queryByText(/waiting for you to confirm/)).not.toBeInTheDocument();
  });

  it('shows the live rating and how many reviews need a reply, linking to Reviews', async () => {
    api.getShopBookings.mockResolvedValue({ data: [], total: 0, page: 1, perPage: 100, totalPages: 0 });
    api.getServices.mockResolvedValue([]);
    api.getStaff.mockResolvedValue([]);
    api.getReviewSummary.mockResolvedValue({ averageRating: 4.6, reviewCount: 128, distribution: [] });
    api.getReviews.mockResolvedValue({ items: [], total: 3 });
    renderPage(<DashboardPage />);

    const card = await screen.findByRole('link', { name: /4\.6 ★/ });
    expect(card).toHaveAttribute('href', '/reviews');
    expect(card).toHaveTextContent('128 reviews · 3 to reply to');
    expect(api.getReviews).toHaveBeenCalledWith('s1', { needsReply: true, limit: 1 });
  });
});

describe('AnalyticsPage', () => {
  it('switches period and shows the average bill', async () => {
    api.getServices.mockResolvedValue([]);
    renderPage(<AnalyticsPage />);
    expect(await screen.findByText('₹2,299.50')).toBeInTheDocument(); // ₹4,599 over 2 completed
    fireEvent.click(screen.getByRole('button', { name: '7 days' }));
    await waitFor(() => expect(api.getShopSummary).toHaveBeenCalledTimes(2));
    const [, from, to] = api.getShopSummary.mock.calls[1];
    expect((new Date(to).getTime() - new Date(from).getTime()) / 86_400_000).toBe(6);
    expect(screen.getByRole('button', { name: '7 days' })).toHaveAttribute('aria-pressed', 'true');
  });
});
