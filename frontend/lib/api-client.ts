/**
 * API Client Utilities
 *
 * Provides helper functions for API calls and URL configuration
 */

const LOCAL_FALLBACK = 'http://localhost:3001';

function isLocalhost(url: string) {
  return /localhost|127\.0\.0\.1/i.test(url);
}

function ensureProtocol(url: string) {
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  return `https://${url}`;
}

function stripTrailingSlash(url: string) {
  return url.endsWith('/') ? url.slice(0, -1) : url;
}

function preferHttps(url: string) {
  if (url.startsWith('http://') && !isLocalhost(url)) {
    return `https://${url.slice('http://'.length)}`;
  }
  return url;
}

/**
 * Get the API URL from environment variables.
 * Falls back to localhost for development and enforces HTTPS in the browser.
 */
export function getApiUrl(): string {
  const envValue = (process.env.NEXT_PUBLIC_API_URL ?? '').trim();
  const base = envValue.length > 0 ? envValue : LOCAL_FALLBACK;
  const withProtocol = ensureProtocol(base);
  const normalized = stripTrailingSlash(withProtocol);

  if (typeof window !== 'undefined') {
    return stripTrailingSlash(preferHttps(normalized));
  }

  return normalized;
}

/**
 * Make a fetch request to the API with error handling
 */
export async function apiFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const apiUrl = getApiUrl();

  if (!apiUrl) {
    throw new Error('NEXT_PUBLIC_API_URL is not configured');
  }

  const url = endpoint.startsWith('http')
    ? endpoint
    : `${apiUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const defaultOptions: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, defaultOptions);

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText);
    throw new Error(
      `API request failed: ${response.status} ${response.statusText} - ${errorText}`
    );
  }

  return response;
}

/**
 * Make a GET request and parse JSON response
 */
export async function apiGet<T = unknown>(endpoint: string): Promise<T> {
  const response = await apiFetch(endpoint, { method: 'GET' });
  return response.json();
}

/**
 * Make a POST request and parse JSON response
 */
export async function apiPost<T = unknown>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  const response = await apiFetch(endpoint, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  });
  return response.json();
}

/**
 * Make a PUT request and parse JSON response
 */
export async function apiPut<T = unknown>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  const response = await apiFetch(endpoint, {
    method: 'PUT',
    body: data ? JSON.stringify(data) : undefined,
  });
  return response.json();
}

/**
 * Make a DELETE request and parse JSON response
 */
export async function apiDelete<T = unknown>(endpoint: string): Promise<T> {
  const response = await apiFetch(endpoint, { method: 'DELETE' });
  return response.json();
}
