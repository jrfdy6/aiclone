const CONTROL_API_BASE = '/api/control';
const DEFAULT_CONTROL_TIMEOUT_MS = 40_000;

export class ControlApiError extends Error {
  readonly status: number;
  readonly reasonCode: string;

  constructor(message: string, { status, reasonCode }: { status: number; reasonCode: string }) {
    super(message);
    this.name = 'ControlApiError';
    this.status = status;
    this.reasonCode = reasonCode;
  }
}

type ControlFetchOptions = RequestInit & {
  timeoutMs?: number;
};

function isAbortError(error: unknown) {
  return error instanceof Error && error.name === 'AbortError';
}

function fallbackMessage(status: number) {
  if (status === 400 || status === 422) return 'That action could not be accepted. Review the selected item and try again.';
  if (status === 401) return 'Your owner session expired. Sign in again and retry the action.';
  if (status === 403) return 'This owner action is not authorized.';
  if (status === 404) return 'That item or action is no longer available. Refresh the page.';
  if (status === 409) return 'The item changed before the action completed. Refresh and review the latest version.';
  if (status === 429) return 'The system is already handling several requests. Wait a moment, then retry.';
  if (status === 503) return 'The local content worker is temporarily unavailable. Your content was not changed.';
  if (status === 504) return 'The local content worker did not respond in time. Check the job status before retrying.';
  return 'The action could not be completed. Your content was not changed.';
}

function boundedOwnerMessage(value: unknown) {
  if (typeof value !== 'string') return null;
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (!normalized || normalized.length > 280) return null;
  const unsafe = /(traceback|exception|\/users\/|\/private\/|postgres(?:ql)?:\/\/|bearer\s|secret|api[_ -]?key|stack trace)/i;
  return unsafe.test(normalized) ? null : normalized;
}

export function ownerSafeErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ControlApiError) return error.message;
  return boundedOwnerMessage(error instanceof Error ? error.message : error) ?? fallback;
}

function boundedReasonCode(value: unknown, status: number) {
  const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
  return /^[a-z0-9][a-z0-9_.-]{0,79}$/.test(normalized) ? normalized : `control_http_${status}`;
}

export async function readSafeControlError(response: Response) {
  let payload: unknown = null;
  try {
    payload = await response.clone().json();
  } catch {
    // Upstream HTML, proxy diagnostics, and arbitrary text are intentionally not shown to the owner.
  }
  const record = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : {};
  const detail = record.detail && typeof record.detail === 'object' && !Array.isArray(record.detail)
    ? record.detail as Record<string, unknown>
    : {};
  const message = boundedOwnerMessage(detail.message)
    ?? boundedOwnerMessage(detail.safe_message)
    ?? boundedOwnerMessage(record.message)
    ?? fallbackMessage(response.status);
  const reasonCode = boundedReasonCode(
    detail.reason_code ?? detail.code ?? record.reason_code ?? record.code,
    response.status,
  );
  return new ControlApiError(message, { status: response.status, reasonCode });
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
      throw await readSafeControlError(response);
    }
    return response;
  } catch (error) {
    if (isAbortError(error)) {
      throw new ControlApiError(
        'The owner action request timed out. Check the item status before retrying.',
        { status: 504, reasonCode: 'control_request_timeout' },
      );
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
