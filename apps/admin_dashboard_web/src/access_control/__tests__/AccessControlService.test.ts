import adminApiClient from '../../apiClient';
import { apiErrorMessage, getRoles, updateRolePermissions } from '../AccessControlService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }));

const record = { id: 'role-support', name: 'support', description: 'Support', permissions: ['users:read'], is_system: true, user_count: 2 };

describe('AccessControlService', () => {
  it('maps roles', async () => {
    vi.mocked(adminApiClient.get).mockResolvedValue({ data: [record] });
    expect(await getRoles()).toEqual([
      { id: 'role-support', name: 'support', description: 'Support', permissions: ['users:read'], isSystem: true, userCount: 2 },
    ]);
  });

  it('sends the full permission list when updating a role', async () => {
    vi.mocked(adminApiClient.put).mockResolvedValue({ data: { ...record, permissions: ['audit:read'] } });
    const role = await updateRolePermissions('role-support', ['audit:read']);
    expect(adminApiClient.put).toHaveBeenCalledWith('/admin/access/roles/role-support/permissions', { permissions: ['audit:read'] });
    expect(role.permissions).toEqual(['audit:read']);
  });

  it('surfaces the API error detail', () => {
    expect(apiErrorMessage({ response: { data: { detail: "Role 'x' already exists" } } }, 'fallback')).toBe("Role 'x' already exists");
    expect(apiErrorMessage(new Error('network'), 'fallback')).toBe('fallback');
  });
});
