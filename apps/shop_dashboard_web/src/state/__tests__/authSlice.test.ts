import reducer, { clearAuth, setCredentials, setError, setLoading } from '../authSlice';
import type { AuthTokens, User } from '../../types';

const user: User = { id: 'u1', name: 'Asha', email: 'asha@example.com', role: 'owner', shopId: 's1' };
const tokens: AuthTokens = { accessToken: 'access', refreshToken: 'refresh', expiresAt: 1_700_000_000_000 };

describe('authSlice', () => {
  it('starts unauthenticated', () => {
    const state = reducer(undefined, { type: '@@INIT' });
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it('stores credentials on login', () => {
    const state = reducer(undefined, setCredentials({ tokens, user }));
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual(user);
    expect(state.accessToken).toBe('access');
    expect(state.expiresAt).toBe(tokens.expiresAt);
  });

  it('clears loading when an error is set', () => {
    const loading = reducer(undefined, setLoading(true));
    const state = reducer(loading, setError('Invalid credentials'));
    expect(state.isLoading).toBe(false);
    expect(state.error).toBe('Invalid credentials');
  });

  it('resets everything on logout', () => {
    const loggedIn = reducer(undefined, setCredentials({ tokens, user }));
    const state = reducer(loggedIn, clearAuth());
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
  });
});
