import { normalizeRailwayRetentionStatus } from './railwayRetentionStatus';

export { normalizeRailwayRetentionStatus };

export type RailwayRetentionMetric = {
  postgres_database_bytes: number;
  tracked_source_relation_bytes: number;
  tracked_retention_overhead_bytes: number;
  tracked_relation_bytes: number;
  estimated_live_rows: number;
  estimated_dead_rows: number;
  row_counts_are_estimates: boolean;
  physical_reclamation_claimed: boolean;
};

export type RailwayRetentionStatus = {
  schema_version: 'railway_retention_status_projection/v1';
  state: 'ready' | 'degraded' | 'blocked';
  ready: boolean;
  checked_at: string;
  stale_after_seconds: number;
  reason_codes: string[];
  plan: {
    state: string;
    receipt_present: boolean;
    lifecycle_status: string | null;
    receipt_id: string | null;
    as_of: string | null;
    created_at: string | null;
    applied_at: string | null;
    rolled_back_at: string | null;
    age_seconds: number | null;
    stale: boolean;
    candidate_rows: number;
    candidate_bytes: number;
    blocked_rows: number;
    local_archive_proof_count: number;
  };
  backup_binding: {
    state: string;
    bound: boolean;
    manifest_recorded: boolean;
    exact_plan_binding_recorded: boolean;
    local_reverification_required: boolean;
  };
  aggregate_compaction: {
    state: string;
    expected_source_rows: number;
    aggregated_source_rows: number;
    aggregate_receipt_rows: number;
    matches: boolean;
  };
  rollback: {
    state: string;
    ready: boolean;
    row_receipts: number;
    aggregate_receipts: number;
    requires_isolated_backup_revalidation: boolean;
  };
  cost: {
    state: string;
    before: RailwayRetentionMetric | null;
    after: RailwayRetentionMetric | null;
    logical_bytes_reduced: number | null;
    logical_reduction_proven: boolean;
    physical: {
      railway_volume_before_bytes: number | null;
      railway_volume_after_bytes: number | null;
      measured: boolean;
      reclamation_claimed: boolean;
    };
    cost_reduction_proven: boolean;
  };
  rules: Array<{
    rule: string;
    state: string;
    candidate_rows: number;
    candidate_bytes: number;
    blocked_rows: number;
    affected_rows: number;
    reason_code: string | null;
  }>;
};

function formatCount(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? new Intl.NumberFormat('en-US').format(value) : '—';
}

function formatBytes(value: number | null | undefined) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not measured';
  if (Math.abs(value) < 1024) return `${formatCount(value)} B`;
  if (Math.abs(value) < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function humanize(value: string | null | undefined) {
  return (value || 'unknown').replaceAll('_', ' ');
}

function statusColor(state: string) {
  if (state === 'ready' || state === 'applied' || state === 'completed') return '#4ade80';
  if (state.includes('blocked') || state === 'missing') return '#fb7185';
  return '#fbbf24';
}

function Fact({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={{ border: '1px solid #1f2937', borderRadius: '14px', background: '#0f172a', padding: '13px' }}>
      <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{label}</p>
      <p style={{ color: 'white', fontSize: '17px', fontWeight: 700, marginTop: '5px' }}>{value}</p>
      <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.45, marginTop: '4px' }}>{detail}</p>
    </div>
  );
}

export default function RailwayRetentionHealthPanel({
  receipt,
  error,
}: {
  receipt: RailwayRetentionStatus | null;
  error: string | null;
}) {
  if (error) {
    return (
      <section style={{ borderRadius: '18px', border: '1px solid rgba(251,113,133,0.45)', background: '#0b1324', padding: '20px' }}>
        <h3 style={{ color: 'white', fontSize: '20px' }}>Railway retention and cost</h3>
        <p role="alert" style={{ color: '#fb7185', marginTop: '8px' }}>
          Retention health is unavailable: {error}
        </p>
        <p style={{ color: '#94a3b8', marginTop: '8px', fontSize: '13px' }}>
          No storage reduction, backup binding, or rollback readiness is being inferred while this read fails.
        </p>
      </section>
    );
  }

  const state = receipt?.state ?? 'blocked';
  const reasonText = receipt?.reason_codes.length ? receipt.reason_codes.map(humanize).join(' · ') : 'No reported blockers';
  const beforeBytes = receipt?.cost.before?.postgres_database_bytes ?? null;
  const afterBytes = receipt?.cost.after?.postgres_database_bytes ?? null;
  const physicalMeasured = receipt?.cost.physical.measured === true;

  return (
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', background: '#0b1324', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <p style={{ color: '#94a3b8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Railway storage control</p>
          <h3 style={{ color: 'white', fontSize: '20px', margin: '5px 0' }}>Retention, backup, rollback, and cost proof</h3>
          <p style={{ color: '#64748b', fontSize: '13px', maxWidth: '760px', lineHeight: 1.5 }}>
            This view reports compact receipt facts only. It does not claim a lower bill, physical reclamation, or rollback readiness without the matching evidence.
          </p>
        </div>
        <div role="status" style={{ textAlign: 'right' }}>
          <p style={{ color: statusColor(state), fontSize: '18px', fontWeight: 700, textTransform: 'capitalize' }}>{state}</p>
          <p style={{ color: '#64748b', fontSize: '12px' }}>{receipt?.checked_at ? new Date(receipt.checked_at).toLocaleString() : 'Not verified'}</p>
        </div>
      </div>

      <p style={{ color: state === 'ready' ? '#86efac' : '#fbbf24', fontSize: '12px', marginBottom: '14px' }}>{reasonText}</p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '10px', marginBottom: '16px' }}>
        <Fact
          label="Plan state"
          value={humanize(receipt?.plan.lifecycle_status)}
          detail={`${formatCount(receipt?.plan.candidate_rows)} candidates · ${formatCount(receipt?.plan.blocked_rows)} blocked`}
        />
        <Fact
          label="Local archive proofs"
          value={formatCount(receipt?.plan.local_archive_proof_count)}
          detail="Exact row/source bindings in the persisted plan"
        />
        <Fact
          label="Backup binding"
          value={receipt?.backup_binding.bound ? 'Recorded' : 'Missing'}
          detail={receipt?.backup_binding.local_reverification_required ? 'Local artifact must be reverified before rollback' : 'Exact artifact verified'}
        />
        <Fact
          label="Aggregate compaction"
          value={humanize(receipt?.aggregate_compaction.state)}
          detail={`${formatCount(receipt?.aggregate_compaction.aggregated_source_rows)} / ${formatCount(receipt?.aggregate_compaction.expected_source_rows)} source rows bound`}
        />
        <Fact
          label="Rollback"
          value={receipt?.rollback.ready ? 'Ready' : humanize(receipt?.rollback.state)}
          detail={`${formatCount(receipt?.rollback.row_receipts)} row receipts · ${formatCount(receipt?.rollback.aggregate_receipts)} aggregates`}
        />
      </div>

      <div style={{ borderTop: '1px solid #1f2937', paddingTop: '14px', marginBottom: '16px' }}>
        <h4 style={{ color: 'white', fontSize: '16px', marginBottom: '10px' }}>Before and after cost facts</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
          <Fact label="Postgres before" value={formatBytes(beforeBytes)} detail="Recorded pg_database_size at plan time" />
          <Fact label="Postgres after" value={formatBytes(afterBytes)} detail="Recorded after the exact retention transaction" />
          <Fact
            label="Logical reduction"
            value={formatBytes(receipt?.cost.logical_bytes_reduced)}
            detail={receipt?.cost.logical_reduction_proven ? 'Measured lower logical bytes' : 'No positive reduction is proven'}
          />
          <Fact
            label="Railway volume / bill"
            value={physicalMeasured ? 'Measured' : 'Not measured'}
            detail={receipt?.cost.cost_reduction_proven ? 'Lower cost proven' : 'Physical reclamation and lower bill remain unproven'}
          />
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Retention lane', 'State', 'Candidates', 'Blocked', 'Affected', 'Reason'].map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '8px 10px 8px 0', borderBottom: '1px solid #1f2937' }}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(receipt?.rules ?? []).length === 0 ? (
              <tr><td colSpan={6} style={{ color: '#fbbf24', padding: '12px 0' }}>No persisted retention plan is available.</td></tr>
            ) : (
              receipt?.rules.map((rule) => (
                <tr key={rule.rule}>
                  <td style={{ color: 'white', padding: '10px 10px 10px 0', borderBottom: '1px solid #162033' }}>{humanize(rule.rule)}</td>
                  <td style={{ color: statusColor(rule.state), padding: '10px 10px 10px 0', borderBottom: '1px solid #162033' }}>{humanize(rule.state)}</td>
                  <td style={{ color: '#cbd5e1', padding: '10px 10px 10px 0', borderBottom: '1px solid #162033' }}>{formatCount(rule.candidate_rows)}</td>
                  <td style={{ color: '#cbd5e1', padding: '10px 10px 10px 0', borderBottom: '1px solid #162033' }}>{formatCount(rule.blocked_rows)}</td>
                  <td style={{ color: '#cbd5e1', padding: '10px 10px 10px 0', borderBottom: '1px solid #162033' }}>{formatCount(rule.affected_rows)}</td>
                  <td style={{ color: '#94a3b8', padding: '10px 0', borderBottom: '1px solid #162033' }}>{humanize(rule.reason_code)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
