import type { AuthTokens } from '../types';

/** auth_service's token response. */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number; // seconds
}

export function toAuthTokens(data: TokenResponse, now = Date.now()): AuthTokens {
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: now + data.expires_in * 1000,
  };
}
