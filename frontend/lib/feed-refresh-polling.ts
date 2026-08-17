export type FeedRefreshStatus = {
  running: boolean;
  state?: 'idle' | 'queued' | 'running' | 'succeeded' | 'failed' | string;
  run_id?: string | null;
  queued_at?: string | null;
  last_run?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  error_type?: string | null;
  reason_codes?: string[];
};

export type FeedRefreshQueueReceipt = {
  status?: string;
  state?: string;
  run_id?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
};

type WaitForFeedRefreshAttemptOptions = {
  receipt: FeedRefreshQueueReceipt;
  readStatus: () => Promise<FeedRefreshStatus>;
  sleep?: (milliseconds: number) => Promise<void>;
  pollIntervalMs?: number;
  timeoutMs?: number;
  timeoutMessage?: string;
};

function parseTimestamp(value: string | null | undefined): number | null {
  if (!value || !value.trim()) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isBoundTerminalStatus(
  status: FeedRefreshStatus,
  runId: string,
  queuedAtMs: number,
): boolean {
  if (status.run_id !== runId) return false;
  const startedAtMs = parseTimestamp(status.started_at);
  const completedAtMs = parseTimestamp(status.completed_at ?? status.last_run);
  return (
    startedAtMs !== null &&
    completedAtMs !== null &&
    startedAtMs >= queuedAtMs &&
    completedAtMs >= startedAtMs
  );
}

export async function waitForFeedRefreshAttempt({
  receipt,
  readStatus,
  sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  pollIntervalMs = 2_500,
  timeoutMs = 240_000,
  timeoutMessage =
    'Feed refresh did not report a terminal state within four minutes. The Railway job may still be running; reload before retrying.',
}: WaitForFeedRefreshAttemptOptions): Promise<FeedRefreshStatus> {
  const runId = String(receipt.run_id || '').trim();
  const queuedAtMs = parseTimestamp(receipt.queued_at ?? receipt.started_at);
  if (!runId || queuedAtMs === null) {
    throw new Error('Feed refresh was queued without a verifiable run receipt. Reload before retrying.');
  }
  if (!Number.isFinite(pollIntervalMs) || pollIntervalMs <= 0 || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error('Feed refresh polling requires a positive interval and timeout.');
  }

  const pollAttempts = Math.max(1, Math.ceil(timeoutMs / pollIntervalMs));
  for (let attempt = 0; attempt < pollAttempts; attempt += 1) {
    const status = await readStatus();
    if (isBoundTerminalStatus(status, runId, queuedAtMs)) {
      if (status.state === 'failed') {
        throw new Error('Feed refresh failed. Reload and review the bounded Ops diagnostics before retrying.');
      }
      if (status.state === 'succeeded') {
        return status;
      }
    }
    if (attempt + 1 < pollAttempts) {
      await sleep(pollIntervalMs);
    }
  }
  throw new Error(timeoutMessage);
}
