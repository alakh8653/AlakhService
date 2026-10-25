import adminApiClient from '../apiClient';

export interface Permission {
  key: string;
  resource: string;
  description: string;
}

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  /** Built-in roles cannot be deleted; `admin` cannot be edited. */
  isSystem: boolean;
  userCount: number;
}

interface RoleRecord {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  is_system: boolean;
  user_count: number;
}

const toRole = (r: RoleRecord): Role => ({
  id: r.id,
  name: r.name,
  description: r.description,
  permissions: r.permissions,
  isSystem: r.is_system,
  userCount: r.user_count,
});

export async function getRoles(): Promise<Role[]> {
  const { data } = await adminApiClient.get<RoleRecord[]>('/admin/access/roles');
  return data.map(toRole);
}

export async function getPermissions(): Promise<Permission[]> {
  const { data } = await adminApiClient.get<Permission[]>('/admin/access/permissions');
  return data;
}

export async function updateRolePermissions(roleId: string, permissions: string[]): Promise<Role> {
  const { data } = await adminApiClient.put<RoleRecord>(`/admin/access/roles/${roleId}/permissions`, { permissions });
  return toRole(data);
}

export async function createRole(name: string, description: string, permissions: string[] = []): Promise<Role> {
  const { data } = await adminApiClient.post<RoleRecord>('/admin/access/roles', { name, description, permissions });
  return toRole(data);
}

export async function deleteRole(roleId: string): Promise<void> {
  await adminApiClient.delete(`/admin/access/roles/${roleId}`);
}

export { apiErrorMessage } from '../shared/apiError';
