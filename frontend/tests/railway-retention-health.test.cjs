const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const opsSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const panelSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'ops', 'RailwayRetentionHealthPanel.tsx'), 'utf8');
const parserSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'ops', 'railwayRetentionStatus.ts'), 'utf8');
const parserCompiled = ts.transpileModule(parserSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const parserModule = { exports: {} };
new Function('module', 'exports', 'require', parserCompiled)(parserModule, parserModule.exports, require);
const { normalizeRailwayRetentionStatus } = parserModule.exports;

function metric(databaseBytes) {
  return {
    postgres_database_bytes: databaseBytes,
    tracked_source_relation_bytes: databaseBytes - 10_000,
    tracked_retention_overhead_bytes: 4_000,
    tracked_relation_bytes: databaseBytes - 6_000,
    estimated_live_rows: 21,
    estimated_dead_rows: 5,
    row_counts_are_estimates: true,
    physical_reclamation_claimed: false,
  };
}

function validStatus() {
  return {
    schema_version: 'railway_retention_status_projection/v1',
    state: 'degraded',
    ready: false,
    checked_at: '2026-08-21T12:00:00Z',
    stale_after_seconds: 172_800,
    reason_codes: [
      'retention_apply_partial',
      'retention_backup_requires_local_reverification',
      'retention_rollback_requires_local_backup',
      'retention_physical_cost_unmeasured',
    ],
    plan: {
      state: 'present',
      receipt_present: true,
      lifecycle_status: 'partially_applied',
      receipt_id: 'receipt-1',
      as_of: '2026-08-21T10:00:00Z',
      created_at: '2026-08-21T11:00:00.123456Z',
      applied_at: '2026-08-21T11:30:00Z',
      rolled_back_at: null,
      age_seconds: 3_600,
      stale: false,
      candidate_rows: 12,
      candidate_bytes: 70_000,
      blocked_rows: 2,
      local_archive_proof_count: 2,
    },
    backup_binding: {
      state: 'recorded_requires_local_reverification',
      bound: true,
      manifest_recorded: true,
      exact_plan_binding_recorded: true,
      local_reverification_required: true,
    },
    aggregate_compaction: {
      state: 'ready',
      expected_source_rows: 10,
      aggregated_source_rows: 10,
      aggregate_receipt_rows: 3,
      matches: true,
    },
    rollback: {
      state: 'requires_local_backup_reverification',
      ready: false,
      row_receipts: 2,
      aggregate_receipts: 3,
      requires_isolated_backup_revalidation: true,
    },
    cost: {
      state: 'measured_logical_only',
      before: metric(120_000_000),
      after: metric(90_000_000),
      logical_bytes_reduced: 30_000_000,
      logical_reduction_proven: true,
      physical: {
        railway_volume_before_bytes: null,
        railway_volume_after_bytes: null,
        measured: false,
        reclamation_claimed: false,
      },
      cost_reduction_proven: false,
    },
    rules: [{
      rule: 'automation_non_action_detail',
      state: 'partially_applied',
      candidate_rows: 10,
      candidate_bytes: 50_000,
      blocked_rows: 2,
      affected_rows: 8,
      reason_code: 'unresolved_nonhealthy_rows_retained',
    }],
    privacy: {
      source_rows_returned: false,
      source_identifiers_returned: false,
      private_payloads_returned: false,
      provider_errors_returned: false,
    },
  };
}

function mutate(pathParts, replacement) {
  const value = structuredClone(validStatus());
  let target = value;
  for (const part of pathParts.slice(0, -1)) target = target[part];
  target[pathParts.at(-1)] = replacement;
  return value;
}

test('Ops System loads retention through the authenticated no-store control plane', () => {
  assert.match(opsSource, /controlApiGet<unknown>\('\/api\/system\/railway-retention'/);
  assert.match(opsSource, /cache: API_NO_STORE/);
  assert.match(opsSource, /normalizeRailwayRetentionStatus\(value\)/);
  assert.match(opsSource, /updateSectionError\('retention'/);
  assert.match(opsSource, /<RailwayRetentionHealthPanel receipt=\{railwayRetention\} error=\{railwayRetentionError\} \/>/);
});

test('retention panel renders plan, backup, aggregate, rollback, and before-after cost facts', () => {
  for (const label of [
    'Plan state',
    'Local archive proofs',
    'Backup binding',
    'Aggregate compaction',
    'Rollback',
    'Before and after cost facts',
    'Postgres before',
    'Postgres after',
    'Logical reduction',
    'Railway volume / bill',
  ]) {
    assert.match(panelSource, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('retention panel keeps blocked, degraded, stale, and unmeasured evidence honest', () => {
  assert.match(panelSource, /state: 'ready' \| 'degraded' \| 'blocked'/);
  assert.match(panelSource, /No storage reduction, backup binding, or rollback readiness is being inferred/);
  assert.match(panelSource, /No positive reduction is proven/);
  assert.match(panelSource, /Physical reclamation and lower bill remain unproven/);
  assert.match(panelSource, /No persisted retention plan is available/);
  assert.doesNotMatch(panelSource, /cost_reduction_proven \? 'Estimated'/);
});

test('retention browser projection has no source bodies, identifiers, manifests, or provider errors', () => {
  assert.doesNotMatch(panelSource, /source_record|source_row_sha256|artifact_relative_path|manifest_sha256|backup_manifest_sha256/);
  assert.doesNotMatch(panelSource, /provider_errors/);
  assert.match(panelSource, /receipt\.reason_codes/);
  assert.match(panelSource, /rule\.reason_code/);
  assert.match(parserSource, /hasClosedPrivacySentinel/);
  assert.doesNotMatch(parserSource, /return value as RailwayRetentionStatus/);
});

test('runtime parser returns a fresh bounded UI projection for a valid receipt', () => {
  const input = validStatus();
  const result = normalizeRailwayRetentionStatus(input);
  assert.ok(result);
  assert.notStrictEqual(result, input);
  assert.notStrictEqual(result.plan, input.plan);
  assert.notStrictEqual(result.cost, input.cost);
  assert.notStrictEqual(result.cost.before, input.cost.before);
  assert.notStrictEqual(result.rules, input.rules);
  assert.notStrictEqual(result.rules[0], input.rules[0]);
  assert.equal(Object.hasOwn(result, 'privacy'), false);
  assert.equal(JSON.stringify(result).includes('private_payloads_returned'), false);
  assert.equal(result.plan.lifecycle_status, 'partially_applied');
  assert.equal(result.cost.logical_bytes_reduced, 30_000_000);
});

test('runtime parser rejects every top-level or nested extra/private field', () => {
  const topLevel = validStatus();
  topLevel.private_source_body = 'must not cross the browser boundary';
  const plan = validStatus();
  plan.plan.provider_error = 'private connection detail';
  const metricValue = validStatus();
  metricValue.cost.before.private_relation_names = ['secret_table'];
  const physical = validStatus();
  physical.cost.physical.provider_invoice = 'private bill';
  const rule = validStatus();
  rule.rules[0].source_identifiers = ['private-id'];
  const privacyExtra = validStatus();
  privacyExtra.privacy.source_body = 'private';
  const privacyViolation = mutate(['privacy', 'provider_errors_returned'], true);

  for (const candidate of [topLevel, plan, metricValue, physical, rule, privacyExtra, privacyViolation]) {
    assert.equal(normalizeRailwayRetentionStatus(candidate), null);
  }
});

test('runtime parser rejects oversized strings, arrays, and integers', () => {
  const tooManyRules = validStatus();
  tooManyRules.rules = Array.from({ length: 17 }, () => structuredClone(tooManyRules.rules[0]));
  const tooManyReasons = validStatus();
  tooManyReasons.reason_codes = Array.from({ length: 13 }, () => 'retention_plan_stale');

  for (const candidate of [
    mutate(['plan', 'receipt_id'], 'a'.repeat(161)),
    mutate(['checked_at'], `2026-08-21T12:00:00.${'1'.repeat(40)}Z`),
    mutate(['plan', 'candidate_bytes'], 1_000_000_000_000_001),
    tooManyRules,
    tooManyReasons,
  ]) {
    assert.equal(normalizeRailwayRetentionStatus(candidate), null);
  }
});

test('runtime parser rejects malformed nested values and timestamps', () => {
  for (const candidate of [
    mutate(['plan'], []),
    mutate(['cost', 'physical'], null),
    mutate(['cost', 'before', 'row_counts_are_estimates'], 'yes'),
    mutate(['checked_at'], '2026-02-30T12:00:00Z'),
    mutate(['plan', 'created_at'], 'not-a-timestamp'),
    mutate(['privacy'], { source_rows_returned: false }),
  ]) {
    assert.equal(normalizeRailwayRetentionStatus(candidate), null);
  }
});

test('runtime parser rejects nonfinite, fractional, and negative bounded facts', () => {
  for (const candidate of [
    mutate(['plan', 'candidate_rows'], -1),
    mutate(['plan', 'candidate_rows'], 1.5),
    mutate(['cost', 'before', 'postgres_database_bytes'], Number.POSITIVE_INFINITY),
    mutate(['cost', 'physical', 'railway_volume_before_bytes'], Number.NaN),
    mutate(['cost', 'logical_bytes_reduced'], Number.NEGATIVE_INFINITY),
  ]) {
    assert.equal(normalizeRailwayRetentionStatus(candidate), null);
  }
});

test('runtime parser rejects invalid lifecycle values and inconsistent state claims', () => {
  for (const candidate of [
    mutate(['state'], 'healthy'),
    mutate(['ready'], true),
    mutate(['plan', 'lifecycle_status'], 'deleted'),
    mutate(['plan', 'receipt_present'], false),
    mutate(['backup_binding', 'state'], 'verified'),
    mutate(['aggregate_compaction', 'matches'], false),
    mutate(['rollback', 'state'], 'completed'),
    mutate(['cost', 'state'], 'unmeasured'),
    mutate(['rules', 0, 'state'], 'executed'),
  ]) {
    assert.equal(normalizeRailwayRetentionStatus(candidate), null);
  }
});
