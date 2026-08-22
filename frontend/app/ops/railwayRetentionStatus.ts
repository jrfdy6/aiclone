import type {
  RailwayRetentionMetric,
  RailwayRetentionStatus,
} from './RailwayRetentionHealthPanel';

const STATUS_FIELDS = [
  'schema_version',
  'state',
  'ready',
  'checked_at',
  'stale_after_seconds',
  'reason_codes',
  'plan',
  'backup_binding',
  'aggregate_compaction',
  'rollback',
  'cost',
  'rules',
  'privacy',
] as const;
const PLAN_FIELDS = [
  'state',
  'receipt_present',
  'lifecycle_status',
  'receipt_id',
  'as_of',
  'created_at',
  'applied_at',
  'rolled_back_at',
  'age_seconds',
  'stale',
  'candidate_rows',
  'candidate_bytes',
  'blocked_rows',
  'local_archive_proof_count',
] as const;
const BACKUP_FIELDS = [
  'state',
  'bound',
  'manifest_recorded',
  'exact_plan_binding_recorded',
  'local_reverification_required',
] as const;
const AGGREGATE_FIELDS = [
  'state',
  'expected_source_rows',
  'aggregated_source_rows',
  'aggregate_receipt_rows',
  'matches',
] as const;
const ROLLBACK_FIELDS = [
  'state',
  'ready',
  'row_receipts',
  'aggregate_receipts',
  'requires_isolated_backup_revalidation',
] as const;
const COST_FIELDS = [
  'state',
  'before',
  'after',
  'logical_bytes_reduced',
  'logical_reduction_proven',
  'physical',
  'cost_reduction_proven',
] as const;
const METRIC_FIELDS = [
  'postgres_database_bytes',
  'tracked_source_relation_bytes',
  'tracked_retention_overhead_bytes',
  'tracked_relation_bytes',
  'estimated_live_rows',
  'estimated_dead_rows',
  'row_counts_are_estimates',
  'physical_reclamation_claimed',
] as const;
const PHYSICAL_FIELDS = [
  'railway_volume_before_bytes',
  'railway_volume_after_bytes',
  'measured',
  'reclamation_claimed',
] as const;
const RULE_FIELDS = [
  'rule',
  'state',
  'candidate_rows',
  'candidate_bytes',
  'blocked_rows',
  'affected_rows',
  'reason_code',
] as const;
const PRIVACY_FIELDS = [
  'source_rows_returned',
  'source_identifiers_returned',
  'private_payloads_returned',
  'provider_errors_returned',
] as const;

const STATUS_STATES = ['ready', 'degraded', 'blocked'] as const;
const PLAN_STATES = ['missing', 'present'] as const;
const PLAN_LIFECYCLES = ['planned', 'applied', 'partially_applied', 'rolled_back', 'failed'] as const;
const BACKUP_STATES = ['missing', 'recorded_requires_local_reverification'] as const;
const AGGREGATE_STATES = ['unavailable', 'pending', 'ready', 'degraded'] as const;
const ROLLBACK_STATES = [
  'unavailable',
  'completed',
  'requires_local_backup_reverification',
  'blocked_missing_backup_binding',
  'not_applicable_pre_apply',
] as const;
const COST_STATES = ['unmeasured', 'before_only', 'measured_logical_only'] as const;
const SAFE_REASON_CODES = [
  'retention_database_unavailable',
  'retention_receipt_missing',
  'retention_plan_stale',
  'retention_plan_blocked',
  'retention_apply_partial',
  'retention_backup_unbound',
  'retention_backup_requires_local_reverification',
  'retention_aggregate_mismatch',
  'retention_rollback_requires_local_backup',
  'retention_physical_cost_unmeasured',
  'retention_no_after_metrics',
  'retention_projection_failed',
] as const;
const SAFE_RULE_NAMES = [
  'automation_non_action_detail',
  'completed_large_job_payloads',
  'standup_payload_compaction',
  'standup_rows_after_audit_window',
  'workspace_snapshot_payload_compaction',
] as const;
const SAFE_RULE_STATES = [
  'planned',
  'applied',
  'partially_applied',
  'blocked',
  'not_applicable',
  'rolled_back',
] as const;
const SAFE_RULE_REASONS = [
  'active_consumer_contract_unproven',
  'per_type_projection_contract_unproven',
  'unresolved_nonhealthy_rows_retained',
  'terminal_recent_or_unproven_rows_retained',
  'migration_proof_or_gate_incomplete',
] as const;

const MAX_BOUNDED_INTEGER = 1_000_000_000_000_000;
const MAX_RULES = 16;
const STALE_AFTER_SECONDS = 48 * 60 * 60;
const RECEIPT_ID_PATTERN = /^[A-Za-z0-9-]{1,160}$/;
const UTC_TIMESTAMP_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isClosedRecord(value: unknown, expectedFields: readonly string[]): value is Record<string, unknown> {
  if (!isRecord(value)) return false;
  const ownKeys = Reflect.ownKeys(value);
  return ownKeys.length === expectedFields.length
    && ownKeys.every((key) => typeof key === 'string' && expectedFields.includes(key));
}

function isEnumValue<const Values extends readonly string[]>(
  value: unknown,
  values: Values,
): value is Values[number] {
  return typeof value === 'string' && values.includes(value);
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

function isBoundedCount(value: unknown): value is number {
  return typeof value === 'number'
    && Number.isSafeInteger(value)
    && value >= 0
    && value <= MAX_BOUNDED_INTEGER;
}

function isBoundedSignedInteger(value: unknown): value is number {
  return typeof value === 'number'
    && Number.isSafeInteger(value)
    && Math.abs(value) <= MAX_BOUNDED_INTEGER;
}

function isUtcTimestamp(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 32) return false;
  const match = UTC_TIMESTAMP_PATTERN.exec(value);
  if (!match) return false;
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) return false;
  const parsed = new Date(milliseconds);
  return parsed.getUTCFullYear() === Number(match[1])
    && parsed.getUTCMonth() + 1 === Number(match[2])
    && parsed.getUTCDate() === Number(match[3])
    && parsed.getUTCHours() === Number(match[4])
    && parsed.getUTCMinutes() === Number(match[5])
    && parsed.getUTCSeconds() === Number(match[6]);
}

function isNullableTimestamp(value: unknown): value is string | null {
  return value === null || isUtcTimestamp(value);
}

function isNullableBoundedCount(value: unknown): value is number | null {
  return value === null || isBoundedCount(value);
}

function isNullableBoundedSignedInteger(value: unknown): value is number | null {
  return value === null || isBoundedSignedInteger(value);
}

function isMetric(value: unknown): value is RailwayRetentionMetric {
  return isClosedRecord(value, METRIC_FIELDS)
    && isBoundedCount(value.postgres_database_bytes)
    && isBoundedCount(value.tracked_source_relation_bytes)
    && isBoundedCount(value.tracked_retention_overhead_bytes)
    && isBoundedCount(value.tracked_relation_bytes)
    && isBoundedCount(value.estimated_live_rows)
    && isBoundedCount(value.estimated_dead_rows)
    && isBoolean(value.row_counts_are_estimates)
    && isBoolean(value.physical_reclamation_claimed);
}

function copyMetric(value: RailwayRetentionMetric): RailwayRetentionMetric {
  return {
    postgres_database_bytes: value.postgres_database_bytes,
    tracked_source_relation_bytes: value.tracked_source_relation_bytes,
    tracked_retention_overhead_bytes: value.tracked_retention_overhead_bytes,
    tracked_relation_bytes: value.tracked_relation_bytes,
    estimated_live_rows: value.estimated_live_rows,
    estimated_dead_rows: value.estimated_dead_rows,
    row_counts_are_estimates: value.row_counts_are_estimates,
    physical_reclamation_claimed: value.physical_reclamation_claimed,
  };
}

function parsePlan(value: unknown): RailwayRetentionStatus['plan'] | null {
  if (!isClosedRecord(value, PLAN_FIELDS)) return null;
  const lifecycle = value.lifecycle_status;
  const receiptId = value.receipt_id;
  if (!isEnumValue(value.state, PLAN_STATES)
    || !isBoolean(value.receipt_present)
    || (lifecycle !== null && !isEnumValue(lifecycle, PLAN_LIFECYCLES))
    || (receiptId !== null && (typeof receiptId !== 'string' || !RECEIPT_ID_PATTERN.test(receiptId)))
    || !isNullableTimestamp(value.as_of)
    || !isNullableTimestamp(value.created_at)
    || !isNullableTimestamp(value.applied_at)
    || !isNullableTimestamp(value.rolled_back_at)
    || !isNullableBoundedCount(value.age_seconds)
    || !isBoolean(value.stale)
    || !isBoundedCount(value.candidate_rows)
    || !isBoundedCount(value.candidate_bytes)
    || !isBoundedCount(value.blocked_rows)
    || !isBoundedCount(value.local_archive_proof_count)) {
    return null;
  }
  if (value.receipt_present !== (value.state === 'present')) return null;
  if (value.state === 'missing' && (lifecycle !== null || receiptId !== null)) return null;
  if (value.state === 'present' && (lifecycle === null || receiptId === null)) return null;
  return {
    state: value.state,
    receipt_present: value.receipt_present,
    lifecycle_status: lifecycle,
    receipt_id: receiptId,
    as_of: value.as_of,
    created_at: value.created_at,
    applied_at: value.applied_at,
    rolled_back_at: value.rolled_back_at,
    age_seconds: value.age_seconds,
    stale: value.stale,
    candidate_rows: value.candidate_rows,
    candidate_bytes: value.candidate_bytes,
    blocked_rows: value.blocked_rows,
    local_archive_proof_count: value.local_archive_proof_count,
  };
}

function parseBackupBinding(value: unknown): RailwayRetentionStatus['backup_binding'] | null {
  if (!isClosedRecord(value, BACKUP_FIELDS)
    || !isEnumValue(value.state, BACKUP_STATES)
    || !isBoolean(value.bound)
    || !isBoolean(value.manifest_recorded)
    || !isBoolean(value.exact_plan_binding_recorded)
    || !isBoolean(value.local_reverification_required)) {
    return null;
  }
  const recorded = value.state === 'recorded_requires_local_reverification';
  if (value.bound !== recorded
    || value.manifest_recorded !== recorded
    || value.exact_plan_binding_recorded !== recorded
    || value.local_reverification_required !== true) {
    return null;
  }
  return {
    state: value.state,
    bound: value.bound,
    manifest_recorded: value.manifest_recorded,
    exact_plan_binding_recorded: value.exact_plan_binding_recorded,
    local_reverification_required: value.local_reverification_required,
  };
}

function parseAggregate(value: unknown): RailwayRetentionStatus['aggregate_compaction'] | null {
  if (!isClosedRecord(value, AGGREGATE_FIELDS)
    || !isEnumValue(value.state, AGGREGATE_STATES)
    || !isBoundedCount(value.expected_source_rows)
    || !isBoundedCount(value.aggregated_source_rows)
    || !isBoundedCount(value.aggregate_receipt_rows)
    || !isBoolean(value.matches)) {
    return null;
  }
  if ((value.state === 'ready' && !value.matches)
    || ((value.state === 'unavailable' || value.state === 'degraded') && value.matches)) {
    return null;
  }
  return {
    state: value.state,
    expected_source_rows: value.expected_source_rows,
    aggregated_source_rows: value.aggregated_source_rows,
    aggregate_receipt_rows: value.aggregate_receipt_rows,
    matches: value.matches,
  };
}

function parseRollback(value: unknown): RailwayRetentionStatus['rollback'] | null {
  if (!isClosedRecord(value, ROLLBACK_FIELDS)
    || !isEnumValue(value.state, ROLLBACK_STATES)
    || !isBoolean(value.ready)
    || !isBoundedCount(value.row_receipts)
    || !isBoundedCount(value.aggregate_receipts)
    || !isBoolean(value.requires_isolated_backup_revalidation)) {
    return null;
  }
  const completed = value.state === 'completed';
  if (value.ready !== completed || value.requires_isolated_backup_revalidation === completed) return null;
  return {
    state: value.state,
    ready: value.ready,
    row_receipts: value.row_receipts,
    aggregate_receipts: value.aggregate_receipts,
    requires_isolated_backup_revalidation: value.requires_isolated_backup_revalidation,
  };
}

function parseCost(value: unknown): RailwayRetentionStatus['cost'] | null {
  if (!isClosedRecord(value, COST_FIELDS)
    || !isEnumValue(value.state, COST_STATES)
    || (value.before !== null && !isMetric(value.before))
    || (value.after !== null && !isMetric(value.after))
    || !isNullableBoundedSignedInteger(value.logical_bytes_reduced)
    || !isBoolean(value.logical_reduction_proven)
    || !isClosedRecord(value.physical, PHYSICAL_FIELDS)
    || !isNullableBoundedCount(value.physical.railway_volume_before_bytes)
    || !isNullableBoundedCount(value.physical.railway_volume_after_bytes)
    || !isBoolean(value.physical.measured)
    || !isBoolean(value.physical.reclamation_claimed)
    || !isBoolean(value.cost_reduction_proven)) {
    return null;
  }
  const before = value.before === null ? null : copyMetric(value.before);
  const after = value.after === null ? null : copyMetric(value.after);
  const expectedCostState = before === null
    ? 'unmeasured'
    : after === null
      ? 'before_only'
      : 'measured_logical_only';
  if (value.state !== expectedCostState) return null;
  if (value.logical_reduction_proven !== (
    value.logical_bytes_reduced !== null && value.logical_bytes_reduced > 0
  )) return null;

  const volumeBefore = value.physical.railway_volume_before_bytes;
  const volumeAfter = value.physical.railway_volume_after_bytes;
  const physicalMeasured = volumeBefore !== null && volumeAfter !== null;
  if (value.physical.measured !== physicalMeasured) return null;
  if (value.physical.reclamation_claimed && !physicalMeasured) return null;
  const reductionProven = physicalMeasured
    && volumeBefore > volumeAfter
    && value.physical.reclamation_claimed;
  if (value.cost_reduction_proven !== reductionProven) return null;

  return {
    state: value.state,
    before,
    after,
    logical_bytes_reduced: value.logical_bytes_reduced,
    logical_reduction_proven: value.logical_reduction_proven,
    physical: {
      railway_volume_before_bytes: volumeBefore,
      railway_volume_after_bytes: volumeAfter,
      measured: value.physical.measured,
      reclamation_claimed: value.physical.reclamation_claimed,
    },
    cost_reduction_proven: value.cost_reduction_proven,
  };
}

function parseRules(value: unknown): RailwayRetentionStatus['rules'] | null {
  if (!Array.isArray(value) || value.length > MAX_RULES) return null;
  const parsed: RailwayRetentionStatus['rules'] = [];
  const seenRules = new Set<string>();
  for (const rule of value) {
    if (!isClosedRecord(rule, RULE_FIELDS)
      || !isEnumValue(rule.rule, SAFE_RULE_NAMES)
      || !isEnumValue(rule.state, SAFE_RULE_STATES)
      || !isBoundedCount(rule.candidate_rows)
      || !isBoundedCount(rule.candidate_bytes)
      || !isBoundedCount(rule.blocked_rows)
      || !isBoundedCount(rule.affected_rows)
      || (rule.reason_code !== null && !isEnumValue(rule.reason_code, SAFE_RULE_REASONS))
      || seenRules.has(rule.rule)) {
      return null;
    }
    seenRules.add(rule.rule);
    parsed.push({
      rule: rule.rule,
      state: rule.state,
      candidate_rows: rule.candidate_rows,
      candidate_bytes: rule.candidate_bytes,
      blocked_rows: rule.blocked_rows,
      affected_rows: rule.affected_rows,
      reason_code: rule.reason_code,
    });
  }
  return parsed;
}

function hasClosedPrivacySentinel(value: unknown): boolean {
  return isClosedRecord(value, PRIVACY_FIELDS)
    && value.source_rows_returned === false
    && value.source_identifiers_returned === false
    && value.private_payloads_returned === false
    && value.provider_errors_returned === false;
}

/**
 * Parses the authenticated backend receipt into a fresh, bounded UI projection.
 * The backend privacy sentinel must be present and all false, but it is deliberately
 * omitted from the returned UI object so the consumer never retains the input envelope.
 */
export function normalizeRailwayRetentionStatus(value: unknown): RailwayRetentionStatus | null {
  try {
    if (!isClosedRecord(value, STATUS_FIELDS)
      || value.schema_version !== 'railway_retention_status_projection/v1'
      || !isEnumValue(value.state, STATUS_STATES)
      || !isBoolean(value.ready)
      || value.ready !== (value.state === 'ready')
      || !isUtcTimestamp(value.checked_at)
      || value.stale_after_seconds !== STALE_AFTER_SECONDS
      || !Array.isArray(value.reason_codes)
      || value.reason_codes.length > SAFE_REASON_CODES.length
      || !value.reason_codes.every((reason) => isEnumValue(reason, SAFE_REASON_CODES))
      || new Set(value.reason_codes).size !== value.reason_codes.length
      || !hasClosedPrivacySentinel(value.privacy)) {
      return null;
    }

    const plan = parsePlan(value.plan);
    const backupBinding = parseBackupBinding(value.backup_binding);
    const aggregateCompaction = parseAggregate(value.aggregate_compaction);
    const rollback = parseRollback(value.rollback);
    const cost = parseCost(value.cost);
    const rules = parseRules(value.rules);
    if (!plan || !backupBinding || !aggregateCompaction || !rollback || !cost || !rules) return null;

    return {
      schema_version: 'railway_retention_status_projection/v1',
      state: value.state,
      ready: value.ready,
      checked_at: value.checked_at,
      stale_after_seconds: STALE_AFTER_SECONDS,
      reason_codes: [...value.reason_codes],
      plan,
      backup_binding: backupBinding,
      aggregate_compaction: aggregateCompaction,
      rollback,
      cost,
      rules,
    };
  } catch {
    return null;
  }
}
