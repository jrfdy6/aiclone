/**
 * API Client Utilities
 *
 * Provides helper functions for API calls and URL configuration
 */

const LOCAL_FALLBACK = 'http://localhost:3001';
const DEFAULT_API_TIMEOUT_MS = 40_000;

type ApiFetchOptions = RequestInit & {
  timeoutMs?: number;
};

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

function isAbortError(error: unknown) {
  return error instanceof Error && error.name === 'AbortError';
}

function buildTimedSignal(timeoutMs: number, upstreamSignal?: AbortSignal) {
  const controller = new AbortController();
  const abortFromUpstream = () => controller.abort();

  if (upstreamSignal?.aborted) {
    controller.abort();
  } else if (upstreamSignal) {
    upstreamSignal.addEventListener('abort', abortFromUpstream, { once: true });
  }

  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timeoutId);
      upstreamSignal?.removeEventListener('abort', abortFromUpstream);
    },
  };
}

/**
 * Get the API URL from environment variables.
 * Falls back to localhost for development and enforces HTTPS for non-local hosts.
 */
export function getApiUrl(): string {
  const envValue = (process.env.NEXT_PUBLIC_API_URL ?? '').trim();
  const base = envValue.length > 0 ? envValue : LOCAL_FALLBACK;
  const withProtocol = ensureProtocol(base);
  const normalized = stripTrailingSlash(withProtocol);
  return stripTrailingSlash(preferHttps(normalized));
}

export function hasConfiguredApiUrl(): boolean {
  return (process.env.NEXT_PUBLIC_API_URL ?? '').trim().length > 0;
}

/**
 * Make a fetch request to the API with error handling
 */
export async function apiFetch(
  endpoint: string,
  options: ApiFetchOptions = {}
): Promise<Response> {
  const { timeoutMs = DEFAULT_API_TIMEOUT_MS, ...requestOptions } = options;
  const apiUrl = getApiUrl();

  if (!apiUrl) {
    throw new Error('NEXT_PUBLIC_API_URL is not configured');
  }

  const url = endpoint.startsWith('http')
    ? endpoint
    : `${apiUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const method = String(requestOptions.method ?? 'GET').toUpperCase();
  const headers = new Headers(requestOptions.headers);
  const hasBody = requestOptions.body !== undefined && requestOptions.body !== null;

  if (!headers.has('Content-Type') && hasBody && method !== 'GET' && method !== 'HEAD') {
    headers.set('Content-Type', 'application/json');
  }

  const defaultOptions: RequestInit = {
    ...requestOptions,
    headers,
  };

  const { signal, cleanup } = buildTimedSignal(timeoutMs, requestOptions.signal ?? undefined);

  let response: Response;
  try {
    response = await fetch(url, {
      ...defaultOptions,
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw new Error(`API request timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    cleanup();
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText);
    throw new Error(
      `API request failed: ${response.status} ${response.statusText} - ${errorText}`
    );
  }

  return response;
}

export async function apiGet<T = unknown>(
  endpoint: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const response = await apiFetch(endpoint, { method: 'GET', ...options });
  return response.json();
}

/**
 * Make a POST request and parse JSON response
 */
export async function apiPost<T = unknown>(
  endpoint: string,
  data?: unknown,
  options: ApiFetchOptions = {}
): Promise<T> {
  const response = await apiFetch(endpoint, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
    ...options,
  });
  return response.json();
}

/**
 * Make a PUT request and parse JSON response
 */
export async function apiPut<T = unknown>(
  endpoint: string,
  data?: unknown,
  options: ApiFetchOptions = {}
): Promise<T> {
  const response = await apiFetch(endpoint, {
    method: 'PUT',
    body: data ? JSON.stringify(data) : undefined,
    ...options,
  });
  return response.json();
}

/**
 * Make a DELETE request and parse JSON response
 */
export async function apiDelete<T = unknown>(
  endpoint: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const response = await apiFetch(endpoint, { method: 'DELETE', ...options });
  return response.json();
}
