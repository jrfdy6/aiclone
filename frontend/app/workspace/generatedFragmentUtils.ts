export type GeneratedOptionBrief = {
  option_number?: number;
  framing_mode?: string;
  primary_claim?: string;
  proof_packet?: string;
  story_beat?: string;
};

export type ContentReservoirSupportItem = {
  source_id?: string;
  asset_id?: string;
  reservoir_lane?: string;
  primary_type?: string;
  score?: number;
  title?: string;
  text?: string;
  source_path?: string;
  source_url?: string;
};

export type CriticOptionReview = {
  option_index?: number;
  score?: number;
  verdict?: 'ready' | 'revise' | 'blocked' | string;
  dimension_scores?: {
    truth?: number;
    safety?: number;
    intent?: number;
    voice?: number;
    hook?: number;
  };
  issues?: string[];
  hook_variants?: string[];
  editorially_ready?: boolean;
};

export type EditorialReadiness = {
  ready?: boolean;
  status?: 'ready' | 'revision_required' | 'blocked' | 'critic_unavailable' | 'critic_not_run' | string;
  critic_status?: string;
  ready_score_threshold?: number;
  deterministic_quality_gate_passed?: boolean;
  semantic_distinctness_passed?: boolean;
  draft_distinctness?: DraftDistinctnessReceipt;
  ready_option_count?: number;
  option_reviews?: CriticOptionReview[];
  blocking_reasons?: string[];
};

export type DraftContractReceipt = {
  schema_version?: string;
  required_option_count?: number;
  maximum_option_count?: number;
  meaningful_difference_required?: boolean;
  independent_critic_required?: boolean;
  critic_reviews_per_option?: number;
  hook_variants_per_option?: number;
};

export type RevisionContractReceipt = {
  schema_version?: string;
  enabled?: boolean;
  trigger?: string;
  revision_calls_per_non_ready_option?: number;
  model_retries_per_revision?: number;
  preserve_ready_sibling_exactly?: boolean;
  fresh_blind_critic_required_after_revision?: boolean;
};

export type RevisionExecutionReceipt = {
  schema_version?: string;
  status?: 'not_required' | 'completed' | 'failed' | string;
  failure_code?: string;
  canonical_order_preserved?: boolean;
  retry_allowed?: boolean;
  initial_critic_call_count?: number;
  revision_call_count?: number;
  final_critic_call_count?: number;
  contains_post_copy?: boolean;
  contains_critic_issue_copy?: boolean;
  options?: {
    canonical_option_index?: number;
    action?: 'preserved' | 'revised' | 'revision_failed' | string;
    attempt_count?: number;
    changed?: boolean;
    error_code?: string;
  }[];
};

export type DraftDistinctnessReceipt = {
  schema_version?: string;
  passed?: boolean;
  required_option_count?: number;
  actual_option_count?: number;
  reason?: string;
  failed_reasons?: string[];
  pairs?: {
    left_option_index?: number;
    right_option_index?: number;
    sequence_similarity?: number;
    term_containment?: number;
    shingle_jaccard?: number;
    opening_signatures_match?: boolean;
    passed?: boolean;
    failed_reasons?: string[];
  }[];
};

export type GenerationStrategyReceipt = {
  schema_version?: string;
  contract_hash?: string;
  approved_at?: string;
};

export type GenerationClassificationReceipt = {
  canonical_pillar?: string;
  career_signal?: string;
  employer_proximity?: string;
  employer_safety?: string;
  proof_posture?: string;
  treatment?: string;
  publish_posture?: string;
  audience?: string;
  generation_audience?: string;
  audience_consequence?: string;
  distinct_thesis?: string;
  why_now?: string;
  development_status?: string;
  classification_state?: string;
  missing_fields?: string[];
  source_freshness?: {
    temporality?: string;
    state?: string;
    dated_at?: string;
    age_days?: number;
    current_claim_allowed?: boolean;
  };
};

export type GeneratedContentDiagnostics = {
  llm_provider_trace?: { provider?: string; actual_model?: string; reasoning_effort?: string; status?: string; error?: string }[];
  planned_option_briefs?: GeneratedOptionBrief[];
  content_reservoir_support?: ContentReservoirSupportItem[];
  grounding_mode?: string;
  intent?: string;
  strategy_contract?: GenerationStrategyReceipt;
  candidate_classification?: GenerationClassificationReceipt;
  draft_contract?: DraftContractReceipt;
  revision_contract?: RevisionContractReceipt;
  revision_execution?: RevisionExecutionReceipt;
  draft_distinctness?: DraftDistinctnessReceipt;
  quality_gate?: {
    passed?: boolean;
    failed_reasons?: string[];
    evaluated_option_count?: number;
  };
  technical_completion?: {
    status?: string;
    writer_status?: string;
    draft_count?: number;
    drafts_preserved?: boolean;
    revision_status?: string;
  };
  critic_review?: {
    status?: string;
    reason?: string;
    message?: string;
    draft_distinctness?: DraftDistinctnessReceipt;
    reviews?: CriticOptionReview[];
  };
  editorial_readiness?: EditorialReadiness;
};

export type GeneratedContentResponse = {
  success?: boolean;
  options?: string[];
  diagnostics?: GeneratedContentDiagnostics;
};

export type LocalCodexJobCreateResponse = {
  success?: boolean;
  job_id?: string | null;
  status?: string;
  message?: string;
  clarification_key?: EvidenceAnswerKey | null;
  clarification_question?: string | null;
  evidence_readiness?: {
    schema_version?: string;
    status?: string;
    ready?: boolean;
    missing_fields?: EvidenceAnswerKey[];
    present_fields?: EvidenceAnswerKey[];
    field_sources?: Partial<Record<EvidenceAnswerKey, string>>;
    block_reason?: string | null;
  };
};

export type EvidenceAnswerKey = 'concrete_action' | 'exact_problem' | 'observable_lesson';
export type EvidenceAnswers = Partial<Record<EvidenceAnswerKey, string>>;
export type EvidenceClarification = {
  key: EvidenceAnswerKey;
  question: string;
};

export type LocalCodexJobStatusResponse = {
  success?: boolean;
  job_id?: string;
  workspace_slug?: string;
  status?: string;
  requested_by?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string | null;
  result?: GeneratedContentResponse | null;
  artifact_count?: number;
};

export type OwnerReviewHandoffResponse = {
  success?: boolean;
  job_id?: string;
  option_index?: number;
  queue_id?: string;
  card_id?: string;
  duplicate?: boolean;
  status?: 'owner_review_draft' | string;
  approval_status?: 'owner_review_required' | string;
  publish_posture?: 'owner_review_required' | string;
  owner_review_required?: boolean;
  message?: string;
};

export function codexJobStatusLabel(status?: string | null) {
  switch ((status || '').trim().toLowerCase()) {
    case 'pending':
      return 'Queued on this Mac';
    case 'claimed':
      return 'Claimed by Mac Codex worker';
    case 'running':
      return 'Codex Terminal running';
    case 'completed':
      return 'Drafts generated locally';
    case 'failed':
      return 'Local run failed';
    case 'canceled':
      return 'Canceled locally';
    default:
      return 'Local job active';
  }
}

export function codexJobStatusHint(status?: string | null) {
  switch ((status || '').trim().toLowerCase()) {
    case 'pending':
      return 'The request is queued and waiting for the launchd Codex worker on this Mac.';
    case 'claimed':
      return 'The Mac worker picked up the request and is preparing the Codex Terminal run.';
    case 'running':
      return 'Codex Terminal is generating two meaningfully different drafts through the signed-in Codex session on this Mac.';
    case 'completed':
      return 'The Mac worker finished two drafts. Check distinctness, the independent critic, and all eight hooks before advancing an option.';
    case 'failed':
      return 'The local worker exited without returning a usable result.';
    case 'canceled':
      return 'This local run was canceled before the result was accepted.';
    default:
      return 'The local launchd worker is handling this request.';
  }
}

export function criticReviewForOption(
  readiness: EditorialReadiness | undefined,
  optionIndex: number,
): CriticOptionReview | undefined {
  return readiness?.option_reviews?.find((review) => review.option_index === optionIndex + 1);
}

export function editorialReadinessLabel(readiness?: EditorialReadiness) {
  if (!readiness) return 'Critic receipt unavailable';
  if (readiness.ready) return `${readiness.ready_option_count ?? 0} option${readiness.ready_option_count === 1 ? '' : 's'} editorially ready`;
  switch (readiness.status) {
    case 'revision_required':
      return 'Revision required';
    case 'blocked':
      return 'Blocked by critic';
    case 'critic_unavailable':
      return 'Critic unavailable';
    case 'critic_not_run':
      return 'Critic did not run';
    default:
      return 'Not editorially ready';
  }
}

export function codexJobStatusTone(status?: string | null) {
  switch ((status || '').trim().toLowerCase()) {
    case 'completed':
      return '#34d399';
    case 'failed':
    case 'canceled':
      return '#f87171';
    default:
      return '#fbbf24';
  }
}

export type GeneratedFragmentPromotionResponse = {
  success?: boolean;
  duplicate?: boolean;
  delta_id?: string;
  route_key?: string;
  route_reason?: string;
  target_file?: string;
  target_label?: string;
  written_files?: string[];
  message?: string;
};

export type GeneratedFragmentPromotionResult = {
  deltaId?: string;
  targetLabel?: string;
};

export type UndoGeneratedFragmentPromotionResponse = {
  success?: boolean;
  already_reverted?: boolean;
  delta_id?: string;
  removed_target_files?: string[];
  preserved_target_files?: string[];
  message?: string;
};

export function splitPromotableFragments(text: string): string[] {
  const normalized = text.replace(/\r\n/g, '\n').trim();
  if (!normalized) return [];

  const fragments: string[] = [];
  const seen = new Set<string>();
  const blocks = normalized
    .split(/\n+/)
    .map((part) => part.trim())
    .filter(Boolean);

  for (const block of blocks) {
    const sentenceMatches = block.match(/[^.!?]+(?:[.!?]+|$)/g) ?? [block];
    for (const rawPart of sentenceMatches) {
      const cleaned = rawPart.replace(/^[\-\u2022\s]+/, '').trim();
      if (!cleaned) continue;
      const words = cleaned.split(/\s+/).filter(Boolean).length;
      if (words < 4) continue;
      const key = cleaned.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      fragments.push(cleaned);
    }
  }

  if (fragments.length > 0) {
    return fragments;
  }
  return [normalized];
}

export function humanizeBrainTargetLabel(targetFile?: string, fallbackLabel?: string) {
  if (fallbackLabel?.trim()) return fallbackLabel.trim();
  const normalized = (targetFile ?? '').trim();
  if (normalized.includes('identity/claims')) return 'Claims';
  if (normalized.includes('identity/VOICE_PATTERNS')) return 'Voice Patterns';
  if (normalized.includes('identity/decision_principles')) return 'Decision Principles';
  if (normalized.includes('prompts/content_pillars')) return 'Content Pillars';
  if (normalized.includes('history/story_bank')) return 'Story Bank';
  if (normalized.includes('history/wins')) return 'Wins';
  return normalized || 'Brain';
}
