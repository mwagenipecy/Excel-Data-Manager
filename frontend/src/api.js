const API_BASE_URL = 'http://localhost:8000';
const TOKEN_KEY = 'auth_token';

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function authFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const response = await fetch(url.startsWith('http') ? url : `${API_BASE_URL}${url}`, {
    ...options,
    headers,
  });
  if (response.status === 401) {
    setAuthToken(null);
    window.dispatchEvent(new Event('auth:logout'));
  }
  return response;
}

export { API_BASE_URL };
