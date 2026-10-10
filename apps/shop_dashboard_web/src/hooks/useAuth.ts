import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../state/store';
import { setCredentials, clearAuth } from '../state/authSlice';
import {
  getCurrentUser,
  login as loginService,
  logout as logoutService,
} from '../services/authService';
import { getShopForOwner } from '../services/shopService';
import type { LoginCredentials } from '../types';

export class NoShopError extends Error {
  constructor() {
    super('This account does not own a shop yet.');
    this.name = 'NoShopError';
  }
}

export function useAuth() {
  const dispatch = useDispatch<AppDispatch>();
  const { user, shop, isAuthenticated, isLoading, error, refreshToken } = useSelector(
    (state: RootState) => state.auth,
  );

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const tokens = await loginService(credentials);
      const currentUser = await getCurrentUser(tokens.accessToken);
      const ownedShop = await getShopForOwner(currentUser.id, tokens.accessToken);
      if (!ownedShop) {
        try {
          await logoutService(tokens.refreshToken, tokens.accessToken);
        } catch {
          // best-effort: the session simply expires
        }
        throw new NoShopError();
      }
      const result = { tokens, user: currentUser, shop: ownedShop };
      dispatch(setCredentials(result));
      return result;
    },
    [dispatch],
  );

  const logout = useCallback(async () => {
    if (refreshToken) {
      try {
        await logoutService(refreshToken);
      } catch {
        // best-effort server logout
      }
    }
    dispatch(clearAuth());
  }, [dispatch, refreshToken]);

  return { user, shop, isAuthenticated, isLoading, error, login, logout };
}
