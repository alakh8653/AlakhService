import adminApiClient from '../apiClient';

export interface Permission {
  id: string;
  key: string;
  description: string;
  resource: string;
}

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  userCount: number;
}

export async function getRoles(): Promise<Role[]> {
  const { data } = await adminApiClient.get<{ data: Role[] }>('/admin/access/roles');
  return data.data;
}

export async function getPermissions(): Promise<Permission[]> {
  const { data } = await adminApiClient.get<{ data: Permission[] }>('/admin/access/permissions');
  return data.data;
}

export async function updateRolePermissions(roleId: string, permissions: string[]): Promise<Role> {
  const { data } = await adminApiClient.put<{ data: Role }>(`/admin/access/roles/${roleId}/permissions`, { permissions });
  return data.data;
}
