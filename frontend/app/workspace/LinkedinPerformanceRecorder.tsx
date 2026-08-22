'use client';

import { useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from 'react';

import { controlApiGet, controlApiPost } from '@/lib/control-api';

export type LinkedinPerformanceEventType =
  | 'owner_reviewed'
  | 'publication_confirmed'
  | 'metrics_24h_recorded'
  | 'metrics_7d_recorded'
  | 'owner_assessment_recorded';

type JobStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed';

type LinkedinPerformanceJob = {
  job_id?: string;
  card_id?: string;
  status: Exclude<JobStatus, 'idle'>;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
  message?: string | null;
  error?: string | null;
};

type QueueResponse = LinkedinPerformanceJob & {
  queued: boolean;
  disposition?: string;
  data_policy?: {
    canonical_writer?: string;
    railway_role?: string;
    raw_copy_accepted?: boolean;
    private_notes_accepted?: boolean;
  };
};

type SubmittedContext = {
  eventType: LinkedinPerformanceEventType;
  identity: string;
  ownerDecision: FormState['ownerDecision'];
  publishedAt: string;
};

export type LinkedinPerformanceVerifiedLifecycle = {
  contentId: string;
  contentVersionSha256: string;
  approvalCompleted?: boolean;
  publicationConfirmed?: boolean;
  publishedAt?: string;
};

export type LinkedinPerformanceRecorderProps = {
  initialContentId?: string;
  initialContentVersionSha256?: string;
  initialClassification?: LinkedinPerformanceInitialClassification;
  verifiedLifecycle?: LinkedinPerformanceVerifiedLifecycle;
  pollIntervalMs?: number;
  onJobCompleted?: (eventType: LinkedinPerformanceEventType, job: LinkedinPerformanceJob) => void;
};

type FormState = {
  contentId: string;
  digest: string;
  idempotencyKey: string;
  occurredAt: string;
  ownerDecision: 'approve' | 'revise' | 'park' | 'reject';
  approvalRef: string;
  ownerEditMinutes: string;
  ownerEditRatio: string;
  publicationUrl: string;
  publishedAt: string;
  confirmationMethod: 'manual_url' | 'opened_post' | 'screenshot' | 'authorized_export';
  evidenceRef: string;
  pillarId: 'ai_native' | 'leadership_operator' | 'trust_systems';
  intent: 'value' | 'invitation' | 'personal';
  treatment: string;
  careerSignal: 'education_anchor' | 'bridge' | 'tech_proof';
  employerSafety: 'pass' | 'owner_review_required';
  proofPosture: 'verified_public' | 'verified_private_anonymize' | 'owner_confirmation_required' | 'principle_only';
  hookFamily: string;
  format: string;
  audience: string;
  experimentId: string;
  referencePublishedAt: string;
  metricSource: 'manual_linkedin_analytics' | 'authorized_export';
  impressions: string;
  membersReached: string;
  reactions: string;
  comments: string;
  reposts: string;
  saves: string;
  sends: string;
  profileViews: string;
  newFollowers: string;
  meaningfulComments: string;
  targetAudienceComments: string;
  meaningfulTargetConversations: string;
  outcomeDm: string;
  outcomeReferral: string;
  outcomeSpeaking: string;
  outcomeRecruiting: string;
  outcomePartnership: string;
  outcomeCareerSignal: string;
  outcomeTechnologyConversation: string;
  outcomeEducationCommunity: string;
  soundedLikeMe: '' | 'yes' | 'mixed' | 'no';
  followUp: '' | 'reuse' | 'iterate' | 'retire' | 'none';
};

export type LinkedinPerformanceInitialClassification = {
  pillarId?: FormState['pillarId'];
  intent?: FormState['intent'];
  treatment?: string;
  careerSignal?: FormState['careerSignal'];
  employerSafety?: FormState['employerSafety'];
  proofPosture?: FormState['proofPosture'];
  hookFamily?: string;
  format?: string;
  audience?: string | string[];
  experimentId?: string;
};

type NormalizedClassification = Required<LinkedinPerformanceInitialClassification> & { audience: string };

const EVENT_OPTIONS: Array<{ value: LinkedinPerformanceEventType; label: string; step: string }> = [
  { value: 'owner_reviewed', label: 'Owner decision', step: '1' },
  { value: 'publication_confirmed', label: 'Confirm publication', step: '2' },
  { value: 'metrics_24h_recorded', label: 'Record 24h metrics', step: '3' },
  { value: 'metrics_7d_recorded', label: 'Record 7d metrics', step: '4' },
  { value: 'owner_assessment_recorded', label: 'Owner assessment', step: '5' },
];

const METRIC_FIELDS: Array<{ key: keyof FormState; api: string; label: string }> = [
  { key: 'impressions', api: 'impressions', label: 'Impressions' },
  { key: 'membersReached', api: 'members_reached', label: 'Members reached' },
  { key: 'reactions', api: 'reactions', label: 'Reactions' },
  { key: 'comments', api: 'comments', label: 'Comments' },
  { key: 'reposts', api: 'reposts', label: 'Reposts' },
  { key: 'saves', api: 'saves', label: 'Saves' },
  { key: 'sends', api: 'sends', label: 'Sends' },
  { key: 'profileViews', api: 'profile_views', label: 'Profile views' },
  { key: 'newFollowers', api: 'new_followers', label: 'New followers' },
  { key: 'meaningfulComments', api: 'meaningful_comments', label: 'Meaningful comments' },
  { key: 'targetAudienceComments', api: 'target_audience_comments', label: 'Target-audience comments' },
];

const OUTCOME_FIELDS: Array<{ key: keyof FormState; api: string; label: string }> = [
  { key: 'outcomeDm', api: 'dm', label: 'DMs' },
  { key: 'outcomeReferral', api: 'referral', label: 'Referrals' },
  { key: 'outcomeSpeaking', api: 'speaking', label: 'Speaking' },
  { key: 'outcomeRecruiting', api: 'recruiting', label: 'Recruiting' },
  { key: 'outcomePartnership', api: 'partnership', label: 'Partnerships' },
  { key: 'outcomeCareerSignal', api: 'career_signal', label: 'Career signals' },
  { key: 'outcomeTechnologyConversation', api: 'technology_conversation', label: 'Technology conversations' },
  { key: 'outcomeEducationCommunity', api: 'education_community', label: 'Education/community outcomes' },
];

const QUALITY_FLAGS = ['too_generic', 'too_safe', 'too_exposed', 'wrong_audience'] as const;
const SHA256_RE = /^(?:sha256:)?[a-fA-F0-9]{64}$/;
const PILLAR_CAREER_SIGNAL: Record<FormState['pillarId'], FormState['careerSignal']> = {
  ai_native: 'tech_proof',
  leadership_operator: 'bridge',
  trust_systems: 'education_anchor',
};
const PILOT_TREATMENTS = new Set([
  'practical_ai_systems',
  'education_or_trust',
  'operator_story_personal_technology',
  'operator_story_education_community',
]);

function isOneOf<T extends string>(value: unknown, options: readonly T[]): value is T {
  return typeof value === 'string' && options.includes(value as T);
}

function normalizeInitialClassification(value?: LinkedinPerformanceInitialClassification): NormalizedClassification {
  const suppliedCareerSignal = isOneOf(value?.careerSignal, ['education_anchor', 'bridge', 'tech_proof'] as const)
    ? value.careerSignal
    : undefined;
  const inferredPillar = suppliedCareerSignal === 'education_anchor'
    ? 'trust_systems'
    : suppliedCareerSignal === 'bridge'
      ? 'leadership_operator'
      : 'ai_native';
  const pillarId = isOneOf(value?.pillarId, ['ai_native', 'leadership_operator', 'trust_systems'] as const)
    ? value.pillarId
    : inferredPillar;
  const intent = isOneOf(value?.intent, ['value', 'invitation', 'personal'] as const) ? value.intent : 'value';
  const employerSafety = isOneOf(value?.employerSafety, ['pass', 'owner_review_required'] as const)
    ? value.employerSafety
    : 'pass';
  const proofPosture = isOneOf(
    value?.proofPosture,
    ['verified_public', 'verified_private_anonymize', 'owner_confirmation_required', 'principle_only'] as const,
  )
    ? value.proofPosture
    : 'verified_public';
  const experimentId = String(value?.experimentId ?? 'initial_six_post_pilot').trim().slice(0, 120);
  const requestedTreatment = String(value?.treatment ?? 'practical_ai_systems').trim().slice(0, 120);
  const treatment =
    experimentId === 'initial_six_post_pilot' && !PILOT_TREATMENTS.has(requestedTreatment)
      ? 'practical_ai_systems'
      : requestedTreatment || 'practical_ai_systems';
  const audience = (Array.isArray(value?.audience) ? value?.audience : String(value?.audience ?? '').split(','))
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 12)
    .join(', ');

  return {
    pillarId,
    intent,
    treatment,
    // Canonical pillar mapping wins over a stale or mismatched caller value.
    careerSignal: PILLAR_CAREER_SIGNAL[pillarId],
    employerSafety,
    proofPosture,
    hookFamily: String(value?.hookFamily ?? '').trim().slice(0, 120),
    format: String(value?.format ?? 'text').trim().slice(0, 80) || 'text',
    audience,
    experimentId,
  };
}

function requestedSeed(props: LinkedinPerformanceRecorderProps) {
  const hasInitialIdentity = props.initialContentId !== undefined || props.initialContentVersionSha256 !== undefined;
  const lifecycle = props.verifiedLifecycle;
  const lifecycleMatchesInitial =
    Boolean(lifecycle) &&
    (!props.initialContentId || props.initialContentId.trim() === lifecycle?.contentId.trim()) &&
    (!props.initialContentVersionSha256 ||
      normalizeDigest(props.initialContentVersionSha256) === normalizeDigest(lifecycle?.contentVersionSha256 ?? ''));
  return {
    identityProvided: hasInitialIdentity || Boolean(lifecycle),
    contentId: hasInitialIdentity
      ? props.initialContentId ?? (lifecycleMatchesInitial ? lifecycle?.contentId : '')
      : lifecycle?.contentId,
    digest: hasInitialIdentity
      ? props.initialContentVersionSha256 ?? (lifecycleMatchesInitial ? lifecycle?.contentVersionSha256 : '')
      : lifecycle?.contentVersionSha256,
    classification: normalizeInitialClassification(props.initialClassification),
  };
}

const panelStyle: CSSProperties = {
  background: 'linear-gradient(145deg, rgba(7,16,31,0.98), rgba(10,22,42,0.98))',
  border: '1px solid rgba(56,189,248,0.2)',
  borderRadius: 16,
  color: '#e2e8f0',
  display: 'grid',
  gap: 16,
  padding: 18,
};

const fieldStyle: CSSProperties = {
  backgroundColor: '#07101f',
  border: '1px solid #26364d',
  borderRadius: 9,
  color: '#e2e8f0',
  fontSize: 13,
  minHeight: 40,
  padding: '9px 10px',
  width: '100%',
};

const labelStyle: CSSProperties = {
  color: '#cbd5e1',
  display: 'grid',
  fontSize: 12,
  fontWeight: 650,
  gap: 6,
};

function localDateTimeValue(value?: string) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIsoDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function normalizeDigest(value: string) {
  return value.trim().replace(/^sha256:/i, '').toLowerCase();
}

function identityKey(contentId: string, digest: string) {
  const normalized = normalizeDigest(digest);
  return contentId.trim() && SHA256_RE.test(normalized) ? `${contentId.trim()}:${normalized}` : '';
}

function optionalNumber(value: string) {
  return value.trim() === '' ? undefined : Number(value);
}

function makeIdempotencyKey(eventType: LinkedinPerformanceEventType, form: FormState) {
  const occurred = (toIsoDate(form.occurredAt) ?? form.occurredAt).replace(/[^0-9A-Za-z]/g, '').slice(0, 20);
  return `${form.contentId.trim()}:${eventType}:${normalizeDigest(form.digest).slice(0, 12)}:${occurred}`;
}

function initialForm(props: LinkedinPerformanceRecorderProps): FormState {
  const seed = requestedSeed(props);
  const seedIdentity = identityKey(seed.contentId ?? '', seed.digest ?? '');
  const lifecycleIdentity = identityKey(
    props.verifiedLifecycle?.contentId ?? '',
    props.verifiedLifecycle?.contentVersionSha256 ?? '',
  );
  const initialPublishedAt = seedIdentity && seedIdentity === lifecycleIdentity
    ? props.verifiedLifecycle?.publishedAt
    : undefined;
  const classification = normalizeInitialClassification(props.initialClassification);
  return {
    contentId: seed.contentId ?? '',
    digest: seed.digest ?? '',
    idempotencyKey: '',
    occurredAt: localDateTimeValue(),
    ownerDecision: 'approve',
    approvalRef: '',
    ownerEditMinutes: '',
    ownerEditRatio: '',
    publicationUrl: '',
    publishedAt: localDateTimeValue(initialPublishedAt),
    confirmationMethod: 'manual_url',
    evidenceRef: '',
    pillarId: classification.pillarId,
    intent: classification.intent,
    treatment: classification.treatment,
    careerSignal: classification.careerSignal,
    employerSafety: classification.employerSafety,
    proofPosture: classification.proofPosture,
    hookFamily: classification.hookFamily,
    format: classification.format,
    audience: classification.audience,
    experimentId: classification.experimentId,
    referencePublishedAt: initialPublishedAt ? localDateTimeValue(initialPublishedAt) : '',
    metricSource: 'manual_linkedin_analytics',
    impressions: '',
    membersReached: '',
    reactions: '',
    comments: '',
    reposts: '',
    saves: '',
    sends: '',
    profileViews: '',
    newFollowers: '',
    meaningfulComments: '',
    targetAudienceComments: '',
    meaningfulTargetConversations: '',
    outcomeDm: '',
    outcomeReferral: '',
    outcomeSpeaking: '',
    outcomeRecruiting: '',
    outcomePartnership: '',
    outcomeCareerSignal: '',
    outcomeTechnologyConversation: '',
    outcomeEducationCommunity: '',
    soundedLikeMe: '',
    followUp: '',
  };
}

function statusTone(status: JobStatus) {
  if (status === 'completed') return '#34d399';
  if (status === 'failed') return '#f87171';
  if (status === 'running') return '#38bdf8';
  if (status === 'queued') return '#fbbf24';
  return '#94a3b8';
}

function statusCopy(status: JobStatus) {
  if (status === 'queued') return 'Queued on Railway; waiting for the signed local worker.';
  if (status === 'running') return 'Running locally; the private ledger has not confirmed completion yet.';
  if (status === 'completed') return 'Completed in the canonical private ledger.';
  if (status === 'failed') return 'Failed; no successful ledger receipt was returned.';
  return 'Nothing has been queued.';
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label style={labelStyle}>
      <span>{label}</span>
      {children}
      {hint ? <span style={{ color: '#64748b', fontSize: 10, fontWeight: 450, lineHeight: 1.4 }}>{hint}</span> : null}
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  max,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  max?: number;
}) {
  return (
    <Field label={label}>
      <input
        min="0"
        max={max}
        step="1"
        inputMode="numeric"
        style={fieldStyle}
        type="number"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

export default function LinkedinPerformanceRecorder(props: LinkedinPerformanceRecorderProps) {
  const verifiedLifecyclePublishedAt = props.verifiedLifecycle?.publishedAt;
  const onJobCompleted = props.onJobCompleted;
  const pollIntervalMs = props.pollIntervalMs;
  const externalSeed = requestedSeed(props);
  const externalSeedToken = JSON.stringify(externalSeed);
  const appliedSeedToken = useRef(externalSeedToken);
  const [eventType, setEventType] = useState<LinkedinPerformanceEventType>('owner_reviewed');
  const [form, setForm] = useState<FormState>(() => initialForm(props));
  const [unavailableMetrics, setUnavailableMetrics] = useState<string[]>([]);
  const [qualityFlags, setQualityFlags] = useState<string[]>([]);
  const [job, setJob] = useState<LinkedinPerformanceJob | null>(null);
  const [submittedContext, setSubmittedContext] = useState<SubmittedContext | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [observedApprovalKey, setObservedApprovalKey] = useState('');
  const [observedPublicationKey, setObservedPublicationKey] = useState('');

  const currentIdentity = useMemo(() => identityKey(form.contentId, form.digest), [form.contentId, form.digest]);
  const verifiedIdentity = useMemo(
    () => identityKey(props.verifiedLifecycle?.contentId ?? '', props.verifiedLifecycle?.contentVersionSha256 ?? ''),
    [props.verifiedLifecycle?.contentId, props.verifiedLifecycle?.contentVersionSha256],
  );
  const approvalCompleted = Boolean(
    currentIdentity &&
      (observedApprovalKey === currentIdentity ||
        (props.verifiedLifecycle?.approvalCompleted === true && verifiedIdentity === currentIdentity)),
  );
  const publicationCompleted = Boolean(
    currentIdentity &&
      (observedPublicationKey === currentIdentity ||
        (props.verifiedLifecycle?.publicationConfirmed === true && verifiedIdentity === currentIdentity)),
  );
  const inFlight = submitting || job?.status === 'queued' || job?.status === 'running';
  const jobStatus: JobStatus = submitting ? 'queued' : job?.status ?? 'idle';

  function setValue<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function switchEvent(next: LinkedinPerformanceEventType) {
    if (inFlight) return;
    setEventType(next);
    setJob(null);
    setSubmittedContext(null);
    setError(null);
    setValue('idempotencyKey', '');
  }

  useEffect(() => {
    if (appliedSeedToken.current === externalSeedToken || inFlight) return;
    const seed = JSON.parse(externalSeedToken) as ReturnType<typeof requestedSeed>;
    const seedIdentity = identityKey(seed.contentId ?? '', seed.digest ?? '');
    const lifecyclePublishedAt = seedIdentity && seedIdentity === verifiedIdentity
      ? verifiedLifecyclePublishedAt
      : undefined;
    appliedSeedToken.current = externalSeedToken;
    setForm((current) => ({
      ...current,
      contentId: seed.identityProvided ? seed.contentId ?? '' : current.contentId,
      digest: seed.identityProvided ? seed.digest ?? '' : current.digest,
      idempotencyKey: '',
      occurredAt: localDateTimeValue(),
      publishedAt: lifecyclePublishedAt ? localDateTimeValue(lifecyclePublishedAt) : localDateTimeValue(),
      referencePublishedAt: lifecyclePublishedAt ? localDateTimeValue(lifecyclePublishedAt) : '',
      pillarId: seed.classification.pillarId,
      intent: seed.classification.intent,
      treatment: seed.classification.treatment,
      careerSignal: seed.classification.careerSignal,
      employerSafety: seed.classification.employerSafety,
      proofPosture: seed.classification.proofPosture,
      hookFamily: seed.classification.hookFamily,
      format: seed.classification.format,
      audience: seed.classification.audience,
      experimentId: seed.classification.experimentId,
    }));
    setEventType('owner_reviewed');
    setUnavailableMetrics([]);
    setQualityFlags([]);
    setJob(null);
    setSubmittedContext(null);
    setError(null);
  }, [externalSeedToken, inFlight, verifiedLifecyclePublishedAt, verifiedIdentity]);

  useEffect(() => {
    const publishedAt = verifiedLifecyclePublishedAt;
    if (!publishedAt || !currentIdentity || verifiedIdentity !== currentIdentity) return;
    const normalized = localDateTimeValue(publishedAt);
    setForm((current) => current.referencePublishedAt === normalized
      ? current
      : { ...current, referencePublishedAt: normalized });
  }, [currentIdentity, verifiedLifecyclePublishedAt, verifiedIdentity]);

  useEffect(() => {
    const cardId = job?.card_id ?? job?.job_id;
    const currentStatus = job?.status;
    if (!cardId || !submittedContext || (currentStatus !== 'queued' && currentStatus !== 'running')) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const next = await controlApiGet<LinkedinPerformanceJob>(
          `/api/workspace/linkedin-performance/jobs/${encodeURIComponent(cardId)}`,
          { timeoutMs: 20_000 },
        );
        if (cancelled) return;
        setJob(next);
        setError(null);
        if (next.status === 'completed') {
          if (submittedContext.eventType === 'owner_reviewed' && submittedContext.ownerDecision === 'approve') {
            setObservedApprovalKey(submittedContext.identity);
          }
          if (submittedContext.eventType === 'publication_confirmed') {
            setObservedPublicationKey(submittedContext.identity);
            setForm((current) => ({ ...current, referencePublishedAt: submittedContext.publishedAt }));
          }
          onJobCompleted?.(submittedContext.eventType, next);
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : 'Unable to read the local ledger job status.');
        }
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), Math.max(1_500, pollIntervalMs ?? 3_000));
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [
    job?.card_id,
    job?.job_id,
    job?.status,
    onJobCompleted,
    pollIntervalMs,
    submittedContext,
  ]);

  function validate(): string | null {
    if (!form.contentId.trim()) return 'Content ID is required.';
    if (!SHA256_RE.test(form.digest.trim())) return 'Enter the exact 64-character SHA-256 digest.';
    const occurredAt = toIsoDate(form.occurredAt);
    if (!occurredAt) return 'Occurred at must be a valid timestamp.';
    if (new Date(occurredAt).getTime() > Date.now() + 60_000) return 'Occurred at cannot be in the future.';

    if (eventType === 'publication_confirmed') {
      if (!approvalCompleted) {
        return 'A completed approval receipt for this exact content ID and digest is required first.';
      }
      if (!/^https:\/\/(?:www\.)?linkedin\.com\/(?:posts\/|feed\/update\/)/i.test(form.publicationUrl.trim())) {
        return 'Enter an HTTPS LinkedIn post URL using /posts/ or /feed/update/.';
      }
      const publishedAt = toIsoDate(form.publishedAt);
      if (!publishedAt) return 'Published at must be a valid timestamp.';
      if (new Date(publishedAt) > new Date(occurredAt)) return 'Published at cannot be later than occurred at.';
      if (!form.treatment.trim()) return 'Treatment is required.';
      const audiences = form.audience.split(',').map((item) => item.trim()).filter(Boolean);
      if (!audiences.length) return 'At least one intended audience is required.';
      if (audiences.length > 12) return 'Intended audience is limited to 12 canonical audience IDs.';
      if (form.careerSignal !== PILLAR_CAREER_SIGNAL[form.pillarId]) {
        return 'Career signal must match the owner-approved canonical pillar contract.';
      }
      if (form.experimentId.trim() === 'initial_six_post_pilot' && !PILOT_TREATMENTS.has(form.treatment.trim())) {
        return 'The initial six-post pilot requires one of its four approved treatments.';
      }
    }

    if (eventType === 'metrics_24h_recorded' || eventType === 'metrics_7d_recorded') {
      const reference = toIsoDate(form.referencePublishedAt);
      if (!reference) return 'Published-at reference is required for the observation-window check.';
      const windowHours = eventType === 'metrics_24h_recorded' ? 24 : 168;
      if (new Date(occurredAt).getTime() < new Date(reference).getTime() + windowHours * 3_600_000) {
        return `${eventType === 'metrics_24h_recorded' ? '24-hour' : '7-day'} metrics cannot be recorded before the full observation window.`;
      }
      const hasMetric = METRIC_FIELDS.some(({ key }) => form[key].trim() !== '');
      if (!hasMetric && unavailableMetrics.length === 0) {
        return 'Record at least one metric or mark at least one metric unavailable.';
      }
    }

    if (eventType === 'owner_assessment_recorded') {
      const reference = toIsoDate(form.referencePublishedAt);
      if (!reference) return 'Published-at reference is required before an owner assessment.';
      if (new Date(occurredAt) < new Date(reference)) return 'Owner assessment cannot occur before publication.';
      const hasOutcome = OUTCOME_FIELDS.some(({ key }) => form[key].trim() !== '');
      const hasAssessment =
        form.meaningfulTargetConversations.trim() !== '' ||
        hasOutcome ||
        Boolean(form.soundedLikeMe) ||
        qualityFlags.length > 0 ||
        Boolean(form.followUp);
      if (!hasAssessment) return 'Add at least one qualitative assessment or outcome.';
    }
    return null;
  }

  function buildPayload() {
    const common: Record<string, unknown> = {
      event_type: eventType,
      idempotency_key: form.idempotencyKey.trim() || makeIdempotencyKey(eventType, form),
      content_id: form.contentId.trim(),
      content_version_sha256: normalizeDigest(form.digest),
      occurred_at: toIsoDate(form.occurredAt),
    };

    if (eventType === 'owner_reviewed') {
      return {
        ...common,
        owner_decision: form.ownerDecision,
        ...(form.approvalRef.trim() ? { approval_ref: form.approvalRef.trim() } : {}),
        ...(optionalNumber(form.ownerEditMinutes) !== undefined
          ? { owner_edit_minutes: optionalNumber(form.ownerEditMinutes) }
          : {}),
        ...(optionalNumber(form.ownerEditRatio) !== undefined
          ? { owner_edit_ratio: optionalNumber(form.ownerEditRatio) }
          : {}),
      };
    }

    if (eventType === 'publication_confirmed') {
      return {
        ...common,
        confirmed: true,
        publication_url: form.publicationUrl.trim(),
        published_at: toIsoDate(form.publishedAt),
        confirmation_method: form.confirmationMethod,
        ...(form.evidenceRef.trim() ? { evidence_ref: form.evidenceRef.trim() } : {}),
        pillar_id: form.pillarId,
        intent: form.intent,
        treatment: form.treatment.trim(),
        career_signal: form.careerSignal,
        employer_safety: form.employerSafety,
        proof_posture: form.proofPosture,
        ...(form.hookFamily.trim() ? { hook_family: form.hookFamily.trim() } : {}),
        ...(form.format.trim() ? { format: form.format.trim() } : {}),
        audience: form.audience.split(',').map((item) => item.trim()).filter(Boolean).slice(0, 12),
        ...(form.experimentId.trim() ? { experiment_id: form.experimentId.trim() } : {}),
      };
    }

    if (eventType === 'metrics_24h_recorded' || eventType === 'metrics_7d_recorded') {
      const metrics = Object.fromEntries(
        METRIC_FIELDS.flatMap(({ key, api }) => {
          const value = optionalNumber(form[key]);
          return value === undefined ? [] : [[api, value]];
        }),
      );
      return {
        ...common,
        metrics,
        unavailable_metrics: unavailableMetrics,
        metric_source: form.metricSource,
      };
    }

    const outcomeCounts = Object.fromEntries(
      OUTCOME_FIELDS.flatMap(({ key, api }) => {
        const value = optionalNumber(form[key]);
        return value === undefined ? [] : [[api, value]];
      }),
    );
    return {
      ...common,
      ...(optionalNumber(form.meaningfulTargetConversations) !== undefined
        ? { meaningful_target_conversations: optionalNumber(form.meaningfulTargetConversations) }
        : {}),
      ...(Object.keys(outcomeCounts).length ? { outcome_counts: outcomeCounts } : {}),
      ...(form.soundedLikeMe ? { sounded_like_me: form.soundedLikeMe } : {}),
      quality_flags: qualityFlags,
      ...(form.followUp ? { follow_up: form.followUp } : {}),
    };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setSubmitting(true);
    setError(null);
    const stableIdempotencyKey = form.idempotencyKey.trim() || makeIdempotencyKey(eventType, form);
    setValue('idempotencyKey', stableIdempotencyKey);
    setSubmittedContext({
      eventType,
      identity: currentIdentity,
      ownerDecision: form.ownerDecision,
      publishedAt: form.publishedAt,
    });
    try {
      const response = await controlApiPost<QueueResponse>(
        '/api/workspace/linkedin-performance/events?legacy_compatibility=true',
        { ...buildPayload(), idempotency_key: stableIdempotencyKey },
        { timeoutMs: 20_000 },
      );
      setJob({ ...response, status: response.status ?? 'queued' });
    } catch (submitError) {
      setJob(null);
      setSubmittedContext(null);
      setError(submitError instanceof Error ? submitError.message : 'Unable to queue the evidence record.');
    } finally {
      setSubmitting(false);
    }
  }

  function renderOwnerReviewFields() {
    return (
      <div style={{ display: 'grid', gap: 12 }}>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
          <Field label="Owner decision">
            <select style={fieldStyle} value={form.ownerDecision} onChange={(event) => setValue('ownerDecision', event.target.value as FormState['ownerDecision'])}>
              <option value="approve">Approve exact version</option>
              <option value="revise">Revise</option>
              <option value="park">Park</option>
              <option value="reject">Reject</option>
            </select>
          </Field>
          <Field label="Approval reference" hint="Optional logical reference only; never paste a local file path.">
            <input style={fieldStyle} value={form.approvalRef} onChange={(event) => setValue('approvalRef', event.target.value)} placeholder="owner-review/queue-123" />
          </Field>
          <Field label="Owner edit minutes">
            <input min="0" max="1440" step="0.1" style={fieldStyle} type="number" value={form.ownerEditMinutes} onChange={(event) => setValue('ownerEditMinutes', event.target.value)} />
          </Field>
          <Field label="Owner edit ratio" hint="0 = unchanged; 1 = fully rewritten.">
            <input min="0" max="1" step="0.01" style={fieldStyle} type="number" value={form.ownerEditRatio} onChange={(event) => setValue('ownerEditRatio', event.target.value)} />
          </Field>
        </div>
      </div>
    );
  }

  function renderPublicationFields() {
    return (
      <div style={{ display: 'grid', gap: 14 }}>
        <div style={{ border: `1px solid ${approvalCompleted ? '#34d39955' : '#fbbf2455'}`, borderRadius: 10, color: approvalCompleted ? '#86efac' : '#fcd34d', fontSize: 12, lineHeight: 1.5, padding: 10 }}>
          {approvalCompleted
            ? 'Approval gate passed for this exact content ID and SHA-256 digest.'
            : 'Approval gate blocked. Complete an “Approve exact version” job for this same ID and digest before confirming publication.'}
        </div>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
          <Field label="LinkedIn post URL">
            <input style={fieldStyle} type="url" value={form.publicationUrl} onChange={(event) => setValue('publicationUrl', event.target.value)} placeholder="https://www.linkedin.com/posts/..." />
          </Field>
          <Field label="Published at">
            <input style={fieldStyle} type="datetime-local" value={form.publishedAt} onChange={(event) => setValue('publishedAt', event.target.value)} />
          </Field>
          <Field label="Confirmation method">
            <select style={fieldStyle} value={form.confirmationMethod} onChange={(event) => setValue('confirmationMethod', event.target.value as FormState['confirmationMethod'])}>
              <option value="manual_url">Manual URL</option>
              <option value="opened_post">Opened post</option>
              <option value="screenshot">Screenshot</option>
              <option value="authorized_export">Authorized export</option>
            </select>
          </Field>
          <Field label="Evidence reference" hint="Optional logical reference; no local path or private note.">
            <input style={fieldStyle} value={form.evidenceRef} onChange={(event) => setValue('evidenceRef', event.target.value)} placeholder="linkedin/evidence-2026-08-14" />
          </Field>
          <Field label="Canonical pillar">
            <select
              style={fieldStyle}
              value={form.pillarId}
              onChange={(event) => {
                const pillarId = event.target.value as FormState['pillarId'];
                setForm((current) => ({ ...current, pillarId, careerSignal: PILLAR_CAREER_SIGNAL[pillarId] }));
              }}
            >
              <option value="ai_native">AI-native intrapreneurship in education</option>
              <option value="leadership_operator">Leadership and operator clarity</option>
              <option value="trust_systems">Family, referral, and trust systems</option>
            </select>
          </Field>
          <Field label="Intent">
            <select style={fieldStyle} value={form.intent} onChange={(event) => setValue('intent', event.target.value as FormState['intent'])}>
              <option value="value">Value</option>
              <option value="invitation">Invitation</option>
              <option value="personal">Personal</option>
            </select>
          </Field>
          <Field label="Treatment">
            <select style={fieldStyle} value={form.treatment} onChange={(event) => setValue('treatment', event.target.value)}>
              {!PILOT_TREATMENTS.has(form.treatment) ? <option value={form.treatment}>{form.treatment}</option> : null}
              <option value="practical_ai_systems">Practical AI systems</option>
              <option value="education_or_trust">Education or trust</option>
              <option value="operator_story_personal_technology">Operator story · personal technology</option>
              <option value="operator_story_education_community">Operator story · education/community</option>
            </select>
          </Field>
          <Field label="Career signal" hint="Derived from the owner-approved canonical pillar contract.">
            <select disabled style={{ ...fieldStyle, opacity: 0.8 }} value={form.careerSignal} onChange={() => undefined}>
              <option value="tech_proof">Tech proof</option>
              <option value="bridge">Bridge</option>
              <option value="education_anchor">Education anchor</option>
            </select>
          </Field>
          <Field label="Employer safety">
            <select style={fieldStyle} value={form.employerSafety} onChange={(event) => setValue('employerSafety', event.target.value as FormState['employerSafety'])}>
              <option value="pass">Pass</option>
              <option value="owner_review_required">Owner review required</option>
            </select>
          </Field>
          <Field label="Proof posture">
            <select style={fieldStyle} value={form.proofPosture} onChange={(event) => setValue('proofPosture', event.target.value as FormState['proofPosture'])}>
              <option value="verified_public">Verified public</option>
              <option value="verified_private_anonymize">Verified private · anonymize</option>
              <option value="owner_confirmation_required">Owner confirmation required</option>
              <option value="principle_only">Principle only</option>
            </select>
          </Field>
          <Field label="Intended audience" hint="Comma-separated canonical audience IDs; maximum 12.">
            <input style={fieldStyle} value={form.audience} onChange={(event) => setValue('audience', event.target.value)} placeholder="ai_systems_operators, education_leaders" />
          </Field>
          <Field label="Experiment ID">
            <input style={fieldStyle} value={form.experimentId} onChange={(event) => setValue('experimentId', event.target.value)} />
          </Field>
          <Field label="Hook family">
            <input style={fieldStyle} value={form.hookFamily} onChange={(event) => setValue('hookFamily', event.target.value)} placeholder="contrarian" />
          </Field>
          <Field label="Format">
            <input style={fieldStyle} value={form.format} onChange={(event) => setValue('format', event.target.value)} placeholder="text" />
          </Field>
        </div>
      </div>
    );
  }

  function renderMetricFields() {
    const windowHours = eventType === 'metrics_24h_recorded' ? 24 : 168;
    return (
      <div style={{ display: 'grid', gap: 14 }}>
        <div style={{ border: '1px solid #38bdf844', borderRadius: 10, color: '#bae6fd', fontSize: 12, lineHeight: 1.5, padding: 10 }}>
          The form checks the full {windowHours}-hour window. The private ledger also requires a confirmed publication for this exact ID and digest; browser entry alone cannot establish publication truth.
        </div>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }}>
          <Field label="Published-at reference" hint="Browser-only time-window check; this value is not sent in the metrics payload.">
            <input style={fieldStyle} type="datetime-local" value={form.referencePublishedAt} onChange={(event) => setValue('referencePublishedAt', event.target.value)} />
          </Field>
          <Field label="Metric source">
            <select style={fieldStyle} value={form.metricSource} onChange={(event) => setValue('metricSource', event.target.value as FormState['metricSource'])}>
              <option value="manual_linkedin_analytics">Manual LinkedIn analytics</option>
              <option value="authorized_export">Authorized export</option>
            </select>
          </Field>
          {METRIC_FIELDS.map(({ key, label }) => (
            <NumberField
              key={key}
              label={label}
              value={form[key]}
              onChange={(value) => {
                setValue(key, value);
                if (value.trim() !== '') {
                  const api = METRIC_FIELDS.find((field) => field.key === key)?.api;
                  if (api) setUnavailableMetrics((current) => current.filter((item) => item !== api));
                }
              }}
            />
          ))}
        </div>
        <fieldset style={{ border: '1px solid #26364d', borderRadius: 10, display: 'grid', gap: 8, margin: 0, padding: 12 }}>
          <legend style={{ color: '#cbd5e1', fontSize: 12, fontWeight: 700, padding: '0 6px' }}>Explicitly unavailable metrics</legend>
          <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))' }}>
            {METRIC_FIELDS.map(({ api, label }) => (
              <label key={api} style={{ alignItems: 'center', color: '#94a3b8', display: 'flex', fontSize: 11, gap: 8 }}>
                <input
                  checked={unavailableMetrics.includes(api)}
                  type="checkbox"
                  onChange={(event) => {
                    setUnavailableMetrics((current) => event.target.checked ? [...current, api] : current.filter((item) => item !== api));
                    if (event.target.checked) {
                      const metricKey = METRIC_FIELDS.find((field) => field.api === api)?.key;
                      if (metricKey) setValue(metricKey, '');
                    }
                  }}
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
      </div>
    );
  }

  function renderAssessmentFields() {
    return (
      <div style={{ display: 'grid', gap: 14 }}>
        <div style={{ border: '1px solid #a78bfa44', borderRadius: 10, color: '#ddd6fe', fontSize: 12, lineHeight: 1.5, padding: 10 }}>
          Assessment is outcome evidence, not a private diary. This surface intentionally has no free-text notes field.
        </div>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }}>
          <Field label="Published-at reference" hint="Browser-only ordering check; the private ledger verifies the matching publication.">
            <input style={fieldStyle} type="datetime-local" value={form.referencePublishedAt} onChange={(event) => setValue('referencePublishedAt', event.target.value)} />
          </Field>
          <NumberField label="Meaningful target conversations" value={form.meaningfulTargetConversations} onChange={(value) => setValue('meaningfulTargetConversations', value)} />
          <Field label="Sounded like me">
            <select style={fieldStyle} value={form.soundedLikeMe} onChange={(event) => setValue('soundedLikeMe', event.target.value as FormState['soundedLikeMe'])}>
              <option value="">Not assessed</option>
              <option value="yes">Yes</option>
              <option value="mixed">Mixed</option>
              <option value="no">No</option>
            </select>
          </Field>
          <Field label="Follow-up">
            <select style={fieldStyle} value={form.followUp} onChange={(event) => setValue('followUp', event.target.value as FormState['followUp'])}>
              <option value="">Not selected</option>
              <option value="reuse">Reuse</option>
              <option value="iterate">Iterate</option>
              <option value="retire">Retire</option>
              <option value="none">None</option>
            </select>
          </Field>
          {OUTCOME_FIELDS.map(({ key, label }) => (
            <NumberField key={key} label={label} value={form[key]} onChange={(value) => setValue(key, value)} />
          ))}
        </div>
        <fieldset style={{ border: '1px solid #26364d', borderRadius: 10, display: 'grid', gap: 8, margin: 0, padding: 12 }}>
          <legend style={{ color: '#cbd5e1', fontSize: 12, fontWeight: 700, padding: '0 6px' }}>Quality flags</legend>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            {QUALITY_FLAGS.map((flag) => (
              <label key={flag} style={{ alignItems: 'center', color: '#94a3b8', display: 'flex', fontSize: 11, gap: 8 }}>
                <input
                  checked={qualityFlags.includes(flag)}
                  type="checkbox"
                  onChange={(event) => setQualityFlags((current) => event.target.checked ? [...current, flag] : current.filter((item) => item !== flag))}
                />
                {flag.replaceAll('_', ' ')}
              </label>
            ))}
          </div>
        </fieldset>
      </div>
    );
  }

  return (
    <section style={panelStyle} data-linkedin-performance-recorder="true">
      <header style={{ display: 'grid', gap: 7 }}>
        <div style={{ alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'space-between' }}>
          <div>
            <p style={{ color: '#38bdf8', fontSize: 10, fontWeight: 800, letterSpacing: '0.12em', margin: 0, textTransform: 'uppercase' }}>Legacy FEEZIE evidence compatibility</p>
            <h3 style={{ color: '#f8fafc', fontSize: 18, margin: '4px 0 0' }}>Record evidence for a legacy banked post</h3>
          </div>
          <span style={{ border: '1px solid #f59e0b55', borderRadius: 999, color: '#fcd34d', fontSize: 10, fontWeight: 750, padding: '5px 9px' }}>ROLLBACK-ONLY · SIGNED TRANSPORT</span>
        </div>
        <p style={{ color: '#94a3b8', fontSize: 12, lineHeight: 1.55, margin: 0 }}>
          Canonical posts record learning in the integrated content portfolio. This records evidence only for the explicitly enabled legacy compatibility lane. It cannot draft, schedule, or publish a LinkedIn post. Raw post copy and private notes are never accepted or sent from this surface.
        </p>
      </header>

      <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(145px, 1fr))' }}>
        {EVENT_OPTIONS.map((option) => {
          const active = eventType === option.value;
          return (
            <button
              key={option.value}
              disabled={inFlight}
              type="button"
              onClick={() => switchEvent(option.value)}
              style={{
                background: active ? '#0c2942' : '#07101f',
                border: `1px solid ${active ? '#38bdf8' : '#26364d'}`,
                borderRadius: 10,
                color: active ? '#bae6fd' : '#94a3b8',
                cursor: inFlight ? 'not-allowed' : 'pointer',
                fontSize: 11,
                fontWeight: 700,
                minHeight: 48,
                opacity: inFlight && !active ? 0.55 : 1,
                padding: 8,
                textAlign: 'left',
              }}
            >
              <span style={{ color: active ? '#38bdf8' : '#64748b', display: 'block', fontSize: 9, marginBottom: 3 }}>STEP {option.step}</span>
              {option.label}
            </button>
          );
        })}
      </div>

      <form onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          <Field label="Content ID" hint="Stable ID shared by approval, publication, metrics, and assessment.">
            <input required style={fieldStyle} value={form.contentId} onChange={(event) => setValue('contentId', event.target.value)} placeholder="FEEZIE-001" />
          </Field>
          <Field label="Exact content SHA-256" hint="64 hex characters (sha256: prefix is accepted). Do not paste the post itself.">
            <input required autoCapitalize="none" autoCorrect="off" spellCheck={false} style={{ ...fieldStyle, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }} value={form.digest} onChange={(event) => setValue('digest', event.target.value)} placeholder="64-character digest" />
          </Field>
          <Field label="Occurred at">
            <input required style={fieldStyle} type="datetime-local" value={form.occurredAt} onChange={(event) => setValue('occurredAt', event.target.value)} />
          </Field>
          <Field label="Idempotency key" hint="Optional. A stable key is created on first submit and retained for safe retry.">
            <input style={fieldStyle} value={form.idempotencyKey} onChange={(event) => setValue('idempotencyKey', event.target.value)} placeholder="Created automatically" />
          </Field>
        </div>

        {eventType === 'owner_reviewed' ? renderOwnerReviewFields() : null}
        {eventType === 'publication_confirmed' ? renderPublicationFields() : null}
        {eventType === 'metrics_24h_recorded' || eventType === 'metrics_7d_recorded' ? renderMetricFields() : null}
        {eventType === 'owner_assessment_recorded' ? renderAssessmentFields() : null}

        {publicationCompleted && eventType !== 'owner_reviewed' ? (
          <p style={{ color: '#86efac', fontSize: 11, margin: 0 }}>A completed publication receipt is known for this exact content version.</p>
        ) : null}

        {error ? (
          <div role="alert" style={{ background: '#3f1018', border: '1px solid #f8717155', borderRadius: 10, color: '#fecaca', fontSize: 12, lineHeight: 1.5, padding: 10 }}>
            {error}
          </div>
        ) : null}

        <div style={{ alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'space-between' }}>
          <div data-performance-job-status={jobStatus} style={{ display: 'grid', gap: 3 }}>
            <strong style={{ color: statusTone(jobStatus), fontSize: 12, textTransform: 'capitalize' }}>{jobStatus}</strong>
            <span style={{ color: '#64748b', fontSize: 10 }}>{statusCopy(jobStatus)}</span>
            {(job?.card_id || job?.job_id) ? <span style={{ color: '#475569', fontSize: 9 }}>Receipt: {job.card_id ?? job.job_id}</span> : null}
            {job?.message ? <span style={{ color: '#94a3b8', fontSize: 10 }}>{job.message}</span> : null}
            {job?.error ? <span style={{ color: '#fca5a5', fontSize: 10 }}>{job.error}</span> : null}
          </div>
          <button
            disabled={inFlight || (eventType === 'publication_confirmed' && !approvalCompleted)}
            type="submit"
            style={{
              background: inFlight || (eventType === 'publication_confirmed' && !approvalCompleted) ? '#1e293b' : '#0ea5e9',
              border: 0,
              borderRadius: 10,
              color: '#f8fafc',
              cursor: inFlight ? 'wait' : 'pointer',
              fontSize: 12,
              fontWeight: 800,
              minHeight: 42,
              padding: '10px 16px',
            }}
          >
            {inFlight ? 'Waiting for ledger…' : `Queue ${EVENT_OPTIONS.find((item) => item.value === eventType)?.label.toLowerCase()}`}
          </button>
        </div>
      </form>

      <footer style={{ borderTop: '1px solid #1e293b', color: '#64748b', fontSize: 10, lineHeight: 1.55, paddingTop: 11 }}>
        Railway is signed transport and a privacy-minimized projection only. Completion means the local worker appended or idempotently matched the canonical private FEEZIE ledger. A queued or running job is not completion.
      </footer>
    </section>
  );
}
