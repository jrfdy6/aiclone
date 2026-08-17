'use client';

export type FeeziePrivateRuntimeContextStatus = {
  schema_version?: string;
  checked_at?: string;
  context_generated_at?: string | null;
  age_seconds?: number | null;
  stale_after_seconds?: number;
  state?: 'ready' | 'degraded' | 'missing' | 'invalid' | 'stale' | string;
  ready?: boolean;
  reason_codes?: string[];
  persona_canon?: { ready?: boolean; count?: number };
  approved_voice_examples?: { ready?: boolean; count?: number };
  anonymized_proof?: { ready?: boolean; count?: number };
  source_grounding?: {
    ready?: boolean;
    strategy_contract_present?: boolean;
    content_integrity_valid?: boolean;
  };
  data_policy?: {
    aggregate_only?: boolean;
    private_context_included?: boolean;
  };
};

export type FeeziePrivateRuntimeLoadState = 'loading' | 'live' | 'error';

const FEEZIE_PRIVATE_RUNTIME_CONTEXT_SCHEMA = 'feezie_private_runtime_context_status/v1';
const FEEZIE_PRIVATE_RUNTIME_STALE_AFTER_SECONDS = 36 * 60 * 60;
const FEEZIE_PRIVATE_RUNTIME_MAX_FUTURE_SKEW_SECONDS = 5 * 60;

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
}

function isTimezoneTimestamp(value: unknown): value is string {
  if (typeof value !== 'string' || value.trim() === '') return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value.trim());
}

export function isFeeziePrivateRuntimeContextReady(
  status: FeeziePrivateRuntimeContextStatus | null | undefined,
): boolean {
  if (!status || typeof status !== 'object') return false;

  return (
    status.schema_version === FEEZIE_PRIVATE_RUNTIME_CONTEXT_SCHEMA
    && isTimezoneTimestamp(status.checked_at)
    && isTimezoneTimestamp(status.context_generated_at)
    && typeof status.age_seconds === 'number'
    && Number.isInteger(status.age_seconds)
    && status.age_seconds >= -FEEZIE_PRIVATE_RUNTIME_MAX_FUTURE_SKEW_SECONDS
    && status.age_seconds <= FEEZIE_PRIVATE_RUNTIME_STALE_AFTER_SECONDS
    && Math.abs(
      Math.trunc((Date.parse(status.checked_at) - Date.parse(status.context_generated_at)) / 1000)
      - status.age_seconds,
    ) <= 1
    && status.stale_after_seconds === FEEZIE_PRIVATE_RUNTIME_STALE_AFTER_SECONDS
    && status.state === 'ready'
    && status.ready === true
    && Array.isArray(status.reason_codes)
    && status.reason_codes.length === 0
    && status.data_policy?.aggregate_only === true
    && status.data_policy.private_context_included === false
    && status.persona_canon?.ready === true
    && isPositiveInteger(status.persona_canon.count)
    && status.approved_voice_examples?.ready === true
    && isPositiveInteger(status.approved_voice_examples.count)
    && status.anonymized_proof?.ready === true
    && isPositiveInteger(status.anonymized_proof.count)
    && status.source_grounding?.ready === true
    && status.source_grounding.strategy_contract_present === true
    && status.source_grounding.content_integrity_valid === true
  );
}

function statusPresentation(
  status: FeeziePrivateRuntimeContextStatus | null | undefined,
  loadState: FeeziePrivateRuntimeLoadState,
) {
  if (loadState === 'loading') {
    return { label: 'Private context checking', tone: '#38bdf8', state: 'loading' };
  }
  if (loadState !== 'live' || !status || status.schema_version !== FEEZIE_PRIVATE_RUNTIME_CONTEXT_SCHEMA) {
    return { label: 'Private context unavailable', tone: '#f87171', state: 'unavailable' };
  }
  if (isFeeziePrivateRuntimeContextReady(status)) {
    return { label: 'Private context ready', tone: '#34d399', state: 'ready' };
  }
  if (status.state === 'invalid' || status.state === 'ready' || status.ready === true) {
    return { label: 'Private context invalid', tone: '#f87171', state: 'invalid' };
  }
  if (status.state === 'missing') {
    return { label: 'Private context missing', tone: '#fbbf24', state: 'missing' };
  }
  return { label: 'Private context degraded', tone: '#fbbf24', state: 'degraded' };
}

function countLabel(value: number | undefined) {
  return isPositiveInteger(value) ? String(value) : '0';
}

export function FeeziePrivateRuntimeStatusBadge({
  status,
  loadState = 'live',
}: {
  status?: FeeziePrivateRuntimeContextStatus | null;
  loadState?: FeeziePrivateRuntimeLoadState;
}) {
  const presentation = statusPresentation(status, loadState);
  const hasBoundedStatus = status?.schema_version === FEEZIE_PRIVATE_RUNTIME_CONTEXT_SCHEMA;
  const generationReady = loadState === 'live' && isFeeziePrivateRuntimeContextReady(status);
  const readinessMessage = generationReady
    ? 'FEEZIE generation is ready.'
    : presentation.state === 'loading'
      ? 'Checking private runtime context before generation.'
      : 'FEEZIE generation stays closed until private runtime context is fully ready.';

  return (
    <div
      data-feezie-private-runtime-context-status={presentation.state}
      data-feezie-generation-ready={generationReady ? 'true' : 'false'}
      style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}
    >
      <span
        style={{
          border: `1px solid ${presentation.tone}66`,
          borderRadius: '999px',
          color: presentation.tone,
          fontSize: '10px',
          fontWeight: 800,
          letterSpacing: '0.04em',
          padding: '4px 8px',
          textTransform: 'uppercase',
        }}
      >
        {presentation.label}
      </span>
      {hasBoundedStatus ? (
        <span style={{ color: '#64748b', fontSize: '11px' }}>
          Persona {countLabel(status?.persona_canon?.count)} · Voice {countLabel(status?.approved_voice_examples?.count)} · Proof {countLabel(status?.anonymized_proof?.count)} · Source {status?.source_grounding?.ready ? 'ready' : 'not ready'}
        </span>
      ) : (
        <span style={{ color: '#64748b', fontSize: '11px' }}>
          {readinessMessage}
        </span>
      )}
      {hasBoundedStatus ? (
        <span style={{ color: generationReady ? '#34d399' : '#fbbf24', fontSize: '11px', width: '100%' }}>
          {readinessMessage}
        </span>
      ) : null}
    </div>
  );
}

export function humanizeFeezieRuntimeReason(value: string) {
  return value.trim().replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
