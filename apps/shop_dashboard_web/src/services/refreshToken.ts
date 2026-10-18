/**
 * Keeps the owner signed in across a page reload (or a phone's pull-to-refresh). Only the refresh
 * token is kept; a fresh access token, the user and their shop are fetched when the app starts.
 */
export const REFRESH_KEY = 'shop_refresh_token';

export function storedRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function rememberRefreshToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    // Storage blocked (private mode): the owner simply signs in again after a reload.
  }
}
