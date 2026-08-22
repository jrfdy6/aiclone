import {
  criticReviewForOption,
  editorialReadinessLabel,
  type GeneratedContentDiagnostics,
} from '@/app/workspace/generatedFragmentUtils';

function humanize(value?: string | null) {
  return String(value ?? '').trim().replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

type CriticReceiptState = {
  badges: string[];
  detail: string;
  reviewReceiptUsable: boolean;
  reviewStageLabel: 'Initial' | 'Final' | 'Critic';
};

function normalizedStatus(value?: string | null) {
  return String(value ?? '').trim().toLowerCase();
}

export function buildCriticReceiptState(
  diagnostics: GeneratedContentDiagnostics | undefined,
): CriticReceiptState {
  const revisionContractEnabled = diagnostics?.revision_contract?.schema_version
    === 'feezie_critic_guided_revision_contract/v1';
  const revision = diagnostics?.revision_execution;
  const criticStatus = normalizedStatus(
    diagnostics?.critic_review?.status || diagnostics?.editorial_readiness?.critic_status,
  );
  const criticCompleted = criticStatus === 'completed';

  if (revisionContractEnabled && revision?.schema_version !== 'feezie_revision_execution_receipt/v1') {
    return {
      badges: ['Initial critic state unavailable', 'Final critic not run'],
      detail: 'The revision receipt is unavailable, so initial and final critic completion cannot be verified. Reviews and hooks are unavailable for owner handoff.',
      reviewReceiptUsable: false,
      reviewStageLabel: 'Final',
    };
  }

  if (revision?.schema_version === 'feezie_revision_execution_receipt/v1') {
    if (revision.status === 'not_required') {
      const initialCompleted = criticCompleted && revision.initial_critic_call_count === 1;
      return {
        badges: [initialCompleted ? 'Initial critic completed' : 'Initial critic unavailable', 'Final critic not required'],
        detail: initialCompleted
          ? 'The initial critic completed and remains the applicable review. A final critic was not required because no revision ran.'
          : 'The initial critic receipt is unavailable. A final critic was not run, so reviews and hooks are unavailable for owner handoff.',
        reviewReceiptUsable: initialCompleted,
        reviewStageLabel: 'Initial',
      };
    }

    if (revision.status === 'completed') {
      const finalCompleted = criticCompleted && revision.final_critic_call_count === 1;
      return {
        badges: ['Initial critic completed', finalCompleted ? 'Final critic completed' : 'Final critic unavailable after revision'],
        detail: finalCompleted
          ? 'The initial and final critics completed. Displayed reviews and hooks come from the fresh final critic.'
          : 'The initial critic completed, but the final critic is unavailable after revision. No final critic reviews or hooks are available for owner handoff.',
        reviewReceiptUsable: finalCompleted,
        reviewStageLabel: 'Final',
      };
    }

    if (revision.status === 'failed') {
      const initialCallCount = revision.initial_critic_call_count ?? 0;
      const initialBadge = initialCallCount === 0
        ? 'Initial critic not run'
        : revision.failure_code === 'initial_critic_failed'
          ? 'Initial critic unavailable'
          : 'Initial critic completed';
      const finalCallCount = revision.final_critic_call_count ?? 0;
      const finalBadge = finalCallCount === 0
        ? 'Final critic not run after revision failure'
        : criticCompleted
          ? 'Final critic receipt rejected after revision'
          : 'Final critic unavailable after revision';
      return {
        badges: [initialBadge, finalBadge],
        detail: `${initialBadge}. ${finalBadge}. No final critic reviews or hooks are available for owner handoff.`,
        reviewReceiptUsable: false,
        reviewStageLabel: 'Final',
      };
    }

    return {
      badges: ['Critic state unavailable'],
      detail: 'The revision receipt has no recognized completion state. Reviews and hooks are unavailable for owner handoff.',
      reviewReceiptUsable: false,
      reviewStageLabel: 'Final',
    };
  }

  if (criticCompleted) {
    return {
      badges: ['Critic completed'],
      detail: 'The independent critic completed. Displayed reviews and hooks come from that critic receipt.',
      reviewReceiptUsable: true,
      reviewStageLabel: 'Critic',
    };
  }
  const criticUnavailable = criticStatus === 'unavailable'
    || diagnostics?.editorial_readiness?.status === 'critic_unavailable';
  const badge = criticUnavailable ? 'Critic unavailable' : 'Critic not run';
  return {
    badges: [badge],
    detail: `${badge}. No critic reviews or hooks are available for owner handoff.`,
    reviewReceiptUsable: false,
    reviewStageLabel: 'Critic',
  };
}

export function deterministicPlanDraftBlockers(
  diagnostics: GeneratedContentDiagnostics | undefined,
) {
  const reasons = [
    ...(diagnostics?.quality_gate?.failed_reasons ?? []),
    ...(diagnostics?.draft_distinctness?.failed_reasons ?? []),
  ];
  return Array.from(new Set(reasons.map((reason) => String(reason).trim()).filter(Boolean))).map((code) => ({
    code,
    stage: /(?:^|_)planned(?:_|$)|^plan_/.test(code.toLowerCase()) ? 'Plan' as const : 'Draft' as const,
  }));
}

function criticReviews(diagnostics: GeneratedContentDiagnostics | undefined) {
  return diagnostics?.critic_review?.reviews ?? diagnostics?.editorial_readiness?.option_reviews ?? [];
}

export function buildCriticCoverageLabel(
  diagnostics: GeneratedContentDiagnostics | undefined,
  state = buildCriticReceiptState(diagnostics),
) {
  const expectedDrafts = diagnostics?.draft_contract?.required_option_count;
  const expectedHooks = diagnostics?.draft_contract?.hook_variants_per_option;
  if (!expectedDrafts || !expectedHooks) return null;
  if (!state.reviewReceiptUsable) {
    return `${state.reviewStageLabel} reviews unavailable · hooks unavailable`;
  }
  const reviews = criticReviews(diagnostics);
  const complete = reviews.length === expectedDrafts
    && reviews.every((review) => review.hook_variants?.length === expectedHooks);
  return complete
    ? `${state.reviewStageLabel} reviews ${reviews.length}/${expectedDrafts} · ${expectedHooks} hooks each`
    : `${state.reviewStageLabel} receipt incomplete · ${reviews.length}/${expectedDrafts} reviews · hook coverage incomplete`;
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
  if (
    diagnostics?.editorial_readiness?.ready !== true
    || normalizedStatus(diagnostics.editorial_readiness.status) !== 'ready'
    || diagnostics.editorial_readiness.semantic_distinctness_passed !== true
  ) return false;
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
  const criticReceipt = buildCriticReceiptState(diagnostics);
  const deterministicBlockers = deterministicPlanDraftBlockers(diagnostics);
  const expectedDrafts = draftContract?.required_option_count;
  const actualDrafts = diagnostics.technical_completion?.draft_count ?? deterministicDistinctness?.actual_option_count;
  const criticCoverageLabel = buildCriticCoverageLabel(diagnostics, criticReceipt);
  const explainedBlockers = new Set([
    ...deterministicBlockers.map((blocker) => blocker.code),
    String(diagnostics.critic_review?.reason ?? '').trim(),
    String(revision?.failure_code ?? '').trim(),
    'independent_critic_not_completed',
    'revision_failed_before_final_critic',
  ].filter(Boolean));
  const otherEditorialBlockers = (readiness?.blocking_reasons ?? []).filter(
    (reason) => !explainedBlockers.has(String(reason).trim()),
  );
  const tone = readinessTone(readiness?.status, readiness?.ready);
  const badges = [
    diagnostics.grounding_mode ? `Grounding ${humanize(diagnostics.grounding_mode)}` : 'Grounding unavailable',
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
    criticReceipt.reviewReceiptUsable && criticDistinctness
      ? `Critic distinction ${criticDistinctness.passed ? 'passed' : 'failed'}`
      : null,
    ...criticReceipt.badges,
    criticCoverageLabel,
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
      {deterministicBlockers.length > 0 && (
        <div data-generation-receipt-blockers="deterministic-plan-draft" style={{ color: '#fbbf24', fontSize: '11px' }}>
          <strong>Deterministic plan/draft blockers</strong>
          <ul style={{ lineHeight: 1.5, margin: '5px 0 0', paddingLeft: '18px' }}>
            {deterministicBlockers.map((blocker) => (
              <li key={blocker.code}>
                {blocker.stage}: {humanize(blocker.code)}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p data-generation-receipt-critic-state="true" style={{ color: criticReceipt.reviewReceiptUsable ? '#94a3b8' : '#fbbf24', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
        Critic availability: {criticReceipt.detail}
      </p>
      {otherEditorialBlockers.length > 0 && (
        <p style={{ color: '#fbbf24', fontSize: '11px', margin: 0 }}>
          Other editorial blockers: {otherEditorialBlockers.map(humanize).join(' · ')}
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
          Revision stopped closed: {humanize(revision.failure_code || 'revision contract failed')}. No option can advance without an admissible final critic receipt.
        </p>
      )}
      {criticReceipt.reviewReceiptUsable && criticDistinctness?.reason && (
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
  const criticReceipt = buildCriticReceiptState(diagnostics);
  const review = criticReviewForOption(diagnostics?.editorial_readiness, optionIndex);
  if (!review || !criticReceipt.reviewReceiptUsable) {
    return (
      <div data-option-critic-receipt="unavailable" style={{ border: '1px solid #fbbf2433', borderRadius: '10px', padding: '10px', display: 'grid', gap: '7px' }}>
        <div style={{ display: 'flex', gap: '7px', alignItems: 'center', flexWrap: 'wrap' }}>
          {criticReceipt.badges.map((badge) => <ReceiptBadge key={badge} label={badge} tone="#fbbf24" />)}
        </div>
        <p style={{ color: '#fbbf24', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
          {criticReceipt.reviewReceiptUsable
            ? `The ${criticReceipt.reviewStageLabel.toLowerCase()} critic completed, but no review receipt is attached to this option. No hook set can be treated as complete.`
            : `${criticReceipt.detail} No review or hook set is attached to this option.`}
        </p>
      </div>
    );
  }
  const ready = isOptionEditoriallyReady(diagnostics, optionIndex);
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
            {hookCount === expectedHooks ? 'Hook lab complete' : 'Hook lab incomplete'} · {hookCount}/{expectedHooks} evidence-bounded alternatives
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
          The critic review is attached, but its hook set is incomplete. Owner handoff requires exactly {expectedHooks} unique hooks.
        </p>
      )}
    </div>
  );
}
