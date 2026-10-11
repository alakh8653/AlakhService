import adminApiClient from '../apiClient';

export interface Account {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  role: string;
  isActive: boolean;
  isVerified: boolean;
  createdAt: string;
}

interface AccountRecord {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export const toAccount = (r: AccountRecord): Account => ({
  id: r.id,
  name: r.full_name,
  email: r.email,
  phone: r.phone,
  role: r.role,
  isActive: r.is_active,
  isVerified: r.is_verified,
  createdAt: r.created_at,
});

/** Accounts whose name, email or phone contains [query] (auth_service, admins only). */
export async function searchAccounts(query: string, limit = 50): Promise<Account[]> {
  const params: Record<string, string | number> = { limit };
  if (query.trim()) params.q = query.trim();
  const { data } = await adminApiClient.get<AccountRecord[]>('/auth/users', { params });
  return data.map(toAccount);
}

/** Bans an account: it can no longer sign in and its sessions are ended. */
export async function banAccount(userId: string, reason: string): Promise<void> {
  await adminApiClient.post(`/admin/users/${encodeURIComponent(userId)}/ban`, { reason });
}

export async function unbanAccount(userId: string): Promise<void> {
  await adminApiClient.post(`/admin/users/${encodeURIComponent(userId)}/unban`);
}
