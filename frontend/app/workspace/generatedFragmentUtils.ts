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

export type GeneratedContentResponse = {
  success?: boolean;
  options?: string[];
  diagnostics?: {
    llm_provider_trace?: { provider?: string; actual_model?: string; status?: string }[];
    planned_option_briefs?: GeneratedOptionBrief[];
    content_reservoir_support?: ContentReservoirSupportItem[];
  };
};

export type LocalCodexJobCreateResponse = {
  success?: boolean;
  job_id?: string;
  status?: string;
  message?: string;
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

export function codexJobStatusLabel(status?: string | null) {
  switch ((status || '').trim().toLowerCase()) {
    case 'pending':
      return 'Queued on this Mac';
    case 'claimed':
      return 'Claimed by local worker';
    case 'running':
      return 'Local worker running';
    case 'completed':
      return 'Completed locally';
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
      return 'The request is queued and waiting for the launchd worker to pick it up.';
    case 'claimed':
      return 'The local worker picked up the request and is preparing the local generation pass.';
    case 'running':
      return 'The local worker is generating options. It will only escalate to Codex Terminal if the local quality gate fails.';
    case 'completed':
      return 'The local worker completed this job and wrote the result back to the workspace.';
    case 'failed':
      return 'The local worker exited without returning a usable result.';
    case 'canceled':
      return 'This local run was canceled before the result was accepted.';
    default:
      return 'The local launchd worker is handling this request.';
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
