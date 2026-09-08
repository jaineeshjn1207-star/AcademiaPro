import axios from 'axios';

const defaultApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  if (typeof window === 'undefined') return 'http://localhost:8000/api/';
  const { protocol, hostname, port, origin } = window.location;
  // Vite dev server talks to Django's default dev port.
  if ((hostname === 'localhost' || hostname === '127.0.0.1') && port === '5173') {
    return 'http://localhost:8000/api/';
  }
  // Production/same-origin deployment.
  return `${origin || `${protocol}//${hostname}`}/api/`;
};

const API_BASE_URL = defaultApiBaseUrl();

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// --------------------------------------------------------------- request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;

    // Let the browser set the multipart boundary itself
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// -------------------------------------------------------------- response
const clearSession = () => {
  ['access_token', 'refresh_token', 'user', 'active_exam'].forEach((k) =>
    localStorage.removeItem(k)
  );
};

let refreshing = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error;

    // A student account locked for unfair means gets rejected on every
    // request from that point on (see IsStudent permission). Force an
    // immediate, clear logout wherever that shows up, not just mid-exam.
    if (response?.status === 403) {
      const msg = response.data?.detail || response.data?.error || '';
      if (typeof msg === 'string' && msg.startsWith('ACCOUNT_BLOCKED:')) {
        clearSession();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login?blocked=1';
        }
        return Promise.reject(error);
      }
    }

    if (!response || response.status !== 401 || config?._retried) {
      return Promise.reject(error);
    }

    // Never try to refresh the login/refresh calls themselves
    const url = config?.url || '';
    if (url.includes('auth/') && (url.includes('login') || url.includes('refresh'))) {
      return Promise.reject(error);
    }

    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      clearSession();
      if (window.location.pathname !== '/login') window.location.href = '/login';
      return Promise.reject(error);
    }

    try {
      // Collapse concurrent 401s into a single refresh round-trip
      refreshing =
        refreshing ||
        axios.post(`${API_BASE_URL}token/refresh/`, { refresh: refreshToken });
      const res = await refreshing;
      refreshing = null;

      const newAccess = res.data.access;
      localStorage.setItem('access_token', newAccess);
      if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh);

      config._retried = true;
      config.headers.Authorization = `Bearer ${newAccess}`;
      return api(config);
    } catch (refreshError) {
      refreshing = null;
      clearSession();
      if (window.location.pathname !== '/login') window.location.href = '/login';
      return Promise.reject(refreshError);
    }
  }
);

export default api;


