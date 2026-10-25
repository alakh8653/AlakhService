import axios from 'axios';
import adminApiClient from '../apiClient';

export const TOKEN_KEY = 'admin_token';

export class SignInError extends Error {}

export class NotAnAdminError extends Error {
  constructor() {
    super('This account does not have admin access.');
  }
}

interface Claims {
  sub?: string;
  role?: string;
  exp?: number;
}

/** Claims of a JWT, without verifying it (the API does that); null if it is not a JWT. */
export function readClaims(token: string | null): Claims | null {
  const payload = token?.split('.')[1];
  if (!payload) return null;
  try {
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/'))) as Claims;
  } catch {
    return null;
  }
}

/** Whether a stored, unexpired admin token is present. */
export function isSignedIn(now: number = Date.now()): boolean {
  const claims = readClaims(localStorage.getItem(TOKEN_KEY));
  return !!claims && claims.role === 'admin' && (claims.exp === undefined || claims.exp * 1000 > now);
}

/** Signs in with an admin account's email or phone and password. Non-admin accounts are refused. */
export async function signIn(identifier: string, password: string): Promise<void> {
  const login = identifier.includes('@') ? { email: identifier.trim().toLowerCase() } : { phone: identifier.trim() };
  let token: string;
  try {
    ({
      data: { access_token: token },
    } = await adminApiClient.post<{ access_token: string }>('/auth/login', { ...login, password }));
  } catch (e) {
    if (!axios.isAxiosError(e)) throw e;
    const detail = (e.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string') return Promise.reject(new SignInError(detail));
    return Promise.reject(new SignInError('Could not sign in. Check your connection and try again.'));
  }
  if (readClaims(token)?.role !== 'admin') throw new NotAnAdminError();
  localStorage.setItem(TOKEN_KEY, token);
}

export function signOut(): void {
  localStorage.removeItem(TOKEN_KEY);
}
