import apiClient from './apiClient';
import type { ApiResponse, AuthTokens, LoginCredentials, User } from '../types';

export interface LoginResponse {
  tokens: AuthTokens;
  user: User;
}

export async function login(credentials: LoginCredentials): Promise<LoginResponse> {
  const { data } = await apiClient.post<ApiResponse<LoginResponse>>(
    '/auth/login',
    credentials,
  );
  return data.data;
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post('/auth/logout', { refreshToken });
}

export async function refreshAccessToken(refreshToken: string): Promise<AuthTokens> {
  const { data } = await apiClient.post<ApiResponse<AuthTokens>>('/auth/refresh', {
    refreshToken,
  });
  return data.data;
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<ApiResponse<User>>('/auth/me');
  return data.data;
}

export async function requestPasswordReset(email: string): Promise<void> {
  await apiClient.post('/auth/password-reset', { email });
}

export async function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<void> {
  await apiClient.post('/auth/password-reset/confirm', { token, newPassword });
}
