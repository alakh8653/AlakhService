import adminApiClient from '../../apiClient';
import { banAccount, searchAccounts, unbanAccount } from '../UserService';

vi.mock('../../apiClient', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
const get = vi.mocked(adminApiClient.get);
const post = vi.mocked(adminApiClient.post);

describe('UserService', () => {
  it('searches auth_service accounts and maps them', async () => {
    get.mockResolvedValue({
      data: [
        {
          id: 'u1',
          full_name: 'Ravi',
          email: 'ravi@example.com',
          phone: null,
          role: 'user',
          is_active: false,
          is_verified: true,
          created_at: '2026-10-01T00:00:00Z',
        },
      ],
    });
    const found = await searchAccounts(' ravi ');
    expect(get).toHaveBeenCalledWith('/auth/users', { params: { limit: 50, q: 'ravi' } });
    expect(found[0]).toMatchObject({ id: 'u1', name: 'Ravi', isActive: false });

    await searchAccounts('');
    expect(get).toHaveBeenLastCalledWith('/auth/users', { params: { limit: 50 } });
  });

  it('bans and unbans through admin_service', async () => {
    post.mockResolvedValue({ data: {} });
    await banAccount('u/1', 'fraud');
    expect(post).toHaveBeenCalledWith('/admin/users/u%2F1/ban', { reason: 'fraud' });
    await unbanAccount('u1');
    expect(post).toHaveBeenLastCalledWith('/admin/users/u1/unban');
  });
});
