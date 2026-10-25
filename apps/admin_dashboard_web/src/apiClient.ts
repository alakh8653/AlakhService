import axios from 'axios';

// Falls back to the local API gateway (see .env.example) when the variable is not set.
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:3000/api/v1';

const adminApiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
});

adminApiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) config.headers.set('Authorization', `Bearer ${token}`);
  return config;
});

// Fail loudly when the API is unreachable or misconfigured (e.g. an SPA fallback page served instead of JSON),
// so callers hit their error path instead of rendering `undefined` data.
adminApiClient.interceptors.response.use(
  (response) => {
    const contentType = String(response.headers['content-type'] ?? '');
    if (response.status !== 204 && !contentType.includes('application/json')) {
      return Promise.reject(new Error(`Unexpected response type "${contentType}" from ${response.config.url}`));
    }
    return response;
  },
  (error: unknown) => {
    // An expired or revoked session: back to the sign-in page (a failed sign-in is handled by the form).
    const status = (error as { response?: { status?: number } }).response?.status;
    const url = (error as { config?: { url?: string } }).config?.url ?? '';
    if (status === 401 && !url.endsWith('/auth/login') && localStorage.getItem('admin_token')) {
      localStorage.removeItem('admin_token');
      window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);

export default adminApiClient;

/** Id (`sub` claim) of the signed-in admin, read from the stored access token. */
export function currentAdminId(): string | null {
  const token = localStorage.getItem('admin_token');
  const payload = token?.split('.')[1];
  if (!payload) return null;
  try {
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    const sub: unknown = JSON.parse(json).sub;
    return typeof sub === 'string' ? sub : null;
  } catch {
    return null;
  }
}
