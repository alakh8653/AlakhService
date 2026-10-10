import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

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
