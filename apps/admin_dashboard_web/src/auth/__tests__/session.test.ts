import adminApiClient from '../../apiClient';
import { isSignedIn, signIn, signOut, TOKEN_KEY } from '../session';

vi.mock('../../apiClient', () => ({ default: { post: vi.fn() } }));
const post = vi.mocked(adminApiClient.post);

const jwt = (claims: object) => `h.${btoa(JSON.stringify(claims))}.s`;
const inAnHour = Math.floor(Date.now() / 1000) + 3600;

describe('admin session', () => {
  beforeEach(() => {
    localStorage.clear();
    post.mockReset();
  });

  it('signs in admins by email or phone and keeps their token', async () => {
    const token = jwt({ sub: 'a1', role: 'admin', exp: inAnHour });
    post.mockResolvedValue({ data: { access_token: token } });

    await signIn(' Ops@Example.com ', 'pw');
    expect(post).toHaveBeenCalledWith('/auth/login', { email: 'ops@example.com', password: 'pw' });
    expect(localStorage.getItem(TOKEN_KEY)).toBe(token);
    expect(isSignedIn()).toBe(true);

    await signIn('+919876543210', 'pw');
    expect(post).toHaveBeenLastCalledWith('/auth/login', { phone: '+919876543210', password: 'pw' });

    signOut();
    expect(isSignedIn()).toBe(false);
  });

  it('refuses accounts that are not admins', async () => {
    post.mockResolvedValue({ data: { access_token: jwt({ sub: 'u1', role: 'user', exp: inAnHour }) } });
    await expect(signIn('user@example.com', 'pw')).rejects.toThrow('does not have admin access');
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it('treats an expired or malformed token as signed out', () => {
    localStorage.setItem(TOKEN_KEY, jwt({ sub: 'a1', role: 'admin', exp: 1 }));
    expect(isSignedIn()).toBe(false);
    localStorage.setItem(TOKEN_KEY, 'not-a-jwt');
    expect(isSignedIn()).toBe(false);
  });
});
