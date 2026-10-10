import apiClient from './apiClient';
import { toAuthTokens, type TokenResponse } from './tokens';
import type { AuthTokens, LoginCredentials, User } from '../types';

interface UserResponse {
  id: string;
  email: string | null;
  phone: string | null;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  role: string;
}

export function toUser(data: UserResponse): User {
  return {
    id: data.id,
    name: data.full_name,
    email: data.email,
    phone: data.phone,
    role: data.role,
  };
}

export async function login(credentials: LoginCredentials): Promise<AuthTokens> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', credentials);
  return toAuthTokens(data);
}

export async function logout(refreshToken: string, accessToken?: string): Promise<void> {
  await apiClient.post(
    '/auth/logout',
    { refresh_token: refreshToken },
    { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined },
  );
}

/** Fetches the signed-in user. Pass a token to call before it is stored. */
export async function getCurrentUser(accessToken?: string): Promise<User> {
  const { data } = await apiClient.get<UserResponse>('/auth/me', {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });
  return toUser(data);
}

export async function requestPasswordReset(email: string): Promise<void> {
  await apiClient.post('/auth/forgot-password', { email });
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await apiClient.post('/auth/reset-password', { token, new_password: newPassword });
}
