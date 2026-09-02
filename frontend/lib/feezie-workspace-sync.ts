export const FEEZIE_WORKSPACE_SYNC_ACTION = 'refresh_feezie_workspace';

export type FeezieWorkspaceSyncQueueReceipt = {
  message?: string;
  queued?: boolean;
  state?: string;
  disposition?: string;
  action?: string;
  card_id?: string;
  job_id?: string;
  card?: {
    id?: string;
    created_at?: string;
    updated_at?: string;
  };
};

export type FeezieWorkspaceSyncStatus = {
  job_id?: string;
  card_id?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
  message?: string | null;
  error_code?: string | null;
};

type WaitForFeezieWorkspaceSyncOptions = {
  receipt: FeezieWorkspaceSyncQueueReceipt;
  readStatus: (cardId: string) => Promise<FeezieWorkspaceSyncStatus>;
  sleep?: (milliseconds: number) => Promise<void>;
  pollIntervalMs?: number;
  timeoutMs?: number;
};

export function parseAiCloneUtcTimestamp(value: string | null | undefined): number | null {
  const normalized = value?.trim() ?? '';
  if (!normalized || !/(?:Z|\+00:00)$/i.test(normalized)) return null;
  const parsed = Date.parse(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function feezieWorkspaceSyncTransitionAt(receipt: FeezieWorkspaceSyncQueueReceipt): number {
  const cardId = String(receipt.card_id || '').trim();
  const jobId = String(receipt.job_id || '').trim();
  const receiptCardId = String(receipt.card?.id || '').trim();
  const disposition = String(receipt.disposition || '').trim();
  const createdAtMs = parseAiCloneUtcTimestamp(receipt.card?.created_at);
  const transitionAtMs = disposition === 'requeued'
    ? parseAiCloneUtcTimestamp(receipt.card?.updated_at)
    : createdAtMs;
  if (
    receipt.queued !== true
    || receipt.action !== FEEZIE_WORKSPACE_SYNC_ACTION
    || !cardId
    || jobId !== cardId
    || receiptCardId !== cardId
    || !['queued', 'already_active', 'requeued'].includes(disposition)
    || createdAtMs === null
    || transitionAtMs === null
    || transitionAtMs < createdAtMs
  ) {
    throw new Error('FEEZIE workspace sync was queued without an exact signed-action receipt. Reload before retrying.');
  }
  return transitionAtMs;
}

export async function waitForFeezieWorkspaceSync({
  receipt,
  readStatus,
  sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  pollIntervalMs = 2_500,
  timeoutMs = 360_000,
}: WaitForFeezieWorkspaceSyncOptions): Promise<FeezieWorkspaceSyncStatus> {
  const cardId = String(receipt.card_id || '').trim();
  const cardCreatedAtMs = parseAiCloneUtcTimestamp(receipt.card?.created_at);
  const transitionAtMs = feezieWorkspaceSyncTransitionAt(receipt);
  if (!Number.isFinite(pollIntervalMs) || pollIntervalMs <= 0 || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error('FEEZIE workspace sync polling requires a positive interval and timeout.');
  }

  const pollAttempts = Math.max(1, Math.ceil(timeoutMs / pollIntervalMs));
  for (let attempt = 0; attempt < pollAttempts; attempt += 1) {
    const status = await readStatus(cardId);
    const statusCreatedAtMs = parseAiCloneUtcTimestamp(status.created_at);
    const statusUpdatedAtMs = parseAiCloneUtcTimestamp(status.updated_at);
    if (
      status.card_id !== cardId
      || status.job_id !== cardId
      || statusCreatedAtMs === null
      || statusCreatedAtMs !== cardCreatedAtMs
      || statusUpdatedAtMs === null
      || statusUpdatedAtMs < transitionAtMs
    ) {
      throw new Error('FEEZIE workspace sync status did not match the exact queued action. Reload before retrying.');
    }

    if (status.status === 'failed') {
      throw new Error('FEEZIE workspace sync failed on the local runner. Review the bounded Ops diagnostics before retrying.');
    }

    if (
      status.status === 'completed'
      && parseAiCloneUtcTimestamp(status.completed_at) !== null
      && parseAiCloneUtcTimestamp(status.completed_at)! >= transitionAtMs
    ) {
      return status;
    }

    if (attempt + 1 < pollAttempts) {
      await sleep(pollIntervalMs);
    }
  }
  throw new Error('FEEZIE workspace sync did not complete on the signed local runner within six minutes. Reload before retrying.');
}
