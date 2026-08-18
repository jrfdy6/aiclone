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

function parseTimestamp(value: string | null | undefined): number | null {
  if (!value || !value.trim()) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export async function waitForFeezieWorkspaceSync({
  receipt,
  readStatus,
  sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  pollIntervalMs = 2_500,
  timeoutMs = 360_000,
}: WaitForFeezieWorkspaceSyncOptions): Promise<FeezieWorkspaceSyncStatus> {
  const cardId = String(receipt.card_id || receipt.job_id || '').trim();
  const queuedAtMs = parseTimestamp(receipt.card?.created_at);
  if (!cardId || queuedAtMs === null || receipt.action !== FEEZIE_WORKSPACE_SYNC_ACTION) {
    throw new Error('FEEZIE workspace sync was queued without an exact signed-action receipt. Reload before retrying.');
  }
  if (!Number.isFinite(pollIntervalMs) || pollIntervalMs <= 0 || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error('FEEZIE workspace sync polling requires a positive interval and timeout.');
  }

  const pollAttempts = Math.max(1, Math.ceil(timeoutMs / pollIntervalMs));
  for (let attempt = 0; attempt < pollAttempts; attempt += 1) {
    const status = await readStatus(cardId);
    const cardCreatedAtMs = parseTimestamp(status.created_at);
    if (
      status.card_id !== cardId
      || status.job_id !== cardId
      || cardCreatedAtMs === null
      || cardCreatedAtMs < queuedAtMs - 1_000
    ) {
      throw new Error('FEEZIE workspace sync status did not match the exact queued action. Reload before retrying.');
    }

    if (status.status === 'failed') {
      throw new Error('FEEZIE workspace sync failed on the local runner. Review the bounded Ops diagnostics before retrying.');
    }

    if (
      status.status === 'completed'
      && parseTimestamp(status.completed_at) !== null
      && parseTimestamp(status.completed_at)! >= queuedAtMs
    ) {
      return status;
    }

    if (attempt + 1 < pollAttempts) {
      await sleep(pollIntervalMs);
    }
  }
  throw new Error('FEEZIE workspace sync did not complete on the signed local runner within six minutes. Reload before retrying.');
}
