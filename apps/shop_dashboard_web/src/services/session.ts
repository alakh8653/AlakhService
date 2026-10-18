import apiClient from './apiClient';
import { toAuthTokens, type TokenResponse } from './tokens';
import { getCurrentUser } from './authService';
import { getShopForOwner } from './shopService';
import type { AuthTokens, Shop, User } from '../types';

export { REFRESH_KEY, rememberRefreshToken, storedRefreshToken } from './refreshToken';

export interface RestoredSession {
  tokens: AuthTokens;
  user: User;
  shop: Shop | null;
}

let inFlight: Promise<RestoredSession> | null = null;

/** Signs back in with the stored refresh token. Concurrent callers share one attempt. */
export function restoreSession(refreshToken: string): Promise<RestoredSession> {
  inFlight ??= (async () => {
    try {
      const { data } = await apiClient.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken });
      const tokens = toAuthTokens(data);
      const user = await getCurrentUser(tokens.accessToken);
      const shop = await getShopForOwner(user.id, tokens.accessToken);
      return { tokens, user, shop };
    } finally {
      inFlight = null;
    }
  })();
  return inFlight;
}
