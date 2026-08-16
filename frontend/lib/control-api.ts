const CONTROL_API_BASE = '/api/control';
const DEFAULT_CONTROL_TIMEOUT_MS = 40_000;

type ControlFetchOptions = RequestInit & {
  timeoutMs?: number;
};

function isAbortError(error: unknown) {
  return error instanceof Error && error.name === 'AbortError';
}

async function controlApiFetch(endpoint: string, options: ControlFetchOptions = {}) {
  const { timeoutMs = DEFAULT_CONTROL_TIMEOUT_MS, ...requestOptions } = options;
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(requestOptions.headers);
  const hasBody = requestOptions.body !== undefined && requestOptions.body !== null;

  if (hasBody && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(`${CONTROL_API_BASE}${path}`, {
      ...requestOptions,
      headers,
      cache: requestOptions.cache ?? 'no-store',
      credentials: 'same-origin',
      signal: controller.signal,
    });
    if (!response.ok) {
      const errorText = await response.text().catch(() => response.statusText);
      throw new Error(`${response.status} ${response.statusText}: ${errorText}`);
    }
    return response;
  } catch (error) {
    if (isAbortError(error)) {
      throw new Error(`Control request timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function controlApiGet<T>(endpoint: string, options: ControlFetchOptions = {}): Promise<T> {
  const response = await controlApiFetch(endpoint, { ...options, method: 'GET' });
  return response.json() as Promise<T>;
}

export async function controlApiPost<T>(endpoint: string, data: unknown, options: ControlFetchOptions = {}): Promise<T> {
  const response = await controlApiFetch(endpoint, {
    ...options,
    method: 'POST',
    body: JSON.stringify(data),
  });
  return response.json() as Promise<T>;
}

export async function controlApiPatch<T>(endpoint: string, data: unknown, options: ControlFetchOptions = {}): Promise<T> {
  const response = await controlApiFetch(endpoint, {
    ...options,
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  return response.json() as Promise<T>;
}
