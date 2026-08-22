export type IntegratedContentJobReceipt = {
  job_id: string;
  card_id?: string;
  created_at?: string;
};

export type IntegratedContentJobStatus = {
  job_id: string;
  card_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  created_at?: string;
  completed_at?: string | null;
  message?: string | null;
  error?: string | null;
  reason_code?: string | null;
};

export class IntegratedContentJobError extends Error {
  readonly kind: 'invalid_receipt' | 'identity_mismatch' | 'terminal_failure' | 'status_unavailable' | 'timeout';
  readonly retryable: boolean;

  constructor(
    message: string,
    kind: IntegratedContentJobError['kind'],
    { retryable = false }: { retryable?: boolean } = {},
  ) {
    super(message);
    this.name = 'IntegratedContentJobError';
    this.kind = kind;
    this.retryable = retryable;
  }
}

export type PendingIntegratedVariantJob = {
  schema_version: 'integrated_content_pending_variant/v1';
  job_id: string;
  card_id: string;
  post_id: string;
  parent_revision_id: string;
  platform: 'linkedin' | 'instagram';
  created_at: string;
};

type SessionStorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

const PENDING_VARIANT_STORAGE_KEY = 'ai_clone.integrated_content.pending_variants.v1';
const MAX_PENDING_JOB_AGE_MS = 24 * 60 * 60 * 1_000;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$/;
const TERMINAL_PARTIAL_DELIVERY_MESSAGE = 'The local job did not finish all of its delivery steps. Refresh before retrying because canonical local state may already contain the action.';

function defaultStorage(): SessionStorageLike | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function isPendingVariantJob(value: unknown): value is PendingIntegratedVariantJob {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  if (item.schema_version !== 'integrated_content_pending_variant/v1') return false;
  if (item.platform !== 'linkedin' && item.platform !== 'instagram') return false;
  if (![item.job_id, item.card_id, item.post_id, item.parent_revision_id].every((field) => (
    typeof field === 'string' && SAFE_ID.test(field)
  ))) return false;
  if (item.job_id !== item.card_id) return false;
  const createdAt = Date.parse(String(item.created_at || ''));
  return Number.isFinite(createdAt) && Date.now() - createdAt <= MAX_PENDING_JOB_AGE_MS;
}

export function listPendingIntegratedVariantJobs(storage: SessionStorageLike | null = defaultStorage()) {
  if (!storage) return [] as PendingIntegratedVariantJob[];
  try {
    const parsed = JSON.parse(storage.getItem(PENDING_VARIANT_STORAGE_KEY) || '[]') as unknown;
    return Array.isArray(parsed) ? parsed.filter(isPendingVariantJob) : [];
  } catch {
    return [] as PendingIntegratedVariantJob[];
  }
}

export function rememberPendingIntegratedVariantJob(
  job: PendingIntegratedVariantJob,
  storage: SessionStorageLike | null = defaultStorage(),
) {
  if (!storage || !isPendingVariantJob(job)) return;
  const remaining = listPendingIntegratedVariantJobs(storage).filter((item) => item.post_id !== job.post_id);
  try {
    storage.setItem(PENDING_VARIANT_STORAGE_KEY, JSON.stringify([...remaining, job]));
  } catch {
    // Private browsing/storage pressure must not block the governed action itself.
  }
}

export function forgetPendingIntegratedVariantJob(
  jobId: string,
  storage: SessionStorageLike | null = defaultStorage(),
) {
  if (!storage) return;
  const remaining = listPendingIntegratedVariantJobs(storage).filter((item) => item.job_id !== jobId);
  try {
    if (remaining.length) storage.setItem(PENDING_VARIANT_STORAGE_KEY, JSON.stringify(remaining));
    else storage.removeItem(PENDING_VARIANT_STORAGE_KEY);
  } catch {
    // The canonical queue remains authoritative even if browser storage is unavailable.
  }
}

function boundedFailureMessage(value: unknown) {
  if (typeof value !== 'string') return null;
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (!normalized || normalized.length > 280) return null;
  const unsafe = /(traceback|exception|\/users\/|\/private\/|postgres(?:ql)?:\/\/|bearer\s|secret|api[_ -]?key|stack trace)/i;
  const genericTransport = /^(?:http(?: error)?\s+\d{3}\b|request failed with status(?: code)?\s+\d{3}\b|fetch failed\b|failed to fetch\b|network error\b|internal server error\b|bad gateway\b|service unavailable\b|gateway timeout\b|econn(?:refused|reset)\b|etimedout\b)/i;
  return unsafe.test(normalized) || genericTransport.test(normalized) ? null : normalized;
}

export async function waitForIntegratedContentJob({
  receipt,
  readStatus,
  sleep = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  pollIntervalMs = 2_500,
  timeoutMs = 360_000,
  maxConsecutiveReadFailures = 3,
  onStatus,
}: {
  receipt: IntegratedContentJobReceipt;
  readStatus: (jobId: string) => Promise<IntegratedContentJobStatus>;
  sleep?: (milliseconds: number) => Promise<void>;
  pollIntervalMs?: number;
  timeoutMs?: number;
  maxConsecutiveReadFailures?: number;
  onStatus?: (status: IntegratedContentJobStatus) => void;
}) {
  const jobId = String(receipt.job_id || '').trim();
  if (!jobId || (receipt.card_id && receipt.card_id !== jobId)) {
    throw new IntegratedContentJobError(
      'The local content job receipt did not identify one exact signed action.',
      'invalid_receipt',
    );
  }
  const attempts = Math.max(1, Math.ceil(timeoutMs / pollIntervalMs));
  let consecutiveReadFailures = 0;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    let status: IntegratedContentJobStatus;
    try {
      status = await readStatus(jobId);
      consecutiveReadFailures = 0;
    } catch {
      consecutiveReadFailures += 1;
      if (consecutiveReadFailures >= Math.max(1, maxConsecutiveReadFailures)) {
        throw new IntegratedContentJobError(
          'The phone temporarily lost the local job status. The action may still be running; refresh to resume it before retrying.',
          'status_unavailable',
          { retryable: true },
        );
      }
      if (attempt + 1 < attempts) await sleep(pollIntervalMs);
      continue;
    }
    if (status.job_id !== jobId || status.card_id !== jobId) {
      throw new IntegratedContentJobError(
        'The local content job status did not match the exact queued action.',
        'identity_mismatch',
      );
    }
    onStatus?.(status);
    if (status.status === 'completed') return status;
    if (status.status === 'failed') {
      throw new IntegratedContentJobError(
        boundedFailureMessage(status.message)
          ?? boundedFailureMessage(status.error)
          ?? TERMINAL_PARTIAL_DELIVERY_MESSAGE,
        'terminal_failure',
      );
    }
    if (attempt + 1 < attempts) await sleep(pollIntervalMs);
  }
  throw new IntegratedContentJobError(
    'The local content job is taking longer than expected. It may still complete; refresh to resume its exact status before retrying.',
    'timeout',
    { retryable: true },
  );
}
