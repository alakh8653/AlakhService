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

export interface Registration {
  name: string;
  email: string;
  phone?: string;
  password: string;
  /** The Terms and Privacy Policy version the owner ticked; auth_service refuses sign-up without it. */
  acceptedTermsVersion: string;
}

/** Creates an account; the owner then signs in and sets up their shop. */
export async function register(reg: Registration): Promise<User> {
  const { data } = await apiClient.post<UserResponse>('/auth/register', {
    full_name: reg.name.trim(),
    email: reg.email.trim().toLowerCase(),
    ...(reg.phone?.trim() ? { phone: reg.phone.trim() } : {}),
    password: reg.password,
    accepted_terms_version: reg.acceptedTermsVersion,
  });
  return toUser(data);
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
