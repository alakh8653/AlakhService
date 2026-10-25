import reducer, { clearAuth, setCredentials, setError, setLoading, setShop } from '../authSlice';
import type { AuthTokens, Shop, User } from '../../types';

const user: User = { id: 'u1', name: 'Asha', email: 'asha@example.com', phone: null, role: 'customer' };
const shop: Shop = {
  id: 's1',
  ownerId: 'u1',
  name: 'Asha Salon',
  category: 'salon',
  description: null,
  city: 'Pune',
  address: null,
  phone: null,
  email: null,
  latitude: null,
  longitude: null,
  ratingAvg: 4.5,
  ratingCount: 10,
  isActive: true,
  isVerified: true,
  createdAt: '2026-01-01T00:00:00Z',
};
const tokens: AuthTokens = { accessToken: 'access', refreshToken: 'refresh', expiresAt: 1_700_000_000_000 };

describe('authSlice', () => {
  it('starts unauthenticated', () => {
    const state = reducer(undefined, { type: '@@INIT' });
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it('stores credentials on login', () => {
    const state = reducer(undefined, setCredentials({ tokens, user, shop }));
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual(user);
    expect(state.accessToken).toBe('access');
    expect(state.expiresAt).toBe(tokens.expiresAt);
    expect(state.shop).toEqual(shop);
  });

  it('replaces the shop after settings are saved', () => {
    const loggedIn = reducer(undefined, setCredentials({ tokens, user, shop }));
    const state = reducer(loggedIn, setShop({ ...shop, name: 'Renamed' }));
    expect(state.shop?.name).toBe('Renamed');
  });

  it('clears loading when an error is set', () => {
    const loading = reducer(undefined, setLoading(true));
    const state = reducer(loading, setError('Invalid credentials'));
    expect(state.isLoading).toBe(false);
    expect(state.error).toBe('Invalid credentials');
  });

  it('resets everything on logout', () => {
    const loggedIn = reducer(undefined, setCredentials({ tokens, user, shop }));
    const state = reducer(loggedIn, clearAuth());
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.shop).toBeNull();
  });

  it('signs in an owner who has not set up a shop yet, then adds the shop', () => {
    let state = reducer(undefined, setCredentials({ tokens, user, shop: null }));
    expect(state.isAuthenticated).toBe(true);
    expect(state.shop).toBeNull();
    state = reducer(state, setShop(shop));
    expect(state.shop?.id).toBe('s1');
  });
});
