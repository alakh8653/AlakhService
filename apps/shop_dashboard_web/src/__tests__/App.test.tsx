import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { store } from '../state/store';
import { clearAuth, setCredentials } from '../state/authSlice';
import { REFRESH_KEY } from '../services/refreshToken';
import type { Shop, User } from '../types';

const restoreSession = vi.fn();
vi.mock('../services/session', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/session')>()),
  restoreSession: (token: string) => restoreSession(token),
}));

const user: User = { id: 'u1', name: 'Asha', email: 'asha@example.com', phone: null, role: 'shop_owner' };
const shop: Shop = {
  id: 's1', ownerId: 'u1', name: 'Asha Salon', category: 'salon', description: null, city: 'Pune', address: null,
  phone: null, email: null, latitude: null, longitude: null, ratingAvg: 0, ratingCount: 0, isActive: true,
  isVerified: true, createdAt: '2026-01-01T00:00:00Z',
};
const tokens = { accessToken: 'a', refreshToken: 'r1', expiresAt: Date.now() + 60_000 };

const renderAt = (path: string) =>
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </Provider>,
  );

beforeEach(() => {
  store.dispatch(clearAuth());
  localStorage.clear();
  restoreSession.mockReset();
});

describe('App routing', () => {
  it('shows a 404 page with a way back for an unknown signed-in address', () => {
    store.dispatch(setCredentials({ tokens, user, shop }));
    renderAt('/no-such-page');
    expect(screen.getByRole('heading', { name: 'This page does not exist' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to dashboard' })).toHaveAttribute('href', '/dashboard');
  });

  it('remembers the refresh token so a reload keeps the owner signed in', () => {
    store.dispatch(setCredentials({ tokens, user, shop }));
    expect(localStorage.getItem(REFRESH_KEY)).toBe('r1');
    store.dispatch(clearAuth());
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('signs back in after a reload and stays on the same page', async () => {
    localStorage.setItem(REFRESH_KEY, 'stored');
    restoreSession.mockResolvedValue({ tokens: { ...tokens, refreshToken: 'rotated' }, user, shop });
    renderAt('/no-such-page');
    expect(screen.getByText('Signing you in…')).toBeInTheDocument();
    expect(await screen.findByText('This page does not exist')).toBeInTheDocument();
    expect(restoreSession).toHaveBeenCalledWith('stored');
    expect(localStorage.getItem(REFRESH_KEY)).toBe('rotated');
  });

  it('falls back to the sign-in page when the stored session has expired', async () => {
    localStorage.setItem(REFRESH_KEY, 'expired');
    restoreSession.mockRejectedValue(new Error('401'));
    renderAt('/bookings');
    expect(await screen.findByRole('heading', { name: 'Sign in to your shop' })).toBeInTheDocument();
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('opens and closes the phone menu', () => {
    store.dispatch(setCredentials({ tokens, user, shop }));
    renderAt('/no-such-page');
    const toggle = screen.getByRole('button', { name: 'Open menu' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('gives the sign-out button an accessible name', () => {
    store.dispatch(setCredentials({ tokens, user, shop }));
    renderAt('/no-such-page');
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
  });
});

describe('LoginPage', () => {
  it('labels its fields and can reveal the password', async () => {
    renderAt('/login');
    const password = screen.getByLabelText('Password');
    expect(screen.getByLabelText('Email')).toHaveAttribute('autocomplete', 'username');
    expect(password).toHaveAttribute('type', 'password');
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(screen.getByText('Enter a valid email address')).toBeInTheDocument());
  });
});

describe('Signed-in layout', () => {
  it('links to Earnings & Payouts and Verification, the legal pages, and has a mute toggle', () => {
    store.dispatch(setCredentials({ tokens, user, shop }));
    renderAt('/no-such-page');
    expect(screen.getByRole('link', { name: 'Earnings & Payouts' })).toHaveAttribute('href', '/earnings');
    expect(screen.getByRole('link', { name: 'Verification' })).toHaveAttribute('href', '/onboarding');
    const legal = screen.getByRole('navigation', { name: 'Legal' });
    expect(legal.querySelector('a[href$="/terms"]')).not.toBeNull();
    expect(legal.querySelector('a[href$="/grievance"]')).not.toBeNull();
    const mute = screen.getByRole('button', { name: 'Mute new booking sound' });
    expect(mute).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(mute);
    expect(mute).toHaveAttribute('aria-pressed', 'true');
    expect(localStorage.getItem('shop_alerts_muted')).toBe('1');
    fireEvent.click(mute);
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument();
    // An approved shop gets no verification banner.
    expect(screen.queryByText(/not visible to customers yet/)).not.toBeInTheDocument();
  });

  it('shows the verification banner while the shop waits for review', () => {
    store.dispatch(setCredentials({ tokens, user, shop: { ...shop, isVerified: false, verificationStatus: 'PENDING_REVIEW' } }));
    renderAt('/no-such-page');
    expect(screen.getByText(/not visible to customers yet/)).toBeInTheDocument();
    expect(screen.getByText('Pending verification')).toBeInTheDocument();
  });
});
