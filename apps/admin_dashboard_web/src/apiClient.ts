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

export default adminApiClient;
