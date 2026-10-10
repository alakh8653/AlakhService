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
adminApiClient.interceptors.response.use((response) => {
  const contentType = String(response.headers['content-type'] ?? '');
  if (response.status !== 204 && !contentType.includes('application/json')) {
    return Promise.reject(new Error(`Unexpected response type "${contentType}" from ${response.config.url}`));
  }
  return response;
});

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
