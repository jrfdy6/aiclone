/**
 * API Client Utilities
 *
 * Provides helper functions for authenticated, same-origin API calls.
 */

const CONTROL_API_BASE = '/api/control';
const DEFAULT_API_TIMEOUT_MS = 40_000;

type ApiFetchOptions = RequestInit & {
  timeoutMs?: number;
};

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
 * Return the authenticated same-origin control-plane proxy.
 *
 * Keeping this compatibility helper pinned to a relative URL prevents legacy
 * browser screens from bypassing the frontend's session gate.
 */
export function getApiUrl(): string {
  return CONTROL_API_BASE;
}

export function hasConfiguredApiUrl(): boolean {
  return true;
}

/**
 * Make a fetch request to the API with error handling
 */
export async function apiFetch(
  endpoint: string,
  options: ApiFetchOptions = {}
): Promise<Response> {
  const { timeoutMs = DEFAULT_API_TIMEOUT_MS, ...requestOptions } = options;
  if (/^https?:\/\//i.test(endpoint)) {
    throw new Error('Absolute backend URLs are not supported in the browser client');
  }

  const url = `${CONTROL_API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

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
