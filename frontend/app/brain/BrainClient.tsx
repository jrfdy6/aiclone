'use client';

import type { ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { apiGet, getApiUrl } from '@/lib/api-client';
import { formatUiTimestamp, parseUiDate } from '@/lib/ui-dates';

export type DocEntry = {
  name: string;
  path: string;
  snippet: string;
  content?: string;
  group?: string;
  updatedAt?: string;
  readMode?: 'runtime' | 'live' | 'snapshot' | 'missing';
  resolvedPath?: string;
};

export type PersonaBundleHealth = {
  bundlePath: string;
  bundleVersion?: string;
  personaId?: string;
  missingFiles: string[];
  missingFrontmatter: string[];
  todoFiles: { path: string; markers: string[] }[];
  status: 'ok' | 'error';
};

export type PersonaPack = {
  key: string;
  title: string;
  description: string;
  sections: { path: string; content: string }[];
};

export type PersonaWorkspace = {
  packs: PersonaPack[];
  pendingMarkdown: string;
  health: PersonaBundleHealth | null;
};

export type DailyBriefEntry = {
  id: string;
  brief_date: string;
  title: string;
  summary?: string | null;
  content_markdown: string;
  source: string;
  source_ref?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type BriefSourceIntelligenceCandidate = {
  item_key?: string | null;
  title?: string | null;
  priority_lane?: string | null;
  source_kind?: string | null;
  route_reason?: string | null;
  handoff_lane?: string | null;
  handoff_reason?: string | null;
  target_file?: string | null;
  source_url?: string | null;
  source_path?: string | null;
  summary?: string | null;
  hook?: string | null;
  section?: string | null;
  response_modes?: string[];
  secondary_consumers?: string[];
  existing_reactions?: BriefReactionEntry[];
  related_persona_context?: BriefReactionPersonaContextEntry[];
};

type BriefConsumerLane = 'source_only' | 'brief_only' | 'persona_candidate' | 'post_candidate' | 'route_to_pm';

type BriefSourceIntelligenceReviewItem = {
  trait?: string | null;
  belief_relation?: string | null;
  review_source?: string | null;
  target_file?: string | null;
};

type BriefReactionEntry = {
  id: string;
  brief_id: string;
  item_key: string;
  item_title: string;
  reaction_kind: 'agree' | 'disagree' | 'nuance' | 'story';
  text: string;
  source_kind?: string | null;
  source_url?: string | null;
  source_path?: string | null;
  linked_delta_id?: string | null;
  linked_capture_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type BriefReactionPersonaContextEntry = {
  delta_id: string;
  trait: string;
  response_kind?: string | null;
  excerpt?: string | null;
  target_file?: string | null;
  review_source?: string | null;
  created_at?: string | null;
};

type BriefSourceIntelligence = {
  generated_at?: string | null;
  base_generated_at?: string | null;
  source_counts?: Record<string, number>;
  source_asset_counts?: Record<string, number>;
  route_counts?: Record<string, number>;
  primary_route_counts?: Record<string, number>;
  belief_relation_counts?: Record<string, number>;
  media_post_seed_count?: number;
  brief_awareness_count?: number;
  belief_evidence_candidate_count?: number;
  pm_route_candidate_count?: number;
  top_brief_awareness?: BriefSourceIntelligenceCandidate[];
  top_media_post_seeds?: BriefSourceIntelligenceCandidate[];
  top_belief_evidence?: BriefSourceIntelligenceCandidate[];
  top_pm_route_candidates?: BriefSourceIntelligenceCandidate[];
  brief_stream?: BriefSourceIntelligenceCandidate[];
  top_review_items?: BriefSourceIntelligenceReviewItem[];
};

export type Automation = {
  id: string;
  name: string;
  schedule: string;
  status: string;
  channel: string;
  last_run_at?: string;
  next_run_at?: string;
};

export type CaptureTelemetry = {
  database_connected: boolean;
  captures: {
    total: number;
    last_24h: number;
    last_7d: number;
  };
  vectors: {
    total: number;
    with_expiry: number;
    overdue: number;
    last_refresh_at?: string | null;
  };
  recent_captures: CaptureSummary[];
};

type CaptureSummary = {
  id: string;
  source?: string;
  topics?: string[];
  importance?: number;
  markdown_path?: string | null;
  created_at?: string | null;
  chunk_count: number;
};

export type OpenBrainHealth = {
  database_connected: boolean;
  vector_extension: boolean;
  embedding_type?: string | null;
  configured_dimension?: number | null;
  storage_backend?: string | null;
  embedder_dimension: number;
  dimension_match: boolean;
  capture_count: number;
  vector_count: number;
  non_expired_vector_count: number;
  search_ready: boolean;
};

export type PersonaDeltaEntry = {
  id: string;
  capture_id?: string | null;
  persona_target: string;
  trait: string;
  notes?: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  committed_at?: string | null;
};

type WorkspaceSnapshotDocEntry = {
  name: string;
  path: string;
  snippet: string;
  content?: string;
  updatedAt?: string;
};

type WorkspaceFile = {
  group?: string;
  name: string;
  path: string;
  snippet: string;
  content?: string;
  updatedAt?: string;
};

type SourceAssetInventory = {
  items?: {
    asset_id?: string;
    title?: string;
    source_channel?: string;
    source_type?: string;
    source_path?: string;
    captured_at?: string;
  }[];
  counts?: {
    total?: number;
    long_form_media?: number;
    pending_segmentation?: number;
    feed_ready?: number;
    by_channel?: Record<string, number>;
  };
};

type LongFormRoutes = {
  assets_considered?: number;
  segments_total?: number;
  route_counts?: Record<string, number>;
  primary_route_counts?: Record<string, number>;
};

type WorkspacePlanCandidate = {
  title: string;
  summary?: string;
  hook?: string;
  rationale?: string;
  source_path?: string;
  source_url?: string;
  priority_lane?: string;
  publish_posture?: string;
  score?: number;
};

type WorkspaceWeeklyPlan = {
  generated_at?: string;
  workspace?: string;
  positioning_model?: string[];
  priority_lanes?: string[];
  recommendations?: WorkspacePlanCandidate[];
  hold_items?: WorkspacePlanCandidate[];
  source_counts?: {
    drafts?: number;
    media?: number;
    research?: number;
    belief_evidence?: number;
  };
};

type WorkspaceReactionItem = {
  title: string;
  author?: string;
  source_platform?: string;
  source_url?: string;
  source_path?: string;
  priority_lane?: string;
  hook?: string;
  summary?: string;
  why_it_matters?: string;
  suggested_comment?: string;
  post_angle?: string;
  score?: number;
};

type WorkspaceReactionQueue = {
  generated_at?: string;
  workspace?: string;
  comment_opportunities?: WorkspaceReactionItem[];
  post_seeds?: WorkspaceReactionItem[];
  counts?: {
    comment_opportunities?: number;
    post_seeds?: number;
    background_only?: number;
  };
};

type WorkspaceFeedItem = {
  id: string;
  platform?: string;
  title: string;
  author?: string;
  source_url?: string;
  why_it_matters?: string;
  summary?: string;
  standout_lines?: string[];
  evaluation?: {
    overall?: number;
    genericity_penalty?: number;
  };
  ranking?: {
    total?: number;
  };
};

type WorkspaceSocialFeed = {
  generated_at?: string;
  workspace?: string;
  strategy_mode?: string;
  items?: WorkspaceFeedItem[];
};

type YouTubeWatchlistVideo = {
  title?: string;
  url?: string;
  author?: string;
  summary?: string;
  published_at?: string | null;
  priority_lane?: string;
  channel_name?: string;
  channel_url?: string;
  already_ingested?: boolean;
};

type YouTubeWatchlistChannel = {
  name?: string;
  url?: string;
  purpose?: string;
  priority_lane?: string;
  error?: string;
  videos?: YouTubeWatchlistVideo[];
};

type YouTubeWatchlistPayload = {
  generated_at?: string;
  workspace?: string;
  runtime?: {
    yt_dlp?: boolean;
    ffmpeg?: boolean;
    whisper?: boolean;
    can_transcribe?: boolean;
    whisper_model?: string;
  };
  auto_ingest?: {
    enabled?: boolean;
    max_videos_per_run?: number;
    per_channel_limit?: number;
  };
  channels?: YouTubeWatchlistChannel[];
  counts?: {
    channels?: number;
    videos?: number;
    already_ingested?: number;
  };
};

type YouTubeIngestJob = {
  job_id: string;
  status: string;
  url?: string;
  title?: string;
  channel_name?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
  ingestion_mode?: string;
  error?: string | null;
};

type WorkspaceFeedbackSummary = {
  total_events?: number;
  average_evaluation_overall?: number | null;
  average_output_expression_quality?: number | null;
  average_expression_delta?: number | null;
  decision_counts?: Record<string, number>;
};

type PersonaReviewSummary = {
  counts?: {
    total?: number;
    brain_pending_review?: number;
    workspace_saved?: number;
    approved_unpromoted?: number;
    pending_promotion?: number;
    committed?: number;
  };
  belief_relation_counts?: Record<string, number>;
};

export type BrainWorkspaceSnapshot = {
  doc_entries?: WorkspaceSnapshotDocEntry[];
  workspace_files?: WorkspaceFile[];
  weekly_plan?: WorkspaceWeeklyPlan | null;
  reaction_queue?: WorkspaceReactionQueue | null;
  social_feed?: WorkspaceSocialFeed | null;
  feedback_summary?: WorkspaceFeedbackSummary | null;
  source_assets?: SourceAssetInventory | null;
  long_form_routes?: LongFormRoutes | null;
  persona_review_summary?: PersonaReviewSummary | null;
};

type PortfolioPathSummary = {
  path?: string;
  updated_at?: string;
  snippet?: string;
  tail?: string;
};

type PortfolioPMCardSummary = {
  id?: string;
  title?: string;
  status?: string;
  owner?: string | null;
  source?: string | null;
  workspace_key?: string;
  updated_at?: string | null;
};

type PortfolioStandupSummary = {
  id?: string;
  status?: string | null;
  workspace_key?: string;
  standup_kind?: string | null;
  summary?: string | null;
  blockers?: string[];
  needs?: string[];
  created_at?: string | null;
};

type PortfolioWorkspaceSummary = {
  workspace_key: string;
  display_name?: string;
  short_label?: string;
  kind?: string;
  status?: string;
  portfolio_visible?: boolean;
  priority_order?: number;
  workspace_root?: string;
  description?: string;
  manager_agent?: string | null;
  target_agent?: string | null;
  workspace_agent?: string | null;
  execution_mode?: string | null;
  default_standup_kind?: string | null;
  pack_status?: { name?: string; exists?: boolean; path?: string; snippet?: string }[];
  local_contracts?: PortfolioPathSummary[];
  latest_briefing?: PortfolioPathSummary | null;
  latest_dispatch?: PortfolioPathSummary | null;
  latest_analytics?: PortfolioPathSummary | null;
  execution_log?: PortfolioPathSummary | null;
  active_pm_cards?: PortfolioPMCardSummary[];
  latest_standups?: PortfolioStandupSummary[];
  persisted_snapshot_types?: Record<string, string[]>;
  counts?: {
    pack_files_present?: number;
    local_contracts?: number;
    active_pm_cards?: number;
    attention_pm_cards?: number;
    latest_standups?: number;
    standup_blockers?: number;
  };
  needs_brain_attention?: boolean;
  source_paths?: string[];
};

type PortfolioWorkspaceSnapshot = {
  generated_at?: string;
  schema_version?: string;
  source?: string;
  workspaces?: PortfolioWorkspaceSummary[];
  counts?: {
    workspaces?: number;
    needs_brain_attention?: number;
    active_pm_cards?: number;
    standup_blockers?: number;
  };
};

type BrainSignalEntry = {
  id: string;
  source_kind: string;
  source_ref?: string | null;
  source_workspace_key?: string;
  raw_summary?: string;
  digest?: string | null;
  signal_types?: string[];
  workspace_candidates?: string[];
  executive_interpretation?: Record<string, string>;
  route_decision?: Record<string, unknown>;
  review_status?: string;
  updated_at?: string;
  created_at?: string;
};

type SourceIntelligenceIndexSummary = {
  schema_version?: string;
  generated_at?: string;
  counts?: {
    total?: number;
    raw?: number;
    digested?: number;
    reviewed?: number;
    routed?: number;
    promoted?: number;
    ignored?: number;
  };
  recent_sources?: {
    source_id?: string;
    source_kind?: string;
    source_class?: string;
    source_channel?: string;
    source_type?: string;
    title?: string;
    status?: string;
    raw_path?: string;
    normalized_path?: string;
    digest_path?: string;
  }[];
};

export type BrainControlPlanePayload = {
  generated_at?: string;
  automations?: Automation[];
  telemetry?: CaptureTelemetry | null;
  telemetry_health?: OpenBrainHealth | null;
  brain_memory_sync?: {
    generated_at?: string;
    source?: string;
    sync_live?: boolean;
    queued_route_count?: number;
    processed_count?: number;
    artifact_paths?: string[];
    processed_items?: Array<{
      delta_id?: string;
      trait?: string;
      workspace_key?: string;
      targets?: string[];
      summary?: string;
    }>;
  } | null;
  workspace_snapshot?: BrainWorkspaceSnapshot | null;
  portfolio_snapshot?: PortfolioWorkspaceSnapshot | null;
  brain_signals?: BrainSignalEntry[];
  source_intelligence_index?: SourceIntelligenceIndexSummary | null;
  summary?: {
    automation_count?: number;
    active_automation_count?: number;
    capture_count?: number;
    doc_count?: number;
    workspace_file_count?: number;
    pending_review_count?: number;
    workspace_saved_count?: number;
    source_asset_count?: number;
    brain_memory_sync_queue_count?: number;
    portfolio_workspace_count?: number;
    portfolio_attention_count?: number;
    brain_signal_count?: number;
    source_intelligence_total?: number;
    source_intelligence_routed?: number;
  };
};

type BrainLongFormIngestForm = {
  url: string;
  title: string;
  summary: string;
  notes: string;
  transcriptText: string;
};

type PromotionItemKind = 'talking_point' | 'framework' | 'anecdote' | 'phrase_candidate' | 'stat';
type PromotionItemProofStrength = 'none' | 'weak' | 'strong';
type PromotionItemGateDecision = 'pending' | 'allow' | 'hold' | 'block';
type PromotionFragmentView = 'recommended' | 'needs_work' | 'all';

type PromotionItem = {
  id: string;
  kind: PromotionItemKind;
  label: string;
  content: string;
  evidence: string | null;
  targetFile: string | null;
  artifactSummary: string | null;
  artifactKind: string | null;
  artifactRef: string | null;
  deltaSummary: string | null;
  reviewInterpretation: string | null;
  capabilitySignal: string | null;
  positioningSignal: string | null;
  leverageSignal: string | null;
  proofSignal: string | null;
  proofStrength: PromotionItemProofStrength;
  gateDecision: PromotionItemGateDecision;
  gateReason: string | null;
  canonPurpose: string | null;
  canonValue: string | null;
  canonProof: string | null;
};

type PromotionGateSummary = {
  decision: PromotionItemGateDecision;
  reason: string | null;
  proofStrength: PromotionItemProofStrength;
  alternativeTarget: string | null;
  selectedCount: number;
};

type BundleFileResult = {
  added?: number;
  skipped?: number;
};

type LocalBundleSyncState = {
  state?: string | null;
  host?: string | null;
  updated_at?: string | null;
  synced_at?: string | null;
  written_files?: string[];
  file_results?: Record<string, BundleFileResult>;
  error?: string | null;
};

type CaptureResponsePayload = {
  capture_id: string;
  chunk_ids: string[];
  chunk_count: number;
  expires_at?: string | null;
};

type BrainPromotionResponse = {
  message?: string;
  delta: PersonaDeltaEntry;
  overlay_counts?: {
    items?: number;
    deltas?: number;
    target_files?: number;
  };
  committed_target_files?: string[];
  bundle_written_files?: string[];
};

type BrainPromotionRerouteResponse = {
  message?: string;
  delta: PersonaDeltaEntry;
  target_file?: string;
};

type BrainSystemRouteResponse = {
  message?: string;
  delta: PersonaDeltaEntry;
  canonical_memory_targets_queued?: string[];
  routes?: Array<{
    workspace_key?: string;
    canonical_memory_targets?: string[];
    standup_kind?: string | null;
    standup?: {
      id: string;
      workspace_key?: string;
      status?: string | null;
    } | null;
    pm_card?: {
      id: string;
      title?: string;
      status?: string;
    } | null;
  }>;
  standup?: {
    id: string;
    workspace_key?: string;
    status?: string | null;
  } | null;
  pm_card?: {
    id: string;
    title?: string;
    status?: string;
  } | null;
};

type BrainRouteHistoryEntry = {
  routed_at?: string;
  workspace_key?: string;
  canonical_memory_targets?: string[];
  standup_kind?: string | null;
  standup_id?: string | null;
  pm_card_id?: string | null;
  pm_title?: string | null;
  summary?: string | null;
};

type PendingCanonicalMemoryRouteEntry = {
  queued_at?: string;
  workspace_key?: string;
  targets?: string[];
  summary?: string | null;
  state?: string | null;
};

type Tab = 'dashboard' | 'briefs' | 'persona' | 'automations' | 'docs';

const API_URL = getApiUrl();
const BRAIN_BRIEFS_TIMEOUT_MS = 12_000;
const BRAIN_PERSONA_TIMEOUT_MS = 45_000;
const BRAIN_CONTROL_PLANE_TIMEOUT_MS = 20_000;
const BRAIN_YOUTUBE_WATCHLIST_TIMEOUT_MS = 20_000;
const BRAIN_YOUTUBE_JOBS_TIMEOUT_MS = 8_000;
const BRAIN_DOC_CONTENT_TIMEOUT_MS = 12_000;
const brainInputStyle = {
  width: '100%',
  boxSizing: 'border-box',
  borderRadius: '10px',
  border: '1px solid #1f2937',
  backgroundColor: '#020617',
  color: 'white',
  padding: '10px 12px',
  fontSize: '13px',
} as const;
const brainTextareaStyle = {
  ...brainInputStyle,
  resize: 'vertical',
  minHeight: '96px',
  lineHeight: 1.5,
} as const;
const brainLinkButtonStyle = {
  borderRadius: '10px',
  border: '1px solid #334155',
  padding: '8px 12px',
  backgroundColor: '#020617',
  color: '#cbd5f5',
  textDecoration: 'none',
  fontSize: '12px',
  fontWeight: 600,
} as const;
const brainFieldLabelStyle = {
  display: 'grid',
  gap: '6px',
  color: '#94a3b8',
  fontSize: '12px',
  fontWeight: 700,
} as const;
function brainSmallButtonStyle(disabled: boolean) {
  return {
    borderRadius: '10px',
    border: '1px solid #334155',
    padding: '8px 12px',
    backgroundColor: disabled ? '#0f172a' : '#020617',
    color: disabled ? '#64748b' : '#cbd5f5',
    cursor: disabled ? 'progress' : 'pointer',
    fontSize: '12px',
    fontWeight: 700,
  } as const;
}
const canonicalMemoryRouteOptions = ['persistent_state', 'learnings', 'chronicle'] as const;
const brainStandupKindOptions = ['auto', 'executive_ops', 'operations', 'weekly_review', 'saturday_vision', 'workspace_sync'] as const;
const brainSignalReviewStatusOptions = ['new', 'in_review', 'reviewed', 'routed', 'ignored'] as const;
const brainSignalRouteOptions = ['source_only', 'canonical_memory', 'persona_canon', 'standup', 'pm', 'workspace_local', 'ignore'] as const;
type BrainSignalRouteTarget = (typeof brainSignalRouteOptions)[number];
const brainWorkspaceOptions = [
  { key: 'shared_ops', label: 'Executive' },
  { key: 'feezie-os', label: 'FEEZIE OS' },
  { key: 'fusion-os', label: 'Fusion OS' },
  { key: 'easyoutfitapp', label: 'Easy Outfit App' },
  { key: 'ai-swag-store', label: 'AI Swag Store' },
  { key: 'agc', label: 'AGC' },
] as const;
type BrainWorkspaceKey = (typeof brainWorkspaceOptions)[number]['key'];
type BrainWorkspaceSignalKey = Exclude<BrainWorkspaceKey, 'shared_ops' | 'feezie-os'>;
type BrainSignalRouteDraft = {
  reviewStatus: string;
  digest: string;
  route: BrainSignalRouteTarget;
  workspaceKey: string;
  summary: string;
  routeReason: string;
  standupKind: string;
  pmTitle: string;
  canonicalTargets: string[];
  yodaMeaning: string;
  neoSystemImpact: string;
  jeanClaudeOperationalTranslation: string;
};

const brainTriagePresetOptions = [
  { key: 'canon_only', label: 'Canon + Memory' },
  { key: 'executive_review', label: 'Executive Review' },
  { key: 'workspace_followup', label: 'Workspace Follow-Up' },
  { key: 'pm_only', label: 'PM Only' },
] as const;

const brainWorkspaceKeywordHints: Record<BrainWorkspaceSignalKey, string[]> = {
  'fusion-os': [
    'fusion',
    'academy',
    'education',
    'higher education',
    'college',
    'admissions',
    'enrollment',
    'referral',
    'referrals',
    'school',
    'schools',
    'family',
    'families',
    'student',
    'students',
    'market development',
    'twice exceptional',
    '2e',
    'neurodivergent',
  ],
  easyoutfitapp: [
    'easy outfit',
    'easyoutfit',
    'outfit',
    'outfits',
    'style',
    'fashion',
    'wardrobe',
    'closet',
    'digital closet',
    'digital organization',
    'personal style',
    'recommendation quality',
    'metadata quality',
  ],
  'ai-swag-store': [
    'swag',
    'merch',
    'merchandise',
    'accessory',
    'accessories',
    'commerce',
    'catalog',
    'fulfillment',
    'product drop',
    'product drops',
    'demand signal',
    'demand test',
    'shop',
    'store',
  ],
  agc: [
    'agc',
    'agc initiative',
    'agc initiatives',
    'agc work',
    'agc mission',
  ],
};

const brainPortfolioAIHints = [
  'ai',
  'artificial intelligence',
  'ai clone',
  'second brain',
  'agent',
  'agents',
  'llm',
  'llms',
  'openai',
  'anthropic',
  'chatgpt',
  'claude',
  'prompt',
  'prompts',
] as const;

const brainPortfolioAIWorkspaces: BrainWorkspaceSignalKey[] = ['fusion-os', 'easyoutfitapp', 'ai-swag-store', 'agc'];

type BrainClientInitialState = {
  briefs?: DailyBriefEntry[];
  personaDeltas?: PersonaDeltaEntry[];
  controlPlane?: BrainControlPlanePayload | null;
};

export default function BrainClient({
  docs,
  personaWorkspace,
  initialState,
}: {
  docs: DocEntry[];
  personaWorkspace: PersonaWorkspace;
  initialState?: BrainClientInitialState;
}) {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [briefs, setBriefs] = useState<DailyBriefEntry[]>(initialState?.briefs ?? []);
  const [selectedBrief, setSelectedBrief] = useState<DailyBriefEntry | null>(initialState?.briefs?.[0] ?? null);
  const [briefsError, setBriefsError] = useState<string | null>(null);
  const [personaDeltas, setPersonaDeltas] = useState<PersonaDeltaEntry[]>(initialState?.personaDeltas ?? []);
  const [personaDeltasError, setPersonaDeltasError] = useState<string | null>(null);
  const [controlPlane, setControlPlane] = useState<BrainControlPlanePayload | null>(initialState?.controlPlane ?? null);
  const [automations, setAutomations] = useState<Automation[]>(initialState?.controlPlane?.automations ?? []);
  const [automationsError, setAutomationsError] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<CaptureTelemetry | null>(initialState?.controlPlane?.telemetry ?? null);
  const [telemetryHealth, setTelemetryHealth] = useState<OpenBrainHealth | null>(initialState?.controlPlane?.telemetry_health ?? null);
  const [telemetryError, setTelemetryError] = useState<string | null>(null);
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState<BrainWorkspaceSnapshot | null>(initialState?.controlPlane?.workspace_snapshot ?? null);
  const [workspaceSnapshotError, setWorkspaceSnapshotError] = useState<string | null>(null);
  const [youtubeWatchlist, setYoutubeWatchlist] = useState<YouTubeWatchlistPayload | null>(null);
  const [youtubeWatchlistError, setYoutubeWatchlistError] = useState<string | null>(null);
  const [youtubeIngestJobs, setYoutubeIngestJobs] = useState<YouTubeIngestJob[]>([]);
  const [longFormIngest, setLongFormIngest] = useState<BrainLongFormIngestForm>({
    url: '',
    title: '',
    summary: '',
    notes: '',
    transcriptText: '',
  });
  const [longFormIngestStatus, setLongFormIngestStatus] = useState<string | null>(null);
  const [longFormIngestError, setLongFormIngestError] = useState<string | null>(null);
  const [longFormSubmitting, setLongFormSubmitting] = useState(false);
  const [viewportWidth, setViewportWidth] = useState(1600);
  const [viewportHeight, setViewportHeight] = useState(1200);
  const mergedDocs = useMemo(() => mergeBrainDocs(docs, workspaceSnapshot), [docs, workspaceSnapshot]);
  const navigateToSection = useCallback((tab: Tab) => {
    setActiveTab(tab);
    if (typeof document === 'undefined') {
      return;
    }
    document.getElementById(`brain-section-${tab}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);
  const tabs = useMemo(
    () => [
      { key: 'dashboard', label: 'Dashboard', active: activeTab === 'dashboard', onSelect: () => navigateToSection('dashboard') },
      { key: 'briefs', label: 'Daily Briefs', active: activeTab === 'briefs', onSelect: () => navigateToSection('briefs') },
      { key: 'persona', label: 'Persona', active: activeTab === 'persona', onSelect: () => navigateToSection('persona') },
      { key: 'automations', label: 'Automations', active: activeTab === 'automations', onSelect: () => navigateToSection('automations') },
      { key: 'docs', label: 'Docs', active: activeTab === 'docs', onSelect: () => navigateToSection('docs') },
    ],
    [activeTab, navigateToSection],
  );

  const applyControlPlanePayload = useCallback((payload: BrainControlPlanePayload | null) => {
    setControlPlane(payload);
    setAutomations(Array.isArray(payload?.automations) ? payload.automations : []);
    setTelemetry(payload?.telemetry ?? null);
    setTelemetryHealth(payload?.telemetry_health ?? null);
    setWorkspaceSnapshot(payload?.workspace_snapshot ?? null);
  }, []);

  const fetchFreshJson = useCallback(async function fetchFreshJson<T>(path: string, timeoutMs: number): Promise<T> {
    const separator = path.includes('?') ? '&' : '?';
    return apiGet<T>(`${path}${separator}brain_ts=${Date.now()}`, { timeoutMs });
  }, []);

  const loadData = useCallback(function loadData(isCancelled: () => boolean = () => false): Promise<void> {
    void fetchFreshJson<DailyBriefEntry[]>('/api/briefs/?limit=50', BRAIN_BRIEFS_TIMEOUT_MS)
      .then((items) => {
        if (isCancelled() || !Array.isArray(items)) {
          return;
        }
        setBriefs(items);
        setSelectedBrief((current) => items.find((entry) => entry.id === current?.id) ?? items[0] ?? null);
        setBriefsError(null);
      })
      .catch((error) => {
        if (isCancelled()) {
          return;
        }
        console.error('Failed to load daily briefs', error);
        setBriefsError('Unable to load daily briefs right now.');
      });

    void fetchFreshJson<PersonaDeltaEntry[]>(
      '/api/persona/deltas?limit=50&view=brain_queue',
      BRAIN_PERSONA_TIMEOUT_MS,
    )
      .then((items) => {
        if (isCancelled() || !Array.isArray(items)) {
          return;
        }
        setPersonaDeltas(items);
        setPersonaDeltasError(null);
      })
      .catch((error) => {
        if (isCancelled()) {
          return;
        }
        console.error('Failed to load persona deltas', error);
        setPersonaDeltasError('Unable to load persona deltas right now.');
      });

    void fetchFreshJson<BrainControlPlanePayload>('/api/brain/control-plane', BRAIN_CONTROL_PLANE_TIMEOUT_MS)
      .then((payload) => {
        if (isCancelled()) {
          return;
        }
        applyControlPlanePayload(payload ?? null);
        setAutomationsError(null);
        setWorkspaceSnapshotError(null);
        setTelemetryError(null);
      })
      .catch((error) => {
        if (isCancelled()) {
          return;
        }
        console.error('Failed to load Brain control plane', error);
        setAutomationsError('Unable to load automations right now.');
        setWorkspaceSnapshotError('Unable to load shared source intelligence right now.');
        setTelemetryError('Unable to load full Open Brain telemetry.');
      });

    void fetchFreshJson<YouTubeWatchlistPayload>('/api/brain/youtube-watchlist', BRAIN_YOUTUBE_WATCHLIST_TIMEOUT_MS)
      .then((payload) => {
        if (isCancelled()) {
          return;
        }
        setYoutubeWatchlist(payload ?? null);
        setYoutubeWatchlistError(null);
      })
      .catch((error) => {
        if (isCancelled()) {
          return;
        }
        console.error('Failed to load YouTube watchlist', error);
        setYoutubeWatchlistError('Unable to load tracked YouTube channels right now.');
      });

    void fetchFreshJson<{ jobs?: YouTubeIngestJob[] }>('/api/brain/youtube-watchlist/jobs', BRAIN_YOUTUBE_JOBS_TIMEOUT_MS)
      .then((payload) => {
        if (isCancelled()) {
          return;
        }
        setYoutubeIngestJobs(Array.isArray(payload?.jobs) ? payload.jobs : []);
      })
      .catch((error) => {
        if (isCancelled()) {
          return;
        }
        console.error('Failed to load YouTube ingest jobs', error);
      });
    return Promise.resolve();
  }, [applyControlPlanePayload, fetchFreshJson]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const syncViewport = () => {
      setViewportWidth(window.innerWidth);
      setViewportHeight(window.innerHeight);
    };
    syncViewport();
    window.addEventListener('resize', syncViewport);
    return () => window.removeEventListener('resize', syncViewport);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const isCancelled = () => cancelled;
    loadData(isCancelled);
    const interval = setInterval(() => loadData(isCancelled), 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [loadData]);

  async function submitLongFormIngest() {
    setLongFormIngestStatus(null);
    setLongFormIngestError(null);
    setLongFormSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/brain/ingest-long-form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: longFormIngest.url || null,
          title: longFormIngest.title || null,
          summary: longFormIngest.summary || null,
          notes: longFormIngest.notes || null,
          transcript_text: longFormIngest.transcriptText || null,
          run_refresh: true,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || 'Unable to register long-form source.');
      }
      setLongFormIngestStatus(`Registered ${payload.title || 'long-form source'} in Brain.`);
      setLongFormIngest({ url: '', title: '', summary: '', notes: '', transcriptText: '' });
      await loadData();
    } catch (error) {
      setLongFormIngestError(error instanceof Error ? error.message : 'Unable to register long-form source.');
    } finally {
      setLongFormSubmitting(false);
    }
  }

  return (
    <RuntimePage module="brain" tabs={tabs} maxWidth="min(1920px, calc(100vw - 24px))">
      <div style={{ display: 'grid', gap: '28px' }}>
        <section id="brain-section-dashboard" style={{ scrollMarginTop: '96px' }}>
          <DashboardPanel
            briefCount={briefs.length}
            docCount={mergedDocs.length}
            automationCount={automations.length}
            controlPlane={controlPlane}
            telemetry={telemetry}
            telemetryHealth={telemetryHealth}
            telemetryError={telemetryError}
            workspaceSnapshot={workspaceSnapshot}
            workspaceSnapshotError={workspaceSnapshotError}
            youtubeWatchlist={youtubeWatchlist}
            youtubeWatchlistError={youtubeWatchlistError}
            youtubeIngestJobs={youtubeIngestJobs}
            longFormIngest={longFormIngest}
            setLongFormIngest={setLongFormIngest}
            longFormIngestStatus={longFormIngestStatus}
            longFormIngestError={longFormIngestError}
            longFormSubmitting={longFormSubmitting}
            onSubmitLongFormIngest={submitLongFormIngest}
            refreshBrainData={() => loadData()}
          />
        </section>
        <section id="brain-section-briefs" style={{ scrollMarginTop: '96px' }}>
          <DailyBriefsPanel briefs={briefs} selected={selectedBrief} onSelect={setSelectedBrief} error={briefsError} onRefresh={() => loadData()} />
        </section>
        <section id="brain-section-persona" style={{ scrollMarginTop: '96px' }}>
          <PersonaPanel
            packs={personaWorkspace.packs}
            deltas={personaDeltas}
            error={personaDeltasError}
            viewportWidth={viewportWidth}
            viewportHeight={viewportHeight}
            refreshBrainData={() => loadData()}
            mergeUpdatedDelta={(updatedDelta) =>
              setPersonaDeltas((current) => current.map((delta) => (delta.id === updatedDelta.id ? updatedDelta : delta)))
            }
          />
        </section>
        <section id="brain-section-automations" style={{ scrollMarginTop: '96px' }}>
          <AutomationsPanel automations={automations} error={automationsError} controlPlane={controlPlane} docCount={mergedDocs.length} />
        </section>
        <section id="brain-section-docs" style={{ scrollMarginTop: '96px' }}>
          <DocsPanel docs={mergedDocs} />
        </section>
      </div>
    </RuntimePage>
  );
}

function DashboardPanel({
  briefCount,
  docCount,
  automationCount,
  controlPlane,
  telemetry,
  telemetryHealth,
  telemetryError,
  workspaceSnapshot,
  workspaceSnapshotError,
  youtubeWatchlist,
  youtubeWatchlistError,
  youtubeIngestJobs,
  longFormIngest,
  setLongFormIngest,
  longFormIngestStatus,
  longFormIngestError,
  longFormSubmitting,
  onSubmitLongFormIngest,
  refreshBrainData,
}: {
  briefCount: number;
  docCount: number;
  automationCount: number;
  controlPlane: BrainControlPlanePayload | null;
  telemetry: CaptureTelemetry | null;
  telemetryHealth: OpenBrainHealth | null;
  telemetryError: string | null;
  workspaceSnapshot: BrainWorkspaceSnapshot | null;
  workspaceSnapshotError: string | null;
  youtubeWatchlist: YouTubeWatchlistPayload | null;
  youtubeWatchlistError: string | null;
  youtubeIngestJobs: YouTubeIngestJob[];
  longFormIngest: BrainLongFormIngestForm;
  setLongFormIngest: (value: BrainLongFormIngestForm) => void;
  longFormIngestStatus: string | null;
  longFormIngestError: string | null;
  longFormSubmitting: boolean;
  onSubmitLongFormIngest: () => Promise<void>;
  refreshBrainData: () => Promise<void>;
}) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <BrainControlPlanePanel
        briefCount={briefCount}
        docCount={docCount}
        automationCount={automationCount}
        controlPlane={controlPlane}
        telemetry={telemetry}
        workspaceSnapshot={workspaceSnapshot}
        workspaceSnapshotError={workspaceSnapshotError}
      />
      <BrainPortfolioPanel
        portfolioSnapshot={controlPlane?.portfolio_snapshot ?? null}
        brainSignals={controlPlane?.brain_signals ?? []}
        refreshBrainData={refreshBrainData}
      />
      <WorkspaceMirrorsPanel workspaceSnapshot={workspaceSnapshot} />
      <BrainLongFormIngestPanel
        value={longFormIngest}
        onChange={setLongFormIngest}
        status={longFormIngestStatus}
        error={longFormIngestError}
        submitting={longFormSubmitting}
        onSubmit={onSubmitLongFormIngest}
        workspaceSnapshot={workspaceSnapshot}
        youtubeWatchlist={youtubeWatchlist}
        youtubeWatchlistError={youtubeWatchlistError}
        youtubeIngestJobs={youtubeIngestJobs}
        refreshBrainData={refreshBrainData}
      />
      <CaptureTelemetryPanel metrics={telemetry} health={telemetryHealth} error={telemetryError} />
    </section>
  );
}

function BrainControlPlanePanel({
  briefCount,
  docCount,
  automationCount,
  controlPlane,
  telemetry,
  workspaceSnapshot,
  workspaceSnapshotError,
}: {
  briefCount: number;
  docCount: number;
  automationCount: number;
  controlPlane: BrainControlPlanePayload | null;
  telemetry: CaptureTelemetry | null;
  workspaceSnapshot: BrainWorkspaceSnapshot | null;
  workspaceSnapshotError: string | null;
}) {
  const sourceCounts = workspaceSnapshot?.source_assets?.counts;
  const routeCounts = workspaceSnapshot?.long_form_routes?.primary_route_counts ?? workspaceSnapshot?.long_form_routes?.route_counts ?? {};
  const personaCounts = workspaceSnapshot?.persona_review_summary?.counts;
  const relationCounts = workspaceSnapshot?.persona_review_summary?.belief_relation_counts ?? {};
  const brainMemorySync = controlPlane?.brain_memory_sync ?? null;
  const sourceIndex = controlPlane?.source_intelligence_index ?? null;
  const memorySyncItems = (brainMemorySync?.processed_items ?? []).slice(0, 4);
  const truthLanes = [
    {
      title: 'Persona Canon',
      tone: '#38bdf8',
      description: 'Identity, voice, stories, and principles you explicitly want the system to remember about you.',
    },
    {
      title: 'Canonical Memory',
      tone: '#22c55e',
      description: 'Operating memory used by pruning, briefs, Chronicle, standups, and the broader maintenance loop.',
    },
    {
      title: 'PM Truth',
      tone: '#f59e0b',
      description: 'Executable work. Only concrete decisions and commitments should land here as PM cards.',
    },
  ];

  return (
    <section
      style={{
        borderRadius: '20px',
        padding: '24px',
        background: 'linear-gradient(135deg, rgba(12,25,55,0.95), rgba(4,8,20,0.95))',
        border: '1px solid rgba(148,163,184,0.15)',
        boxShadow: '0 25px 70px rgba(3,5,15,0.45)',
      }}
    >
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Brain Overview</p>
          <h1 style={{ color: 'white', fontSize: '32px', margin: '4px 0 10px' }}>One surface for the AI clone brain</h1>
          <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.65, maxWidth: '860px', margin: 0 }}>
            This page should let you read the operating memory, review persona deltas, inspect automations, and route important signal without bouncing between separate brain pages.
          </p>
        </div>
        <div style={{ display: 'grid', gap: '8px', justifyItems: 'end' }}>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <a href="#brain-section-briefs" style={brainLinkButtonStyle}>
              Daily briefs
            </a>
            <a href="#brain-section-persona" style={brainLinkButtonStyle}>
              Persona queue
            </a>
            <a href="#brain-section-docs" style={brainLinkButtonStyle}>
              Docs + memory
            </a>
          </div>
          {workspaceSnapshotError && <p style={{ color: '#fca5a5', fontSize: '12px', margin: 0 }}>{workspaceSnapshotError}</p>}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '14px' }}>
        <TelemetryStat label="Briefs" value={briefCount} tone="#38bdf8" detail="Saved daily briefs" />
        <TelemetryStat label="Automations" value={automationCount} tone="#fbbf24" detail="Configured jobs" />
        <TelemetryStat label="Docs" value={docCount} tone="#34d399" detail="Docs visible in Brain" />
        <TelemetryStat label="Captures" value={telemetry?.captures.total ?? 0} tone="#818cf8" detail="Open Brain all time" />
        <TelemetryStat label="Pending Review" value={personaCounts?.brain_pending_review ?? 0} tone="#f97316" detail="Brain queue" />
        <TelemetryStat label="Workspace Saved" value={personaCounts?.workspace_saved ?? 0} tone="#22c55e" detail="Already approved" />
        <TelemetryStat
          label="Workspaces"
          value={controlPlane?.summary?.portfolio_workspace_count ?? 0}
          tone="#a78bfa"
          detail="Visible in portfolio snapshot"
        />
        <TelemetryStat
          label="Need Attention"
          value={controlPlane?.summary?.portfolio_attention_count ?? 0}
          tone={(controlPlane?.summary?.portfolio_attention_count ?? 0) > 0 ? '#f97316' : '#22c55e'}
          detail="PM review, blockers, or failed work"
        />
        <TelemetryStat label="Brain Signals" value={controlPlane?.summary?.brain_signal_count ?? 0} tone="#38bdf8" detail="Recent review objects" />
        <TelemetryStat
          label="Source Index"
          value={controlPlane?.summary?.source_intelligence_total ?? sourceIndex?.counts?.total ?? 0}
          tone="#34d399"
          detail="Registered source-intelligence assets"
        />
        <TelemetryStat
          label="Memory Queue"
          value={brainMemorySync?.queued_route_count ?? 0}
          tone={(brainMemorySync?.queued_route_count ?? 0) > 0 ? '#fbbf24' : '#22c55e'}
          detail="Queued for local canonical-memory sync"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '14px' }}>
        {truthLanes.map((lane) => (
          <div
            key={lane.title}
            style={{
              borderRadius: '12px',
              border: `1px solid ${lane.tone}33`,
              backgroundColor: `${lane.tone}10`,
              padding: '12px',
            }}
          >
            <p style={{ color: lane.tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{lane.title}</p>
            <p style={{ color: '#dbe7ff', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{lane.description}</p>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 0.9fr) minmax(0, 1.1fr)', gap: '12px', marginBottom: '14px' }}>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px', display: 'grid', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div>
              <p style={{ color: '#22c55e', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Canonical Memory Sync</p>
              <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: '8px 0 0' }}>
                Local brain worker that drains reviewed signal into persistent memory files for briefs, standups, Chronicle, and the maintenance loop.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <InlineBadge label={brainMemorySync?.sync_live ? 'Sync live' : 'Sync idle'} tone={brainMemorySync?.sync_live ? '#22c55e' : '#64748b'} />
              <InlineBadge label={`Queue ${numberMeta(brainMemorySync?.queued_route_count)}`} tone={(brainMemorySync?.queued_route_count ?? 0) > 0 ? '#fbbf24' : '#38bdf8'} />
              <InlineBadge label={`Processed ${numberMeta(brainMemorySync?.processed_count)}`} tone="#818cf8" />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
            <TelemetryMeta
              label="Last Sync"
              value={brainMemorySync?.generated_at ? formatTimestamp(brainMemorySync.generated_at) : '—'}
              detail="Latest status published into the control plane"
            />
            <TelemetryMeta
              label="Artifacts"
              value={String(brainMemorySync?.artifact_paths?.length ?? 0)}
              detail="Files touched or reported by the local worker"
            />
            <TelemetryMeta
              label="Queue Depth"
              value={String(brainMemorySync?.queued_route_count ?? 0)}
              detail="Pending canonical-memory route entries"
            />
          </div>
        </div>
        <BriefOverlayBlock
          title="Latest Memory Promotions"
          items={memorySyncItems.map(
            (item) =>
              `${item.workspace_key || 'shared_ops'} · ${(item.targets ?? []).join(', ') || 'memory'} · ${truncateText(item.summary || 'No summary saved.', 120)}`,
          )}
          emptyLabel="No recent canonical-memory promotions processed yet."
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        <BriefOverlayBlock
          title="Shared Source System"
          items={[
            `Source assets: ${numberMeta(sourceCounts?.total)}`,
            `Registry: ${numberMeta(sourceIndex?.counts?.total)} total / ${numberMeta(sourceIndex?.counts?.routed)} routed`,
            `Digested: ${numberMeta(sourceIndex?.counts?.digested)} / reviewed: ${numberMeta(sourceIndex?.counts?.reviewed)}`,
            `Long-form media: ${numberMeta(sourceCounts?.long_form_media)}`,
            `Pending segmentation: ${numberMeta(sourceCounts?.pending_segmentation)}`,
            `Feed-ready: ${numberMeta(sourceCounts?.feed_ready)}`,
          ]}
          emptyLabel="No shared source data yet."
        />
        <BriefOverlayBlock
          title="Source Registry"
          items={(sourceIndex?.recent_sources ?? []).slice(0, 5).map(
            (source) =>
              `${humanizeSnakeCase(source.status || 'raw')} · ${source.source_channel || source.source_kind || 'source'} · ${truncateText(source.title || source.source_id || 'Untitled source', 96)}`,
          )}
          emptyLabel="No source-intelligence registry entries are visible yet."
        />
        <BriefOverlayBlock
          title="Primary Routes"
          items={Object.entries(routeCounts).map(([key, value]) => `${humanizeSnakeCase(key)}: ${value}`)}
          emptyLabel="No route data yet."
        />
        <BriefOverlayBlock
          title="Belief Relations"
          items={Object.entries(relationCounts).map(([key, value]) => `${humanizeBeliefRelation(key)}: ${value}`)}
          emptyLabel="No relation data yet."
        />
      </div>
    </section>
  );
}

function BrainPortfolioPanel({
  portfolioSnapshot,
  brainSignals,
  refreshBrainData,
}: {
  portfolioSnapshot: PortfolioWorkspaceSnapshot | null;
  brainSignals: BrainSignalEntry[];
  refreshBrainData: () => Promise<void>;
}) {
  const workspaces = portfolioSnapshot?.workspaces ?? [];
  const recentSignals = brainSignals.slice(0, 8);
  const [routingSignalId, setRoutingSignalId] = useState<string | null>(null);
  const [reviewingSignalId, setReviewingSignalId] = useState<string | null>(null);
  const [routeStatus, setRouteStatus] = useState<string | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [signalDrafts, setSignalDrafts] = useState<Record<string, Partial<BrainSignalRouteDraft>>>({});

  function defaultSignalDraft(signal: BrainSignalEntry): BrainSignalRouteDraft {
    const interpretation = signal.executive_interpretation ?? {};
    const summary = signal.digest || signal.raw_summary || signal.source_kind;
    const workspaceKey =
      canonicalBrainWorkspaceKey(signal.source_workspace_key) ??
      canonicalBrainWorkspaceKey(signal.workspace_candidates?.[0]) ??
      'shared_ops';
    return {
      reviewStatus: signal.review_status === 'new' ? 'reviewed' : signal.review_status || 'reviewed',
      digest: signal.digest || signal.raw_summary || '',
      route: 'standup',
      workspaceKey,
      summary,
      routeReason: '',
      standupKind: 'auto',
      pmTitle: '',
      canonicalTargets: ['persistent_state'],
      yodaMeaning: interpretation.yoda_meaning || '',
      neoSystemImpact: interpretation.neo_system_impact || '',
      jeanClaudeOperationalTranslation: interpretation.jean_claude_operational_translation || '',
    };
  }

  function signalDraft(signal: BrainSignalEntry): BrainSignalRouteDraft {
    return {
      ...defaultSignalDraft(signal),
      ...(signalDrafts[signal.id] ?? {}),
    };
  }

  function updateSignalDraft(signal: BrainSignalEntry, patch: Partial<BrainSignalRouteDraft>) {
    setSignalDrafts((current) => ({
      ...current,
      [signal.id]: {
        ...(current[signal.id] ?? {}),
        ...patch,
      },
    }));
  }

  function toggleSignalCanonicalTarget(signal: BrainSignalEntry, target: string) {
    const draft = signalDraft(signal);
    const next = draft.canonicalTargets.includes(target)
      ? draft.canonicalTargets.filter((item) => item !== target)
      : [...draft.canonicalTargets, target];
    updateSignalDraft(signal, { canonicalTargets: next });
  }

  async function reviewBrainSignal(signal: BrainSignalEntry) {
    const draft = signalDraft(signal);
    setReviewingSignalId(signal.id);
    setRouteStatus(null);
    setRouteError(null);
    try {
      const response = await fetch(`${API_URL}/api/brain/signals/${encodeURIComponent(signal.id)}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          digest: draft.digest,
          review_status: draft.reviewStatus,
          workspace_candidates: [draft.workspaceKey],
          executive_interpretation: {
            yoda_meaning: draft.yodaMeaning,
            neo_system_impact: draft.neoSystemImpact,
            jean_claude_operational_translation: draft.jeanClaudeOperationalTranslation,
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || 'Unable to review Brain Signal.');
      }
      setRouteStatus('Brain Signal review saved.');
      await refreshBrainData();
    } catch (error) {
      setRouteError(error instanceof Error ? error.message : 'Unable to review Brain Signal.');
    } finally {
      setReviewingSignalId(null);
    }
  }

  async function routeBrainSignal(signal: BrainSignalEntry) {
    const draft = signalDraft(signal);
    setRoutingSignalId(signal.id);
    setRouteStatus(null);
    setRouteError(null);
    if (draft.route === 'pm' && !draft.pmTitle.trim()) {
      setRouteError('PM routes require a bounded action title.');
      setRoutingSignalId(null);
      return;
    }
    if (draft.route === 'canonical_memory' && draft.canonicalTargets.length === 0) {
      setRouteError('Choose at least one memory target before routing to canonical memory.');
      setRoutingSignalId(null);
      return;
    }
    try {
      const response = await fetch(`${API_URL}/api/brain/signals/${encodeURIComponent(signal.id)}/route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          route: draft.route,
          workspace_key: draft.workspaceKey,
          summary: draft.summary || draft.digest || signal.digest || signal.raw_summary || signal.source_kind,
          route_reason: draft.routeReason || defaultBrainSignalRouteReason(draft.route),
          canonical_memory_targets: draft.route === 'canonical_memory' ? draft.canonicalTargets : [],
          standup_kind: draft.standupKind,
          pm_title: draft.route === 'pm' ? draft.pmTitle : null,
          executive_interpretation: {
            yoda_meaning: draft.yodaMeaning,
            neo_system_impact: draft.neoSystemImpact,
            jean_claude_operational_translation: draft.jeanClaudeOperationalTranslation,
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || 'Unable to route Brain Signal.');
      }
      setRouteStatus(`Brain Signal routed to ${humanizeSnakeCase(draft.route)}.`);
      await refreshBrainData();
    } catch (error) {
      setRouteError(error instanceof Error ? error.message : 'Unable to route Brain Signal.');
    } finally {
      setRoutingSignalId(null);
    }
  }

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <p style={{ color: '#a78bfa', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Portfolio Control Plane</p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, maxWidth: '860px' }}>
            Brain reads local workspace proof, PM truth, standups, and persisted snapshots here before deciding whether signal belongs in memory, persona, standup, PM, workspace-local follow-up, or no action.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <InlineBadge label={`Updated ${portfolioSnapshot?.generated_at ? formatTimestamp(portfolioSnapshot.generated_at) : 'not yet'}`} tone="#64748b" />
          <InlineBadge label={`Schema ${portfolioSnapshot?.schema_version ?? 'pending'}`} tone="#818cf8" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '14px' }}>
        <TelemetryStat label="Workspaces" value={portfolioSnapshot?.counts?.workspaces ?? workspaces.length} tone="#a78bfa" detail="Visible portfolio workspaces" />
        <TelemetryStat
          label="Attention"
          value={portfolioSnapshot?.counts?.needs_brain_attention ?? workspaces.filter((workspace) => workspace.needs_brain_attention).length}
          tone={(portfolioSnapshot?.counts?.needs_brain_attention ?? 0) > 0 ? '#f97316' : '#22c55e'}
          detail="Review, blockers, or failed work"
        />
        <TelemetryStat label="PM Cards" value={portfolioSnapshot?.counts?.active_pm_cards ?? 0} tone="#fbbf24" detail="Active workspace work" />
        <TelemetryStat label="Blockers" value={portfolioSnapshot?.counts?.standup_blockers ?? 0} tone="#f87171" detail="Latest standup blockers" />
        <TelemetryStat label="Signals" value={recentSignals.length} tone="#38bdf8" detail="Recent Brain Signal objects" />
      </div>

      {workspaces.length > 0 ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px', marginBottom: '14px' }}>
          {workspaces.map((workspace) => {
            const blockers = workspace.latest_standups?.flatMap((standup) => standup.blockers ?? []).slice(0, 3) ?? [];
            const latestStandup = workspace.latest_standups?.[0] ?? null;
            const latestState =
              workspace.latest_briefing?.snippet ||
              workspace.latest_analytics?.snippet ||
              latestStandup?.summary ||
              workspace.description ||
              'No workspace state published yet.';
            const lastExecution =
              workspace.execution_log?.tail ||
              workspace.execution_log?.snippet ||
              workspace.latest_dispatch?.snippet ||
              'No execution result visible yet.';
            const snapshotTypes = Object.entries(workspace.persisted_snapshot_types ?? {})
              .flatMap(([workspaceKey, types]) => types.map((type) => `${workspaceKey}:${type}`))
              .slice(0, 4);
            return (
              <div
                key={workspace.workspace_key}
                style={{
                  borderRadius: '14px',
                  border: `1px solid ${workspace.needs_brain_attention ? 'rgba(249,115,22,0.45)' : '#1f2937'}`,
                  backgroundColor: workspace.needs_brain_attention ? 'rgba(67,20,7,0.35)' : '#020617',
                  padding: '14px',
                  display: 'grid',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start' }}>
                  <div style={{ minWidth: 0 }}>
                    <p style={{ color: 'white', fontSize: '15px', fontWeight: 700, margin: 0 }}>{workspace.display_name ?? workspace.workspace_key}</p>
                    <p style={{ color: '#64748b', fontSize: '12px', margin: '4px 0 0' }}>
                      {workspace.execution_mode ? humanizeSnakeCase(workspace.execution_mode) : 'workspace'} · {workspace.status ?? 'planned'}
                    </p>
                  </div>
                  <InlineBadge
                    label={workspace.needs_brain_attention ? 'Needs Brain' : 'No blocker'}
                    tone={workspace.needs_brain_attention ? '#f97316' : '#22c55e'}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '8px' }}>
                  <TelemetryMeta label="Pack" value={`${workspace.counts?.pack_files_present ?? 0}/5`} detail="Identity files" />
                  <TelemetryMeta label="PM" value={String(workspace.counts?.active_pm_cards ?? 0)} detail="Active cards" />
                  <TelemetryMeta label="Blockers" value={String(workspace.counts?.standup_blockers ?? blockers.length)} detail="Standup blockers" />
                </div>

                <div style={{ display: 'grid', gap: '8px' }}>
                  <PortfolioFact label="Latest State" value={truncateText(latestState, 190)} />
                  <PortfolioFact label="Last Execution Result" value={truncateText(lastExecution, 190)} />
                  <PortfolioFact
                    label="Active Blockers"
                    value={blockers.length > 0 ? blockers.map((blocker) => truncateText(blocker, 90)).join(' · ') : 'No active blockers reported.'}
                  />
                </div>

                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {(workspace.local_contracts ?? []).slice(0, 3).map((contract) => (
                    <InlineBadge key={`${workspace.workspace_key}-${contract.path}`} label={contract.path?.split('/').pop() ?? 'contract'} tone="#38bdf8" />
                  ))}
                  {snapshotTypes.map((snapshotType) => (
                    <InlineBadge key={`${workspace.workspace_key}-${snapshotType}`} label={snapshotType} tone="#64748b" />
                  ))}
                  {(workspace.local_contracts ?? []).length === 0 && snapshotTypes.length === 0 && <InlineBadge label="No local proof yet" tone="#64748b" />}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <MirrorEmptyState message="No portfolio workspace snapshot is visible in the current Brain control-plane payload." />
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 0.85fr) minmax(0, 1.15fr)', gap: '12px' }}>
        <BriefOverlayBlock
          title="Workspace Attention"
          items={workspaces
            .filter((workspace) => workspace.needs_brain_attention)
            .map((workspace) => `${workspace.display_name ?? workspace.workspace_key}: ${numberMeta(workspace.counts?.attention_pm_cards)} PM review/blocked cards, ${numberMeta(workspace.counts?.standup_blockers)} blockers`)}
          emptyLabel="No workspace currently requires Brain attention."
        />
        <BriefOverlayBlock
          title="Recent Brain Signals"
          items={recentSignals.map((signal) => {
            const workspace = signal.source_workspace_key || signal.workspace_candidates?.[0] || 'shared_ops';
            return `${humanizeSnakeCase(signal.review_status || 'new')} · ${workspace} · ${truncateText(signal.digest || signal.raw_summary || signal.source_kind, 120)}`;
          })}
          emptyLabel="No Brain Signals have been registered yet."
        />
      </div>

      {(routeStatus || routeError || recentSignals.length > 0) && (
        <div style={{ marginTop: '14px', display: 'grid', gap: '10px' }}>
          {routeStatus && <p style={{ color: '#22c55e', fontSize: '12px', margin: 0 }}>{routeStatus}</p>}
          {routeError && <p style={{ color: '#f87171', fontSize: '12px', margin: 0 }}>{routeError}</p>}
          {recentSignals.map((signal) => (
            <BrainSignalReviewCard
              key={signal.id}
              signal={signal}
              draft={signalDraft(signal)}
              disabled={routingSignalId === signal.id || reviewingSignalId === signal.id}
              routing={routingSignalId === signal.id}
              reviewing={reviewingSignalId === signal.id}
              onDraftChange={(patch) => updateSignalDraft(signal, patch)}
              onToggleMemoryTarget={(target) => toggleSignalCanonicalTarget(signal, target)}
              onReview={() => void reviewBrainSignal(signal)}
              onRoute={() => void routeBrainSignal(signal)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function BrainSignalReviewCard({
  signal,
  draft,
  disabled,
  reviewing,
  routing,
  onDraftChange,
  onToggleMemoryTarget,
  onReview,
  onRoute,
}: {
  signal: BrainSignalEntry;
  draft: BrainSignalRouteDraft;
  disabled: boolean;
  reviewing: boolean;
  routing: boolean;
  onDraftChange: (patch: Partial<BrainSignalRouteDraft>) => void;
  onToggleMemoryTarget: (target: string) => void;
  onReview: () => void;
  onRoute: () => void;
}) {
  const routeHistory = brainSignalRouteHistory(signal);
  const latestRoute = brainSignalLatestRoute(signal);
  const routeRequiresPMTitle = draft.route === 'pm';
  const routeRequiresMemoryTarget = draft.route === 'canonical_memory';
  const routeDisabled = disabled || (routeRequiresPMTitle && !draft.pmTitle.trim()) || (routeRequiresMemoryTarget && draft.canonicalTargets.length === 0);
  return (
    <div style={{ borderRadius: '12px', border: '1px solid #1e293b', backgroundColor: '#020617', padding: '12px', display: 'grid', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0, maxWidth: '760px' }}>
          <p style={{ color: '#e2e8f0', fontSize: '14px', fontWeight: 700, margin: 0 }}>
            {humanizeSnakeCase(signal.source_kind)} · {humanizeSnakeCase(signal.review_status || 'new')}
          </p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.5, margin: '6px 0 0' }}>
            {truncateText(signal.digest || signal.raw_summary || 'No signal summary saved.', 220)}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <InlineBadge label={signal.source_workspace_key || 'shared_ops'} tone="#38bdf8" />
          {latestRoute && <InlineBadge label={`latest ${humanizeSnakeCase(readRecordString(latestRoute, 'route') || 'route')}`} tone="#a78bfa" />}
          {signal.source_ref && <InlineBadge label={truncateText(signal.source_ref, 36)} tone="#64748b" />}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '10px' }}>
        <label style={brainFieldLabelStyle}>
          Review status
          <select value={draft.reviewStatus} onChange={(event) => onDraftChange({ reviewStatus: event.target.value })} style={brainInputStyle}>
            {brainSignalReviewStatusOptions.map((status) => (
              <option key={status} value={status}>
                {humanizeSnakeCase(status)}
              </option>
            ))}
          </select>
        </label>
        <label style={brainFieldLabelStyle}>
          Workspace
          <select value={draft.workspaceKey} onChange={(event) => onDraftChange({ workspaceKey: event.target.value })} style={brainInputStyle}>
            {brainWorkspaceOptions.map((workspace) => (
              <option key={workspace.key} value={workspace.key}>
                {workspace.label}
              </option>
            ))}
          </select>
        </label>
        <label style={brainFieldLabelStyle}>
          Route
          <select value={draft.route} onChange={(event) => onDraftChange({ route: event.target.value as BrainSignalRouteTarget })} style={brainInputStyle}>
            {brainSignalRouteOptions.map((route) => (
              <option key={route} value={route}>
                {humanizeSnakeCase(route)}
              </option>
            ))}
          </select>
        </label>
        <label style={brainFieldLabelStyle}>
          Standup kind
          <select value={draft.standupKind} onChange={(event) => onDraftChange({ standupKind: event.target.value })} style={brainInputStyle} disabled={draft.route !== 'standup'}>
            {brainStandupKindOptions.map((kind) => (
              <option key={kind} value={kind}>
                {humanizeSnakeCase(kind)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label style={brainFieldLabelStyle}>
        Digest
        <textarea value={draft.digest} onChange={(event) => onDraftChange({ digest: event.target.value })} style={{ ...brainTextareaStyle, minHeight: '72px' }} />
      </label>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
        <label style={brainFieldLabelStyle}>
          Route summary
          <textarea value={draft.summary} onChange={(event) => onDraftChange({ summary: event.target.value })} style={{ ...brainTextareaStyle, minHeight: '72px' }} />
        </label>
        <label style={brainFieldLabelStyle}>
          Why route now
          <textarea value={draft.routeReason} onChange={(event) => onDraftChange({ routeReason: event.target.value })} placeholder={defaultBrainSignalRouteReason(draft.route)} style={{ ...brainTextareaStyle, minHeight: '72px' }} />
        </label>
      </div>

      {draft.route === 'pm' && (
        <label style={brainFieldLabelStyle}>
          PM action title
          <input value={draft.pmTitle} onChange={(event) => onDraftChange({ pmTitle: event.target.value })} placeholder="Resolve bounded workspace issue" style={brainInputStyle} />
        </label>
      )}

      {draft.route === 'canonical_memory' && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {canonicalMemoryRouteOptions.map((target) => {
            const active = draft.canonicalTargets.includes(target);
            return (
              <button key={target} type="button" onClick={() => onToggleMemoryTarget(target)} style={triageToggleButtonStyle(active)}>
                {humanizeSnakeCase(target)}
              </button>
            );
          })}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
        <label style={brainFieldLabelStyle}>
          Yoda meaning
          <input value={draft.yodaMeaning} onChange={(event) => onDraftChange({ yodaMeaning: event.target.value })} style={brainInputStyle} />
        </label>
        <label style={brainFieldLabelStyle}>
          Neo system impact
          <input value={draft.neoSystemImpact} onChange={(event) => onDraftChange({ neoSystemImpact: event.target.value })} style={brainInputStyle} />
        </label>
        <label style={brainFieldLabelStyle}>
          Jean-Claude translation
          <input
            value={draft.jeanClaudeOperationalTranslation}
            onChange={(event) => onDraftChange({ jeanClaudeOperationalTranslation: event.target.value })}
            style={brainInputStyle}
          />
        </label>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ color: '#64748b', fontSize: '12px' }}>
          {routeHistory.length > 0 ? `${routeHistory.length} route event${routeHistory.length === 1 ? '' : 's'} recorded.` : 'No route history yet.'}
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button type="button" onClick={onReview} disabled={disabled} style={brainSmallButtonStyle(disabled)}>
            {reviewing ? 'Saving...' : 'Save Review'}
          </button>
          <button type="button" onClick={onRoute} disabled={routeDisabled} style={brainSmallButtonStyle(routeDisabled)}>
            {routing ? 'Routing...' : `Route to ${humanizeSnakeCase(draft.route)}`}
          </button>
        </div>
      </div>

      {routeHistory.length > 0 && (
        <div style={{ borderRadius: '10px', border: '1px solid #1e293b', backgroundColor: '#030712', padding: '10px', display: 'grid', gap: '8px' }}>
          <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>Route History</p>
          {routeHistory.slice(-3).map((entry, index) => (
            <div key={`${signal.id}-route-${index}`} style={{ color: '#cbd5e1', fontSize: '12px', lineHeight: 1.45 }}>
              <strong style={{ color: '#e2e8f0' }}>{humanizeSnakeCase(readRecordString(entry, 'route') || 'route')}</strong>
              {' · '}
              {readRecordString(entry, 'workspace_key') || 'shared_ops'}
              {readRecordString(entry, 'routed_at') ? ` · ${formatTimestamp(readRecordString(entry, 'routed_at'))}` : ''}
              {readRecordString(entry, 'summary') ? ` · ${truncateText(readRecordString(entry, 'summary'), 120)}` : ''}
              <BrainSignalRouteWriteback entry={entry} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function brainSignalRouteHistory(signal: BrainSignalEntry) {
  const history = signal.route_decision?.history;
  if (Array.isArray(history)) {
    return history.filter((entry): entry is Record<string, unknown> => isUnknownRecord(entry));
  }
  const latest = brainSignalLatestRoute(signal);
  return latest ? [latest] : [];
}

function brainSignalLatestRoute(signal: BrainSignalEntry) {
  const latest = signal.route_decision?.latest;
  return isUnknownRecord(latest) ? latest : null;
}

function BrainSignalRouteWriteback({ entry }: { entry: Record<string, unknown> }) {
  const standup = isUnknownRecord(entry.standup) ? entry.standup : null;
  const pmCard = isUnknownRecord(entry.pm_card) ? entry.pm_card : null;
  const memoryTargets = Array.isArray(entry.canonical_memory_targets)
    ? entry.canonical_memory_targets.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  if (!standup && !pmCard && memoryTargets.length === 0 && !readRecordString(entry, 'ignored_reason')) {
    return null;
  }
  return (
    <span style={{ display: 'block', color: '#64748b', marginTop: '4px' }}>
      {standup && `Standup ${readRecordString(standup, 'id') || 'queued'}. `}
      {pmCard && `PM ${readRecordString(pmCard, 'id') || readRecordString(pmCard, 'title') || 'queued'}. `}
      {memoryTargets.length > 0 && `Memory ${memoryTargets.join(', ')}. `}
      {readRecordString(entry, 'ignored_reason') && `Ignored: ${truncateText(readRecordString(entry, 'ignored_reason'), 100)}`}
    </span>
  );
}

function defaultBrainSignalRouteReason(route: BrainSignalRouteTarget) {
  if (route === 'ignore') return 'Operator marked this Brain Signal as no-action.';
  if (route === 'standup') return 'Operator routed this Brain Signal for standup interpretation.';
  if (route === 'pm') return 'Operator confirmed this Brain Signal is action-shaped and should become bounded PM work now.';
  if (route === 'canonical_memory') return 'Operator confirmed this Brain Signal should update canonical memory.';
  if (route === 'persona_canon') return 'Operator confirmed this Brain Signal should be considered for persona canon.';
  if (route === 'workspace_local') return 'Operator confirmed this Brain Signal belongs in the selected workspace local context.';
  return 'Operator kept this Brain Signal in source intelligence only.';
}

function isUnknownRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function readRecordString(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === 'string' ? value : '';
}

function PortfolioFact({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ borderRadius: '10px', border: '1px solid #1e293b', backgroundColor: '#030712', padding: '10px' }}>
      <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 6px' }}>{label}</p>
      <p style={{ color: '#dbe7ff', fontSize: '13px', lineHeight: 1.45, margin: 0 }}>{value}</p>
    </div>
  );
}

function BrainLongFormIngestPanel({
  value,
  onChange,
  status,
  error,
  submitting,
  onSubmit,
  workspaceSnapshot,
  youtubeWatchlist,
  youtubeWatchlistError,
  youtubeIngestJobs,
  refreshBrainData,
}: {
  value: BrainLongFormIngestForm;
  onChange: (value: BrainLongFormIngestForm) => void;
  status: string | null;
  error: string | null;
  submitting: boolean;
  onSubmit: () => Promise<void>;
  workspaceSnapshot: BrainWorkspaceSnapshot | null;
  youtubeWatchlist: YouTubeWatchlistPayload | null;
  youtubeWatchlistError: string | null;
  youtubeIngestJobs: YouTubeIngestJob[];
  refreshBrainData: () => Promise<void>;
}) {
  const recentAssets = (workspaceSnapshot?.source_assets?.items ?? []).slice(0, 4);
  const [queueingUrl, setQueueingUrl] = useState<string | null>(null);
  const [queueStatus, setQueueStatus] = useState<string | null>(null);
  const [queueError, setQueueError] = useState<string | null>(null);
  const watchlistChannels = youtubeWatchlist?.channels ?? [];
  const recentJobs = youtubeIngestJobs.slice(0, 6);

  function updateField(key: keyof BrainLongFormIngestForm, next: string) {
    onChange({ ...value, [key]: next });
  }

  async function queueWatchlistVideo(video: YouTubeWatchlistVideo) {
    if (!video.url) {
      setQueueError('This video is missing a URL and cannot be queued.');
      return;
    }
    setQueueStatus(null);
    setQueueError(null);
    setQueueingUrl(video.url);
    try {
      const response = await fetch(`${API_URL}/api/brain/youtube-watchlist/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: video.url,
          title: video.title || null,
          summary: video.summary || null,
          author: video.author || null,
          channel_name: video.channel_name || null,
          priority_lane: video.priority_lane || null,
          run_refresh: true,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || 'Unable to queue YouTube ingest.');
      }
      setQueueStatus(`Queued ${video.title || 'YouTube source'} for Brain ingest.`);
      await refreshBrainData();
    } catch (ingestError) {
      setQueueError(ingestError instanceof Error ? ingestError.message : 'Unable to queue YouTube ingest.');
    } finally {
      setQueueingUrl(null);
    }
  }

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Brain Long-Form Intake</p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, maxWidth: '760px' }}>
            Register YouTube videos, podcasts, and other long-form sources here so Brain becomes the global entry point. These land in the shared source system first, then feed briefs, planning, and persona review.
          </p>
        </div>
        <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right' }}>
          <div>Assets visible: {numberMeta(workspaceSnapshot?.source_assets?.counts?.total)}</div>
          <div>Pending segmentation: {numberMeta(workspaceSnapshot?.source_assets?.counts?.pending_segmentation)}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 1fr)', gap: '16px' }}>
          <div style={{ display: 'grid', gap: '10px' }}>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Source URL</span>
              <input
                value={value.url}
                onChange={(event) => updateField('url', event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                style={brainInputStyle}
              />
            </label>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Title</span>
              <input
                value={value.title}
                onChange={(event) => updateField('title', event.target.value)}
                placeholder="Optional title override"
                style={brainInputStyle}
              />
            </label>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Summary</span>
              <textarea
                value={value.summary}
                onChange={(event) => updateField('summary', event.target.value)}
                placeholder="One or two lines about why this source matters"
                rows={3}
                style={brainTextareaStyle}
              />
            </label>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Notes</span>
              <textarea
                value={value.notes}
                onChange={(event) => updateField('notes', event.target.value)}
                placeholder="Optional notes, implications, or what to look for"
                rows={4}
                style={brainTextareaStyle}
              />
            </label>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Transcript Text</span>
              <textarea
                value={value.transcriptText}
                onChange={(event) => updateField('transcriptText', event.target.value)}
                placeholder="Optional full or partial transcript if you already have it"
                rows={8}
                style={brainTextareaStyle}
              />
            </label>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => void onSubmit()}
                disabled={submitting}
                style={{
                  border: '1px solid rgba(56,189,248,0.45)',
                  borderRadius: '10px',
                  padding: '10px 14px',
                  background: submitting ? '#0f172a' : 'rgba(8,47,73,0.8)',
                  color: 'white',
                  cursor: submitting ? 'progress' : 'pointer',
                  fontWeight: 600,
                }}
              >
                {submitting ? 'Registering…' : 'Register Long-Form Source'}
              </button>
              {status && <span style={{ color: '#22c55e', fontSize: '12px' }}>{status}</span>}
              {error && <span style={{ color: '#f87171', fontSize: '12px' }}>{error}</span>}
            </div>
          </div>

          <div style={{ display: 'grid', gap: '12px' }}>
            <BriefOverlayBlock
              title="What This Does"
              items={[
                'Writes a normalized long-form source into knowledge/ingestions/**.',
                'Refreshes the shared snapshot used by Brain, briefs, planner, and /ops.',
                'Keeps the source upstream until segmentation produces claim-sized units.',
              ]}
              emptyLabel=""
            />
            <BriefOverlayBlock
              title="Recent Source Assets"
              items={recentAssets.map((item) => `${item.title || 'Untitled'} · ${humanizeSnakeCase(item.source_channel || 'manual')}`)}
              emptyLabel="No long-form assets are visible yet."
            />
          </div>
        </div>

        <section style={{ borderRadius: '14px', border: '1px solid #1e293b', backgroundColor: '#020617', padding: '16px', display: 'grid', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <div>
              <p style={{ color: '#fbbf24', letterSpacing: '0.18em', fontSize: '11px', textTransform: 'uppercase' }}>YouTube Watchlist</p>
              <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, maxWidth: '820px' }}>
                These tracked channels route into the same Brain ingest path. If the local media runtime is available, Brain can pull audio and transcript automatically.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <InlineBadge
                label={
                  youtubeWatchlist?.runtime?.can_transcribe
                    ? `Transcript runtime ready (${youtubeWatchlist?.runtime?.whisper_model || 'whisper'})`
                    : 'Transcript runtime unavailable'
                }
                tone={youtubeWatchlist?.runtime?.can_transcribe ? '#22c55e' : '#f97316'}
              />
              <InlineBadge
                label={`Channels ${numberMeta(youtubeWatchlist?.counts?.channels)}`}
                tone="#38bdf8"
              />
              <InlineBadge
                label={`Videos ${numberMeta(youtubeWatchlist?.counts?.videos)}`}
                tone="#818cf8"
              />
              {youtubeWatchlist?.auto_ingest?.enabled && (
                <InlineBadge
                  label={`Auto ingest ${numberMeta(youtubeWatchlist?.auto_ingest?.max_videos_per_run)}/run`}
                  tone="#fbbf24"
                />
              )}
            </div>
          </div>

          {youtubeWatchlistError && <p style={{ color: '#f87171', fontSize: '12px' }}>{youtubeWatchlistError}</p>}
          {queueStatus && <p style={{ color: '#22c55e', fontSize: '12px' }}>{queueStatus}</p>}
          {queueError && <p style={{ color: '#f87171', fontSize: '12px' }}>{queueError}</p>}

          <div style={{ display: 'grid', gap: '12px' }}>
            {watchlistChannels.length > 0 ? (
              watchlistChannels.map((channel, channelIndex) => (
                <div
                  key={`${channel.name || 'channel'}-${channelIndex}`}
                  style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712', padding: '14px', display: 'grid', gap: '12px' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                    <div style={{ display: 'grid', gap: '6px' }}>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                        <p style={{ color: 'white', fontSize: '15px', fontWeight: 600 }}>{channel.name || 'YouTube channel'}</p>
                        {channel.priority_lane && <InlineBadge label={humanizeSnakeCase(channel.priority_lane)} tone="#38bdf8" />}
                        {channel.error && <InlineBadge label="Feed lookup failed" tone="#f97316" />}
                      </div>
                      {channel.purpose && <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.5 }}>{channel.purpose}</p>}
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {channel.url && (
                        <a href={channel.url} target="_blank" rel="noreferrer" style={brainLinkButtonStyle}>
                          Open channel
                        </a>
                      )}
                      {channel.videos && channel.videos.length > 0 && (
                        <InlineBadge label={`${channel.videos.length} recent`} tone="#64748b" />
                      )}
                    </div>
                  </div>

                  {channel.error ? (
                    <p style={{ color: '#fca5a5', fontSize: '12px' }}>{channel.error}</p>
                  ) : channel.videos && channel.videos.length > 0 ? (
                    <div style={{ display: 'grid', gap: '10px' }}>
                      {channel.videos.map((video, videoIndex) => (
                        <div
                          key={`${video.url || video.title || 'video'}-${videoIndex}`}
                          style={{ borderRadius: '12px', border: '1px solid #162033', backgroundColor: '#020617', padding: '12px', display: 'grid', gap: '10px' }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                            <div style={{ display: 'grid', gap: '6px', minWidth: 0 }}>
                              <p style={{ color: '#e2e8f0', fontSize: '14px', fontWeight: 600 }}>{video.title || 'Untitled video'}</p>
                              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                {video.author && <InlineBadge label={video.author} tone="#64748b" />}
                                {video.published_at && <InlineBadge label={formatTimestampValue(video.published_at)} tone="#64748b" />}
                                {video.already_ingested && <InlineBadge label="Already in Brain" tone="#22c55e" />}
                              </div>
                              {video.summary && <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55 }}>{video.summary}</p>}
                            </div>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              {video.url && (
                                <a href={video.url} target="_blank" rel="noreferrer" style={brainLinkButtonStyle}>
                                  Open video
                                </a>
                              )}
                              <button
                                type="button"
                                onClick={() => void queueWatchlistVideo(video)}
                                disabled={!video.url || queueingUrl === video.url}
                                style={{
                                  border: '1px solid rgba(56,189,248,0.45)',
                                  borderRadius: '10px',
                                  padding: '8px 12px',
                                  backgroundColor: queueingUrl === video.url ? '#0f172a' : 'rgba(8,47,73,0.8)',
                                  color: 'white',
                                  cursor: !video.url ? 'not-allowed' : queueingUrl === video.url ? 'progress' : 'pointer',
                                  fontSize: '12px',
                                  fontWeight: 600,
                                }}
                              >
                                {queueingUrl === video.url ? 'Queueing…' : video.already_ingested ? 'Re-ingest now' : 'Ingest now'}
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ color: '#94a3b8', fontSize: '12px' }}>No recent videos were discovered for this channel yet.</p>
                  )}
                </div>
              ))
            ) : (
              <p style={{ color: '#94a3b8', fontSize: '12px' }}>No YouTube channels are configured in the workspace watchlist yet.</p>
            )}
          </div>

          <BriefOverlayBlock
            title="Recent Ingest Jobs"
            items={recentJobs.map((job) => {
              const label = job.title || job.url || 'YouTube ingest';
              const mode = job.ingestion_mode ? ` · ${humanizeSnakeCase(job.ingestion_mode)}` : '';
              return `${label} · ${humanizeSnakeCase(job.status)}${mode}`;
            })}
            emptyLabel="No watchlist ingest jobs have been queued yet."
          />
        </section>
      </div>
    </section>
  );
}

function WorkspaceMirrorsPanel({ workspaceSnapshot }: { workspaceSnapshot: BrainWorkspaceSnapshot | null }) {
  const weeklyPlan = workspaceSnapshot?.weekly_plan ?? null;
  const reactionQueue = workspaceSnapshot?.reaction_queue ?? null;
  const socialFeed = workspaceSnapshot?.social_feed ?? null;
  const feedbackSummary = workspaceSnapshot?.feedback_summary ?? null;

  if (!weeklyPlan && !reactionQueue && !socialFeed) {
    return null;
  }

  const positioningModel = (weeklyPlan?.positioning_model ?? []).slice(0, 3);
  const recommendations = (weeklyPlan?.recommendations ?? []).slice(0, 3);
  const commentOpportunities = (reactionQueue?.comment_opportunities ?? []).slice(0, 3);
  const postSeeds = (reactionQueue?.post_seeds ?? []).slice(0, 3);
  const feedItems = (socialFeed?.items ?? []).slice(0, 3);

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workspace Mirrors</p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, maxWidth: '820px' }}>
            These are collapsed Brain-side mirrors of the highest-value Workspace modules. They stay available here as fallback context without replacing the full Workspace surface.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Link href="/workspace" style={brainLinkButtonStyle}>
            Open Workspace
          </Link>
          <Link href="/workspace/posting" style={brainLinkButtonStyle}>
            Open Posting
          </Link>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '12px' }}>
        <WorkspaceMirrorCard
          title="Weekly Plan"
          meta={[
            weeklyPlan?.generated_at ? `Updated ${formatTimestamp(weeklyPlan.generated_at)}` : 'No plan timestamp',
            `Recommendations ${numberMeta(weeklyPlan?.recommendations?.length)}`,
            `Media ${numberMeta(weeklyPlan?.source_counts?.media)}`,
          ]}
        >
          <div style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {(weeklyPlan?.priority_lanes ?? []).slice(0, 6).map((lane) => (
                <InlineBadge key={lane} label={humanizeSnakeCase(lane)} tone="#38bdf8" />
              ))}
              {(weeklyPlan?.priority_lanes ?? []).length === 0 && <InlineBadge label="No priority lanes yet" tone="#64748b" />}
            </div>
            {positioningModel.length > 0 && (
              <BriefOverlayBlock title="Positioning Model" items={positioningModel} emptyLabel="No positioning model yet." />
            )}
            <div style={{ display: 'grid', gap: '10px' }}>
              {recommendations.length > 0 ? (
                recommendations.map((item, index) => (
                  <MirrorItemCard
                    key={`${item.title}-${index}`}
                    title={item.title}
                    body={item.hook || item.summary || item.rationale || 'No recommendation summary available.'}
                    meta={[
                      item.priority_lane ? humanizeSnakeCase(item.priority_lane) : null,
                      item.publish_posture ? humanizeSnakeCase(item.publish_posture) : null,
                      typeof item.score === 'number' ? `score ${item.score}` : null,
                    ]}
                    href={item.source_url || null}
                    hrefLabel="Open source"
                  />
                ))
              ) : (
                <MirrorEmptyState message="No top recommendations are visible in the workspace snapshot yet." />
              )}
            </div>
          </div>
        </WorkspaceMirrorCard>

        <WorkspaceMirrorCard
          title="Reaction Queue"
          meta={[
            reactionQueue?.generated_at ? `Updated ${formatTimestamp(reactionQueue.generated_at)}` : 'No queue timestamp',
            `Comments ${numberMeta(reactionQueue?.counts?.comment_opportunities)}`,
            `Post seeds ${numberMeta(reactionQueue?.counts?.post_seeds)}`,
          ]}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
            <BriefOverlayBlock
              title="Immediate Comment Opportunities"
              items={commentOpportunities.map((item) => `${item.title} · ${item.author || humanizeSnakeCase(item.priority_lane || 'unknown lane')}`)}
              emptyLabel="No comment-ready items in the queue right now."
            />
            <BriefOverlayBlock
              title="Post Seeds"
              items={postSeeds.map((item) => `${item.title} · ${item.post_angle || item.summary || 'No angle yet.'}`)}
              emptyLabel="No post seeds in the queue right now."
            />
          </div>
        </WorkspaceMirrorCard>

        <WorkspaceMirrorCard
          title="Social Feed + Tuning"
          meta={[
            socialFeed?.generated_at ? `Updated ${formatTimestamp(socialFeed.generated_at)}` : 'No feed timestamp',
            `Items ${numberMeta(socialFeed?.items?.length)}`,
            `Feedback ${numberMeta(feedbackSummary?.total_events)}`,
          ]}
        >
          <div style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
              <TelemetryStat label="Feedback Events" value={feedbackSummary?.total_events ?? 0} tone="#fbbf24" detail="copy / like / dislike / approve" />
              <TelemetryStat
                label="Avg Eval"
                value={typeof feedbackSummary?.average_evaluation_overall === 'number' ? feedbackSummary.average_evaluation_overall : 0}
                tone="#38bdf8"
                detail="recent recorded output quality"
              />
              <TelemetryStat
                label="Expression"
                value={typeof feedbackSummary?.average_output_expression_quality === 'number' ? feedbackSummary.average_output_expression_quality : 0}
                tone="#22c55e"
                detail="recent expression quality"
              />
            </div>
            <div style={{ display: 'grid', gap: '10px' }}>
              {feedItems.length > 0 ? (
                feedItems.map((item) => (
                  <MirrorItemCard
                    key={item.id}
                    title={item.title}
                    body={item.why_it_matters || item.summary || item.standout_lines?.[0] || 'No summary available.'}
                    meta={[
                      item.author || null,
                      item.platform ? humanizeSnakeCase(item.platform) : null,
                      typeof item.evaluation?.overall === 'number' ? `eval ${item.evaluation.overall.toFixed(1)}` : null,
                      typeof item.ranking?.total === 'number' ? `rank ${item.ranking.total.toFixed(1)}` : null,
                    ]}
                    href={item.source_url || null}
                    hrefLabel="Open post"
                  />
                ))
              ) : (
                <MirrorEmptyState message="No feed items are visible in the current workspace snapshot." />
              )}
            </div>
          </div>
        </WorkspaceMirrorCard>
      </div>
    </section>
  );
}

function WorkspaceMirrorCard({
  title,
  meta,
  children,
}: {
  title: string;
  meta: string[];
  children: ReactNode;
}) {
  return (
    <details
      style={{
        borderRadius: '14px',
        border: '1px solid #1f2937',
        backgroundColor: '#020617',
        overflow: 'hidden',
      }}
    >
      <summary
        style={{
          cursor: 'pointer',
          listStyle: 'none',
          padding: '14px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          gap: '12px',
          alignItems: 'center',
          color: 'white',
        }}
      >
        <span style={{ display: 'grid', gap: '4px', minWidth: 0 }}>
          <span style={{ color: '#e2e8f0', fontSize: '15px', fontWeight: 600 }}>{title}</span>
          <span style={{ color: '#64748b', fontSize: '12px' }}>{meta.filter(Boolean).join(' · ')}</span>
        </span>
        <span style={{ color: '#38bdf8', fontSize: '12px', whiteSpace: 'nowrap' }}>Expand</span>
      </summary>
      <div style={{ padding: '0 16px 16px', display: 'grid', gap: '12px' }}>{children}</div>
    </details>
  );
}

function MirrorItemCard({
  title,
  body,
  meta,
  href,
  hrefLabel,
}: {
  title: string;
  body: string;
  meta: (string | null)[];
  href?: string | null;
  hrefLabel?: string;
}) {
  return (
    <div style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712', padding: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start', marginBottom: '6px', flexWrap: 'wrap' }}>
        <p style={{ color: 'white', fontSize: '14px', fontWeight: 600, margin: 0 }}>{title}</p>
        {href && (
          <a href={href} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
            {hrefLabel || 'Open'}
          </a>
        )}
      </div>
      <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: '0 0 8px' }}>{body}</p>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {meta.filter(Boolean).map((item, index) => (
          <InlineBadge key={`${title}-meta-${index}`} label={String(item)} tone="#64748b" />
        ))}
      </div>
    </div>
  );
}

function MirrorEmptyState({ message }: { message: string }) {
  return (
    <div style={{ borderRadius: '12px', border: '1px dashed #334155', backgroundColor: '#030712', padding: '14px', color: '#64748b', fontSize: '13px' }}>
      {message}
    </div>
  );
}

function DailyBriefsPanel({
  briefs,
  selected,
  onSelect,
  error,
  onRefresh,
}: {
  briefs: DailyBriefEntry[];
  selected: DailyBriefEntry | null;
  onSelect: (entry: DailyBriefEntry) => void;
  error: string | null;
  onRefresh: () => Promise<void>;
}) {
  const selectedSourceIntelligence = selected ? briefSourceIntelligence(selected) : null;
  const streamItems = selected ? briefStreamItems(selected) : [];
  return (
    <section style={{ display: 'flex', gap: '18px', borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', minHeight: '520px' }}>
      <div style={{ width: '280px', borderRight: '1px solid #0f172a', paddingRight: '14px', maxHeight: '480px', overflowY: 'auto' }}>
        {error && <p style={{ color: '#f87171' }}>{error}</p>}
        {!error && briefs.length === 0 && <p style={{ color: '#475569' }}>No daily briefs saved yet.</p>}
        {briefs.map((entry) => (
          <button
            key={entry.id}
            onClick={() => onSelect(entry)}
            style={{
              width: '100%',
              textAlign: 'left',
              marginBottom: '8px',
              padding: '10px',
              borderRadius: '12px',
              border: entry === selected ? '1px solid #38bdf8' : '1px solid transparent',
              backgroundColor: entry === selected ? '#0f172a' : 'transparent',
              color: 'white',
              cursor: 'pointer',
            }}
          >
            <p style={{ fontSize: '12px', color: '#94a3b8' }}>{entry.brief_date}</p>
            <p style={{ fontSize: '14px', fontWeight: 600 }}>{entry.title}</p>
          </button>
        ))}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {selected ? (
          <div style={{ display: 'grid', gap: '14px' }}>
            <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '4px' }}>{selected.brief_date}</p>
            <div>
              <h2 style={{ color: 'white', fontSize: '26px', marginBottom: '8px' }}>{selected.title}</h2>
              {selected.summary && <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '12px' }}>{selected.summary}</p>}
            </div>
            <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
              <p style={{ color: '#fbbf24', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Surface Contract</p>
              <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                Daily Briefs are for fast system awareness: what happened, what changed, and what deserves attention now. Persona is the separate curation surface where you decide what should become durable identity, worldview, or canon.
              </p>
            </div>
            <BriefLaneLegendPanel />
            <BriefSystemChainPanel brief={selected} overlay={selectedSourceIntelligence} streamCount={streamItems.length} />
            {selectedSourceIntelligence && <BriefSourceIntelligencePanel overlay={selectedSourceIntelligence} />}
            {streamItems.length > 0 && <BriefStreamPanel brief={selected} items={streamItems} onRefresh={onRefresh} />}
            <div
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '16px',
                color: '#cbd5f5',
                fontSize: '14px',
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
              }}
            >
              <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 10px' }}>Saved Brief</p>
              {selected.content_markdown}
            </div>
          </div>
        ) : (
          <p style={{ color: '#475569' }}>Select a brief to read the saved markdown.</p>
        )}
      </div>
    </section>
  );
}

function BriefLaneLegendPanel() {
  const lanes: BriefConsumerLane[] = ['source_only', 'brief_only', 'persona_candidate', 'post_candidate', 'route_to_pm'];
  return (
    <section style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#22c55e', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Handoff Lanes</p>
        <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
          The source system can feed multiple downstream consumers, but each consumer has a different job. These lane labels tell you whether an item should stay awareness-only, become persona work, turn into public expression, or earn explicit operational routing.
        </p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
        {lanes.map((lane) => {
          const definition = briefConsumerLaneDefinition(lane);
          return (
            <div key={lane} style={{ borderRadius: '12px', border: `1px solid ${definition.tone}33`, backgroundColor: `${definition.tone}10`, padding: '12px' }}>
              <p style={{ color: definition.tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{definition.label}</p>
              <p style={{ color: '#dbe7ff', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{definition.description}</p>
            </div>
          );
        })}
      </div>
      <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.5, margin: '10px 0 0' }}>
        The live cards below only show promoted candidates. Source-only and brief-only signals can still appear in the saved brief or upstream counts without becoming Persona or PM work.
      </p>
    </section>
  );
}

function BriefSystemChainPanel({
  brief,
  overlay,
  streamCount,
}: {
  brief: DailyBriefEntry;
  overlay: BriefSourceIntelligence | null;
  streamCount: number;
}) {
  const reviewCount = overlay?.top_review_items?.length ?? 0;
  const syncOrigin =
    typeof brief.metadata?.sync_origin === 'string' && brief.metadata.sync_origin.trim()
      ? brief.metadata.sync_origin.trim()
      : brief.source;
  const cards = [
    {
      title: 'System Digest',
      value: brief.brief_date,
      detail: `Saved narrative snapshot from ${humanizeSnakeCase(syncOrigin || 'workspace_markdown')}`,
      tone: '#818cf8',
    },
    {
      title: 'Live Source Layer',
      value: overlay?.generated_at ? formatTimestamp(overlay.generated_at) : 'No live overlay',
      detail: overlay ? 'Current upstream source pressure layered onto the latest brief.' : 'No source overlay attached to this brief.',
      tone: '#38bdf8',
    },
    {
      title: 'Action Stream',
      value: String(streamCount),
      detail: 'Posting or response-ready items flowing from the same source system.',
      tone: '#22c55e',
    },
    {
      title: 'Persona Handoff',
      value: String(reviewCount),
      detail: 'Possible persona curation items surfaced from the same live source layer.',
      tone: '#f59e0b',
    },
  ];

  return (
    <section style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#a78bfa', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Shared Intelligence Chain</p>
        <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
          The brief is the saved digest. The live overlay is the current upstream source system. Persona is downstream from this flow: the brief can point toward persona implications, but persona curation still happens in the Persona queue.
        </p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
        {cards.map((card) => (
          <div key={card.title} style={{ borderRadius: '12px', border: `1px solid ${card.tone}33`, backgroundColor: `${card.tone}10`, padding: '12px' }}>
            <p style={{ color: card.tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{card.title}</p>
            <p style={{ color: 'white', fontSize: '15px', fontWeight: 700, margin: '0 0 6px' }}>{card.value}</p>
            <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>{card.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function BriefSourceIntelligencePanel({ overlay }: { overlay: BriefSourceIntelligence }) {
  const sourceCounts = overlay.source_counts ?? {};
  const assetCounts = overlay.source_asset_counts ?? {};
  const routeCounts = overlay.route_counts ?? {};
  const relationCounts = overlay.belief_relation_counts ?? {};
  const briefAwareness = overlay.top_brief_awareness ?? [];
  const mediaSeeds = overlay.top_media_post_seeds ?? [];
  const beliefEvidence = overlay.top_belief_evidence ?? [];
  const pmRouteCandidates = overlay.top_pm_route_candidates ?? [];
  const reviewItems = overlay.top_review_items ?? [];

  return (
    <section
      style={{
        borderRadius: '14px',
        border: '1px solid #1f2937',
        backgroundColor: '#020617',
        padding: '16px',
        marginBottom: '12px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', marginBottom: '10px', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Live Source Intelligence</p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, maxWidth: '760px' }}>
            This is the current shared source and planning overlay. It can point toward posting, planning, or persona implications, but it is not itself a second persona queue.
          </p>
          <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.5, margin: '8px 0 0' }}>
            Each highlighted item now carries a downstream lane label so the brief can show what it is nominating without pretending to do the persona decision itself.
          </p>
        </div>
        <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right' }}>
          <div>{overlay.generated_at ? formatTimestamp(overlay.generated_at) : 'No live timestamp'}</div>
          {overlay.base_generated_at && <div>Base plan {overlay.base_generated_at}</div>}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
        <InlineBadge label={`brief ${numberMeta(overlay.brief_awareness_count)}`} tone="#38bdf8" />
        <InlineBadge label={`media ${numberMeta(sourceCounts.media)}`} tone="#38bdf8" />
        <InlineBadge label={`belief ${numberMeta(sourceCounts.belief_evidence)}`} tone="#22c55e" />
        <InlineBadge label={`pm ${numberMeta(overlay.pm_route_candidate_count)}`} tone="#fb7185" />
        <InlineBadge label={`assets ${numberMeta(assetCounts.total)}`} tone="#818cf8" />
        <InlineBadge label={`segments ${numberMeta(routeCounts.post_seed)}/${numberMeta(routeCounts.belief_evidence)}`} tone="#f59e0b" />
        <InlineBadge label={`relations ${Object.keys(relationCounts).length}`} tone="#64748b" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '12px' }}>
        <PriorityFocusCard
          title="What matters now"
          description={briefAwareness[0] ? compactBriefCandidate(briefAwareness[0]) : 'No awareness-only source signal is leading the brief right now.'}
          tone="#38bdf8"
          lane="brief_only"
        />
        <PriorityFocusCard
          title="What deserves a post"
          description={mediaSeeds[0] ? compactBriefCandidate(mediaSeeds[0]) : 'No strong media-derived post seed has surfaced yet.'}
          tone="#38bdf8"
          lane="post_candidate"
        />
        <PriorityFocusCard
          title="What may affect persona"
          description={beliefEvidence[0] ? compactBriefCandidate(beliefEvidence[0]) : 'No strong persona-relevant belief signal is visible right now.'}
          tone="#22c55e"
          lane="persona_candidate"
        />
        <PriorityFocusCard
          title="What may need routing"
          description={pmRouteCandidates[0] ? compactBriefCandidate(pmRouteCandidates[0]) : 'No operational route candidate is surfacing from the source layer right now.'}
          tone="#fb7185"
          lane="route_to_pm"
        />
        <PriorityFocusCard
          title="What may need persona curation"
          description={reviewItems[0] ? compactReviewItem(reviewItems[0]) : 'No persona handoff item is at the top of the queue right now.'}
          tone="#818cf8"
          lane="persona_candidate"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        <BriefOverlayBlock
          title="Route Mix"
          items={Object.entries(routeCounts).map(([key, value]) => `${humanizeSnakeCase(key)}: ${value}`)}
          emptyLabel="No route counts yet."
        />
        <BriefOverlayBlock
          title="Belief Relations"
          items={Object.entries(relationCounts).map(([key, value]) => `${humanizeBeliefRelation(key)}: ${value}`)}
          emptyLabel="No relation counts yet."
        />
        <BriefOverlayBlock
          title="Brief Awareness"
          items={briefAwareness.map((item) => compactBriefCandidate(item))}
          emptyLabel="No awareness-only source highlights yet."
        />
        <BriefOverlayBlock
          title="Top Media Seeds"
          items={mediaSeeds.map((item) => compactBriefCandidate(item))}
          emptyLabel="No live media seeds yet."
        />
        <BriefOverlayBlock
          title="Signals With Persona Implications"
          items={beliefEvidence.map((item) => compactBriefCandidate(item))}
          emptyLabel="No live persona-relevant signals yet."
        />
        <BriefOverlayBlock
          title="Operational Route Candidates"
          items={pmRouteCandidates.map((item) => compactBriefCandidate(item))}
          emptyLabel="No operational route candidates yet."
        />
      </div>

      {reviewItems.length > 0 && (
        <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #1f2937' }}>
          <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Persona Handoff Preview</p>
          <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5, margin: '0 0 8px' }}>
            These items are possible handoffs into Persona. They are not canon decisions yet, and they should be judged in the Persona queue rather than here in the brief.
          </p>
          <div style={{ display: 'grid', gap: '8px' }}>
            {reviewItems.map((item, index) => (
              <div key={`${item.trait ?? 'review'}-${index}`} style={{ borderRadius: '10px', border: '1px solid #1f2937', padding: '10px', backgroundColor: '#030712' }}>
                <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.5, marginBottom: '6px' }}>{item.trait ?? 'Untitled review item'}</p>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <InlineBadge label={briefConsumerLaneDefinition('persona_candidate').label} tone={briefConsumerLaneDefinition('persona_candidate').tone} />
                  <InlineBadge label={humanizeBeliefRelation(item.belief_relation ?? null)} tone="#22c55e" />
                  <InlineBadge label={humanizeReviewSource(item.review_source ?? null)} tone="#64748b" />
                  {item.target_file && <InlineBadge label={item.target_file} tone="#818cf8" />}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function BriefStreamPanel({
  brief,
  items,
  onRefresh,
}: {
  brief: DailyBriefEntry;
  items: BriefSourceIntelligenceCandidate[];
  onRefresh: () => Promise<void>;
}) {
  const [activeItemKey, setActiveItemKey] = useState<string>(items[0]?.item_key?.trim() || '');
  const [reactionKind, setReactionKind] = useState<'agree' | 'disagree' | 'nuance' | 'story'>('nuance');
  const [reactionText, setReactionText] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const firstKey = items[0]?.item_key?.trim() || '';
    setActiveItemKey((current) => (current && items.some((item) => item.item_key === current) ? current : firstKey));
    setReactionText('');
    setMessage(null);
    setError(null);
  }, [brief.id, items]);

  const activeItem = items.find((item) => item.item_key === activeItemKey) ?? items[0] ?? null;

  function startReaction(item: BriefSourceIntelligenceCandidate, kind: 'agree' | 'disagree' | 'nuance' | 'story') {
    setActiveItemKey(item.item_key?.trim() || '');
    setReactionKind(kind);
    const title = item.title?.trim() || 'this';
    const prefix =
      kind === 'agree'
        ? `What I agree with about "${title}":\n- `
        : kind === 'disagree'
        ? `What I disagree with about "${title}":\n- `
        : kind === 'story'
        ? `Story or example this brings up for "${title}":\n- `
        : `Nuance I want to preserve for "${title}":\n- `;
    setReactionText((current) => (current.trim().length > 0 && activeItemKey === item.item_key ? current : prefix));
    setMessage(null);
    setError(null);
  }

  async function submitReaction() {
    if (!activeItem) return;
    const trimmed = reactionText.trim();
    if (!trimmed) {
      setError('Add a thought before saving it to Persona.');
      return;
    }
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/api/briefs/reactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brief_id: brief.id,
          item_key: activeItem.item_key,
          item_title: activeItem.title,
          item_summary: activeItem.summary,
          item_hook: activeItem.hook,
          source_kind: activeItem.source_kind,
          source_url: activeItem.source_url,
          source_path: activeItem.source_path,
          priority_lane: activeItem.priority_lane,
          route_reason: activeItem.route_reason,
          target_file: activeItem.target_file,
          reaction_kind: reactionKind,
          text: trimmed,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `Save failed with ${response.status}`);
      }
      setReactionText('');
      setMessage(`Saved to Persona as ${humanizeResponseKind(reactionKind)}. It is now in the Brain review flow.`);
      await onRefresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save this brief reaction right now.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      style={{
        borderRadius: '14px',
        border: '1px solid #1f2937',
        backgroundColor: '#020617',
        padding: '16px',
        display: 'grid',
        gap: '14px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Brief Stream</p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
            Read the source cards, react here, and let those reactions feed Persona. The lane labels tell you whether the card is mainly a post candidate, a persona candidate, or a signal that only deserves awareness unless you explicitly route it further.
          </p>
        </div>
        <InlineBadge label={`${items.length} source card${items.length === 1 ? '' : 's'}`} tone="#38bdf8" />
      </div>

      <div style={{ display: 'grid', gap: '12px' }}>
        {items.map((item) => {
          const isActive = item.item_key === activeItem?.item_key;
          const consumerLanes = briefConsumerLanesForCandidate(item);
          const primaryLane = consumerLanes[0] ?? 'brief_only';
          const primaryLaneDefinition = briefConsumerLaneDefinition(primaryLane);
          const relatedContext = item.related_persona_context ?? [];
          const existingReactions = item.existing_reactions ?? [];
          return (
            <article
              key={item.item_key || item.title}
              style={{
                borderRadius: '14px',
                border: `1px solid ${isActive ? '#38bdf8' : '#1f2937'}`,
                backgroundColor: isActive ? '#081325' : '#010617',
                padding: '14px',
                display: 'grid',
                gap: '10px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <div style={{ minWidth: 0 }}>
                  <h3 style={{ color: 'white', fontSize: '16px', margin: '0 0 6px', lineHeight: 1.45 }}>{item.title || 'Untitled source'}</h3>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {consumerLanes.map((lane) => {
                      const definition = briefConsumerLaneDefinition(lane);
                      return <InlineBadge key={`${item.item_key || item.title}-${lane}`} label={definition.label} tone={definition.tone} />;
                    })}
                    {item.section && <InlineBadge label={humanizeSnakeCase(item.section)} tone="#818cf8" />}
                    {item.priority_lane && <InlineBadge label={humanizeSnakeCase(item.priority_lane)} tone="#22c55e" />}
                    {item.source_kind && <InlineBadge label={humanizeSnakeCase(item.source_kind)} tone="#64748b" />}
                    {item.target_file && <InlineBadge label={humanizeTargetFileLabel(item.target_file)} tone="#64748b" />}
                  </div>
                </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <Link
                  href={buildPostingWorkspaceHref(item, 'post')}
                  style={{
                    borderRadius: '999px',
                    border: '1px solid rgba(56,189,248,0.55)',
                    backgroundColor: '#082f49',
                    color: 'white',
                    padding: '8px 12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    textDecoration: 'none',
                  }}
                >
                  Write post
                </Link>
                <Link
                  href={buildPostingWorkspaceHref(item, 'comment')}
                  style={{
                    borderRadius: '999px',
                    border: '1px solid rgba(34,197,94,0.55)',
                    backgroundColor: '#052e1a',
                    color: 'white',
                    padding: '8px 12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    textDecoration: 'none',
                  }}
                >
                  Comment on this
                </Link>
                {item.source_url && (
                  <a
                    href={item.source_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        borderRadius: '999px',
                        border: '1px solid #334155',
                        backgroundColor: '#020617',
                        color: '#cbd5f5',
                        padding: '8px 12px',
                        fontSize: '12px',
                        fontWeight: 600,
                        textDecoration: 'none',
                      }}
                    >
                      Open source
                    </a>
                  )}
                </div>
              </div>

              <p style={{ color: primaryLaneDefinition.tone, fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                {briefConsumerLaneGuidance(primaryLane)}
              </p>
              {item.summary && <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.6, margin: 0 }}>{item.summary}</p>}
              {item.hook && <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>Hook: {item.hook}</p>}
              {item.route_reason && <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>Why it matters: {item.route_reason}</p>}
              {item.source_path && !item.source_url && <p style={{ color: '#475569', fontSize: '11px', margin: 0 }}>{item.source_path}</p>}

              {relatedContext.length > 0 && (
                <div style={{ display: 'grid', gap: '8px' }}>
                  <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Related Persona Context</p>
                  {relatedContext.map((context) => (
                    <div key={context.delta_id} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020b16', padding: '10px 12px' }}>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                        <InlineBadge label={humanizeSavedResponseKind(context.response_kind || 'nuance')} tone="#818cf8" />
                        {context.target_file && <InlineBadge label={humanizeTargetFileLabel(context.target_file)} tone="#64748b" />}
                        {context.review_source && <InlineBadge label={humanizeReviewSource(context.review_source)} tone="#64748b" />}
                      </div>
                      <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600, margin: '0 0 4px' }}>{context.trait}</p>
                      {context.excerpt && <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{context.excerpt}</p>}
                    </div>
                  ))}
                </div>
              )}

              {existingReactions.length > 0 && (
                <div style={{ display: 'grid', gap: '8px' }}>
                  <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Recent Brief Reactions</p>
                  {existingReactions.map((reaction) => (
                    <div key={reaction.id} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020b16', padding: '10px 12px' }}>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                        <InlineBadge label={humanizeSavedResponseKind(reaction.reaction_kind)} tone="#38bdf8" />
                        {reaction.linked_delta_id && <InlineBadge label="Linked to Persona" tone="#22c55e" />}
                      </div>
                      <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{truncateText(reaction.text, 220)}</p>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <QuickFillButton label="Agree" onClick={() => startReaction(item, 'agree')} />
                <QuickFillButton label="Disagree" onClick={() => startReaction(item, 'disagree')} />
                <QuickFillButton label="Nuance" onClick={() => startReaction(item, 'nuance')} />
                <QuickFillButton label="Story" onClick={() => startReaction(item, 'story')} />
              </div>

              {isActive && (
                <div style={{ display: 'grid', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <InlineBadge label={`Saving as ${humanizeResponseKind(reactionKind)}`} tone="#38bdf8" />
                    <InlineBadge label={`Source role ${primaryLaneDefinition.label}`} tone={primaryLaneDefinition.tone} />
                    {item.target_file && <InlineBadge label={`Persona target ${humanizeTargetFileLabel(item.target_file)}`} tone="#64748b" />}
                  </div>
                  <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                    Saving a reaction here creates a Persona handoff. It does not automatically change the underlying source role of this card, which is currently <span style={{ color: primaryLaneDefinition.tone }}>{primaryLaneDefinition.label.toLowerCase()}</span>.
                  </p>
                  <textarea
                    value={reactionText}
                    onChange={(event) => {
                      setReactionText(event.target.value);
                      if (message) setMessage(null);
                      if (error) setError(null);
                    }}
                    placeholder="Capture your actual take here. This will save to Open Brain and create a linked Persona delta."
                    style={brainTextareaStyle}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                    <div style={{ display: 'grid', gap: '4px' }}>
                      {message && <span style={{ color: '#22c55e', fontSize: '12px' }}>{message}</span>}
                      {error && <span style={{ color: '#f87171', fontSize: '12px' }}>{error}</span>}
                    </div>
                    <button
                      onClick={() => submitReaction()}
                      disabled={saving}
                      style={{
                        border: '1px solid #38bdf8',
                        backgroundColor: saving ? '#0c4a6e' : '#0f172a',
                        color: 'white',
                        borderRadius: '12px',
                        padding: '10px 14px',
                        cursor: saving ? 'wait' : 'pointer',
                        fontWeight: 600,
                      }}
                    >
                      {saving ? 'Saving…' : 'Save to Persona'}
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function BriefOverlayBlock({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel: string }) {
  return (
    <div style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712', padding: '12px' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{title}</p>
      {items.length === 0 ? (
        <p style={{ color: '#475569', fontSize: '12px' }}>{emptyLabel}</p>
      ) : (
        <div style={{ display: 'grid', gap: '6px' }}>
          {items.map((item, index) => (
            <p key={`${title}-${index}`} style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.45 }}>
              {item}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function PriorityFocusCard({
  title,
  description,
  tone,
  lane,
}: {
  title: string;
  description: string;
  tone: string;
  lane?: BriefConsumerLane;
}) {
  const laneDefinition = lane ? briefConsumerLaneDefinition(lane) : null;
  return (
    <div style={{ borderRadius: '12px', border: `1px solid ${tone}33`, backgroundColor: `${tone}10`, padding: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start', marginBottom: '8px', flexWrap: 'wrap' }}>
        <p style={{ color: tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>{title}</p>
        {laneDefinition && <InlineBadge label={laneDefinition.label} tone={laneDefinition.tone} />}
      </div>
      <p style={{ color: '#dbe7ff', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{description}</p>
    </div>
  );
}

function StepCallout({ step, title, description }: { step: string; title: string; description: string }) {
  return (
    <div style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '12px' }}>
      <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>
        Step {step}
      </p>
      <p style={{ color: 'white', fontSize: '14px', fontWeight: 600, margin: '0 0 6px' }}>{title}</p>
      <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{description}</p>
    </div>
  );
}

function PersonaPanel({
  packs,
  deltas,
  error,
  viewportWidth,
  viewportHeight,
  refreshBrainData,
  mergeUpdatedDelta,
}: {
  packs: PersonaPack[];
  deltas: PersonaDeltaEntry[];
  error: string | null;
  viewportWidth: number;
  viewportHeight: number;
  refreshBrainData: () => Promise<void>;
  mergeUpdatedDelta: (updatedDelta: PersonaDeltaEntry) => void;
}) {
  const [completedDeltaIds, setCompletedDeltaIds] = useState<string[]>([]);
  const [showMutedActive, setShowMutedActive] = useState(false);
  const [lifecycleView, setLifecycleView] = useState<'pending_promotion' | 'workspace_saved' | 'committed' | 'resolved'>('pending_promotion');
  const [showLifecycleAudit, setShowLifecycleAudit] = useState(false);
  const visibleDeltas = useMemo(() => deltas.filter((delta) => !completedDeltaIds.includes(delta.id)), [completedDeltaIds, deltas]);
  const activeReviewDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'brain_pending_review'), [visibleDeltas]);
  const workspaceSavedDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'workspace_saved'), [visibleDeltas]);
  const pendingPromotionDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'pending_promotion'), [visibleDeltas]);
  const committedDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'committed'), [visibleDeltas]);
  const resolvedHistoryDeltas = useMemo(
    () =>
      visibleDeltas.filter((delta) => {
        const stage = personaDeltaStage(delta);
        return stage === 'resolved' || stage === 'approved_unpromoted' || stage === 'reviewed';
      }),
    [visibleDeltas],
  );
  const scoredActiveReviewDeltas = useMemo(
    () =>
      activeReviewDeltas
        .map((delta) => {
          const promotionCandidateCount = promotionSignalCount(delta.metadata);
          const muted = shouldMuteActivePersonaDelta(delta, promotionCandidateCount);
          return {
            delta,
            muted,
            promotionCandidateCount,
            promotionReady: isPromotionReady(delta.status, delta.metadata),
            score: personaDeltaPriorityScore(delta, promotionCandidateCount, muted),
          };
        })
        .sort((left, right) => timestampMs(right.delta.created_at) - timestampMs(left.delta.created_at)),
    [activeReviewDeltas],
  );
  const primaryActiveReviewDeltas = useMemo(() => scoredActiveReviewDeltas.filter((item) => !item.muted), [scoredActiveReviewDeltas]);
  const mutedActiveReviewDeltas = useMemo(() => scoredActiveReviewDeltas.filter((item) => item.muted), [scoredActiveReviewDeltas]);
  const visibleActiveReviewDeltas = useMemo(() => {
    if (primaryActiveReviewDeltas.length === 0) {
      return mutedActiveReviewDeltas;
    }
    const combined = showMutedActive ? [...primaryActiveReviewDeltas, ...mutedActiveReviewDeltas] : primaryActiveReviewDeltas;
    return [...combined].sort((left, right) => timestampMs(right.delta.created_at) - timestampMs(left.delta.created_at));
  }, [mutedActiveReviewDeltas, primaryActiveReviewDeltas, showMutedActive]);
  const reviewQueue = useMemo(() => visibleActiveReviewDeltas.map((item) => item.delta), [visibleActiveReviewDeltas]);
  const [selectedDeltaId, setSelectedDeltaId] = useState<string>(reviewQueue[0]?.id ?? '');
  const [reflectionText, setReflectionText] = useState('');
  const [reflectionState, setReflectionState] = useState<{ tone: 'idle' | 'success' | 'error'; message: string }>({
    tone: 'idle',
    message: '',
  });
  const [isSavingReflection, setIsSavingReflection] = useState(false);
  const [promotionState, setPromotionState] = useState<{ tone: 'idle' | 'success' | 'error'; message: string }>({
    tone: 'idle',
    message: '',
  });
  const [promotingDeltaId, setPromotingDeltaId] = useState<string | null>(null);
  const [reroutingDeltaId, setReroutingDeltaId] = useState<string | null>(null);
  const [recentlyQueuedDeltaId, setRecentlyQueuedDeltaId] = useState<string | null>(null);
  const [recentlyCommittedDeltaId, setRecentlyCommittedDeltaId] = useState<string | null>(null);
  const [promotionItemTargetOverrides, setPromotionItemTargetOverrides] = useState<Record<string, string>>({});
  const [routeToMemory, setRouteToMemory] = useState(false);
  const [routeToStandup, setRouteToStandup] = useState(false);
  const [routeToPM, setRouteToPM] = useState(false);
  const [triageMemoryTargets, setTriageMemoryTargets] = useState<string[]>(['persistent_state']);
  const [triageWorkspaceKeys, setTriageWorkspaceKeys] = useState<string[]>(['shared_ops']);
  const [triageStandupKind, setTriageStandupKind] = useState<'auto' | 'executive_ops' | 'operations' | 'weekly_review' | 'saturday_vision' | 'workspace_sync'>('auto');
  const [triagePMTitle, setTriagePMTitle] = useState('');
  const [showTriageControls, setShowTriageControls] = useState(true);
  const [triageState, setTriageState] = useState<{ tone: 'idle' | 'success' | 'error'; message: string }>({ tone: 'idle', message: '' });
  const [isRoutingSignal, setIsRoutingSignal] = useState(false);
  const selectedDelta = useMemo(
    () => reviewQueue.find((delta) => delta.id === selectedDeltaId) ?? reviewQueue[0] ?? null,
    [reviewQueue, selectedDeltaId],
  );
  const selectedScoredDelta = useMemo(
    () => scoredActiveReviewDeltas.find((item) => item.delta.id === selectedDelta?.id) ?? null,
    [scoredActiveReviewDeltas, selectedDelta],
  );
  const targetFile = selectedDelta ? metadataText(selectedDelta.metadata, 'target_file') : null;
  const [selectedPromotionItemIds, setSelectedPromotionItemIds] = useState<string[]>([]);
  const [promotionFragmentView, setPromotionFragmentView] = useState<PromotionFragmentView>('recommended');
  const [selectedResponseKind, setSelectedResponseKind] = useState<'agree' | 'disagree' | 'nuance' | 'story' | 'language'>('nuance');
  const baseSelectableItems = useMemo(() => buildPromotionItems(selectedDelta, targetFile), [selectedDelta, targetFile]);
  const selectableItems = useMemo(
    () => applyPromotionTargetOverrides(baseSelectableItems, promotionItemTargetOverrides),
    [baseSelectableItems, promotionItemTargetOverrides],
  );
  const rankedSelectableItems = useMemo(() => rankPromotionItems(selectableItems, targetFile), [selectableItems, targetFile]);
  const recommendedSelectableItems = useMemo(
    () => rankedSelectableItems.filter((item) => resolvePromotionGate(item, targetFile).decision === 'allow'),
    [rankedSelectableItems, targetFile],
  );
  const needsWorkSelectableItems = useMemo(
    () => rankedSelectableItems.filter((item) => resolvePromotionGate(item, targetFile).decision !== 'allow'),
    [rankedSelectableItems, targetFile],
  );
  const displaySelectableItems = useMemo(() => {
    const selected = new Set(selectedPromotionItemIds);
    const base =
      promotionFragmentView === 'recommended'
        ? recommendedSelectableItems
        : promotionFragmentView === 'needs_work'
        ? needsWorkSelectableItems
        : rankedSelectableItems;
    if (selected.size === 0) {
      return base;
    }
    const merged = [...base];
    for (const item of rankedSelectableItems) {
      if (selected.has(item.id) && !merged.some((entry) => entry.id === item.id)) {
        merged.push(item);
      }
    }
    return merged;
  }, [
    needsWorkSelectableItems,
    promotionFragmentView,
    rankedSelectableItems,
    recommendedSelectableItems,
    selectedPromotionItemIds,
  ]);
  const selectedPromotionItems = useMemo(
    () => selectableItems.filter((item) => selectedPromotionItemIds.includes(item.id)),
    [selectableItems, selectedPromotionItemIds],
  );
  const selectedPromotionTargetFiles = useMemo(
    () => Array.from(new Set(selectedPromotionItems.map((item) => item.targetFile).filter((value): value is string => Boolean(value)))),
    [selectedPromotionItems],
  );
  const suggestedTargetFile = metadataText(selectedDelta?.metadata, 'suggested_target_file') ?? targetFile;
  const reviewSource = metadataText(selectedDelta?.metadata, 'review_source');
  const primaryRoute = metadataText(selectedDelta?.metadata, 'primary_route');
  const weakSourceFragment = metadataBoolean(selectedDelta?.metadata, 'weak_source_fragment');
  const contextTargetFile = selectedPromotionTargetFiles[0] ?? selectableItems[0]?.targetFile ?? suggestedTargetFile;
  const linkedPack = useMemo(() => findPackBySection(packs, contextTargetFile) ?? packs[0] ?? null, [packs, contextTargetFile]);
  const targetSection = useMemo(() => findPackSection(packs, contextTargetFile), [packs, contextTargetFile]);
  const activeContext = targetSection?.content ?? linkedPack?.sections[0]?.content ?? null;
  const activeContextPath = targetSection?.path ?? linkedPack?.sections[0]?.path ?? null;
  const reviewHeadline = selectedDelta ? buildReviewHeadline(selectedDelta, suggestedTargetFile) : 'No persona review items queued.';
  const reviewReason = selectedDelta ? buildReviewReason(selectedDelta, suggestedTargetFile, activeContextPath) : 'There is no pending persona item to review right now.';
  const reviewAsk = selectedDelta ? buildReviewAsk(selectedDelta, suggestedTargetFile) : 'You can still save a general thought to memory if you want to capture something new.';
  const evidenceLabel =
    metadataText(selectedDelta?.metadata, 'evidence_source') ?? (selectedDelta?.capture_id ? `capture ${selectedDelta.capture_id}` : 'Not linked yet');
  const statusLabel = selectedDelta?.status ?? 'pending';
  const savedResponseKind = metadataText(selectedDelta?.metadata, 'owner_response_kind');
  const savedResponseExcerpt = metadataText(selectedDelta?.metadata, 'owner_response_excerpt');
  const promotionTargetChoices = useMemo(
    () => candidateTargetsForItems(selectedPromotionItems.length > 0 ? selectedPromotionItems : selectableItems, targetFile),
    [selectedPromotionItems, selectableItems, targetFile],
  );
  const availablePromotionGate = useMemo(
    () => summarizePromotionItems(selectableItems, targetFile),
    [selectableItems, targetFile],
  );
  const selectedPromotionGate = useMemo(
    () => summarizePromotionItems(selectedPromotionItems, targetFile),
    [selectedPromotionItems, targetFile],
  );
  const activePromotionAlternativeTarget =
    (selectedPromotionItems.length > 0 ? selectedPromotionGate.alternativeTarget : null) || availablePromotionGate.alternativeTarget;
  const canonActionItems = useMemo(
    () => (selectedPromotionItems.length > 0 ? selectedPromotionItems : recommendedSelectableItems),
    [recommendedSelectableItems, selectedPromotionItems],
  );
  const canonActionGate = useMemo(
    () => summarizePromotionItems(canonActionItems, targetFile),
    [canonActionItems, targetFile],
  );
  const canMakeCanonNow = canonActionItems.length > 0 && canonActionGate.decision === 'allow';
  const hasRouteTargets = routeToMemory || routeToStandup || routeToPM;
  const isFinalizePending = isSavingReflection || isRoutingSignal;
  const finalizeActionDisabled = !hasRouteTargets && canonActionItems.length === 0;
  const finalizeActionBusyLabel = hasRouteTargets
    ? canMakeCanonNow
      ? 'Finalizing…'
      : 'Saving + routing…'
    : canMakeCanonNow
    ? 'Making canon…'
    : 'Saving canon…';
  const finalizeActionSummary = hasRouteTargets
    ? canonActionItems.length > 0
      ? canMakeCanonNow
      ? 'Finalize will write canon now and send this signal downstream.'
        : `${canonActionGate.reason || 'Finalize will save this canon selection.'} Routing runs in the same action.`
      : 'Finalize will save this review and send it downstream.'
    : canonActionItems.length > 0
    ? canMakeCanonNow
      ? 'Finalize will write the selected canon fragments now.'
      : canonActionGate.reason || 'Finalize will save this canon selection for later promotion.'
    : 'Choose canon fragments or route targets to finalize. Use Save note if you only want to capture your judgment.';
  const backendSuggestedWorkspaceKeys = useMemo(
    () => canonicalBrainWorkspaceKeys(metadataStringArray(selectedDelta?.metadata, 'brain_suggested_workspace_keys')),
    [selectedDelta],
  );
  const conservativeFallbackWorkspaceKeys = useMemo(() => fallbackBrainWorkspaceKeys(selectedDelta), [selectedDelta]);
  const usingBackendWorkspaceSuggestions = backendSuggestedWorkspaceKeys.length > 0;
  const suggestedWorkspaceKeys = useMemo(
    () => (usingBackendWorkspaceSuggestions ? backendSuggestedWorkspaceKeys : conservativeFallbackWorkspaceKeys),
    [backendSuggestedWorkspaceKeys, conservativeFallbackWorkspaceKeys, usingBackendWorkspaceSuggestions],
  );
  const backendWorkspaceSuggestionDetails = useMemo(
    () =>
      metadataArray(selectedDelta?.metadata, 'brain_workspace_suggestion_details').filter(
        (value): value is { workspace_key?: BrainWorkspaceKey; reasons?: string[] } =>
          Boolean(
            value &&
              typeof value === 'object' &&
              !Array.isArray(value) &&
              (!('workspace_key' in value) || value.workspace_key == null || (typeof value.workspace_key === 'string' && isBrainWorkspaceKey(value.workspace_key))),
          ),
      ),
    [selectedDelta],
  );
  const suggestedWorkspaceReasonSummary = useMemo(() => {
    const firstDetail = backendWorkspaceSuggestionDetails.find(
      (detail) => detail.workspace_key && suggestedWorkspaceKeys.includes(detail.workspace_key),
    );
    const firstReason = Array.isArray(firstDetail?.reasons) ? firstDetail?.reasons.find((reason) => typeof reason === 'string' && reason.trim().length > 0) : null;
    return typeof firstReason === 'string' ? firstReason : null;
  }, [backendWorkspaceSuggestionDetails, suggestedWorkspaceKeys]);
  const routeHistory = useMemo(
    () =>
      metadataArray(selectedDelta?.metadata, 'brain_route_history').filter(
        (entry): entry is BrainRouteHistoryEntry => Boolean(entry && typeof entry === 'object'),
      ),
    [selectedDelta],
  );
  const pendingCanonicalMemoryRoutes = useMemo(
    () =>
      metadataArray(selectedDelta?.metadata, 'pending_canonical_memory_routes').filter(
        (entry): entry is PendingCanonicalMemoryRouteEntry => Boolean(entry && typeof entry === 'object'),
      ),
    [selectedDelta],
  );
  const triageWorkspaceSelection = useMemo(() => (triageWorkspaceKeys.length > 0 ? triageWorkspaceKeys : suggestedWorkspaceKeys), [suggestedWorkspaceKeys, triageWorkspaceKeys]);
  const triageExecutionPreviews = useMemo(
    () =>
      triageWorkspaceSelection.map((workspaceKey) => {
        const effectiveKind = triageStandupKind === 'auto' ? suggestStandupKindForWorkspace(workspaceKey) : triageStandupKind;
        return {
          workspaceKey,
          standupKind: effectiveKind,
          participants: participantsForBrainRoute(workspaceKey, effectiveKind),
          executionModel: executionModelForBrainWorkspace(workspaceKey),
        };
      }),
    [triageStandupKind, triageWorkspaceSelection],
  );
  const triageWorkspaceSummary = useMemo(
    () => triageWorkspaceSelection.map(labelForBrainWorkspace).join(', '),
    [triageWorkspaceSelection],
  );
  const triageRouteSummary = useMemo(() => {
    const parts: string[] = [];
    if (routeToMemory) {
      parts.push(
        triageMemoryTargets.length > 0
          ? `Memory: ${triageMemoryTargets.map(humanizeCanonicalMemoryTarget).join(', ')}`
          : 'Memory enabled',
      );
    }
    if (routeToStandup) {
      parts.push(`Standup: ${compactStandupKind(triageStandupKind)}`);
    }
    if (routeToPM) {
      parts.push('PM queue enabled');
    }
    return parts.length > 0 ? parts.join(' · ') : 'Review only for now. No downstream routing is enabled.';
  }, [routeToMemory, routeToPM, routeToStandup, triageMemoryTargets, triageStandupKind]);
  const sourceTitle = metadataText(selectedDelta?.metadata, 'evidence_source') ?? metadataText(selectedDelta?.metadata, 'source_asset_id') ?? selectedDelta?.trait ?? 'Untitled source';
  const sourceChannel = metadataText(selectedDelta?.metadata, 'source_channel') ?? metadataText(selectedDelta?.metadata, 'source_type');
  const sourceUrl = metadataText(selectedDelta?.metadata, 'source_url');
  const sourceExcerpt =
    metadataText(selectedDelta?.metadata, 'source_excerpt_clean') ??
    metadataText(selectedDelta?.metadata, 'segment_excerpt') ??
    metadataStringArray(selectedDelta?.metadata, 'talking_points')[0] ??
    selectedDelta?.notes?.trim() ??
    null;
  const sourceContextExcerpt = metadataText(selectedDelta?.metadata, 'source_context_excerpt');
  const sourceContextBefore = metadataStringArray(selectedDelta?.metadata, 'source_context_before');
  const sourceContextAfter = metadataStringArray(selectedDelta?.metadata, 'source_context_after');
  const talkingPoints = useMemo(
    () =>
      metadataStringArray(selectedDelta?.metadata, 'talking_points')
        .filter((point) => point && point !== sourceExcerpt)
        .slice(0, 3),
    [selectedDelta, sourceExcerpt],
  );
  const routeOptions = useMemo(
    () =>
      Array.from(
        new Set(
          metadataStringArray(selectedDelta?.metadata, 'response_modes').filter((value) => value && value !== primaryRoute),
        ),
      ),
    [selectedDelta, primaryRoute],
  );
  const beliefSummary = metadataText(selectedDelta?.metadata, 'system_hypothesis') ?? metadataText(selectedDelta?.metadata, 'belief_summary');
  const experienceAnchor = metadataText(selectedDelta?.metadata, 'experience_anchor');
  const experienceSummary =
    metadataText(selectedDelta?.metadata, 'system_experience_hypothesis') ?? metadataText(selectedDelta?.metadata, 'experience_summary');
  const routeReason = metadataText(selectedDelta?.metadata, 'route_reason');
  const pendingCount = primaryActiveReviewDeltas.length;
  const totalPendingCount = scoredActiveReviewDeltas.length;
  const mutedCount = mutedActiveReviewDeltas.length;
  const promotionReadyCount = scoredActiveReviewDeltas.filter((item) => item.promotionReady).length;
  const lifecycleGroups = useMemo(
    () => [
      {
        key: 'workspace_saved',
        title: 'Workspace Saved',
        description: 'Approved from Workspace and already saved. No second approval needed here.',
        count: workspaceSavedDeltas.length,
        items: workspaceSavedDeltas,
        tone: '#22c55e',
      },
      {
        key: 'pending_promotion',
        title: 'Queued For Promotion',
        description: 'Reviewed in Brain and holding selected canonical items for later promotion.',
        count: pendingPromotionDeltas.length,
        items: pendingPromotionDeltas,
        tone: '#38bdf8',
      },
      {
        key: 'committed',
        title: 'Committed',
        description: 'Already written into canonical persona files.',
        count: committedDeltas.length,
        items: committedDeltas,
        tone: '#818cf8',
      },
      {
        key: 'resolved',
        title: 'Resolved / Replaced',
        description: 'Historical items that were handled, superseded, or intentionally cleared.',
        count: resolvedHistoryDeltas.length,
        items: resolvedHistoryDeltas,
        tone: '#64748b',
      },
    ],
    [committedDeltas, pendingPromotionDeltas, resolvedHistoryDeltas, workspaceSavedDeltas],
  );
  const activeLifecycleGroup = useMemo(
    () => lifecycleGroups.find((group) => group.key === lifecycleView) ?? lifecycleGroups[0],
    [lifecycleGroups, lifecycleView],
  );
  const stackPersonaShell = viewportWidth < 1220;
  const stackPersonaDetail = viewportWidth < 1480;
  const usePinnedPersonaViewport = viewportWidth >= 1180 && viewportHeight >= 760;
  const compactPersonaChrome = usePinnedPersonaViewport;
  const personaViewportHeight = usePinnedPersonaViewport ? 'calc(100vh - 162px)' : 'auto';
  const personaSectionRows = usePinnedPersonaViewport
    ? showLifecycleAudit
      ? selectedDelta
        ? 'minmax(0, 1.42fr) minmax(300px, 0.64fr)'
        : 'minmax(0, 1.1fr) minmax(300px, 0.9fr)'
      : 'minmax(0, 1fr) auto'
    : 'none';
  const activeReviewRows = usePinnedPersonaViewport ? 'auto auto auto minmax(0, 1fr) auto' : 'none';
  const reflectionToneColor = reflectionState.tone === 'success' ? '#22c55e' : reflectionState.tone === 'error' ? '#f87171' : '#64748b';
  const triageToneColor = triageState.tone === 'success' ? '#22c55e' : triageState.tone === 'error' ? '#f87171' : '#64748b';

  useEffect(() => {
    if (!usePinnedPersonaViewport) {
      setShowLifecycleAudit(true);
    }
  }, [usePinnedPersonaViewport]);

  useEffect(() => {
    if (!selectedDelta && reviewQueue[0]) {
      setSelectedDeltaId(reviewQueue[0].id);
      return;
    }
    if (reviewQueue.length === 0 && selectedDeltaId) {
      setSelectedDeltaId('');
    }
  }, [reviewQueue, selectedDelta, selectedDeltaId]);

  useEffect(() => {
    const existingItems = readPromotionItemsFromMetadata(selectedDelta?.metadata);
    const existingIds = existingItems.map((item) => item.id);
    const availableIds = new Set(selectableItems.map((item) => item.id));
    setSelectedPromotionItemIds(existingIds.filter((itemId) => availableIds.has(itemId)));
  }, [selectableItems, selectedDelta?.id, selectedDelta?.metadata]);

  useEffect(() => {
    const existing = metadataText(selectedDelta?.metadata, 'owner_response_kind');
    if (existing === 'agree' || existing === 'disagree' || existing === 'nuance' || existing === 'story' || existing === 'language') {
      setSelectedResponseKind(existing);
      return;
    }
    setSelectedResponseKind('nuance');
  }, [selectedDelta?.id, selectedDelta?.metadata]);

  useEffect(() => {
    setReflectionText(metadataText(selectedDelta?.metadata, 'owner_response_excerpt') ?? '');
    setReflectionState({ tone: 'idle', message: '' });
  }, [selectedDelta?.id, selectedDelta?.metadata]);

  useEffect(() => {
    setPromotionItemTargetOverrides({});
  }, [selectedDelta]);

  useEffect(() => {
    setRouteToMemory(false);
    setRouteToStandup(false);
    setRouteToPM(false);
    setShowTriageControls(true);
    setTriageMemoryTargets(['persistent_state']);
    setTriageWorkspaceKeys(suggestedWorkspaceKeys);
    setTriageStandupKind('auto');
    setTriagePMTitle(selectedDelta ? defaultBrainPMTitle(selectedDelta) : '');
    setTriageState({ tone: 'idle', message: '' });
  }, [selectedDelta, suggestedWorkspaceKeys]);

  async function postPromotionCommit(deltaId: string) {
    const response = await fetch(`${API_URL}/api/brain/persona-promote/${deltaId}`, {
      method: 'POST',
      headers: { 'Cache-Control': 'no-store' },
      cache: 'no-store',
    });
    const payload = (await response.json()) as BrainPromotionResponse | { detail?: string };
    if (!response.ok) {
      throw new Error((payload as { detail?: string }).detail || `Promotion failed with ${response.status}`);
    }
    return payload as BrainPromotionResponse;
  }

  async function commitPromotion(delta: PersonaDeltaEntry) {
    const gateSummary = summarizePromotionItems(readPromotionItemsFromMetadata(delta.metadata), metadataText(delta.metadata, 'target_file'));
    if (gateSummary.decision !== 'allow') {
      setPromotionState({
        tone: 'error',
        message:
          gateSummary.decision === 'block'
            ? gateSummary.reason || 'This queued item is blocked from canon until it has a real artifact/output anchor.'
            : gateSummary.reason || 'This queued item is held until the proof is stronger.',
      });
      return;
    }
    setPromotionState({ tone: 'idle', message: '' });
    setPromotingDeltaId(delta.id);
    try {
      const payload = await postPromotionCommit(delta.id);
      mergeUpdatedDelta(payload.delta);
      await refreshBrainData();
      setRecentlyQueuedDeltaId(null);
      setRecentlyCommittedDeltaId(delta.id);
      setLifecycleView('committed');
      setPromotionState({
        tone: 'success',
        message: formatPromotionSuccessMessage(payload.message, payload.committed_target_files, payload.bundle_written_files),
      });
      if (selectedDeltaId === delta.id) {
        setSelectedDeltaId(reviewQueue[0]?.id ?? '');
      }
    } catch (error) {
      setPromotionState({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to commit this promotion right now.',
      });
    } finally {
      setPromotingDeltaId(null);
    }
  }

  async function reroutePromotion(delta: PersonaDeltaEntry, targetFile: string) {
    setPromotionState({ tone: 'idle', message: '' });
    setReroutingDeltaId(delta.id);
    try {
      const response = await fetch(`${API_URL}/api/brain/persona-reroute/${delta.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_file: targetFile }),
      });
      const payload = (await response.json()) as BrainPromotionRerouteResponse | { detail?: string };
      if (!response.ok) {
        throw new Error((payload as { detail?: string }).detail || `Reroute failed with ${response.status}`);
      }
      mergeUpdatedDelta((payload as BrainPromotionRerouteResponse).delta);
      await refreshBrainData();
      setRecentlyQueuedDeltaId(delta.id);
      setRecentlyCommittedDeltaId(null);
      setLifecycleView('pending_promotion');
      setPromotionState({
        tone: 'success',
        message:
          (payload as BrainPromotionRerouteResponse).message ||
          `Queued promotion rerouted to ${humanizeTargetFileLabel(targetFile)}. Ready for canon commit.`,
      });
    } catch (error) {
      setPromotionState({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to reroute this promotion right now.',
      });
    } finally {
      setReroutingDeltaId(null);
    }
  }

  function setPromotionItemTarget(itemId: string, nextTarget: string) {
    setPromotionItemTargetOverrides((current) => {
      const updated = { ...current };
      updated[itemId] = nextTarget;
      return updated;
    });
  }

  function applyBulkPromotionTarget(nextTarget: string) {
    const targetIds = selectedPromotionItems.length > 0 ? selectedPromotionItems.map((item) => item.id) : selectableItems.map((item) => item.id);
    if (targetIds.length === 0) return;
    setPromotionItemTargetOverrides((current) => {
      const updated = { ...current };
      for (const itemId of targetIds) {
        updated[itemId] = nextTarget;
      }
      return updated;
    });
  }

  function resetBulkPromotionTargets() {
    const targetIds = selectedPromotionItems.length > 0 ? selectedPromotionItems.map((item) => item.id) : selectableItems.map((item) => item.id);
    if (targetIds.length === 0) return;
    setPromotionItemTargetOverrides((current) => {
      const updated = { ...current };
      for (const itemId of targetIds) {
        delete updated[itemId];
      }
      return updated;
    });
  }

  function queueTemplate(kind: 'agree' | 'disagree' | 'nuance' | 'story' | 'language') {
    if (!selectedDelta) {
      return;
    }
    setSelectedResponseKind(kind);
    const prefix =
      kind === 'agree'
        ? `What I agree with about "${selectedDelta.trait}":\n- `
        : kind === 'disagree'
        ? `What I disagree with about "${selectedDelta.trait}":\n- `
        : kind === 'nuance'
        ? `Nuance I want preserved for "${selectedDelta.trait}":\n- `
        : kind === 'story'
        ? `Personal story or example that should shape "${selectedDelta.trait}":\n- `
        : `Language and wording I prefer for "${selectedDelta.trait}":\n- `;
    setReflectionText((current) => (current.trim().length > 0 ? current : prefix));
    setReflectionState({ tone: 'idle', message: '' });
  }

  function seedSourceDecision(kind: 'not_useful' | 'source_only' | 'post_seed' | 'canon_candidate') {
    if (!selectedDelta) {
      return;
    }
    const subject = sourceTitle || selectedDelta.trait;
    const template =
      kind === 'not_useful'
        ? `Source judgment for "${subject}":\n- This depends on too much missing context to be useful for memory or canon right now.\n- Keep it out of canon.`
        : kind === 'source_only'
        ? `Source judgment for "${subject}":\n- There may be signal here, but it should stay source intelligence for now.\n- I do not want this treated as canon yet.`
        : kind === 'post_seed'
        ? `Source judgment for "${subject}":\n- This is more useful as a post seed or writing angle than a canon claim.\n- The idea I would keep is: `
        : `Source judgment for "${subject}":\n- This feels meaningful enough to keep beyond source intelligence.\n- What I would preserve is: `;
    setSelectedResponseKind(kind === 'not_useful' ? 'disagree' : 'nuance');
    setReflectionText((current) => (current.trim().length > 0 ? current : template));
    setReflectionState({ tone: 'idle', message: '' });
  }

  async function saveReflection(mode: 'reviewed' | 'approved' = 'reviewed', options: { routeAfterSave?: boolean } = {}) {
    const routeAfterSave = options.routeAfterSave ?? false;
    const trimmedReflection = reflectionText.trim();
    const effectivePromotionItems =
      mode === 'approved' && selectedPromotionItems.length === 0 && recommendedSelectableItems.length > 0
        ? recommendedSelectableItems
        : selectedPromotionItems;
    const effectiveReflection =
      trimmedReflection ||
      savedResponseExcerpt ||
      (mode === 'approved' && effectivePromotionItems.length > 0
        ? `Approved canon fragments from "${sourceTitle || selectedDelta?.trait || 'this source'}".`
        : '');
    const keepSelectableSourceOpen = mode === 'reviewed' && selectableItems.length > 0 && !routeAfterSave;
    const effectivePromotionTargetFiles = Array.from(
      new Set(effectivePromotionItems.map((item) => item.targetFile).filter((value): value is string => Boolean(value))),
    );
    const effectivePromotionGate = summarizePromotionItems(effectivePromotionItems, targetFile);
    if (mode === 'approved' && effectivePromotionItems.length === 0) {
      setReflectionState({ tone: 'error', message: 'No promotion-ready fragments are selected yet.' });
      return;
    }
    if (!trimmedReflection && mode === 'reviewed' && !routeAfterSave) {
      setReflectionState({ tone: 'error', message: 'Add a thought before saving it to memory.' });
      return;
    }
    if (!effectiveReflection && mode === 'approved') {
      setReflectionState({ tone: 'error', message: 'Add a short note or pick canon fragments before finalizing this review.' });
      return;
    }
    if (routeAfterSave) {
      const routeError = validateRoutingSelection(effectiveReflection, effectivePromotionItems);
      if (routeError) {
        setReflectionState({ tone: 'error', message: routeError });
        setTriageState({ tone: 'error', message: routeError });
        return;
      }
    }

    setIsSavingReflection(true);
    if (routeAfterSave) {
      setIsRoutingSignal(true);
    }
    setReflectionState({ tone: 'idle', message: '' });
    try {
      let canonOutcome: 'none' | 'queued' | 'committed' = 'none';
      let routeOutcomeMessage = '';
      let routeFailureMessage = '';
      const payload = {
        text: buildReflectionCaptureText({
          delta: selectedDelta,
          reflectionText: effectiveReflection,
          targetFile: effectivePromotionTargetFiles[0] ?? targetFile,
          sectionContent: targetSection?.content ?? null,
          selectedItems: effectivePromotionItems,
        }),
        source: 'persona_reflection',
        topics: buildReflectionTopics(selectedDelta, effectivePromotionTargetFiles[0] ?? targetFile, effectivePromotionItems),
        importance: 3,
        metadata: {
          capture_kind: 'persona_reflection',
          origin: 'brain.persona.ui',
          owner_response_kind: selectedResponseKind,
          linked_delta_id: selectedDelta?.id ?? null,
          linked_capture_id: selectedDelta?.capture_id ?? null,
          persona_target: selectedDelta?.persona_target ?? null,
          target_file: effectivePromotionTargetFiles.length === 1 ? effectivePromotionTargetFiles[0] : targetFile,
          trait: selectedDelta?.trait ?? null,
          reference_pack: linkedPack?.key ?? null,
          input_mode: 'text',
          selected_promotion_items: effectivePromotionItems,
        },
      };

      const response = await fetch(`${API_URL}/api/capture/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Capture save failed with ${response.status}`);
      }
      const result = (await response.json()) as CaptureResponsePayload;
      if (selectedDelta) {
        const reviewPayload = {
          mode,
          response_kind: selectedResponseKind,
          resolution_capture_id: result.capture_id,
          reflection_excerpt: effectiveReflection.slice(0, 4000),
          selected_promotion_items: effectivePromotionItems,
        };
        const reviewResponse = await fetch(`${API_URL}/api/brain/persona-review/${selectedDelta.id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(reviewPayload),
        });
        if (!reviewResponse.ok) {
          const detail = await reviewResponse.text();
          throw new Error(detail || `Persona review update failed with ${reviewResponse.status}`);
        }
        const updatedDelta = (await reviewResponse.json()) as PersonaDeltaEntry;
        mergeUpdatedDelta(updatedDelta);
        if (mode === 'approved') {
          setSelectedPromotionItemIds(effectivePromotionItems.map((item) => item.id));
          if (effectivePromotionGate.decision === 'allow') {
            try {
              const committed = await postPromotionCommit(updatedDelta.id);
              mergeUpdatedDelta(committed.delta);
              setRecentlyQueuedDeltaId(null);
              setRecentlyCommittedDeltaId(committed.delta.id);
              setLifecycleView('committed');
              setPromotionState({
                tone: 'success',
                message: formatPromotionSuccessMessage(committed.message, committed.committed_target_files, committed.bundle_written_files),
              });
              canonOutcome = 'committed';
            } catch (promoteError) {
              setRecentlyQueuedDeltaId(updatedDelta.id);
              setRecentlyCommittedDeltaId(null);
              setLifecycleView('pending_promotion');
              setPromotionState({
                tone: 'error',
                message:
                  promoteError instanceof Error
                    ? `Your canon selection was saved, but committing to canon failed: ${promoteError.message}`
                    : 'Your canon selection was saved, but committing to canon failed.',
              });
              canonOutcome = 'queued';
            }
          } else {
            setRecentlyQueuedDeltaId(updatedDelta.id);
            setRecentlyCommittedDeltaId(null);
            setLifecycleView('pending_promotion');
            setPromotionState({
              tone: 'success',
              message: `Saved canon selection for ${describePromotionTargets(effectivePromotionItems, targetFile)}. ${effectivePromotionGate.reason || 'Held until the proof is strong enough to commit.'}`,
            });
            canonOutcome = 'queued';
          }
        } else {
          setPromotionState({ tone: 'idle', message: '' });
          setRecentlyQueuedDeltaId(null);
          setRecentlyCommittedDeltaId(null);
        }
        if (routeAfterSave) {
          try {
            const { result: routeResult, message } = await submitRouteForDelta(updatedDelta.id, effectiveReflection, effectivePromotionItems);
            mergeUpdatedDelta(routeResult.delta);
            routeOutcomeMessage = message;
            setTriageState({ tone: 'success', message });
          } catch (routeError) {
            routeFailureMessage =
              routeError instanceof Error ? routeError.message : 'Unable to route this reviewed signal right now.';
            setTriageState({
              tone: 'error',
              message: routeFailureMessage,
            });
          }
        }
      }
      const nextQueue = selectedDelta ? reviewQueue.filter((delta) => delta.id !== selectedDelta.id) : reviewQueue;
      await refreshBrainData();
      if (selectedDelta && !keepSelectableSourceOpen) {
        setCompletedDeltaIds((current) => (current.includes(selectedDelta.id) ? current : [...current, selectedDelta.id]));
      }
      setSelectedDeltaId(keepSelectableSourceOpen ? selectedDelta?.id ?? '' : nextQueue[0]?.id ?? '');
      setReflectionText('');
      const baseMessage = keepSelectableSourceOpen
        ? `Saved to Open Brain as capture ${result.capture_id}. This source stays open so you can select canonical items when ready.`
        : nextQueue[0]
        ? mode === 'approved'
          ? canonOutcome === 'committed'
            ? `Saved to Open Brain as capture ${result.capture_id} and wrote ${effectivePromotionItems.length} selected item${effectivePromotionItems.length === 1 ? '' : 's'} into canon. Moving to the next review item.`
            : `Saved to Open Brain as capture ${result.capture_id} and saved ${effectivePromotionItems.length} selected item${effectivePromotionItems.length === 1 ? '' : 's'} as a canon selection. Moving to the next review item.`
          : `Saved to Open Brain as capture ${result.capture_id}. Moving to the next review item.`
        : mode === 'approved'
        ? canonOutcome === 'committed'
          ? `Saved to Open Brain as capture ${result.capture_id} and wrote ${effectivePromotionItems.length} selected item${effectivePromotionItems.length === 1 ? '' : 's'} into canon. You are done for now.`
          : `Saved to Open Brain as capture ${result.capture_id} and saved ${effectivePromotionItems.length} selected item${effectivePromotionItems.length === 1 ? '' : 's'} as a canon selection. You are done for now.`
        : `Saved to Open Brain as capture ${result.capture_id}. You are done for now.`;
      setReflectionState({
        tone: routeFailureMessage ? 'error' : 'success',
        message: routeAfterSave
          ? `${baseMessage} ${routeFailureMessage ? `Review saved, but routing failed: ${routeFailureMessage}` : routeOutcomeMessage || 'Routing completed in the same action.'}`
          : baseMessage,
      });
    } catch (saveError) {
      setReflectionState({
        tone: 'error',
        message: saveError instanceof Error ? saveError.message : 'Unable to save reflection right now.',
      });
    } finally {
      setIsSavingReflection(false);
      if (routeAfterSave) {
        setIsRoutingSignal(false);
      }
    }
  }

  function toggleMemoryTarget(target: string) {
    setTriageMemoryTargets((current) => (current.includes(target) ? current.filter((entry) => entry !== target) : [...current, target]));
    setTriageState({ tone: 'success', message: `Canonical memory target updated: ${humanizeCanonicalMemoryTarget(target)}.` });
  }

  function toggleTriageWorkspace(target: string) {
    setTriageWorkspaceKeys((current) => {
      if (current.includes(target)) {
        return current.length === 1 ? current : current.filter((entry) => entry !== target);
      }
      return [...current, target];
    });
    setTriageState({ tone: 'success', message: `Workspace routing updated: ${labelForBrainWorkspace(target)}.` });
  }

  function toggleRouteTarget(route: 'memory' | 'standup' | 'pm') {
    setShowTriageControls(true);
    if (route === 'memory') {
      const next = !routeToMemory;
      setRouteToMemory(next);
      setTriageState({ tone: 'success', message: `Canonical memory route ${next ? 'enabled' : 'disabled'}.` });
      return;
    }
    if (route === 'standup') {
      const next = !routeToStandup;
      setRouteToStandup(next);
      setTriageState({ tone: 'success', message: `Standup queue route ${next ? 'enabled' : 'disabled'}.` });
      return;
    }
    const next = !routeToPM;
    setRouteToPM(next);
    setTriageState({ tone: 'success', message: `PM queue route ${next ? 'enabled' : 'disabled'}.` });
  }

  function applyTriagePreset(preset: (typeof brainTriagePresetOptions)[number]['key']) {
    setShowTriageControls(true);
    if (preset === 'canon_only') {
      setRouteToMemory(true);
      setRouteToStandup(false);
      setRouteToPM(false);
      setTriageMemoryTargets(['persistent_state', 'learnings']);
      setTriageState({ tone: 'success', message: 'Preset applied: Canon + Memory.' });
      return;
    }
    if (preset === 'executive_review') {
      setRouteToMemory(true);
      setRouteToStandup(true);
      setRouteToPM(false);
      setTriageWorkspaceKeys(['shared_ops']);
      setTriageStandupKind('executive_ops');
      setTriageMemoryTargets(['persistent_state', 'chronicle']);
      setTriageState({ tone: 'success', message: 'Preset applied: Executive Review.' });
      return;
    }
    if (preset === 'workspace_followup') {
      const workspaceKeys =
        triageWorkspaceSelection.length === 1 && triageWorkspaceSelection[0] === 'shared_ops'
          ? suggestedWorkspaceKeys
          : triageWorkspaceSelection;
      setRouteToMemory(true);
      setRouteToStandup(true);
      setRouteToPM(true);
      setTriageWorkspaceKeys(workspaceKeys);
      setTriageStandupKind('auto');
      setTriageMemoryTargets(['chronicle', 'learnings']);
      if (selectedDelta) {
        setTriagePMTitle(defaultBrainPMTitle(selectedDelta));
      }
      setTriageState({
        tone: 'success',
        message: `Preset applied: Workspace Follow-Up (${workspaceKeys.map(labelForBrainWorkspace).join(', ')}).`,
      });
      return;
    }
    setRouteToMemory(false);
    setRouteToStandup(false);
    setRouteToPM(true);
    if (selectedDelta) {
      setTriagePMTitle(defaultBrainPMTitle(selectedDelta));
    }
    setTriageState({ tone: 'success', message: 'Preset applied: PM Only.' });
  }

  function validateRoutingSelection(effectiveReflection: string, promotionItems: PromotionItem[] = selectedPromotionItems) {
    if (!effectiveReflection && promotionItems.length === 0) {
      return 'Add a short reflection or select canonical fragments before routing this signal.';
    }
    if (!routeToMemory && !routeToStandup && !routeToPM) {
      return 'Select at least one route target.';
    }
    if (routeToMemory && triageMemoryTargets.length === 0) {
      return 'Choose at least one canonical memory target.';
    }
    return null;
  }

  function buildRouteResultMessage(result: BrainSystemRouteResponse) {
    const routeBits: string[] = [];
    if (result.canonical_memory_targets_queued?.length) {
      routeBits.push(`queued for ${result.canonical_memory_targets_queued.map(humanizeCanonicalMemoryTarget).join(', ')}`);
    }
    if ((result.routes || []).some((entry) => entry.standup?.id) || result.standup?.id) {
      routeBits.push(`standup queued for ${triageWorkspaceSelection.length} workspace${triageWorkspaceSelection.length === 1 ? '' : 's'}`);
    }
    if ((result.routes || []).some((entry) => entry.pm_card?.id) || result.pm_card?.id) {
      routeBits.push(`PM work created for ${triageWorkspaceSelection.length} workspace${triageWorkspaceSelection.length === 1 ? '' : 's'}`);
    }
    return routeBits.length > 0
      ? `Brain routed this signal to ${triageWorkspaceSelection.map(labelForBrainWorkspace).join(', ')}: ${routeBits.join(' · ')}.`
      : result.message || 'Brain triage updated.';
  }

  async function submitRouteForDelta(deltaId: string, effectiveReflection: string, promotionItems: PromotionItem[] = selectedPromotionItems) {
    const response = await fetch(`${API_URL}/api/brain/system-route/${deltaId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reflection_excerpt: effectiveReflection || null,
        selected_promotion_items: promotionItems,
        workspace_key: triageWorkspaceSelection[0] ?? 'shared_ops',
        workspace_keys: triageWorkspaceSelection,
        canonical_memory_targets: routeToMemory ? triageMemoryTargets : [],
        route_to_standup: routeToStandup,
        standup_kind: triageStandupKind,
        route_to_pm: routeToPM,
        pm_title: routeToPM ? triagePMTitle || defaultBrainPMTitle(selectedDelta) : null,
      }),
    });
    const payload = (await response.json()) as BrainSystemRouteResponse | { detail?: string };
    if (!response.ok) {
      throw new Error((payload as { detail?: string }).detail || 'Unable to route this reviewed signal.');
    }
    const result = payload as BrainSystemRouteResponse;
    return {
      result,
      message: buildRouteResultMessage(result),
    };
  }

  async function routeSelectedSignal() {
    if (!selectedDelta) {
      setTriageState({ tone: 'error', message: 'Choose a review item before routing it.' });
      return;
    }
    const effectiveReflection = reflectionText.trim() || savedResponseExcerpt || '';
    const routeError = validateRoutingSelection(effectiveReflection);
    if (routeError) {
      setTriageState({ tone: 'error', message: routeError });
      return;
    }

    setIsRoutingSignal(true);
    setTriageState({ tone: 'idle', message: '' });
    try {
      const { result, message } = await submitRouteForDelta(selectedDelta.id, effectiveReflection, selectedPromotionItems);
      mergeUpdatedDelta(result.delta);
      await refreshBrainData();
      setTriageState({
        tone: 'success',
        message,
      });
    } catch (routeError) {
      setTriageState({
        tone: 'error',
        message: routeError instanceof Error ? routeError.message : 'Unable to route this reviewed signal right now.',
      });
    } finally {
      setIsRoutingSignal(false);
    }
  }

  async function finalizeReviewedSignal() {
    if (!selectedDelta) {
      setReflectionState({ tone: 'error', message: 'Choose a review item before finalizing it.' });
      return;
    }
    if (!hasRouteTargets && canonActionItems.length === 0) {
      setReflectionState({
        tone: 'error',
        message: 'Choose canon fragments or a route target before finalizing. Use Save note if you only want to store your judgment.',
      });
      return;
    }
    await saveReflection(canonActionItems.length > 0 ? 'approved' : 'reviewed', {
      routeAfterSave: hasRouteTargets,
    });
  }

  return (
    <section
      style={{
        display: 'grid',
        gap: '16px',
        height: personaViewportHeight,
        minHeight: 0,
        gridTemplateRows: personaSectionRows,
      }}
    >
      <section
        style={{
          borderRadius: '18px',
          border: '1px solid #1f2937',
          backgroundColor: '#050b19',
          padding: compactPersonaChrome ? '14px' : '18px',
          display: 'grid',
          gap: compactPersonaChrome ? '10px' : '12px',
          alignItems: 'start',
          minHeight: usePinnedPersonaViewport ? 'calc(100vh - 162px)' : 0,
          overflowX: 'hidden',
          overflowY: usePinnedPersonaViewport ? 'auto' : 'visible',
          gridTemplateRows: activeReviewRows,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: compactPersonaChrome ? '10px' : '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ maxWidth: compactPersonaChrome ? '900px' : '760px' }}>
            <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Active Review</p>
            <h2 style={{ color: 'white', fontSize: compactPersonaChrome ? '24px' : '28px', margin: '4px 0 6px' }}>{reviewHeadline}</h2>
            <p style={{ color: '#94a3b8', fontSize: compactPersonaChrome ? '13px' : '14px', lineHeight: 1.6, margin: 0 }}>
              {selectedDelta
                ? `${pendingCount} primary review item${pendingCount === 1 ? '' : 's'} remaining${mutedCount > 0 ? `, plus ${mutedCount} muted long-form item${mutedCount === 1 ? '' : 's'}` : ''}.`
                : 'No pending reviews right now.'}
            </p>
          </div>
          {!compactPersonaChrome && (
            <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right', maxWidth: '360px' }}>
              Workspace approvals already count as saved. Brain is where you resolve unresolved items, add nuance, and decide what should become canon without auto-rewriting the bundle.
            </div>
          )}
        </div>

        {compactPersonaChrome ? (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <InlineBadge label="1 Choose review item" tone="#38bdf8" />
            <InlineBadge label="2 Review source" tone="#22c55e" />
            <InlineBadge label="3 Save or route" tone="#818cf8" />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: stackPersonaShell ? 'minmax(0, 1fr)' : 'repeat(3, minmax(0, 1fr))', gap: '8px' }}>
            <StepCallout step="1" title="Choose item" description="Pick one review item from the left rail." />
            <StepCallout step="2" title="Review source" description="Start with the source itself and its surrounding context before you decide on routing." />
            <StepCallout step="3" title="Save your take" description="Record agreement, disagreement, nuance, story, or wording. Queue promotion only if fragments deserve canon." />
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <ReviewMetaChip label="Active" value={String(totalPendingCount)} tone="#38bdf8" />
          <ReviewMetaChip label="Promotion Ready" value={String(promotionReadyCount)} tone="#f59e0b" />
          <ReviewMetaChip label="Queued" value={String(pendingPromotionDeltas.length)} tone="#f59e0b" />
          <ReviewMetaChip label="History" value={String(resolvedHistoryDeltas.length + workspaceSavedDeltas.length + committedDeltas.length)} tone="#64748b" />
        </div>

        {selectedDelta ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: stackPersonaShell ? 'minmax(0, 1fr)' : '340px minmax(0, 1fr)',
              gap: '14px',
              alignItems: 'stretch',
              height: '100%',
              minHeight: 0,
              overflow: 'hidden',
            }}
          >
            <aside
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '14px',
                display: 'grid',
                gap: '12px',
                alignSelf: 'stretch',
                height: '100%',
                minHeight: 0,
                overflow: 'hidden',
                gridTemplateRows: 'auto auto minmax(0, 1fr)',
              }}
            >
              <div>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Step 1 · Choose review item</p>
                <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                  Newest items appear first. Muted long-form fragments stay out of the way unless you choose to inspect them.
                </p>
              </div>
              {primaryActiveReviewDeltas.length > 0 && mutedActiveReviewDeltas.length > 0 && (
                <div
                  style={{
                    display: 'grid',
                    gap: '8px',
                    padding: '10px 12px',
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#010617',
                  }}
                >
                  <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                    {mutedCount} lower-confidence long-form item{mutedCount === 1 ? '' : 's'} muted by default.
                  </p>
                  <button
                    onClick={() => setShowMutedActive((current) => !current)}
                    style={{
                      borderRadius: '999px',
                      border: '1px solid #334155',
                      backgroundColor: showMutedActive ? '#0f172a' : '#020617',
                      color: '#cbd5f5',
                      padding: '8px 12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      justifySelf: 'start',
                    }}
                  >
                    {showMutedActive ? `Hide muted (${mutedCount})` : `Show muted (${mutedCount})`}
                  </button>
                </div>
              )}
              <div style={{ minHeight: 0, overflowY: 'auto', display: 'grid', gap: '10px', paddingRight: '2px' }}>
                {visibleActiveReviewDeltas.map(({ delta, muted, promotionReady }) => {
                  const isActive = delta.id === (selectedDelta?.id ?? '');
                  return (
                    <button
                      key={delta.id}
                      onClick={() => setSelectedDeltaId(delta.id)}
                      style={{
                        textAlign: 'left',
                        borderRadius: '14px',
                        border: `1px solid ${isActive ? '#38bdf8' : '#1f2937'}`,
                        backgroundColor: isActive ? '#082f49' : '#020617',
                        padding: '12px',
                        cursor: 'pointer',
                      }}
                    >
                      <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600, marginBottom: '6px', lineHeight: 1.45 }}>
                        {truncateText(reviewQueueCardTitle(delta), 110)}
                      </p>
                      <p style={{ color: '#cbd5f5', fontSize: '12px', marginBottom: '8px', lineHeight: 1.55 }}>
                        {truncateText(reviewQueueCardSummary(delta), 120)}
                      </p>
                      <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>{metadataText(delta.metadata, 'target_file') ?? 'Target file not assigned'}</p>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                        {isActive && <InlineBadge label="selected" tone="#38bdf8" />}
                        <InlineBadge label={humanizeBeliefRelation(metadataText(delta.metadata, 'belief_relation'))} tone="#22c55e" />
                        {promotionReady && <InlineBadge label="promotion-ready" tone="#f59e0b" />}
                        {muted && <InlineBadge label="muted" tone="#64748b" />}
                      </div>
                      <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {formatTimestamp(delta.created_at)}
                      </p>
                    </button>
                  );
                })}
              </div>
            </aside>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: stackPersonaDetail ? 'minmax(0, 1fr)' : 'minmax(0, 1.08fr) minmax(420px, 0.92fr)',
                gap: '14px',
                alignItems: 'stretch',
                height: '100%',
                minHeight: 0,
                overflow: 'hidden',
              }}
            >
            <section
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: compactPersonaChrome ? '14px' : '16px',
                display: 'grid',
                gap: '12px',
                alignSelf: 'stretch',
                minWidth: 0,
                minHeight: 0,
                overflowX: 'hidden',
                overflowY: usePinnedPersonaViewport ? 'auto' : 'visible',
                gridTemplateRows: 'auto auto auto minmax(0, 1fr)',
              }}
            >
              <div>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Step 2 · Review source first</p>
                <p style={{ color: '#cbd5f5', fontSize: '18px', fontWeight: 600, lineHeight: 1.45, margin: '0 0 8px' }}>{sourceTitle}</p>
                <p style={{ color: '#94a3b8', fontSize: compactPersonaChrome ? '13px' : '14px', lineHeight: 1.6, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word', margin: 0 }}>
                  {compactPersonaChrome ? truncateText(reviewReason, 260) : reviewReason}
                </p>
              </div>

              <div style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.6, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                {sourceChannel && (
                  <>
                    <span>Source channel: {sourceChannel}</span>
                    <span style={{ margin: '0 8px' }}>·</span>
                  </>
                )}
                {primaryRoute && (
                  <>
                    <span>Best first move: {humanizePrimaryRoute(primaryRoute)}</span>
                    <span style={{ margin: '0 8px' }}>·</span>
                  </>
                )}
                <span>{evidenceLabel}</span>
                {selectedPromotionTargetFiles.length > 0 && (
                  <>
                    <span style={{ margin: '0 8px' }}>·</span>
                    <span>Selected targets: {describePromotionTargets(selectedPromotionItems, suggestedTargetFile)}</span>
                  </>
                )}
                <span style={{ margin: '0 8px' }}>·</span>
                <span>{statusLabel}</span>
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {sourceChannel && <InlineBadge label={sourceChannel} tone="#64748b" />}
                {reviewSource === 'long_form_media.segment' && <InlineBadge label="Source-first review" tone="#38bdf8" />}
                {primaryRoute && <InlineBadge label={humanizePrimaryRoute(primaryRoute)} tone="#22c55e" />}
                <InlineBadge
                  label={selectedScoredDelta?.promotionReady ? 'Promotion-ready path open' : 'Needs review before promotion'}
                  tone={selectedScoredDelta?.promotionReady ? '#f59e0b' : '#38bdf8'}
                />
                <InlineBadge
                  label={
                    weakSourceFragment
                      ? 'No canon fragments yet'
                      : `${selectableItems.length} optional fragment${selectableItems.length === 1 ? '' : 's'}`
                  }
                  tone={!weakSourceFragment && selectableItems.length > 0 ? '#818cf8' : '#64748b'}
                />
                {selectedScoredDelta?.muted && <InlineBadge label="Muted long-form item" tone="#64748b" />}
                {selectedScoredDelta && <InlineBadge label={`Priority ${selectedScoredDelta.score}`} tone="#22c55e" />}
              </div>

              <div style={{ minHeight: 0, overflowY: 'auto', paddingRight: '4px' }}>
                <div
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#010617',
                    padding: '12px',
                    marginBottom: '14px',
                    display: 'grid',
                    gap: '12px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Source excerpt</p>
                      <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.6, margin: 0, whiteSpace: 'pre-wrap' }}>
                        {sourceExcerpt ? truncateText(sourceExcerpt, compactPersonaChrome ? 340 : 520) : 'No clean excerpt is attached to this review item yet.'}
                      </p>
                    </div>
                    {sourceUrl && (
                      <a href={sourceUrl} target="_blank" rel="noreferrer" style={{ ...brainLinkButtonStyle, justifySelf: 'start', whiteSpace: 'nowrap' }}>
                        Open source
                      </a>
                    )}
                  </div>
                  <div style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px 12px' }}>
                    <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 6px' }}>Decision prompt</p>
                    <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.6, margin: 0 }}>{reviewAsk}</p>
                  </div>
                  {selectedDelta.trait && selectedDelta.trait !== sourceExcerpt && (
                    <div style={{ borderRadius: '12px', border: '1px solid #312e81', backgroundColor: '#1e1b4b22', padding: '10px 12px' }}>
                      <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>System claim candidate</p>
                      <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{selectedDelta.trait}</p>
                    </div>
                  )}
                  {((beliefSummary || experienceAnchor || experienceSummary || routeReason || primaryRoute || routeOptions.length > 0 || suggestedTargetFile) ||
                    (sourceContextExcerpt && sourceContextExcerpt !== sourceExcerpt) ||
                    talkingPoints.length > 0) && (
                    <details>
                      <summary style={{ color: '#38bdf8', fontSize: '12px', cursor: 'pointer', margin: 0 }}>System context and routing hints</summary>
                      <div style={{ marginTop: '12px', display: 'grid', gap: '10px' }}>
                        {(beliefSummary || primaryRoute || routeOptions.length > 0 || suggestedTargetFile || experienceAnchor || routeReason) && (
                          <div
                            style={{
                              display: 'grid',
                              gridTemplateColumns: viewportWidth >= 1500 ? 'repeat(3, minmax(0, 1fr))' : viewportWidth >= 1180 ? 'repeat(2, minmax(0, 1fr))' : 'minmax(0, 1fr)',
                              gap: '8px',
                            }}
                          >
                            {(primaryRoute || routeOptions.length > 0) && (
                              <div style={{ borderRadius: '10px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px' }}>
                                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 4px' }}>
                                  Possible next moves
                                </p>
                                <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                                  {[primaryRoute ? humanizePrimaryRoute(primaryRoute) : null, ...routeOptions.map((value) => humanizePrimaryRoute(value))]
                                    .filter(Boolean)
                                    .join(' · ')}
                                </p>
                              </div>
                            )}
                            {suggestedTargetFile && (
                              <div style={{ borderRadius: '10px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px' }}>
                                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 4px' }}>
                                  Possible canon destination
                                </p>
                                <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                                  {humanizeTargetFileLabel(suggestedTargetFile)}
                                </p>
                              </div>
                            )}
                            {beliefSummary && (
                              <div style={{ borderRadius: '10px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px' }}>
                                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 4px' }}>System hypothesis</p>
                                <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{beliefSummary}</p>
                              </div>
                            )}
                            {(experienceAnchor || experienceSummary) && (
                              <div style={{ borderRadius: '10px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px' }}>
                                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 4px' }}>
                                  Experience anchor
                                </p>
                                <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                                  {experienceAnchor || experienceSummary}
                                </p>
                              </div>
                            )}
                            {routeReason && (
                              <div style={{ borderRadius: '10px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px' }}>
                                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 4px' }}>
                                  Why it was flagged
                                </p>
                                <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{routeReason}</p>
                              </div>
                            )}
                          </div>
                        )}
                        {sourceContextExcerpt && sourceContextExcerpt !== sourceExcerpt && (
                          <div>
                            <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>
                              Surrounding source context
                            </p>
                            <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.6, margin: 0, whiteSpace: 'pre-wrap' }}>
                              {truncateText(sourceContextExcerpt, 760)}
                            </p>
                            {(sourceContextBefore.length > 0 || sourceContextAfter.length > 0) && (
                              <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.55, margin: '8px 0 0' }}>
                                {sourceContextBefore.length > 0 && `Earlier lines: ${sourceContextBefore.length}. `}
                                {sourceContextAfter.length > 0 && `Later lines: ${sourceContextAfter.length}.`}
                              </p>
                            )}
                          </div>
                        )}
                        {talkingPoints.length > 0 && (
                          <div>
                            <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>
                              Additional source fragments
                            </p>
                            <div style={{ display: 'grid', gap: '6px' }}>
                              {talkingPoints.map((point) => (
                                <p key={point} style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                                  - {truncateText(point, 220)}
                                </p>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                  )}
                </div>
                <details style={{ marginBottom: '16px' }}>
                  <summary style={{ color: '#38bdf8', fontSize: '12px', cursor: 'pointer', marginBottom: '8px' }}>Raw review packet</summary>
                  <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.7, whiteSpace: 'pre-wrap', margin: '12px 0 0' }}>
                    {selectedDelta.notes || 'No candidate notes were attached to this review item.'}
                  </p>
                </details>
                {selectableItems.length > 0 && (
                  <div
                    style={{
                      marginBottom: '16px',
                      maxHeight: usePinnedPersonaViewport ? '260px' : '330px',
                      overflowY: 'auto',
                      paddingRight: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'baseline', marginBottom: '10px', flexWrap: 'wrap' }}>
                      <p style={{ color: '#818cf8', fontSize: '13px', fontWeight: 700, margin: 0 }}>
                        Optional canon fragments
                      </p>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <InlineBadge label={`${selectedPromotionItems.length} selected`} tone="#818cf8" />
                        <InlineBadge label={`${displaySelectableItems.length} shown`} tone="#64748b" />
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                      <button
                        type="button"
                        onClick={() => setPromotionFragmentView('recommended')}
                        style={triageChoiceButtonStyle(promotionFragmentView === 'recommended')}
                      >
                        Recommended ({recommendedSelectableItems.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setPromotionFragmentView('needs_work')}
                        style={triageChoiceButtonStyle(promotionFragmentView === 'needs_work')}
                      >
                        Needs work ({needsWorkSelectableItems.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setPromotionFragmentView('all')}
                        style={triageChoiceButtonStyle(promotionFragmentView === 'all')}
                      >
                        All ({rankedSelectableItems.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedPromotionItemIds(recommendedSelectableItems.map((item) => item.id))}
                        style={triageChoiceButtonStyle(false)}
                      >
                        Select recommended
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedPromotionItemIds([])}
                        style={triageChoiceButtonStyle(false)}
                      >
                        Clear selection
                      </button>
                    </div>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: viewportWidth >= 1180 ? 'repeat(2, minmax(0, 1fr))' : 'minmax(0, 1fr)',
                        gap: '10px',
                      }}
                    >
                      {displaySelectableItems.map((item) => {
                        const checked = selectedPromotionItemIds.includes(item.id);
                        const suggestedTarget = bestTargetForPromotionItem(item, targetFile);
                        return (
                          <div
                            key={item.id}
                            style={{
                              width: '100%',
                              display: 'block',
                              borderRadius: '12px',
                              border: `1px solid ${checked ? '#38bdf8' : '#1f2937'}`,
                              backgroundColor: checked ? '#082f49' : '#020617',
                              padding: '10px 12px',
                              cursor: 'pointer',
                              boxSizing: 'border-box',
                            }}
                          >
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  setSelectedPromotionItemIds((current) =>
                                    current.includes(item.id) ? current.filter((entry) => entry !== item.id) : [...current, item.id],
                                  );
                                  if (reflectionState.tone !== 'idle') {
                                    setReflectionState({ tone: 'idle', message: '' });
                                  }
                                }}
                                style={{
                                  width: '16px',
                                  height: '16px',
                                  marginTop: '2px',
                                  accentColor: '#38bdf8',
                                  cursor: 'pointer',
                                }}
                              />
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', marginBottom: '6px', flexWrap: 'wrap' }}>
                                  <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600, overflowWrap: 'anywhere', wordBreak: 'break-word', margin: 0 }}>
                                    {item.label}
                                  </p>
                                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                    <InlineBadge label={humanizePromotionKind(item.kind)} tone="#64748b" />
                                    <InlineBadge
                                      label={`Best fit: ${humanizeTargetFileLabel(suggestedTarget)}`}
                                      tone={suggestedTarget === item.targetFile ? '#38bdf8' : '#818cf8'}
                                    />
                                    <InlineBadge label={humanizeGateDecision(resolvePromotionGate(item, targetFile).decision)} tone={gateDecisionTone(resolvePromotionGate(item, targetFile).decision)} />
                                    <InlineBadge label={`proof ${item.proofStrength}`} tone={proofStrengthTone(item.proofStrength)} />
                                  </div>
                                </div>
                                <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5, overflowWrap: 'anywhere', wordBreak: 'break-word', margin: 0 }}>{item.content}</p>
                                {item.artifactSummary && (
                                  <p style={{ color: '#94a3b8', fontSize: '12px', margin: '6px 0 0', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                                    Artifact: {item.artifactSummary}
                                  </p>
                                )}
                                {item.evidence && <p style={{ color: '#64748b', fontSize: '12px', margin: '6px 0 0', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>Evidence: {item.evidence}</p>}
                                {resolvePromotionGate(item, targetFile).reason && (
                                  <p style={{ color: gateDecisionTone(resolvePromotionGate(item, targetFile).decision), fontSize: '12px', margin: '6px 0 0', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                                    {resolvePromotionGate(item, targetFile).reason}
                                  </p>
                                )}
                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' }}>
                                  {candidateTargetsForPromotionItem(item, targetFile).map((choice) => {
                                    const active = choice === item.targetFile;
                                    return (
                                      <button
                                        key={choice}
                                        type="button"
                                        onClick={(event) => {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          setPromotionItemTarget(item.id, choice);
                                        }}
                                        style={{
                                          borderRadius: '999px',
                                          border: active ? '1px solid #38bdf8' : '1px solid #334155',
                                          backgroundColor: active ? '#082f49' : '#020617',
                                          color: active ? '#f8fafc' : '#cbd5f5',
                                          padding: '6px 10px',
                                          fontSize: '11px',
                                          fontWeight: 600,
                                          cursor: 'pointer',
                                        }}
                                      >
                                        {humanizeTargetFileLabel(choice)}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {displaySelectableItems.length === 0 && (
                      <p style={{ color: '#64748b', fontSize: '12px', margin: '10px 0 0' }}>
                        No fragments match this filter yet. Switch to `All` to inspect everything.
                      </p>
                    )}
                  </div>
                )}
                <details>
                  <summary style={{ color: '#818cf8', cursor: 'pointer', fontSize: '13px', fontWeight: 600, marginBottom: '12px' }}>
                    Compare against current canon (optional)
                  </summary>
                  <div style={{ marginTop: '12px' }}>
                    {activeContext ? (
                      <>
                        <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{activeContextPath ?? 'Canonical bundle excerpt'}</p>
                        <pre style={{ margin: 0, color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, whiteSpace: 'pre-wrap', fontFamily: 'inherit', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                          {truncateText(activeContext, 2200)}
                        </pre>
                      </>
                    ) : (
                      <p style={{ color: '#475569', fontSize: '13px', lineHeight: 1.55 }}>
                        There is no canonical excerpt attached yet. Use your response to say where this belongs and how it should be phrased.
                      </p>
                    )}
                  </div>
                </details>
              </div>
            </section>

            <section
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: compactPersonaChrome ? '14px' : '16px',
                display: 'grid',
                gap: '12px',
                alignSelf: 'stretch',
                minWidth: 0,
                minHeight: 0,
                overflowX: 'hidden',
                overflowY: usePinnedPersonaViewport ? 'auto' : 'visible',
                gridTemplateRows: compactPersonaChrome ? 'auto auto auto minmax(180px, 1fr) auto' : 'auto auto auto auto minmax(140px, 1fr) auto',
              }}
            >
              <div
                style={{
                  borderRadius: '12px',
                  border: '1px solid #1f2937',
                  backgroundColor: '#010617',
                  padding: compactPersonaChrome ? '12px' : '14px',
                  display: 'grid',
                  gap: compactPersonaChrome ? '9px' : '10px',
                }}
              >
                <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Step 3 · Save and route</p>
                {!compactPersonaChrome && (
                  <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.6, margin: 0 }}>
                    Decide whether this source is worth keeping at all before you worry about promotion. Only use canon when the source is actually strong enough.
                  </p>
                )}
                <div style={{ display: 'grid', gap: '8px' }}>
                  <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Source call</p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <QuickFillButton label="Not useful" onClick={() => seedSourceDecision('not_useful')} />
                    <QuickFillButton label="Useful source" onClick={() => seedSourceDecision('source_only')} />
                    <QuickFillButton label="Post idea" onClick={() => seedSourceDecision('post_seed')} />
                    <QuickFillButton label="Memory / canon" onClick={() => seedSourceDecision('canon_candidate')} />
                  </div>
                </div>
                <div style={{ display: 'grid', gap: '8px' }}>
                  <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>Response</p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <QuickFillButton label="Agree" onClick={() => queueTemplate('agree')} />
                    <QuickFillButton label="Disagree" onClick={() => queueTemplate('disagree')} />
                    <QuickFillButton label="Nuance" onClick={() => queueTemplate('nuance')} />
                    <QuickFillButton label="Personal Story" onClick={() => queueTemplate('story')} />
                    <QuickFillButton label="Wording" onClick={() => queueTemplate('language')} />
                  </div>
                </div>
                <div style={{ display: 'grid', gap: '10px', padding: '10px', borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#010617' }}>
                  <div style={{ display: 'grid', gap: '4px' }}>
                    <p style={{ color: '#cbd5f5', fontSize: '12px', fontWeight: 700, margin: 0 }}>
                      Routing
                    </p>
                    <p style={{ color: '#94a3b8', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                      Choose where this should go after review. Workspaces can stay broad; memory, standup, and PM are optional downstream actions.
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {brainTriagePresetOptions.map((preset) => (
                      <button
                        key={preset.key}
                        onClick={() => applyTriagePreset(preset.key)}
                        style={triageChoiceButtonStyle(false)}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                  <div style={{ display: 'grid', gap: '6px' }}>
                    <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
                      Workspaces
                    </p>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {brainWorkspaceOptions.map((workspace) => (
                        <button
                          key={workspace.key}
                          type="button"
                          onClick={() => toggleTriageWorkspace(workspace.key)}
                          style={triageToggleButtonStyle(triageWorkspaceSelection.includes(workspace.key))}
                        >
                          {workspace.label}
                        </button>
                        ))}
                    </div>
                    <p style={{ color: '#64748b', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                      Brain starts with FEEZIE OS and uses {usingBackendWorkspaceSuggestions ? 'backend workspace contracts' : 'conservative fallback defaults'} to suggest other relevant routes. Suggested now: {suggestedWorkspaceKeys.map(labelForBrainWorkspace).join(', ')}.
                      {suggestedWorkspaceReasonSummary ? ` ${suggestedWorkspaceReasonSummary}` : ''}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <button onClick={() => toggleRouteTarget('memory')} style={triageToggleButtonStyle(routeToMemory)}>
                      Canonical Memory
                    </button>
                    <button onClick={() => toggleRouteTarget('standup')} style={triageToggleButtonStyle(routeToStandup)}>
                      Standup Queue
                    </button>
                    <button onClick={() => toggleRouteTarget('pm')} style={triageToggleButtonStyle(routeToPM)}>
                      PM Queue
                    </button>
                  </div>
                  {routeToMemory && (
                    <div style={{ display: 'grid', gap: '6px' }}>
                      <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
                        Memory targets
                      </p>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {canonicalMemoryRouteOptions.map((target) => (
                          <button
                            key={target}
                            type="button"
                            onClick={() => toggleMemoryTarget(target)}
                            style={triageToggleButtonStyle(triageMemoryTargets.includes(target))}
                          >
                            {humanizeCanonicalMemoryTarget(target)}
                          </button>
                        ))}
                      </div>
                      {triageMemoryTargets.length === 0 && <span style={{ color: '#f59e0b', fontSize: '11px' }}>No canonical memory target selected yet.</span>}
                    </div>
                  )}
                  {routeToStandup && (
                    <div style={{ display: 'grid', gap: '6px' }}>
                      <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
                        Standup type
                      </p>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {brainStandupKindOptions.map((kind) => (
                          <button
                            key={kind}
                            type="button"
                            onClick={() => setTriageStandupKind(kind)}
                            style={triageChoiceButtonStyle(triageStandupKind === kind)}
                          >
                            {compactStandupKind(kind)}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {routeToPM && (
                    <label style={{ margin: 0, display: 'grid', gap: '6px' }}>
                      <span style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>PM title</span>
                      <input
                        value={triagePMTitle}
                        onChange={(event) => setTriagePMTitle(event.target.value)}
                        placeholder={selectedDelta ? defaultBrainPMTitle(selectedDelta) : 'Operationalize reviewed signal'}
                        style={{ ...brainInputStyle, padding: '8px 10px' }}
                      />
                    </label>
                  )}
                  {(routeToStandup || routeToPM) && triageExecutionPreviews.length > 0 && (
                    <div style={{ display: 'grid', gridTemplateColumns: viewportWidth >= 1460 ? 'repeat(2, minmax(0, 1fr))' : 'minmax(0, 1fr)', gap: '8px' }}>
                      {triageExecutionPreviews.map((preview) => (
                        <div
                          key={`${preview.workspaceKey}-${preview.standupKind}`}
                          style={{
                            borderRadius: '12px',
                            border: '1px solid #1f2937',
                            backgroundColor: '#020617',
                            padding: '10px 12px',
                            display: 'grid',
                            gap: '4px',
                          }}
                        >
                          <p style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: 700, margin: 0 }}>{labelForBrainWorkspace(preview.workspaceKey)}</p>
                          <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                            {preview.executionModel.mode === 'delegated'
                              ? `${preview.executionModel.manager} manages. ${preview.executionModel.executor} executes.`
                              : `${preview.executionModel.executor} executes directly.`}
                          </p>
                          <p style={{ color: '#64748b', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                            {preview.participants.join(' · ')} · {compactStandupKind(preview.standupKind)}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                  <div
                    style={{
                      display: 'grid',
                      gap: '4px',
                      paddingTop: '8px',
                      borderTop: '1px solid #172036',
                    }}
                  >
                    <p style={{ color: '#cbd5f5', fontSize: '12px', margin: 0, lineHeight: 1.5 }}>
                      Workspaces: {triageWorkspaceSummary}
                    </p>
                    <p style={{ color: hasRouteTargets ? '#94a3b8' : '#64748b', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                      {triageRouteSummary}
                    </p>
                  </div>
                  {triageState.message && (
                    <p style={{ color: triageToneColor, fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                      {triageState.message}
                    </p>
                  )}
                </div>
              </div>

              <div
                style={{
                  display: 'grid',
                  gap: '12px',
                  minHeight: 0,
                  gridTemplateRows: usePinnedPersonaViewport ? 'minmax(220px, 1fr) auto' : 'auto auto',
                }}
              >
                <textarea
                  value={reflectionText}
                  onChange={(event) => {
                    setReflectionText(event.target.value);
                    if (reflectionState.tone !== 'idle') {
                      setReflectionState({ tone: 'idle', message: '' });
                    }
                  }}
                  placeholder={`Example: Yes, this is true. I am building an AI project that supports these initiatives, but I want it framed as a system that strengthens AI Clone, BrandEasy, Outfit A Congo, Collective Fusion, market development, and public leadership rather than a flat list.`}
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    minHeight: usePinnedPersonaViewport ? '220px' : '220px',
                    height: usePinnedPersonaViewport ? '100%' : undefined,
                    resize: 'vertical',
                    borderRadius: '14px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#010617',
                    color: '#e2e8f0',
                    padding: '14px',
                    fontSize: '14px',
                    lineHeight: 1.6,
                    outline: 'none',
                    overflowY: 'auto',
                  }}
                />

                <div
                  style={{
                    display: 'grid',
                    gap: '10px',
                    borderRadius: '14px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#020617',
                    padding: '12px',
                    position: usePinnedPersonaViewport ? 'sticky' : 'static',
                    bottom: usePinnedPersonaViewport ? 0 : undefined,
                    zIndex: 1,
                  }}
                >
                  <div style={{ display: 'grid', gap: '4px' }}>
                    <p style={{ color: '#f8fafc', fontSize: '12px', fontWeight: 700, margin: 0 }}>Submit</p>
                    <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                      Save note stores judgment only. Finalize is the done action for canon and downstream routing.
                    </p>
                  </div>
                  {selectedPromotionItems.length > 0 && compactPersonaChrome && (
                    <div
                      style={{
                        borderRadius: '10px',
                        border: `1px solid ${gateDecisionTone(selectedPromotionGate.decision)}55`,
                        backgroundColor: `${gateDecisionTone(selectedPromotionGate.decision)}12`,
                        padding: '8px 10px',
                        display: 'grid',
                        gap: '6px',
                      }}
                    >
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        <InlineBadge label={humanizeGateDecision(selectedPromotionGate.decision)} tone={gateDecisionTone(selectedPromotionGate.decision)} />
                        <InlineBadge label={`${selectedPromotionGate.selectedCount} selected`} tone="#818cf8" />
                        <InlineBadge label={`proof ${selectedPromotionGate.proofStrength}`} tone={proofStrengthTone(selectedPromotionGate.proofStrength)} />
                      </div>
                      <p style={{ color: '#dbe7ff', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                        {selectedPromotionGate.reason || 'These selected fragments are ready for canon review.'}
                      </p>
                    </div>
                  )}
                  {(error || reflectionState.message) && (
                    <p style={{ color: error ? '#f87171' : reflectionToneColor, fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                      {error || reflectionState.message}
                    </p>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {selectedPromotionItems.length > 0 && <InlineBadge label={`${selectedPromotionItems.length} canon selected`} tone="#818cf8" />}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px', maxWidth: '560px' }}>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        <button
                          onClick={() => saveReflection('reviewed')}
                          disabled={isFinalizePending}
                          style={{
                            border: '1px solid #334155',
                            backgroundColor: isFinalizePending ? '#0f172a' : '#020617',
                            color: isFinalizePending ? '#64748b' : '#cbd5f5',
                            borderRadius: '12px',
                            padding: '10px 14px',
                            cursor: isFinalizePending ? 'wait' : 'pointer',
                            fontWeight: 600,
                          }}
                        >
                          {isFinalizePending ? 'Saving…' : 'Save note'}
                        </button>
                        <button
                          onClick={() => finalizeReviewedSignal()}
                          disabled={isFinalizePending || finalizeActionDisabled}
                          style={{
                            border: '1px solid #f59e0b',
                            backgroundColor: isFinalizePending || finalizeActionDisabled ? '#111827' : '#f59e0b',
                            color: isFinalizePending || finalizeActionDisabled ? '#64748b' : '#0f172a',
                            borderRadius: '12px',
                            padding: '10px 16px',
                            cursor: isFinalizePending ? 'wait' : finalizeActionDisabled ? 'not-allowed' : 'pointer',
                            fontWeight: 700,
                            boxShadow: isFinalizePending || finalizeActionDisabled ? 'none' : '0 10px 24px rgba(245, 158, 11, 0.22)',
                          }}
                        >
                          {isFinalizePending ? finalizeActionBusyLabel : 'Finalize'}
                        </button>
                      </div>
                      <p style={{ color: '#94a3b8', fontSize: '11px', maxWidth: '560px', textAlign: 'left', margin: 0 }}>
                        {finalizeActionSummary}
                      </p>
                    </div>
                  </div>
                  {savedResponseExcerpt && compactPersonaChrome && (
                    <details
                      style={{
                        borderRadius: '10px',
                        border: '1px solid #1f2937',
                        backgroundColor: '#0b1220',
                        padding: '8px 10px',
                        color: '#cbd5f5',
                      }}
                    >
                      <summary style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer' }}>
                        Current saved take
                      </summary>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0 6px' }}>
                        {savedResponseKind && <InlineBadge label={humanizeSavedResponseKind(savedResponseKind)} tone="#818cf8" />}
                        {metadataText(selectedDelta.metadata, 'resolution_capture_id') && (
                          <InlineBadge label={`capture ${metadataText(selectedDelta.metadata, 'resolution_capture_id')}`} tone="#64748b" />
                        )}
                      </div>
                      <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.55, whiteSpace: 'pre-wrap', margin: 0 }}>
                        {truncateText(savedResponseExcerpt, 520)}
                      </p>
                    </details>
                  )}
                </div>
              </div>

              {selectableItems.length > 0 && (
                <div
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#010617',
                    padding: '12px',
                    display: 'grid',
                    gap: '8px',
                    maxHeight: usePinnedPersonaViewport ? '260px' : '330px',
                    overflowY: 'auto',
                    paddingRight: '4px',
                  }}
                >
                  <details>
                    <summary style={{ color: '#818cf8', cursor: 'pointer', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
                      Promotion target
                    </summary>
                    <div style={{ marginTop: '10px', display: 'grid', gap: '8px' }}>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                        <InlineBadge
                          label={
                            selectedPromotionTargetFiles.length > 0
                              ? `Selected: ${describePromotionTargets(selectedPromotionItems, targetFile)}`
                              : `Default: ${humanizeTargetFileLabel(targetFile)}`
                          }
                          tone="#818cf8"
                        />
                        {selectedPromotionTargetFiles.length > 1 && <InlineBadge label="Mixed-target mode" tone="#22c55e" />}
                      </div>
                      <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                        Choose where these fragments should land before you queue promotion.
                      </p>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {promotionTargetChoices.map((choice, index) => {
                          const active =
                            selectedPromotionItems.length > 0
                              ? selectedPromotionItems.every((item) => item.targetFile === choice)
                              : selectableItems.every((item) => item.targetFile === choice);
                          return (
                            <button
                              key={choice}
                              onClick={() => applyBulkPromotionTarget(choice)}
                              style={{
                                borderRadius: '999px',
                                border: active ? '1px solid #38bdf8' : '1px solid #334155',
                                backgroundColor: active ? '#082f49' : '#020617',
                                color: active ? '#f8fafc' : '#cbd5f5',
                                padding: '8px 12px',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              {humanizeTargetFileLabel(choice)}
                              {index === 0 ? ' Suggested' : ''}
                            </button>
                          );
                        })}
                        {activePromotionAlternativeTarget &&
                          !promotionTargetChoices.includes(activePromotionAlternativeTarget) && (
                            <button
                              onClick={() => applyBulkPromotionTarget(activePromotionAlternativeTarget)}
                              style={{
                                borderRadius: '999px',
                                border: '1px solid #334155',
                                backgroundColor: '#082f49',
                                color: '#cbd5f5',
                                padding: '8px 12px',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              Use {humanizeTargetFileLabel(activePromotionAlternativeTarget)}
                            </button>
                          )}
                        {Object.keys(promotionItemTargetOverrides).length > 0 && (
                          <button
                            onClick={() => resetBulkPromotionTargets()}
                            style={{
                              borderRadius: '999px',
                              border: '1px solid #334155',
                              backgroundColor: '#020617',
                              color: '#cbd5f5',
                              padding: '8px 12px',
                              fontSize: '12px',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            Reset selected targets
                          </button>
                        )}
                      </div>
                    </div>
                  </details>
                </div>
              )}

              {selectedPromotionItems.length > 0 && !compactPersonaChrome && (
                <div
                  style={{
                    borderRadius: '12px',
                    border: `1px solid ${gateDecisionTone(selectedPromotionGate.decision)}55`,
                    backgroundColor: `${gateDecisionTone(selectedPromotionGate.decision)}12`,
                    padding: '12px',
                    color: '#cbd5f5',
                  }}
                >
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '8px' }}>
                    <InlineBadge label={humanizeGateDecision(selectedPromotionGate.decision)} tone={gateDecisionTone(selectedPromotionGate.decision)} />
                    <InlineBadge label={`${selectedPromotionGate.selectedCount} selected`} tone="#818cf8" />
                    <InlineBadge label={`proof ${selectedPromotionGate.proofStrength}`} tone={proofStrengthTone(selectedPromotionGate.proofStrength)} />
                  </div>
                  <p style={{ color: '#dbe7ff', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                    {selectedPromotionGate.reason || 'These selected fragments are ready for canon review.'}
                  </p>
                  {selectedPromotionGate.alternativeTarget && (
                    <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: '8px 0 0' }}>
                      Better fit if you want to preserve the idea now: {selectedPromotionGate.alternativeTarget}
                    </p>
                  )}
                </div>
              )}

              {savedResponseExcerpt && !compactPersonaChrome && (
                <details
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#0b1220',
                    padding: '10px 12px',
                    color: '#cbd5f5',
                  }}
                >
                  <summary style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer' }}>
                    Your current take
                  </summary>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '10px 0 8px' }}>
                    {savedResponseKind && <InlineBadge label={humanizeSavedResponseKind(savedResponseKind)} tone="#818cf8" />}
                    {metadataText(selectedDelta.metadata, 'resolution_capture_id') && (
                      <InlineBadge label={`capture ${metadataText(selectedDelta.metadata, 'resolution_capture_id')}`} tone="#64748b" />
                    )}
                  </div>
                  <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>
                    {truncateText(savedResponseExcerpt, 900)}
                  </p>
                </details>
              )}
            </section>
            </div>
          </div>
        ) : (
          <div
            style={{
              flex: 1,
              minHeight: 0,
              borderRadius: '14px',
              border: '1px solid #1f2937',
              backgroundColor: '#020617',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '24px',
            }}
          >
            <div style={{ maxWidth: '560px' }}>
              <p style={{ color: '#22c55e', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.18em', marginBottom: '10px' }}>Done</p>
              <h3 style={{ color: 'white', fontSize: '28px', margin: '0 0 10px' }}>You are done for now.</h3>
              <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.65 }}>
                There are no pending persona review items left in this session. New reflections can come back through future persona deltas.
              </p>
              {reflectionState.message && (
                <p style={{ color: reflectionState.tone === 'success' ? '#22c55e' : '#f87171', fontSize: '12px', marginTop: '12px' }}>{reflectionState.message}</p>
              )}
            </div>
          </div>
        )}
        {promotionState.message && promotionState.tone === 'success' && (
          <div
            style={{
              position: usePinnedPersonaViewport ? 'sticky' : 'static',
              top: usePinnedPersonaViewport ? '88px' : undefined,
              zIndex: 2,
              borderRadius: '999px',
              border: '1px solid #14532d',
              backgroundColor: '#052e16',
              padding: '8px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              flexWrap: 'wrap',
              width: 'fit-content',
              maxWidth: '100%',
            }}
          >
            <InlineBadge label="Canon updated" tone="#22c55e" />
            <p style={{ color: '#dcfce7', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
              {promotionState.message}
            </p>
          </div>
        )}
      </section>

      <section
        style={{
          borderRadius: '18px',
          border: '1px solid #334155',
          background: 'linear-gradient(180deg, #071224 0%, #050b19 100%)',
          padding: showLifecycleAudit ? '18px' : '6px 10px',
          display: 'grid',
          gap: showLifecycleAudit ? '16px' : '0',
          minHeight: 0,
          overflow: 'hidden',
          gridTemplateRows: showLifecycleAudit && usePinnedPersonaViewport ? 'auto auto minmax(0, 1fr)' : 'auto',
          boxShadow: showLifecycleAudit ? '0 18px 40px rgba(2, 6, 23, 0.35)' : 'none',
        }}
      >
        {showLifecycleAudit ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div>
                <p style={{ color: '#818cf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Canon Audit</p>
                <h3 style={{ color: 'white', fontSize: '24px', margin: '0 0 8px' }}>Saved, held, committed, and resolved canon activity</h3>
                <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.6 }}>
                  Use this only when you want to inspect what happened after review. The active review workspace stays above.
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setShowLifecycleAudit((current) => !current)}
                  style={triageChoiceButtonStyle(showLifecycleAudit)}
                >
                  Hide audit trail
                </button>
              </div>
            </div>
            {promotionState.message && promotionState.tone !== 'success' && (
              <p style={{ color: '#f87171', fontSize: '12px' }}>{promotionState.message}</p>
            )}
          </>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <p style={{ color: '#818cf8', letterSpacing: '0.18em', fontSize: '10px', textTransform: 'uppercase', margin: 0 }}>Canon Audit</p>
            <button
              type="button"
              onClick={() => setShowLifecycleAudit(true)}
              style={triageChoiceButtonStyle(false)}
            >
              Open audit trail
            </button>
          </div>
        )}
        {showLifecycleAudit && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: viewportWidth >= 1160 ? 'repeat(4, minmax(0, 1fr))' : viewportWidth >= 760 ? 'repeat(2, minmax(0, 1fr))' : 'minmax(0, 1fr)',
              gap: '10px',
            }}
          >
            {lifecycleGroups.map((group) => {
              const active = lifecycleView === group.key;
              return (
                <button
                  key={group.key}
                  onClick={() => setLifecycleView(group.key as 'pending_promotion' | 'workspace_saved' | 'committed' | 'resolved')}
                  style={{
                    borderRadius: '14px',
                    border: `1px solid ${active ? `${group.tone}88` : '#1f2937'}`,
                    backgroundColor: active ? `${group.tone}18` : '#020617',
                    color: active ? '#f8fafc' : '#94a3b8',
                    padding: '12px 14px',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    textAlign: 'left',
                    display: 'grid',
                    gap: '6px',
                  }}
                  >
                    <span style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em', color: active ? group.tone : '#64748b' }}>
                      {compactLifecycleLabel(group.key)}
                    </span>
                    <span style={{ fontSize: '22px', lineHeight: 1, color: '#f8fafc' }}>{group.count}</span>
                    <span style={{ color: active ? '#dbe7ff' : '#94a3b8', fontSize: '11px', lineHeight: 1.5 }}>
                      {group.description}
                    </span>
                  </button>
              );
            })}
          </div>
        )}
        {showLifecycleAudit && activeLifecycleGroup && (
          <div
            style={{
              borderRadius: '14px',
              border: '1px solid #1f2937',
              backgroundColor: '#020617',
              padding: '14px',
              display: 'grid',
              gap: '10px',
              minHeight: 0,
              overflow: 'hidden',
              gridTemplateRows: 'auto minmax(0, 1fr)',
            }}
          >
            <div>
              <div
                style={{
                  borderRadius: '12px',
                  border: `1px solid ${activeLifecycleGroup.tone}44`,
                  backgroundColor: `${activeLifecycleGroup.tone}12`,
                  padding: '12px 14px',
                  display: 'grid',
                  gap: '6px',
                }}
              >
                <p style={{ color: activeLifecycleGroup.tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em', margin: 0 }}>
                  You are viewing {activeLifecycleGroup.title}
                </p>
                <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.55, margin: 0 }}>
                  {activeLifecycleGroup.description}
                </p>
              </div>
            </div>
            <div style={{ display: 'grid', gap: '8px', minHeight: 0, overflowY: 'auto', paddingRight: '2px' }}>
              {activeLifecycleGroup.items.length === 0 ? (
                <p style={{ color: '#475569', fontSize: '12px' }}>Nothing in this state right now.</p>
              ) : (
                activeLifecycleGroup.items.slice(0, 12).map((item) => (
                  (() => {
                    const queuedItems = readPromotionItemsFromMetadata(item.metadata);
                    const committedItems = readPromotionItemsFromMetadata(item.metadata, 'committed_promotion_items');
                    const lifecycleItems = activeLifecycleGroup.key === 'committed' && committedItems.length > 0 ? committedItems : queuedItems;
                    const gateSummary = summarizePromotionItems(queuedItems, metadataText(item.metadata, 'target_file'));
                    const lifecycleTargetFiles =
                      activeLifecycleGroup.key === 'committed'
                        ? metadataStringArray(item.metadata, 'committed_target_files')
                        : Array.from(new Set(lifecycleItems.map((promotionItem) => promotionItem.targetFile).filter((value): value is string => Boolean(value))));
                    const bundleWrittenFiles = metadataStringArray(item.metadata, 'bundle_written_files');
                    const bundleFileResults = metadataObject<Record<string, BundleFileResult>>(item.metadata, 'bundle_file_results');
                    const bundleSync = metadataObject<LocalBundleSyncState>(item.metadata, 'local_bundle_sync');
                    const bundleResultSummary = summarizeBundleFileResults(bundleFileResults);
                    const committedAt = metadataText(item.metadata, 'promotion_committed_at') ?? item.committed_at ?? null;
                    const isRecentlyQueued = recentlyQueuedDeltaId === item.id;
                    const isRecentlyCommitted = recentlyCommittedDeltaId === item.id;
                    const routeHistoryCount = metadataArray(item.metadata, 'brain_route_history').length;
                    const commitDisabled = activeLifecycleGroup.key === 'pending_promotion' && gateSummary.decision !== 'allow';
                    return (
                  <div
                    key={item.id}
                    style={{
                      borderRadius: '14px',
                      border: `1px solid ${isRecentlyCommitted ? '#22c55e' : isRecentlyQueued ? '#38bdf8' : '#1f2937'}`,
                      padding: '10px',
                      backgroundColor: isRecentlyCommitted ? '#052e1b' : isRecentlyQueued ? '#082f49' : '#0b1220',
                    }}
                  >
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                      <InlineBadge label={activeLifecycleGroup.title} tone={activeLifecycleGroup.tone} />
                      {activeLifecycleGroup.key === 'pending_promotion' && (
                        <InlineBadge label={humanizeGateDecision(gateSummary.decision)} tone={gateDecisionTone(gateSummary.decision)} />
                      )}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '6px' }}>
                      <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>{truncateText(item.trait, 140)}</p>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>{formatTimestamp(item.created_at)}</span>
                    </div>
                    {(isRecentlyQueued || isRecentlyCommitted || lifecycleItems.length > 0) && (
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                        {isRecentlyQueued && <InlineBadge label="just queued" tone="#38bdf8" />}
                        {isRecentlyCommitted && <InlineBadge label="just committed" tone="#22c55e" />}
                        {lifecycleItems.length > 0 && <InlineBadge label={`${lifecycleItems.length} fragment${lifecycleItems.length === 1 ? '' : 's'}`} tone="#818cf8" />}
                        {activeLifecycleGroup.key === 'pending_promotion' && (
                          <InlineBadge label={humanizeGateDecision(gateSummary.decision)} tone={gateDecisionTone(gateSummary.decision)} />
                        )}
                        {activeLifecycleGroup.key === 'committed' && committedAt && (
                          <InlineBadge label={`Committed ${formatTimestamp(committedAt)}`} tone="#22c55e" />
                        )}
                        {routeHistoryCount > 0 && <InlineBadge label={`${routeHistoryCount} routed`} tone="#38bdf8" />}
                        {activeLifecycleGroup.key === 'committed' && (
                          <InlineBadge label={humanizeLocalBundleSyncState(bundleSync?.state)} tone={localBundleSyncTone(bundleSync?.state)} />
                        )}
                      </div>
                    )}
                    {(lifecycleTargetFiles.length > 0 || bundleWrittenFiles.length > 0) && (
                      <div style={{ display: 'grid', gap: '4px', marginBottom: '8px' }}>
                        {lifecycleTargetFiles.length > 0 && (
                          <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                            Targets: {lifecycleTargetFiles.map((path) => humanizeTargetFileLabel(path)).join(', ')}
                          </p>
                        )}
                        {activeLifecycleGroup.key === 'committed' && bundleWrittenFiles.length > 0 && (
                          <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                            Written files: {bundleWrittenFiles.map((path) => humanizeTargetFileLabel(path)).join(', ')}
                          </p>
                        )}
                      </div>
                    )}
                    {metadataText(item.metadata, 'owner_response_excerpt') && (
                      <div style={{ marginBottom: '8px' }}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                          {metadataText(item.metadata, 'owner_response_kind') && (
                            <InlineBadge label={humanizeSavedResponseKind(metadataText(item.metadata, 'owner_response_kind') ?? '')} tone="#818cf8" />
                          )}
                          {metadataText(item.metadata, 'belief_relation') && (
                            <InlineBadge label={humanizeBeliefRelation(metadataText(item.metadata, 'belief_relation'))} tone="#22c55e" />
                          )}
                        </div>
                        <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                          {truncateText(metadataText(item.metadata, 'owner_response_excerpt') ?? '', 180)}
                        </p>
                      </div>
                    )}
                    {lifecycleItems.length > 0 && (
                      <div
                        style={{
                          marginBottom: '8px',
                          padding: '10px',
                          borderRadius: '12px',
                          border: '1px solid #1f2937',
                          backgroundColor: '#020617',
                          display: 'grid',
                          gap: '8px',
                        }}
                      >
                        <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
                          {activeLifecycleGroup.key === 'committed' ? 'Committed fragments' : 'Queued fragments'}
                        </p>
                        <div style={{ display: 'grid', gap: '8px' }}>
                          {lifecycleItems.map((promotionItem) => (
                            <div
                              key={promotionItem.id}
                              style={{
                                borderRadius: '10px',
                                border: '1px solid #1f2937',
                                backgroundColor: '#0b1220',
                                padding: '9px 10px',
                                display: 'grid',
                                gap: '6px',
                              }}
                            >
                              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                <InlineBadge label={humanizePromotionKind(promotionItem.kind)} tone="#64748b" />
                                <InlineBadge label={humanizeTargetFileLabel(promotionItem.targetFile)} tone="#818cf8" />
                                {activeLifecycleGroup.key !== 'committed' && (
                                  <InlineBadge
                                    label={humanizeGateDecision(resolvePromotionGate(promotionItem, metadataText(item.metadata, 'target_file')).decision)}
                                    tone={gateDecisionTone(resolvePromotionGate(promotionItem, metadataText(item.metadata, 'target_file')).decision)}
                                  />
                                )}
                              </div>
                              <p style={{ color: '#e2e8f0', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                                {truncateText(promotionItem.content, 220)}
                              </p>
                              {promotionItem.artifactSummary && (
                                <p style={{ color: '#94a3b8', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                                  Artifact: {promotionItem.artifactSummary}
                                </p>
                              )}
                              {activeLifecycleGroup.key === 'committed' && (promotionItem.canonPurpose || promotionItem.canonValue || promotionItem.canonProof) && (
                                <div style={{ display: 'grid', gap: '4px' }}>
                                  {promotionItem.canonPurpose && (
                                    <p style={{ color: '#dbe7ff', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                                      Purpose: {truncateText(promotionItem.canonPurpose, 180)}
                                    </p>
                                  )}
                                  {promotionItem.canonValue && (
                                    <p style={{ color: '#cbd5f5', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                                      Value: {truncateText(promotionItem.canonValue, 180)}
                                    </p>
                                  )}
                                  {promotionItem.canonProof && (
                                    <p style={{ color: '#94a3b8', fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
                                      Proof: {truncateText(promotionItem.canonProof, 180)}
                                    </p>
                                  )}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {activeLifecycleGroup.key === 'pending_promotion' && (
                      <div
                        style={{
                          marginBottom: '8px',
                          padding: '8px 10px',
                          borderRadius: '10px',
                          border: `1px solid ${gateDecisionTone(gateSummary.decision)}44`,
                          backgroundColor: `${gateDecisionTone(gateSummary.decision)}12`,
                        }}
                      >
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                          <InlineBadge label={humanizeGateDecision(gateSummary.decision)} tone={gateDecisionTone(gateSummary.decision)} />
                          <InlineBadge label={`proof ${gateSummary.proofStrength}`} tone={proofStrengthTone(gateSummary.proofStrength)} />
                        </div>
                        <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                          {gateSummary.reason || 'This queued item is ready to commit to canon.'}
                        </p>
                        {gateSummary.alternativeTarget && (
                          <p style={{ color: '#94a3b8', fontSize: '11px', lineHeight: 1.5, margin: '6px 0 0' }}>
                            Better fit right now: {gateSummary.alternativeTarget}
                          </p>
                        )}
                      </div>
                    )}
                    {activeLifecycleGroup.key === 'committed' && (
                      <div
                        style={{
                          marginBottom: '8px',
                          padding: '8px 10px',
                          borderRadius: '10px',
                          border: `1px solid ${localBundleSyncTone(bundleSync?.state)}44`,
                          backgroundColor: `${localBundleSyncTone(bundleSync?.state)}12`,
                        }}
                      >
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                          <InlineBadge label={humanizeLocalBundleSyncState(bundleSync?.state)} tone={localBundleSyncTone(bundleSync?.state)} />
                          {bundleWrittenFiles.length > 0 && (
                            <InlineBadge label={`${bundleWrittenFiles.length} bundle file${bundleWrittenFiles.length === 1 ? '' : 's'}`} tone="#818cf8" />
                          )}
                        </div>
                        {bundleResultSummary && (
                          <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                            Write results: {bundleResultSummary}
                          </p>
                        )}
                        {bundleSync?.synced_at && (
                          <p style={{ color: '#94a3b8', fontSize: '11px', lineHeight: 1.5, margin: bundleResultSummary ? '6px 0 0' : 0 }}>
                            Synced locally at {formatTimestamp(bundleSync.synced_at)}
                          </p>
                        )}
                        {bundleSync?.error && (
                          <p style={{ color: '#fca5a5', fontSize: '11px', lineHeight: 1.5, margin: '6px 0 0' }}>
                            Last sync error: {truncateText(bundleSync.error, 180)}
                          </p>
                        )}
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                      <span style={{ color: '#64748b', fontSize: '11px' }}>{humanizeReviewSource(metadataText(item.metadata, 'review_source'))}</span>
                      {activeLifecycleGroup.key === 'pending_promotion' && (
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                          {gateSummary.alternativeTarget && (
                            <button
                              onClick={() => void reroutePromotion(item, gateSummary.alternativeTarget!)}
                              disabled={Boolean(reroutingDeltaId) || Boolean(promotingDeltaId)}
                              style={{
                                borderRadius: '10px',
                                border: '1px solid #334155',
                                backgroundColor: reroutingDeltaId === item.id ? '#0f172a' : '#082f49',
                                color: '#cbd5f5',
                                padding: '8px 10px',
                                cursor: reroutingDeltaId || promotingDeltaId ? 'wait' : 'pointer',
                                fontSize: '12px',
                                fontWeight: 600,
                              }}
                            >
                              {reroutingDeltaId === item.id ? 'Rerouting…' : `Reroute to ${humanizeTargetFileLabel(gateSummary.alternativeTarget)}`}
                            </button>
                          )}
                          <button
                            onClick={() => void commitPromotion(item)}
                            disabled={Boolean(reroutingDeltaId) || promotingDeltaId === item.id || commitDisabled}
                            style={{
                              borderRadius: '10px',
                              border: `1px solid ${commitDisabled ? '#475569' : '#818cf8'}`,
                              backgroundColor: commitDisabled ? '#0f172a' : promotingDeltaId === item.id ? '#312e81' : '#1e1b4b',
                              color: commitDisabled ? '#64748b' : 'white',
                              padding: '8px 10px',
                              cursor: reroutingDeltaId || commitDisabled ? 'not-allowed' : promotingDeltaId === item.id ? 'wait' : 'pointer',
                              fontSize: '12px',
                              fontWeight: 600,
                            }}
                          >
                            {commitDisabled ? (gateSummary.decision === 'block' ? 'Blocked' : 'Held') : promotingDeltaId === item.id ? 'Committing…' : 'Commit to canon'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                    );
                  })()
                ))
              )}
            </div>
          </div>
        )}
      </section>
    </section>
  );
}

function QuickFillButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        borderRadius: '999px',
        border: '1px solid #1f2937',
        backgroundColor: '#020617',
        color: '#cbd5f5',
        padding: '6px 10px',
        fontSize: '12px',
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );
}

function ReviewMetaChip({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div style={{ borderRadius: '999px', border: `1px solid ${tone}44`, backgroundColor: `${tone}18`, padding: '6px 10px' }}>
      <span style={{ color: '#94a3b8', fontSize: '11px', marginRight: '6px', textTransform: 'uppercase' }}>{label}</span>
      <span style={{ color: tone, fontSize: '12px', fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function InlineBadge({ label, tone }: { label: string; tone: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        maxWidth: '100%',
        borderRadius: '999px',
        border: `1px solid ${tone}44`,
        backgroundColor: `${tone}18`,
        color: tone,
        padding: '4px 8px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        whiteSpace: 'normal',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
      }}
    >
      {label}
    </span>
  );
}

function CaptureTelemetryPanel({
  metrics,
  health,
  error,
}: {
  metrics: CaptureTelemetry | null;
  health: OpenBrainHealth | null;
  error: string | null;
}) {
  if (error) {
    return <p style={{ color: '#f87171' }}>{error}</p>;
  }

  const storageLabel = health?.storage_backend === 'pgvector' ? 'Native vector mode' : health?.storage_backend === 'jsonb' ? 'JSON fallback' : 'Unknown';
  const serviceLabel = health?.search_ready ? 'Search ready' : health?.database_connected ? 'Memory store online' : 'Memory store offline';
  const subtitle =
    health?.storage_backend === 'pgvector'
      ? 'Capture + refresh stats from the native Postgres vector lane.'
      : 'Capture + refresh stats from the Postgres memory lane. JSON fallback is active until native vector support is available.';

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Open Brain Telemetry</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>{subtitle}</p>
        </div>
        <p style={{ color: health?.database_connected ? '#22c55e' : '#f87171', fontSize: '12px' }}>
          {serviceLabel}
        </p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <TelemetryMeta label="Storage" value={storageLabel} detail={health?.embedding_type ?? 'n/a'} />
        <TelemetryMeta label="Native Vector Ext" value={health?.vector_extension ? 'Enabled' : 'Unavailable'} detail="Current Postgres capability" />
        <TelemetryMeta
          label="Embedding Dimension"
          value={health?.configured_dimension ? `${health.configured_dimension}/${health.embedder_dimension}` : `${health?.embedder_dimension ?? 0}`}
          detail={health?.dimension_match ? 'DB and embedder aligned' : 'Running fallback storage mode'}
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <TelemetryStat label="Captures" value={metrics?.captures.total ?? 0} tone="#38bdf8" detail="All time" />
        <TelemetryStat label="Last 24h" value={metrics?.captures.last_24h ?? 0} tone="#34d399" detail="Fresh ingest" />
        <TelemetryStat label="Chunks" value={metrics?.vectors.total ?? 0} tone="#f97316" detail="Indexed memory rows" />
        <TelemetryStat label="Expiring" value={metrics?.vectors.with_expiry ?? 0} tone="#fbbf24" detail="Short-term" />
        <TelemetryStat label="Overdue" value={metrics?.vectors.overdue ?? 0} tone="#f87171" detail="Needs cleanup" />
        <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
          <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Last refresh run</p>
          <p style={{ color: '#cbd5f5', fontSize: '18px', fontWeight: 600 }}>{metrics?.vectors.last_refresh_at ? formatTimestamp(metrics.vectors.last_refresh_at) : '—'}</p>
          <p style={{ color: '#475569', fontSize: '12px' }}>memory_vectors.last_refreshed_at</p>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Source', 'Topics', 'Chunks', 'Created'].map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!metrics || metrics.recent_captures.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ padding: '12px 0', color: '#475569' }}>No captures recorded yet.</td>
              </tr>
            ) : (
              metrics.recent_captures.map((capture) => (
                <tr key={capture.id}>
                  <td style={{ padding: '10px 0', color: '#e2e8f0', fontWeight: 600 }}>{capture.source ?? '—'}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{(capture.topics ?? []).join(', ') || '—'}</td>
                  <td style={{ padding: '10px 0', color: '#e2e8f0' }}>{capture.chunk_count}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{capture.created_at ? formatTimestamp(capture.created_at) : '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TelemetryMeta({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
  );
}

function TelemetryStat({ label, value, detail, tone }: { label: string; value: number; detail: string; tone: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: tone, fontSize: '22px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
  );
}

function AutomationsPanel({
  automations,
  error,
  controlPlane,
  docCount,
}: {
  automations: Automation[];
  error: string | null;
  controlPlane: BrainControlPlanePayload | null;
  docCount: number;
}) {
  if (error) {
    return <p style={{ color: '#f87171' }}>{error}</p>;
  }
  const hasRows = automations.length > 0;
  const summary = controlPlane?.summary ?? null;
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', display: 'grid', gap: '14px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Automations</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>Use this tab as the operational surface: which jobs exist, when they ran, and whether the system is healthy enough to trust them.</p>
        </div>
        {summary && (
          <p style={{ color: '#94a3b8', fontSize: '12px' }}>
            {summary.active_automation_count ?? automations.length} active · {summary.capture_count ?? 0} captures · {docCount} docs
          </p>
        )}
      </div>
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <TelemetryMeta label="Active Jobs" value={String(summary.active_automation_count ?? automations.length)} detail="Currently visible automation contracts" />
          <TelemetryMeta label="Captures" value={String(summary.capture_count ?? 0)} detail="Open Brain capture total" />
          <TelemetryMeta label="Pending Review" value={String(summary.pending_review_count ?? 0)} detail="Brain persona queue" />
          <TelemetryMeta label="Source Assets" value={String(summary.source_asset_count ?? 0)} detail="Shared long-form source inventory" />
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Name</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Schedule</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Status</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Channel</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Last Run</th>
            </tr>
          </thead>
          <tbody>
            {!hasRows && (
              <tr>
                <td colSpan={5} style={{ padding: '12px 0', color: '#475569' }}>No automations found.</td>
              </tr>
            )}
            {hasRows &&
              automations.map((job) => (
                <tr key={job.id}>
                  <td style={{ padding: '10px 0', color: 'white', fontWeight: 600 }}>{job.name}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.schedule}</td>
                  <td style={{ padding: '10px 0' }}>{statusBadge(job.status)}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{job.channel}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.last_run_at ? formatTimestamp(job.last_run_at) : '—'}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DocsPanel({ docs }: { docs: DocEntry[] }) {
  const [docQuery, setDocQuery] = useState('');
  const [selectedGroup, setSelectedGroup] = useState('all');
  const [recentDocPaths, setRecentDocPaths] = useState<string[]>([]);
  const [docContentByPath, setDocContentByPath] = useState<Record<string, DocEntry>>({});
  const [loadingDocPath, setLoadingDocPath] = useState<string | null>(null);
  const [docContentError, setDocContentError] = useState<string | null>(null);
  const filteredDocs = useMemo(() => {
    const query = docQuery.trim().toLowerCase();
    return docs.filter((doc) => {
      const group = doc.group ?? inferDocGroup(doc.path);
      const matchesGroup = selectedGroup === 'all' || group === selectedGroup;
      const loadedContent = docContentByPath[doc.path]?.content ?? doc.content ?? '';
      const haystack = `${doc.name}\n${doc.path}\n${doc.snippet}\n${loadedContent}`.toLowerCase();
      const matchesQuery = query.length === 0 || haystack.includes(query);
      return matchesGroup && matchesQuery;
    });
  }, [docContentByPath, docQuery, docs, selectedGroup]);
  const groupedDocs = useMemo(() => {
    const groups = new Map<string, DocEntry[]>();
    for (const doc of filteredDocs) {
      const key = doc.group ?? inferDocGroup(doc.path);
      const current = groups.get(key) ?? [];
      current.push(doc);
      groups.set(key, current);
    }
    return Array.from(groups.entries()).map(([group, items]) => ({
      group,
      items: items.sort((left, right) => left.name.localeCompare(right.name)),
    }));
  }, [filteredDocs]);
  const allGroups = useMemo(() => Array.from(new Set(docs.map((doc) => doc.group ?? inferDocGroup(doc.path)))).sort(), [docs]);
  const [selectedDocPath, setSelectedDocPath] = useState<string>(docs[0]?.path ?? '');
  const selectedDoc = useMemo(
    () => groupedDocs.flatMap((entry) => entry.items).find((doc) => doc.path === selectedDocPath) ?? groupedDocs[0]?.items[0] ?? null,
    [groupedDocs, selectedDocPath],
  );
  const recentDocs = useMemo(
    () => recentDocPaths.map((path) => docs.find((doc) => doc.path === path)).filter((doc): doc is DocEntry => Boolean(doc)),
    [docs, recentDocPaths],
  );

  useEffect(() => {
    if (selectedDoc) {
      return;
    }
    if (groupedDocs[0]?.items[0]) {
      setSelectedDocPath(groupedDocs[0].items[0].path);
    }
  }, [groupedDocs, selectedDoc]);
  const selectedDocContent = selectedDoc ? docContentByPath[selectedDoc.path]?.content ?? selectedDoc.content ?? null : null;
  const selectedDocIsLoading = selectedDoc ? loadingDocPath === selectedDoc.path : false;

  useEffect(() => {
    if (!selectedDoc || selectedDoc.content || docContentByPath[selectedDoc.path]) {
      return;
    }
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), BRAIN_DOC_CONTENT_TIMEOUT_MS);
    setLoadingDocPath(selectedDoc.path);
    setDocContentError(null);

    fetch(`/api/brain-docs?path=${encodeURIComponent(selectedDoc.path)}`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = await response.text().catch(() => response.statusText);
          throw new Error(`${response.status} ${response.statusText}: ${text}`);
        }
        return response.json() as Promise<DocEntry>;
      })
      .then((doc) => {
        setDocContentByPath((current) => ({
          ...current,
          [selectedDoc.path]: doc,
        }));
      })
      .catch((error) => {
        if (error instanceof Error && error.name === 'AbortError') {
          setDocContentError(`Document load timed out after ${BRAIN_DOC_CONTENT_TIMEOUT_MS}ms.`);
          return;
        }
        setDocContentError(error instanceof Error ? error.message : 'Unable to load document content.');
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
        setLoadingDocPath((current) => (current === selectedDoc.path ? null : current));
      });

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [docContentByPath, selectedDoc]);

  return (
    <section style={{ display: 'flex', gap: '18px', borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', minHeight: '560px' }}>
      <div style={{ width: '320px', borderRight: '1px solid #0f172a', paddingRight: '12px', maxHeight: '520px', overflowY: 'auto' }}>
        <div style={{ marginBottom: '12px' }}>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Knowledge Docs</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>
            Brain is the canonical reading surface for operating docs, system contracts, persona files, canonical memory, and reference material.
          </p>
        </div>
        <div style={{ display: 'grid', gap: '10px', marginBottom: '14px' }}>
          <input
            value={docQuery}
            onChange={(event) => setDocQuery(event.target.value)}
            placeholder="Search docs, paths, or content"
            style={brainInputStyle}
          />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setSelectedGroup('all')}
              style={docsFilterButtonStyle(selectedGroup === 'all')}
            >
              All
            </button>
            {allGroups.map((group) => (
              <button
                key={group}
                onClick={() => setSelectedGroup(group)}
                style={docsFilterButtonStyle(selectedGroup === group)}
              >
                {group}
              </button>
            ))}
          </div>
        </div>
        {recentDocs.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Recently viewed</p>
            <div style={{ display: 'grid', gap: '8px' }}>
              {recentDocs.slice(0, 3).map((doc) => (
                <button
                  key={`recent-${doc.path}`}
                  onClick={() => setSelectedDocPath(doc.path)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '10px',
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#020617',
                    color: 'white',
                    cursor: 'pointer',
                  }}
                >
                  <p style={{ fontSize: '13px', fontWeight: 600 }}>{doc.name}</p>
                  <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.45 }}>{truncateText(doc.snippet, 90)}</p>
                </button>
              ))}
            </div>
          </div>
        )}
        {groupedDocs.length === 0 && <p style={{ color: '#475569' }}>No documentation found.</p>}
        {groupedDocs.map((group) => (
          <div key={group.group} style={{ marginBottom: '16px' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{group.group}</p>
            <div style={{ display: 'grid', gap: '8px' }}>
              {group.items.map((doc) => {
                const isSelected = doc.path === (selectedDoc?.path ?? '');
                return (
                  <button
                    key={doc.path}
                    onClick={() => {
                      setSelectedDocPath(doc.path);
                      setRecentDocPaths((current) => [doc.path, ...current.filter((entry) => entry !== doc.path)].slice(0, 5));
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '10px',
                      borderRadius: '12px',
                      border: isSelected ? '1px solid #38bdf8' : '1px solid transparent',
                      backgroundColor: isSelected ? '#0f172a' : 'transparent',
                      color: 'white',
                      cursor: 'pointer',
                    }}
                  >
                    <p style={{ fontSize: '13px', fontWeight: 600 }}>
                      {doc.name}
                      {doc.readMode && doc.readMode !== 'live' ? ` (${doc.readMode})` : ''}
                    </p>
                    <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.45 }}>{doc.snippet}</p>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {selectedDoc ? (
          <div>
            <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '4px' }}>{selectedDoc.group ?? inferDocGroup(selectedDoc.path)}</p>
                <h2 style={{ color: 'white', fontSize: '24px', marginBottom: '6px' }}>{selectedDoc.name}</h2>
                <p style={{ color: '#64748b', fontSize: '12px' }}>
                  {selectedDoc.path}
                  {selectedDoc.readMode && ` · ${selectedDoc.readMode}`}
                  {selectedDoc.resolvedPath && selectedDoc.resolvedPath !== selectedDoc.path ? ` · reads ${selectedDoc.resolvedPath}` : ''}
                </p>
              </div>
              {selectedDoc.updatedAt && <p style={{ color: '#64748b', fontSize: '12px' }}>Updated {formatTimestamp(selectedDoc.updatedAt)}</p>}
            </div>
            <div
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '16px',
                color: '#cbd5f5',
                fontSize: '14px',
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                maxHeight: '500px',
                overflowY: 'auto',
              }}
            >
              {selectedDocIsLoading ? 'Loading document content...' : docContentError ? docContentError : selectedDocContent?.trim() || selectedDoc.snippet}
            </div>
          </div>
        ) : (
          <p style={{ color: '#475569' }}>Select a document to read it here.</p>
        )}
      </div>
    </section>
  );
}

function statusBadge(status?: string) {
  const normalized = status?.toLowerCase();
  const color =
    normalized === 'healthy' || normalized === 'active'
      ? '#22c55e'
      : normalized === 'warning'
      ? '#fbbf24'
      : normalized === 'error'
      ? '#f87171'
      : '#94a3b8';
  const background = `${color}33`;
  return (
    <span style={{ padding: '4px 12px', borderRadius: '999px', backgroundColor: background, color, fontSize: '12px', textTransform: 'capitalize' }}>
      {status ?? 'unknown'}
    </span>
  );
}

function docsFilterButtonStyle(active: boolean) {
  return {
    borderRadius: '999px',
    border: active ? '1px solid #38bdf8' : '1px solid #1f2937',
    backgroundColor: active ? '#082f49' : '#020617',
    color: active ? '#f8fafc' : '#94a3b8',
    padding: '7px 11px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
  };
}

function triageToggleButtonStyle(active: boolean) {
  return {
    borderRadius: '999px',
    border: active ? '1px solid #38bdf8' : '1px solid #334155',
    backgroundColor: active ? '#082f49' : '#020617',
    color: active ? '#f8fafc' : '#cbd5f5',
    padding: '8px 12px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
  };
}

function triageChoiceButtonStyle(active: boolean) {
  return {
    borderRadius: '999px',
    border: active ? '1px solid #818cf8' : '1px solid #334155',
    backgroundColor: active ? '#1e1b4b' : '#020617',
    color: active ? '#f8fafc' : '#cbd5f5',
    padding: '8px 12px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
  };
}

function compactLifecycleLabel(key: string) {
  if (key === 'workspace_saved') return 'Saved';
  if (key === 'pending_promotion') return 'Queued';
  if (key === 'committed') return 'Committed';
  return 'History';
}

function metadataText(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}

function metadataObject<T extends object>(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as T) : null;
}

function metadataArray(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return Array.isArray(value) ? value : [];
}

function metadataStringArray(metadata: Record<string, unknown> | undefined, key: string) {
  return metadataArray(metadata, key).filter((value): value is string => typeof value === 'string' && value.trim().length > 0);
}

function metadataBoolean(metadata: Record<string, unknown> | undefined, key: string) {
  return metadata?.[key] === true;
}

function stablePromotionItemId(kind: PromotionItemKind, title: string, content: string) {
  const source = `${kind}:${title}:${content}`;
  let hash = 0;
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash * 31 + source.charCodeAt(index)) >>> 0;
  }
  return `${kind}:${hash.toString(16)}`;
}

function normalizePromotionContentKey(value: string) {
  return value
    .toLowerCase()
    .replace(/<\d{2}:\d{2}:\d{2}\.\d{3}>/g, ' ')
    .replace(/<\/?c(?:\.[^>]*)?>/g, ' ')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function promotionItemPriority(kind: PromotionItemKind) {
  if (kind === 'stat') return 5;
  if (kind === 'anecdote') return 4;
  if (kind === 'framework') return 3;
  if (kind === 'talking_point') return 2;
  return 1;
}

function meetsPromotionItemLengthFloor(kind: PromotionItemKind, content: string) {
  const words = content.split(/\s+/).filter(Boolean).length;
  if (kind === 'phrase_candidate') {
    return words >= 3 && words <= 16;
  }
  if (kind === 'stat') {
    return words >= 5;
  }
  return words >= 6;
}

function buildPromotionItems(delta: PersonaDeltaEntry | null, targetFile: string | null): PromotionItem[] {
  if (!delta) {
    return [];
  }
  if (metadataBoolean(delta.metadata, 'weak_source_fragment')) {
    return [];
  }
  const items: PromotionItem[] = [];
  const itemIndexByContent = new Map<string, number>();
  const sourceExcerptBaseline = normalizePromotionContentKey(
    metadataText(delta.metadata, 'source_excerpt_clean') ??
      metadataText(delta.metadata, 'segment_excerpt') ??
      metadataStringArray(delta.metadata, 'talking_points')[0] ??
      '',
  );
  const deltaSummary = delta.trait?.trim() || null;
  const reviewInterpretation = metadataText(delta.metadata, 'owner_response_excerpt') ?? delta.notes?.trim() ?? null;
  const pushItem = (kind: PromotionItemKind, label: string, content: string, evidence?: string | null) => {
    const normalizedContent = content.trim();
    if (!normalizedContent) return;
    if (!meetsPromotionItemLengthFloor(kind, normalizedContent)) return;
    const dedupeKey = normalizePromotionContentKey(normalizedContent);
    if (!dedupeKey) return;
    if (kind === 'talking_point' && sourceExcerptBaseline && dedupeKey === sourceExcerptBaseline) {
      return;
    }
    const normalizedEvidence = evidence?.trim() || null;
    const proofStrength: PromotionItemProofStrength = kind === 'stat' ? 'strong' : normalizedEvidence ? 'weak' : 'none';
    const artifactSummary = kind === 'stat' ? normalizedContent : null;
    const artifactKind = kind === 'stat' ? 'metric_or_proof_point' : null;
    const proofSignal = kind === 'stat' ? normalizedContent : normalizedEvidence;
    const nextItem: PromotionItem = {
      id: stablePromotionItemId(kind, label, normalizedContent),
      kind,
      label,
      content: normalizedContent,
      evidence: normalizedEvidence,
      targetFile,
      artifactSummary,
      artifactKind,
      artifactRef: null,
      deltaSummary,
      reviewInterpretation,
      capabilitySignal: null,
      positioningSignal: null,
      leverageSignal: null,
      proofSignal,
      proofStrength,
      gateDecision: 'pending',
      gateReason: null,
      canonPurpose: null,
      canonValue: null,
      canonProof: null,
    };
    const existingIndex = itemIndexByContent.get(dedupeKey);
    if (existingIndex !== undefined) {
      const existing = items[existingIndex];
      const existingScore = promotionItemPriority(existing.kind) + (existing.evidence ? 1 : 0);
      const nextScore = promotionItemPriority(nextItem.kind) + (nextItem.evidence ? 1 : 0);
      if (nextScore > existingScore) {
        items[existingIndex] = nextItem;
      }
      return;
    }
    itemIndexByContent.set(dedupeKey, items.length);
    items.push(nextItem);
  };

  for (const entry of metadataArray(delta.metadata, 'talking_points')) {
    if (typeof entry === 'string') {
      pushItem('talking_point', 'Talking point', entry);
    }
  }
  for (const entry of metadataArray(delta.metadata, 'frameworks')) {
    if (entry && typeof entry === 'object') {
      const framework = entry as Record<string, unknown>;
      pushItem(
        'framework',
        String(framework.title || 'Framework'),
        String(framework.takeaway || framework.evidence || '').trim(),
        typeof framework.evidence === 'string' ? framework.evidence : null,
      );
    }
  }
  for (const entry of metadataArray(delta.metadata, 'anecdotes')) {
    if (entry && typeof entry === 'object') {
      const anecdote = entry as Record<string, unknown>;
      pushItem(
        'anecdote',
        String(anecdote.title || 'Anecdote'),
        String(anecdote.summary || anecdote.evidence || '').trim(),
        typeof anecdote.evidence === 'string' ? anecdote.evidence : null,
      );
    }
  }
  for (const entry of metadataArray(delta.metadata, 'phrase_candidates')) {
    if (typeof entry === 'string') {
      pushItem('phrase_candidate', 'Reusable phrase', entry);
    }
  }
  for (const entry of metadataArray(delta.metadata, 'stats')) {
    if (typeof entry === 'string') {
      pushItem('stat', 'Proof point', entry);
    }
  }
  return items;
}

function readPromotionItemsFromMetadata(
  metadata: Record<string, unknown> | undefined,
  key: 'selected_promotion_items' | 'committed_promotion_items' = 'selected_promotion_items',
): PromotionItem[] {
  const items = metadataArray(metadata, key);
  const parsed = items
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null;
      const record = entry as Record<string, unknown>;
      const kind = record.kind;
      const id = record.id;
      const label = record.label;
      const content = record.content;
      if (typeof kind !== 'string' || typeof id !== 'string' || typeof label !== 'string' || typeof content !== 'string') {
        return null;
      }
      return {
        id,
        kind: kind as PromotionItemKind,
        label,
        content,
        evidence: typeof record.evidence === 'string' ? record.evidence : null,
        targetFile:
          typeof record.targetFile === 'string' ? record.targetFile : typeof record.target_file === 'string' ? record.target_file : null,
        artifactSummary:
          typeof record.artifactSummary === 'string'
            ? record.artifactSummary
            : typeof record.artifact_summary === 'string'
            ? record.artifact_summary
            : null,
        artifactKind:
          typeof record.artifactKind === 'string'
            ? record.artifactKind
            : typeof record.artifact_kind === 'string'
            ? record.artifact_kind
            : null,
        artifactRef:
          typeof record.artifactRef === 'string' ? record.artifactRef : typeof record.artifact_ref === 'string' ? record.artifact_ref : null,
        deltaSummary:
          typeof record.deltaSummary === 'string'
            ? record.deltaSummary
            : typeof record.delta_summary === 'string'
            ? record.delta_summary
            : null,
        reviewInterpretation:
          typeof record.reviewInterpretation === 'string'
            ? record.reviewInterpretation
            : typeof record.review_interpretation === 'string'
            ? record.review_interpretation
            : null,
        capabilitySignal:
          typeof record.capabilitySignal === 'string'
            ? record.capabilitySignal
            : typeof record.capability_signal === 'string'
            ? record.capability_signal
            : null,
        positioningSignal:
          typeof record.positioningSignal === 'string'
            ? record.positioningSignal
            : typeof record.positioning_signal === 'string'
            ? record.positioning_signal
            : null,
        leverageSignal:
          typeof record.leverageSignal === 'string'
            ? record.leverageSignal
            : typeof record.leverage_signal === 'string'
            ? record.leverage_signal
            : null,
        proofSignal:
          typeof record.proofSignal === 'string'
            ? record.proofSignal
            : typeof record.proof_signal === 'string'
            ? record.proof_signal
            : null,
        proofStrength:
          record.proofStrength === 'weak' || record.proofStrength === 'strong'
            ? record.proofStrength
            : record.proof_strength === 'weak' || record.proof_strength === 'strong'
            ? record.proof_strength
            : 'none',
        gateDecision:
          record.gateDecision === 'allow' || record.gateDecision === 'hold' || record.gateDecision === 'block'
            ? record.gateDecision
            : record.gate_decision === 'allow' || record.gate_decision === 'hold' || record.gate_decision === 'block'
            ? record.gate_decision
            : 'pending',
        gateReason:
          typeof record.gateReason === 'string' ? record.gateReason : typeof record.gate_reason === 'string' ? record.gate_reason : null,
        canonPurpose:
          typeof record.canonPurpose === 'string'
            ? record.canonPurpose
            : typeof record.canon_purpose === 'string'
            ? record.canon_purpose
            : null,
        canonValue:
          typeof record.canonValue === 'string'
            ? record.canonValue
            : typeof record.canon_value === 'string'
            ? record.canon_value
            : null,
        canonProof:
          typeof record.canonProof === 'string'
            ? record.canonProof
            : typeof record.canon_proof === 'string'
            ? record.canon_proof
            : null,
      } satisfies PromotionItem;
    })
    .filter((item): item is PromotionItem => item !== null);
  return parsed;
}

function humanizePromotionKind(kind: PromotionItemKind) {
  switch (kind) {
    case 'talking_point':
      return 'Talking point';
    case 'framework':
      return 'Framework';
    case 'anecdote':
      return 'Anecdote';
    case 'phrase_candidate':
      return 'Reusable phrase';
    case 'stat':
      return 'Proof point';
    default:
      return kind;
  }
}

function humanizeGateDecision(decision: PromotionItemGateDecision) {
  if (decision === 'allow') return 'Allowed';
  if (decision === 'hold') return 'Held';
  if (decision === 'block') return 'Blocked';
  return 'Pending';
}

function gateDecisionTone(decision: PromotionItemGateDecision) {
  if (decision === 'allow') return '#22c55e';
  if (decision === 'hold') return '#f59e0b';
  if (decision === 'block') return '#f87171';
  return '#64748b';
}

function proofStrengthTone(strength: PromotionItemProofStrength) {
  if (strength === 'strong') return '#22c55e';
  if (strength === 'weak') return '#f59e0b';
  return '#64748b';
}

function inferPromotionGate(item: PromotionItem, targetFile: string | null): { decision: PromotionItemGateDecision; reason: string | null } {
  const effectiveTarget = item.targetFile ?? targetFile;
  const explicitDecision = item.gateDecision;
  if (effectiveTarget?.includes('history/initiatives')) {
    const hasArtifactAnchor = Boolean(item.artifactSummary || item.artifactRef || item.artifactKind);
    if (explicitDecision === 'allow' && hasArtifactAnchor && item.proofStrength === 'strong') {
      return { decision: 'allow', reason: item.gateReason || 'Artifact-backed proof is present.' };
    }
    if (explicitDecision === 'hold' && hasArtifactAnchor) {
      return { decision: 'hold', reason: item.gateReason || 'Artifact anchor exists, but the proof is not strong enough yet.' };
    }
    if (explicitDecision === 'block' && !hasArtifactAnchor) {
      return { decision: 'block', reason: item.gateReason || 'Initiatives canon requires a visible artifact, output, or metric.' };
    }
    if (hasArtifactAnchor && item.proofStrength === 'strong') {
      return { decision: 'allow', reason: item.gateReason || 'Artifact-backed proof is present.' };
    }
    if (hasArtifactAnchor) {
      return { decision: 'hold', reason: item.gateReason || 'Artifact anchor exists, but the proof is still weak.' };
    }
    return { decision: 'block', reason: item.gateReason || 'Initiatives canon requires a visible artifact, output, or metric.' };
  }
  return {
    decision: explicitDecision === 'hold' || explicitDecision === 'block' || explicitDecision === 'allow' ? explicitDecision : 'allow',
    reason: item.gateReason,
  };
}

function suggestAlternativeTarget(item: PromotionItem, targetFile: string | null) {
  const effectiveTarget = item.targetFile ?? targetFile;
  if (!effectiveTarget?.includes('history/initiatives')) {
    return null;
  }
  if (item.kind === 'anecdote') return 'history/story_bank.md';
  if (item.kind === 'phrase_candidate') return 'identity/VOICE_PATTERNS.md';
  return 'identity/claims.md';
}

function summarizePromotionItems(items: PromotionItem[], targetFile: string | null): PromotionGateSummary {
  if (items.length === 0) {
    return {
      decision: 'pending',
      reason: 'Select at least one fragment to see whether canon commit is allowed.',
      proofStrength: 'none',
      alternativeTarget: null,
      selectedCount: 0,
    };
  }
  const assessed = items.map((item) => ({ item, gate: inferPromotionGate(item, targetFile) }));
  const strongestProof = assessed.reduce<PromotionItemProofStrength>((current, entry) => {
    if (entry.item.proofStrength === 'strong') return 'strong';
    if (entry.item.proofStrength === 'weak' && current === 'none') return 'weak';
    return current;
  }, 'none');
  const block = assessed.find((entry) => entry.gate.decision === 'block');
  if (block) {
    return {
      decision: 'block',
      reason: block.gate.reason,
      proofStrength: strongestProof,
      alternativeTarget: suggestAlternativeTarget(block.item, targetFile),
      selectedCount: items.length,
    };
  }
  const hold = assessed.find((entry) => entry.gate.decision === 'hold');
  if (hold) {
    return {
      decision: 'hold',
      reason: hold.gate.reason,
      proofStrength: strongestProof,
      alternativeTarget: suggestAlternativeTarget(hold.item, targetFile),
      selectedCount: items.length,
    };
  }
  return {
    decision: 'allow',
    reason: assessed.find((entry) => entry.gate.reason)?.gate.reason || 'These selected fragments are ready for canon commit.',
    proofStrength: strongestProof,
    alternativeTarget: null,
    selectedCount: items.length,
  };
}

function resolvePromotionGate(item: PromotionItem, targetFile: string | null) {
  return inferPromotionGate(item, targetFile);
}

function promotionItemSortScore(item: PromotionItem, targetFile: string | null) {
  const gate = resolvePromotionGate(item, targetFile);
  const gateScore = gate.decision === 'allow' ? 6 : gate.decision === 'hold' ? 2 : gate.decision === 'block' ? -2 : 0;
  const proofScore = item.proofStrength === 'strong' ? 4 : item.proofStrength === 'weak' ? 2 : 0;
  const kindScore = promotionItemPriority(item.kind);
  const targetScore = targetPriority(item.targetFile ?? targetFile);
  return gateScore + proofScore + kindScore + targetScore;
}

function rankPromotionItems(items: PromotionItem[], targetFile: string | null) {
  return [...items].sort((left, right) => {
    const scoreDiff = promotionItemSortScore(right, targetFile) - promotionItemSortScore(left, targetFile);
    if (scoreDiff !== 0) {
      return scoreDiff;
    }
    const proofDiff = (right.proofStrength === 'strong' ? 2 : right.proofStrength === 'weak' ? 1 : 0) - (left.proofStrength === 'strong' ? 2 : left.proofStrength === 'weak' ? 1 : 0);
    if (proofDiff !== 0) {
      return proofDiff;
    }
    return left.content.localeCompare(right.content);
  });
}

function humanizeTargetFileLabel(targetFile: string | null) {
  if (!targetFile) return 'canon target';
  if (targetFile.includes('identity/claims')) return 'Claims';
  if (targetFile.includes('identity/VOICE_PATTERNS')) return 'Voice Patterns';
  if (targetFile.includes('history/story_bank')) return 'Story Bank';
  if (targetFile.includes('history/initiatives')) return 'Initiatives';
  if (targetFile.includes('identity/decision_principles')) return 'Decision Principles';
  if (targetFile.includes('prompts/content_pillars')) return 'Content Pillars';
  return targetFile;
}

function summarizeCommittedTargetFiles(targetFiles: string[] | null | undefined) {
  const labels = Array.from(new Set((targetFiles || []).map((targetFile) => humanizeTargetFileLabel(targetFile)).filter(Boolean)));
  if (labels.length === 0) return 'canon';
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, 2).join(', ')}, and ${labels.length - 2} more`;
}

function formatPromotionSuccessMessage(
  baseMessage: string | null | undefined,
  targetFiles: string[] | null | undefined,
  bundleWrittenFiles: string[] | null | undefined,
) {
  const normalized = (baseMessage || '').trim();
  const targetSummary = summarizeCommittedTargetFiles(targetFiles);
  const syncSummary = humanizeLocalBundleSyncState((bundleWrittenFiles || []).length > 0 ? 'synced' : 'pending');
  if (normalized) {
    return `${normalized} ${targetSummary !== 'canon' ? `${targetSummary}. ` : ''}${syncSummary}.`.trim();
  }
  if (targetSummary === 'canon') {
    return `Canon updated. ${syncSummary}.`;
  }
  return `Canon updated in ${targetSummary}. ${syncSummary}.`;
}

function humanizeLocalBundleSyncState(state: string | null | undefined) {
  const normalized = (state || '').trim().toLowerCase();
  if (normalized === 'synced') return 'Local bundle synced';
  if (normalized === 'failed') return 'Local sync failed';
  if (normalized === 'pending') return 'Local sync pending';
  return 'Local sync pending';
}

function localBundleSyncTone(state: string | null | undefined) {
  const normalized = (state || '').trim().toLowerCase();
  if (normalized === 'synced') return '#22c55e';
  if (normalized === 'failed') return '#f87171';
  if (normalized === 'pending') return '#f59e0b';
  return '#64748b';
}

function summarizeBundleFileResults(fileResults: Record<string, BundleFileResult> | null) {
  if (!fileResults) return null;
  const parts = Object.entries(fileResults)
    .filter(([, result]) => result && typeof result === 'object')
    .map(([path, result]) => {
      const label = humanizeTargetFileLabel(path);
      const additions = typeof result.added === 'number' ? `+${result.added}` : null;
      const skipped = typeof result.skipped === 'number' && result.skipped > 0 ? `${result.skipped} skipped` : null;
      return [label, additions, skipped].filter(Boolean).join(' · ');
    })
    .filter(Boolean);
  return parts.length > 0 ? parts.join(' | ') : null;
}

function candidateTargetsForPromotionItem(item: PromotionItem, fallbackTarget: string | null) {
  const targets: string[] = [];
  const push = (target: string | null | undefined) => {
    const normalized = typeof target === 'string' ? target.trim() : '';
    if (!normalized || targets.includes(normalized)) return;
    targets.push(normalized);
  };
  const current = item.targetFile ?? fallbackTarget;
  const likelyInitiative = Boolean(item.artifactSummary || item.artifactRef || item.proofStrength === 'strong');

  switch (item.kind) {
    case 'anecdote':
      push('history/story_bank.md');
      push('identity/claims.md');
      push(current);
      break;
    case 'phrase_candidate':
      push('identity/VOICE_PATTERNS.md');
      push('identity/claims.md');
      push(current);
      break;
    case 'framework':
      if (current?.includes('prompts/content_pillars')) {
        push('prompts/content_pillars.md');
      }
      if (current?.includes('identity/decision_principles')) {
        push('identity/decision_principles.md');
      }
      push('identity/decision_principles.md');
      push('prompts/content_pillars.md');
      push('identity/claims.md');
      push(current);
      break;
    case 'stat':
      if (likelyInitiative) {
        push('history/initiatives.md');
      }
      push('identity/claims.md');
      push(current);
      break;
    case 'talking_point':
    default:
      push(current);
      push('identity/claims.md');
      push('identity/decision_principles.md');
      if (likelyInitiative) {
        push('history/initiatives.md');
      }
      break;
  }

  return targets.slice(0, 4);
}

function bestTargetForPromotionItem(item: PromotionItem, fallbackTarget: string | null) {
  return candidateTargetsForPromotionItem(item, fallbackTarget)[0] ?? item.targetFile ?? fallbackTarget;
}

function candidateTargetsForItems(items: PromotionItem[], fallbackTarget: string | null) {
  const ordered: string[] = [];
  for (const item of items) {
    for (const target of candidateTargetsForPromotionItem(item, fallbackTarget)) {
      if (!ordered.includes(target)) {
        ordered.push(target);
      }
    }
  }
  if (ordered.length === 0 && fallbackTarget) {
    ordered.push(fallbackTarget);
  }
  return ordered.slice(0, 4);
}

function applyPromotionTargetOverrides(items: PromotionItem[], overrides: Record<string, string>) {
  if (items.length === 0) {
    return items;
  }
  return items.map((item) => {
    const override = overrides[item.id];
    if (!override || override === item.targetFile) {
      return item;
    }
    return { ...item, targetFile: override };
  });
}

function describePromotionTargets(items: PromotionItem[], fallbackTarget: string | null) {
  const targets = Array.from(new Set(items.map((item) => item.targetFile ?? fallbackTarget).filter((value): value is string => Boolean(value))));
  if (targets.length === 0) {
    return humanizeTargetFileLabel(fallbackTarget);
  }
  return targets.map((target) => humanizeTargetFileLabel(target)).join(', ');
}

function hasSelectablePromotionMetadata(metadata: Record<string, unknown> | undefined) {
  return (
    metadataArray(metadata, 'talking_points').length > 0 ||
    metadataArray(metadata, 'frameworks').length > 0 ||
    metadataArray(metadata, 'anecdotes').length > 0 ||
    metadataArray(metadata, 'phrase_candidates').length > 0 ||
    metadataArray(metadata, 'stats').length > 0
  );
}

function promotionSignalCount(metadata: Record<string, unknown> | undefined) {
  const explicit = metadata?.queue_promotion_signal_count;
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    return explicit;
  }
  return (
    metadataArray(metadata, 'talking_points').length +
    metadataArray(metadata, 'frameworks').length +
    metadataArray(metadata, 'anecdotes').length +
    metadataArray(metadata, 'phrase_candidates').length +
    metadataArray(metadata, 'stats').length
  );
}

function isPromotionReady(status: string, metadata: Record<string, unknown> | undefined) {
  if (typeof metadata?.queue_promotion_ready === 'boolean') {
    return metadata.queue_promotion_ready;
  }
  const normalized = (status || 'draft').toLowerCase();
  return (normalized === 'in_review' || normalized === 'reviewed') && hasSelectablePromotionMetadata(metadata);
}

function targetPriority(targetFile: string | null) {
  if (!targetFile) return 1;
  if (targetFile.includes('identity/claims')) return 5;
  if (targetFile.includes('identity/VOICE_PATTERNS')) return 5;
  if (targetFile.includes('identity/philosophy')) return 4;
  if (targetFile.includes('identity/decision_principles')) return 4;
  if (targetFile.includes('prompts/content_pillars')) return 4;
  if (targetFile.includes('history/story_bank')) return 3;
  if (targetFile.includes('history/wins')) return 3;
  if (targetFile.includes('history/initiatives')) return 2;
  if (targetFile.includes('history/resume')) return 1;
  return 1;
}

function recencyPriority(createdAt: string) {
  const ageMs = Date.now() - timestampMs(createdAt);
  const dayMs = 24 * 60 * 60 * 1000;
  if (ageMs <= dayMs) return 4;
  if (ageMs <= 3 * dayMs) return 3;
  if (ageMs <= 7 * dayMs) return 2;
  if (ageMs <= 30 * dayMs) return 1;
  return 0;
}

function reviewStatePriority(status: string, metadata: Record<string, unknown> | undefined) {
  const normalized = (status || 'draft').toLowerCase();
  if (isPromotionReady(normalized, metadata)) return 6;
  if (normalized === 'in_review') return 5;
  if (normalized === 'reviewed') return 4;
  if (normalized === 'pending') return 3;
  if (normalized === 'draft') return 2;
  return 0;
}

function reviewSourcePriority(reviewSource: string | null) {
  if (reviewSource === 'brain.persona.ui') return 3;
  if (reviewSource === 'linkedin_workspace.feed_quote') return 2;
  if (reviewSource === 'long_form_media.segment') return 1;
  return 0;
}

function looksWeakLongFormText(text: string) {
  const normalized = text.toLowerCase();
  return [
    '# clean transcript',
    '**open questions:**',
    'machine learning is a subset of ai',
    'that element in green',
    "my team and i thought",
    "i'm super proud",
    'alive in spirit',
    'not very well done',
    'why does it have to be that way',
  ].some((pattern) => normalized.includes(pattern));
}

function shouldMuteActivePersonaDelta(delta: PersonaDeltaEntry, promotionCandidateCount: number) {
  if (typeof delta.metadata?.queue_muted === 'boolean') {
    return delta.metadata.queue_muted;
  }
  const reviewSource = metadataText(delta.metadata, 'review_source');
  if (reviewSource !== 'long_form_media.segment') {
    return false;
  }
  if (metadataText(delta.metadata, 'sync_state') === 'stale_segment') {
    return true;
  }
  if (looksWeakLongFormText(delta.trait) || looksWeakLongFormText(delta.notes || '')) {
    return true;
  }
  if (promotionCandidateCount === 0) {
    return true;
  }
  const hasStrongSignal =
    metadataArray(delta.metadata, 'frameworks').length > 0 ||
    metadataArray(delta.metadata, 'anecdotes').length > 0 ||
    metadataArray(delta.metadata, 'phrase_candidates').length > 0;
  return !hasStrongSignal && promotionCandidateCount < 3;
}

function personaDeltaPriorityScore(delta: PersonaDeltaEntry, promotionCandidateCount: number, muted: boolean) {
  const explicit = delta.metadata?.queue_priority_score;
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    return explicit;
  }
  const targetFile = metadataText(delta.metadata, 'target_file');
  const reviewSource = metadataText(delta.metadata, 'review_source');
  let score = 0;
  score += targetPriority(targetFile) * 4;
  score += promotionCandidateCount * 2;
  score += recencyPriority(delta.created_at);
  score += reviewStatePriority(delta.status, delta.metadata);
  score += reviewSourcePriority(reviewSource);
  if (metadataBoolean(delta.metadata, 'pending_promotion')) {
    score += 4;
  }
  if (muted) {
    score -= 8;
  }
  return score;
}

function isWorkspaceApproved(status: string, metadata: Record<string, unknown> | undefined) {
  const normalized = (status || 'draft').toLowerCase();
  const reviewSource = metadataText(metadata, 'review_source');
  const approvalState = metadataText(metadata, 'approval_state');
  return normalized === 'approved' && (reviewSource === 'linkedin_workspace.feed_quote' || approvalState === 'approved_from_workspace');
}

function isBrainPendingReview(status: string, metadata: Record<string, unknown> | undefined) {
  const normalized = (status || 'draft').toLowerCase();
  if (normalized === 'draft' || normalized === 'pending' || normalized === 'in_review') {
    return true;
  }
  return normalized === 'reviewed' && hasSelectablePromotionMetadata(metadata) && !metadataBoolean(metadata, 'pending_promotion');
}

function personaDeltaStage(delta: PersonaDeltaEntry) {
  const queuedStage = metadataText(delta.metadata, 'queue_stage');
  if (queuedStage) return queuedStage;
  const status = (delta.status || 'draft').toLowerCase();
  if (status === 'committed') return 'committed';
  if (metadataBoolean(delta.metadata, 'pending_promotion')) return 'pending_promotion';
  if (isWorkspaceApproved(status, delta.metadata)) return 'workspace_saved';
  if (isBrainPendingReview(status, delta.metadata)) return 'brain_pending_review';
  if (status === 'approved') return 'approved_unpromoted';
  return status || 'draft';
}

function findPackBySection(packs: PersonaPack[], relPath: string | null) {
  if (!relPath) return null;
  return packs.find((pack) => pack.sections.some((section) => section.path === relPath)) ?? null;
}

function findPackSection(packs: PersonaPack[], relPath: string | null) {
  if (!relPath) return null;
  for (const pack of packs) {
    const section = pack.sections.find((item) => item.path === relPath);
    if (section) {
      return section;
    }
  }
  return null;
}

function briefSourceIntelligence(entry: DailyBriefEntry | null) {
  return entry ? metadataObject<BriefSourceIntelligence>(entry.metadata, 'source_intelligence') : null;
}

function briefStreamItems(entry: DailyBriefEntry | null) {
  const overlay = briefSourceIntelligence(entry);
  return Array.isArray(overlay?.brief_stream) ? overlay.brief_stream.filter((item): item is BriefSourceIntelligenceCandidate => Boolean(item)) : [];
}

function buildPostingWorkspaceHref(item: BriefSourceIntelligenceCandidate, mode: 'post' | 'comment') {
  const params = new URLSearchParams();
  params.set('mode', mode);
  params.set('autoplay', '1');
  if (item.item_key?.trim()) params.set('itemKey', item.item_key.trim());
  if (item.title?.trim()) params.set('title', item.title.trim());
  if (item.summary?.trim()) params.set('summary', item.summary.trim());
  if (item.hook?.trim()) params.set('hook', item.hook.trim());
  if (item.priority_lane?.trim()) params.set('priorityLane', item.priority_lane.trim());
  if (item.source_kind?.trim()) params.set('sourceKind', item.source_kind.trim());
  if (item.route_reason?.trim()) params.set('routeReason', item.route_reason.trim());
  if (item.target_file?.trim()) params.set('targetFile', item.target_file.trim());
  if (item.section?.trim()) params.set('section', item.section.trim());
  if (item.source_url?.trim()) params.set('sourceUrl', item.source_url.trim());
  if (item.source_path?.trim()) params.set('sourcePath', item.source_path.trim());
  return `/workspace/posting?${params.toString()}`;
}

function numberMeta(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '0';
}

function humanizeSnakeCase(value: string | null | undefined) {
  if (!value) return 'Unknown';
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function briefConsumerLaneDefinition(lane: BriefConsumerLane) {
  if (lane === 'source_only') {
    return {
      label: 'Source only',
      tone: '#64748b',
      description: 'Captured upstream signal. Keep it in source intelligence unless it earns a stronger promotion.',
    };
  }
  if (lane === 'brief_only') {
    return {
      label: 'Brief only',
      tone: '#38bdf8',
      description: 'Useful cycle awareness. Mention it in the brief, but do not treat it as persona or PM by default.',
    };
  }
  if (lane === 'persona_candidate') {
    return {
      label: 'Persona candidate',
      tone: '#22c55e',
      description: 'Potential durable identity, worldview, or canon signal. Judge it in Persona before preserving it.',
    };
  }
  if (lane === 'post_candidate') {
    return {
      label: 'Post candidate',
      tone: '#f59e0b',
      description: 'Expression-ready material for comments, reposts, or post seeds. Public output is the main consumer.',
    };
  }
  return {
    label: 'Route to PM',
    tone: '#fb7185',
    description: 'Worth explicit operational routing after judgment. Do not treat it as PM work automatically.',
  };
}

function briefConsumerLaneGuidance(lane: BriefConsumerLane) {
  if (lane === 'source_only') {
    return 'Keep this upstream for now. It is a source artifact, not yet a brief, persona, or PM commitment.';
  }
  if (lane === 'brief_only') {
    return 'This belongs in situational awareness first. It helps the daily brief, but it does not deserve persona or PM by default.';
  }
  if (lane === 'persona_candidate') {
    return 'This may reveal durable truth about Johnnie. Use Persona to decide whether it becomes identity, worldview, or canon.';
  }
  if (lane === 'post_candidate') {
    return 'This is mainly an expression opportunity. Use posting or commentary first unless your reaction exposes durable persona truth.';
  }
  return 'This looks operationally meaningful, but it still needs explicit routing. Let judgment happen before it becomes executable work.';
}

function briefConsumerLanesForCandidate(item: BriefSourceIntelligenceCandidate): BriefConsumerLane[] {
  const explicitLane = (item.handoff_lane || '').trim() as BriefConsumerLane | '';
  if (explicitLane === 'source_only' || explicitLane === 'brief_only' || explicitLane === 'persona_candidate' || explicitLane === 'post_candidate' || explicitLane === 'route_to_pm') {
    return [explicitLane];
  }
  const lanes: BriefConsumerLane[] = [];
  const section = (item.section || '').trim();
  const responseModes = (item.response_modes ?? []).map((value) => value.trim()).filter(Boolean);
  const pmSignalText = [item.route_reason, item.summary, item.priority_lane, item.target_file]
    .map((value) => value?.toLowerCase?.() || '')
    .join(' ');
  const hasExplicitPMSignal = /(pm|execution|dispatch|backlog|standup|queue|workflow|ops)/.test(pmSignalText);

  if (section === 'belief_evidence') {
    lanes.push('persona_candidate');
  }
  if (section === 'post_seed') {
    lanes.push('post_candidate');
  }

  if (responseModes.some((mode) => mode === 'belief_evidence')) {
    lanes.push('persona_candidate');
  }
  if (responseModes.some((mode) => mode === 'post_seed' || mode === 'comment' || mode === 'repost')) {
    lanes.push('post_candidate');
  }
  if (hasExplicitPMSignal) {
    lanes.push('route_to_pm');
  }

  if (lanes.length === 0) {
    lanes.push('brief_only');
  }

  return Array.from(new Set(lanes));
}

function compactBriefCandidate(item: BriefSourceIntelligenceCandidate) {
  const title = item.title?.trim() || 'Untitled candidate';
  const primaryLane = briefConsumerLanesForCandidate(item)[0] ?? 'brief_only';
  const parts = [
    briefConsumerLaneDefinition(primaryLane).label,
    item.priority_lane?.trim(),
    item.target_file?.trim(),
    item.handoff_reason?.trim(),
    item.route_reason?.trim(),
  ].filter(Boolean);
  return parts.length > 0 ? `${title} · ${parts.join(' · ')}` : title;
}

function compactReviewItem(item: BriefSourceIntelligenceReviewItem) {
  const trait = item.trait?.trim() || 'Untitled review item';
  const parts = [
    briefConsumerLaneDefinition('persona_candidate').label,
    item.belief_relation ? humanizeBeliefRelation(item.belief_relation) : null,
    humanizeReviewSource(item.review_source ?? null),
  ].filter(Boolean);
  return parts.length > 0 ? `${trait} · ${parts.join(' · ')}` : trait;
}

function truncateText(text: string, limit: number) {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trimEnd()}\n…`;
}

function buildReviewHeadline(delta: PersonaDeltaEntry, targetFile: string | null) {
  const sourceTitle = metadataText(delta.metadata, 'evidence_source');
  const reviewSource = metadataText(delta.metadata, 'review_source');
  if (reviewSource === 'long_form_media.segment' && sourceTitle) {
    return sourceTitle;
  }
  if (sourceTitle && targetFile) {
    return `${sourceTitle} → ${humanizeTargetPath(targetFile)}`;
  }
  if (sourceTitle) {
    return sourceTitle;
  }
  if (!targetFile) {
    return delta.trait;
  }
  return `${delta.trait} → ${humanizeTargetPath(targetFile)}`;
}

function buildReviewReason(delta: PersonaDeltaEntry, targetFile: string | null, contextPath: string | null) {
  const explicitReason = metadataText(delta.metadata, 'why_showing');
  if (explicitReason) {
    return explicitReason;
  }
  const reviewSource = metadataText(delta.metadata, 'review_source');
  if (reviewSource === 'long_form_media.segment') {
    const contextLabel = contextPath ? ` The closest live canon context is ${contextPath}.` : '';
    return `Start with the source itself. Decide what the segment is actually saying before you worry about canon routing, workspace routing, or file placement.${contextLabel}`;
  }
  const targetLabel = targetFile ? humanizeTargetPath(targetFile) : 'the persona bundle';
  const contextLabel = contextPath ? ` The closest live context is pulled from ${contextPath}.` : '';
  return `This is still pending, so I need your judgment before it becomes part of ${targetLabel}.${contextLabel} I am showing it now because it looks durable enough to affect how your initiatives, voice, or narrative get represented.`;
}

function buildReviewAsk(delta: PersonaDeltaEntry, targetFile: string | null) {
  const explicitPrompt = metadataText(delta.metadata, 'review_prompt');
  if (explicitPrompt) {
    return explicitPrompt;
  }
  if (metadataBoolean(delta.metadata, 'weak_source_fragment')) {
    return 'First decide whether this source is meaningful enough to keep at all. If it depends on too much missing context, leave it as source intelligence or ignore it.';
  }
  if (metadataText(delta.metadata, 'review_source') === 'long_form_media.segment') {
    return 'What is the real point of the source, what do you agree or disagree with, and should it stay source intelligence, become memory, turn into a post seed, or affect canon?';
  }
  const targetLabel = targetFile ? humanizeTargetPath(targetFile) : 'the persona bundle';
  return `Tell me if this belongs in ${targetLabel}, what is accurate about it, what nuance is missing, and how you would phrase it in your own voice.`;
}

function humanizeTargetPath(path: string) {
  return path
    .replace(/^identity\//, 'identity / ')
    .replace(/^history\//, 'history / ')
    .replace(/^prompts\//, 'prompts / ')
    .replace(/\.md$/i, '')
    .replace(/[_-]+/g, ' ');
}

function buildReflectionTopics(delta: PersonaDeltaEntry | null, targetFile: string | null, selectedItems: PromotionItem[] = []) {
  const topics = ['persona', 'reflection'];
  if (delta?.persona_target) topics.push(delta.persona_target);
  if (targetFile) topics.push(targetFile);
  for (const item of selectedItems) {
    if (item.targetFile) {
      topics.push(item.targetFile);
    }
  }
  return Array.from(new Set(topics));
}

function buildReflectionCaptureText({
  delta,
  reflectionText,
  targetFile,
  sectionContent,
  selectedItems,
}: {
  delta: PersonaDeltaEntry | null;
  reflectionText: string;
  targetFile: string | null;
  sectionContent: string | null;
  selectedItems: PromotionItem[];
}) {
  const lines = [
    '# Persona Reflection',
    '',
    `Trait: ${delta?.trait ?? 'General reflection'}`,
    `Persona target: ${delta?.persona_target ?? 'general'}`,
    `Target file: ${targetFile ?? 'not assigned'}`,
    delta?.capture_id ? `Linked capture: ${delta.capture_id}` : 'Linked capture: none',
    '',
    '## Candidate Notes',
    delta?.notes?.trim() || 'No candidate notes provided.',
    '',
  ];

  if (selectedItems.length > 0) {
    const targetSummary = describePromotionTargets(selectedItems, targetFile);
    lines.push('## Selected For Promotion');
    lines.push(`Target files: ${targetSummary}`);
    for (const item of selectedItems) {
      lines.push(`- [${humanizePromotionKind(item.kind)} | ${humanizeTargetFileLabel(item.targetFile ?? targetFile)}] ${item.label}: ${item.content}`);
      if (item.evidence) {
        lines.push(`  Evidence: ${item.evidence}`);
      }
    }
    lines.push('');
  }

  if (sectionContent) {
    lines.push('## Current Canonical Context', truncateText(sectionContent, 1200), '');
  }

  lines.push('## My Reaction', reflectionText.trim());
  return lines.join('\n');
}

function formatTimestamp(value: Date | string) {
  return formatUiTimestamp(value);
}

function formatTimestampValue(value: string) {
  return formatTimestamp(value);
}

function timestampMs(value: string) {
  const parsed = parseUiDate(value);
  return parsed ? parsed.getTime() : 0;
}

function humanizeReviewSource(source: string | null) {
  if (!source) return 'No source';
  if (source === 'long_form_media.segment') return 'Long-form segment';
  if (source === 'linkedin_workspace.feed_quote') return 'Workspace approval';
  if (source === 'brain.daily_brief.stream') return 'Brief stream reaction';
  if (source === 'brain.persona.ui') return 'Brain review';
  return source.replace(/[_./-]+/g, ' ');
}

function humanizeBeliefRelation(value: string | null) {
  if (!value) return 'Unknown relation';
  if (value === 'agreement') return 'Agreement';
  if (value === 'qualified_agreement') return 'Qualified agreement';
  if (value === 'disagreement') return 'Disagreement';
  if (value === 'translation') return 'Translation';
  if (value === 'experience_match') return 'Experience match';
  if (value === 'system_translation') return 'System translation';
  return value.replace(/[_-]+/g, ' ');
}

function humanizePrimaryRoute(value: string | null) {
  if (!value) return 'Unknown route';
  if (value === 'belief_evidence') return 'Possible canon candidate';
  if (value === 'post_seed') return 'Post seed';
  if (value === 'comment') return 'Direct reaction';
  if (value === 'repost') return 'Repost';
  return value.replace(/[_-]+/g, ' ');
}

function humanizeResponseKind(value: 'agree' | 'disagree' | 'nuance' | 'story' | 'language') {
  if (value === 'agree') return 'Agreement';
  if (value === 'disagree') return 'Disagreement';
  if (value === 'nuance') return 'Nuance';
  if (value === 'story') return 'Personal story';
  return 'Wording';
}

function humanizeSavedResponseKind(value: string) {
  if (value === 'agree' || value === 'disagree' || value === 'nuance' || value === 'story' || value === 'language') {
    return humanizeResponseKind(value);
  }
  return value.replace(/[_-]+/g, ' ');
}

function humanizeCanonicalMemoryTarget(value: string) {
  if (value === 'persistent_state') return 'Persistent State';
  if (value === 'learnings') return 'Learnings';
  if (value === 'chronicle') return 'Codex Chronicle';
  return value.replace(/[_-]+/g, ' ');
}

function compactStandupKind(value: string) {
  if (value === 'auto') return 'Auto';
  if (value === 'executive_ops') return 'Executive';
  if (value === 'operations') return 'Operations';
  if (value === 'weekly_review') return 'Weekly Review';
  if (value === 'saturday_vision') return 'Saturday Vision';
  if (value === 'workspace_sync') return 'Workspace';
  return value.replace(/[_-]+/g, ' ');
}

function isBrainWorkspaceKey(value: string): value is BrainWorkspaceKey {
  return brainWorkspaceOptions.some((option) => option.key === value);
}

function canonicalBrainWorkspaceKey(value: string | null | undefined): BrainWorkspaceKey | null {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (
    normalized === 'feezie' ||
    normalized === 'feezie os' ||
    normalized === 'feezie-os' ||
    normalized === 'linkedin' ||
    normalized === 'linkedin os' ||
    normalized === 'linkedin-os' ||
    normalized === 'linkedin content os' ||
    normalized === 'linkedin-content-os'
  ) {
    return 'feezie-os';
  }
  return isBrainWorkspaceKey(normalized) ? normalized : null;
}

function canonicalBrainWorkspaceKeys(values: string[]): BrainWorkspaceKey[] {
  const keys: BrainWorkspaceKey[] = [];
  for (const value of values) {
    const key = canonicalBrainWorkspaceKey(value);
    if (key && !keys.includes(key)) {
      keys.push(key);
    }
  }
  return keys;
}

function fallbackBrainWorkspaceKeys(delta: PersonaDeltaEntry | null): BrainWorkspaceKey[] {
  const keys: BrainWorkspaceKey[] = [];
  const push = (workspaceKey: BrainWorkspaceKey) => {
    if (!keys.includes(workspaceKey)) {
      keys.push(workspaceKey);
    }
  };

  push('feezie-os');

  const metadataWorkspace = metadataText(delta?.metadata, 'workspace_key');
  const canonicalMetadataWorkspace = canonicalBrainWorkspaceKey(metadataWorkspace);
  if (canonicalMetadataWorkspace) {
    push(canonicalMetadataWorkspace);
  }

  for (const priorWorkspace of metadataStringArray(delta?.metadata, 'last_brain_route_workspace_keys')) {
    const canonicalPriorWorkspace = canonicalBrainWorkspaceKey(priorWorkspace);
    if (canonicalPriorWorkspace) {
      push(canonicalPriorWorkspace);
    }
  }

  if (!keys.includes('shared_ops')) {
    push('shared_ops');
  }

  return keys;
}

function labelForBrainWorkspace(workspaceKey: string) {
  const canonical = canonicalBrainWorkspaceKey(workspaceKey);
  return brainWorkspaceOptions.find((option) => option.key === canonical)?.label ?? humanizeSnakeCase(workspaceKey);
}

function suggestStandupKindForWorkspace(workspaceKey: string) {
  return workspaceKey === 'shared_ops' ? 'executive_ops' : 'workspace_sync';
}

function executionModelForBrainWorkspace(workspaceKey: string) {
  const canonical = canonicalBrainWorkspaceKey(workspaceKey) ?? workspaceKey;
  if (canonical === 'shared_ops' || canonical === 'feezie-os') {
    return {
      manager: 'Jean-Claude',
      executor: 'Jean-Claude',
      mode: 'direct' as const,
    };
  }
  const workspaceAgents: Record<string, string> = {
    'fusion-os': 'Fusion Systems Operator',
    easyoutfitapp: 'Easy Outfit App Operator Agent',
    'ai-swag-store': 'AI Swag Store Operator Agent',
    agc: 'AGC Operator Agent',
  };
  return {
    manager: 'Jean-Claude',
    executor: workspaceAgents[canonical] || 'Workspace Agent',
    mode: 'delegated' as const,
  };
}

function participantsForBrainRoute(workspaceKey: string, standupKind: string) {
  if (standupKind === 'auto') {
    return participantsForBrainRoute(workspaceKey, suggestStandupKindForWorkspace(workspaceKey));
  }
  if (standupKind === 'executive_ops' || standupKind === 'operations' || standupKind === 'weekly_review' || standupKind === 'saturday_vision') {
    return ['Jean-Claude', 'Neo', 'Yoda'];
  }
  const canonical = canonicalBrainWorkspaceKey(workspaceKey) ?? workspaceKey;
  if (canonical === 'shared_ops' || canonical === 'feezie-os') {
    return ['Jean-Claude', 'Neo', 'Yoda'];
  }
  const executionModel = executionModelForBrainWorkspace(canonical);
  return executionModel.mode === 'delegated' ? ['Jean-Claude', executionModel.executor] : ['Jean-Claude'];
}

function reviewQueueCardTitle(delta: PersonaDeltaEntry) {
  return metadataText(delta.metadata, 'evidence_source') ?? truncateText(delta.trait, 96);
}

function reviewQueueCardSummary(delta: PersonaDeltaEntry) {
  return (
    metadataText(delta.metadata, 'source_excerpt_clean') ??
    metadataText(delta.metadata, 'segment_excerpt') ??
    metadataText(delta.metadata, 'system_hypothesis') ??
    truncateText(delta.trait, 140)
  );
}

function defaultBrainPMTitle(delta: PersonaDeltaEntry) {
  return `Operationalize reviewed signal: ${truncateText(delta.trait, 96).replace(/\n/g, ' ')}`;
}

function inferDocGroup(path: string) {
  const normalizedPath = path.replace(/^(\.\.\/)+/, '');
  if (normalizedPath.startsWith('memory/')) return 'Canonical Memory';
  if (normalizedPath.startsWith('SOPs/')) return 'Operating Docs';
  if (normalizedPath.startsWith('docs/')) return 'System Docs';
  if (normalizedPath.startsWith('knowledge/source-intelligence/')) return 'Source Intelligence';
  if (normalizedPath.startsWith('knowledge/persona/')) return 'Persona Bundle';
  if (normalizedPath.startsWith('knowledge/aiclone/')) return 'Knowledge Docs';
  if (normalizedPath.startsWith('workspaces/')) return 'Workspace Reference';
  return 'Reference Docs';
}

function mergeBrainDocs(docs: DocEntry[], workspaceSnapshot: BrainWorkspaceSnapshot | null) {
  const registry = new Map<string, DocEntry>();
  for (const doc of docs) {
    registry.set(doc.path, {
      ...doc,
      group: doc.group ?? inferDocGroup(doc.path),
    });
  }
  for (const doc of workspaceSnapshot?.doc_entries ?? []) {
    registry.set(doc.path, {
      name: doc.name,
      path: doc.path,
      snippet: doc.snippet,
      content: doc.content,
      updatedAt: doc.updatedAt,
      group: inferDocGroup(doc.path),
    });
  }
  for (const file of workspaceSnapshot?.workspace_files ?? []) {
    const group = file.group ?? '';
    const shouldInclude =
      group.startsWith('persona-bundle/') ||
      group.startsWith('linkedin-content-os/docs') ||
      group.startsWith('linkedin-content-os/analytics');
    if (!shouldInclude || registry.has(file.path)) {
      continue;
    }
    registry.set(file.path, {
      name: file.name,
      path: file.path,
      snippet: file.snippet,
      content: file.content,
      updatedAt: file.updatedAt,
      group: group.startsWith('persona-bundle/') ? 'Persona Bundle' : 'Workspace Reference',
    });
  }
  return Array.from(registry.values()).sort((left, right) => left.path.localeCompare(right.path));
}
