import {
  criticReviewForOption,
  editorialReadinessLabel,
  type GeneratedContentDiagnostics,
} from '@/app/workspace/generatedFragmentUtils';

function humanize(value?: string | null) {
  return String(value ?? '').trim().replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function readinessTone(status?: string, ready?: boolean) {
  if (ready) return '#34d399';
  if (status === 'blocked') return '#f87171';
  return '#fbbf24';
}

function ReceiptBadge({ label, tone = '#94a3b8' }: { label: string; tone?: string }) {
  return (
    <span
      style={{
        border: `1px solid ${tone}55`,
        borderRadius: '999px',
        color: tone,
        fontSize: '10px',
        fontWeight: 700,
        letterSpacing: '0.03em',
        padding: '4px 8px',
        textTransform: 'uppercase',
      }}
    >
      {label}
    </span>
  );
}

export function isOptionEditoriallyReady(diagnostics: GeneratedContentDiagnostics | undefined, optionIndex: number) {
  const review = criticReviewForOption(diagnostics?.editorial_readiness, optionIndex);
  if (review?.editorially_ready !== true) return false;
  if (diagnostics?.revision_contract?.schema_version === 'feezie_critic_guided_revision_contract/v1') {
    const revision = diagnostics.revision_execution;
    if (
      revision?.schema_version !== 'feezie_revision_execution_receipt/v1'
      || !['not_required', 'completed'].includes(revision.status ?? '')
      || revision.retry_allowed !== false
      || revision.contains_post_copy !== false
      || revision.contains_critic_issue_copy !== false
    ) return false;
    if (revision.status === 'not_required' && (revision.revision_call_count !== 0 || revision.final_critic_call_count !== 0)) return false;
    if (revision.status === 'completed' && (revision.revision_call_count ?? 0) < 1) return false;
    if (revision.status === 'completed' && revision.final_critic_call_count !== 1) return false;
  }
  const contract = diagnostics?.draft_contract;
  if (contract?.schema_version !== 'feezie_draft_contract/v1') return true;
  const expectedHooks = contract.hook_variants_per_option ?? 8;
  return (
    diagnostics?.draft_distinctness?.passed === true
    && diagnostics?.critic_review?.draft_distinctness?.passed === true
    && review.hook_variants?.length === expectedHooks
  );
}

export function GenerationReceiptSummary({ diagnostics }: { diagnostics?: GeneratedContentDiagnostics }) {
  if (!diagnostics) return null;
  const readiness = diagnostics.editorial_readiness;
  const classification = diagnostics.candidate_classification;
  const strategy = diagnostics.strategy_contract;
  const freshness = classification?.source_freshness;
  const draftContract = diagnostics.draft_contract;
  const deterministicDistinctness = diagnostics.draft_distinctness;
  const criticDistinctness = diagnostics.critic_review?.draft_distinctness;
  const revision = diagnostics.revision_execution;
  const expectedDrafts = draftContract?.required_option_count;
  const actualDrafts = diagnostics.technical_completion?.draft_count ?? deterministicDistinctness?.actual_option_count;
  const expectedHooks = draftContract?.hook_variants_per_option;
  const criticReviews = diagnostics.critic_review?.reviews ?? [];
  const completeCriticCoverage = Boolean(
    expectedDrafts
    && expectedHooks
    && criticReviews.length === expectedDrafts
    && criticReviews.every((review) => review.hook_variants?.length === expectedHooks),
  );
  const tone = readinessTone(readiness?.status, readiness?.ready);
  const badges = [
    diagnostics.intent ? `Intent ${humanize(diagnostics.intent)}` : null,
    strategy?.contract_hash ? `Contract ${strategy.contract_hash.slice(0, 8)}` : 'Contract unavailable',
    classification?.canonical_pillar ? `Pillar ${humanize(classification.canonical_pillar)}` : null,
    classification?.employer_safety ? `Safety ${humanize(classification.employer_safety)}` : null,
    classification?.proof_posture ? `Proof ${humanize(classification.proof_posture)}` : null,
    freshness?.state
      ? `Source ${humanize(freshness.state)}${typeof freshness.age_days === 'number' ? ` · ${freshness.age_days}d` : ''}`
      : null,
    expectedDrafts ? `Drafts ${actualDrafts ?? 0}/${expectedDrafts}` : null,
    deterministicDistinctness
      ? `Deterministic distinction ${deterministicDistinctness.passed ? 'passed' : 'failed'}`
      : null,
    criticDistinctness
      ? `Critic distinction ${criticDistinctness.passed ? 'passed' : 'failed'}`
      : null,
    expectedDrafts && expectedHooks
      ? `Critic + hooks ${completeCriticCoverage ? `${expectedDrafts}/${expectedDrafts} · ${expectedHooks} each` : 'incomplete'}`
      : null,
    revision?.schema_version === 'feezie_revision_execution_receipt/v1'
      ? revision.status === 'not_required'
        ? 'Revision not required · 0 calls'
        : revision.status === 'completed'
          ? `Revision completed · ${revision.revision_call_count ?? 0} target call${revision.revision_call_count === 1 ? '' : 's'} · fresh critic ${revision.final_critic_call_count ?? 0}/1`
          : `Revision failed · ${revision.revision_call_count ?? 0} attempted`
      : diagnostics.revision_contract?.schema_version === 'feezie_critic_guided_revision_contract/v1'
        ? 'Revision receipt unavailable'
        : null,
  ].filter((value): value is string => Boolean(value));

  return (
    <div style={{ border: `1px solid ${tone}44`, borderRadius: '12px', backgroundColor: '#07101f', padding: '12px', display: 'grid', gap: '9px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ color: tone, fontSize: '12px' }}>{editorialReadinessLabel(readiness)}</strong>
        <span style={{ color: '#64748b', fontSize: '11px' }}>
          Technical completion is separate from editorial readiness.
        </span>
      </div>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {badges.map((badge) => <ReceiptBadge key={badge} label={badge} />)}
      </div>
      {(readiness?.blocking_reasons?.length ?? 0) > 0 && (
        <p style={{ color: '#fbbf24', fontSize: '11px', margin: 0 }}>
          Blocking reasons: {readiness?.blocking_reasons?.map(humanize).join(' · ')}
        </p>
      )}
      {revision?.status === 'not_required' && (
        <p style={{ color: '#94a3b8', fontSize: '11px', margin: 0 }}>
          The initial critic cleared both options, so no revision or second critic call was needed.
        </p>
      )}
      {revision?.status === 'completed' && (
        <p style={{ color: '#94a3b8', fontSize: '11px', margin: 0 }}>
          Only the non-ready target {revision.revision_call_count === 1 ? 'was' : 'options were'} revised once. The displayed verdicts come from the fresh final critic.
        </p>
      )}
      {revision?.status === 'failed' && (
        <p style={{ color: '#f87171', fontSize: '11px', margin: 0 }}>
          Revision stopped closed: {humanize(revision.failure_code || 'revision contract failed')}. No option can advance from the earlier critic.
        </p>
      )}
      {(deterministicDistinctness?.failed_reasons?.length ?? 0) > 0 && (
        <p style={{ color: '#fbbf24', fontSize: '11px', margin: 0 }}>
          Draft distinction: {deterministicDistinctness?.failed_reasons?.map(humanize).join(' · ')}
        </p>
      )}
      {criticDistinctness?.reason && (
        <p style={{ color: criticDistinctness.passed ? '#94a3b8' : '#fbbf24', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
          Independent critic on distinction: {criticDistinctness.reason}
        </p>
      )}
      {classification?.audience_consequence && (
        <p style={{ color: '#94a3b8', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
          Audience consequence: {classification.audience_consequence}
        </p>
      )}
    </div>
  );
}

export function OptionCriticReceipt({
  diagnostics,
  optionIndex,
}: {
  diagnostics?: GeneratedContentDiagnostics;
  optionIndex: number;
}) {
  const review = criticReviewForOption(diagnostics?.editorial_readiness, optionIndex);
  if (!review) {
    return (
      <p style={{ color: '#fbbf24', fontSize: '11px', margin: 0 }}>
        No independent critic receipt is attached to this option.
      </p>
    );
  }
  const ready = review.editorially_ready === true;
  const tone = ready ? '#34d399' : review.verdict === 'blocked' ? '#f87171' : '#fbbf24';
  const dimensions = Object.entries(review.dimension_scores ?? {});
  const expectedHooks = diagnostics?.draft_contract?.hook_variants_per_option ?? 8;
  const hookCount = review.hook_variants?.length ?? 0;
  const revisionRow = diagnostics?.revision_execution?.options?.find(
    (item) => item.canonical_option_index === optionIndex + 1,
  );
  const revisionLabel = revisionRow?.action === 'revised'
    ? 'Revised once'
    : revisionRow?.action === 'revision_failed'
      ? 'Revision failed'
      : revisionRow?.action === 'preserved'
        ? 'Original preserved'
        : null;
  const revisionTone = revisionRow?.action === 'revised'
    ? '#38bdf8'
    : revisionRow?.action === 'revision_failed'
      ? '#f87171'
      : '#94a3b8';

  return (
    <div style={{ border: `1px solid ${tone}33`, borderRadius: '10px', padding: '10px', display: 'grid', gap: '8px' }}>
      <div style={{ display: 'flex', gap: '7px', alignItems: 'center', flexWrap: 'wrap' }}>
        <ReceiptBadge label={ready ? 'Editorially ready' : humanize(review.verdict || 'Needs revision')} tone={tone} />
        <ReceiptBadge label={`Critic ${review.score ?? 'n/a'}/10`} tone={tone} />
        {revisionLabel && <ReceiptBadge label={revisionLabel} tone={revisionTone} />}
        {dimensions.map(([dimension, score]) => (
          <ReceiptBadge key={dimension} label={`${humanize(dimension)} ${score}/10`} />
        ))}
      </div>
      {(review.issues?.length ?? 0) > 0 && (
        <ul style={{ color: '#fbbf24', fontSize: '11px', lineHeight: 1.5, margin: 0, paddingLeft: '18px' }}>
          {review.issues?.map((issue) => <li key={issue}>{issue}</li>)}
        </ul>
      )}
      {hookCount > 0 && (
        <details>
          <summary style={{ color: '#93c5fd', cursor: 'pointer', fontSize: '11px', fontWeight: 700 }}>
            Hook lab · {hookCount}/{expectedHooks} evidence-bounded alternatives
          </summary>
          <ol style={{ color: '#cbd5e1', fontSize: '11px', lineHeight: 1.55, margin: '8px 0 0', paddingLeft: '20px' }}>
            {review.hook_variants?.map((hook) => <li key={hook}>{hook}</li>)}
          </ol>
          <p style={{ color: '#64748b', fontSize: '10px', margin: '7px 0 0' }}>
            These are suggestions only. A changed hook must be re-reviewed before owner handoff.
          </p>
        </details>
      )}
      {hookCount !== expectedHooks && (
        <p style={{ color: '#fbbf24', fontSize: '10px', margin: 0 }}>
          Owner handoff requires exactly {expectedHooks} unique hooks for this independently criticized draft.
        </p>
      )}
    </div>
  );
}
