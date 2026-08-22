export type FirestoreReadinessState = 'ready' | 'degraded';

export type FirestoreReadinessCheck = {
  key: string;
  scope: 'top_level' | 'collection_group';
  collection: string;
  consumerRole: string;
  state: FirestoreReadinessState;
  durationMs: number;
  reasonCodes: string[];
};

export type FirestoreReadinessReceipt = {
  schemaVersion: 'firestore_retained_role_readiness/v1';
  state: FirestoreReadinessState;
  ready: boolean;
  checkedAt: string | null;
  durationMs: number;
  requiredCheckCount: number;
  passedCheckCount: number;
  failedCheckCount: number;
  reasonCodes: string[];
  checks: FirestoreReadinessCheck[];
};

type ExpectedCheck = Omit<FirestoreReadinessCheck, 'state' | 'durationMs' | 'reasonCodes'>;

const SCHEMA_VERSION = 'firestore_retained_role_readiness/v1' as const;
const EXPECTED_CHECKS: readonly ExpectedCheck[] = [
  { key: 'activity_logs', scope: 'top_level', collection: 'activity_logs', consumerRole: 'legacy_activity_compatibility' },
  { key: 'knowledge_docs', scope: 'top_level', collection: 'knowledge_docs', consumerRole: 'knowledge_and_drive_ingest' },
  { key: 'playbooks', scope: 'top_level', collection: 'playbooks', consumerRole: 'playbook_product' },
  { key: 'research_insights', scope: 'top_level', collection: 'research_insights', consumerRole: 'legacy_research_compatibility' },
  { key: 'research_tasks', scope: 'top_level', collection: 'research_tasks', consumerRole: 'legacy_research_compatibility' },
  { key: 'system_logs', scope: 'top_level', collection: 'system_logs', consumerRole: 'system_log_and_analytics_compatibility' },
  { key: 'prospects_top_level', scope: 'top_level', collection: 'prospects', consumerRole: 'legacy_prospect_read_compatibility' },
  { key: 'memory_chunks', scope: 'collection_group', collection: 'memory_chunks', consumerRole: 'memory_retrieval_fallback' },
  { key: 'ingest_jobs', scope: 'collection_group', collection: 'ingest_jobs', consumerRole: 'ingestion_job_state' },
  { key: 'prospect_discoveries', scope: 'collection_group', collection: 'prospect_discoveries', consumerRole: 'prospect_discovery_history' },
  { key: 'prospects_nested', scope: 'collection_group', collection: 'prospects', consumerRole: 'canonical_prospect_authority' },
  { key: 'topic_intelligence', scope: 'collection_group', collection: 'topic_intelligence', consumerRole: 'topic_intelligence_and_research_pages' },
];

const SAFE_REASON_CODES = new Set([
  'firestore_unavailable',
  'firestore_probe_failed',
  'firestore_probe_timeout',
  'firestore_readiness_projection_rejected',
  'firestore_readiness_invalid',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function safeDuration(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.min(Math.max(Math.round(value), 0), 120_000)
    : 0;
}

function safeReasonCodes(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return Array.from(new Set(value.filter((item): item is string => typeof item === 'string' && SAFE_REASON_CODES.has(item)))).slice(0, 5);
}

function safeCheckedAt(value: unknown): string | null {
  if (typeof value !== 'string' || value.length > 40 || !/^\d{4}-\d{2}-\d{2}T/.test(value)) return null;
  return Number.isNaN(Date.parse(value)) ? null : value;
}

export function normalizeFirestoreReadinessReceipt(payload: unknown): FirestoreReadinessReceipt {
  const source = isRecord(payload) ? payload : {};
  const rawChecks = Array.isArray(source.checks) ? source.checks.filter(isRecord) : [];
  const schemaValid = source.schema_version === SCHEMA_VERSION && source.mode === 'read_only_aggregate_queries';

  const checks = EXPECTED_CHECKS.map((expected) => {
    const raw = rawChecks.find((item) => item.key === expected.key);
    const bindingValid = Boolean(
      raw
      && raw.scope === expected.scope
      && raw.collection === expected.collection
      && raw.consumer_role === expected.consumerRole,
    );
    const state: FirestoreReadinessState = schemaValid && bindingValid && raw?.state === 'ready' ? 'ready' : 'degraded';
    const reasonCodes = bindingValid ? safeReasonCodes(raw?.reason_codes) : ['firestore_readiness_invalid'];
    return {
      ...expected,
      state,
      durationMs: bindingValid ? safeDuration(raw?.duration_ms) : 0,
      reasonCodes: state === 'ready' ? [] : reasonCodes.length ? reasonCodes : ['firestore_readiness_invalid'],
    };
  });

  const passedCheckCount = checks.filter((check) => check.state === 'ready').length;
  const failedCheckCount = checks.length - passedCheckCount;
  const ready = schemaValid && source.ready === true && source.state === 'ready' && failedCheckCount === 0;
  const reasonCodes = ready
    ? []
    : Array.from(new Set([
        ...safeReasonCodes(source.reason_codes),
        ...checks.flatMap((check) => check.reasonCodes),
      ])).slice(0, 5);

  return {
    schemaVersion: SCHEMA_VERSION,
    state: ready ? 'ready' : 'degraded',
    ready,
    checkedAt: safeCheckedAt(source.checked_at),
    durationMs: safeDuration(source.duration_ms),
    requiredCheckCount: checks.length,
    passedCheckCount,
    failedCheckCount,
    reasonCodes: reasonCodes.length ? reasonCodes : ['firestore_readiness_invalid'],
    checks,
  };
}
