import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from '../state/store';
import { setCredentials, clearAuth } from '../state/authSlice';
import { login as loginService, logout as logoutService } from '../services/authService';
import type { LoginCredentials } from '../types';

export function useAuth() {
  const dispatch = useDispatch<AppDispatch>();
  const { user, isAuthenticated, isLoading, error, refreshToken } = useSelector(
    (state: RootState) => state.auth,
  );

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const result = await loginService(credentials);
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

  return { user, isAuthenticated, isLoading, error, login, logout };
}
