export const EDIT_CLASSIFICATIONS = [
  'factual',
  'voice',
  'audience',
  'strategy',
  'evidence_attribution',
  'safety_privacy',
  'platform',
  'worldview',
  'one_off',
] as const;

export type EditClassification = (typeof EDIT_CLASSIFICATIONS)[number];
export type OwnerLearningAction =
  | 'variant_selected'
  | 'variant_rejected'
  | 'owner_approved'
  | 'publication_confirmed';
export type PublicationPlatform = 'linkedin' | 'instagram';
export type IntegrityConfirmation = {
  truth: boolean;
  safety: boolean;
  privacy: boolean;
  attribution: boolean;
};

export const EMPTY_INTEGRITY_CONFIRMATION: IntegrityConfirmation = {
  truth: false,
  safety: false,
  privacy: false,
  attribution: false,
};
const OWNER_LEARNING_ACTIONS: OwnerLearningAction[] = [
  'variant_selected',
  'variant_rejected',
  'owner_approved',
  'publication_confirmed',
];

type OwnerPostOpportunity = {
  opportunity_id: string;
  thesis: string;
  status: string;
  truth_state: string;
  safety_state: string;
  attribution_state: string;
  synthesis: { evidence_ids: string[]; interpretation_ids: string[] };
  lineage: { source_ids: string[]; post_id?: string | null };
};

export type OwnerPostThesisResolution = {
  mode: 'synthesized' | 'manual' | 'blocked';
  thesis: string | null;
  opportunityId: string | null;
  blocker: string | null;
};

export function buildPersonaReversalPayload({
  promotionId,
  personaCandidateId,
  canonVersion,
  reason,
  ownerConfirmed,
}: {
  promotionId: string;
  personaCandidateId: string;
  canonVersion: string;
  reason: string;
  ownerConfirmed: boolean;
}) {
  if (ownerConfirmed !== true) throw new Error('Persona reversal requires explicit owner confirmation.');
  const cleanedReason = String(reason || '').replace(/\s+/g, ' ').trim();
  if (!cleanedReason) throw new Error('Explain why this learned pattern should be reversed.');
  if (cleanedReason.length > 1_000) throw new Error('Persona reversal reason must be 1,000 characters or fewer.');
  return {
    promotion_id: requiredIdentifier(promotionId, 'Promotion'),
    persona_candidate_id: requiredIdentifier(personaCandidateId, 'Persona candidate'),
    canon_version: requiredIdentifier(canonVersion, 'Canon version'),
    reason: cleanedReason,
    owner_confirmed: true,
  };
}

function requiredIdentifier(value: string, label: string): string {
  const cleaned = String(value || '').trim();
  if (!cleaned) throw new Error(`${label} is required.`);
  return cleaned;
}

function exactRevisionSha(value: string): string {
  const cleaned = String(value || '').trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(cleaned)) {
    throw new Error('The owner action must bind one exact revision SHA-256 digest.');
  }
  return cleaned;
}

function awarePastIso(value: string, label: string, nowMs: number): string {
  const parsed = new Date(value);
  if (!value || Number.isNaN(parsed.getTime())) throw new Error(`${label} is required.`);
  if (parsed.getTime() > nowMs) throw new Error(`${label} cannot be in the future.`);
  return parsed.toISOString();
}

function publicationUrl(platform: PublicationPlatform, value: string): string {
  const cleaned = String(value || '').trim();
  let parsed: URL;
  try {
    parsed = new URL(cleaned);
  } catch {
    throw new Error('Publication confirmation requires a valid public URL.');
  }
  const expectedHost = `${platform}.com`;
  const hostname = parsed.hostname.toLowerCase();
  if (
    parsed.protocol !== 'https:'
    || (hostname !== expectedHost && !hostname.endsWith(`.${expectedHost}`))
    || Boolean(parsed.username || parsed.password)
    || parsed.pathname === '/'
    || !parsed.pathname
  ) {
    throw new Error(`Publication URL must identify the published ${platform === 'linkedin' ? 'LinkedIn' : 'Instagram'} item.`);
  }
  return cleaned;
}

export function resolveOwnerPostThesis(
  sourceId: string,
  opportunities: OwnerPostOpportunity[],
  manualThesis: string,
): OwnerPostThesisResolution {
  const linkedSyntheses = opportunities.filter((opportunity) => (
    opportunity.lineage.source_ids.includes(sourceId)
    && opportunity.synthesis.evidence_ids.length > 0
    && opportunity.synthesis.interpretation_ids.length > 0
  ));
  const eligible = linkedSyntheses.find((opportunity) => (
    !opportunity.lineage.post_id
    && !['blocked', 'rejected', 'published'].includes(opportunity.status)
    && opportunity.truth_state === 'pass'
    && ['pass', 'owner_review_required'].includes(opportunity.safety_state)
    && ['pass', 'required'].includes(opportunity.attribution_state)
  ));
  if (eligible) {
    return {
      mode: 'synthesized',
      thesis: eligible.thesis,
      opportunityId: eligible.opportunity_id,
      blocker: null,
    };
  }
  if (linkedSyntheses.length > 0) {
    const opportunity = linkedSyntheses[0];
    const blocker = opportunity.lineage.post_id
      ? 'This synthesized opportunity already has a canonical post.'
      : `The existing synthesized opportunity is not draftable: status ${opportunity.status}, truth ${opportunity.truth_state}, safety ${opportunity.safety_state}, attribution ${opportunity.attribution_state}.`;
    return { mode: 'blocked', thesis: null, opportunityId: opportunity.opportunity_id, blocker };
  }
  const thesis = String(manualThesis || '').replace(/\s+/g, ' ').trim();
  return { mode: 'manual', thesis: thesis || null, opportunityId: null, blocker: null };
}

export function buildManualEditPayload({
  postId,
  parentRevisionId,
  body,
  parentBody,
  editClassification,
}: {
  postId: string;
  parentRevisionId: string;
  body: string;
  parentBody: string;
  editClassification: string;
}) {
  const editedBody = String(body || '').trim();
  if (!editedBody) throw new Error('Edited copy is required.');
  if (editedBody === String(parentBody || '').trim()) {
    throw new Error('An immutable edit must change the selected revision bytes.');
  }
  if (!EDIT_CLASSIFICATIONS.includes(editClassification as EditClassification)) {
    throw new Error('Choose why this edit was made before saving it.');
  }
  return {
    post_id: requiredIdentifier(postId, 'Post'),
    parent_revision_id: requiredIdentifier(parentRevisionId, 'Parent revision'),
    body: editedBody,
    edit_classification: editClassification as EditClassification,
  };
}

export function buildLearningActionPayload({
  postId,
  revisionId,
  eventKind,
  revisionSha256,
  ownerConfirmed,
  eventAt,
  integrityConfirmation,
  platform,
  publicUrl,
  nowMs = Date.now(),
}: {
  postId: string;
  revisionId: string;
  eventKind: OwnerLearningAction;
  revisionSha256: string;
  ownerConfirmed: boolean;
  eventAt?: string;
  integrityConfirmation?: IntegrityConfirmation;
  platform?: PublicationPlatform;
  publicUrl?: string;
  nowMs?: number;
}) {
  if (ownerConfirmed !== true) throw new Error('This action requires explicit owner confirmation.');
  if (!OWNER_LEARNING_ACTIONS.includes(eventKind)) throw new Error('Unsupported owner learning action.');
  const base = {
    post_id: requiredIdentifier(postId, 'Post'),
    revision_id: requiredIdentifier(revisionId, 'Revision'),
    event_kind: eventKind,
    revision_sha256: exactRevisionSha(revisionSha256),
    owner_confirmed: true,
  } as const;
  if (eventKind === 'variant_selected' || eventKind === 'variant_rejected') return base;
  if (eventKind === 'owner_approved') {
    const confirmation = integrityConfirmation ?? EMPTY_INTEGRITY_CONFIRMATION;
    if (!confirmation.truth || !confirmation.safety || !confirmation.privacy || !confirmation.attribution) {
      throw new Error('Approval requires explicit truth, safety, privacy, and attribution confirmation.');
    }
    return {
      ...base,
      event_at: awarePastIso(eventAt || '', 'Approval time', nowMs),
      integrity_confirmation: { ...confirmation },
    };
  }
  if (!platform) throw new Error('Choose the platform where this exact revision was published.');
  return {
    ...base,
    event_at: awarePastIso(eventAt || '', 'Publication time', nowMs),
    platform,
    public_url: publicationUrl(platform, publicUrl || ''),
  };
}
