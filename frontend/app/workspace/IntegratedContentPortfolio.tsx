'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { controlApiGet, controlApiPost, ownerSafeErrorMessage } from '@/lib/control-api';
import { safeExternalHttpsUrl } from '@/lib/display-privacy';
import {
  forgetPendingIntegratedVariantJob,
  IntegratedContentJobError,
  IntegratedContentJobReceipt,
  IntegratedContentJobStatus,
  listPendingIntegratedVariantJobs,
  rememberPendingIntegratedVariantJob,
  waitForIntegratedContentJob,
} from '@/lib/integrated-content-job';
import {
  buildVariantRequestControls,
  initializeVariantControls,
  updateVariantControl,
  VariantControlOption,
  VariantControlState,
} from '@/lib/integrated-content-controls';
import {
  buildLearningActionPayload,
  buildManualEditPayload,
  buildPersonaReversalPayload,
  EDIT_CLASSIFICATIONS,
  EditClassification,
  EMPTY_INTEGRITY_CONFIRMATION,
  IntegrityConfirmation,
  OwnerLearningAction,
  PublicationPlatform,
  resolveOwnerPostThesis,
} from '@/lib/integrated-content-owner-actions';
import { formatUiTimestamp } from '@/lib/ui-dates';

type BoundedSummary = Record<string, boolean | number | string | string[] | null>;

type IntegratedInterpretation = {
  interpretation_id: string;
  lens_name: string;
  lens_version: string;
  provenance_kind: 'independent_agent' | 'deterministic_policy' | 'synthesized_lens';
  reading: BoundedSummary;
  confidence?: number | null;
  created_at: string;
};

type IntegratedEvidence = {
  evidence_id: string;
  extractor_name: string;
  extractor_version: string;
  confidence?: number | null;
  references: Array<{ kind: string; start?: number; end?: number; excerpt?: string | null; source_url?: string }>;
  interpretations: IntegratedInterpretation[];
  created_at: string;
};

type IntegratedRevision = {
  revision_id: string;
  parent_revision_id?: string | null;
  revision_kind: 'base' | 'edit' | 'variant' | 'revision';
  platform?: string | null;
  controls: Record<string, unknown>;
  body: string;
  content_sha256: string;
  attribution: {
    required: boolean;
    public_source_name?: string | null;
    public_source_url?: string | null;
  };
  variant_generation?: {
    eligible: boolean;
    reason_code?: string | null;
    message?: string | null;
  };
  created_at: string;
};

type IntegratedPost = {
  post_id: string;
  opportunity_id: string;
  thesis: string;
  status: string;
  current_revision_id?: string | null;
  revisions: IntegratedRevision[];
  variant_control_options: VariantControlOption[];
  learning_events: Array<{
    learning_event_id: string;
    revision_id: string;
    event_kind: string;
    edit_classification?: string | null;
    occurred_at: string;
    summary: BoundedSummary;
  }>;
  persona_candidates: Array<{
    persona_candidate_id: string;
    candidate_kind: string;
    status: string;
    claim: BoundedSummary;
    evidence_count: number;
    qualifying_post_count: number;
    independent_context_count: number;
    automatic_promotion_eligible: boolean;
    lifecycle_authority: string;
    promotion?: {
      promotion_id: string;
      canon_version: string;
      promotion_rule: string;
      promoted_at: string;
      reversed_at?: string | null;
    } | null;
  }>;
  decisions: Array<{
    decision_id: string;
    decision_type: string;
    status: string;
    title: string;
    state_version: number;
  }>;
  lineage: Record<string, string[] | string | null>;
  updated_at: string;
};

type IntegratedOpportunity = {
  opportunity_id: string;
  thesis: string;
  status: string;
  owner_requested: boolean;
  truth_state: string;
  safety_state: string;
  attribution_state: string;
  source_count: number;
  strategy_contract_ref?: string | null;
  synthesis: {
    evidence_ids: string[];
    interpretation_ids: string[];
    canonical_belief_refs: string[];
    exploratory_conflict: boolean;
  };
  selection?: { disposition: string; reason: BoundedSummary; selected_at: string } | null;
  drafting?: {
    generation_job_id: string;
    portfolio_cycle_id?: string | null;
    draft_authority: 'owner_requested' | 'portfolio_selected';
    status: 'queued' | 'running' | 'succeeded' | 'failed';
    attempt_count: number;
    post_id?: string | null;
    revision_id?: string | null;
    generation_receipt_sha256?: string | null;
    safe_error_code?: string | null;
    updated_at: string;
    completed_at?: string | null;
  } | null;
  lineage: { source_ids: string[]; evidence_ids: string[]; interpretation_ids: string[]; post_id?: string | null };
  updated_at: string;
};

type IntegratedSource = {
  source_id: string;
  source_kind: string;
  title: string;
  author_or_publisher?: string | null;
  canonical_url?: string | null;
  origins: string[];
  discoveries: Array<{
    discovery_id: string;
    origin: string;
    discovery_route: string;
    external_ref?: string | null;
    discovered_at: string;
    relevance_state: string;
  }>;
  rights_state: string;
  admissibility_state: string;
  capture: {
    captured: boolean;
    capture_kinds: string[];
    captured_at?: string | null;
    content_sha256?: string | null;
  };
  evidence_count: number;
  evidence: IntegratedEvidence[];
  merged_source_aliases: Array<{ source_id: string; source_kind: string; canonical_url?: string | null }>;
  updated_at: string;
};

export type IntegratedContentProjection = {
  schema_version: 'integrated_content_portfolio/v1';
  generated_at: string;
  state: 'ready' | 'empty' | 'degraded' | 'error';
  reason_codes: string[];
  counts: {
    sources: number;
    discoveries: number;
    opportunities: number;
    posts: number;
    revisions: number;
    evidence: number;
    interpretations: number;
    learning_events: number;
    persona_candidates: number;
    decisions: number;
    origins: Record<string, number>;
  };
  sources: IntegratedSource[];
  opportunities: IntegratedOpportunity[];
  posts: IntegratedPost[];
  activity_summary: {
    learning: { total: number; by_kind: Record<string, number>; edit_classifications: Record<string, number> };
    persona: { total: number; by_status: Record<string, number>; automatic_promotion_eligible: number; recent: IntegratedPost['persona_candidates'] };
    decisions: { total: number; by_status: Record<string, number>; recent: IntegratedPost['decisions'] };
  };
  controller_capabilities: Record<string, boolean>;
  controller_gaps: Array<{ capability: string; reason_code: string; safe_behavior: string }>;
};

const PUBLISHED_VARIANT_MESSAGE = 'This post is already published. Variant generation is disabled because this lifecycle cannot select or reject new post-publication revisions.';

function readable(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function currentLocalDateTimeInputValue(now = new Date()): string {
  const local = new Date(now.getTime() - (now.getTimezoneOffset() * 60_000));
  return local.toISOString().slice(0, 16);
}

function summaryText(summary: BoundedSummary): string {
  return Object.entries(summary)
    .map(([key, value]) => `${readable(key)}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
    .join(' · ');
}

function statusColor(state: IntegratedContentProjection['state']) {
  if (state === 'ready') return '#86efac';
  if (state === 'empty') return '#93c5fd';
  return '#fbbf24';
}

function revisionLabel(revision: IntegratedRevision) {
  const platform = revision.platform ? readable(revision.platform) : null;
  if (revision.revision_kind === 'edit') return platform ? `Owner edit · ${platform}` : 'Owner edit';
  if (revision.revision_kind === 'variant') return platform ? `${platform} variant` : 'Variant';
  if (revision.revision_kind === 'base') return 'Canonical base';
  return platform || readable(revision.revision_kind);
}

export default function IntegratedContentPortfolio() {
  const [projection, setProjection] = useState<IntegratedContentProjection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedByPost, setSelectedByPost] = useState<Record<string, string>>({});
  const [variantStatus, setVariantStatus] = useState<Record<string, string>>({});
  const [variantBusy, setVariantBusy] = useState<Record<string, boolean>>({});
  const [variantControls, setVariantControls] = useState<Record<string, VariantControlState>>({});
  const [sourceThesis, setSourceThesis] = useState<Record<string, string>>({});
  const [sourceRequestStatus, setSourceRequestStatus] = useState<Record<string, string>>({});
  const [sourceRequestBusy, setSourceRequestBusy] = useState<Record<string, boolean>>({});
  const [ownerActionStatus, setOwnerActionStatus] = useState<Record<string, string>>({});
  const [ownerActionBusy, setOwnerActionBusy] = useState<Record<string, boolean>>({});
  const [editDrafts, setEditDrafts] = useState<Record<string, {
    parentRevisionId: string;
    body: string;
    editClassification: '' | EditClassification;
  }>>({});
  const [integrityConfirmations, setIntegrityConfirmations] = useState<Record<string, IntegrityConfirmation>>({});
  const [publicationForms, setPublicationForms] = useState<Record<string, {
    platform: PublicationPlatform;
    publicUrl: string;
    eventAt: string;
  }>>({});
  const [personaReversalReasons, setPersonaReversalReasons] = useState<Record<string, string>>({});
  const [personaReversalStatus, setPersonaReversalStatus] = useState<Record<string, string>>({});
  const [personaReversalBusy, setPersonaReversalBusy] = useState<Record<string, boolean>>({});
  const resumingVariantJobs = useRef(new Set<string>());
  const variantActionLocks = useRef(new Set<string>());
  const sourceRequestLocks = useRef(new Set<string>());
  const ownerActionLocks = useRef(new Set<string>());
  const personaReversalLocks = useRef(new Set<string>());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await controlApiGet<IntegratedContentProjection>('/api/workspace/integrated-content', { cache: 'no-store' });
      if (payload.schema_version !== 'integrated_content_portfolio/v1') throw new Error('The integrated content projection is invalid.');
      setProjection(payload);
    } catch (caught) {
      setError(ownerSafeErrorMessage(caught, 'The integrated content portfolio is unavailable.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const originSummary = useMemo(
    () => Object.entries(projection?.counts.origins ?? {}).sort(([left], [right]) => left.localeCompare(right)),
    [projection],
  );

  const requestVariant = useCallback(async (post: IntegratedPost, parentRevisionId: string, platform: 'linkedin' | 'instagram') => {
    if (variantBusy[post.post_id] || variantActionLocks.current.has(post.post_id)) return;
    if (post.status === 'published') {
      setVariantStatus((current) => ({
        ...current,
        [post.post_id]: PUBLISHED_VARIANT_MESSAGE,
      }));
      return;
    }
    const parent = post.revisions.find((candidate) => candidate.revision_id === parentRevisionId);
    if (!projection?.controller_capabilities.variant_generation || parent?.variant_generation?.eligible !== true) {
      setVariantStatus((current) => ({
        ...current,
        [post.post_id]: parent?.variant_generation?.message
          || 'Variant generation is not available from this revision. Choose an eligible generated revision or refresh readiness.',
      }));
      return;
    }
    const controls = buildVariantRequestControls(
      post.variant_control_options,
      variantControls[post.post_id] ?? initializeVariantControls(post.variant_control_options),
      platform,
    );
    variantActionLocks.current.add(post.post_id);
    setVariantBusy((current) => ({ ...current, [post.post_id]: true }));
    setVariantStatus((current) => ({ ...current, [post.post_id]: `Queuing ${readable(platform)} variant…` }));
    let queuedJobId: string | null = null;
    try {
      const receipt = await controlApiPost<IntegratedContentJobReceipt>('/api/workspace/integrated-content/variants', { post_id: post.post_id, parent_revision_id: parentRevisionId, platform, controls });
      queuedJobId = receipt.job_id;
      rememberPendingIntegratedVariantJob({
        schema_version: 'integrated_content_pending_variant/v1',
        job_id: receipt.job_id,
        card_id: receipt.card_id || receipt.job_id,
        post_id: post.post_id,
        parent_revision_id: parentRevisionId,
        platform,
        created_at: receipt.created_at || new Date().toISOString(),
      });
      setVariantStatus((current) => ({ ...current, [post.post_id]: `Queued as ${receipt.job_id}. Waiting for the governed local generator…` }));
      await waitForIntegratedContentJob({
        receipt,
        readStatus: (jobId) => controlApiGet<IntegratedContentJobStatus>(`/api/workspace/integrated-content/variants/${encodeURIComponent(jobId)}`, { cache: 'no-store' }),
        onStatus: (status) => setVariantStatus((current) => ({
          ...current,
          [post.post_id]: status.status === 'running'
            ? `${readable(platform)} generation is running locally. Nothing will be published.`
            : `Queued as ${receipt.job_id}. Waiting for the governed local generator…`,
        })),
      });
      forgetPendingIntegratedVariantJob(receipt.job_id);
      setVariantStatus((current) => ({ ...current, [post.post_id]: `${readable(platform)} variant completed and the canonical projection was refreshed.` }));
      await load();
    } catch (caught) {
      if (queuedJobId && (!(caught instanceof IntegratedContentJobError) || !caught.retryable)) {
        forgetPendingIntegratedVariantJob(queuedJobId);
      }
      setVariantStatus((current) => ({ ...current, [post.post_id]: ownerSafeErrorMessage(caught, 'Variant request failed.') }));
    } finally {
      variantActionLocks.current.delete(post.post_id);
      setVariantBusy((current) => ({ ...current, [post.post_id]: false }));
    }
  }, [load, projection, variantBusy, variantControls]);

  useEffect(() => {
    let cancelled = false;
    const pendingJobs = listPendingIntegratedVariantJobs();
    for (const pending of pendingJobs) {
      if (resumingVariantJobs.current.has(pending.job_id)) continue;
      resumingVariantJobs.current.add(pending.job_id);
      setVariantBusy((current) => ({ ...current, [pending.post_id]: true }));
      setVariantStatus((current) => ({
        ...current,
        [pending.post_id]: `Resuming ${readable(pending.platform)} job ${pending.job_id}…`,
      }));
      void waitForIntegratedContentJob({
        receipt: { job_id: pending.job_id, card_id: pending.card_id, created_at: pending.created_at },
        readStatus: (jobId) => controlApiGet<IntegratedContentJobStatus>(
          `/api/workspace/integrated-content/variants/${encodeURIComponent(jobId)}`,
          { cache: 'no-store' },
        ),
        onStatus: (status) => {
          if (cancelled) return;
          setVariantStatus((current) => ({
            ...current,
            [pending.post_id]: status.status === 'running'
              ? `${readable(pending.platform)} generation is running locally. Nothing will be published.`
              : `Resumed exact job ${pending.job_id}; waiting for the local worker…`,
          }));
        },
      }).then(async () => {
        forgetPendingIntegratedVariantJob(pending.job_id);
        if (cancelled) return;
        setVariantStatus((current) => ({
          ...current,
          [pending.post_id]: `${readable(pending.platform)} variant completed and the canonical projection was refreshed.`,
        }));
        await load();
      }).catch((caught: unknown) => {
        if (!(caught instanceof IntegratedContentJobError) || !caught.retryable) {
          forgetPendingIntegratedVariantJob(pending.job_id);
        }
        if (!cancelled) {
          setVariantStatus((current) => ({
            ...current,
            [pending.post_id]: ownerSafeErrorMessage(caught, 'The saved variant job could not be resumed.'),
          }));
        }
      }).finally(() => {
        resumingVariantJobs.current.delete(pending.job_id);
        if (!cancelled) setVariantBusy((current) => ({ ...current, [pending.post_id]: false }));
      });
    }
    return () => {
      cancelled = true;
    };
  }, [load]);

  const runOwnerAction = useCallback(async ({
    postId,
    endpoint,
    payload,
    queuedMessage,
    completedMessage,
  }: {
    postId: string;
    endpoint: '/api/workspace/integrated-content/manual-edits' | '/api/workspace/integrated-content/learning-actions';
    payload: Record<string, unknown>;
    queuedMessage: string;
    completedMessage: string;
  }) => {
    if (ownerActionLocks.current.has(postId)) return;
    ownerActionLocks.current.add(postId);
    setOwnerActionBusy((current) => ({ ...current, [postId]: true }));
    setOwnerActionStatus((current) => ({ ...current, [postId]: queuedMessage }));
    try {
      const receipt = await controlApiPost<IntegratedContentJobReceipt>(endpoint, payload);
      setOwnerActionStatus((current) => ({
        ...current,
        [postId]: `Queued as ${receipt.job_id}. Waiting for the exact owner action to reach canonical local SQL…`,
      }));
      await waitForIntegratedContentJob({
        receipt,
        readStatus: (jobId) => controlApiGet<IntegratedContentJobStatus>(
          `/api/workspace/integrated-content/owner-actions/${encodeURIComponent(jobId)}`,
          { cache: 'no-store' },
        ),
      });
      setSelectedByPost((current) => {
        const next = { ...current };
        delete next[postId];
        return next;
      });
      setOwnerActionStatus((current) => ({ ...current, [postId]: completedMessage }));
      await load();
    } catch (caught) {
      setOwnerActionStatus((current) => ({
        ...current,
        [postId]: ownerSafeErrorMessage(caught, 'The owner action failed.'),
      }));
    } finally {
      ownerActionLocks.current.delete(postId);
      setOwnerActionBusy((current) => ({ ...current, [postId]: false }));
    }
  }, [load]);

  const submitManualEdit = useCallback(async (
    post: IntegratedPost,
    revision: IntegratedRevision,
    draft: { parentRevisionId: string; body: string; editClassification: '' | EditClassification },
  ) => {
    try {
      const payload = buildManualEditPayload({
        postId: post.post_id,
        parentRevisionId: revision.revision_id,
        body: draft.body,
        parentBody: revision.body,
        editClassification: draft.editClassification,
      });
      await runOwnerAction({
        postId: post.post_id,
        endpoint: '/api/workspace/integrated-content/manual-edits',
        payload,
        queuedMessage: 'Queuing an immutable owner edit with its learning classification…',
        completedMessage: 'Immutable edit completed; the exact child revision and learning event are now projected.',
      });
    } catch (caught) {
      setOwnerActionStatus((current) => ({
        ...current,
        [post.post_id]: ownerSafeErrorMessage(caught, 'The manual edit could not be queued.'),
      }));
    }
  }, [runOwnerAction]);

  const submitLearningAction = useCallback(async ({
    post,
    revision,
    eventKind,
    eventAt,
    integrityConfirmation,
    platform,
    publicUrl,
  }: {
    post: IntegratedPost;
    revision: IntegratedRevision;
    eventKind: OwnerLearningAction;
    eventAt?: string;
    integrityConfirmation?: IntegrityConfirmation;
    platform?: PublicationPlatform;
    publicUrl?: string;
  }) => {
    try {
      const payload = buildLearningActionPayload({
        postId: post.post_id,
        revisionId: revision.revision_id,
        eventKind,
        revisionSha256: revision.content_sha256,
        ownerConfirmed: true,
        eventAt,
        integrityConfirmation,
        platform,
        publicUrl,
      });
      const labels: Record<OwnerLearningAction, [string, string]> = {
        variant_selected: ['Queuing exact variant selection…', 'Variant selected as the exact current revision.'],
        variant_rejected: ['Queuing exact variant rejection…', 'Variant rejection recorded without changing canonical copy.'],
        owner_approved: ['Queuing exact-revision integrity approval…', 'Exact revision approved with all four integrity attestations.'],
        publication_confirmed: ['Queuing publication confirmation…', 'Publication confirmed against the exact approved revision.'],
      };
      await runOwnerAction({
        postId: post.post_id,
        endpoint: '/api/workspace/integrated-content/learning-actions',
        payload,
        queuedMessage: labels[eventKind][0],
        completedMessage: labels[eventKind][1],
      });
    } catch (caught) {
      setOwnerActionStatus((current) => ({
        ...current,
        [post.post_id]: ownerSafeErrorMessage(caught, 'The learning action could not be queued.'),
      }));
    }
  }, [runOwnerAction]);

  const reversePersonaPromotion = useCallback(async (
    candidate: IntegratedPost['persona_candidates'][number],
  ) => {
    const promotion = candidate.promotion;
    if (!promotion || promotion.reversed_at) {
      setPersonaReversalStatus((current) => ({
        ...current,
        [candidate.persona_candidate_id]: 'This persona promotion is not currently reversible.',
      }));
      return;
    }
    const candidateId = candidate.persona_candidate_id;
    if (personaReversalLocks.current.has(candidateId)) return;
    personaReversalLocks.current.add(candidateId);
    try {
      const payload = buildPersonaReversalPayload({
        promotionId: promotion.promotion_id,
        personaCandidateId: candidateId,
        canonVersion: promotion.canon_version,
        reason: personaReversalReasons[candidateId] ?? '',
        ownerConfirmed: true,
      });
      setPersonaReversalBusy((current) => ({ ...current, [candidateId]: true }));
      setPersonaReversalStatus((current) => ({
        ...current,
        [candidateId]: 'Queuing exact governed persona reversal…',
      }));
      const receipt = await controlApiPost<IntegratedContentJobReceipt>(
        '/api/workspace/integrated-content/persona-reversals',
        payload,
      );
      setPersonaReversalStatus((current) => ({
        ...current,
        [candidateId]: `Queued as ${receipt.job_id}. Waiting for the private canonical overlay and SQL receipt…`,
      }));
      await waitForIntegratedContentJob({
        receipt,
        readStatus: (jobId) => controlApiGet<IntegratedContentJobStatus>(
          `/api/workspace/integrated-content/persona-actions/${encodeURIComponent(jobId)}`,
          { cache: 'no-store' },
        ),
      });
      setPersonaReversalStatus((current) => ({
        ...current,
        [candidateId]: 'Persona promotion reversed and the canonical projection refreshed.',
      }));
      await load();
    } catch (caught) {
      setPersonaReversalStatus((current) => ({
        ...current,
        [candidateId]: ownerSafeErrorMessage(caught, 'Persona reversal failed.'),
      }));
    } finally {
      personaReversalLocks.current.delete(candidateId);
      setPersonaReversalBusy((current) => ({ ...current, [candidateId]: false }));
    }
  }, [load, personaReversalReasons]);

  const requestOwnerPost = useCallback(async (source: IntegratedSource) => {
    if (sourceRequestBusy[source.source_id] || sourceRequestLocks.current.has(source.source_id)) return;
    const resolution = resolveOwnerPostThesis(
      source.source_id,
      projection?.opportunities ?? [],
      sourceThesis[source.source_id] ?? '',
    );
    if (resolution.blocker) {
      setSourceRequestStatus((current) => ({ ...current, [source.source_id]: resolution.blocker || 'The synthesized opportunity is blocked.' }));
      return;
    }
    const thesis = resolution.thesis;
    if (!thesis) {
      setSourceRequestStatus((current) => ({ ...current, [source.source_id]: 'No synthesized opportunity exists yet. Add the manual thesis you want this source to support.' }));
      return;
    }
    sourceRequestLocks.current.add(source.source_id);
    setSourceRequestStatus((current) => ({
      ...current,
      [source.source_id]: resolution.mode === 'synthesized'
        ? `Queuing the existing synthesized opportunity ${resolution.opportunityId} as an owner-requested canonical post…`
        : 'Queuing an owner-requested canonical post from the manual thesis…',
    }));
    setSourceRequestBusy((current) => ({ ...current, [source.source_id]: true }));
    try {
      const receipt = await controlApiPost<IntegratedContentJobReceipt>('/api/workspace/integrated-content/owner-posts', { source_id: source.source_id, thesis, controls: {} });
      setSourceRequestStatus((current) => ({ ...current, [source.source_id]: `Queued as ${receipt.job_id}. Waiting on evidence, truth, safety and attribution gates…` }));
      await waitForIntegratedContentJob({
        receipt,
        readStatus: (jobId) => controlApiGet<IntegratedContentJobStatus>(`/api/workspace/integrated-content/owner-posts/${encodeURIComponent(jobId)}`, { cache: 'no-store' }),
      });
      setSourceRequestStatus((current) => ({ ...current, [source.source_id]: 'Canonical post completed and the owner portfolio was refreshed.' }));
      await load();
    } catch (caught) {
      setSourceRequestStatus((current) => ({ ...current, [source.source_id]: ownerSafeErrorMessage(caught, 'Post request failed.') }));
    } finally {
      sourceRequestLocks.current.delete(source.source_id);
      setSourceRequestBusy((current) => ({ ...current, [source.source_id]: false }));
    }
  }, [load, projection, sourceRequestBusy, sourceThesis]);

  return (
    <section id="integrated-content-portfolio" aria-labelledby="integrated-content-title" style={panelStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <p style={eyebrowStyle}>Canonical content intelligence</p>
          <h2 id="integrated-content-title" style={{ margin: '4px 0 6px', color: 'white', fontSize: '24px' }}>Sources → Opportunities → Posts</h2>
          <p style={helperStyle}>Local SQL owns lifecycle and lineage. Railway carries this bounded authenticated review projection.</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading} style={buttonStyle}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {loading && !projection ? <p role="status" style={helperStyle}>Loading canonical content state…</p> : null}
      {error ? <p role="alert" style={{ ...noticeStyle, color: '#fecaca' }}>{error}</p> : null}
      {projection ? (
        <>
          <div style={statusRowStyle}>
            <strong style={{ color: statusColor(projection.state) }}>{readable(projection.state)}</strong>
            <span>{projection.counts.sources} sources</span>
            <span>{projection.counts.discoveries} discoveries</span>
            <span>{projection.counts.evidence} evidence records</span>
            <span>{projection.counts.interpretations} interpretations</span>
            <span>{projection.counts.opportunities} opportunities</span>
            <span>{projection.counts.posts} posts</span>
            <span>Projected {formatUiTimestamp(projection.generated_at)}</span>
          </div>
          {projection.state === 'degraded' || projection.state === 'error' ? (
            <p role="alert" style={noticeStyle}>Degraded: {(projection.reason_codes ?? []).map(readable).join(', ') || 'Unknown projection failure'}.</p>
          ) : null}
          {originSummary.length ? (
            <div aria-label="Discovery origins" style={pillRowStyle}>
              {originSummary.map(([origin, count]) => <span key={origin} style={pillStyle}>{readable(origin)} · {count}</span>)}
            </div>
          ) : null}

          {projection.state === 'empty' ? (
            <p style={noticeStyle}>The source registry is ready, but no canonical opportunities or posts have been projected yet.</p>
          ) : null}

          {projection.sources.length ? (
            <div style={{ display: 'grid', gap: '9px' }}>
              <h3 style={headingStyle}>Recent canonical sources</h3>
              {projection.sources.map((source) => {
                const ownerPostResolution = resolveOwnerPostThesis(
                  source.source_id,
                  projection.opportunities,
                  sourceThesis[source.source_id] ?? '',
                );
                const ownerPostReady = (
                  source.capture.captured
                  && source.evidence_count > 0
                  && source.admissibility_state === 'admissible'
                  && Boolean(ownerPostResolution.thesis)
                  && !ownerPostResolution.blocker
                );
                return <article key={source.source_id} style={cardStyle}>
                  <div style={cardHeaderStyle}>
                    <div><strong style={{ color: 'white' }}>{source.title}</strong><p style={helperStyle}>{source.author_or_publisher || readable(source.source_kind)}</p></div>
                    {safeExternalHttpsUrl(source.canonical_url) ? <a href={safeExternalHttpsUrl(source.canonical_url) ?? undefined} target="_blank" rel="noreferrer" style={{ color: '#7dd3fc', fontSize: '12px' }}>Open original</a> : null}
                  </div>
                  <div style={pillRowStyle}>
                    {source.origins.map((origin) => <span key={origin} style={pillStyle}>{readable(origin)}</span>)}
                    <span style={pillStyle}>{source.capture.captured ? `Captured ${source.capture.capture_kinds.map(readable).join(' + ')}` : 'Registered only'}</span>
                    <span style={pillStyle}>{source.evidence_count} evidence record{source.evidence_count === 1 ? '' : 's'}</span>
                    {source.merged_source_aliases.length ? <span style={pillStyle}>{source.merged_source_aliases.length} exact-content alias{source.merged_source_aliases.length === 1 ? '' : 'es'} merged</span> : null}
                    <span style={pillStyle}>{readable(source.admissibility_state)}</span>
                    <span style={pillStyle}>Rights {readable(source.rights_state)}</span>
                  </div>
                  <div style={lineageGridStyle}>
                    <div>
                      <strong style={microHeadingStyle}>Capture and identity</strong>
                      <p style={helperStyle}>{source.capture.captured_at ? `Captured ${formatUiTimestamp(source.capture.captured_at)}` : 'Capture time not yet recorded'}</p>
                      <p style={helperStyle}>{source.capture.content_sha256 ? `Content SHA-256 ${source.capture.content_sha256}` : 'Content hash pending capture'}</p>
                    </div>
                    <details>
                      <summary style={detailsSummaryStyle}>Discovery routes ({source.discoveries.length})</summary>
                      <ul style={compactListStyle}>
                        {source.discoveries.map((discovery) => (
                          <li key={discovery.discovery_id}>
                            <strong>{readable(discovery.origin)}</strong> through {discovery.discovery_route} · {readable(discovery.relevance_state)} · {formatUiTimestamp(discovery.discovered_at)}
                            {discovery.external_ref ? <> · <span>{discovery.external_ref}</span></> : null}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </div>
                  {source.merged_source_aliases.length ? (
                    <details>
                      <summary style={detailsSummaryStyle}>Merged source identities ({source.merged_source_aliases.length})</summary>
                      <ul style={compactListStyle}>
                        {source.merged_source_aliases.map((alias) => (
                          <li key={alias.source_id}>
                            <strong>{alias.source_id}</strong> · {readable(alias.source_kind)}
                            {safeExternalHttpsUrl(alias.canonical_url) ? <> · <a href={safeExternalHttpsUrl(alias.canonical_url) ?? undefined} target="_blank" rel="noreferrer" style={{ color: '#7dd3fc' }}>Open alias origin</a></> : null}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                  {source.evidence.length ? (
                    <details>
                      <summary style={detailsSummaryStyle}>Evidence and named interpretations ({source.evidence.length})</summary>
                      <div style={{ display: 'grid', gap: '10px', marginTop: '9px' }}>
                        {source.evidence.map((evidence) => (
                          <article key={evidence.evidence_id} style={nestedCardStyle}>
                            <strong style={microHeadingStyle}>{evidence.extractor_name} v{evidence.extractor_version}</strong>
                            <p style={helperStyle}>Confidence {evidence.confidence ?? 'not scored'} · {formatUiTimestamp(evidence.created_at)}</p>
                            {evidence.references.length ? (
                              <ul style={compactListStyle}>
                                {evidence.references.map((reference, index) => (
                                  <li key={`${evidence.evidence_id}-${index}`}>
                                    {readable(reference.kind)}{typeof reference.start === 'number' ? ` ${reference.start}${typeof reference.end === 'number' ? `–${reference.end}` : ''}` : ''}: {reference.excerpt || 'Exact reference retained; compact excerpt unavailable.'}
                                  </li>
                                ))}
                              </ul>
                            ) : <p style={helperStyle}>No bounded evidence reference is available in this projection.</p>}
                            {evidence.interpretations.map((interpretation) => (
                              <div key={interpretation.interpretation_id} style={interpretationStyle}>
                                <strong>{readable(interpretation.lens_name)} · v{interpretation.lens_version} · {readable(interpretation.provenance_kind)}</strong>
                                <span>{summaryText(interpretation.reading) || 'Structured reading retained without a browser-safe summary.'}</span>
                              </div>
                            ))}
                          </article>
                        ))}
                      </div>
                    </details>
                  ) : null}
                  {ownerPostResolution.mode === 'synthesized' ? (
                    <p style={noticeStyle}><strong>Existing synthesized opportunity:</strong> {ownerPostResolution.thesis}</p>
                  ) : ownerPostResolution.mode === 'blocked' ? (
                    <p role="alert" style={{ ...noticeStyle, color: '#fecaca' }}>{ownerPostResolution.blocker}</p>
                  ) : (
                    <input aria-label={`Manual thesis for ${source.title}`} value={sourceThesis[source.source_id] ?? ''} onChange={(event) => setSourceThesis((current) => ({ ...current, [source.source_id]: event.target.value }))} placeholder="No synthesis exists yet. Add the thesis this source should support." style={{ ...selectStyle, width: '100%', maxWidth: 'none' }} />
                  )}
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      disabled={
                        !ownerPostReady
                        || sourceRequestBusy[source.source_id] === true
                        || projection.controller_capabilities.owner_requested_post !== true
                      }
                      onClick={() => void requestOwnerPost(source)}
                      style={buttonStyle}
                    >
                      {sourceRequestBusy[source.source_id] ? 'Creating canonical post…' : 'Create post from this'}
                    </button>
                    <span style={helperStyle}>The existing synthesized thesis is authoritative when available; manual thesis entry appears only when no synthesis exists.</span>
                  </div>
                  {sourceRequestStatus[source.source_id] ? <p role="status" style={helperStyle}>{sourceRequestStatus[source.source_id]}</p> : null}
                </article>
              })}
            </div>
          ) : null}

          {projection.opportunities.length ? (
            <div style={{ display: 'grid', gap: '9px' }}>
              <h3 style={headingStyle}>Content opportunities</h3>
              {projection.opportunities.map((item) => (
                <article key={item.opportunity_id} style={cardStyle}>
                  <div style={cardHeaderStyle}>
                    <strong style={{ color: 'white' }}>{item.thesis}</strong>
                    <span style={pillStyle}>{readable(item.status)}</span>
                  </div>
                  <p style={helperStyle}>{item.source_count} linked source{item.source_count === 1 ? '' : 's'} · Truth {readable(item.truth_state)} · Safety {readable(item.safety_state)} · Attribution {readable(item.attribution_state)}</p>
                  {item.owner_requested ? <span style={{ ...pillStyle, color: '#fde68a' }}>Owner requested</span> : null}
                  <div style={pillRowStyle}>
                    {item.selection ? <span style={pillStyle}>Portfolio {readable(item.selection.disposition)}</span> : <span style={pillStyle}>Awaiting portfolio selection</span>}
                    {item.drafting ? <span style={pillStyle}>Draft job {readable(item.drafting.status)}</span> : null}
                    {item.synthesis.exploratory_conflict ? <span style={{ ...pillStyle, color: '#fde68a' }}>Exploratory conflict</span> : null}
                    {item.synthesis.canonical_belief_refs.map((belief) => <span key={belief} style={pillStyle}>Belief {belief}</span>)}
                  </div>
                  {item.drafting ? (
                    <p role={item.drafting.status === 'failed' ? 'alert' : 'status'} style={{ ...helperStyle, color: item.drafting.status === 'failed' ? '#fecaca' : '#cbd5e1' }}>
                      {item.drafting.status === 'succeeded'
                        ? 'Canonical draft ready for owner review. Nothing was published.'
                        : item.drafting.status === 'running'
                          ? 'Canonical drafting is running locally. Publication remains owner-controlled.'
                          : item.drafting.status === 'failed'
                            ? `Drafting failed safely${item.drafting.safe_error_code ? ` (${readable(item.drafting.safe_error_code)})` : ''}; the selected opportunity remains retriable.`
                            : 'Canonical drafting is queued locally.'}
                      {' '}Attempt {item.drafting.attempt_count} · Updated {formatUiTimestamp(item.drafting.updated_at)}
                      {item.drafting.generation_receipt_sha256 ? ' · Production receipt bound' : ''}
                    </p>
                  ) : item.selection?.disposition === 'selected' && !item.lineage.post_id ? (
                    <p role="status" style={helperStyle}>Selected for scheduled canonical drafting; no generation job has claimed it yet.</p>
                  ) : null}
                  <details>
                    <summary style={detailsSummaryStyle}>Opportunity lineage</summary>
                    <p style={helperStyle}>Sources: {item.lineage.source_ids.join(', ') || 'none'}<br />Evidence: {item.lineage.evidence_ids.join(', ') || 'not explicitly bound'}<br />Interpretations: {item.lineage.interpretation_ids.join(', ') || 'not explicitly bound'}<br />Canonical post: {item.lineage.post_id || 'not drafted'}</p>
                  </details>
                </article>
              ))}
            </div>
          ) : null}

          <div style={lineageGridStyle} aria-label="Canonical learning, persona, and decision summary">
            <div style={nestedCardStyle}>
              <strong style={microHeadingStyle}>Learning events</strong>
              <p style={helperStyle}>{projection.activity_summary.learning.total} total · {Object.entries(projection.activity_summary.learning.by_kind).map(([kind, count]) => `${readable(kind)} ${count}`).join(' · ') || 'none recorded'}</p>
            </div>
            <div style={nestedCardStyle}>
              <strong style={microHeadingStyle}>Persona learning</strong>
              <p style={helperStyle}>{projection.activity_summary.persona.total} candidates · {projection.activity_summary.persona.automatic_promotion_eligible} currently satisfy the governed reversible-pattern threshold</p>
            </div>
            <div style={nestedCardStyle}>
              <strong style={microHeadingStyle}>Canonical decisions</strong>
              <p style={helperStyle}>{projection.activity_summary.decisions.total} decisions · {Object.entries(projection.activity_summary.decisions.by_status).map(([status, count]) => `${readable(status)} ${count}`).join(' · ') || 'none recorded'}</p>
            </div>
          </div>
          {projection.activity_summary.persona.recent.length || projection.activity_summary.decisions.recent.length ? (
            <details>
              <summary style={detailsSummaryStyle}>Recent persona and decision records</summary>
              {projection.activity_summary.persona.recent.length ? (
                <div style={{ display: 'grid', gap: '9px', marginTop: '9px' }}>
                  {projection.activity_summary.persona.recent.map((candidate) => {
                    const promotion = candidate.promotion;
                    const activePromotion = candidate.status === 'promoted' && promotion && !promotion.reversed_at;
                    return (
                      <article key={candidate.persona_candidate_id} style={nestedCardStyle}>
                        <strong style={microHeadingStyle}>{readable(candidate.candidate_kind)} · {readable(candidate.status)}</strong>
                        <p style={helperStyle}>{summaryText(candidate.claim)} · {candidate.qualifying_post_count}/3 approved published posts · {candidate.independent_context_count}/2 independent contexts</p>
                        {promotion ? (
                          <p style={helperStyle}>
                            Promotion {promotion.promotion_id} · {promotion.canon_version} · {promotion.reversed_at ? `reversed ${formatUiTimestamp(promotion.reversed_at)}` : `promoted ${formatUiTimestamp(promotion.promoted_at)}`}
                          </p>
                        ) : null}
                        {activePromotion ? (
                          <div style={ownerActionPanelStyle} aria-label={`Reverse persona promotion ${candidate.persona_candidate_id}`}>
                            <p style={helperStyle}>Reversal removes only the exact governed recurring-pattern item. The evidence chain and versioned receipt remain auditable.</p>
                            <textarea
                              aria-label={`Persona reversal reason for ${candidate.persona_candidate_id}`}
                              value={personaReversalReasons[candidate.persona_candidate_id] ?? ''}
                              rows={2}
                              maxLength={1000}
                              disabled={personaReversalBusy[candidate.persona_candidate_id] === true}
                              onChange={(event) => setPersonaReversalReasons((current) => ({
                                ...current,
                                [candidate.persona_candidate_id]: event.target.value,
                              }))}
                              placeholder="Why should this learned pattern be removed from canonical persona?"
                              style={textareaStyle}
                            />
                            <button
                              type="button"
                              disabled={
                                projection.controller_capabilities.persona_reversal !== true
                                || personaReversalBusy[candidate.persona_candidate_id] === true
                                || !(personaReversalReasons[candidate.persona_candidate_id] ?? '').trim()
                              }
                              onClick={() => void reversePersonaPromotion(candidate)}
                              style={buttonStyle}
                            >
                              Reverse exact persona promotion
                            </button>
                          </div>
                        ) : null}
                        {personaReversalStatus[candidate.persona_candidate_id] ? (
                          <p role="status" style={noticeStyle}>{personaReversalStatus[candidate.persona_candidate_id]}</p>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              ) : null}
              {projection.activity_summary.decisions.recent.length ? <ul style={compactListStyle}>{projection.activity_summary.decisions.recent.map((decision) => <li key={decision.decision_id}><strong>{decision.title}</strong> · {readable(decision.status)} · version {decision.state_version}</li>)}</ul> : null}
            </details>
          ) : null}

          {projection.controller_gaps.length ? (
            <details>
              <summary style={detailsSummaryStyle}>Remaining governed controller boundaries</summary>
              <p style={helperStyle}>This panel supports governed variants, immutable edits, exact selection and rejection, integrity approval, publication confirmation, owner-requested posts, and exact persona-promotion reversal.</p>
              <ul style={compactListStyle}>
                {projection.controller_gaps.map((gap) => <li key={gap.capability}><strong>{readable(gap.capability)}</strong> · {readable(gap.reason_code)} · {readable(gap.safe_behavior)}</li>)}
              </ul>
            </details>
          ) : null}

          {projection.posts.length ? (
            <div style={{ display: 'grid', gap: '12px' }}>
              <h3 style={headingStyle}>Canonical posts and linked revisions</h3>
              {projection.posts.map((post) => {
                const selectedId = selectedByPost[post.post_id] ?? post.current_revision_id ?? post.revisions[0]?.revision_id;
                const revision = post.revisions.find((candidate) => candidate.revision_id === selectedId) ?? post.revisions[0];
                const actionKey = revision ? `${post.post_id}:${revision.revision_id}` : post.post_id;
                const storedDraft = editDrafts[post.post_id];
                const editDraft = revision && storedDraft?.parentRevisionId === revision.revision_id
                  ? storedDraft
                  : revision
                    ? { parentRevisionId: revision.revision_id, body: revision.body, editClassification: '' as const }
                    : null;
                const integrityConfirmation = integrityConfirmations[actionKey] ?? EMPTY_INTEGRITY_CONFIRMATION;
                const publicationForm = publicationForms[actionKey] ?? {
                  platform: revision?.platform === 'instagram' ? 'instagram' as const : 'linkedin' as const,
                  publicUrl: '',
                  eventAt: currentLocalDateTimeInputValue(),
                };
                const exactEvents = revision
                  ? post.learning_events.filter((event) => event.revision_id === revision.revision_id)
                  : [];
                const hasVariantSelection = exactEvents.some((event) => event.event_kind === 'variant_selected');
                const hasVariantRejection = exactEvents.some((event) => event.event_kind === 'variant_rejected');
                const hasOwnerApproval = exactEvents.some((event) => event.event_kind === 'owner_approved');
                const hasPublication = exactEvents.some((event) => event.event_kind === 'publication_confirmed');
                const isExactCurrent = Boolean(revision && post.current_revision_id === revision.revision_id);
                const actionBusy = ownerActionBusy[post.post_id] === true;
                const generationBusy = variantBusy[post.post_id] === true;
                const postPublished = post.status === 'published';
                const variantGenerationReady = Boolean(
                  !postPublished
                  && projection.controller_capabilities.variant_generation === true
                  && revision?.variant_generation?.eligible === true,
                );
                const variantGenerationReason = postPublished
                  ? PUBLISHED_VARIANT_MESSAGE
                  : revision?.variant_generation?.message
                    || (projection.controller_capabilities.variant_generation !== true
                      ? 'Variant generation is temporarily unavailable. Review and lineage remain available.'
                      : 'This revision is not eligible for remote generation. Choose a generated revision whose approved remote-safe input binding is retained.');
                return (
                  <article key={post.post_id} style={cardStyle}>
                    <div style={cardHeaderStyle}>
                      <div>
                        <strong style={{ color: 'white' }}>{post.thesis}</strong>
                        <p style={helperStyle}>{readable(post.status)} · {post.revisions.length} linked revision{post.revisions.length === 1 ? '' : 's'}</p>
                      </div>
                      <select
                        aria-label={`Select revision for ${post.thesis}`}
                        value={revision?.revision_id ?? ''}
                        onChange={(event) => setSelectedByPost((current) => ({ ...current, [post.post_id]: event.target.value }))}
                        style={selectStyle}
                      >
                        {post.revisions.map((candidate, index) => (
                          <option key={candidate.revision_id} value={candidate.revision_id}>
                            {index + 1}. {revisionLabel(candidate)}
                          </option>
                        ))}
                      </select>
                      <p style={helperStyle}>Revision toggling is review-only. It does not select, approve, reject, or publish canonical copy.</p>
                    </div>
                    {revision ? (
                      <>
                        <pre style={copyStyle}>{revision.body}</pre>
                        <div style={pillRowStyle}>
                          <span style={pillStyle}>{revisionLabel(revision)}</span>
                          {Object.entries(revision.controls).map(([key, value]) => <span key={key} style={pillStyle}>{readable(key)}: {String(value)}</span>)}
                          <span style={pillStyle}>SHA {revision.content_sha256.slice(0, 10)}…</span>
                        </div>
                        <div aria-label={`Variant controls for ${post.thesis}`} style={{ ...pillRowStyle, alignItems: 'center' }}>
                          {post.variant_control_options.map((control) => {
                            const currentControls = variantControls[post.post_id] ?? initializeVariantControls(post.variant_control_options);
                            return (
                              <label key={control.key} style={helperStyle}>{control.label}{' '}
                                <select
                                  aria-label={`${control.label} for ${post.thesis}`}
                                  value={currentControls[control.key] ?? control.default}
                                  disabled={generationBusy || !variantGenerationReady}
                                  onChange={(event) => setVariantControls((current) => ({
                                    ...current,
                                    [post.post_id]: updateVariantControl(post.variant_control_options, currentControls, control.key, event.target.value),
                                  }))}
                                  style={selectStyle}
                                >
                                  {!control.default ? <option value="">Keep current</option> : null}
                                  {control.values.map((value) => <option key={value} value={value}>{readable(value)}</option>)}
                                </select>
                              </label>
                            );
                          })}
                          <button
                            type="button"
                            disabled={generationBusy || !variantGenerationReady}
                            onClick={() => void requestVariant(post, revision.revision_id, 'linkedin')}
                            style={buttonStyle}
                          >
                            {generationBusy ? 'Variant in progress…' : 'LinkedIn variant'}
                          </button>
                          <button
                            type="button"
                            disabled={generationBusy || !variantGenerationReady}
                            onClick={() => void requestVariant(post, revision.revision_id, 'instagram')}
                            style={buttonStyle}
                          >
                            {generationBusy ? 'Variant in progress…' : 'Instagram variant'}
                          </button>
                        </div>
                        {!variantGenerationReady ? <p role="status" style={helperStyle}>{variantGenerationReason}</p> : null}
                        {variantStatus[post.post_id] ? <p role="status" style={helperStyle}>{variantStatus[post.post_id]}</p> : null}
                        {revision.attribution.required ? (
                          <p style={helperStyle}>
                            Attribution: {safeExternalHttpsUrl(revision.attribution.public_source_url) ? (
                              <a href={safeExternalHttpsUrl(revision.attribution.public_source_url) ?? undefined} target="_blank" rel="noreferrer" style={{ color: '#7dd3fc' }}>
                                {revision.attribution.public_source_name || 'Original source'}
                              </a>
                            ) : revision.attribution.public_source_name || 'Required before publication'}
                          </p>
                        ) : null}
                        {revision.revision_kind === 'variant' ? (
                          <div style={ownerActionPanelStyle} aria-label={`Exact variant decision for ${post.thesis}`}>
                            <div>
                              <strong style={microHeadingStyle}>Exact variant decision</strong>
                              <p style={helperStyle}>Selection or rejection binds revision {revision.revision_id} and SHA-256 {revision.content_sha256}.</p>
                            </div>
                            <div style={pillRowStyle}>
                              <button
                                type="button"
                                disabled={
                                  projection.controller_capabilities.variant_selection !== true
                                  || actionBusy
                                  || isExactCurrent
                                  || hasVariantRejection
                                  || post.status === 'published'
                                }
                                onClick={() => void submitLearningAction({ post, revision, eventKind: 'variant_selected' })}
                                style={buttonStyle}
                              >
                                {isExactCurrent || hasVariantSelection ? 'Exact variant selected' : 'Select exact variant'}
                              </button>
                              <button
                                type="button"
                                disabled={
                                  projection.controller_capabilities.variant_rejection !== true
                                  || actionBusy
                                  || isExactCurrent
                                  || hasVariantSelection
                                  || hasVariantRejection
                                  || post.status === 'published'
                                }
                                onClick={() => void submitLearningAction({ post, revision, eventKind: 'variant_rejected' })}
                                style={buttonStyle}
                              >
                                {hasVariantRejection ? 'Variant rejected' : 'Reject exact variant'}
                              </button>
                            </div>
                          </div>
                        ) : null}
                        {editDraft ? (
                          <div style={ownerActionPanelStyle} aria-label={`Immutable edit for ${post.thesis}`}>
                            <div>
                              <strong style={microHeadingStyle}>Immutable owner edit</strong>
                              <p style={helperStyle}>Saving creates a child revision; it never overwrites the selected bytes. Only the exact current revision may be edited.</p>
                            </div>
                            <textarea
                              aria-label={`Edited copy for ${post.thesis}`}
                              value={editDraft.body}
                              rows={10}
                              disabled={
                                projection.controller_capabilities.manual_edit_classification !== true
                                || actionBusy
                                || !isExactCurrent
                                || post.status === 'published'
                              }
                              onChange={(event) => setEditDrafts((current) => ({
                                ...current,
                                [post.post_id]: {
                                  parentRevisionId: revision.revision_id,
                                  body: event.target.value,
                                  editClassification: editDraft.editClassification,
                                },
                              }))}
                              style={textareaStyle}
                            />
                            <div style={pillRowStyle}>
                              <label style={helperStyle}>Edit classification{' '}
                                <select
                                  aria-label={`Edit classification for ${post.thesis}`}
                                  value={editDraft.editClassification}
                                  disabled={
                                    projection.controller_capabilities.manual_edit_classification !== true
                                    || actionBusy
                                    || !isExactCurrent
                                    || post.status === 'published'
                                  }
                                  onChange={(event) => setEditDrafts((current) => ({
                                    ...current,
                                    [post.post_id]: {
                                      parentRevisionId: revision.revision_id,
                                      body: editDraft.body,
                                      editClassification: event.target.value as '' | EditClassification,
                                    },
                                  }))}
                                  style={selectStyle}
                                >
                                  <option value="">Choose one</option>
                                  {EDIT_CLASSIFICATIONS.map((classification) => (
                                    <option key={classification} value={classification}>{readable(classification)}</option>
                                  ))}
                                </select>
                              </label>
                              <button
                                type="button"
                                disabled={
                                  projection.controller_capabilities.manual_edit_classification !== true
                                  || actionBusy
                                  || !isExactCurrent
                                  || post.status === 'published'
                                  || !editDraft.editClassification
                                  || editDraft.body.trim() === revision.body.trim()
                                }
                                onClick={() => void submitManualEdit(post, revision, editDraft)}
                                style={buttonStyle}
                              >
                                Save immutable edit
                              </button>
                            </div>
                            {!isExactCurrent ? <p role="alert" style={helperStyle}>Toggle back to the exact current revision before creating an edit.</p> : null}
                          </div>
                        ) : null}
                        <div style={ownerActionPanelStyle} aria-label={`Integrity approval for ${post.thesis}`}>
                          <div>
                            <strong style={microHeadingStyle}>Owner integrity approval</strong>
                            <p style={helperStyle}>Approval is bound to this exact revision and requires all four explicit attestations.</p>
                          </div>
                          <div style={pillRowStyle}>
                            {(Object.keys(EMPTY_INTEGRITY_CONFIRMATION) as Array<keyof IntegrityConfirmation>).map((key) => (
                              <label key={key} style={checkLabelStyle}>
                                <input
                                  type="checkbox"
                                  checked={integrityConfirmation[key]}
                                  disabled={
                                    projection.controller_capabilities.owner_approval !== true
                                    || actionBusy
                                    || !isExactCurrent
                                    || hasOwnerApproval
                                    || post.status === 'published'
                                  }
                                  onChange={(event) => setIntegrityConfirmations((current) => ({
                                    ...current,
                                    [actionKey]: { ...integrityConfirmation, [key]: event.target.checked },
                                  }))}
                                />
                                {readable(key)} confirmed
                              </label>
                            ))}
                          </div>
                          <button
                            type="button"
                            disabled={
                              projection.controller_capabilities.owner_approval !== true
                              || actionBusy
                              || !isExactCurrent
                              || hasOwnerApproval
                              || post.status === 'published'
                              || !Object.values(integrityConfirmation).every(Boolean)
                            }
                            onClick={() => void submitLearningAction({
                              post,
                              revision,
                              eventKind: 'owner_approved',
                              eventAt: new Date().toISOString(),
                              integrityConfirmation,
                            })}
                            style={buttonStyle}
                          >
                            {hasOwnerApproval ? 'Exact revision approved' : 'Approve exact revision'}
                          </button>
                        </div>
                        <div style={ownerActionPanelStyle} aria-label={`Publication confirmation for ${post.thesis}`}>
                          <div>
                            <strong style={microHeadingStyle}>Publication confirmation</strong>
                            <p style={helperStyle}>Confirm only after publishing this exact approved revision yourself on the native platform.</p>
                          </div>
                          <div style={publicationGridStyle}>
                            <label style={helperStyle}>Platform{' '}
                              <select
                                aria-label={`Publication platform for ${post.thesis}`}
                                value={publicationForm.platform}
                                disabled={
                                  projection.controller_capabilities.publication_confirmation !== true
                                  || actionBusy
                                  || post.status !== 'approved'
                                  || !isExactCurrent
                                  || hasPublication
                                }
                                onChange={(event) => setPublicationForms((current) => ({
                                  ...current,
                                  [actionKey]: { ...publicationForm, platform: event.target.value as PublicationPlatform },
                                }))}
                                style={selectStyle}
                              >
                                <option value="linkedin">LinkedIn</option>
                                <option value="instagram">Instagram</option>
                              </select>
                            </label>
                            <label style={helperStyle}>Published item URL{' '}
                              <input
                                aria-label={`Published item URL for ${post.thesis}`}
                                type="url"
                                value={publicationForm.publicUrl}
                                disabled={
                                  projection.controller_capabilities.publication_confirmation !== true
                                  || actionBusy
                                  || post.status !== 'approved'
                                  || !isExactCurrent
                                  || hasPublication
                                }
                                onChange={(event) => setPublicationForms((current) => ({
                                  ...current,
                                  [actionKey]: { ...publicationForm, publicUrl: event.target.value },
                                }))}
                                placeholder={`https://www.${publicationForm.platform}.com/…`}
                                style={{ ...selectStyle, maxWidth: 'none', width: '100%' }}
                              />
                            </label>
                            <label style={helperStyle}>Published at{' '}
                              <input
                                aria-label={`Publication time for ${post.thesis}`}
                                type="datetime-local"
                                value={publicationForm.eventAt}
                                disabled={
                                  projection.controller_capabilities.publication_confirmation !== true
                                  || actionBusy
                                  || post.status !== 'approved'
                                  || !isExactCurrent
                                  || hasPublication
                                }
                                onChange={(event) => setPublicationForms((current) => ({
                                  ...current,
                                  [actionKey]: { ...publicationForm, eventAt: event.target.value },
                                }))}
                                style={{ ...selectStyle, maxWidth: 'none', width: '100%' }}
                              />
                            </label>
                          </div>
                          <button
                            type="button"
                            disabled={
                              projection.controller_capabilities.publication_confirmation !== true
                              || actionBusy
                              || post.status !== 'approved'
                              || !isExactCurrent
                              || hasPublication
                              || !publicationForm.publicUrl.trim()
                              || !publicationForm.eventAt
                            }
                            onClick={() => void submitLearningAction({
                              post,
                              revision,
                              eventKind: 'publication_confirmed',
                              eventAt: publicationForm.eventAt,
                              platform: publicationForm.platform,
                              publicUrl: publicationForm.publicUrl,
                            })}
                            style={buttonStyle}
                          >
                            {hasPublication ? 'Publication confirmed' : 'Confirm exact published revision'}
                          </button>
                        </div>
                        {ownerActionStatus[post.post_id] ? <p role="status" style={noticeStyle}>{ownerActionStatus[post.post_id]}</p> : null}
                        <details>
                          <summary style={detailsSummaryStyle}>Complete source-to-decision lineage</summary>
                          <div style={{ ...lineageGridStyle, marginTop: '9px' }}>
                            {Object.entries(post.lineage).map(([key, value]) => (
                              <p key={key} style={helperStyle}><strong>{readable(key)}:</strong> {Array.isArray(value) ? value.join(', ') || 'none' : value || 'none'}</p>
                            ))}
                          </div>
                        </details>
                        {post.learning_events.length ? (
                          <details>
                            <summary style={detailsSummaryStyle}>Owner learning and publication events ({post.learning_events.length})</summary>
                            <ul style={compactListStyle}>
                              {post.learning_events.map((event) => (
                                <li key={event.learning_event_id}>
                                  <strong>{readable(event.event_kind)}</strong>{event.edit_classification ? ` · ${readable(event.edit_classification)}` : ''} · {formatUiTimestamp(event.occurred_at)}
                                  {Object.keys(event.summary).length ? ` · ${summaryText(event.summary)}` : ''}
                                </li>
                              ))}
                            </ul>
                          </details>
                        ) : null}
                        {post.persona_candidates.length ? (
                          <details>
                            <summary style={detailsSummaryStyle}>Persona candidates ({post.persona_candidates.length})</summary>
                            <ul style={compactListStyle}>
                              {post.persona_candidates.map((candidate) => (
                                <li key={candidate.persona_candidate_id}>
                                  <strong>{readable(candidate.candidate_kind)}</strong> · {readable(candidate.status)} · {summaryText(candidate.claim)} · {candidate.qualifying_post_count}/3 approved published posts · {candidate.independent_context_count}/2 contexts · {candidate.automatic_promotion_eligible ? 'eligible under the governed reversible-pattern rule' : 'not eligible for automatic promotion'} · lifecycle verified from canonical learning events
                                </li>
                              ))}
                            </ul>
                          </details>
                        ) : null}
                        {post.decisions.length ? (
                          <details>
                            <summary style={detailsSummaryStyle}>Linked canonical decisions ({post.decisions.length})</summary>
                            <ul style={compactListStyle}>{post.decisions.map((decision) => <li key={decision.decision_id}><strong>{decision.title}</strong> · {readable(decision.status)} · v{decision.state_version}</li>)}</ul>
                          </details>
                        ) : null}
                      </>
                    ) : <p style={noticeStyle}>No readable revision is available for this post.</p>}
                  </article>
                );
              })}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

const panelStyle = { padding: '20px', borderRadius: '14px', border: '1px solid rgba(56,189,248,0.24)', background: 'rgba(15,23,42,0.82)', display: 'grid', gap: '16px', minWidth: 0, width: '100%', boxSizing: 'border-box' as const, overflowWrap: 'anywhere' as const };
const eyebrowStyle = { margin: 0, color: '#38bdf8', fontSize: '11px', fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase' as const };
const helperStyle = { margin: '4px 0 0', color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, overflowWrap: 'anywhere' as const };
const noticeStyle = { margin: 0, padding: '10px 12px', borderRadius: '9px', background: 'rgba(30,41,59,0.72)', color: '#cbd5e1', fontSize: '12px' };
const buttonStyle = { border: '1px solid rgba(56,189,248,0.45)', borderRadius: '8px', background: 'rgba(14,116,144,0.24)', color: '#bae6fd', padding: '8px 12px', cursor: 'pointer' };
const statusRowStyle = { display: 'flex', gap: '12px', flexWrap: 'wrap' as const, color: '#94a3b8', fontSize: '12px', alignItems: 'center' };
const pillRowStyle = { display: 'flex', gap: '7px', flexWrap: 'wrap' as const };
const pillStyle = { padding: '4px 7px', border: '1px solid rgba(148,163,184,0.22)', borderRadius: '999px', color: '#cbd5e1', fontSize: '11px', background: 'rgba(15,23,42,0.58)' };
const headingStyle = { margin: '4px 0 0', color: '#e2e8f0', fontSize: '14px' };
const cardStyle = { padding: '13px', borderRadius: '10px', border: '1px solid rgba(148,163,184,0.18)', background: 'rgba(2,6,23,0.52)', display: 'grid', gap: '10px', minWidth: 0 };
const cardHeaderStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' as const };
const selectStyle = { width: 'min(100%, 240px)', maxWidth: '100%', minWidth: 0, boxSizing: 'border-box' as const, borderRadius: '7px', border: '1px solid rgba(148,163,184,0.28)', background: '#0f172a', color: '#e2e8f0', padding: '7px' };
const copyStyle = { margin: 0, padding: '12px', maxHeight: '320px', overflow: 'auto', whiteSpace: 'pre-wrap' as const, overflowWrap: 'anywhere' as const, borderRadius: '8px', background: 'rgba(15,23,42,0.9)', color: '#e2e8f0', fontFamily: 'inherit', fontSize: '13px', lineHeight: 1.6 };
const lineageGridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '9px', minWidth: 0 };
const nestedCardStyle = { padding: '10px', borderRadius: '8px', border: '1px solid rgba(148,163,184,0.16)', background: 'rgba(15,23,42,0.52)', display: 'grid', gap: '5px', minWidth: 0, overflowWrap: 'anywhere' as const };
const microHeadingStyle = { color: '#cbd5e1', fontSize: '12px' };
const detailsSummaryStyle = { color: '#bae6fd', cursor: 'pointer', fontSize: '12px' };
const compactListStyle = { color: '#cbd5e1', margin: '8px 0 0', paddingLeft: '20px', display: 'grid', gap: '6px', fontSize: '12px', lineHeight: 1.5, minWidth: 0, overflowWrap: 'anywhere' as const };
const interpretationStyle = { display: 'grid', gap: '3px', borderLeft: '2px solid rgba(56,189,248,.45)', paddingLeft: '8px', color: '#cbd5e1', fontSize: '12px', minWidth: 0, overflowWrap: 'anywhere' as const };
const ownerActionPanelStyle = { padding: '11px', borderRadius: '9px', border: '1px solid rgba(56,189,248,0.2)', background: 'rgba(15,23,42,0.62)', display: 'grid', gap: '9px' };
const textareaStyle = { width: '100%', boxSizing: 'border-box' as const, resize: 'vertical' as const, borderRadius: '8px', border: '1px solid rgba(148,163,184,0.28)', background: '#0f172a', color: '#e2e8f0', padding: '10px', fontFamily: 'inherit', fontSize: '13px', lineHeight: 1.55 };
const checkLabelStyle = { display: 'inline-flex', gap: '6px', alignItems: 'center', color: '#cbd5e1', fontSize: '12px' };
const publicationGridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '9px', alignItems: 'end' };
