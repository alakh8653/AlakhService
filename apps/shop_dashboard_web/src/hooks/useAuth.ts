import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../state/store';
import { setCredentials, clearAuth, setShop } from '../state/authSlice';
import {
  getCurrentUser,
  login as loginService,
  logout as logoutService,
} from '../services/authService';
import { createShop as createShopService, getShopForOwner, type NewShop } from '../services/shopService';
import type { LoginCredentials } from '../types';

export function useAuth() {
  const dispatch = useDispatch<AppDispatch>();
  const { user, shop, isAuthenticated, isLoading, error, refreshToken } = useSelector(
    (state: RootState) => state.auth,
  );

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const tokens = await loginService(credentials);
      const currentUser = await getCurrentUser(tokens.accessToken);
      // An owner without a shop yet is signed in and taken to shop setup.
      const ownedShop = await getShopForOwner(currentUser.id, tokens.accessToken);
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

  const createShop = useCallback(
    async (details: NewShop) => {
      if (!user) throw new Error('Not signed in');
      const created = await createShopService(user.id, details);
      dispatch(setShop(created));
      return created;
    },
    [dispatch, user],
  );

  return { user, shop, isAuthenticated, isLoading, error, login, logout, createShop };
}
