'use client';

import Link from 'next/link';
import { Suspense, type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { LinkedinWorkspaceSurface } from '@/app/workspace/WorkspaceClient';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { getApiUrl } from '@/lib/api-client';
import { formatUiDate, formatUiDateWithWeekday, formatUiNumber, formatUiTime, formatUiTimestamp } from '@/lib/ui-dates';

const API_URL = getApiUrl();
const REPO_ROOT = '/Users/neo/.openclaw/workspace';
const WORKSPACE_ROOT_BY_KEY: Record<string, string> = {
  'linkedin-os': `${REPO_ROOT}/workspaces/linkedin-content-os`,
  'fusion-os': `${REPO_ROOT}/workspaces/fusion-os`,
  easyoutfitapp: `${REPO_ROOT}/workspaces/easy-outfit`,
  'ai-swag-store': `${REPO_ROOT}/workspaces/ai-swag-store`,
  agc: `${REPO_ROOT}/workspaces/agc`,
  shared_ops: `${REPO_ROOT}/workspaces/shared-ops`,
};
const REPO_RELATIVE_PREFIXES = ['knowledge/', 'memory/', 'workspaces/', 'frontend/', 'backend/', 'scripts/', 'automations/'];
const WORKSPACE_RELATIVE_PREFIXES = ['drafts/', 'docs/', 'analytics/', 'plans/', 'research/', 'briefings/', 'dispatch/', 'memory/'];

function pickWorkspacePath(files: WorkspaceFile[], workspaceKey?: string): string | null {
  if (!workspaceKey) {
    return null;
  }
  const match =
    files.find((file) => file.path.includes(`/workspaces/${workspaceKey}/`)) ??
    files.find((file) => file.group.startsWith(workspaceKey));
  return match?.path ?? null;
}

export type WorkspaceFile = {
  group: string;
  name: string;
  path: string;
  snippet: string;
  content: string;
  updatedAt: string;
};

export type DocReference = {
  name: string;
  path: string;
  snippet: string;
  content: string;
  updatedAt: string;
};

export type ExecutiveArtifact = {
  id: string;
  label: string;
  category: 'codex' | 'openclaw' | 'local' | 'memory';
  path?: string;
  updatedAt?: string;
  summary: string;
  detail: string;
};

export type ChronicleEntry = {
  id: string;
  createdAt?: string;
  workspaceKey: string;
  scope?: string;
  summary: string;
  signalTypes: string[];
  decisions: string[];
  blockers: string[];
  followUps: string[];
  tags: string[];
};

export type StandupPrepPacket = {
  id: string;
  standupKind: string;
  workspaceKey: string;
  ownerAgent: string;
  generatedAt?: string;
  summary: string;
  agenda: string[];
  blockers: string[];
  commitments: string[];
  needs: string[];
  artifactDeltas: string[];
  pmSnapshot?: Record<string, unknown>;
  pmUpdateTitles: string[];
  memoryPromotions: string[];
  sourcePaths: string[];
  path: string;
};

export type PMRecommendationItem = {
  workspaceKey: string;
  scope: string;
  ownerAgent: string;
  title: string;
  status: string;
  reason: string;
};

export type PMRecommendationPacket = {
  id: string;
  workspaceKey: string;
  createdAt?: string;
  path: string;
  items: PMRecommendationItem[];
};

export type ExecutiveFeed = {
  artifacts: ExecutiveArtifact[];
  chronicleEntries: ChronicleEntry[];
  standupPreps: StandupPrepPacket[];
  pmRecommendations: PMRecommendationPacket[];
};

type ComplianceMetrics = {
  approvals_last_24h: number;
  prospects_with_email: number;
  total_system_events?: number;
};

type SystemLog = {
  id?: string;
  component?: string;
  level?: string;
  message?: string;
  timestamp?: string;
};

type HealthPayload = {
  status?: string;
  service?: string;
  version?: string;
  firestore?: string;
};

type Automation = {
  id: string;
  name: string;
  schedule: string;
  cron: string;
  status: string;
  channel: string;
  metrics?: Record<string, string>;
  source?: string;
  runtime?: string | null;
  last_status?: string;
  scope?: string;
  workspace_key?: string | null;
  last_run_at?: string;
  next_run_at?: string;
};

type AutomationRun = {
  id: string;
  automation_id: string;
  automation_name: string;
  status: string;
  run_at?: string | null;
  finished_at?: string | null;
  action_required?: boolean;
  owner_agent?: string | null;
  scope?: string;
  workspace_key?: string | null;
  metadata?: Record<string, unknown>;
};

type PMCard = {
  id: string;
  title: string;
  owner?: string | null;
  status: string;
  source?: string | null;
  link_type?: string | null;
  link_id?: string | null;
  due_at?: string | null;
  payload?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

type PMReviewAttentionClass = 'needs_owner' | 'needs_host' | 'stale' | 'autonomous' | 'fyi';

type PMReviewPolicyPayload = {
  attention_class?: PMReviewAttentionClass;
  attention_reason?: string | null;
  policy_label?: string | null;
  interrupt_policy?: string | null;
  recommended_resolution_mode?: PMCardResolutionMode | null;
  suggested_next_title?: string | null;
  suggested_next_reason?: string | null;
  auto_resolve_eligible?: boolean;
  owner_decision_gate?: boolean;
};

type PMReviewHygieneResult = {
  resolved_count?: number;
  resolved?: Array<{
    card_id: string;
    title: string;
    workspace_key: string;
    rule?: string;
    reason?: string;
  }>;
};

type PMAutoProgressItem = {
  card_id: string;
  title: string;
  workspace_key: string;
  action?: 'approve' | 'return' | 'blocked';
  resolution_mode?: PMCardResolutionMode | null;
  rule?: string;
  reason?: string;
  successor_card_id?: string | null;
  successor_card_title?: string | null;
  host_action_card_id?: string | null;
  host_action_card_title?: string | null;
};

type PMAutoProgressResult = {
  processed_count?: number;
  advanced_count?: number;
  returned_count?: number;
  escalated_count?: number;
  closed_count?: number;
  continued_count?: number;
  processed?: PMAutoProgressItem[];
  audit_entry?: PMAutoProgressAuditEntry;
};

const OWNER_REVIEW_ACTIVE_WIP_LIMIT = 3;

type PMAutoProgressAuditEntry = {
  run_id: string;
  processed_at: string;
  processed_count: number;
  advanced_count: number;
  returned_count: number;
  escalated_count: number;
  closed_count: number;
  continued_count: number;
  processed: PMAutoProgressItem[];
};

type PMAutoProgressAuditReport = {
  path?: string;
  window_hours?: number;
  summary?: {
    runs?: number;
    processed_count?: number;
    advanced_count?: number;
    returned_count?: number;
    escalated_count?: number;
    closed_count?: number;
    continued_count?: number;
  };
  entries?: PMAutoProgressAuditEntry[];
};

type ExecutionQueueEntry = {
  card_id: string;
  title: string;
  workspace_key: string;
  pm_status: string;
  execution_state: string;
  manager_agent: string;
  target_agent: string;
  workspace_agent?: string | null;
  execution_mode: string;
  requested_by?: string | null;
  assigned_runner?: string | null;
  lane: string;
  reason?: string | null;
  source?: string | null;
  link_type?: string | null;
  front_door_agent?: string | null;
  trigger_key?: string | null;
  manager_attention_required?: boolean;
  executor_status?: string | null;
  executor_worker_id?: string | null;
  execution_packet_path?: string | null;
  sop_path?: string | null;
  briefing_path?: string | null;
  latest_result_status?: string | null;
  latest_result_summary?: string | null;
  latest_result_artifacts?: string[];
  queued_at?: string | null;
  last_transition_at?: string | null;
};

type UnifiedBoardLaneKey = 'todo' | 'ready' | 'queued' | 'running' | 'review' | 'failed' | 'done';

type UnifiedBoardItem = {
  id: string;
  cardId: string;
  title: string;
  workspaceKey: string;
  lane: UnifiedBoardLaneKey;
  pmStatus: string;
  executionState?: string | null;
  managerAgent?: string | null;
  targetAgent?: string | null;
  workspaceAgent?: string | null;
  executionMode?: string | null;
  reason?: string | null;
  source?: string | null;
  owner?: string | null;
  updatedAt?: string | null;
  dueAt?: string | null;
  queueEntry?: ExecutionQueueEntry | null;
  pmReviewPolicy?: PMReviewPolicyPayload | null;
};

type BoardItemGuidance = {
  summary: string;
  userRole: string;
  nextAction: string;
};

type OwnerAttentionKind = 'decision' | 'stale' | 'update';

type OwnerAttentionItem = {
  cardId: string;
  title: string;
  workspaceKey: string;
  kind: OwnerAttentionKind;
  attentionClass?: PMReviewAttentionClass;
  lane: UnifiedBoardLaneKey;
  summary: string;
  nextAction: string;
  updatedAt?: string | null;
};

type StandupEntry = {
  id: string;
  owner: string;
  workspace_key?: string;
  status?: string | null;
  blockers: string[];
  commitments: string[];
  needs: string[];
  source?: string | null;
  conversation_path?: string | null;
  payload?: Record<string, unknown>;
  created_at?: string;
};

type StandupPromotionResult = {
  standup: StandupEntry;
  created_cards: PMCard[];
  existing_cards: PMCard[];
};

type StandupRecordProvenance = {
  label: string;
  tone: string;
  background: string;
  border: string;
  description: string;
};

type StandupParticipantBuckets = {
  observed: string[];
  inferred: string[];
  merged: string[];
};

type LinkedStandupCard = {
  card: PMCard;
  queueEntry: ExecutionQueueEntry | null;
  boardItem: UnifiedBoardItem;
  guidance: BoardItemGuidance;
};

type MeetingHistoryItem = {
  label: string;
  detail: string;
  tone?: string;
};

type MissionActivityRow = {
  key: string;
  stream: string;
  activity: string;
  status: string;
  lastSeen?: Date;
};

type MeetingRoomHealth = {
  key: string;
  label: string;
  workspaceKey: string;
  status: string;
  reason: string;
  latestEntry: StandupEntry | null;
  roundCount: number;
};

type MeetingOpsSummary = {
  rooms: MeetingRoomHealth[];
  byRoomKey: Record<string, MeetingRoomHealth>;
  linkedCardCount: number;
  resolvedLinkedCardCount: number;
  orphanStandupCount: number;
  staleReadyCount: number;
  staleReviewCount: number;
  staleRunningCount: number;
  recentStandups: StandupEntry[];
};

type PMCardDispatchResult = {
  card: PMCard;
  queue_entry: ExecutionQueueEntry;
};

type PMCardActionResult = {
  card: PMCard;
  queue_entry?: ExecutionQueueEntry | null;
  successor_card?: PMCard | null;
};

type PMCardResolutionMode = 'close_only' | 'close_and_spawn_next';

type PMCardActionOptions = {
  reason?: string;
  resolutionMode?: PMCardResolutionMode;
  nextTitle?: string;
  nextReason?: string;
  proofItems?: string[];
};

type OwnerReviewDecision = 'approve' | 'revise' | 'park';

type OwnerReviewSystemAssessment = {
  suggested_decision?: OwnerReviewDecision | string;
  confidence?: 'high' | 'medium' | 'low' | string;
  summary?: string;
  reasons?: string[];
  missing_items?: string[];
  fallback_action?: string;
};

type OwnerDecisionScaffold = {
  decision_question?: string;
  recommended_decision?: OwnerReviewDecision | string;
  must_verify?: string[];
  approve_when?: string[];
  revise_when?: string[];
  park_when?: string[];
  optional_strengtheners?: string[];
  neo_answer_contract?: string;
};

type OwnerReviewCardPayload = {
  queue_id?: string;
  title?: string;
  lane?: string;
  format?: string;
  core_angle?: string;
  why_now?: string;
  status?: string;
  approval_status?: string;
  draft_path?: string;
  owner_packet_path?: string | null;
  proof_anchors?: string[];
  first_pass_draft?: string;
  draft_owner_notes?: string[];
  packet_recommendation?: string | null;
  current_notes?: string | null;
  publish_posture?: string;
  reviewed_at?: string | null;
  sync_state?: string;
  entry_kind?: string;
  source_kind?: string;
  source_url?: string | null;
  idea_id?: string | null;
  summary?: string | null;
  revision_goals?: string[];
  latent_reason?: string | null;
  transform_type?: string | null;
  system_assessment?: OwnerReviewSystemAssessment | null;
  decision_scaffold?: OwnerDecisionScaffold | null;
};

type HostActionRequiredPayload = {
  summary?: string | null;
  steps?: string[];
  proof_required?: string[];
  proof_fields?: HostActionProofField[];
  source_card_id?: string | null;
  source_card_title?: string | null;
  source_result_id?: string | null;
  source_result_summary?: string | null;
  detected_from?: string | null;
  created_at?: string | null;
};

type HostActionProofField = {
  kind?: string | null;
  label?: string | null;
  placeholder?: string | null;
  multiline?: boolean | null;
  requirement?: string | null;
};

type OwnerReviewActionResult = {
  workflow?: {
    status?: string;
    message?: string;
    card_id?: string | null;
    target_agent?: string | null;
    execution_state?: string | null;
  } | null;
  source_card_id?: string;
};

type Panel = 'mission' | 'team' | 'pm' | 'standups' | 'workspace' | 'docs';

const PANEL_HASH: Record<Panel, string> = {
  mission: '',
  team: '#team',
  pm: '#pm',
  standups: '#standups',
  workspace: '#workspace',
  docs: '#docs',
};

type OrgNode = {
  id: string;
  name: string;
  role: string;
  description: string;
  status: 'active' | 'planned';
  highlight: 'core' | 'ops' | 'brain' | 'lab';
  responsibilities?: string[];
};

type PlanCandidate = {
  source_kind: string;
  title: string;
  category: string;
  role_alignment: string;
  risk_level: string;
  publish_posture: string;
  hook: string;
  rationale: string;
  source_path: string;
  score: number;
  priority_lane?: string;
  source_url?: string;
  target_file?: string;
  route_reason?: string;
  response_modes?: string[];
};

type WeeklyPlan = {
  generated_at: string;
  workspace: string;
  positioning_model: string[];
  priority_lanes: string[];
  recommendations: PlanCandidate[];
  hold_items: PlanCandidate[];
  market_signals: PlanMarketSignal[];
  media_post_seeds?: PlanCandidate[];
  belief_evidence_candidates?: PlanCandidate[];
  media_summary?: {
    assets_considered?: number;
    segments_total?: number;
    route_counts?: Record<string, number>;
    primary_route_counts?: Record<string, number>;
  };
  source_counts: {
    drafts: number;
    media: number;
    research: number;
    belief_evidence?: number;
  };
};

type PlanMarketSignal = {
  source_kind?: string;
  title: string;
  theme?: string;
  priority_lane: string;
  role_alignment: string;
  summary: string;
  source_path: string;
};

type ReactionItem = {
  title: string;
  author: string;
  source_platform?: string;
  source_type?: string;
  source_url?: string;
  source_path: string;
  priority_lane: string;
  role_alignment: string;
  risk_level?: string;
  publish_posture?: string;
  recommended_move?: string;
  hook: string;
  summary: string;
  why_it_matters: string;
  comment_angle?: string;
  suggested_comment: string;
  post_angle: string;
  score: number;
};

type ReactionQueue = {
  generated_at: string;
  workspace?: string;
  comment_opportunities: ReactionItem[];
  post_seeds: ReactionItem[];
  counts: {
    comment_opportunities: number;
    post_seeds: number;
    background_only: number;
  };
};

type VariantEvaluation = {
  lane_distinctiveness: number;
  belief_clarity: number;
  experience_anchor_strength: number;
  voice_match: number;
  expression_quality?: number;
  role_safety_score: number;
  genericity_penalty: number;
  source_expression_quality?: number;
  output_expression_quality?: number;
  expression_delta?: number;
  source_structure?: string | null;
  output_structure?: string | null;
  structure_preserved?: boolean | null;
  overall: number;
  warnings?: string[];
};

type VariantExpressionAssessment = {
  source_text?: string;
  output_text?: string;
  strategy?: string;
  source_structure?: string;
  output_structure?: string;
  structure_preserved?: boolean;
  source_expression_quality?: number;
  output_expression_quality?: number;
  expression_delta?: number;
  overlap_ratio?: number;
  adjusted_output_quality?: number;
  warnings?: string[];
};

type VariantBeliefAssessment = {
  stance?: string;
  agreement_level?: string;
  belief_used?: string;
  belief_summary?: string;
  experience_anchor?: string;
  experience_summary?: string;
  role_safety?: string;
};

type VariantTechniqueAssessment = {
  techniques?: string[];
  emotional_profile?: string[];
  reason?: string;
};

type FeedVariant = {
  label: string;
  comment: string;
  short_comment?: string;
  repost: string;
  why_this_angle?: string;
  stance?: string;
  agreement_level?: string;
  belief_used?: string;
  belief_summary?: string;
  experience_anchor?: string;
  experience_summary?: string;
  role_safety?: string;
  techniques?: string[];
  emotional_profile?: string[];
  technique_reason?: string;
  expression_assessment?: VariantExpressionAssessment;
  evaluation?: VariantEvaluation;
};

type FeedRecommendationMode = 'comment' | 'repost' | 'post_seed';

type FeedEditorialSummary = {
  mode: FeedRecommendationMode;
  recommendation: string;
  why: string[];
  bestAngle: string;
  draft: string;
  draftTone: string;
  optionalLabel?: string;
  optionalDraft?: string;
  laneFit: 'high' | 'medium' | 'low';
  voiceFit: 'high' | 'medium' | 'low';
  specificityRisk: 'high' | 'medium' | 'low';
  bestUse: string;
  avoid: string;
};

type SocialFeedItem = {
  id: string;
  platform: string;
  source_type?: string;
  source_class?: string;
  unit_kind?: string;
  response_modes?: string[];
  source_lane: string;
  capture_method?: string;
  title: string;
  author: string;
  source_url?: string;
  source_path?: string;
  why_it_matters?: string;
  comment_draft?: string;
  repost_draft?: string;
  lens_variants?: Partial<Record<string, FeedVariant>>;
  standout_lines?: string[];
  lenses?: string[];
  summary?: string;
  belief_assessment?: VariantBeliefAssessment;
  technique_assessment?: VariantTechniqueAssessment;
  expression_assessment?: VariantExpressionAssessment;
  evaluation?: VariantEvaluation;
  ranking: { total: number };
};

type SocialFeed = {
  generated_at: string;
  workspace: string;
  strategy_mode: string;
  items: SocialFeedItem[];
};

type FeedRefreshStatus = {
  running: boolean;
  last_run?: string | null;
  started_at?: string | null;
  error?: string | null;
};

type FeedbackSummary = {
  total_events?: number;
  decision_counts?: Record<string, number>;
  technique_counts?: Record<string, number>;
  stance_counts?: Record<string, number>;
  average_evaluation_overall?: number | null;
  average_output_expression_quality?: number | null;
  average_expression_delta?: number | null;
};

type TuningVariantRecord = {
  itemId: string;
  title: string;
  platform: string;
  sourceClass: string;
  unitKind: string;
  responseModes: string[];
  lane: FeedLensId;
  laneLabel: string;
  overall: number;
  expressionQuality: number;
  sourceExpressionQuality: number;
  expressionDelta: number;
  sourceStructure: string;
  outputStructure: string;
  structurePreserved: boolean | null;
  strategy: string;
  sourceText: string;
  outputText: string;
  overlapRatio: number;
  warnings: string[];
};

type TuningLaneHealth = {
  lane: FeedLensId;
  laneLabel: string;
  variants: number;
  avgOverall: number;
  avgSource: number;
  avgExpression: number;
  avgDelta: number;
  weakSourceCount: number;
  warningCount: number;
};

type TuningAttentionItem = {
  itemId: string;
  title: string;
  platform: string;
  laneLabel: string;
  reason: string;
  overall: number;
  sourceExpressionQuality: number;
  expressionQuality: number;
  expressionDelta: number;
  sourceText: string;
  outputText: string;
};

type TuningPlatformHealth = {
  platform: string;
  variants: number;
  avgOverall: number;
  avgSource: number;
  avgExpression: number;
  avgDelta: number;
  weakSourceCount: number;
};

type TuningSourceClassHealth = {
  sourceClass: string;
  variants: number;
  avgOverall: number;
  avgSource: number;
  avgExpression: number;
  avgDelta: number;
  weakSourceCount: number;
};

type TuningUnitKindHealth = {
  unitKind: string;
  variants: number;
  avgSource: number;
  avgExpression: number;
  avgDelta: number;
  weakSourceCount: number;
};

type TuningResponseModeHealth = {
  mode: string;
  itemCount: number;
  variants: number;
  avgSource: number;
  avgExpression: number;
  avgDelta: number;
  weakSourceCount: number;
};

type TuningStructureHealth = {
  structure: string;
  variants: number;
  avgSource: number;
  avgExpression: number;
  avgDelta: number;
  preservedRate: number;
};

type TuningDashboard = {
  itemCount: number;
  placeholderExcludedCount: number;
  sampleMode: 'real-only' | 'all-items';
  variantCount: number;
  avgOverall: number;
  avgSourceExpressionQuality: number;
  avgExpressionQuality: number;
  avgExpressionDelta: number;
  weakSourceCount: number;
  warningVariantCount: number;
  degradedCount: number;
  neutralDeltaCount: number;
  lowExpressionCount: number;
  structureLossCount: number;
  laneDominanceCount: number;
  suspectTitleCount: number;
  strategyCounts: Array<{ label: string; count: number }>;
  warningCounts: Array<{ label: string; count: number }>;
  failureModes: Array<{ label: string; count: number }>;
  laneHealth: TuningLaneHealth[];
  platformHealth: TuningPlatformHealth[];
  sourceClassHealth: TuningSourceClassHealth[];
  unitKindHealth: TuningUnitKindHealth[];
  responseModeHealth: TuningResponseModeHealth[];
  structureHealth: TuningStructureHealth[];
  attentionQueue: TuningAttentionItem[];
};

type SourceAsset = {
  asset_id: string;
  title: string;
  source_class: string;
  source_channel: string;
  source_type: string;
  source_url?: string;
  author?: string;
  captured_at?: string;
  source_path: string;
  raw_path?: string;
  summary?: string;
  topics?: string[];
  tags?: string[];
  response_modes?: string[];
  routing_status?: string;
  feed_ready?: boolean;
  segmentation_ready?: boolean;
  origin?: string;
  word_count?: number | null;
};

type SourceAssetInventory = {
  generated_at?: string;
  workspace?: string;
  items: SourceAsset[];
  counts?: {
    total?: number;
    long_form_media?: number;
    pending_segmentation?: number;
    feed_ready?: number;
    by_channel?: Record<string, number>;
  };
};

type LongFormRouteCandidate = {
  candidate_id: string;
  asset_id: string;
  title: string;
  source_channel: string;
  source_url?: string;
  source_path: string;
  segment: string;
  lane_hint: string;
  target_file: string;
  stance?: string;
  belief_summary?: string;
  response_modes: string[];
  primary_route: string;
  route_reason?: string;
  route_score?: number;
};

type LongFormRouteSummary = {
  generated_at?: string;
  assets_considered?: number;
  segments_total?: number;
  skipped_no_segments?: number;
  route_counts?: Record<string, number>;
  primary_route_counts?: Record<string, number>;
  lane_counts?: Record<string, number>;
  by_channel?: Record<string, number>;
  candidates?: LongFormRouteCandidate[];
};

type PersonaReviewSummaryItem = {
  id: string;
  trait: string;
  persona_target: string;
  status: string;
  stage: string;
  review_source?: string | null;
  target_file?: string | null;
  belief_relation?: string | null;
  approval_state?: string | null;
  created_at?: string | null;
  committed_at?: string | null;
};

type PersonaReviewSummary = {
  generated_at?: string;
  workspace?: string;
  counts?: {
    total?: number;
    brain_pending_review?: number;
    workspace_saved?: number;
    approved_unpromoted?: number;
    pending_promotion?: number;
    committed?: number;
  };
  status_counts?: Record<string, number>;
  review_source_counts?: Record<string, number>;
  target_file_counts?: Record<string, number>;
  belief_relation_counts?: Record<string, number>;
  recent?: PersonaReviewSummaryItem[];
  long_form_sync?: {
    assets_considered?: number;
    created_count?: number;
    skipped_existing?: number;
    skipped_no_segments?: number;
    resolved_stale?: number;
    created?: Array<{
      id?: string;
      trait?: string;
      target_file?: string;
      source_asset_id?: string;
      review_key?: string;
    }>;
  };
};

type WorkspaceSnapshot = {
  workspace_files?: WorkspaceFile[];
  doc_entries?: DocReference[];
  weekly_plan?: WeeklyPlan | null;
  reaction_queue?: ReactionQueue | null;
  social_feed?: SocialFeed | null;
  source_assets?: SourceAssetInventory | null;
  persona_review_summary?: PersonaReviewSummary | null;
  long_form_routes?: LongFormRouteSummary | null;
  feedback_summary?: FeedbackSummary | null;
  refresh_status?: FeedRefreshStatus | null;
};

type OpenBrainTelemetry = {
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
  recent_captures: RecentCapture[];
};

type RecentCapture = {
  id: string;
  source?: string;
  topics?: string[];
  importance?: number;
  markdown_path?: string | null;
  created_at?: string | null;
  chunk_count: number;
};

type WorkspaceLensId =
  | 'all'
  | 'admissions'
  | 'entrepreneurship'
  | 'current-role'
  | 'program-leadership'
  | 'enrollment-management'
  | 'ai'
  | 'ops-pm'
  | 'therapy'
  | 'referral'
  | 'personal-story';

type FeedLensId = Exclude<WorkspaceLensId, 'all'>;

type WorkspaceLens = {
  id: WorkspaceLensId;
  label: string;
  description: string;
};

type SourceRecord = {
  title: string;
  sourcePath: string;
  priorityLane: string;
  roleAlignment: string;
  summary: string;
  author?: string;
  sourcePlatform?: string;
  sourceType?: string;
  sourceUrl?: string;
  hook?: string;
};

type SourceAssetRecord = {
  assetId: string;
  title: string;
  sourcePath: string;
  sourceChannel: string;
  sourceType: string;
  sourceClass: string;
  summary: string;
  responseModes: string[];
  routingStatus?: string;
  sourceUrl?: string;
  wordCount?: number | null;
  capturedAt?: string;
  origin?: string;
  tags: string[];
  topics: string[];
};

type OpenBrainHealth = {
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

type TelemetryErrors = {
  metrics: string | null;
  logs: string | null;
  health: string | null;
  automations: string | null;
  brain: string | null;
  brainHealth: string | null;
  pmCards: string | null;
  executionQueue: string | null;
  standups: string | null;
};

type LogsResponse = { logs?: SystemLog[] } | SystemLog[];
type AutomationsResponse =
  | { data?: Automation[]; runs?: AutomationRun[] }
  | { automations?: Automation[]; runs?: AutomationRun[] }
  | Automation[]
  | null
  | undefined;

const TELEMETRY_LABELS: Record<keyof TelemetryErrors, string> = {
  metrics: 'Compliance metrics',
  logs: 'System logs',
  health: 'Service health',
  automations: 'Automations suite',
  brain: 'Open Brain telemetry',
  brainHealth: 'Open Brain health',
  pmCards: 'PM board',
  executionQueue: 'Codex execution queue',
  standups: 'Standups',
};

const orgLayers: OrgNode[][] = [
  [
    {
      id: 'feeze',
      name: 'Feeze',
      role: 'Principal Operator',
      description: 'Approves production deploys, data use, and spend.',
      status: 'active',
      highlight: 'core',
      responsibilities: ['Final approvals', 'Risk posture', 'Product direction'],
    },
  ],
  [
    {
      id: 'neo',
      name: 'Neo',
      role: 'Core Agent',
      description: 'Routes work across Ops, Brain, and Lab while enforcing guardrails.',
      status: 'active',
      highlight: 'ops',
      responsibilities: ['Mission Control', 'Process orchestration', 'Deployment coordination'],
    },
  ],
  [
    {
      id: 'brain-agent',
      name: 'Brain Agent',
      role: 'Knowledge lane',
      description: 'Daily briefs, docs, persona deltas, and memory health.',
      status: 'planned',
      highlight: 'brain',
      responsibilities: ['Daily brief cron', 'Docs mirror', 'Memory review'],
    },
    {
      id: 'lab-agent',
      name: 'Lab Agent',
      role: 'Staging lane',
      description: 'Owns prototypes, build logs, and self-improvement runs.',
      status: 'planned',
      highlight: 'lab',
      responsibilities: ['Nightly self-improvement', 'Build logs', 'Staging QA'],
    },
  ],
];

const WORKSPACE_LENSES: WorkspaceLens[] = [
  { id: 'all', label: 'All Lanes', description: 'Show every ranked idea and signal in the workspace.' },
  { id: 'admissions', label: 'Admissions', description: 'Lead with admissions, outreach, and family-facing takes.' },
  { id: 'entrepreneurship', label: 'Entrepreneurship', description: 'Bias toward builder, founder-adjacent, and leverage stories.' },
  { id: 'current-role', label: 'Current Job', description: 'Keep the post anchored to the current role, employer context, and immediate work.' },
  { id: 'program-leadership', label: 'Program Leadership', description: 'Center leadership, team clarity, coaching, and execution systems.' },
  { id: 'enrollment-management', label: 'Enrollment', description: 'Pull toward enrollment pipeline, conversion, and student journey.' },
  { id: 'ai', label: 'AI', description: 'Make the point about AI literacy, AI judgment, and using AI well.' },
  { id: 'ops-pm', label: 'Ops / PM', description: 'Focus on workflow, ownership, handoffs, cadence, and delivery.' },
  { id: 'therapy', label: 'Therapy', description: 'Highlight the human, emotional, and relational experience underneath the system.' },
  { id: 'referral', label: 'Referral', description: 'Focus on partner trust, handoffs, and what makes referrals compound.' },
  { id: 'personal-story', label: 'Personal Story', description: 'Highlight lived experience, identity, and story-led framing.' },
];

const POST_MODE_OPTIONS: { id: FeedLensId; label: string }[] = [
  { id: 'entrepreneurship', label: 'Entrepreneurship' },
  { id: 'current-role', label: 'Current Job' },
  { id: 'program-leadership', label: 'Program Leadership' },
  { id: 'enrollment-management', label: 'Enrollment' },
  { id: 'ai', label: 'AI' },
  { id: 'ops-pm', label: 'Ops / PM' },
  { id: 'therapy', label: 'Therapy' },
  { id: 'referral', label: 'Referral' },
  { id: 'personal-story', label: 'Personal Story' },
  { id: 'admissions', label: 'Admissions' },
];

const FEED_LENS_IDS = POST_MODE_OPTIONS.map((mode) => mode.id);

const FEED_LENS_ALIASES: Record<string, FeedLensId> = {
  admissions: 'admissions',
  entrepreneurship: 'entrepreneurship',
  'current-role': 'current-role',
  'current role': 'current-role',
  'current job': 'current-role',
  job: 'current-role',
  'job / current role': 'current-role',
  'program-leadership': 'program-leadership',
  'job / program leadership': 'program-leadership',
  'program leadership': 'program-leadership',
  leadership: 'program-leadership',
  'enrollment-management': 'enrollment-management',
  enrollment: 'enrollment-management',
  'enrollment mgmt': 'enrollment-management',
  ai: 'ai',
  'ai + ops': 'ai',
  'ai-entrepreneurship': 'ai',
  'ops-pm': 'ops-pm',
  'ops / pm': 'ops-pm',
  'ops / project management': 'ops-pm',
  'project management': 'ops-pm',
  pm: 'ops-pm',
  therapy: 'therapy',
  'therapy / referral': 'therapy',
  'therapist / referral': 'therapy',
  'therapist-referral': 'therapy',
  referral: 'referral',
  'personal-story': 'personal-story',
  'personal story': 'personal-story',
};

const FEED_LENS_VARIANT_KEYS: Record<FeedLensId, string[]> = {
  admissions: ['admissions'],
  entrepreneurship: ['entrepreneurship'],
  'current-role': ['current-role', 'program-leadership'],
  'program-leadership': ['program-leadership', 'current-role'],
  'enrollment-management': ['enrollment-management'],
  ai: ['ai', 'ai-entrepreneurship'],
  'ops-pm': ['ops-pm', 'ai-entrepreneurship'],
  therapy: ['therapy', 'therapist-referral'],
  referral: ['referral', 'therapist-referral'],
  'personal-story': ['personal-story'],
};

type WorkspaceHubKey = 'linkedin-os' | 'fusion-os' | 'easyoutfitapp' | 'ai-swag-store' | 'agc';
type WorkspaceHubStatus = 'live' | 'standing_up' | 'planned';

const WORKSPACE_HUBS: Array<{
  id: WorkspaceHubKey;
  label: string;
  shortLabel: string;
  status: WorkspaceHubStatus;
  accent: string;
  description: string;
  agent: string;
  operatingPrinciples: string[];
  route?: string;
}> = [
  {
    id: 'linkedin-os',
    label: 'FEEZIE OS',
    shortLabel: 'FEEZIE',
    status: 'live',
    accent: '#38bdf8',
    description: 'Posting execution system for signal intake, reaction loops, content generation, and persona-grounded visibility.',
    agent: 'LinkedIn Operator',
    operatingPrinciples: [
      'Persona truth first, posting second',
      'Use live source signals before generic ideation',
      'Turn reactions into reusable visibility assets',
    ],
    route: '/workspace',
  },
  {
    id: 'fusion-os',
    label: 'Fusion OS',
    shortLabel: 'Fusion',
    status: 'standing_up',
    accent: '#22c55e',
    description: 'Admissions, enrollment, school operations, referral systems, and leadership execution for Fusion-adjacent work.',
    agent: 'Fusion Systems Operator',
    operatingPrinciples: [
      'Protect trust with families and partners',
      'Let frontline signals drive process changes',
      'Make execution clearer before scaling it',
    ],
  },
  {
    id: 'easyoutfitapp',
    label: 'EasyOutfitApp',
    shortLabel: 'Easy Outfit',
    status: 'planned',
    accent: '#f472b6',
    description: 'Product, outfit logic, metadata quality, user feedback, and style-system refinement for the Easy Outfit app.',
    agent: 'Easy Outfit Product Agent',
    operatingPrinciples: [
      'Metadata before vibes',
      'Validate every outfit against context',
      'Make recommendation quality obvious to the user',
    ],
  },
  {
    id: 'ai-swag-store',
    label: 'AI Swag Store',
    shortLabel: 'Swag Store',
    status: 'planned',
    accent: '#f59e0b',
    description: 'Commerce, merchandising, product drops, and demand testing for AI-branded physical goods.',
    agent: 'Commerce Growth Agent',
    operatingPrinciples: [
      'Test demand before expanding catalog',
      'Use signal-backed creative, not generic merch',
      'Keep ops simple enough to repeat',
    ],
  },
  {
    id: 'agc',
    label: 'AGC',
    shortLabel: 'AGC',
    status: 'planned',
    accent: '#a78bfa',
    description: 'Dedicated operating system slot for AGC work with its own agent, memory, and execution rules.',
    agent: 'AGC Strategy Agent',
    operatingPrinciples: [
      'Separate the mission from the noise',
      'Use a distinct operating model per initiative',
      'Keep decisions traceable back to goals',
    ],
  },
];

function workspaceLifecycleLabel(status: WorkspaceHubStatus) {
  switch (status) {
    case 'live':
      return 'Live';
    case 'standing_up':
      return 'Standing up';
    default:
      return 'Planned';
  }
}

function workspaceLifecycleDetail(status: WorkspaceHubStatus) {
  switch (status) {
    case 'live':
      return 'Dedicated interface and active execution lane';
    case 'standing_up':
      return 'Backend lane is active and accumulating artifacts';
    default:
      return 'Portfolio slot is defined but still waiting on activity';
  }
}

function timestampMs(value?: string | null) {
  if (!value) {
    return 0;
  }
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

function sortByTimestampDesc<T>(items: readonly T[], getValue: (item: T) => string | null | undefined): T[] {
  return [...items].sort((left, right) => timestampMs(getValue(right)) - timestampMs(getValue(left)));
}

function workspaceDirectoryName(workspaceKey: WorkspaceHubKey) {
  const root = WORKSPACE_ROOT_BY_KEY[workspaceKey] ?? '';
  const segments = root.split('/').filter(Boolean);
  return segments[segments.length - 1] ?? workspaceKey;
}

function workspaceFileBelongsToHub(file: WorkspaceFile, workspaceKey: WorkspaceHubKey) {
  const normalizedPath = file.path.replace(/\\/g, '/');
  const directoryName = workspaceDirectoryName(workspaceKey);
  return normalizedPath.includes(`/workspaces/${directoryName}/`) || file.group.includes(directoryName);
}

function workspaceRelativeFilePath(filePath: string, workspaceKey: WorkspaceHubKey) {
  const normalizedPath = filePath.replace(/\\/g, '/');
  const directoryName = workspaceDirectoryName(workspaceKey);
  const marker = `/workspaces/${directoryName}/`;
  const markerIndex = normalizedPath.indexOf(marker);
  if (markerIndex >= 0) {
    return normalizedPath.slice(markerIndex + marker.length);
  }
  return normalizedPath.split('/').slice(-2).join('/');
}

function workspaceFileSection(file: WorkspaceFile, workspaceKey: WorkspaceHubKey) {
  const relative = workspaceRelativeFilePath(file.path, workspaceKey);
  return relative.split('/')[0] || 'root';
}

function workspaceFilePriority(file: WorkspaceFile, workspaceKey: WorkspaceHubKey) {
  switch (workspaceFileSection(file, workspaceKey)) {
    case 'docs':
      return 0;
    case 'standups':
      return 1;
    case 'analytics':
      return 2;
    case 'memory':
      return 3;
    case 'briefings':
      return 4;
    case 'root':
      return 5;
    case 'agent-ledgers':
      return 6;
    case 'dispatch':
      return 99;
    default:
      return 7;
  }
}

export default function OpsClient({
  workspaceFiles,
  docEntries,
  executiveFeed,
  initialPanel = 'mission',
  initialWorkspaceKey,
}: {
  workspaceFiles: WorkspaceFile[];
  docEntries: DocReference[];
  executiveFeed: ExecutiveFeed;
  initialPanel?: Panel;
  initialWorkspaceKey?: string;
}) {
  const [metrics, setMetrics] = useState<ComplianceMetrics | null>(null);
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [automationRuns, setAutomationRuns] = useState<AutomationRun[]>([]);
  const [pmCards, setPmCards] = useState<PMCard[]>([]);
  const [reviewHygieneSummary, setReviewHygieneSummary] = useState<PMReviewHygieneResult | null>(null);
  const [reviewProgressSummary, setReviewProgressSummary] = useState<PMAutoProgressResult | null>(null);
  const [reviewProgressAudit, setReviewProgressAudit] = useState<PMAutoProgressAuditReport | null>(null);
  const [executionQueue, setExecutionQueue] = useState<ExecutionQueueEntry[]>([]);
  const [standups, setStandups] = useState<StandupEntry[]>([]);
  const [brainMetrics, setBrainMetrics] = useState<OpenBrainTelemetry | null>(null);
  const [brainHealth, setBrainHealth] = useState<OpenBrainHealth | null>(null);
  const [liveWorkspaceFiles, setLiveWorkspaceFiles] = useState<WorkspaceFile[] | null>(null);
  const [liveDocEntries, setLiveDocEntries] = useState<DocReference[] | null>(null);
  const [liveWeeklyPlan, setLiveWeeklyPlan] = useState<WeeklyPlan | null>(null);
  const [liveReactionQueue, setLiveReactionQueue] = useState<ReactionQueue | null>(null);
  const [liveSocialFeed, setLiveSocialFeed] = useState<SocialFeed | null>(null);
  const [liveSourceAssets, setLiveSourceAssets] = useState<SourceAssetInventory | null>(null);
  const [livePersonaReviewSummary, setLivePersonaReviewSummary] = useState<PersonaReviewSummary | null>(null);
  const [liveLongFormRoutes, setLiveLongFormRoutes] = useState<LongFormRouteSummary | null>(null);
  const [feedbackSummary, setFeedbackSummary] = useState<FeedbackSummary | null>(null);
  const [workspaceRefreshStatus, setWorkspaceRefreshStatus] = useState<FeedRefreshStatus | null>(null);
  const [workspaceSnapshotState, setWorkspaceSnapshotState] = useState<'loading' | 'live' | 'error'>('loading');
  const [workspaceSnapshotError, setWorkspaceSnapshotError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activePanel, setActivePanel] = useState<Panel>(initialPanel);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const pmMaintenanceInFlightRef = useRef(false);
  const effectiveWorkspaceFiles = liveWorkspaceFiles ?? workspaceFiles;
  const effectiveDocEntries = liveDocEntries ?? docEntries;
  const effectiveWeeklyPlan = liveWeeklyPlan;
  const effectiveReactionQueue = liveReactionQueue;
  const effectiveSocialFeed = liveSocialFeed;
  const [selectedWorkspacePath, setSelectedWorkspacePath] = useState(() => pickWorkspacePath(workspaceFiles, initialWorkspaceKey) ?? workspaceFiles[0]?.path ?? '');
  const [selectedDocPath, setSelectedDocPath] = useState(docEntries[0]?.path ?? '');
  const [sectionErrors, setSectionErrors] = useState<TelemetryErrors>({
    metrics: null,
    logs: null,
    health: null,
    automations: null,
    brain: null,
    brainHealth: null,
    pmCards: null,
    executionQueue: null,
    standups: null,
  });

  const updateSectionError = useCallback((key: keyof TelemetryErrors, message: string | null) => {
    setSectionErrors((prev) => ({ ...prev, [key]: message }));
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const syncPanelFromHash = () => {
      const hash = window.location.hash;
      const nextPanel = (Object.entries(PANEL_HASH).find(([, value]) => value === hash)?.[0] ?? initialPanel) as Panel;
      setActivePanel(nextPanel);
    };

    syncPanelFromHash();
    window.addEventListener('hashchange', syncPanelFromHash);
    return () => window.removeEventListener('hashchange', syncPanelFromHash);
  }, [initialPanel]);

  const selectPanel = useCallback((panel: Panel) => {
    setActivePanel(panel);
    if (typeof window === 'undefined') {
      return;
    }
    const nextUrl = `${window.location.pathname}${window.location.search}${PANEL_HASH[panel]}`;
    window.history.replaceState(null, '', nextUrl);
  }, []);

  const loadWorkspaceSnapshot = useCallback(async () => {
    try {
      const snapshot = await fetchJson<WorkspaceSnapshot>(`${API_URL}/api/workspace/linkedin-os-snapshot`);
      if (snapshot.workspace_files?.length) {
        setLiveWorkspaceFiles(snapshot.workspace_files);
      }
      if (snapshot.doc_entries?.length) {
        setLiveDocEntries(snapshot.doc_entries);
      }
      setLiveWeeklyPlan(snapshot.weekly_plan ?? null);
      setLiveReactionQueue(snapshot.reaction_queue ?? null);
      setLiveSocialFeed(snapshot.social_feed ?? null);
      setLiveSourceAssets(snapshot.source_assets ?? null);
      setLivePersonaReviewSummary(snapshot.persona_review_summary ?? null);
      setLiveLongFormRoutes(snapshot.long_form_routes ?? null);
      setFeedbackSummary(snapshot.feedback_summary ?? null);
      setWorkspaceRefreshStatus(snapshot.refresh_status ?? null);
      setWorkspaceSnapshotState('live');
      setWorkspaceSnapshotError(null);
    } catch (error) {
      setWorkspaceSnapshotState('error');
      setWorkspaceSnapshotError(toErrorMessage(error));
    }
  }, []);

  useEffect(() => {
    if (!effectiveWorkspaceFiles.some((file) => file.path === selectedWorkspacePath)) {
      setSelectedWorkspacePath(pickWorkspacePath(effectiveWorkspaceFiles, initialWorkspaceKey) ?? effectiveWorkspaceFiles[0]?.path ?? '');
    }
  }, [effectiveWorkspaceFiles, initialWorkspaceKey, selectedWorkspacePath]);

  useEffect(() => {
    if (!effectiveDocEntries.some((entry) => entry.path === selectedDocPath)) {
      setSelectedDocPath(effectiveDocEntries[0]?.path ?? '');
    }
  }, [effectiveDocEntries, selectedDocPath]);

  useEffect(() => {
    loadWorkspaceSnapshot();
  }, [loadWorkspaceSnapshot]);

  const runPmMaintenance = useCallback(async () => {
    if (pmMaintenanceInFlightRef.current) {
      return;
    }
    pmMaintenanceInFlightRef.current = true;
    try {
      const [autoResolveResp, ownerReviewSyncResp, autoProgressResp] = await Promise.allSettled([
        postJson<PMReviewHygieneResult>(`${API_URL}/api/pm/review-hygiene/auto-resolve`),
        postJson<Record<string, unknown>>(`${API_URL}/api/pm/owner-review/sync`),
        postJson<PMAutoProgressResult>(`${API_URL}/api/pm/review-hygiene/auto-progress`),
      ]);

      if (autoResolveResp.status === 'fulfilled') {
        setReviewHygieneSummary(autoResolveResp.value ?? null);
      }
      if (autoProgressResp.status === 'fulfilled') {
        setReviewProgressSummary(autoProgressResp.value ?? null);
      }

      const maintenanceErrors = [autoResolveResp, ownerReviewSyncResp, autoProgressResp]
        .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
        .map((result) => toErrorMessage(result.reason));
      if (maintenanceErrors.length > 0) {
        console.warn('PM maintenance skipped after telemetry load', maintenanceErrors.join(' | '));
      }
    } finally {
      pmMaintenanceInFlightRef.current = false;
    }
  }, []);

  const loadTelemetry = useCallback(async () => {
    setIsRefreshing(true);
    setGlobalError(null);

    const revealTelemetry = () => setLoading(false);
    const trackRequest = async <T,>(
      request: Promise<T>,
      onSuccess: (value: T) => void,
      onError?: (error: unknown) => void,
    ): Promise<{ ok: boolean }> => {
      try {
        const value = await request;
        onSuccess(value);
        revealTelemetry();
        return { ok: true };
      } catch (error) {
        onError?.(error);
        revealTelemetry();
        return { ok: false };
      }
    };

    const requests = await Promise.all([
      trackRequest(
        fetchJson<ComplianceMetrics>(`${API_URL}/api/analytics/compliance`),
        (value) => {
          setMetrics(value ?? null);
          updateSectionError('metrics', null);
        },
        (error) => updateSectionError('metrics', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<LogsResponse>(`${API_URL}/api/system/logs/?limit=40`),
        (value) => {
          setLogs(normalizeLogs(value));
          updateSectionError('logs', null);
        },
        (error) => updateSectionError('logs', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<HealthPayload>(`${API_URL}/health`),
        (value) => {
          setHealth(value ?? null);
          updateSectionError('health', null);
        },
        (error) => updateSectionError('health', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<AutomationsResponse>(`${API_URL}/api/automations/`),
        (value) => {
          setAutomations(normalizeAutomations(value));
          setAutomationRuns(normalizeAutomationRuns(value));
          updateSectionError('automations', null);
        },
        (error) => updateSectionError('automations', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<OpenBrainTelemetry>(`${API_URL}/api/analytics/open-brain`),
        (value) => {
          setBrainMetrics(value ?? null);
          updateSectionError('brain', null);
        },
        (error) => updateSectionError('brain', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<OpenBrainHealth>(`${API_URL}/api/open-brain/health`),
        (value) => {
          setBrainHealth(value ?? null);
          updateSectionError('brainHealth', null);
        },
        (error) => updateSectionError('brainHealth', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<PMCard[]>(`${API_URL}/api/pm/cards?limit=50`),
        (value) => {
          setPmCards(Array.isArray(value) ? value : []);
          updateSectionError('pmCards', null);
        },
        (error) => updateSectionError('pmCards', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<ExecutionQueueEntry[]>(`${API_URL}/api/pm/execution-queue?limit=50`),
        (value) => {
          setExecutionQueue(Array.isArray(value) ? value : []);
          updateSectionError('executionQueue', null);
        },
        (error) => updateSectionError('executionQueue', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<StandupEntry[]>(`${API_URL}/api/standups/?limit=20`),
        (value) => {
          setStandups(Array.isArray(value) ? value : []);
          updateSectionError('standups', null);
        },
        (error) => updateSectionError('standups', toErrorMessage(error)),
      ),
      trackRequest(
        fetchJson<PMAutoProgressAuditReport>(`${API_URL}/api/pm/review-hygiene/audit?limit=8&hours=24`),
        (value) => setReviewProgressAudit(value ?? null),
        () => setReviewProgressAudit(null),
      ),
    ]);

    const failures = requests.filter((result) => !result.ok);
    if (failures.length === requests.length) {
      setGlobalError('Unable to reach the production control APIs right now. Check backend health and Railway logs before trusting the UI.');
    }

    setCheckedAt(new Date());
    setLoading(false);
    setIsRefreshing(false);
    void runPmMaintenance();
  }, [runPmMaintenance, updateSectionError]);

  const promoteStandup = useCallback(
    async (prep: StandupPrepPacket, recommendationPacket: PMRecommendationPacket | null, chronicleEntry: ChronicleEntry | null) => {
      const response = await fetch(`${API_URL}/api/standups/promote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildStandupPromotionPayload(prep, recommendationPacket, chronicleEntry)),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => response.statusText);
        throw new Error(`${response.status} ${response.statusText}: ${text}`);
      }
      const result = (await response.json()) as StandupPromotionResult;
      await loadTelemetry();
      return result;
    },
    [loadTelemetry],
  );

  const dispatchPmCard = useCallback(
    async (cardId: string, targetAgent = 'Jean-Claude') => {
      const response = await fetch(`${API_URL}/api/pm/cards/${cardId}/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_agent: targetAgent,
          lane: 'codex',
          requested_by: 'Jean-Claude',
          execution_state: 'queued',
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => response.statusText);
        throw new Error(`${response.status} ${response.statusText}: ${text}`);
      }
      const result = (await response.json()) as PMCardDispatchResult;
      await loadTelemetry();
      return result;
    },
    [loadTelemetry],
  );

  const updatePmCard = useCallback(
    async (cardId: string, patch: { status?: string; payload?: Record<string, unknown> }) => {
      const response = await fetch(`${API_URL}/api/pm/cards/${cardId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => response.statusText);
        throw new Error(`${response.status} ${response.statusText}: ${text}`);
      }
      const result = (await response.json()) as PMCard;
      await loadTelemetry();
      return result;
    },
    [loadTelemetry],
  );

  const actOnPmCard = useCallback(
    async (cardId: string, action: 'approve' | 'return' | 'blocked', options?: PMCardActionOptions) => {
      const response = await fetch(`${API_URL}/api/pm/cards/${cardId}/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          requested_by: 'Neo',
          reason: options?.reason,
          resolution_mode: options?.resolutionMode,
          next_title: options?.nextTitle,
          next_reason: options?.nextReason,
          proof_items: options?.proofItems,
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => response.statusText);
        throw new Error(`${response.status} ${response.statusText}: ${text}`);
      }
      const result = (await response.json()) as PMCardActionResult;
      await loadTelemetry();
      return result;
    },
    [loadTelemetry],
  );

  const actOnOwnerReviewCard = useCallback(
    async (cardId: string, decision: OwnerReviewDecision, notes: string) => {
      const response = await fetch(`${API_URL}/api/pm/cards/${cardId}/owner-review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          notes,
        }),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => response.statusText);
        throw new Error(`${response.status} ${response.statusText}: ${text}`);
      }
      const result = (await response.json()) as OwnerReviewActionResult;
      await loadTelemetry();
      return result;
    },
    [loadTelemetry],
  );

  useEffect(() => {
    loadTelemetry();
    const interval = setInterval(loadTelemetry, 60_000);
    return () => clearInterval(interval);
  }, [loadTelemetry]);

  const sectionErrorSummary = useMemo(() => {
    const messages = Object.entries(sectionErrors)
      .filter(([, value]) => Boolean(value))
      .map(([key, value]) => `${TELEMETRY_LABELS[key as keyof TelemetryErrors]}: ${value}`);
    return messages.length ? messages.join(' | ') : null;
  }, [sectionErrors]);

  const modelRows = useMemo(() => {
    if (!health) return [];
    return [
      {
        name: health.service ?? 'aiclone-backend',
        status: health.status ?? 'unknown',
        version: health.version ?? 'n/a',
        datastore: health.firestore ?? 'n/a',
      },
    ];
  }, [health]);

  const sessionRows = useMemo(() => {
    const map = new Map<string, { component: string; lastMessage: string; lastTimestamp?: Date }>();
    logs.forEach((log) => {
      if (!log.component) return;
      const ts = log.timestamp ? new Date(log.timestamp) : undefined;
      const existing = map.get(log.component);
      if (!existing || (ts && existing.lastTimestamp && ts > existing.lastTimestamp) || (!existing?.lastTimestamp && ts)) {
        map.set(log.component, {
          component: log.component,
          lastMessage: log.message ?? '',
          lastTimestamp: ts,
        });
      }
    });
    return Array.from(map.values()).sort((a, b) => {
      const aTime = a.lastTimestamp?.getTime() ?? 0;
      const bTime = b.lastTimestamp?.getTime() ?? 0;
      return bTime - aTime;
    });
  }, [logs]);

  const activityRows = useMemo(
    () =>
      buildMissionActivityRows({
        executionQueue,
        automations,
        automationRuns,
        sessions: sessionRows,
      }),
    [executionQueue, automations, automationRuns, sessionRows],
  );

  const selectedWorkspace = useMemo(
    () => effectiveWorkspaceFiles.find((file) => file.path === selectedWorkspacePath) ?? effectiveWorkspaceFiles[0] ?? null,
    [effectiveWorkspaceFiles, selectedWorkspacePath],
  );
  const selectedDoc = useMemo(
    () => effectiveDocEntries.find((entry) => entry.path === selectedDocPath) ?? effectiveDocEntries[0] ?? null,
    [effectiveDocEntries, selectedDocPath],
  );
  const openArtifactPath = useCallback(
    (sourcePath: string) => {
      const docMatch =
        effectiveDocEntries.find((entry) => entry.path === sourcePath) ??
        findDocBySourcePath(effectiveDocEntries, sourcePath);
      if (docMatch) {
        setSelectedDocPath(docMatch.path);
        setActivePanel('docs');
        return;
      }

      const workspaceMatch =
        effectiveWorkspaceFiles.find((file) => file.path === sourcePath) ??
        findWorkspaceFileBySourcePath(effectiveWorkspaceFiles, sourcePath);
      if (workspaceMatch) {
        setSelectedWorkspacePath(workspaceMatch.path);
        setActivePanel('workspace');
      }
    },
    [effectiveDocEntries, effectiveWorkspaceFiles],
  );

  const tabs = [
    { key: 'mission', label: 'Mission Control', active: activePanel === 'mission', onSelect: () => selectPanel('mission') },
    { key: 'team', label: 'Team', active: activePanel === 'team', onSelect: () => selectPanel('team') },
    { key: 'pm', label: 'PM Board', active: activePanel === 'pm', onSelect: () => selectPanel('pm') },
    { key: 'standups', label: 'Standups', active: activePanel === 'standups', onSelect: () => selectPanel('standups') },
    { key: 'workspace', label: 'Workspaces', active: activePanel === 'workspace', onSelect: () => selectPanel('workspace') },
    { key: 'docs', label: 'Docs', active: activePanel === 'docs', onSelect: () => selectPanel('docs') },
  ];

  return (
    <RuntimePage module="ops" tabs={tabs}>
      <header style={{ marginBottom: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <div>
            <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Ops</p>
            <h1 style={{ fontSize: '40px', fontWeight: 700, color: 'white', margin: '4px 0' }}>Mission Control</h1>
            <p style={{ color: '#8ea0bd', maxWidth: '760px' }}>Runtime health, live telemetry, team surfaces, and the control-center shell from the March 20 reference screenshots.</p>
          </div>
          <div style={{ textAlign: 'right', color: '#94a3b8', fontSize: '13px', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
            <p>Last check: {checkedAt ? formatUiTime(checkedAt) : loading ? 'Checking...' : '-'}</p>
            <p>Refresh cadence: 60s poll + manual trigger</p>
            <button
              onClick={loadTelemetry}
              disabled={isRefreshing}
              style={{
                padding: '9px 18px',
                borderRadius: '999px',
                border: '1px solid rgba(251,191,36,0.35)',
                backgroundColor: isRefreshing ? '#101827' : '#fbbf24',
                color: isRefreshing ? '#94a3b8' : '#0f172a',
                fontWeight: 700,
                cursor: isRefreshing ? 'not-allowed' : 'pointer',
              }}
            >
              {isRefreshing ? 'Refreshing...' : 'Manual refresh'}
            </button>
          </div>
        </div>
      </header>

      {globalError && <SectionAlert message={globalError} />}
      {!globalError && sectionErrorSummary && <SectionAlert message={sectionErrorSummary} />}

      {activePanel === 'mission' && (
        <MissionControlView
          loading={loading}
          metrics={metrics}
          metricsError={sectionErrors.metrics}
          models={modelRows}
          modelsError={sectionErrors.health}
          activityRows={activityRows}
          sessionsError={sectionErrors.logs}
          cronJobs={automations}
          cronError={sectionErrors.automations}
          executionQueue={executionQueue}
          queueError={sectionErrors.executionQueue}
          automations={automations}
          automationRuns={automationRuns}
          brainMetrics={brainMetrics}
          brainError={sectionErrors.brain}
          brainHealth={brainHealth}
          brainHealthError={sectionErrors.brainHealth}
        />
      )}
      {activePanel === 'team' && <OrgChartSection layers={orgLayers} />}
      {activePanel === 'pm' && (
        <PMBoardPanel
          cards={pmCards}
          reviewHygieneSummary={reviewHygieneSummary}
          reviewProgressSummary={reviewProgressSummary}
          reviewProgressAudit={reviewProgressAudit}
          executionQueue={executionQueue}
          standups={standups}
          automations={automations}
          executiveFeed={executiveFeed}
          error={sectionErrors.pmCards}
          queueError={sectionErrors.executionQueue}
          onDispatch={dispatchPmCard}
          onActOnPmCard={actOnPmCard}
          onActOnOwnerReviewCard={actOnOwnerReviewCard}
          onOpenArtifactPath={openArtifactPath}
        />
      )}
      {activePanel === 'standups' && (
        <StandupsPanel
          entries={standups}
          pmCards={pmCards}
          executionQueue={executionQueue}
          automations={automations}
          executiveFeed={executiveFeed}
          error={sectionErrors.standups}
          onPromote={promoteStandup}
          onOpenArtifactPath={openArtifactPath}
          onDispatchPmCard={dispatchPmCard}
          onActOnPmCard={actOnPmCard}
        />
      )}
      {activePanel === 'workspace' && (
        <WorkspaceHubPanel
          files={effectiveWorkspaceFiles}
          selected={selectedWorkspace}
          onSelect={setSelectedWorkspacePath}
          cards={pmCards}
          executionQueue={executionQueue}
          standups={standups}
          executiveFeed={executiveFeed}
          plan={effectiveWeeklyPlan}
          reactionQueue={effectiveReactionQueue}
          socialFeed={effectiveSocialFeed}
          sourceAssets={liveSourceAssets}
          personaReviewSummary={livePersonaReviewSummary}
          longFormRoutes={liveLongFormRoutes}
          workspaceSnapshotState={workspaceSnapshotState}
          workspaceSnapshotError={workspaceSnapshotError}
          workspaceRefreshStatus={workspaceRefreshStatus}
          feedbackSummary={feedbackSummary}
          onReloadLiveSnapshot={loadWorkspaceSnapshot}
        />
      )}
      {activePanel === 'docs' && <DocsPanel docs={effectiveDocEntries} selected={selectedDoc} onSelect={setSelectedDocPath} />}
    </RuntimePage>
  );
}

function MissionControlView({
  loading,
  metrics,
  metricsError,
  models,
  modelsError,
  activityRows,
  sessionsError,
  cronJobs,
  cronError,
  executionQueue,
  queueError,
  automations,
  automationRuns,
  brainMetrics,
  brainError,
  brainHealth,
  brainHealthError,
}: {
  loading: boolean;
  metrics: ComplianceMetrics | null;
  metricsError: string | null;
  models: { name: string; status: string; version: string; datastore: string }[];
  modelsError: string | null;
  activityRows: MissionActivityRow[];
  sessionsError: string | null;
  cronJobs: Automation[];
  cronError: string | null;
  executionQueue: ExecutionQueueEntry[];
  queueError: string | null;
  automations: Automation[];
  automationRuns: AutomationRun[];
  brainMetrics: OpenBrainTelemetry | null;
  brainError: string | null;
  brainHealth: OpenBrainHealth | null;
  brainHealthError: string | null;
}) {
  if (loading) {
    return <p style={{ color: '#94a3b8' }}>Refreshing telemetry...</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <HeroCard metrics={metrics} sessions={activityRows.length} cronCount={cronJobs.length} />
      <LocalWorkerHealthPanel executionQueue={executionQueue} automations={automations} automationRuns={automationRuns} />
      {metricsError && <SectionAlert message={`${TELEMETRY_LABELS.metrics}: ${metricsError}`} />}
      <StatusTable
        title="Models"
        subtitle="Backend surfaces + data stores"
        headers={['Name', 'Status', 'Version', 'Datastore']}
        rows={models.map((model) => [model.name, statusBadge(model.status), model.version, model.datastore])}
      />
      {modelsError && <SectionAlert message={`${TELEMETRY_LABELS.health}: ${modelsError}`} />}
      <OpenBrainPanel metrics={brainMetrics} health={brainHealth} />
      {brainError && <SectionAlert message={`${TELEMETRY_LABELS.brain}: ${brainError}`} />}
      {brainHealthError && <SectionAlert message={`${TELEMETRY_LABELS.brainHealth}: ${brainHealthError}`} />}
      <StatusTable
        title="Active Streams"
        subtitle="Execution lanes, automation runs, and live backlog signals"
        headers={['Stream', 'Activity', 'Status', 'Last Seen']}
        rows={activityRows.map((row) => [row.stream, row.activity, statusBadge(row.status), row.lastSeen ? formatTimestamp(row.lastSeen) : '-'])}
      />
      {queueError && <SectionAlert message={`${TELEMETRY_LABELS.executionQueue}: ${queueError}`} />}
      {sessionsError && activityRows.length === 0 && <SectionAlert message={`${TELEMETRY_LABELS.logs}: ${sessionsError}`} />}
      <CronTable cronJobs={cronJobs} />
      {cronError && <SectionAlert message={`${TELEMETRY_LABELS.automations}: ${cronError}`} />}
    </div>
  );
}

function HeroCard({ metrics, sessions, cronCount }: { metrics: ComplianceMetrics | null; sessions: number; cronCount: number }) {
  const cards = [
    { label: 'Approvals', value: metrics?.approvals_last_24h ?? 0, detail: 'Last 24h', tone: '#fbbf24' },
    { label: 'Prospects Ready', value: metrics?.prospects_with_email ?? 0, detail: 'Email staged', tone: '#38bdf8' },
    { label: 'Active Streams', value: sessions, detail: 'Runtime activity', tone: '#4ade80' },
    { label: 'Cron Runs', value: cronCount, detail: 'Isolated jobs', tone: '#f472b6' },
  ];
  return (
    <section
      style={{
        borderRadius: '22px',
        padding: '24px',
        background: 'linear-gradient(135deg, rgba(17,24,39,0.94), rgba(8,12,24,0.98))',
        border: '1px solid rgba(251,191,36,0.18)',
        boxShadow: '0 26px 72px rgba(0,0,0,0.35)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Ops Dashboard</p>
          <h2 style={{ color: 'white', fontSize: '32px', margin: '4px 0' }}>Mission Control</h2>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Realtime guardrails, sessions, and automations for the production agent.</p>
        </div>
        <div style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'right' }}>
          <p>Reference shell aligned to March 20 capture</p>
          <p>Bottom dock routes across Ops, Brain, and Lab</p>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
        {cards.map((card) => (
          <div key={card.label} style={{ padding: '16px', borderRadius: '18px', backgroundColor: '#060b18', border: '1px solid rgba(30,41,59,0.9)' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{card.label}</p>
            <p style={{ color: card.tone, fontSize: '30px', fontWeight: 700 }}>{card.value}</p>
            <p style={{ color: '#475569', fontSize: '12px' }}>{card.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function LocalWorkerHealthPanel({
  executionQueue,
  automations,
  automationRuns,
}: {
  executionQueue: ExecutionQueueEntry[];
  automations: Automation[];
  automationRuns: AutomationRun[];
}) {
  const localWorkerIds = [
    'feezie_codex_bridge',
    'jean_claude_execution_dispatch',
    'workspace_agent_dispatch',
    'codex_workspace_execution',
    'codex_chronicle_sync',
  ];
  const workerAutomations = localWorkerIds
    .map((id) => automations.find((item) => item.id === id))
    .filter((item): item is Automation => Boolean(item));
  const healthyWorkers = workerAutomations.filter((item) => {
    const runtime = String(item.runtime ?? '').toLowerCase();
    const status = String(item.status ?? '').toLowerCase();
    const lastStatus = String(item.last_status ?? '').toLowerCase();
    return runtime.includes('active') || status === 'active' || lastStatus === 'ok';
  }).length;

  const claimedEntries = executionQueue.filter((entry) => String(entry.executor_status ?? '').toLowerCase() === 'running');
  const failedEntries = [...executionQueue]
    .filter((entry) => {
      const executorStatus = String(entry.executor_status ?? '').toLowerCase();
      const executionState = normalizeExecutionState(entry.execution_state);
      return executorStatus === 'failed' || executionState === 'failed';
    })
    .sort((left, right) => {
      const leftTime = activityTimestampForQueue(left)?.getTime() ?? 0;
      const rightTime = activityTimestampForQueue(right)?.getTime() ?? 0;
      return rightTime - leftTime;
    });
  const staleRunningEntries = executionQueue.filter((entry) => {
    const state = normalizeExecutionState(entry.execution_state);
    const timestamp = activityTimestampForQueue(entry);
    return Boolean(timestamp) && ['queued', 'running'].includes(state) && Date.now() - (timestamp?.getTime() ?? 0) > 24 * 60 * 60 * 1000;
  });
  const latestCodexCompletion = [...automationRuns]
    .filter((run) => run.automation_id === 'codex_workspace_execution' && normalizeAutomationRunStatus(run.status) === 'ok')
    .sort((left, right) => (runTimestamp(right)?.getTime() ?? 0) - (runTimestamp(left)?.getTime() ?? 0))[0];

  const summaryCards = [
    {
      label: 'Launchd workers',
      value: workerAutomations.length ? `${healthyWorkers}/${workerAutomations.length}` : '0',
      detail: workerAutomations.length ? 'healthy / expected' : 'no local workers reported',
      tone: healthyWorkers === workerAutomations.length && workerAutomations.length ? '#4ade80' : '#fbbf24',
    },
    {
      label: 'Claims in flight',
      value: String(claimedEntries.length),
      detail: claimedEntries.length ? summarize(claimedEntries[0]?.title ?? '', 38) : 'no cards currently claimed',
      tone: claimedEntries.length ? '#38bdf8' : '#94a3b8',
    },
    {
      label: 'Stale active lanes',
      value: String(staleRunningEntries.length),
      detail: staleRunningEntries.length ? summarize(staleRunningEntries[0]?.title ?? '', 38) : 'no stale queued/running cards',
      tone: staleRunningEntries.length ? '#f87171' : '#4ade80',
    },
    {
      label: 'Last Codex completion',
      value: latestCodexCompletion?.finished_at ? formatTimestamp(new Date(latestCodexCompletion.finished_at)) : '-',
      detail: latestCodexCompletion ? summarize(extractAutomationRunSummary(latestCodexCompletion) || 'latest execution completed', 44) : 'no successful run mirrored yet',
      tone: latestCodexCompletion ? '#c084fc' : '#94a3b8',
    },
  ];

  return (
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#08111f', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <div>
          <p style={{ color: '#22c55e', letterSpacing: '0.18em', fontSize: '11px', textTransform: 'uppercase' }}>Local workers</p>
          <h3 style={{ color: 'white', fontSize: '22px', margin: '4px 0' }}>Launchd and Codex health</h3>
          <p style={{ color: '#94a3b8', fontSize: '13px' }}>Thin Railway control plane, local launchd executors, and the latest Codex write-back signal.</p>
        </div>
        <div style={{ color: '#94a3b8', fontSize: '12px', textAlign: 'right' }}>
          <p>{failedEntries.length ? `${failedEntries.length} failed lane${failedEntries.length === 1 ? '' : 's'} need attention` : 'No failed execution lanes reported'}</p>
          <p>{workerAutomations.length ? `${workerAutomations.length} local automation${workerAutomations.length === 1 ? '' : 's'} mirrored` : 'Waiting for local automation mirror data'}</p>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        {summaryCards.map((card) => (
          <div key={card.label} style={{ padding: '14px', borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{card.label}</p>
            <p style={{ color: card.tone, fontSize: '20px', fontWeight: 700, margin: '6px 0' }}>{card.value}</p>
            <p style={{ color: '#64748b', fontSize: '12px' }}>{card.detail}</p>
          </div>
        ))}
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={opsHealthHeaderStyle}>Worker</th>
              <th style={opsHealthHeaderStyle}>Runtime</th>
              <th style={opsHealthHeaderStyle}>Latest signal</th>
              <th style={opsHealthHeaderStyle}>Last run</th>
            </tr>
          </thead>
          <tbody>
            {workerAutomations.map((item) => (
              <tr key={item.id}>
                <td style={opsHealthCellStyle}>
                  <div style={{ color: 'white', fontWeight: 600 }}>{item.name}</div>
                  <div style={{ color: '#64748b', fontSize: '12px' }}>{item.id}</div>
                </td>
                <td style={opsHealthCellStyle}>{statusBadge(String(item.runtime ?? item.status ?? 'unknown'))}</td>
                <td style={opsHealthCellStyle}>{item.last_status ? humanizeStatusLabel(item.last_status) : '-'}</td>
                <td style={opsHealthCellStyle}>{item.last_run_at ? formatTimestamp(new Date(item.last_run_at)) : '-'}</td>
              </tr>
            ))}
            {!workerAutomations.length && (
              <tr>
                <td colSpan={4} style={{ ...opsHealthCellStyle, color: '#64748b' }}>
                  Local worker automations have not been mirrored into Ops yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {failedEntries.length > 0 && (
        <div style={{ marginTop: '14px', padding: '14px 16px', borderRadius: '14px', border: '1px solid rgba(248,113,113,0.35)', backgroundColor: 'rgba(127,29,29,0.24)' }}>
          <p style={{ color: '#fca5a5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: '6px' }}>Latest failure</p>
          <p style={{ color: 'white', fontWeight: 600 }}>{failedEntries[0].title}</p>
          <p style={{ color: '#fecaca', fontSize: '13px' }}>
            {failedEntries[0].workspace_key} · {failedEntries[0].executor_status ?? failedEntries[0].execution_state}
            {failedEntries[0].last_transition_at ? ` · ${formatTimestamp(new Date(failedEntries[0].last_transition_at))}` : ''}
          </p>
        </div>
      )}
    </section>
  );
}

const opsHealthHeaderStyle: CSSProperties = {
  textAlign: 'left',
  fontSize: '11px',
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  color: '#64748b',
  padding: '0 0 10px',
};

const opsHealthCellStyle: CSSProperties = {
  padding: '10px 0',
  borderTop: '1px solid rgba(30, 41, 59, 0.7)',
  color: '#cbd5f5',
  fontSize: '13px',
  verticalAlign: 'top',
};

function OpenBrainPanel({ metrics, health }: { metrics: OpenBrainTelemetry | null; health: OpenBrainHealth | null }) {
  const storageLabel = health?.storage_backend === 'pgvector' ? 'Native vector mode' : health?.storage_backend === 'jsonb' ? 'JSON fallback' : 'Unknown';
  const serviceLabel = health?.search_ready ? 'Search ready' : health?.database_connected ? 'Memory store online' : 'Memory store offline';
  const subtitle =
    health?.storage_backend === 'pgvector'
      ? 'Capture + refresh telemetry from the native Postgres vector lane.'
      : 'Capture + refresh telemetry from the Postgres memory lane. JSON fallback is active until native vector support is available.';

  return (
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Open Brain</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>{subtitle}</p>
        </div>
        <p style={{ color: health?.database_connected ? '#22c55e' : '#f87171', fontSize: '12px' }}>{serviceLabel}</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <MiniMeta label="Storage" value={storageLabel} detail={health?.embedding_type ?? 'n/a'} />
        <MiniMeta label="Native Vector Ext" value={health?.vector_extension ? 'Enabled' : 'Unavailable'} detail="Current Postgres capability" />
        <MiniMeta
          label="Embedding Dimension"
          value={health?.configured_dimension ? `${health.configured_dimension}/${health.embedder_dimension}` : `${health?.embedder_dimension ?? 0}`}
          detail={health?.dimension_match ? 'DB and embedder aligned' : 'Running fallback storage mode'}
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <MiniStat label="Captures" value={metrics?.captures.total ?? 0} tone="#38bdf8" detail="All time" />
        <MiniStat label="New (24h)" value={metrics?.captures.last_24h ?? 0} tone="#4ade80" detail="Working memory" />
        <MiniStat label="Chunks" value={metrics?.vectors.total ?? 0} tone="#f97316" detail="Indexed memory rows" />
        <MiniStat label="Expiring" value={metrics?.vectors.with_expiry ?? 0} tone="#fbbf24" detail="Short-term" />
        <MiniStat label="Overdue" value={metrics?.vectors.overdue ?? 0} tone="#f87171" detail="Needs cleanup" />
        <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
          <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Last refresh</p>
          <p style={{ color: '#cbd5f5', fontSize: '18px', fontWeight: 600 }}>
            {metrics?.vectors.last_refresh_at ? formatTimestamp(new Date(metrics.vectors.last_refresh_at)) : '-'}
          </p>
          <p style={{ color: '#475569', fontSize: '12px' }}>memory_vectors.last_refreshed_at</p>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Source', 'Topics', 'Importance', 'Chunks', 'Created'].map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!metrics || metrics.recent_captures.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '12px 0', color: '#475569' }}>No captures recorded yet.</td>
              </tr>
            ) : (
              metrics.recent_captures.map((item) => (
                <tr key={item.id}>
                  <td style={{ padding: '10px 0', color: '#e2e8f0', fontWeight: 600 }}>{item.source ?? '-'}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{(item.topics ?? []).join(', ') || '-'}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{item.importance ?? '-'}</td>
                  <td style={{ padding: '10px 0', color: '#e2e8f0' }}>{item.chunk_count}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{item.created_at ? formatTimestamp(new Date(item.created_at)) : '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const STANDUP_ROOMS: {
  key: string;
  label: string;
  workspaceKey: string;
  description: string;
  participants: string[];
  sources: string[];
}[] = [
  {
    key: 'executive_ops',
    label: 'Executive Standup',
    workspaceKey: 'shared_ops',
    description: 'System-wide review across Chronicle, pruning cycles, heartbeat, dream cycle, PM board movement, and cross-workspace execution.',
    participants: ['Jean-Claude', 'Neo', 'Yoda'],
    sources: ['Codex Chronicle', 'Pruning Cycles', 'Heartbeat', 'Daily Brief', 'Dream Cycle', 'OpenClaw Crons', 'Local Device Loop'],
  },
  {
    key: 'operations',
    label: 'Operations Standup',
    workspaceKey: 'shared_ops',
    description: 'Maintenance lane for automation health, Open Brain continuity, delivery integrity, and local runtime behavior.',
    participants: ['Jean-Claude', 'Neo'],
    sources: ['Heartbeat', 'OpenClaw Crons', 'Pruning Cycles', 'Persistent State', 'PM Queue'],
  },
  {
    key: 'weekly_review',
    label: 'Weekly Review',
    workspaceKey: 'shared_ops',
    description: 'Retrospective and next-week planning driven by PM outcomes, prior meeting transcripts, runner results, and maintenance signals.',
    participants: ['Jean-Claude', 'Neo', 'Yoda'],
    sources: ['PM Board', 'Meeting Transcripts', 'Chronicle', 'Daily Brief', 'Runner Results'],
  },
  {
    key: 'saturday_vision',
    label: 'Saturday Vision Sync',
    workspaceKey: 'shared_ops',
    description: 'Strategy-only meeting for Johnnie, FEEZIE OS, and portfolio direction. No routine PM hygiene unless a conclusion clearly deserves promotion into real work.',
    participants: ['Jean-Claude', 'Neo', 'Yoda'],
    sources: ['Chronicle', 'Strategic Memos', 'Weekly Review', 'FEEZIE OS', 'Long-Term Goals'],
  },
  {
    key: 'linkedin-os',
    label: 'FEEZIE OS Standup',
    workspaceKey: 'linkedin-os',
    description: 'Workspace meeting for FEEZIE OS execution across the current LinkedIn lane and broader public visibility direction.',
    participants: ['Jean-Claude', 'Neo', 'Yoda'],
    sources: ['Codex Chronicle', 'Workspace Files', 'PM Board', 'Progress Pulse', 'Dream Cycle'],
  },
  {
    key: 'fusion-os',
    label: 'Fusion Standup',
    workspaceKey: 'fusion-os',
    description: 'Workspace meeting lane where Jean-Claude manages and Fusion Systems Operator executes inside Fusion only.',
    participants: ['Jean-Claude', 'Fusion Systems Operator'],
    sources: ['Chronicle', 'PM Board', 'Workspace Docs'],
  },
  {
    key: 'easyoutfitapp',
    label: 'EasyOutfitApp Standup',
    workspaceKey: 'easyoutfitapp',
    description: 'Workspace meeting lane where Jean-Claude manages and Easy Outfit Product Agent executes inside EasyOutfitApp only.',
    participants: ['Jean-Claude', 'Easy Outfit Product Agent'],
    sources: ['Chronicle', 'PM Board', 'Workspace Docs'],
  },
  {
    key: 'ai-swag-store',
    label: 'AI Swag Store Standup',
    workspaceKey: 'ai-swag-store',
    description: 'Workspace meeting lane where Jean-Claude manages and Commerce Growth Agent executes inside AI Swag Store only.',
    participants: ['Jean-Claude', 'Commerce Growth Agent'],
    sources: ['Chronicle', 'PM Board', 'Workspace Docs'],
  },
  {
    key: 'agc',
    label: 'AGC Standup',
    workspaceKey: 'agc',
    description: 'Workspace meeting lane where Jean-Claude manages and AGC Strategy Agent executes inside AGC only.',
    participants: ['Jean-Claude', 'AGC Strategy Agent'],
    sources: ['Chronicle', 'PM Board', 'Workspace Docs'],
  },
];

function PMBoardPanel({
  cards,
  reviewHygieneSummary,
  reviewProgressSummary,
  reviewProgressAudit,
  executionQueue,
  standups,
  automations,
  executiveFeed,
  error,
  queueError,
  onDispatch,
  onActOnPmCard,
  onActOnOwnerReviewCard,
  onOpenArtifactPath,
}: {
  cards: PMCard[];
  reviewHygieneSummary: PMReviewHygieneResult | null;
  reviewProgressSummary: PMAutoProgressResult | null;
  reviewProgressAudit: PMAutoProgressAuditReport | null;
  executionQueue: ExecutionQueueEntry[];
  standups: StandupEntry[];
  automations: Automation[];
  executiveFeed: ExecutiveFeed;
  error: string | null;
  queueError: string | null;
  onDispatch: (cardId: string, targetAgent?: string) => Promise<PMCardDispatchResult>;
  onActOnPmCard: (cardId: string, action: 'approve' | 'return' | 'blocked', options?: PMCardActionOptions) => Promise<PMCardActionResult>;
  onActOnOwnerReviewCard: (cardId: string, decision: OwnerReviewDecision, notes: string) => Promise<OwnerReviewActionResult>;
  onOpenArtifactPath: (path: string) => void;
}) {
  const buckets = useMemo(() => groupPmCards(cards), [cards]);
  const executionBuckets = useMemo(() => groupExecutionQueue(executionQueue), [executionQueue]);
  const rawUnifiedBoard = useMemo(() => buildUnifiedOpsBoard(cards, executionQueue), [cards, executionQueue]);
  const { board: unifiedBoard, hiddenOwnerReviewItems } = useMemo(
    () => applyOwnerReviewWipLimit(rawUnifiedBoard),
    [rawUnifiedBoard],
  );
  const activeCards = useMemo(() => cards.filter((card) => normalizeStatus(card.status) !== 'done'), [cards]);
  const recommendationItems = useMemo(
    () =>
      executiveFeed.pmRecommendations.flatMap((packet) =>
        packet.items.map((item) => ({
          ...item,
          packetId: packet.id,
          createdAt: packet.createdAt,
          path: packet.path,
        })),
      ),
    [executiveFeed.pmRecommendations],
  );
  const laneSummary = useMemo(() => buildPmLaneSummary(activeCards), [activeCards]);
  const automationCounts = useMemo(() => summarizeAutomationSources(automations), [automations]);
  const meetingOps = useMemo(() => buildMeetingOps(STANDUP_ROOMS, standups, cards, executionQueue), [standups, cards, executionQueue]);
  const healthyRoomCount = useMemo(() => meetingOps.rooms.filter((room) => room.status === 'ok').length, [meetingOps]);
  const latestMeetingAt = useMemo(() => {
    const timestamps = meetingOps.rooms
      .map((room) => room.latestEntry?.created_at)
      .filter((value): value is string => Boolean(value))
      .map((value) => new Date(value).getTime())
      .filter((value) => Number.isFinite(value));
    if (timestamps.length === 0) {
      return null;
    }
    return new Date(Math.max(...timestamps));
  }, [meetingOps]);
  const missingRoomCount = useMemo(() => meetingOps.rooms.filter((room) => room.status === 'missing').length, [meetingOps]);
  const staleLaneCount = meetingOps.staleReadyCount + meetingOps.staleReviewCount + meetingOps.staleRunningCount;
  const opsSummaryTone = staleLaneCount > 0 || missingRoomCount > 0 ? '#f59e0b' : executionBuckets.running.length > 0 ? '#22c55e' : '#38bdf8';
  const boardColumns: { key: UnifiedBoardLaneKey; label: string; detail: string }[] = [
    { key: 'todo', label: 'Backlog', detail: 'pm card exists, not in execution yet' },
    { key: 'ready', label: 'Ready', detail: 'Jean-Claude can open SOP now' },
    { key: 'queued', label: 'Queued', detail: 'opened and waiting on pickup' },
    { key: 'running', label: 'Running', detail: 'actively being worked' },
    { key: 'review', label: 'Review', detail: 'result returned, waiting on judgment' },
    { key: 'failed', label: 'System Recovery', detail: 'failed automation and execution retries' },
    { key: 'done', label: 'Done', detail: 'closed and kept for history' },
  ];
  const humanBoardColumns = useMemo(
    () => boardColumns.filter((column) => column.key !== 'failed' && column.key !== 'done'),
    [boardColumns],
  );
  const systemRecoveryColumn = useMemo(
    () =>
      boardColumns.find((column) => column.key === 'failed') ?? {
        key: 'failed' as const,
        label: 'System Recovery',
        detail: 'failed automation and execution retries',
      },
    [boardColumns],
  );
  const hiddenOwnerReviewCount = hiddenOwnerReviewItems.length;
  const visibleHumanCardCount = useMemo(
    () => humanBoardColumns.reduce((sum, column) => sum + unifiedBoard[column.key].length, 0),
    [humanBoardColumns, unifiedBoard],
  );
  const systemRecoveryCount = unifiedBoard.failed.length;
  const visibleReviewCount = unifiedBoard.review.length;
  const opsSummaryBullets = [
    `Board: ${visibleHumanCardCount} human-action card${visibleHumanCardCount === 1 ? '' : 's'} visible, ${systemRecoveryCount} system-recovery lane${systemRecoveryCount === 1 ? '' : 's'}, ${executionBuckets.running.length} running, ${visibleReviewCount} waiting on review${hiddenOwnerReviewCount > 0 ? ` (${hiddenOwnerReviewCount} more owner-review card${hiddenOwnerReviewCount === 1 ? '' : 's'} held in backlog)` : ''}.`,
    `Meetings: ${healthyRoomCount}/${meetingOps.rooms.length} healthy lanes, ${meetingOps.orphanStandupCount} orphan standup${meetingOps.orphanStandupCount === 1 ? '' : 's'}, ${missingRoomCount} missing room${missingRoomCount === 1 ? '' : 's'}.`,
    `Automation: ${automationCounts.total} visible job${automationCounts.total === 1 ? '' : 's'}, ${automationCounts.launchd} launchd-driven, latest meeting ${latestMeetingAt ? formatTimestamp(latestMeetingAt) : 'not recorded yet'}.`,
    staleLaneCount > 0
      ? `Attention: ${meetingOps.staleReadyCount} stale ready, ${meetingOps.staleReviewCount} stale review, ${meetingOps.staleRunningCount} stale running lane${staleLaneCount === 1 ? '' : 's'}.`
      : 'Attention: no stale ready/review/running execution lanes are currently visible.',
  ];
  const compactOverview = [
    { label: 'Human Action', value: `${visibleHumanCardCount}`, detail: hiddenOwnerReviewCount > 0 ? `${hiddenOwnerReviewCount} owner-review held` : 'owner + host work' },
    { label: 'System Recovery', value: `${systemRecoveryCount}`, detail: 'failed automation lanes' },
    { label: 'Closed', value: `${buckets.done.length}`, detail: 'resolved history' },
    { label: 'Standup Queue', value: `${recommendationItems.length}`, detail: 'pending promotion' },
    { label: 'Ready', value: `${executionBuckets.ready.length}`, detail: 'Jean-Claude can open now' },
    { label: 'Running', value: `${executionBuckets.running.length}`, detail: 'live execution' },
    { label: 'Workspaces', value: `${laneSummary.workspaceLanes}`, detail: 'active lane buckets' },
    { label: 'Healthy Rooms', value: `${healthyRoomCount}/${meetingOps.rooms.length}`, detail: latestMeetingAt ? formatTimestamp(latestMeetingAt) : 'no transcript yet' },
    { label: 'Automations', value: `${automationCounts.total}`, detail: `${automationCounts.launchd} launchd jobs` },
  ];
  const [dispatchingCardId, setDispatchingCardId] = useState<string | null>(null);
  const [dispatchFeedback, setDispatchFeedback] = useState<string | null>(null);
  const [dispatchError, setDispatchError] = useState<string | null>(null);
  const [selectedBoardCardId, setSelectedBoardCardId] = useState<string | null>(null);
  const [selectedBoardSnapshot, setSelectedBoardSnapshot] = useState<{
    boardItem: UnifiedBoardItem;
    card: PMCard;
    linkedStandups: StandupEntry[];
  } | null>(null);
  const unifiedBoardItems = useMemo(() => Object.values(unifiedBoard).flat(), [unifiedBoard]);
  const ownerAttentionItems = useMemo(() => buildOwnerAttentionItems(unifiedBoardItems), [unifiedBoardItems]);
  const ownerAttentionCounts = useMemo(
    () => ({
      decision: ownerAttentionItems.filter((item) => item.kind === 'decision').length,
      stale: ownerAttentionItems.filter((item) => item.kind === 'stale').length,
      update: ownerAttentionItems.filter((item) => item.kind === 'update').length,
    }),
    [ownerAttentionItems],
  );
  const ownerInboxItems = useMemo(
    () => ownerAttentionItems.filter((item) => item.kind !== 'update'),
    [ownerAttentionItems],
  );
  const reviewProgressWindowSummary = reviewProgressAudit?.summary ?? null;
  const recentAutoProgressItems = useMemo(
    () =>
      (reviewProgressAudit?.entries ?? [])
        .flatMap((entry) =>
          (entry.processed ?? []).map((item) => ({
            ...item,
            processed_at: entry.processed_at,
          })),
        )
        .slice(0, 5),
    [reviewProgressAudit],
  );
  const [showAutoProgressHistory, setShowAutoProgressHistory] = useState(false);
  const liveSelectedBoardItem = useMemo(
    () => (selectedBoardCardId ? unifiedBoardItems.find((item) => item.cardId === selectedBoardCardId) ?? null : null),
    [selectedBoardCardId, unifiedBoardItems],
  );
  const liveSelectedBoardCard = useMemo(
    () => (selectedBoardCardId ? cards.find((card) => card.id === selectedBoardCardId) ?? null : null),
    [cards, selectedBoardCardId],
  );
  const liveSelectedBoardLinkedStandups = useMemo(
    () => (liveSelectedBoardCard ? linkedStandupsForCard(liveSelectedBoardCard, standups) : []),
    [liveSelectedBoardCard, standups],
  );
  const selectedBoardSnapshotMatches = selectedBoardSnapshot?.card.id === selectedBoardCardId;
  const selectedBoardItem = selectedBoardSnapshotMatches ? selectedBoardSnapshot.boardItem : liveSelectedBoardItem;
  const selectedBoardCard = selectedBoardSnapshotMatches ? selectedBoardSnapshot.card : liveSelectedBoardCard;
  const selectedBoardLinkedStandups = selectedBoardSnapshotMatches ? selectedBoardSnapshot.linkedStandups : liveSelectedBoardLinkedStandups;
  const recentClosedItems = useMemo(() => unifiedBoard.done.slice(0, 12), [unifiedBoard.done]);

  const handleDispatch = useCallback(
    async (entry: ExecutionQueueEntry) => {
      try {
        setDispatchingCardId(entry.card_id);
        setDispatchError(null);
        setDispatchFeedback(null);
        const result = await onDispatch(entry.card_id, entry.target_agent || 'Jean-Claude');
        setDispatchFeedback(
          `Jean-Claude opened the execution lane for "${result.card.title}" and routed it toward ${result.queue_entry.target_agent}.`,
        );
      } catch (dispatchIssue) {
        setDispatchError(toErrorMessage(dispatchIssue));
      } finally {
        setDispatchingCardId(null);
      }
    },
    [onDispatch],
  );

  useEffect(() => {
    if (!selectedBoardCardId) {
      setSelectedBoardSnapshot(null);
      return undefined;
    }
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedBoardCardId(null);
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [selectedBoardCardId]);

  useEffect(() => {
    if (!selectedBoardCardId) {
      return;
    }
    if (selectedBoardSnapshot?.card.id === selectedBoardCardId) {
      return;
    }
    if (liveSelectedBoardItem && liveSelectedBoardCard) {
      setSelectedBoardSnapshot({
        boardItem: liveSelectedBoardItem,
        card: liveSelectedBoardCard,
        linkedStandups: liveSelectedBoardLinkedStandups,
      });
    }
  }, [
    selectedBoardCardId,
    selectedBoardSnapshot,
    liveSelectedBoardItem,
    liveSelectedBoardCard,
    liveSelectedBoardLinkedStandups,
  ]);

  const renderOperationalBoardCard = useCallback(
    (item: UnifiedBoardItem, laneKey: UnifiedBoardLaneKey) => {
      const theme = workspaceBoardTheme(item.workspaceKey);
      return (
        <article
          key={`${laneKey}-${item.id}`}
          role="button"
          tabIndex={0}
          onClick={() => setSelectedBoardCardId(item.cardId)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setSelectedBoardCardId(item.cardId);
            }
          }}
          style={{
            borderRadius: '10px',
            border: `1px solid ${theme.border}`,
            backgroundColor: theme.background,
            boxShadow: `inset 0 3px 0 0 ${theme.accent}`,
            padding: '10px',
            cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '6px', marginBottom: '6px', alignItems: 'center' }}>
            <p style={{ color: 'white', fontWeight: 600, margin: 0, fontSize: '13px', lineHeight: 1.35 }}>{item.title}</p>
            {statusBadge(item.executionState ? displayExecutionStateLabel(item.executionState) : displayPmStatusLabel(item.pmStatus, item.lane, item.executionState))}
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '11px', color: '#cbd5e1', marginBottom: '6px' }}>
            <span style={{ padding: '3px 8px', borderRadius: '999px', backgroundColor: `${theme.accent}22`, color: theme.accent }}>
              {meetingLabelForWorkspace(item.workspaceKey)}
            </span>
            {item.executionState && statusBadge(displayPmStatusLabel(item.pmStatus, item.lane, item.executionState))}
            {!item.executionState && item.owner ? <span>{item.owner}</span> : null}
          </div>
          {item.reason && <p style={{ color: '#e2e8f0', fontSize: '12px', lineHeight: 1.45, margin: '0 0 8px' }}>{item.reason}</p>}
          <div style={{ color: '#94a3b8', fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {item.queueEntry?.front_door_agent ? <span>Intake: {item.queueEntry.front_door_agent}</span> : null}
            {item.queueEntry ? <span>Manager: {displayManagerAgent(item.workspaceKey, item.managerAgent)}</span> : null}
            {item.queueEntry ? <span>Target: {displayTargetAgent(item.workspaceKey, item.targetAgent)}</span> : null}
            {item.workspaceAgent ? <span>Agent: {displayWorkspaceAgent(item.workspaceKey, item.workspaceAgent)}</span> : null}
            {item.executionMode ? <span>Mode: {item.executionMode}</span> : null}
            {displayWorkerStatusLabel(item.queueEntry) ? <span>Worker: {displayWorkerStatusLabel(item.queueEntry)}</span> : null}
            {item.queueEntry?.manager_attention_required ? <span>Manager attention: required</span> : null}
            <span>Updated: {item.updatedAt ? formatTimestamp(new Date(item.updatedAt)) : '-'}</span>
          </div>
          {laneKey === 'ready' && item.queueEntry ? (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                void handleDispatch(item.queueEntry as ExecutionQueueEntry);
              }}
              disabled={dispatchingCardId === item.cardId}
              style={{
                marginTop: '10px',
                width: '100%',
                borderRadius: '999px',
                border: `1px solid ${theme.border}`,
                backgroundColor: dispatchingCardId === item.cardId ? '#0f172a' : '#0f3d37',
                color: '#d1fae5',
                padding: '8px 10px',
                cursor: dispatchingCardId === item.cardId ? 'wait' : 'pointer',
                fontWeight: 600,
                fontSize: '12px',
              }}
            >
              {dispatchingCardId === item.cardId ? 'Queueing...' : 'Open SOP'}
            </button>
          ) : null}
        </article>
      );
    },
    [dispatchingCardId, handleDispatch],
  );

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>PM Board</p>
        <h2 style={{ fontSize: '28px', margin: '4px 0', color: 'white' }}>Execution truth</h2>
        <p style={{ color: '#94a3b8', maxWidth: '980px' }}>Standups feed this board. The board stays visible first; meeting detail and recommendation detail stay nearby but collapsed until you need them.</p>
      </div>
      {error && <SectionAlert message={`${TELEMETRY_LABELS.pmCards}: ${error}`} />}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        {compactOverview.map((item) => (
          <div key={`overview-${item.label}`} style={{ borderRadius: '999px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '8px 12px', display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{item.label}</span>
            <span style={{ color: '#e2e8f0', fontSize: '16px', fontWeight: 700 }}>{item.value}</span>
            <span style={{ color: '#475569', fontSize: '12px' }}>{item.detail}</span>
          </div>
        ))}
      </div>
      <section style={{ borderRadius: '16px', border: `1px solid ${opsSummaryTone}33`, backgroundColor: `${opsSummaryTone}10`, padding: '14px' }}>
        <p style={{ color: opsSummaryTone, letterSpacing: '0.18em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Daily Ops Summary</p>
        <div style={{ display: 'grid', gap: '6px' }}>
          {opsSummaryBullets.map((line) => (
            <p key={line} style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
              {line}
            </p>
          ))}
        </div>
      </section>
      {(Number(reviewProgressSummary?.processed_count ?? 0) > 0 || Number(reviewProgressWindowSummary?.processed_count ?? 0) > 0) && (
        <section style={{ borderRadius: '16px', border: '1px solid rgba(34,197,94,0.22)', backgroundColor: 'rgba(34,197,94,0.08)', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '10px' }}>
            <div>
              <p style={{ color: '#22c55e', letterSpacing: '0.18em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Recent Automatic Decisions</p>
              <p style={{ color: '#f8fafc', fontSize: '12px', fontWeight: 700, margin: '0 0 6px' }}>History only. Do not work cards from this section.</p>
              <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                This is a recent audit trail of routine PM cards the system already processed. Use <strong>What Needs You</strong> for current action.
              </p>
            </div>
            {recentAutoProgressItems.length > 0 ? (
              <button
                type="button"
                onClick={() => setShowAutoProgressHistory((value) => !value)}
                style={{
                  borderRadius: '999px',
                  border: '1px solid rgba(148,163,184,0.24)',
                  backgroundColor: 'rgba(15,23,42,0.65)',
                  color: '#e2e8f0',
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '7px 11px',
                  cursor: 'pointer',
                }}
              >
                {showAutoProgressHistory ? 'Hide history' : `Show history (${recentAutoProgressItems.length})`}
              </button>
            ) : null}
          </div>
          <div style={{ marginBottom: recentAutoProgressItems.length > 0 ? '12px' : 0 }}>
            <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
              Routine PM review cards auto-advance, auto-return, or escalate based on the completion contract instead of waiting for manual cleanup.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: recentAutoProgressItems.length > 0 ? '12px' : 0 }}>
            <div style={{ borderRadius: '999px', border: '1px solid rgba(34,197,94,0.28)', backgroundColor: 'rgba(34,197,94,0.08)', padding: '7px 11px', color: '#dcfce7', fontSize: '12px' }}>
              This refresh: advanced {reviewProgressSummary?.advanced_count ?? 0}
            </div>
            <div style={{ borderRadius: '999px', border: '1px solid rgba(251,191,36,0.28)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '7px 11px', color: '#fef3c7', fontSize: '12px' }}>
              Returned: {reviewProgressSummary?.returned_count ?? 0}
            </div>
            <div style={{ borderRadius: '999px', border: '1px solid rgba(248,113,113,0.28)', backgroundColor: 'rgba(248,113,113,0.08)', padding: '7px 11px', color: '#fecaca', fontSize: '12px' }}>
              Escalated: {reviewProgressSummary?.escalated_count ?? 0}
            </div>
            <div style={{ borderRadius: '999px', border: '1px solid rgba(148,163,184,0.24)', backgroundColor: 'rgba(148,163,184,0.08)', padding: '7px 11px', color: '#cbd5e1', fontSize: '12px' }}>
              Last 24h: advanced {reviewProgressWindowSummary?.advanced_count ?? 0}, returned {reviewProgressWindowSummary?.returned_count ?? 0}, escalated {reviewProgressWindowSummary?.escalated_count ?? 0}
            </div>
          </div>
          {showAutoProgressHistory && recentAutoProgressItems.length > 0 && (
            <div style={{ display: 'grid', gap: '8px' }}>
              {recentAutoProgressItems.map((item) => (
                <article key={`auto-progress-${item.card_id}-${item.processed_at}`} style={{ borderRadius: '12px', border: '1px solid rgba(148,163,184,0.18)', backgroundColor: '#08101f', padding: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '4px' }}>
                    <p style={{ color: 'white', fontSize: '14px', fontWeight: 700, margin: 0 }}>{autoProgressSourceTitle(item)}</p>
                    <span style={{ color: '#94a3b8', fontSize: '12px' }}>{item.processed_at ? formatTimestamp(new Date(item.processed_at)) : '-'}</span>
                  </div>
                  <p style={{ color: '#7dd3fc', fontSize: '11px', letterSpacing: '0.08em', textTransform: 'uppercase', margin: '0 0 4px' }}>History Event</p>
                  <p style={{ color: '#cbd5e1', fontSize: '12px', margin: '0 0 6px' }}>{describeAutoProgressItem(item)}</p>
                  <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{describeAutoProgressOutcome(item)}</p>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
      <section style={{ borderRadius: '18px', border: '1px solid rgba(56,189,248,0.22)', backgroundColor: '#08101f', padding: '14px' }}>
        <div style={{ marginBottom: '10px' }}>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>What Needs You</p>
          <h3 style={{ fontSize: '20px', color: 'white', margin: '4px 0' }}>Owner inbox</h3>
          <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>
            This is the owner-sorted list. Start here. Ignore the rest of the board unless priorities changed.
          </p>
          {hiddenOwnerReviewCount > 0 ? (
            <p style={{ color: '#fbbf24', fontSize: '12px', margin: '8px 0 0' }}>
              Showing the top {OWNER_REVIEW_ACTIVE_WIP_LIMIT} owner-review cards. {hiddenOwnerReviewCount} more pending owner-review card{hiddenOwnerReviewCount === 1 ? '' : 's'} are held in backlog until you clear the current set.
            </p>
          ) : null}
          {Number(reviewHygieneSummary?.resolved_count ?? 0) > 0 ? (
            <p style={{ color: '#86efac', fontSize: '12px', margin: '8px 0 0' }}>
              The system cleared {reviewHygieneSummary?.resolved_count} stale review card{reviewHygieneSummary?.resolved_count === 1 ? '' : 's'} on this refresh.
            </p>
          ) : null}
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
          <div style={{ borderRadius: '999px', border: '1px solid rgba(251,191,36,0.28)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '7px 11px', color: '#fef3c7', fontSize: '12px' }}>
            Needs action: {ownerAttentionCounts.decision}
          </div>
          <div style={{ borderRadius: '999px', border: '1px solid rgba(248,113,113,0.28)', backgroundColor: 'rgba(248,113,113,0.08)', padding: '7px 11px', color: '#fecaca', fontSize: '12px' }}>
            Probably stale: {ownerAttentionCounts.stale}
          </div>
          <div style={{ borderRadius: '999px', border: '1px solid rgba(148,163,184,0.24)', backgroundColor: 'rgba(148,163,184,0.08)', padding: '7px 11px', color: '#cbd5e1', fontSize: '12px' }}>
            System-managed: {ownerAttentionCounts.update}
          </div>
          {hiddenOwnerReviewCount > 0 ? (
            <div style={{ borderRadius: '999px', border: '1px solid rgba(56,189,248,0.24)', backgroundColor: 'rgba(56,189,248,0.08)', padding: '7px 11px', color: '#bae6fd', fontSize: '12px' }}>
              Owner-review backlog: {hiddenOwnerReviewCount}
            </div>
          ) : null}
        </div>
        {ownerInboxItems.length === 0 ? (
          <EmptyPanel message={ownerAttentionCounts.update > 0 ? 'Nothing needs your action right now. The remaining cards look like background updates.' : 'Nothing currently looks like it needs your action.'} compact />
        ) : (
          <div style={{ display: 'grid', gap: '10px' }}>
            {ownerInboxItems.map((item) => {
              const theme = workspaceBoardTheme(item.workspaceKey);
              const tone =
                item.kind === 'decision'
                  ? item.attentionClass === 'needs_host'
                    ? { label: 'Needs host step', color: '#fef3c7', border: 'rgba(251,191,36,0.28)', background: 'rgba(251,191,36,0.08)' }
                    : { label: 'Needs your call', color: '#fef3c7', border: 'rgba(251,191,36,0.28)', background: 'rgba(251,191,36,0.08)' }
                  : item.kind === 'stale'
                    ? { label: 'Probably stale', color: '#fecaca', border: 'rgba(248,113,113,0.28)', background: 'rgba(248,113,113,0.08)' }
                    : { label: 'System-managed', color: '#cbd5e1', border: 'rgba(148,163,184,0.24)', background: 'rgba(148,163,184,0.08)' };
              return (
                <article
                  key={`owner-inbox-${item.cardId}`}
                  style={{
                    borderRadius: '14px',
                    border: `1px solid ${theme.border}`,
                    backgroundColor: theme.background,
                    padding: '12px',
                    display: 'grid',
                    gap: '8px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                      <span style={{ borderRadius: '999px', border: `1px solid ${tone.border}`, backgroundColor: tone.background, color: tone.color, padding: '4px 8px', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase' }}>
                        {tone.label}
                      </span>
                      <span style={{ color: theme.accent, fontSize: '12px' }}>{meetingLabelForWorkspace(item.workspaceKey)}</span>
                    </div>
                    <span style={{ color: '#94a3b8', fontSize: '12px' }}>{item.updatedAt ? formatTimestamp(new Date(item.updatedAt)) : '-'}</span>
                  </div>
                  <p style={{ color: 'white', fontSize: '15px', fontWeight: 700, margin: 0 }}>{item.title}</p>
                  <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{item.summary}</p>
                  <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{item.nextAction}</p>
                  <div>
                    <button
                      type="button"
                      onClick={() => setSelectedBoardCardId(item.cardId)}
                      style={{
                        borderRadius: '999px',
                        border: `1px solid ${theme.border}`,
                        backgroundColor: '#0f172a',
                        color: '#f8fafc',
                        padding: '8px 12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      Open card
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
      <details style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '12px 14px' }}>
        <summary style={{ cursor: 'pointer', color: 'white', fontWeight: 700, listStyle: 'none' }}>
          Meeting lanes and standup context
          <span style={{ color: '#64748b', fontWeight: 400, marginLeft: '10px', fontSize: '13px' }}>
            {healthyRoomCount}/{meetingOps.rooms.length} healthy · {recommendationItems.length} pending recommendations
          </span>
        </summary>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px', marginTop: '12px' }}>
          {STANDUP_ROOMS.map((room) => {
            const roomHealth = meetingOps.byRoomKey[room.key];
            const itemCount = laneSummary.byWorkspace[room.workspaceKey] ?? 0;
            const recommendationCount = recommendationItems.filter((item) => item.workspaceKey === room.workspaceKey).length;
            const latestMeetingLabel = roomHealth?.latestEntry?.created_at
              ? formatTimestamp(new Date(roomHealth.latestEntry.created_at))
              : roomHealth?.status === 'planned'
                ? 'Not scheduled yet'
                : 'No transcript yet';
            const roomStatus =
              recommendationCount > 0 && (!roomHealth || roomHealth.status === 'planned')
                ? 'active'
                : roomHealth?.status ?? 'planned';
            return (
              <article key={room.key} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
                  <p style={{ color: 'white', fontWeight: 700, margin: 0, fontSize: '14px' }}>{room.label}</p>
                  {statusBadge(roomStatus)}
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', color: '#94a3b8', fontSize: '12px' }}>
                  <span>PM {itemCount}</span>
                  <span>Pending {recommendationCount}</span>
                  <span>{latestMeetingLabel}</span>
                </div>
              </article>
            );
          })}
        </div>
        <div style={{ display: 'grid', gap: '10px', marginTop: '12px' }}>
          {recommendationItems.length === 0 ? (
            <EmptyPanel message="No standup-generated PM recommendations yet." compact />
          ) : (
            recommendationItems.map((item, index) => (
              <article key={`${item.packetId}-${index}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
                  <p style={{ color: 'white', fontWeight: 600, margin: 0 }}>{item.title}</p>
                  {statusBadge(item.status)}
                </div>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>
                  <span>{meetingLabelForWorkspace(item.workspaceKey)}</span>
                  <span>{item.ownerAgent}</span>
                  <span>{item.createdAt ? formatTimestamp(new Date(item.createdAt)) : 'Pending promotion'}</span>
                </div>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{item.reason}</p>
              </article>
            ))
          )}
        </div>
      </details>
      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '14px' }}>
        <div style={{ marginBottom: '10px' }}>
          <p style={{ color: '#22c55e', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Operational Board</p>
          <h3 style={{ fontSize: '20px', color: 'white', margin: '4px 0' }}>One board for PM + execution</h3>
          <p style={{ color: '#94a3b8', fontSize: '13px' }}>Human-action lanes stay visible first. System recovery is separated below. Closed and cancelled cards fall out of the main board and stay in collapsed history.</p>
        </div>
        {queueError && <SectionAlert message={`${TELEMETRY_LABELS.executionQueue}: ${queueError}`} />}
        {dispatchError && <SectionAlert message={dispatchError} />}
        {dispatchFeedback && <SectionAlert message={dispatchFeedback} />}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {humanBoardColumns.map((column) => (
            <div key={`board-meta-${column.key}`} style={{ borderRadius: '999px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '7px 11px', display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{column.label}</span>
              <span style={{ color: '#e2e8f0', fontSize: '15px', fontWeight: 700 }}>{unifiedBoard[column.key].length}</span>
            </div>
          ))}
          <div style={{ borderRadius: '999px', border: '1px solid rgba(248,113,113,0.24)', backgroundColor: 'rgba(248,113,113,0.08)', padding: '7px 11px', display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ color: '#fecaca', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{systemRecoveryColumn.label}</span>
            <span style={{ color: '#fee2e2', fontSize: '15px', fontWeight: 700 }}>{systemRecoveryCount}</span>
          </div>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${humanBoardColumns.length}, minmax(0, 1fr))`,
            gap: '10px',
            marginTop: '12px',
            alignItems: 'start',
          }}
        >
          {humanBoardColumns.map((column) => (
            <div
              key={column.key}
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#050b19',
                padding: '12px',
                height: 'clamp(360px, calc(100vh - 360px), 560px)',
                overflowY: 'auto',
                minWidth: 0,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                <p style={{ color: 'white', fontWeight: 700, margin: 0, fontSize: '14px' }}>{column.label}</p>
                <span style={{ color: '#64748b', fontSize: '11px' }}>{unifiedBoard[column.key].length}</span>
              </div>
              <p style={{ color: '#64748b', fontSize: '11px', margin: '0 0 10px' }}>{column.detail}</p>
              {column.key === 'review' && hiddenOwnerReviewCount > 0 ? (
                <p style={{ color: '#fbbf24', fontSize: '11px', margin: '0 0 10px' }}>
                  {hiddenOwnerReviewCount} more owner-review card{hiddenOwnerReviewCount === 1 ? '' : 's'} are held in backlog so the active review lane stays capped at {OWNER_REVIEW_ACTIVE_WIP_LIMIT}.
                </p>
              ) : null}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {unifiedBoard[column.key].length === 0 && <p style={{ color: '#475569', fontSize: '12px' }}>Nothing in this lane yet.</p>}
                {unifiedBoard[column.key].map((item) => renderOperationalBoardCard(item, column.key))}
              </div>
            </div>
          ))}
        </div>
        <section style={{ marginTop: '12px', borderRadius: '14px', border: '1px solid rgba(248,113,113,0.22)', backgroundColor: 'rgba(127,29,29,0.12)', padding: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '4px', flexWrap: 'wrap' }}>
            <p style={{ color: '#fee2e2', fontWeight: 700, margin: 0, fontSize: '14px' }}>{systemRecoveryColumn.label}</p>
            <span style={{ color: '#fecaca', fontSize: '11px' }}>{systemRecoveryCount}</span>
          </div>
          <p style={{ color: '#fca5a5', fontSize: '11px', margin: '0 0 10px' }}>{systemRecoveryColumn.detail}</p>
          <p style={{ color: '#cbd5e1', fontSize: '12px', lineHeight: 1.55, margin: '0 0 10px' }}>
            These are failed autonomous or execution lanes. They stay visible for deliberate recovery work, not because they are ordinary owner approvals or host confirmations.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {systemRecoveryCount === 0 ? <p style={{ color: '#475569', fontSize: '12px', margin: 0 }}>Nothing in system recovery right now.</p> : null}
            {unifiedBoard.failed.map((item) => renderOperationalBoardCard(item, systemRecoveryColumn.key))}
          </div>
        </section>
        <details style={{ marginTop: '12px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '12px 14px' }}>
          <summary style={{ cursor: 'pointer', color: 'white', fontWeight: 700, listStyle: 'none' }}>
            Recent closed cards
            <span style={{ color: '#64748b', fontWeight: 400, marginLeft: '10px', fontSize: '13px' }}>
              {unifiedBoard.done.length} total
            </span>
          </summary>
          <p style={{ color: '#94a3b8', fontSize: '12px', margin: '10px 0 0' }}>
            Closed work stays here for traceability, but it no longer crowds the active board.
          </p>
          <div style={{ display: 'grid', gap: '8px', marginTop: '12px' }}>
            {recentClosedItems.length === 0 ? (
              <p style={{ color: '#475569', fontSize: '12px', margin: 0 }}>No closed cards in the current snapshot.</p>
            ) : (
              recentClosedItems.map((item) => {
                const theme = workspaceBoardTheme(item.workspaceKey);
                return (
                  <article
                    key={`done-history-${item.id}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedBoardCardId(item.cardId)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setSelectedBoardCardId(item.cardId);
                      }
                    }}
                    style={{
                      borderRadius: '10px',
                      border: `1px solid ${theme.border}`,
                      backgroundColor: theme.background,
                      padding: '10px',
                      cursor: 'pointer',
                    }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
                        <p style={{ color: 'white', fontWeight: 600, margin: 0, fontSize: '13px', lineHeight: 1.35 }}>{item.title}</p>
                        {statusBadge(item.executionState ? displayExecutionStateLabel(item.executionState) : displayPmStatusLabel(item.pmStatus, item.lane, item.executionState))}
                      </div>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', fontSize: '11px', color: '#cbd5e1' }}>
                      <span style={{ padding: '3px 8px', borderRadius: '999px', backgroundColor: `${theme.accent}22`, color: theme.accent }}>
                        {meetingLabelForWorkspace(item.workspaceKey)}
                      </span>
                      <span>Updated: {item.updatedAt ? formatTimestamp(new Date(item.updatedAt)) : '-'}</span>
                    </div>
                  </article>
                );
              })
            )}
          </div>
        </details>
      </section>
      {selectedBoardItem && selectedBoardCard ? (
        <PMCardDetailModal
          key={selectedBoardCard.id}
          boardItem={selectedBoardItem}
          card={selectedBoardCard}
          linkedStandups={selectedBoardLinkedStandups}
          boardColumns={boardColumns}
          onClose={() => setSelectedBoardCardId(null)}
          onSelectCard={(cardId) => setSelectedBoardCardId(cardId)}
          onDispatch={onDispatch}
          onActOnPmCard={onActOnPmCard}
          onActOnOwnerReviewCard={onActOnOwnerReviewCard}
          onOpenArtifactPath={onOpenArtifactPath}
        />
      ) : null}
    </section>
  );
}

function PMCardDetailModal({
  boardItem,
  card,
  linkedStandups,
  boardColumns,
  onClose,
  onSelectCard,
  onDispatch,
  onActOnPmCard,
  onActOnOwnerReviewCard,
  onOpenArtifactPath,
}: {
  boardItem: UnifiedBoardItem;
  card: PMCard;
  linkedStandups: StandupEntry[];
  boardColumns: { key: UnifiedBoardLaneKey; label: string; detail: string }[];
  onClose: () => void;
  onSelectCard: (cardId: string | null) => void;
  onDispatch: (cardId: string, targetAgent?: string) => Promise<PMCardDispatchResult>;
  onActOnPmCard: (cardId: string, action: 'approve' | 'return' | 'blocked', options?: PMCardActionOptions) => Promise<PMCardActionResult>;
  onActOnOwnerReviewCard: (cardId: string, decision: OwnerReviewDecision, notes: string) => Promise<OwnerReviewActionResult>;
  onOpenArtifactPath: (path: string) => void;
}) {
  const [activeTab, setActiveTab] = useState<'overview' | 'evidence' | 'outcomes' | 'raw'>('overview');
  const [actioningCardId, setActioningCardId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const theme = workspaceBoardTheme(boardItem.workspaceKey);
  const guidance = boardItemGuidance(boardItem);
  const payload = card.payload ?? {};
  const pmReviewPolicy =
    payload.pm_review_policy && typeof payload.pm_review_policy === 'object'
      ? (payload.pm_review_policy as PMReviewPolicyPayload)
      : null;
  const ownerReviewPayload =
    payload.owner_review && typeof payload.owner_review === 'object'
      ? (payload.owner_review as OwnerReviewCardPayload)
      : null;
  const hostActionPayload =
    payload.host_action_required && typeof payload.host_action_required === 'object'
      ? (payload.host_action_required as HostActionRequiredPayload)
      : null;
  const hostActionFollowupPayload =
    payload.host_action_followup && typeof payload.host_action_followup === 'object'
      ? (payload.host_action_followup as HostActionRequiredPayload)
      : null;
  const hostActionProofRequired = Array.isArray(hostActionPayload?.proof_required)
    ? hostActionPayload.proof_required.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  const isHostActionCard = Boolean(hostActionPayload);
  const displayCardTitle = ownerReviewDisplayTitle(card, ownerReviewPayload);
  const isOwnerReviewCard = card.link_type === 'owner_review' || Boolean(ownerReviewPayload?.queue_id);
  const isPendingOwnerReview =
    isOwnerReviewCard &&
    (ownerReviewPayload?.sync_state === 'pending_owner_review' ||
      ownerReviewPayload?.approval_status === 'owner_review_required' ||
      boardItem.lane === 'review');
  const [ownerReviewNotes, setOwnerReviewNotes] = useState(ownerReviewPayload?.current_notes ?? '');
  const [ownerReviewNotesDirty, setOwnerReviewNotesDirty] = useState(false);
  const [resolutionMode, setResolutionMode] = useState<PMCardResolutionMode | null>(pmReviewPolicy?.recommended_resolution_mode ?? null);
  const [resolutionNote, setResolutionNote] = useState('');
  const [resolutionInputsDirty, setResolutionInputsDirty] = useState(false);
  const [nextCardTitle, setNextCardTitle] = useState(pmReviewPolicy?.suggested_next_title ?? '');
  const [nextCardReason, setNextCardReason] = useState(pmReviewPolicy?.suggested_next_reason ?? '');
  const rawSource = boardItem.source ?? card.source ?? 'manual';
  const linkType = typeof card.link_type === 'string' && card.link_type.trim() ? card.link_type.trim() : 'manual';
  const linkId = typeof card.link_id === 'string' && card.link_id.trim() ? card.link_id.trim() : null;
  const createdFromStandupId =
    typeof payload.created_from_standup_id === 'string' && payload.created_from_standup_id.trim()
      ? payload.created_from_standup_id.trim()
      : null;
  const createdFromPrepId =
    typeof payload.created_from_prep_id === 'string' && payload.created_from_prep_id.trim() ? payload.created_from_prep_id.trim() : null;
  const recommendationPath =
    typeof payload.recommendation_path === 'string' && payload.recommendation_path.trim() ? payload.recommendation_path.trim() : null;
  const latestExecutionResult =
    payload.latest_execution_result && typeof payload.latest_execution_result === 'object'
      ? (payload.latest_execution_result as Record<string, unknown>)
      : null;
  const latestExecutionSummary =
    typeof latestExecutionResult?.summary === 'string' && latestExecutionResult.summary.trim() ? latestExecutionResult.summary.trim() : null;
  const latestManualReview =
    payload.latest_manual_review && typeof payload.latest_manual_review === 'object'
      ? (payload.latest_manual_review as Record<string, unknown>)
      : null;
  const hostActionSteps = Array.isArray(hostActionPayload?.steps)
    ? hostActionPayload.steps.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  const ownerReviewProofAnchors = Array.isArray(ownerReviewPayload?.proof_anchors)
    ? ownerReviewPayload?.proof_anchors.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  const ownerReviewAssessment =
    ownerReviewPayload?.system_assessment && typeof ownerReviewPayload.system_assessment === 'object'
      ? ownerReviewPayload.system_assessment
      : null;
  const ownerDecisionScaffold =
    ownerReviewPayload?.decision_scaffold && typeof ownerReviewPayload.decision_scaffold === 'object'
      ? ownerReviewPayload.decision_scaffold
      : null;
  const executionPacketPath =
    typeof boardItem.queueEntry?.execution_packet_path === 'string' && boardItem.queueEntry.execution_packet_path.trim()
      ? boardItem.queueEntry.execution_packet_path.trim()
      : null;
  const sopArtifactPath =
    typeof boardItem.queueEntry?.sop_path === 'string' && boardItem.queueEntry.sop_path.trim() ? boardItem.queueEntry.sop_path.trim() : null;
  const briefingArtifactPath =
    typeof boardItem.queueEntry?.briefing_path === 'string' && boardItem.queueEntry.briefing_path.trim()
      ? boardItem.queueEntry.briefing_path.trim()
      : null;
  const latestExecutionArtifacts = Array.isArray(boardItem.queueEntry?.latest_result_artifacts)
    ? boardItem.queueEntry?.latest_result_artifacts.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  const linkedConversationPaths = Array.from(
    new Set(
      linkedStandups
        .map((entry) => (typeof entry.conversation_path === 'string' && entry.conversation_path.trim() ? entry.conversation_path.trim() : null))
        .filter((value): value is string => Boolean(value)),
    ),
  );
  const linkedSourcePaths = Array.from(
    new Set(
      linkedStandups.flatMap((entry) => {
        const itemPayload = entry.payload ?? {};
        return Array.isArray(itemPayload.source_paths)
          ? itemPayload.source_paths.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
          : [];
      }),
    ),
  );
  const historyItems = buildPmCardHistoryItems(card, boardItem, linkedStandups);
  const heldAtPmLayer = isHeldPmLayerStatus(card.status, boardItem.lane, boardItem.executionState);
  const likelyStaleBoardItem = isLikelyStaleBoardItem(boardItem);
  const pmStatusLabel = displayPmStatusLabel(card.status, boardItem.lane, boardItem.executionState);
  const executionStatusLabel = boardItem.executionState ? displayExecutionStateLabel(boardItem.executionState) : null;
  const validationPrimaryText =
    (hostActionPayload?.summary ? summarize(hostActionPayload.summary, 320) : null) ??
    (ownerReviewPayload?.first_pass_draft ? summarize(ownerReviewPayload.first_pass_draft, 320) : null) ??
    latestExecutionSummary ??
    boardItem.queueEntry?.latest_result_summary ??
    boardItem.reason ??
    (linkedStandups[0] ? summarize(standupSummary(linkedStandups[0]), 220) : 'The system has not attached a concise result summary to this card yet.');
  const validationDecisionText = isHostActionCard
    ? 'Decide whether the external host step is complete, should be handed back into system work, or needs to stay blocked.'
    : isPendingOwnerReview
      ? 'Decide whether this draft is ready to move forward, needs revision, or should be parked.'
      : boardItem.lane === 'review'
        ? 'Decide whether the returned result is good enough to accept, continue, or reroute.'
        : boardItem.lane === 'failed'
          ? 'Decide whether this blocked lane should be rerouted, clarified, or kept blocked.'
          : 'Confirm whether this card should move, stay parked, or be treated as already handled.';
  const effectiveResolutionMode = resolutionMode ?? pmReviewPolicy?.recommended_resolution_mode ?? null;
  const effectiveNextCardTitle = nextCardTitle.trim() || pmReviewPolicy?.suggested_next_title || '';
  const acceptanceNeedsResolutionChoice = !isHostActionCard && !isPendingOwnerReview && boardItem.lane === 'review' && effectiveResolutionMode === null;
  const acceptanceNeedsNextCardTitle =
    !isHostActionCard &&
    !isPendingOwnerReview &&
    boardItem.lane === 'review' &&
    effectiveResolutionMode === 'close_and_spawn_next' &&
    !effectiveNextCardTitle;
  const validationOutcomeText = isHostActionCard
    ? hostActionFollowupPayload?.summary
      ? `If you mark this complete, PM will close this host-action card and create the next host step: "${hostActionFollowupPayload.summary}". If the step cannot happen yet, you can send it back into system work or block it.`
      : 'If you mark this complete, PM will close this host-action card and remove it from active work. If the step cannot happen yet, you can send it back into system work or block it.'
    : isPendingOwnerReview
      ? 'If you approve this draft, PM writes the decision back and queues Jean-Claude for follow-through automatically.'
      : boardItem.lane === 'review'
        ? acceptanceNeedsResolutionChoice
          ? 'If you want to accept this, PM still needs one explicit branch from you: choose `Close only` to end this lane, or `Close and spawn next` to keep the initiative moving.'
          : acceptanceNeedsNextCardTitle
            ? 'If you want to accept this and continue the initiative, PM is ready to create the next card but still needs you to name that next lane.'
          : effectiveResolutionMode === 'close_and_spawn_next' && effectiveNextCardTitle
            ? `If you accept this, PM will close this card and spawn "${effectiveNextCardTitle}".`
            : effectiveResolutionMode === 'close_only'
              ? 'If you accept this, PM will close this card and remove it from active work.'
              : 'Before you accept this, PM still needs to know whether to close the lane or create the next card.'
        : boardItem.lane === 'failed'
          ? 'If you mark this blocked, the system will keep it visible until a clearer reroute exists.'
          : 'This card is not currently in the review decision path.';
  const validationChecklist = [
    isHostActionCard
      ? {
          label: 'Host step attached',
          ready: Boolean(hostActionPayload?.summary || hostActionSteps.length > 0),
          detail: hostActionSteps.length > 0 ? 'The card includes explicit host steps.' : 'The host step summary is missing from this card.',
        }
      : isPendingOwnerReview
      ? {
          label: 'Draft attached',
          ready: Boolean(ownerReviewPayload?.first_pass_draft || ownerReviewPayload?.draft_path),
          detail: ownerReviewPayload?.draft_path ? 'Draft text or file is attached to the card.' : 'No draft text or draft file is attached yet.',
        }
      : {
          label: 'Result summary attached',
          ready: Boolean(latestExecutionSummary || boardItem.queueEntry?.latest_result_summary),
          detail: latestExecutionSummary || boardItem.queueEntry?.latest_result_summary ? 'A returned result summary is attached.' : 'There is no concise result summary attached yet.',
        },
    isHostActionCard
      ? {
          label: 'Source result linked',
          ready: Boolean(hostActionPayload?.source_card_title || hostActionPayload?.source_result_summary),
          detail:
            hostActionPayload?.source_card_title || hostActionPayload?.source_result_summary
              ? 'The host step is linked back to the internal result that created it.'
              : 'This host-action card is missing the source result context.',
        }
      : {
          label: 'Proof attached',
          ready: Boolean(ownerReviewProofAnchors.length > 0 || latestExecutionArtifacts.length > 0 || executionPacketPath || sopArtifactPath || briefingArtifactPath),
          detail:
            ownerReviewProofAnchors.length > 0
              ? `${ownerReviewProofAnchors.length} proof anchor${ownerReviewProofAnchors.length === 1 ? '' : 's'} attached.`
              : latestExecutionArtifacts.length > 0 || executionPacketPath || sopArtifactPath || briefingArtifactPath
                ? 'Execution artifacts are attached to this card.'
                : 'No direct proof or result artifacts are attached yet.',
        },
    {
      label: isHostActionCard ? 'Expected evidence is visible' : 'Source context linked',
      ready: isHostActionCard ? true : Boolean(linkedStandups.length > 0 || linkedSourcePaths.length > 0 || recommendationPath),
      detail: isHostActionCard
        ? hostActionProofRequired.length > 0
          ? `The card spells out ${hostActionProofRequired.length} evidence expectation${hostActionProofRequired.length === 1 ? '' : 's'} for audit context.`
          : 'No specific evidence is listed. A simple yes or no is enough.'
        : linkedStandups.length > 0 || linkedSourcePaths.length > 0 || recommendationPath
          ? 'Standup or source context is linked for traceability.'
          : 'No standup or supporting source context is linked yet.',
    },
    isHostActionCard
      ? {
          label: 'What completion means is clear',
          ready: Boolean(hostActionPayload?.summary || hostActionSteps.length > 0),
          detail: 'The remaining step is explicit enough to complete or return with a note.',
        }
      : isPendingOwnerReview
      ? {
          label: 'Recommendation present',
          ready: Boolean(ownerReviewPayload?.packet_recommendation || ownerReviewPayload?.why_now || ownerReviewPayload?.core_angle),
          detail:
            ownerReviewPayload?.packet_recommendation || ownerReviewPayload?.why_now || ownerReviewPayload?.core_angle
              ? 'The draft includes recommendation context or framing.'
              : 'There is no recommendation or framing note attached to this draft yet.',
        }
      : acceptanceNeedsNextCardTitle
        ? {
            label: 'Next card named',
            ready: false,
            detail: 'You already chose to continue the loop, but PM still needs a title for the next card it should create.',
          }
        : {
            label: 'Accept path chosen',
            ready: Boolean(boardItem.lane !== 'review' || effectiveResolutionMode !== null),
            detail:
              boardItem.lane !== 'review'
                ? 'This card is not waiting on a review resolution.'
                : effectiveResolutionMode === 'close_only'
                  ? 'If you accept this, PM will simply close the current lane.'
                  : effectiveResolutionMode === 'close_and_spawn_next'
                    ? 'If you accept this, PM will close this lane and continue the initiative into a new card.'
                    : 'You still need to choose whether accepting this should end the lane or spawn the next card.',
          },
  ];
  const validationMissingItems = validationChecklist.filter((item) => !item.ready);
  const validationTone = validationMissingItems.length === 0 ? '#22c55e' : validationChecklist.some((item) => item.ready) ? '#f59e0b' : '#f87171';
  const validationStateLabel = validationMissingItems.length === 0 ? 'Enough to review' : validationChecklist.some((item) => item.ready) ? 'Thin evidence' : 'Not enough proof yet';
  const validationQuickLinks = dedupeStrings(
    [
      ownerReviewPayload?.draft_path ? String(ownerReviewPayload.draft_path) : '',
      ownerReviewPayload?.owner_packet_path ? String(ownerReviewPayload.owner_packet_path) : '',
      recommendationPath ?? '',
      executionPacketPath ?? '',
      sopArtifactPath ?? '',
      briefingArtifactPath ?? '',
      ...latestExecutionArtifacts,
      ...linkedSourcePaths,
      ...linkedConversationPaths,
    ].filter((value): value is string => Boolean(value && value.trim())),
  ).slice(0, 6);
  const storyboardWhyText = likelyStaleBoardItem
    ? 'The system pulled this card back up because it looked stale. Before you judge the work itself, first decide whether this is still a live issue or just residue from something you already handled elsewhere.'
    : isHostActionCard
      ? 'This card surfaced because the system finished the internal PM lane and detected one remaining step that has to happen outside the runtime.'
      : isPendingOwnerReview
      ? 'This card surfaced because the system hit an explicit owner gate. A draft exists, but the workflow is not allowed to move it forward until you make the call.'
      : boardItem.lane === 'review'
        ? 'This card surfaced because execution returned something and PM now needs a closure judgment. The question is not “what is PM,” it is whether this returned result should be accepted, continued, or sent back.'
        : boardItem.lane === 'failed'
          ? 'This card surfaced because the normal loop broke. Something blocked or failed, and PM is waiting for a clearer human decision before it moves again.'
          : boardItem.lane === 'ready'
            ? 'This card is here because the system believes the work is framed well enough to start. It has not started execution yet.'
            : 'This card is here because PM is still tracking this work as an active lane.';
  const storyboardProofText =
    isHostActionCard
      ? (() => {
          const proofBits = [
            hostActionPayload?.source_card_title ? `This step was spawned from "${hostActionPayload.source_card_title}"` : null,
            hostActionPayload?.source_result_summary ? `The source result says: ${hostActionPayload.source_result_summary}` : null,
            hostActionProofRequired.length > 0
              ? `${hostActionProofRequired.length} expected evidence item${hostActionProofRequired.length === 1 ? '' : 's'} are attached for context`
              : null,
          ].filter((item): item is string => Boolean(item));
          return proofBits.length > 0
            ? proofBits.join('. ') + '.'
            : 'The card tells you the remaining host step, but it does not carry much supporting context yet.';
        })()
      :
    validationQuickLinks.length > 0 || ownerReviewProofAnchors.length > 0
      ? [
          validationQuickLinks.length > 0
            ? `Openable proof is attached in ${validationQuickLinks.length} linked file${validationQuickLinks.length === 1 ? '' : 's'}`
            : null,
          ownerReviewProofAnchors.length > 0
            ? `${ownerReviewProofAnchors.length} proof anchor${ownerReviewProofAnchors.length === 1 ? '' : 's'} are quoted on the card`
            : null,
          linkedStandups.length > 0
            ? `${linkedStandups.length} linked standup record${linkedStandups.length === 1 ? '' : 's'} give source context`
            : null,
        ]
          .filter((item): item is string => Boolean(item))
          .join('. ') + '.'
      : 'The card does not carry much direct proof yet. If you are unsure, that is a signal to revise or return it rather than guess.';
  const storyboardMissingText =
    isHostActionCard
      ? 'Nothing critical is missing from the card. The remaining question is simply whether the host step is done yet.'
      : acceptanceNeedsResolutionChoice
      ? 'The work itself may be reviewable, but PM does not yet know what "accept" should mean. You still need to choose one of two branches: end this lane now, or close it and create the next card.'
      : acceptanceNeedsNextCardTitle
        ? 'You already chose to continue the loop, but PM still needs you to name the next card it should create.'
        : validationMissingItems.length > 0
          ? `What still feels thin: ${validationMissingItems.map((item) => item.label.toLowerCase()).join(', ')}.`
          : 'Nothing obvious is missing for a first-pass judgment. You may still want to inspect the proof, but the card is not obviously under-explained.';
  const storyboardDecisionDetail =
    isHostActionCard
      ? 'You are deciding whether the host step has been completed cleanly enough to close this card, or whether it needs to go back into system work or stay blocked.'
      : acceptanceNeedsResolutionChoice
      ? 'You are deciding two things: first, whether the returned result is good enough; second, if it is good enough, whether this lane should end here or continue into a new PM card.'
      : acceptanceNeedsNextCardTitle
        ? 'You are deciding whether the returned result is good enough and, if it is, what the follow-up card should be called.'
        : boardItem.lane === 'review' && effectiveResolutionMode === 'close_and_spawn_next' && effectiveNextCardTitle
          ? `${validationDecisionText} The current default is to accept this and continue into "${effectiveNextCardTitle}".`
          : validationDecisionText;
  const storyboardFallbackText = isHostActionCard
    ? 'If the host step cannot happen yet, return it to Jean-Claude or mark it blocked instead of closing it optimistically.'
    : isPendingOwnerReview
    ? 'If the draft is not ready, use revision or park instead of trying to interpret around missing context.'
    : acceptanceNeedsResolutionChoice
      ? 'If you are not ready to choose between ending the lane and continuing it, return it to Jean-Claude or mark it blocked instead of accepting it ambiguously.'
      : acceptanceNeedsNextCardTitle
        ? 'If you are not ready to name the next lane, return it to Jean-Claude or mark it blocked instead of creating a vague follow-up.'
    : boardItem.lane === 'review'
      ? 'If this still feels thin after the storyboard and proof, return it to Jean-Claude or mark it blocked rather than forcing a close.'
      : 'If the plot still feels incomplete, do not resolve it just to clear the board.';
  const storyboardItems = [
    {
      title: '1. Why you are seeing this',
      detail: storyboardWhyText,
      tone: '#38bdf8',
    },
    {
      title: '2. What changed',
      detail: validationPrimaryText,
      tone: '#f8fafc',
    },
    {
      title: '3. Why the system thinks it is real',
      detail: storyboardProofText,
      tone: '#a7f3d0',
    },
    {
      title: '4. What is still thin or missing',
      detail: storyboardMissingText,
      tone: validationMissingItems.length > 0 ? '#fecaca' : '#cbd5f5',
    },
    {
      title: '5. What you are actually deciding',
      detail: storyboardDecisionDetail,
      tone: '#fef3c7',
    },
    {
      title: '6. What happens next',
      detail: `${validationOutcomeText} ${storyboardFallbackText}`,
      tone: '#cbd5f5',
    },
  ];
  const rawRecord = JSON.stringify(
    {
      card,
      queue_entry: boardItem.queueEntry ?? null,
      linked_standups: linkedStandups.map((entry) => ({
        id: entry.id,
        owner: entry.owner,
        workspace_key: entry.workspace_key,
        status: entry.status,
        source: entry.source,
        conversation_path: entry.conversation_path,
        created_at: entry.created_at,
        payload: entry.payload ?? {},
      })),
    },
    null,
    2,
  );
  const codexPacketMode = useMemo<'clarify_only' | 'execute_repo_work'>(() => {
    if (isPendingOwnerReview || isHostActionCard) {
      return 'clarify_only';
    }
    if (boardItem.lane === 'failed' || boardItem.lane === 'queued' || boardItem.lane === 'running' || boardItem.lane === 'ready') {
      return 'execute_repo_work';
    }
    if (boardItem.lane === 'review' && pmReviewPolicy?.attention_class !== 'needs_owner' && pmReviewPolicy?.attention_class !== 'needs_host') {
      return 'execute_repo_work';
    }
    return 'clarify_only';
  }, [boardItem.lane, isHostActionCard, isPendingOwnerReview, pmReviewPolicy?.attention_class]);
  const codexCardKind = useMemo(() => {
    if (isPendingOwnerReview) {
      return 'owner_decision';
    }
    if (isHostActionCard) {
      return 'host_confirmation';
    }
    if (boardItem.lane === 'failed') {
      return 'execution_retry';
    }
    if (likelyStaleBoardItem) {
      return 'stale_or_already_handled';
    }
    if (boardItem.lane === 'review') {
      return 'execution_review';
    }
    return 'execution_lane';
  }, [boardItem.lane, isHostActionCard, isPendingOwnerReview, likelyStaleBoardItem]);
  const codexDefaultAction = useMemo(() => {
    if (isPendingOwnerReview) {
      const suggested = ownerReviewAssessment?.suggested_decision;
      return typeof suggested === 'string' && suggested.trim() ? suggested.trim() : 'make_owner_decision';
    }
    if (isHostActionCard) {
      return 'confirm_host_step_if_done_otherwise_block_or_return';
    }
    if (boardItem.lane === 'failed') {
      return 'return_to_jean_claude_with_concrete_result_or_blocker';
    }
    if (likelyStaleBoardItem) {
      return 'close_if_already_handled_otherwise_clarify_next_step';
    }
    if (boardItem.lane === 'review') {
      return pmReviewPolicy?.recommended_resolution_mode === 'close_and_spawn_next' ? 'accept_and_spawn_next' : 'accept_or_return';
    }
    return 'follow_card_guidance';
  }, [boardItem.lane, isHostActionCard, isPendingOwnerReview, likelyStaleBoardItem, ownerReviewAssessment?.suggested_decision, pmReviewPolicy?.recommended_resolution_mode]);
  const codexWorkspaceRoot = useMemo(() => workspaceRootForKey(boardItem.workspaceKey), [boardItem.workspaceKey]);
  const ownerReviewResolvedDraftPath = useMemo(
    () => (ownerReviewPayload?.draft_path ? resolveCodexArtifactPath(String(ownerReviewPayload.draft_path), boardItem.workspaceKey) : null),
    [boardItem.workspaceKey, ownerReviewPayload?.draft_path],
  );
  const ownerReviewResolvedPacketPath = useMemo(
    () => (ownerReviewPayload?.owner_packet_path ? resolveCodexArtifactPath(String(ownerReviewPayload.owner_packet_path), boardItem.workspaceKey) : null),
    [boardItem.workspaceKey, ownerReviewPayload?.owner_packet_path],
  );
  const ownerReviewResolvedProofAnchors = useMemo(
    () =>
      ownerReviewProofAnchors.map((anchor) => {
        const resolved = resolveCodexArtifactPath(anchor, boardItem.workspaceKey);
        return resolved && resolved !== anchor ? { raw: anchor, resolved } : { raw: anchor, resolved: null };
      }),
    [boardItem.workspaceKey, ownerReviewProofAnchors],
  );
  const codexPacket = useMemo(() => {
    const lines: string[] = [
      `You are working from a PM card in ${REPO_ROOT}.`,
      '',
      `Mode: ${codexPacketMode}`,
      `Card kind: ${codexCardKind}`,
      `Default action: ${codexDefaultAction}`,
      `Repo root: ${REPO_ROOT}`,
      `Workspace root: ${codexWorkspaceRoot}`,
      '',
      'Guardrails:',
      '- Treat the PM card as the source of truth.',
      '- Do not reinterpret the task beyond what is necessary to complete it.',
      '- Do not invent facts, metrics, proof, or external actions.',
      '- Do not make owner decisions unless the card explicitly asks for owner judgment.',
      codexPacketMode === 'execute_repo_work'
        ? '- Complete repo-side work if it can be completed safely from this workspace.'
        : '- Clarify the task first. Do not execute repo changes unless the card clearly supports them.',
      '- If anything still requires Neo, state exactly what it is.',
      '- If the card is blocked, not due yet, or depends on an external UI, say so directly.',
      '- Do not mutate PM/backend state unless the card explicitly requires it.',
      '',
      'Return:',
      '1. What this card is asking',
      '2. What I can do now',
      '3. What I did',
      '4. What still requires Neo',
      '5. Files changed',
      '',
      'PM card snapshot:',
      `- Title: ${displayCardTitle}`,
      `- Workspace: ${meetingLabelForWorkspace(boardItem.workspaceKey)} (${boardItem.workspaceKey})`,
      `- Lane: ${boardColumns.find((column) => column.key === boardItem.lane)?.label ?? boardItem.lane}`,
      `- PM status: ${card.status}`,
      `- Execution state: ${executionStatusLabel ?? 'not in execution yet'}`,
      `- Source: ${rawSource}`,
      `- Link type: ${linkType}`,
      linkId ? `- Link id: ${linkId}` : '',
      card.due_at ? `- Due at: ${card.due_at}` : '',
      pmReviewPolicy?.attention_class ? `- Attention class: ${pmReviewPolicy.attention_class}` : '',
      pmReviewPolicy?.attention_reason ? `- Attention reason: ${pmReviewPolicy.attention_reason}` : '',
      `- Why this card exists: ${boardItem.reason ?? guidance.summary}`,
      `- Your role: ${guidance.userRole}`,
      `- Next best action: ${guidance.nextAction}`,
      `- Codex can help now: ${codexPacketMode === 'execute_repo_work' ? 'yes, repo-side work' : 'yes, clarification only'}`,
      '',
      'Card explanation already on the PM surface:',
      `- Storyboard summary: ${storyboardWhyText}`,
      `- Decision required: ${storyboardDecisionDetail}`,
      `- Fallback if unclear: ${storyboardFallbackText}`,
    ];

    if (isPendingOwnerReview) {
      lines.push(
        '',
        'Owner review context:',
        ownerReviewPayload?.queue_id ? `- Queue id: ${ownerReviewPayload.queue_id}` : '',
        ownerReviewPayload?.summary ? `- Summary: ${ownerReviewPayload.summary}` : '',
        ownerReviewPayload?.core_angle ? `- Core angle: ${ownerReviewPayload.core_angle}` : '',
        ownerReviewPayload?.why_now ? `- Why now: ${ownerReviewPayload.why_now}` : '',
        ownerReviewPayload?.packet_recommendation ? `- Packet recommendation: ${ownerReviewPayload.packet_recommendation}` : '',
        ownerReviewPayload?.draft_path
          ? `- Draft path: ${ownerReviewPayload.draft_path}${ownerReviewResolvedDraftPath && ownerReviewResolvedDraftPath !== ownerReviewPayload.draft_path ? ` (resolved: ${ownerReviewResolvedDraftPath})` : ''}`
          : '',
        ownerReviewPayload?.owner_packet_path
          ? `- Owner packet path: ${ownerReviewPayload.owner_packet_path}${ownerReviewResolvedPacketPath && ownerReviewResolvedPacketPath !== ownerReviewPayload.owner_packet_path ? ` (resolved: ${ownerReviewResolvedPacketPath})` : ''}`
          : '',
        ownerReviewAssessment?.summary ? `- System read: ${ownerReviewAssessment.summary}` : '',
        ownerReviewAssessment?.confidence ? `- System confidence: ${ownerReviewAssessment.confidence}` : '',
      );
      if (ownerReviewAssessment?.reasons?.length) {
        lines.push('- System reasons:');
        ownerReviewAssessment.reasons.forEach((reason) => lines.push(`  - ${reason}`));
      }
      if (ownerReviewAssessment?.missing_items?.length) {
        lines.push('- Missing items:');
        ownerReviewAssessment.missing_items.forEach((item) => lines.push(`  - ${item}`));
      }
      if (ownerReviewResolvedProofAnchors.length > 0) {
        lines.push('- Proof anchors:');
        ownerReviewResolvedProofAnchors.forEach(({ raw, resolved }) =>
          lines.push(`  - ${resolved && resolved !== raw ? `${raw} (resolved: ${resolved})` : raw}`),
        );
      }
      if (ownerDecisionScaffold) {
        lines.push(
          '',
          'Owner decision scaffold:',
          ownerDecisionScaffold.decision_question ? `- Decision question: ${ownerDecisionScaffold.decision_question}` : '',
          ownerDecisionScaffold.recommended_decision ? `- Recommended decision: ${ownerDecisionScaffold.recommended_decision}` : '',
          ownerDecisionScaffold.neo_answer_contract ? `- Neo answer contract: ${ownerDecisionScaffold.neo_answer_contract}` : '',
        );
        if (ownerDecisionScaffold.must_verify?.length) {
          lines.push('- Must verify first:');
          ownerDecisionScaffold.must_verify.forEach((entry) => lines.push(`  - ${entry}`));
        }
        if (ownerDecisionScaffold.approve_when?.length) {
          lines.push('- Approve when:');
          ownerDecisionScaffold.approve_when.forEach((entry) => lines.push(`  - ${entry}`));
        }
        if (ownerDecisionScaffold.revise_when?.length) {
          lines.push('- Revise when:');
          ownerDecisionScaffold.revise_when.forEach((entry) => lines.push(`  - ${entry}`));
        }
        if (ownerDecisionScaffold.park_when?.length) {
          lines.push('- Park when:');
          ownerDecisionScaffold.park_when.forEach((entry) => lines.push(`  - ${entry}`));
        }
        if (ownerDecisionScaffold.optional_strengtheners?.length) {
          lines.push('- Optional strengtheners:');
          ownerDecisionScaffold.optional_strengtheners.forEach((entry) => lines.push(`  - ${entry}`));
        }
      }
    }

    if (isHostActionCard) {
      lines.push(
        '',
        'Host action context:',
        hostActionPayload?.summary ? `- Remaining step: ${hostActionPayload.summary}` : '',
        hostActionPayload?.source_card_title ? `- Source card: ${hostActionPayload.source_card_title}` : '',
        hostActionPayload?.source_result_summary ? `- Source result: ${hostActionPayload.source_result_summary}` : '',
        hostActionPayload?.detected_from ? `- Detected from: ${hostActionPayload.detected_from}` : '',
      );
      if (hostActionSteps.length > 0) {
        lines.push('- Host steps:');
        hostActionSteps.forEach((step) => lines.push(`  - ${step}`));
      }
      if (hostActionProofRequired.length > 0) {
        lines.push('- Expected evidence:');
        hostActionProofRequired.forEach((item) => lines.push(`  - ${item}`));
      }
      if (hostActionFollowupPayload?.summary) {
        lines.push(`- Delayed follow-up after completion: ${hostActionFollowupPayload.summary}`);
      }
    }

    if (latestExecutionSummary || latestExecutionArtifacts.length > 0 || executionPacketPath || sopArtifactPath || briefingArtifactPath) {
      lines.push(
        '',
        'Execution context:',
        latestExecutionSummary ? `- Latest execution summary: ${latestExecutionSummary}` : '- Latest execution summary: none attached',
        executionPacketPath ? `- Execution packet: ${executionPacketPath}` : '',
        sopArtifactPath ? `- SOP: ${sopArtifactPath}` : '',
        briefingArtifactPath ? `- Briefing: ${briefingArtifactPath}` : '',
      );
      if (latestExecutionArtifacts.length > 0) {
        lines.push('- Latest execution artifacts:');
        latestExecutionArtifacts.forEach((artifact) => lines.push(`  - ${artifact}`));
      }
    }

    if (linkedStandups.length > 0 || linkedConversationPaths.length > 0 || linkedSourcePaths.length > 0) {
      lines.push('', 'Linked context:');
      if (linkedStandups.length > 0) {
        lines.push(`- Linked standups: ${linkedStandups.length}`);
      }
      if (linkedConversationPaths.length > 0) {
        lines.push('- Conversation paths:');
        linkedConversationPaths.forEach((path) => lines.push(`  - ${path}`));
      }
      if (linkedSourcePaths.length > 0) {
        lines.push('- Source paths:');
        linkedSourcePaths.forEach((path) => lines.push(`  - ${path}`));
      }
    }

    lines.push('', 'Raw PM payload:', '```json', rawRecord, '```');
    const cleanedLines = lines.reduce<string[]>((acc, line) => {
      if (line !== '') {
        acc.push(line);
        return acc;
      }
      if (acc[acc.length - 1] !== '') {
        acc.push('');
      }
      return acc;
    }, []);
    return cleanedLines.join('\n');
  }, [
    boardColumns,
    boardItem.lane,
    boardItem.reason,
    boardItem.workspaceKey,
    briefingArtifactPath,
    card.due_at,
    card.status,
    codexCardKind,
    codexDefaultAction,
    codexPacketMode,
    displayCardTitle,
    executionPacketPath,
    executionStatusLabel,
    guidance.nextAction,
    guidance.summary,
    guidance.userRole,
    hostActionFollowupPayload?.summary,
    hostActionPayload?.detected_from,
    hostActionPayload?.source_card_title,
    hostActionPayload?.source_result_summary,
    hostActionPayload?.summary,
    hostActionProofRequired,
    hostActionSteps,
    isHostActionCard,
    isPendingOwnerReview,
    latestExecutionArtifacts,
    latestExecutionSummary,
    linkedConversationPaths,
    linkedSourcePaths,
    linkedStandups.length,
    linkId,
    linkType,
    meetingLabelForWorkspace,
    ownerReviewAssessment?.confidence,
    ownerDecisionScaffold,
    ownerReviewAssessment?.missing_items,
    ownerReviewAssessment?.reasons,
    ownerReviewAssessment?.summary,
    ownerReviewPayload?.core_angle,
    ownerReviewPayload?.draft_path,
    ownerReviewPayload?.owner_packet_path,
    ownerReviewPayload?.packet_recommendation,
    ownerReviewPayload?.queue_id,
    ownerReviewPayload?.summary,
    ownerReviewPayload?.why_now,
    ownerReviewResolvedDraftPath,
    ownerReviewResolvedPacketPath,
    ownerReviewResolvedProofAnchors,
    pmReviewPolicy?.attention_class,
    pmReviewPolicy?.attention_reason,
    rawRecord,
    rawSource,
    sopArtifactPath,
    storyboardDecisionDetail,
    storyboardFallbackText,
    storyboardWhyText,
    codexWorkspaceRoot,
  ]);
  const pmEventChainItems = [
    {
      label: 'Signal',
      value: createdFromPrepId ? 'Prep packet' : rawSource,
      detail: createdFromPrepId ? summarize(createdFromPrepId, 42) : summarize(rawSource, 72),
      tone: '#38bdf8',
    },
    {
      label: 'Standup',
      value: linkedStandups.length > 0 ? `${linkedStandups.length} linked` : 'No linked meeting',
      detail: linkedStandups[0] ? summarize(standupLabel(linkedStandups[0]), 54) : 'This card was not linked back to a standup record.',
      tone: '#a78bfa',
    },
    {
      label: 'PM',
      value: pmStatusLabel,
      detail: boardColumns.find((column) => column.key === boardItem.lane)?.label ?? boardItem.lane,
      tone: '#f59e0b',
    },
    {
      label: 'Execution',
      value: executionStatusLabel ?? 'Not in execution',
      detail: `${displayManagerAgent(boardItem.workspaceKey, boardItem.managerAgent)} -> ${displayTargetAgent(boardItem.workspaceKey, boardItem.targetAgent)}`,
      tone: '#22c55e',
    },
    {
      label: 'Result',
      value: latestExecutionResult ? humanizeStatusLabel(String(latestExecutionResult.status || 'unknown')) : 'No result yet',
      detail: latestExecutionSummary ? summarize(latestExecutionSummary, 84) : 'Execution has not written back a result.',
      tone: '#818cf8',
    },
  ];

  useEffect(() => {
    setOwnerReviewNotes(ownerReviewPayload?.current_notes ?? '');
    setOwnerReviewNotesDirty(false);
  }, [card.id]);

  useEffect(() => {
    if (ownerReviewNotesDirty) {
      return;
    }
    setOwnerReviewNotes(ownerReviewPayload?.current_notes ?? '');
  }, [ownerReviewNotesDirty, ownerReviewPayload?.current_notes]);

  const reviewNeedsEvidenceFirst = boardItem.lane === 'review';
  const tabSequence = reviewNeedsEvidenceFirst
    ? ([
        ['evidence', 'Evidence'],
        ['overview', 'Overview'],
        ['outcomes', 'Outcomes'],
        ['raw', 'Raw'],
      ] as const)
    : ([
        ['overview', 'Overview'],
        ['evidence', 'Evidence'],
        ['outcomes', 'Outcomes'],
        ['raw', 'Raw'],
      ] as const);
  const evidenceFirstLinks = [
    ...(ownerReviewPayload?.draft_path ? [String(ownerReviewPayload.draft_path)] : []),
    ...(ownerReviewPayload?.owner_packet_path ? [String(ownerReviewPayload.owner_packet_path)] : []),
    ...validationQuickLinks,
  ].filter((value, index, array) => value && array.indexOf(value) === index);
  const evidenceFirstPreview = ownerReviewPayload?.first_pass_draft
    ? ownerReviewPayload.first_pass_draft
    : latestExecutionSummary || null;

  useEffect(() => {
    setActiveTab(reviewNeedsEvidenceFirst ? 'evidence' : 'overview');
  }, [card.id, reviewNeedsEvidenceFirst]);

  useEffect(() => {
    setResolutionMode(pmReviewPolicy?.recommended_resolution_mode ?? null);
    setResolutionNote('');
    setResolutionInputsDirty(false);
    setNextCardTitle(pmReviewPolicy?.suggested_next_title ?? '');
    setNextCardReason(pmReviewPolicy?.suggested_next_reason ?? '');
  }, [card.id]);

  useEffect(() => {
    if (resolutionInputsDirty) {
      return;
    }
    setResolutionMode(pmReviewPolicy?.recommended_resolution_mode ?? null);
    setNextCardTitle(pmReviewPolicy?.suggested_next_title ?? '');
    setNextCardReason(pmReviewPolicy?.suggested_next_reason ?? '');
  }, [pmReviewPolicy?.recommended_resolution_mode, pmReviewPolicy?.suggested_next_reason, pmReviewPolicy?.suggested_next_title, resolutionInputsDirty]);

  const handleCopyForCodex = useCallback(async () => {
    try {
      setActionError(null);
      setActionFeedback(null);
      if (typeof navigator === 'undefined' || !navigator.clipboard) {
        throw new Error('Clipboard access is not available in this browser session.');
      }
      await navigator.clipboard.writeText(codexPacket);
      setActionFeedback(`Copied Codex work packet for ${displayCardTitle}.`);
    } catch (error) {
      setActionError(`Copy for Codex: ${toErrorMessage(error)}`);
    }
  }, [codexPacket, displayCardTitle]);

  const handleCardAction = async (action: 'dispatch' | 'approve' | 'return' | 'blocked') => {
    try {
      setActioningCardId(card.id);
      setActionError(null);
      setActionFeedback(null);
      if (action === 'dispatch') {
        await onDispatch(card.id, boardItem.queueEntry?.target_agent || displayTargetAgent(boardItem.workspaceKey, boardItem.targetAgent));
        setActionFeedback(`Opened SOP for ${displayCardTitle}.`);
        return;
      }
      if (action === 'approve') {
        if (!resolutionMode) {
          throw new Error('Choose what should happen next before resolving this card.');
        }
        if (resolutionMode === 'close_and_spawn_next' && !nextCardTitle.trim()) {
          throw new Error('Add a title for the next PM card before resolving this card.');
        }
        const result = await onActOnPmCard(card.id, action, {
          reason: resolutionNote.trim() || undefined,
          resolutionMode,
          nextTitle: nextCardTitle.trim() || undefined,
          nextReason: nextCardReason.trim() || undefined,
        });
        setResolutionInputsDirty(false);
        setActionFeedback(
          result.successor_card
            ? `Resolved ${displayCardTitle} and spawned "${result.successor_card.title}".`
            : `Resolved ${displayCardTitle} and closed this lane.`,
        );
        return;
      }
      await onActOnPmCard(card.id, action, {
        reason: resolutionNote.trim() || undefined,
      });
      setResolutionInputsDirty(false);
      setActionFeedback(
        action === 'return'
          ? `Returned ${displayCardTitle} to Jean-Claude.`
          : `Marked ${displayCardTitle} as blocked and rerouted it to Jean-Claude.`,
      );
    } catch (error) {
      setActionError(toErrorMessage(error));
    } finally {
      setActioningCardId(null);
    }
  };

  const handleOwnerReviewAction = async (decision: OwnerReviewDecision) => {
    try {
      setActioningCardId(card.id);
      setActionError(null);
      setActionFeedback(null);
      const result = await onActOnOwnerReviewCard(card.id, decision, ownerReviewNotes);
      const queuedFollowupCardId = result.workflow?.card_id ?? null;
      setActionFeedback(
        result.workflow?.message ??
          (decision === 'approve'
            ? `Approved ${displayCardTitle}.`
            : decision === 'revise'
              ? `Requested revision for ${displayCardTitle}.`
              : `Parked ${displayCardTitle}.`),
      );
      setOwnerReviewNotesDirty(false);
      if (decision === 'park') {
        onSelectCard(null);
        return;
      }
      setActiveTab('overview');
      onSelectCard(queuedFollowupCardId || card.id);
    } catch (error) {
      setActionError(toErrorMessage(error));
    } finally {
      setActioningCardId(null);
    }
  };

  const handleAlreadyHandled = async () => {
    try {
      setActioningCardId(card.id);
      setActionError(null);
      setActionFeedback(null);
      await onActOnPmCard(card.id, 'approve', {
        reason: resolutionNote.trim() || 'Closed as already handled outside PM.',
        resolutionMode: 'close_only',
      });
      setResolutionInputsDirty(false);
      setActionFeedback(`Closed ${displayCardTitle} as already handled.`);
    } catch (error) {
      setActionError(toErrorMessage(error));
    } finally {
      setActioningCardId(null);
    }
  };

  const handleHostActionComplete = async () => {
    try {
      setActioningCardId(card.id);
      setActionError(null);
      setActionFeedback(null);
      await onActOnPmCard(card.id, 'approve', {
        reason: resolutionNote.trim(),
        resolutionMode: 'close_only',
      });
      setResolutionInputsDirty(false);
      setActionFeedback(`Closed ${displayCardTitle} as completed host work.`);
      onSelectCard(null);
    } catch (error) {
      setActionError(toErrorMessage(error));
    } finally {
      setActioningCardId(null);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 80,
        backgroundColor: 'rgba(2, 6, 23, 0.78)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '28px',
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: 'min(980px, 100%)',
          maxHeight: 'min(88vh, 940px)',
          overflowY: 'auto',
          borderRadius: '22px',
          border: '1px solid #1f2937',
          backgroundColor: '#0b1324',
          boxShadow: '0 24px 80px rgba(15, 23, 42, 0.55)',
          padding: '18px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'flex-start', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#94a3b8', letterSpacing: '0.16em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>PM Card Detail</p>
            <h3 style={{ color: 'white', fontSize: '28px', lineHeight: 1.2, margin: 0 }}>{boardItem.title}</h3>
            <p style={{ color: '#94a3b8', fontSize: '13px', margin: '6px 0 0' }}>
              {meetingLabelForWorkspace(boardItem.workspaceKey)} · {boardItem.updatedAt ? formatTimestamp(new Date(boardItem.updatedAt)) : '-'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={handleCopyForCodex}
              style={{
                borderRadius: '999px',
                border: '1px solid rgba(56,189,248,0.32)',
                backgroundColor: 'rgba(56,189,248,0.12)',
                color: '#dbeafe',
                padding: '8px 12px',
                cursor: 'pointer',
                fontWeight: 700,
              }}
            >
              Copy for Codex
            </button>
            <button
              type="button"
              onClick={onClose}
              style={{
                borderRadius: '999px',
                border: '1px solid #1f2937',
                backgroundColor: '#111827',
                color: '#cbd5e1',
                padding: '8px 12px',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              Close
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <span style={{ padding: '6px 12px', borderRadius: '999px', backgroundColor: `${theme.accent}22`, color: theme.accent, border: `1px solid ${theme.border}` }}>
            {meetingLabelForWorkspace(boardItem.workspaceKey)}
          </span>
          <span style={{ padding: '6px 12px', borderRadius: '999px', backgroundColor: '#111827', color: '#e2e8f0', border: '1px solid #1f2937' }}>
            Lane: {boardColumns.find((column) => column.key === boardItem.lane)?.label ?? boardItem.lane}
          </span>
          {statusBadge(pmStatusLabel)}
          {executionStatusLabel ? statusBadge(executionStatusLabel) : null}
          {linkedStandups.length > 0 ? (
            <span style={{ padding: '6px 12px', borderRadius: '999px', backgroundColor: '#111827', color: '#cbd5f5', border: '1px solid #1f2937', fontSize: '12px' }}>
              {linkedStandups.length} linked meeting{linkedStandups.length === 1 ? '' : 's'}
            </span>
          ) : null}
        </div>

        {actionError && <SectionAlert message={`PM card action: ${actionError}`} />}
        {actionFeedback && (
          <div style={{ borderRadius: '14px', border: '1px solid rgba(34,197,94,0.35)', backgroundColor: 'rgba(34,197,94,0.08)', padding: '12px 14px', color: '#bbf7d0', fontSize: '13px', marginBottom: '12px' }}>
            {actionFeedback}
          </div>
        )}
        {likelyStaleBoardItem ? (
          <section style={{ borderRadius: '14px', border: '1px solid rgba(248,113,113,0.28)', backgroundColor: 'rgba(248,113,113,0.08)', padding: '12px 14px', marginBottom: '12px' }}>
            <p style={{ color: '#fecaca', fontSize: '14px', fontWeight: 700, margin: '0 0 6px' }}>This may already be handled</p>
            <p style={{ color: '#fee2e2', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
              The system pulled this card back up because it looked stale. If you already fixed it somewhere else, you can close it here without creating more work.
            </p>
          </section>
        ) : null}

        {reviewNeedsEvidenceFirst ? (
          <section
            style={{
              borderRadius: '16px',
              border: '1px solid rgba(56,189,248,0.28)',
              backgroundColor: 'rgba(56,189,248,0.08)',
              padding: '14px',
              marginBottom: '14px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '10px' }}>
              <div>
                <p style={{ color: '#38bdf8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', margin: '0 0 4px' }}>Evidence First</p>
                <p style={{ color: '#e2e8f0', fontSize: '14px', margin: 0 }}>
                  Read the proof before the storyline. This is the concrete material the review decision should rest on.
                </p>
              </div>
              {validationStateLabel ? (
                <span style={{ borderRadius: '999px', border: '1px solid rgba(56,189,248,0.35)', backgroundColor: '#08101f', color: '#e0f2fe', padding: '6px 10px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase' }}>
                  {validationStateLabel}
                </span>
              ) : null}
            </div>
            {evidenceFirstLinks.length > 0 ? (
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: ownerReviewProofAnchors.length > 0 || evidenceFirstPreview ? '10px' : 0 }}>
                {evidenceFirstLinks.map((path) => (
                  <button
                    key={`${card.id}-evidence-first-link-${path}`}
                    type="button"
                    onClick={() => onOpenArtifactPath(path)}
                    style={{
                      borderRadius: '999px',
                      border: '1px solid #334155',
                      backgroundColor: '#0f172a',
                      color: '#f8fafc',
                      padding: '8px 10px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                    }}
                    title={path}
                  >
                    {summarizePathForDisplay(path)}
                  </button>
                ))}
              </div>
            ) : null}
            {ownerReviewProofAnchors.length > 0 ? (
              <div style={{ display: 'grid', gap: '4px', marginBottom: evidenceFirstPreview ? '10px' : 0 }}>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>Proof anchors</p>
                {ownerReviewProofAnchors.slice(0, 3).map((anchor) => (
                  <p key={`${card.id}-evidence-first-anchor-${anchor}`} style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                    {anchor}
                  </p>
                ))}
              </div>
            ) : null}
            {evidenceFirstPreview ? (
              <section style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '12px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.08em', fontSize: '12px', textTransform: 'uppercase', margin: '0 0 8px' }}>
                  Draft / evidence preview
                </p>
                <pre
                  style={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: '#e2e8f0',
                    fontSize: '12px',
                    lineHeight: 1.6,
                    margin: 0,
                    maxHeight: '220px',
                    overflowY: 'auto',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                  }}
                >
                  {evidenceFirstPreview}
                </pre>
              </section>
            ) : null}
          </section>
        ) : null}

        <section
          style={{
            borderRadius: '16px',
            border: `1px solid ${validationTone}33`,
            backgroundColor: `${validationTone}10`,
            padding: '14px',
            marginBottom: '14px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '10px' }}>
            <div>
              <p style={{ color: validationTone, letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', margin: '0 0 4px' }}>Storyboard</p>
              <p style={{ color: '#e2e8f0', fontSize: '14px', margin: 0 }}>Read this top to bottom. It answers the usual follow-up questions in order.</p>
            </div>
            <span style={{ borderRadius: '999px', border: `1px solid ${validationTone}55`, backgroundColor: `${validationTone}20`, color: '#f8fafc', padding: '6px 10px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase' }}>
              {validationStateLabel}
            </span>
          </div>
          <div style={{ display: 'grid', gap: '10px' }}>
            {storyboardItems.map((item) => (
              <section
                key={`${card.id}-storyboard-${item.title}`}
                style={{
                  borderRadius: '14px',
                  border: '1px solid #1f2937',
                  backgroundColor: '#08101f',
                  padding: '12px',
                }}
              >
                <p style={{ color: item.tone, letterSpacing: '0.06em', fontSize: '12px', fontWeight: 700, margin: '0 0 6px' }}>{item.title}</p>
                <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.6, margin: 0 }}>{item.detail}</p>
              </section>
            ))}
          </div>
          <section style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '12px', marginTop: '12px' }}>
            <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', margin: '0 0 8px' }}>Quick proof</p>
            {validationQuickLinks.length > 0 ? (
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: ownerReviewProofAnchors.length > 0 ? '10px' : 0 }}>
                {validationQuickLinks.map((path) => (
                  <button
                    key={`${card.id}-validation-link-${path}`}
                    type="button"
                    onClick={() => onOpenArtifactPath(path)}
                    style={{
                      borderRadius: '999px',
                      border: '1px solid #334155',
                      backgroundColor: '#0f172a',
                      color: '#f8fafc',
                      padding: '8px 10px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                    }}
                    title={path}
                  >
                    {summarizePathForDisplay(path)}
                  </button>
                ))}
              </div>
            ) : (
              <p style={{ color: '#64748b', fontSize: '13px', lineHeight: 1.55, margin: ownerReviewProofAnchors.length > 0 ? '0 0 10px' : 0 }}>
                No openable proof files are attached yet.
              </p>
            )}
            {ownerReviewProofAnchors.length > 0 ? (
              <div style={{ display: 'grid', gap: '4px' }}>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>Proof anchors</p>
                {ownerReviewProofAnchors.slice(0, 4).map((anchor) => (
                  <p key={`${card.id}-proof-anchor-${anchor}`} style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                    {anchor}
                  </p>
                ))}
              </div>
            ) : null}
          </section>
        </section>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
          {tabSequence.map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              style={{
                borderRadius: '999px',
                border: activeTab === key ? '1px solid rgba(251,191,36,0.45)' : '1px solid #334155',
                backgroundColor: activeTab === key ? 'rgba(251,191,36,0.12)' : '#0f172a',
                color: activeTab === key ? '#f8fafc' : '#94a3b8',
                padding: '8px 14px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <section
          style={{
            borderRadius: '16px',
            border: '1px solid rgba(251,191,36,0.18)',
            backgroundColor: '#111827',
            padding: '14px',
            marginBottom: '14px',
          }}
        >
          <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>
            Actions
          </p>
          {pmReviewPolicy?.policy_label && !isPendingOwnerReview && !isHostActionCard && (boardItem.lane === 'review' || Boolean(pmReviewPolicy.auto_resolve_eligible)) ? (
            <section style={{ borderRadius: '14px', border: '1px solid rgba(56,189,248,0.22)', backgroundColor: '#08101f', padding: '12px 14px', marginBottom: '12px' }}>
              <p style={{ color: '#38bdf8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', margin: '0 0 6px' }}>System Policy</p>
              <p style={{ color: '#dbeafe', fontSize: '13px', lineHeight: 1.55, margin: '0 0 6px' }}>{pmReviewPolicy.policy_label}</p>
              {pmReviewPolicy.attention_reason ? (
                <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{pmReviewPolicy.attention_reason}</p>
              ) : null}
            </section>
          ) : null}
          {isPendingOwnerReview && ownerReviewPayload ? (
            <div style={{ display: 'grid', gap: '12px' }}>
              <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>
                Open the draft, make the owner call here, and let PM queue the follow-up automatically.
              </p>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#94a3b8', fontSize: '12px' }}>Owner notes</span>
                <textarea
                  value={ownerReviewNotes}
                  onChange={(event) => {
                    setOwnerReviewNotes(event.target.value);
                    setOwnerReviewNotesDirty(true);
                  }}
                  placeholder="Add revision notes, scheduling notes, or why this should be parked."
                  rows={4}
                  style={{
                    width: '100%',
                    borderRadius: '12px',
                    border: '1px solid #334155',
                    backgroundColor: '#0f172a',
                    color: '#e2e8f0',
                    padding: '12px',
                    fontSize: '13px',
                    lineHeight: 1.5,
                    resize: 'vertical',
                  }}
                />
              </label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleOwnerReviewAction('approve')}
                  style={meetingActionButtonStyle('success', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Saving…' : 'Approve draft'}
                </button>
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleOwnerReviewAction('revise')}
                  style={meetingActionButtonStyle('secondary', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Saving…' : 'Request revision'}
                </button>
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleOwnerReviewAction('park')}
                  style={meetingActionButtonStyle('danger', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Saving…' : 'Park draft'}
                </button>
              </div>
            </div>
          ) : isHostActionCard && hostActionPayload ? (
            <div style={{ display: 'grid', gap: '12px' }}>
              <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>
                The system already finished the internal work. This card is only for the external host step that still needs to happen.
              </p>
              {hostActionFollowupPayload?.summary ? (
                <p style={{ color: '#93c5fd', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                  Closing this card will spawn the next delayed host step: {hostActionFollowupPayload.summary}
                </p>
              ) : null}
              {hostActionPayload.source_card_id ? (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    disabled={actioningCardId === card.id}
                    onClick={() => onSelectCard(hostActionPayload.source_card_id ?? null)}
                    style={meetingActionButtonStyle('secondary', actioningCardId === card.id)}
                  >
                    Open source PM card
                  </button>
                </div>
              ) : null}
              {hostActionProofRequired.length > 0 ? (
                <div style={{ display: 'grid', gap: '6px', borderRadius: '12px', border: '1px solid #334155', backgroundColor: '#08101f', padding: '12px' }}>
                  <p style={{ color: '#f8fafc', fontSize: '12px', fontWeight: 700, margin: 0 }}>Expected evidence</p>
                  {hostActionProofRequired.map((item, index) => (
                    <p key={`${card.id}-host-proof-${index}`} style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                      {index + 1}. {item}
                    </p>
                  ))}
                </div>
              ) : null}
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#94a3b8', fontSize: '12px' }}>Optional note</span>
                <textarea
                  value={resolutionNote}
                  onChange={(event) => {
                    setResolutionNote(event.target.value);
                    setResolutionInputsDirty(true);
                  }}
                  placeholder="Add one sentence of nuance if needed."
                  rows={2}
                  style={{
                    width: '100%',
                    borderRadius: '12px',
                    border: '1px solid #334155',
                    backgroundColor: '#0f172a',
                    color: '#e2e8f0',
                    padding: '12px',
                    fontSize: '13px',
                    lineHeight: 1.5,
                    resize: 'vertical',
                  }}
                />
              </label>
              <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                Use this card as a simple host confirmation. The evidence list is here for context, not as a form you have to fill out.
              </p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleHostActionComplete()}
                  style={meetingActionButtonStyle('success', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Saving…' : 'Yes, host step complete'}
                </button>
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleCardAction('return')}
                  style={meetingActionButtonStyle('secondary', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Returning…' : 'No, return to Jean-Claude'}
                </button>
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleCardAction('blocked')}
                  style={meetingActionButtonStyle('danger', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Routing…' : 'Mark blocked'}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '12px' }}>
              {boardItem.lane === 'review' ? (
                <div style={{ display: 'grid', gap: '12px' }}>
                  <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>
                    Resolving a review card now requires an explicit next-step choice so the loop either closes intentionally or spawns the next lane.
                  </p>
                  {pmReviewPolicy?.recommended_resolution_mode ? (
                    <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>
                      Default for this workspace: {pmReviewPolicy.recommended_resolution_mode === 'close_and_spawn_next' ? 'close and spawn the next card' : 'close only'}.
                    </p>
                  ) : null}
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {([
                      ['close_only', 'Close only'],
                      ['close_and_spawn_next', 'Close and spawn next'],
                    ] as const).map(([mode, label]) => (
                      <button
                        key={`${card.id}-resolution-${mode}`}
                        type="button"
                        onClick={() => {
                          setResolutionMode(mode);
                          setResolutionInputsDirty(true);
                        }}
                        disabled={actioningCardId === card.id}
                        style={{
                          borderRadius: '999px',
                          border: resolutionMode === mode ? '1px solid rgba(251,191,36,0.45)' : '1px solid #334155',
                          backgroundColor: resolutionMode === mode ? 'rgba(251,191,36,0.12)' : '#0f172a',
                          color: resolutionMode === mode ? '#f8fafc' : '#94a3b8',
                          padding: '8px 14px',
                          fontWeight: 700,
                          cursor: actioningCardId === card.id ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <label style={{ display: 'grid', gap: '6px' }}>
                    <span style={{ color: '#94a3b8', fontSize: '12px' }}>Resolution note</span>
                    <textarea
                      value={resolutionNote}
                      onChange={(event) => {
                        setResolutionNote(event.target.value);
                        setResolutionInputsDirty(true);
                      }}
                      placeholder="Optional note about why this result is accepted or how the loop should continue."
                      rows={3}
                      style={{
                        width: '100%',
                        borderRadius: '12px',
                        border: '1px solid #334155',
                        backgroundColor: '#0f172a',
                        color: '#e2e8f0',
                        padding: '12px',
                        fontSize: '13px',
                        lineHeight: 1.5,
                        resize: 'vertical',
                      }}
                    />
                  </label>
                  {resolutionMode === 'close_and_spawn_next' ? (
                    <div style={{ display: 'grid', gap: '10px' }}>
                      <label style={{ display: 'grid', gap: '6px' }}>
                        <span style={{ color: '#94a3b8', fontSize: '12px' }}>Next PM card title</span>
                        <input
                          value={nextCardTitle}
                          onChange={(event) => {
                            setNextCardTitle(event.target.value);
                            setResolutionInputsDirty(true);
                          }}
                          placeholder="Name the concrete next lane this result should create."
                          style={{
                            width: '100%',
                            borderRadius: '12px',
                            border: '1px solid #334155',
                            backgroundColor: '#0f172a',
                            color: '#e2e8f0',
                            padding: '12px',
                            fontSize: '13px',
                          }}
                        />
                      </label>
                      <label style={{ display: 'grid', gap: '6px' }}>
                        <span style={{ color: '#94a3b8', fontSize: '12px' }}>Why the next card exists</span>
                        <textarea
                          value={nextCardReason}
                          onChange={(event) => {
                            setNextCardReason(event.target.value);
                            setResolutionInputsDirty(true);
                          }}
                          placeholder="Optional context for the follow-on card."
                          rows={3}
                          style={{
                            width: '100%',
                            borderRadius: '12px',
                            border: '1px solid #334155',
                            backgroundColor: '#0f172a',
                            color: '#e2e8f0',
                            padding: '12px',
                            fontSize: '13px',
                            lineHeight: 1.5,
                            resize: 'vertical',
                          }}
                        />
                      </label>
                    </div>
                  ) : null}
                </div>
              ) : null}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {likelyStaleBoardItem && boardItem.lane === 'review' ? (
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleAlreadyHandled()}
                  style={meetingActionButtonStyle('secondary', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Closing…' : 'Already handled'}
                </button>
              ) : null}
              {(boardItem.lane === 'ready' || boardItem.lane === 'todo') && (
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleCardAction('dispatch')}
                  style={meetingActionButtonStyle('primary', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Opening…' : 'Open SOP'}
                </button>
              )}
              {boardItem.lane === 'review' && (
                <button
                  type="button"
                  disabled={
                    actioningCardId === card.id ||
                    !resolutionMode ||
                    (resolutionMode === 'close_and_spawn_next' && !nextCardTitle.trim())
                  }
                  onClick={() => void handleCardAction('approve')}
                  style={meetingActionButtonStyle('success', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Resolving…' : 'Resolve'}
                </button>
              )}
              {['review', 'queued', 'running', 'failed'].includes(boardItem.lane) && (
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleCardAction('return')}
                  style={meetingActionButtonStyle('secondary', actioningCardId === card.id)}
                >
                  {actioningCardId === card.id ? 'Returning…' : 'Return to Jean-Claude'}
                </button>
              )}
              {['review', 'queued', 'running', 'failed'].includes(boardItem.lane) && (
                <button
                  type="button"
                  disabled={actioningCardId === card.id}
                  onClick={() => void handleCardAction('blocked')}
                  style={meetingActionButtonStyle('danger', actioningCardId === card.id)}
                  >
                    {actioningCardId === card.id ? 'Routing…' : 'Mark blocked'}
                  </button>
              )}
              </div>
            </div>
          )}
        </section>

        {activeTab === 'overview' && (
          <div style={{ display: 'grid', gap: '14px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1.25fr 0.95fr', gap: '14px' }}>
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '16px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>What This Card Means</p>
                <p style={{ color: '#e2e8f0', fontSize: '15px', lineHeight: 1.6, margin: '0 0 14px' }}>{guidance.summary}</p>

                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Your Role</p>
                <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.6, margin: '0 0 14px' }}>{guidance.userRole}</p>

                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Next Best Action</p>
                <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.6, margin: 0 }}>{guidance.nextAction}</p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '16px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Card Metadata</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', color: '#cbd5f5', fontSize: '13px' }}>
                  <div>Source: {rawSource}</div>
                  <div>PM status: {pmStatusLabel}</div>
                  <div>Execution state: {isHostActionCard ? 'host step only' : executionStatusLabel ?? 'not in execution yet'}</div>
                  {boardItem.queueEntry?.front_door_agent ? <div>Front door: {boardItem.queueEntry.front_door_agent}</div> : null}
                  <div>Updated: {boardItem.updatedAt ? formatTimestamp(new Date(boardItem.updatedAt)) : '-'}</div>
                  <div>Due: {boardItem.dueAt ? formatTimestamp(new Date(boardItem.dueAt)) : '-'}</div>
                  {!isHostActionCard ? <div>Manager: {displayManagerAgent(boardItem.workspaceKey, boardItem.managerAgent)}</div> : null}
                  {!isHostActionCard ? <div>Target: {displayTargetAgent(boardItem.workspaceKey, boardItem.targetAgent)}</div> : null}
                  {!isHostActionCard && boardItem.workspaceAgent ? <div>Workspace agent: {displayWorkspaceAgent(boardItem.workspaceKey, boardItem.workspaceAgent)}</div> : null}
                  {!isHostActionCard && boardItem.executionMode ? <div>Execution mode: {boardItem.executionMode}</div> : null}
                  {!isHostActionCard && displayWorkerStatusLabel(boardItem.queueEntry) ? <div>Worker status: {displayWorkerStatusLabel(boardItem.queueEntry)}</div> : null}
                  {!isHostActionCard && boardItem.queueEntry?.executor_worker_id ? <div>Worker host: {boardItem.queueEntry.executor_worker_id}</div> : null}
                  {!isHostActionCard && boardItem.queueEntry?.manager_attention_required ? <div>Manager attention: required</div> : null}
                </div>
              </section>
            </div>

            {boardItem.reason ? (
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '16px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Why This Card Exists</p>
                <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.65, margin: 0 }}>{boardItem.reason}</p>
              </section>
            ) : null}

            {ownerReviewPayload ? (
              <section style={{ borderRadius: '16px', border: '1px solid rgba(251,191,36,0.28)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '16px' }}>
                <p style={{ color: '#fbbf24', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Owner Review Context</p>
                <div style={{ display: 'grid', gap: '8px', color: '#fef3c7', fontSize: '13px' }}>
                  <div>{ownerReviewKindLabel(ownerReviewPayload)}: {ownerReviewReferenceLabel(ownerReviewPayload, linkId)}</div>
                  {ownerReviewPayload.format ? <div>Format: {ownerReviewPayload.format}</div> : null}
                  {ownerReviewPayload.transform_type ? <div>Transform type: {humanizeStatusLabel(ownerReviewPayload.transform_type)}</div> : null}
                  {ownerReviewPayload.latent_reason ? <div>Why it was preserved: {humanizeStatusLabel(ownerReviewPayload.latent_reason)}</div> : null}
                  {ownerReviewPayload.packet_recommendation ? <div>Recommendation: {ownerReviewPayload.packet_recommendation}</div> : null}
                  {ownerReviewPayload.core_angle ? <div>Core angle: {ownerReviewPayload.core_angle}</div> : null}
                  {ownerReviewPayload.summary ? <div>Source summary: {ownerReviewPayload.summary}</div> : null}
                  {ownerReviewPayload.why_now ? <div>Why now: {ownerReviewPayload.why_now}</div> : null}
                  <div>Approval status: {humanizeStatusLabel(ownerReviewPayload.approval_status ?? 'unknown')}</div>
                </div>
              </section>
            ) : hostActionPayload ? (
              <section style={{ borderRadius: '16px', border: '1px solid rgba(251,191,36,0.28)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '16px' }}>
                <p style={{ color: '#fbbf24', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Host Action Context</p>
                <div style={{ display: 'grid', gap: '8px', color: '#fef3c7', fontSize: '13px' }}>
                  {hostActionPayload.summary ? <div>Remaining step: {hostActionPayload.summary}</div> : null}
                  {hostActionPayload.source_card_title ? <div>Source card: {hostActionPayload.source_card_title}</div> : null}
                  {hostActionPayload.source_result_summary ? <div>Source result: {hostActionPayload.source_result_summary}</div> : null}
                  {hostActionPayload.detected_from ? <div>Detected from: {humanizeStatusLabel(hostActionPayload.detected_from)}</div> : null}
                  {hostActionSteps.length > 0 ? (
                    <div>
                      Host steps:
                      <div style={{ display: 'grid', gap: '4px', marginTop: '6px' }}>
                        {hostActionSteps.map((step) => (
                          <div key={`${card.id}-host-step-${step}`}>{step}</div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {hostActionProofRequired.length > 0 ? (
                    <div>
                      Expected evidence:
                      <div style={{ display: 'grid', gap: '4px', marginTop: '6px' }}>
                        {hostActionProofRequired.map((step) => (
                          <div key={`${card.id}-host-proof-${step}`}>{step}</div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}

            {ownerReviewAssessment ? (
              <section style={{ borderRadius: '16px', border: '1px solid rgba(56,189,248,0.28)', backgroundColor: 'rgba(56,189,248,0.08)', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '10px' }}>
                  <p style={{ color: '#38bdf8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', margin: 0 }}>System Read</p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {ownerReviewAssessment.suggested_decision ? (
                      <span style={{ borderRadius: '999px', border: '1px solid rgba(56,189,248,0.4)', backgroundColor: '#08101f', color: '#e0f2fe', padding: '6px 10px', fontSize: '12px', fontWeight: 700 }}>
                        Suggestion: {humanizeStatusLabel(ownerReviewAssessment.suggested_decision)}
                      </span>
                    ) : null}
                    {ownerReviewAssessment.confidence ? (
                      <span style={{ borderRadius: '999px', border: '1px solid rgba(148,163,184,0.32)', backgroundColor: '#08101f', color: '#cbd5e1', padding: '6px 10px', fontSize: '12px', fontWeight: 700 }}>
                        Confidence: {humanizeStatusLabel(ownerReviewAssessment.confidence)}
                      </span>
                    ) : null}
                  </div>
                </div>
                {ownerReviewAssessment.summary ? (
                  <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.65, margin: '0 0 10px' }}>{ownerReviewAssessment.summary}</p>
                ) : null}
                {Array.isArray(ownerReviewAssessment.reasons) && ownerReviewAssessment.reasons.length > 0 ? (
                  <div style={{ marginBottom: ownerReviewAssessment.missing_items?.length ? '10px' : 0 }}>
                    <p style={{ color: '#93c5fd', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 6px' }}>Why the system is leaning this way</p>
                    <div style={{ display: 'grid', gap: '4px' }}>
                      {ownerReviewAssessment.reasons.map((reason) => (
                        <p key={`${card.id}-assessment-reason-${reason}`} style={{ color: '#dbeafe', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                          {reason}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}
                {Array.isArray(ownerReviewAssessment.missing_items) && ownerReviewAssessment.missing_items.length > 0 ? (
                  <div style={{ marginBottom: ownerReviewAssessment.fallback_action ? '10px' : 0 }}>
                    <p style={{ color: '#fca5a5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 6px' }}>What still looks thin</p>
                    <div style={{ display: 'grid', gap: '4px' }}>
                      {ownerReviewAssessment.missing_items.map((entry) => (
                        <p key={`${card.id}-assessment-missing-${entry}`} style={{ color: '#fee2e2', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                          {entry}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}
                {ownerReviewAssessment.fallback_action ? (
                  <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.6, margin: 0 }}>{ownerReviewAssessment.fallback_action}</p>
                ) : null}
              </section>
            ) : null}

            {ownerDecisionScaffold ? (
              <section style={{ borderRadius: '16px', border: '1px solid rgba(16,185,129,0.28)', backgroundColor: 'rgba(16,185,129,0.08)', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '10px' }}>
                  <p style={{ color: '#34d399', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', margin: 0 }}>Owner Decision Scaffold</p>
                  {ownerDecisionScaffold.recommended_decision ? (
                    <span style={{ borderRadius: '999px', border: '1px solid rgba(16,185,129,0.4)', backgroundColor: '#08101f', color: '#d1fae5', padding: '6px 10px', fontSize: '12px', fontWeight: 700 }}>
                      Default: {humanizeStatusLabel(ownerDecisionScaffold.recommended_decision)}
                    </span>
                  ) : null}
                </div>
                {ownerDecisionScaffold.decision_question ? (
                  <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.65, margin: '0 0 10px' }}>{ownerDecisionScaffold.decision_question}</p>
                ) : null}
                {ownerDecisionScaffold.neo_answer_contract ? (
                  <p style={{ color: '#d1fae5', fontSize: '13px', lineHeight: 1.6, margin: '0 0 12px' }}>{ownerDecisionScaffold.neo_answer_contract}</p>
                ) : null}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                  {[
                    { label: 'Must Verify First', items: ownerDecisionScaffold.must_verify, tone: '#a7f3d0' },
                    { label: 'Approve When', items: ownerDecisionScaffold.approve_when, tone: '#d1fae5' },
                    { label: 'Revise When', items: ownerDecisionScaffold.revise_when, tone: '#fef3c7' },
                    { label: 'Park When', items: ownerDecisionScaffold.park_when, tone: '#fecaca' },
                  ]
                    .filter((section) => Array.isArray(section.items) && section.items.length > 0)
                    .map((section) => (
                      <div key={`${card.id}-scaffold-${section.label}`} style={{ borderRadius: '12px', border: '1px solid rgba(15,23,42,0.6)', backgroundColor: '#08101f', padding: '12px' }}>
                        <p style={{ color: section.tone, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 8px' }}>{section.label}</p>
                        <div style={{ display: 'grid', gap: '6px' }}>
                          {(section.items ?? []).map((entry) => (
                            <p key={`${card.id}-scaffold-entry-${section.label}-${entry}`} style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                              {entry}
                            </p>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
                {Array.isArray(ownerDecisionScaffold.optional_strengtheners) && ownerDecisionScaffold.optional_strengtheners.length > 0 ? (
                  <div style={{ marginTop: '12px' }}>
                    <p style={{ color: '#93c5fd', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 6px' }}>Optional Strengtheners</p>
                    <div style={{ display: 'grid', gap: '4px' }}>
                      {ownerDecisionScaffold.optional_strengtheners.map((entry) => (
                        <p key={`${card.id}-scaffold-optional-${entry}`} style={{ color: '#dbeafe', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                          {entry}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}
              </section>
            ) : null}

            {heldAtPmLayer ? (
              <section style={{ borderRadius: '16px', border: '1px solid rgba(251,191,36,0.28)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '16px' }}>
                <p style={{ color: '#fbbf24', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Held At PM Layer</p>
                <p style={{ color: '#fef3c7', fontSize: '14px', lineHeight: 1.65, margin: 0 }}>
                  This card carries a blocked judgment in PM metadata, but it is not currently in an active execution lane. That means the system is holding it for clearer direction before execution resumes.
                </p>
              </section>
            ) : null}

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#08101f', padding: '16px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Linked Meeting Context</p>
              {linkedStandups.length === 0 ? (
                <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No standup record is explicitly linked to this PM card yet.</p>
              ) : (
                <div style={{ display: 'grid', gap: '10px' }}>
                  {linkedStandups.map((entry) => {
                    const provenance = standupRecordProvenance(entry);
                    return (
                      <article key={`${card.id}-linked-standup-${entry.id}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap', marginBottom: '6px' }}>
                          <p style={{ color: 'white', fontWeight: 700, margin: 0 }}>{standupLabel(entry)}</p>
                          <span
                            style={{
                              borderRadius: '999px',
                              border: `1px solid ${provenance.border}`,
                              backgroundColor: provenance.background,
                              color: provenance.tone,
                              padding: '4px 8px',
                              fontSize: '10px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                            }}
                          >
                            {provenance.label}
                          </span>
                        </div>
                        <p style={{ color: '#94a3b8', fontSize: '12px', margin: '0 0 6px' }}>
                          {meetingLabelForWorkspace(entry.workspace_key ?? 'shared_ops')} · {entry.created_at ? formatTimestamp(new Date(entry.created_at)) : '-'}
                        </p>
                        <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{summarize(standupSummary(entry), 180)}</p>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === 'evidence' && (
          <div style={{ display: 'grid', gap: '12px' }}>
            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Record Linkage</p>
              <div style={{ display: 'grid', gap: '6px', color: '#cbd5f5', fontSize: '13px' }}>
                <div>Source: {rawSource}</div>
                <div>Link type: {linkType}</div>
                {boardItem.queueEntry?.trigger_key ? <div>Trigger key: {boardItem.queueEntry.trigger_key}</div> : null}
                {linkId ? <div>Link id: {linkId}</div> : null}
                {createdFromStandupId ? <div>Created from standup: {createdFromStandupId}</div> : null}
                {createdFromPrepId ? <div>Created from prep: {createdFromPrepId}</div> : null}
                {recommendationPath ? (
                  <div>
                    Recommendation packet:{' '}
                    <button
                      type="button"
                      onClick={() => onOpenArtifactPath(recommendationPath)}
                      style={{
                        border: 'none',
                        background: 'transparent',
                        padding: 0,
                        color: '#f8fafc',
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        textUnderlineOffset: '2px',
                      }}
                      title={recommendationPath}
                    >
                      {summarizePathForDisplay(recommendationPath)}
                    </button>
                  </div>
                ) : null}
              </div>
            </section>

            {ownerReviewPayload ? (
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Owner Review Draft</p>
                <div style={{ display: 'grid', gap: '10px' }}>
                  {ownerReviewPayload.draft_path ? (
                    <div>
                      <span style={{ color: '#94a3b8', fontSize: '12px' }}>Draft path: </span>
                      <button
                        type="button"
                        onClick={() => onOpenArtifactPath(ownerReviewPayload.draft_path as string)}
                        style={{
                          border: 'none',
                          background: 'transparent',
                          padding: 0,
                          color: '#f8fafc',
                          fontSize: '12px',
                          fontFamily: 'monospace',
                          cursor: 'pointer',
                          textDecoration: 'underline',
                          textUnderlineOffset: '2px',
                        }}
                        title={ownerReviewPayload.draft_path}
                      >
                        {summarizePathForDisplay(String(ownerReviewPayload.draft_path))}
                      </button>
                    </div>
                  ) : null}
                  {ownerReviewPayload.owner_packet_path ? (
                    <div>
                      <span style={{ color: '#94a3b8', fontSize: '12px' }}>Owner packet: </span>
                      <button
                        type="button"
                        onClick={() => onOpenArtifactPath(ownerReviewPayload.owner_packet_path as string)}
                        style={{
                          border: 'none',
                          background: 'transparent',
                          padding: 0,
                          color: '#f8fafc',
                          fontSize: '12px',
                          fontFamily: 'monospace',
                          cursor: 'pointer',
                          textDecoration: 'underline',
                          textUnderlineOffset: '2px',
                        }}
                        title={ownerReviewPayload.owner_packet_path ?? undefined}
                      >
                        {summarizePathForDisplay(String(ownerReviewPayload.owner_packet_path))}
                      </button>
                    </div>
                  ) : null}
                  {ownerReviewPayload.first_pass_draft ? (
                    <pre
                      style={{
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        color: '#e2e8f0',
                        fontSize: '12px',
                        lineHeight: 1.6,
                        margin: 0,
                        maxHeight: '280px',
                        overflowY: 'auto',
                        borderRadius: '12px',
                        border: '1px solid #1f2937',
                        backgroundColor: '#0b1324',
                        padding: '12px',
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                      }}
                    >
                      {ownerReviewPayload.first_pass_draft}
                    </pre>
                  ) : (
                    <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No first-pass draft text is attached to this PM card yet.</p>
                  )}
                  {(ownerReviewPayload.draft_owner_notes ?? []).length > 0 ? (
                    <div style={{ display: 'grid', gap: '6px' }}>
                      <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>Draft notes</p>
                      {(ownerReviewPayload.draft_owner_notes ?? []).map((note) => (
                        <p key={`${card.id}-owner-note-${note}`} style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>
                          {note}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Execution Artifacts</p>
              {!executionPacketPath && !sopArtifactPath && !briefingArtifactPath && latestExecutionArtifacts.length === 0 ? (
                <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No execution artifact paths are attached to this card yet.</p>
              ) : (
                <div style={{ display: 'grid', gap: '6px' }}>
                  {[
                    ['Execution packet', executionPacketPath],
                    ['SOP', sopArtifactPath],
                    ['Briefing', briefingArtifactPath],
                    ...latestExecutionArtifacts.map((path, index) => [`Result artifact ${index + 1}`, path] as const),
                  ].map(([label, path]) =>
                    path ? (
                      <div key={`${card.id}-${label}-${path}`}>
                        <span style={{ color: '#94a3b8', fontSize: '12px' }}>{label}: </span>
                        <button
                          type="button"
                          onClick={() => onOpenArtifactPath(path)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            padding: 0,
                            color: '#f8fafc',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                            textUnderlineOffset: '2px',
                          }}
                          title={path}
                        >
                          {summarizePathForDisplay(path)}
                        </button>
                      </div>
                    ) : null,
                  )}
                </div>
              )}
            </section>

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Linked Meeting Artifacts</p>
              {linkedStandups.length === 0 && linkedConversationPaths.length === 0 && linkedSourcePaths.length === 0 ? (
                <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No linked meeting artifacts are available for this card yet.</p>
              ) : (
                <div style={{ display: 'grid', gap: '10px' }}>
                  {linkedConversationPaths.length > 0 ? (
                    <div style={{ display: 'grid', gap: '4px' }}>
                      <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>Conversation artifacts</p>
                      {linkedConversationPaths.map((path) => (
                        <button
                          key={`${card.id}-conversation-${path}`}
                          type="button"
                          onClick={() => onOpenArtifactPath(path)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            padding: 0,
                            textAlign: 'left',
                            color: '#cbd5f5',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                            textUnderlineOffset: '2px',
                          }}
                          title={path}
                        >
                          {summarizePathForDisplay(path)}
                        </button>
                      ))}
                    </div>
                  ) : null}

                  {linkedSourcePaths.length > 0 ? (
                    <div style={{ display: 'grid', gap: '4px' }}>
                      <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>Supporting source paths</p>
                      {linkedSourcePaths.slice(0, 8).map((path) => (
                        <button
                          key={`${card.id}-source-${path}`}
                          type="button"
                          onClick={() => onOpenArtifactPath(path)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            padding: 0,
                            textAlign: 'left',
                            color: '#cbd5f5',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                            textUnderlineOffset: '2px',
                          }}
                          title={path}
                        >
                          {summarizePathForDisplay(path)}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}
            </section>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Latest Manual Review</p>
                {!latestManualReview ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No manual review metadata stored on this card yet.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px', color: '#e2e8f0', fontSize: '13px' }}>
                    <span>Action: {String(latestManualReview.action || 'unknown')}</span>
                    {latestManualReview.resolution_mode ? <span>Resolution mode: {String(latestManualReview.resolution_mode)}</span> : null}
                    <span>Reviewed by: {String(latestManualReview.reviewed_by || 'unknown')}</span>
                    <span>From lane: {String(latestManualReview.from_lane || 'unknown')}</span>
                    {latestManualReview.successor_card_title ? <span>Spawned next card: {String(latestManualReview.successor_card_title)}</span> : null}
                    <span>
                      Reviewed at:{' '}
                      {latestManualReview.reviewed_at ? formatTimestamp(new Date(String(latestManualReview.reviewed_at))) : '-'}
                    </span>
                  </div>
                )}
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Latest Execution Result</p>
                {!latestExecutionResult ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No execution result has been written back yet.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px', color: '#e2e8f0', fontSize: '13px' }}>
                    <span>Status: {String(latestExecutionResult.status || 'unknown')}</span>
                    {latestExecutionSummary ? <span>Summary: {summarize(latestExecutionSummary, 180)}</span> : null}
                    {latestExecutionResult.review_resolution ? <span>Review resolution: {String(latestExecutionResult.review_resolution)}</span> : null}
                    {latestExecutionResult.reviewed_at ? <span>Reviewed at: {formatTimestamp(new Date(String(latestExecutionResult.reviewed_at)))}</span> : null}
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {activeTab === 'outcomes' && (
          <div style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Current Lane</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{boardColumns.find((column) => column.key === boardItem.lane)?.label ?? boardItem.lane}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{guidance.summary}</p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Linked Meetings</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{linkedStandups.length}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>meeting record{linkedStandups.length === 1 ? '' : 's'} currently point into this card</p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Execution Ownership</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{displayTargetAgent(boardItem.workspaceKey, boardItem.targetAgent)}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>managed by {displayManagerAgent(boardItem.workspaceKey, boardItem.managerAgent)}</p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Latest Result</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{latestExecutionResult ? String(latestExecutionResult.status || 'unknown') : 'No result yet'}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{latestExecutionSummary ? summarize(latestExecutionSummary, 96) : 'Execution has not written a result back yet.'}</p>
              </section>
            </div>

            <EventChainStrip
              title="Shared Event Chain"
              description="This is the common source-to-execution spine for the card, using the same lifecycle story the standup reader shows."
              items={pmEventChainItems}
            />

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Meeting-To-Work Chain</p>
              <div style={{ display: 'grid', gap: '8px' }}>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  1. {linkedStandups.length > 0 ? `${linkedStandups.length} standup record${linkedStandups.length === 1 ? '' : 's'} linked into this card.` : `This card currently has no linked standup record.`}
                </p>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  2. The PM card is currently `{pmStatusLabel}` in PM and `{executionStatusLabel ?? 'not in execution yet'}` in execution.
                </p>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  3. Manager/target chain: {displayManagerAgent(boardItem.workspaceKey, boardItem.managerAgent)} {'->'} {displayTargetAgent(boardItem.workspaceKey, boardItem.targetAgent)}.
                </p>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  4. Latest result signal: {latestExecutionResult ? humanizeStatusLabel(String(latestExecutionResult.status || 'unknown')) : 'none yet'}.
                </p>
              </div>
            </section>

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Record History</p>
              <div style={{ display: 'grid', gap: '8px' }}>
                {historyItems.map((item) => (
                  <div key={`${card.id}-history-${item.label}-${item.detail}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '12px' }}>
                    <p style={{ color: item.tone ?? '#f8fafc', fontSize: '13px', fontWeight: 700, margin: '0 0 4px' }}>{item.label}</p>
                    <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{item.detail}</p>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {activeTab === 'raw' && (
          <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
            <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Stored PM Payload</p>
            <pre
              style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                color: '#e2e8f0',
                fontSize: '12px',
                lineHeight: 1.6,
                margin: 0,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
              }}
            >
              {rawRecord}
            </pre>
          </section>
        )}
      </div>
    </div>
  );
}

function StandupsPanel({
  entries,
  pmCards,
  executionQueue,
  automations,
  executiveFeed,
  error,
  onPromote,
  onOpenArtifactPath,
  onDispatchPmCard,
  onActOnPmCard,
}: {
  entries: StandupEntry[];
  pmCards: PMCard[];
  executionQueue: ExecutionQueueEntry[];
  automations: Automation[];
  executiveFeed: ExecutiveFeed;
  error: string | null;
  onPromote: (
    prep: StandupPrepPacket,
    recommendationPacket: PMRecommendationPacket | null,
    chronicleEntry: ChronicleEntry | null,
  ) => Promise<StandupPromotionResult>;
  onOpenArtifactPath: (path: string) => void;
  onDispatchPmCard: (cardId: string, targetAgent?: string) => Promise<PMCardDispatchResult>;
  onActOnPmCard: (cardId: string, action: 'approve' | 'return' | 'blocked', options?: PMCardActionOptions) => Promise<PMCardActionResult>;
}) {
  const automationCounts = useMemo(() => summarizeAutomationSources(automations), [automations]);
  const latestChronicle = executiveFeed.chronicleEntries[executiveFeed.chronicleEntries.length - 1] ?? executiveFeed.chronicleEntries[0] ?? null;
  const meetingOps = useMemo(() => buildMeetingOps(STANDUP_ROOMS, entries, pmCards, executionQueue), [entries, pmCards, executionQueue]);
  const [meetingView, setMeetingView] = useState<'list' | 'weekly' | 'monthly'>('list');
  const [promotingKey, setPromotingKey] = useState<string | null>(null);
  const [promotionFeedback, setPromotionFeedback] = useState<string | null>(null);
  const [promotionError, setPromotionError] = useState<string | null>(null);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);

  useEffect(() => {
    if (meetingOps.recentStandups.length === 0) {
      setSelectedMeetingId(null);
      return;
    }
    if (!selectedMeetingId || !meetingOps.recentStandups.some((entry) => entry.id === selectedMeetingId)) {
      setSelectedMeetingId(meetingOps.recentStandups[0].id);
    }
  }, [meetingOps.recentStandups, selectedMeetingId]);

  const handlePromote = useCallback(
    async (room: (typeof STANDUP_ROOMS)[number], prep: StandupPrepPacket) => {
      try {
        setPromotingKey(room.key);
        setPromotionError(null);
        setPromotionFeedback(null);
        const recommendationPacket = findRecommendationPacketForRoom(room, executiveFeed.pmRecommendations);
        const result = await onPromote(prep, recommendationPacket, latestChronicle);
        const createdCount = result.created_cards.length;
        const existingCount = result.existing_cards.length;
        setPromotionFeedback(
          `${room.label} created. ${createdCount} PM card${createdCount === 1 ? '' : 's'} added${existingCount ? `, ${existingCount} already existed` : ''}.`,
        );
      } catch (err) {
        setPromotionError(toErrorMessage(err));
      } finally {
        setPromotingKey(null);
      }
    },
    [executiveFeed.pmRecommendations, latestChronicle, onPromote],
  );

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Standups</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>Meeting layer</h2>
        <p style={{ color: '#94a3b8' }}>The PM board leads the meeting. Chronicle, pruning, crons, and workspace artifacts only support the decisions, owners, and PM mutations that come out of it.</p>
      </div>
      {error && <SectionAlert message={`${TELEMETRY_LABELS.standups}: ${error}`} />}
      {promotionError && <SectionAlert message={`Standup promotion: ${promotionError}`} />}
      {promotionFeedback && (
        <div style={{ borderRadius: '14px', border: '1px solid rgba(34,197,94,0.35)', backgroundColor: 'rgba(34,197,94,0.08)', padding: '12px 14px', color: '#bbf7d0', fontSize: '13px' }}>
          {promotionFeedback}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
        <MiniMeta label="Chronicle Chunks" value={`${executiveFeed.chronicleEntries.length}`} detail="recent Codex memory stream" />
        <MiniMeta label="Standup Packs" value={`${executiveFeed.standupPreps.length}`} detail="PM-first meetings ready" />
        <MiniMeta label="PM Packets" value={`${executiveFeed.pmRecommendations.length}`} detail="standup-driven execution queue" />
        <MiniMeta label="Automation Jobs" value={`${automationCounts.total}`} detail="jobs visible in Ops right now" />
        <MiniMeta label="Launchd Loop" value={`${automationCounts.launchd}`} detail="local runner and maintenance jobs" />
        <MiniMeta label="Latest Chronicle" value={latestChronicle?.createdAt ? formatTimestamp(new Date(latestChronicle.createdAt)) : '-'} detail={latestChronicle ? summarize(latestChronicle.summary, 52) : 'No Chronicle entries yet'} />
      </div>
      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '16px' }}>
        <div style={{ marginBottom: '12px' }}>
          <p style={{ color: '#22c55e', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Meeting Ops</p>
          <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Watchdog, dispatch, and accountability</h3>
          <p style={{ color: '#94a3b8' }}>This is the practical signal: did the meeting run, did it attach to PM work, and is the resulting work still moving.</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <MiniMeta
            label="Healthy Rooms"
            value={`${meetingOps.rooms.filter((room) => room.status === 'ok').length}`}
            detail={`${meetingOps.rooms.filter((room) => room.status !== 'ok' && room.status !== 'planned').length} need attention`}
          />
          <MiniMeta label="Linked Cards" value={`${meetingOps.linkedCardCount}`} detail="active PM cards tied back to standups" />
          <MiniMeta label="Resolved Links" value={`${meetingOps.resolvedLinkedCardCount}`} detail="closed historical PM cards kept for transcript traceability" />
          <MiniMeta label="Orphan Standups" value={`${meetingOps.orphanStandupCount}`} detail="meetings with decisions but no linked PM card" />
          <MiniMeta label="Stale Ready" value={`${meetingOps.staleReadyCount}`} detail="ready execution items aging in place" />
          <MiniMeta label="Stale Review" value={`${meetingOps.staleReviewCount}`} detail="results waiting too long for a closeout" />
          <MiniMeta label="Stale Running" value={`${meetingOps.staleRunningCount}`} detail="queued/running lanes that need follow-through" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginTop: '14px' }}>
          {meetingOps.rooms.map((room) => (
            <article key={`room-health-${room.key}`} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
                <p style={{ color: 'white', fontWeight: 700, margin: 0 }}>{room.label}</p>
                {statusBadge(room.status)}
              </div>
              <p style={{ color: '#cbd5f5', fontSize: '13px', margin: '0 0 8px' }}>{room.reason}</p>
              <div style={{ color: '#64748b', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span>Workspace: {meetingLabelForWorkspace(room.workspaceKey)}</span>
                <span>Rounds: {room.roundCount}</span>
                <span>
                  Latest: {room.latestEntry?.created_at ? formatTimestamp(new Date(room.latestEntry.created_at)) : 'No transcript yet'}
                </span>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '16px' }}>
        <div style={{ marginBottom: '12px' }}>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Source Artifacts</p>
          <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>What is feeding the meetings right now</h3>
        <p style={{ color: '#94a3b8' }}>These are the supporting files and runtime surfaces the team should read after checking the PM board slice for the meeting.</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          {executiveFeed.artifacts.map((artifact) => (
            <article key={artifact.id} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
                <p style={{ color: 'white', fontWeight: 600, margin: 0 }}>{artifact.label}</p>
                {statusBadge(artifact.category)}
              </div>
              <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: '0 0 8px' }}>{artifact.summary}</p>
              <div style={{ color: '#94a3b8', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span>{artifact.detail}</span>
                <span>{artifact.updatedAt ? formatTimestamp(new Date(artifact.updatedAt)) : 'No timestamp'}</span>
                {artifact.path && <span>{artifact.path}</span>}
              </div>
            </article>
          ))}
        </div>
      </section>
      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#c084fc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Meeting History</p>
            <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Reader, weekly, and monthly views</h3>
            <p style={{ color: '#94a3b8' }}>Use Reader when you want the actual meeting card, not just a transcript dump.</p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {(['list', 'weekly', 'monthly'] as const).map((view) => (
              <button
                key={view}
                type="button"
                onClick={() => setMeetingView(view)}
                style={{
                  borderRadius: '999px',
                  border: '1px solid #334155',
                  backgroundColor: meetingView === view ? '#1e293b' : '#0b1324',
                  color: meetingView === view ? '#f8fafc' : '#94a3b8',
                  padding: '8px 14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {view === 'list' ? 'reader' : view}
              </button>
            ))}
          </div>
        </div>
        {meetingView === 'list' && (
          <MeetingReaderView
            entries={meetingOps.recentStandups}
            pmCards={pmCards}
            executionQueue={executionQueue}
            selectedMeetingId={selectedMeetingId}
            onSelectMeeting={setSelectedMeetingId}
            onOpenArtifactPath={onOpenArtifactPath}
            onDispatchPmCard={onDispatchPmCard}
            onActOnPmCard={onActOnPmCard}
          />
        )}
        {meetingView === 'weekly' && <MeetingWeeklyView entries={meetingOps.recentStandups} />}
        {meetingView === 'monthly' && <MeetingMonthlyView entries={meetingOps.recentStandups} />}
      </section>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
        {STANDUP_ROOMS.map((room) => {
          const prep = findStandupPrepForRoom(room, executiveFeed.standupPreps);
          const liveEntry = findLiveStandupEntry(room, entries);
          const roomHealth = meetingOps.byRoomKey[room.key];
          const agenda = prep?.agenda ?? extractStandupList(liveEntry?.payload, 'agenda');
          const blockers = prep?.blockers ?? liveEntry?.blockers ?? [];
          const commitments = prep?.commitments ?? liveEntry?.commitments ?? [];
          const needs = prep?.needs ?? liveEntry?.needs ?? [];
          const artifactDeltas = prep?.artifactDeltas ?? extractStandupList(liveEntry?.payload, 'artifact_deltas');
          const pmSnapshotLines = prep ? extractPmSnapshotLines(prep.pmSnapshot) : extractPmSnapshotLines(liveEntry?.payload?.pm_snapshot);
          const pmTitles = prep?.pmUpdateTitles ?? [];
          const cardStatus = prep ? 'prepared' : roomHealth?.status ?? (liveEntry ? liveEntry.status ?? 'recorded' : room.workspaceKey === 'shared_ops' ? 'ready' : 'planned');

          return (
            <article
              key={room.key}
              onClick={() => {
                if (liveEntry) {
                  setMeetingView('list');
                  setSelectedMeetingId(liveEntry.id);
                }
              }}
              style={{
                borderRadius: '18px',
                border: '1px solid #1f2937',
                backgroundColor: '#0b1324',
                padding: '18px',
                cursor: liveEntry ? 'pointer' : 'default',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ fontSize: '20px', color: 'white', margin: 0 }}>{room.label}</h3>
                  <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '4px' }}>{prep?.generatedAt ? formatTimestamp(new Date(prep.generatedAt)) : liveEntry?.created_at ? formatTimestamp(new Date(liveEntry.created_at)) : 'Awaiting first artifact-backed meeting'}</p>
                </div>
                {statusBadge(cardStatus)}
              </div>
              <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.6, marginBottom: '12px' }}>{prep?.summary ?? room.description}</p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
                {room.participants.map((participant) => (
                  <span key={participant} style={{ borderRadius: '999px', border: '1px solid #334155', padding: '4px 10px', color: '#e2e8f0', fontSize: '12px' }}>
                    {participant}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
                {room.sources.map((source) => (
                  <span key={source} style={{ borderRadius: '999px', backgroundColor: '#0f172a', border: '1px solid #1f2937', padding: '4px 10px', color: '#94a3b8', fontSize: '11px' }}>
                    {source}
                  </span>
                ))}
              </div>
              {prep && (
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
                  <div style={{ color: '#94a3b8', fontSize: '12px' }}>
                    Promotion will create the standup record and seed PM cards from the current prep packet.
                  </div>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      void handlePromote(room, prep);
                    }}
                    disabled={promotingKey === room.key}
                    style={{
                      padding: '8px 14px',
                      borderRadius: '999px',
                      border: '1px solid rgba(56,189,248,0.35)',
                      backgroundColor: promotingKey === room.key ? '#0f172a' : '#38bdf8',
                      color: promotingKey === room.key ? '#94a3b8' : '#04111f',
                      fontWeight: 700,
                      cursor: promotingKey === room.key ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {promotingKey === room.key ? 'Creating…' : `Create ${room.label}`}
                  </button>
                </div>
              )}
              {liveEntry && (
                <div style={{ color: '#38bdf8', fontSize: '12px', marginBottom: '12px' }}>
                  Open meeting reader
                </div>
              )}
              <PanelList title="Captured PM Snapshot" items={pmSnapshotLines} emptyLabel="No PM snapshot captured yet." />
              <PanelList title="Agenda" items={agenda} emptyLabel="No agenda captured yet." />
              <PanelList title="Artifact Deltas" items={artifactDeltas} emptyLabel="No supporting artifact deltas captured yet." />
              <PanelList title="Blockers" items={blockers} emptyLabel="No blockers captured yet." />
              <PanelList title="Commitments" items={commitments} emptyLabel="No commitments captured yet." />
              <PanelList title="Needs" items={needs} emptyLabel="No cross-team needs captured yet." />
              <PanelList title="PM Changes" items={pmTitles} emptyLabel="No PM recommendations attached yet." />
            </article>
          );
        })}
      </div>
      <div style={{ display: 'grid', gap: '14px' }}>
        {entries.length === 0 && <EmptyPanel message="No live standup API entries recorded yet. The new local standup-prep packets are ready to seed the first meetings." />}
        {entries.map((entry) => {
          const sections = extractStandupSections(entry.payload);
          return (
            <article key={entry.id} style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '20px', color: 'white', margin: 0 }}>{entry.owner}</h3>
                <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '4px' }}>
                  {meetingLabelForWorkspace(entry.workspace_key ?? 'shared_ops')} · {entry.created_at ? formatTimestamp(new Date(entry.created_at)) : '-'}
                </p>
              </div>
              {statusBadge(entry.status ?? 'pending')}
            </div>
            <PanelList title="Status" items={entry.status ? [entry.status] : []} emptyLabel="No status summary yet." />
            <PanelList title="Captured PM Snapshot" items={extractPmSnapshotLines(entry.payload?.pm_snapshot)} emptyLabel="No PM snapshot captured." />
            <PanelList title="Current Linked PM Cards" items={liveLinkedCardItems(entry, pmCards)} emptyLabel="No live PM cards linked to this standup." />
            <PanelList title="Agenda" items={extractStandupList(entry.payload, 'agenda')} emptyLabel="No agenda captured." />
            {sections.map((section) => (
              <PanelList key={`${entry.id}-${section.key}`} title={section.title} items={section.items} emptyLabel={`No ${section.title.toLowerCase()} captured.`} />
            ))}
            <PanelList title="Discussion" items={extractStandupDiscussion(entry.payload)} emptyLabel="No executive discussion captured." />
            <PanelList title="Decisions" items={extractStandupList(entry.payload, 'decisions')} emptyLabel="No decisions captured." />
            <PanelList title="Owners" items={extractStandupList(entry.payload, 'owners')} emptyLabel="No owners captured." />
            <PanelList title="Artifact Deltas" items={extractStandupList(entry.payload, 'artifact_deltas')} emptyLabel="No artifact deltas captured." />
            <PanelList title="Blockers" items={entry.blockers} emptyLabel="No blockers captured." />
            <PanelList title="Commitments" items={entry.commitments} emptyLabel="No commitments captured." />
            <PanelList title="Needs" items={entry.needs} emptyLabel="No cross-team needs captured." />
            </article>
          );
        })}
      </div>
    </section>
  );
}

function MeetingReaderView({
  entries,
  pmCards,
  executionQueue,
  selectedMeetingId,
  onSelectMeeting,
  onOpenArtifactPath,
  onDispatchPmCard,
  onActOnPmCard,
}: {
  entries: StandupEntry[];
  pmCards: PMCard[];
  executionQueue: ExecutionQueueEntry[];
  selectedMeetingId: string | null;
  onSelectMeeting: (id: string) => void;
  onOpenArtifactPath: (path: string) => void;
  onDispatchPmCard: (cardId: string, targetAgent?: string) => Promise<PMCardDispatchResult>;
  onActOnPmCard: (cardId: string, action: 'approve' | 'return' | 'blocked', options?: PMCardActionOptions) => Promise<PMCardActionResult>;
}) {
  const [activeTab, setActiveTab] = useState<'conversation' | 'evidence' | 'outcomes' | 'raw'>('conversation');
  const [actioningCardId, setActioningCardId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const selectedEntry = entries.find((entry) => entry.id === selectedMeetingId) ?? entries[0] ?? null;

  useEffect(() => {
    setActionFeedback(null);
    setActionError(null);
  }, [selectedMeetingId]);

  if (!selectedEntry) {
    return <EmptyPanel message="No standup transcripts recorded yet." compact />;
  }

  const room = standupRoom(selectedEntry);
  const discussion = standupDiscussion(selectedEntry);
  const agenda = extractStandupList(selectedEntry.payload, 'agenda');
  const decisions = extractStandupList(selectedEntry.payload, 'decisions');
  const owners = extractStandupList(selectedEntry.payload, 'owners');
  const artifactDeltas = extractStandupList(selectedEntry.payload, 'artifact_deltas');
  const standupSections = extractStandupSections(selectedEntry.payload);
  const provenance = standupRecordProvenance(selectedEntry);
  const participantBuckets = standupParticipantBuckets(selectedEntry);
  const payload = selectedEntry.payload ?? {};
  const rawSource = typeof selectedEntry.source === 'string' && selectedEntry.source.trim() ? selectedEntry.source.trim() : 'unknown';
  const prepId = typeof payload.prep_id === 'string' && payload.prep_id.trim() ? payload.prep_id.trim() : null;
  const sourcePaths = Array.isArray(payload.source_paths)
    ? payload.source_paths.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  const recommendationPath = typeof payload.recommendation_path === 'string' && payload.recommendation_path.trim() ? payload.recommendation_path.trim() : null;
  const conversationPath = typeof selectedEntry.conversation_path === 'string' && selectedEntry.conversation_path.trim()
    ? selectedEntry.conversation_path.trim()
    : null;
  const linkedStandupCards = buildLinkedStandupCards(selectedEntry, pmCards, executionQueue);
  const inferenceNotes = buildStandupInferenceNotes(selectedEntry, participantBuckets);
  const historyItems = buildStandupHistoryItems(selectedEntry, linkedStandupCards);
  const rawRecord = JSON.stringify(
    {
      id: selectedEntry.id,
      owner: selectedEntry.owner,
      workspace_key: selectedEntry.workspace_key,
      status: selectedEntry.status,
      source: selectedEntry.source,
      conversation_path: selectedEntry.conversation_path,
      blockers: selectedEntry.blockers,
      commitments: selectedEntry.commitments,
      needs: selectedEntry.needs,
      payload: selectedEntry.payload ?? {},
      created_at: selectedEntry.created_at,
    },
    null,
    2,
  );
  const standupEventChainItems = [
    {
      label: 'Source',
      value: prepId ? 'Prep packet' : rawSource,
      detail: prepId ? summarize(prepId, 42) : summarize(rawSource, 72),
      tone: '#38bdf8',
    },
    {
      label: 'Meeting',
      value: selectedEntry.status ?? 'completed',
      detail: selectedEntry.created_at ? formatTimestamp(new Date(selectedEntry.created_at)) : 'No timestamp stored',
      tone: '#a78bfa',
    },
    {
      label: 'PM',
      value: `${linkedStandupCards.length} linked`,
      detail: linkedStandupCards[0] ? summarize(linkedStandupCards[0].card.title, 72) : 'No PM card has been linked to this meeting yet.',
      tone: '#f59e0b',
    },
    {
      label: 'Execution',
      value: summarizeLinkedExecutionStates(linkedStandupCards),
      detail: linkedStandupCards.length > 0 ? 'Current downstream state of meeting-created work.' : 'Execution begins once linked PM cards are created.',
      tone: '#22c55e',
    },
    {
      label: 'Result',
      value: linkedStandupCards.some((item) => item.boardItem.lane === 'done')
        ? `${linkedStandupCards.filter((item) => item.boardItem.lane === 'done').length} closed`
        : 'No closed results yet',
      detail: linkedStandupCards.some((item) => item.boardItem.lane === 'review')
        ? `${linkedStandupCards.filter((item) => item.boardItem.lane === 'review').length} waiting on review`
        : 'No linked card is waiting on review right now.',
      tone: '#818cf8',
    },
  ];

  const handleLinkedCardAction = async (action: 'dispatch' | 'approve' | 'return' | 'blocked', item: LinkedStandupCard) => {
    try {
      setActioningCardId(item.card.id);
      setActionError(null);
      setActionFeedback(null);
      if (action === 'dispatch') {
        await onDispatchPmCard(item.card.id, item.queueEntry?.target_agent || displayTargetAgent(item.boardItem.workspaceKey, item.boardItem.targetAgent));
        setActionFeedback(`Opened SOP for ${item.card.title}.`);
        return;
      }
      if (action === 'approve') {
        setActionFeedback('Resolve review cards from the PM Board modal so you can choose whether to close the lane or spawn the next card.');
        return;
      }
      await onActOnPmCard(item.card.id, action);
      setActionFeedback(
        action === 'return'
          ? `Returned ${item.card.title} to Jean-Claude.`
          : `Marked ${item.card.title} as blocked and rerouted it to Jean-Claude.`,
      );
    } catch (error) {
      setActionError(toErrorMessage(error));
    } finally {
      setActioningCardId(null);
    }
  };

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(250px, 0.78fr) minmax(0, 2.2fr)',
        gap: '14px',
        alignItems: 'start',
      }}
    >
      <aside style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '14px', minHeight: '620px' }}>
        <div style={{ marginBottom: '12px' }}>
          <p style={{ color: '#94a3b8', letterSpacing: '0.16em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Agent Meetings</p>
          <p style={{ color: 'white', fontWeight: 700, margin: 0 }}>Recent sessions</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {entries.map((entry) => {
            const active = entry.id === selectedEntry.id;
            const entryRoom = standupRoom(entry);
            const entryDiscussion = standupDiscussion(entry);
            const entryParticipants = standupParticipantBuckets(entry);
            const entryProvenance = standupRecordProvenance(entry);
            return (
              <button
                key={`reader-${entry.id}`}
                type="button"
                onClick={() => onSelectMeeting(entry.id)}
                style={{
                  textAlign: 'left',
                  borderRadius: '14px',
                  border: active ? '1px solid rgba(251,191,36,0.45)' : '1px solid #1f2937',
                  backgroundColor: active ? 'rgba(251,191,36,0.12)' : '#08101f',
                  padding: '12px',
                  cursor: 'pointer',
                  display: 'grid',
                  gap: '6px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center' }}>
                  <p style={{ color: 'white', fontWeight: 700, fontSize: '13px', margin: 0 }}>{standupLabel(entry)}</p>
                  {statusBadge(entry.status ?? 'completed')}
                </div>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>
                  {entry.created_at ? formatTimestamp(new Date(entry.created_at)) : '-'}
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', color: '#64748b', fontSize: '11px' }}>
                  <span>{meetingLabelForWorkspace(entry.workspace_key ?? 'shared_ops')}</span>
                  <span>{entryDiscussion.length} rounds</span>
                  <span>{entryParticipants.merged.length} attendees</span>
                  {entryRoom ? <span>{entryRoom.key}</span> : null}
                </div>
                <span
                  style={{
                    width: 'fit-content',
                    borderRadius: '999px',
                    border: `1px solid ${entryProvenance.border}`,
                    backgroundColor: entryProvenance.background,
                    color: entryProvenance.tone,
                    padding: '4px 8px',
                    fontSize: '10px',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                  }}
                >
                  {entryProvenance.label}
                </span>
                <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.45, margin: 0 }}>{summarize(standupSummary(entry), 84)}</p>
              </button>
            );
          })}
        </div>
      </aside>

      <section style={{ borderRadius: '22px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px', alignItems: 'flex-start', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#fbbf24', letterSpacing: '0.16em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Conversation</p>
            <h3 style={{ color: 'white', fontSize: '28px', lineHeight: 1.2, margin: 0 }}>{standupLabel(selectedEntry)}</h3>
            <p style={{ color: '#94a3b8', fontSize: '13px', margin: '6px 0 0' }}>
              {meetingLabelForWorkspace(selectedEntry.workspace_key ?? 'shared_ops')} · {selectedEntry.created_at ? formatTimestamp(new Date(selectedEntry.created_at)) : '-'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {statusBadge(selectedEntry.status ?? 'completed')}
            {room ? (
              <span style={{ borderRadius: '999px', border: '1px solid #334155', padding: '6px 10px', color: '#cbd5f5', fontSize: '12px' }}>
                {room.key}
              </span>
            ) : null}
            <span
              style={{
                borderRadius: '999px',
                border: `1px solid ${provenance.border}`,
                backgroundColor: provenance.background,
                color: provenance.tone,
                padding: '6px 10px',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              {provenance.label}
            </span>
          </div>
        </div>

        {actionError && <SectionAlert message={`Meeting reader action: ${actionError}`} />}
        {actionFeedback && (
          <div style={{ borderRadius: '14px', border: '1px solid rgba(34,197,94,0.35)', backgroundColor: 'rgba(34,197,94,0.08)', padding: '12px 14px', color: '#bbf7d0', fontSize: '13px', marginBottom: '12px' }}>
            {actionFeedback}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
          {([
            ['conversation', 'Conversation'],
            ['evidence', 'Evidence'],
            ['outcomes', 'Outcomes'],
            ['raw', 'Raw'],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              style={{
                borderRadius: '999px',
                border: activeTab === key ? '1px solid rgba(251,191,36,0.45)' : '1px solid #334155',
                backgroundColor: activeTab === key ? 'rgba(251,191,36,0.12)' : '#0f172a',
                color: activeTab === key ? '#f8fafc' : '#94a3b8',
                padding: '8px 14px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {activeTab === 'conversation' && (
          <div style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Topic</p>
                <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.65, margin: 0 }}>
                  {standupSummary(selectedEntry)}
                  {agenda.length > 0 ? ` ${agenda[0]}` : ''}
                </p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Attendee Snapshot</p>
                <div style={{ display: 'grid', gap: '6px', color: '#e2e8f0', fontSize: '13px' }}>
                  <span>{participantBuckets.observed.length} observed attendee{participantBuckets.observed.length === 1 ? '' : 's'}</span>
                  <span>{participantBuckets.inferred.length} inferred from room defaults</span>
                  <span>{participantBuckets.merged.length} shown in the meeting reader</span>
                </div>
              </section>
            </div>

            {discussion.length > 0
              ? discussion.map((round, index) => {
                  const speaker = typeof round.speaker === 'string' && round.speaker.trim() ? round.speaker.trim() : 'Unknown';
                  const note = typeof round.note === 'string' && round.note.trim() ? round.note.trim() : 'No note captured.';
                  const focus = typeof round.focus === 'string' && round.focus.trim() ? round.focus.trim().replace(/[_-]+/g, ' ') : null;
                  const roundNumber = typeof round.round === 'number' ? round.round : index + 1;
                  return (
                    <section key={`${selectedEntry.id}-round-${roundNumber}-${speaker}-${index}`} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '8px' }}>
                        <p style={{ color: 'white', fontSize: '16px', fontWeight: 700, margin: 0 }}>{`Round ${roundNumber}: ${speaker}`}</p>
                        {focus ? <span style={{ color: '#94a3b8', fontSize: '12px' }}>{focus}</span> : null}
                      </div>
                      <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.7, margin: 0 }}>{note}</p>
                    </section>
                  );
                })
              : (
                <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                  <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Conversation</p>
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No structured discussion rounds were captured for this meeting yet.</p>
                </section>
              )}

            {standupSections.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                {standupSections.map((section) => (
                  <section key={`${selectedEntry.id}-${section.key}`} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                    <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>{section.title}</p>
                    <div style={{ display: 'grid', gap: '6px' }}>
                      {section.items.map((item) => (
                        <p key={`${selectedEntry.id}-${section.key}-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                          - {item}
                        </p>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Decisions</p>
                {decisions.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No decisions captured.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {decisions.map((item) => (
                      <p key={`${selectedEntry.id}-decision-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                        - {item}
                      </p>
                    ))}
                  </div>
                )}
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Commitments</p>
                {selectedEntry.commitments.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No commitments captured.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {selectedEntry.commitments.map((item) => (
                      <p key={`${selectedEntry.id}-commitment-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                        - {item}
                      </p>
                    ))}
                  </div>
                )}
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Blockers</p>
                {selectedEntry.blockers.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No blockers captured.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {selectedEntry.blockers.map((item) => (
                      <p key={`${selectedEntry.id}-blocker-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                        - {item}
                      </p>
                    ))}
                  </div>
                )}
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Cross-Team Needs</p>
                {selectedEntry.needs.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No cross-team needs captured.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {selectedEntry.needs.map((item) => (
                      <p key={`${selectedEntry.id}-need-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                        - {item}
                      </p>
                    ))}
                  </div>
                )}
              </section>
            </div>

            {(owners.length > 0 || artifactDeltas.length > 0) && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                  <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Owners</p>
                  {owners.length === 0 ? (
                    <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No owners captured.</p>
                  ) : (
                    <div style={{ display: 'grid', gap: '6px' }}>
                      {owners.map((item) => (
                        <p key={`${selectedEntry.id}-owner-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                          - {item}
                        </p>
                      ))}
                    </div>
                  )}
                </section>

                <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                  <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Artifact Deltas</p>
                  {artifactDeltas.length === 0 ? (
                    <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No artifact deltas captured.</p>
                  ) : (
                    <div style={{ display: 'grid', gap: '6px' }}>
                      {artifactDeltas.map((item) => (
                        <p key={`${selectedEntry.id}-artifact-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                          - {item}
                        </p>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}
          </div>
        )}

        {activeTab === 'evidence' && (
          <div style={{ display: 'grid', gap: '12px' }}>
            <section
              style={{
                borderRadius: '16px',
                border: `1px solid ${provenance.border}`,
                backgroundColor: provenance.background,
                padding: '14px',
              }}
            >
              <p style={{ color: provenance.tone, letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Meeting Provenance</p>
              <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.65, margin: 0 }}>{provenance.description}</p>
              <div style={{ display: 'grid', gap: '6px', marginTop: '12px' }}>
                <p style={{ color: '#cbd5f5', fontSize: '12px', margin: 0 }}>
                  <span style={{ color: '#94a3b8' }}>Stored source:</span>{' '}
                  <code style={{ color: 'white', fontSize: '12px' }}>{rawSource}</code>
                </p>
                {prepId ? (
                  <p style={{ color: '#cbd5f5', fontSize: '12px', margin: 0 }}>
                    <span style={{ color: '#94a3b8' }}>Prep packet:</span>{' '}
                    <code style={{ color: 'white', fontSize: '12px' }}>{prepId}</code>
                  </p>
                ) : null}
                {recommendationPath ? (
                  <p style={{ color: '#cbd5f5', fontSize: '12px', margin: 0 }}>
                    <span style={{ color: '#94a3b8' }}>Recommendation packet:</span>{' '}
                    <button
                      type="button"
                      onClick={() => onOpenArtifactPath(recommendationPath)}
                      style={{
                        border: 'none',
                        background: 'transparent',
                        padding: 0,
                        color: '#f8fafc',
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        textUnderlineOffset: '2px',
                      }}
                      title={recommendationPath}
                    >
                      {summarizePathForDisplay(recommendationPath)}
                    </button>
                  </p>
                ) : null}
                {conversationPath ? (
                  <p style={{ color: '#cbd5f5', fontSize: '12px', margin: 0 }}>
                    <span style={{ color: '#94a3b8' }}>Conversation artifact:</span>{' '}
                    <button
                      type="button"
                      onClick={() => onOpenArtifactPath(conversationPath)}
                      style={{
                        border: 'none',
                        background: 'transparent',
                        padding: 0,
                        color: '#f8fafc',
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        textUnderlineOffset: '2px',
                      }}
                      title={conversationPath}
                    >
                      {summarizePathForDisplay(conversationPath)}
                    </button>
                  </p>
                ) : null}
                {sourcePaths.length > 0 ? (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>Supporting sources:</p>
                    <div style={{ display: 'grid', gap: '4px' }}>
                      {sourcePaths.slice(0, 6).map((path) => (
                        <button
                          key={`${selectedEntry.id}-source-path-${path}`}
                          type="button"
                          onClick={() => onOpenArtifactPath(path)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            padding: 0,
                            textAlign: 'left',
                            color: '#cbd5f5',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                            cursor: 'pointer',
                            textDecoration: 'underline',
                            textUnderlineOffset: '2px',
                          }}
                          title={path}
                        >
                          {summarizePathForDisplay(path)}
                        </button>
                      ))}
                      {sourcePaths.length > 6 ? (
                        <p style={{ color: '#94a3b8', fontSize: '11px', margin: 0 }}>
                          +{sourcePaths.length - 6} more source path{sourcePaths.length - 6 === 1 ? '' : 's'} stored on this record
                        </p>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            </section>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Observed Attendees</p>
                {participantBuckets.observed.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No attendees were explicitly stored on the record.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {participantBuckets.observed.map((participant) => (
                      <p key={`${selectedEntry.id}-observed-${participant}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                        - {participant}
                      </p>
                    ))}
                  </div>
                )}
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Inferred From Room Defaults</p>
                {participantBuckets.inferred.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No default-room attendees were added on top of the stored record.</p>
                ) : (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {participantBuckets.inferred.map((participant) => (
                      <p key={`${selectedEntry.id}-inferred-${participant}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                        - {participant}
                      </p>
                    ))}
                  </div>
                )}
              </section>
            </div>

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Inference Disclosure</p>
              {inferenceNotes.length === 0 ? (
                <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No additional inference rules were detected for this meeting record.</p>
              ) : (
                <div style={{ display: 'grid', gap: '6px' }}>
                  {inferenceNotes.map((item) => (
                    <p key={`${selectedEntry.id}-inference-${item}`} style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                      - {item}
                    </p>
                  ))}
                </div>
              )}
            </section>

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Record History</p>
              <div style={{ display: 'grid', gap: '8px' }}>
                {historyItems.map((item) => (
                  <div key={`${selectedEntry.id}-history-${item.label}-${item.detail}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '12px' }}>
                    <p style={{ color: item.tone ?? '#f8fafc', fontSize: '13px', fontWeight: 700, margin: '0 0 4px' }}>{item.label}</p>
                    <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{item.detail}</p>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {activeTab === 'outcomes' && (
          <div style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Chain Start</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{prepId ? 'Prep packet' : rawSource}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{prepId ? summarize(prepId, 48) : summarize(standupSummary(selectedEntry), 88)}</p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Standup Record</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{selectedEntry.status ?? 'completed'}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{selectedEntry.created_at ? formatTimestamp(new Date(selectedEntry.created_at)) : 'No timestamp'}</p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>PM Links</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{linkedStandupCards.length}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>linked card{linkedStandupCards.length === 1 ? '' : 's'} from this meeting</p>
              </section>

              <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
                <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Execution State</p>
                <p style={{ color: 'white', fontWeight: 700, margin: '0 0 4px' }}>{summarizeLinkedExecutionStates(linkedStandupCards)}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>current downstream state for meeting-created work</p>
              </section>
            </div>

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Meeting-To-Work Chain</p>
              <div style={{ display: 'grid', gap: '8px' }}>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  1. {prepId ? `Prep packet ${prepId}` : `Stored source ${rawSource}`} shaped the meeting input.
                </p>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  2. The standup record was written as `{selectedEntry.status ?? 'completed'}` on {selectedEntry.created_at ? formatTimestamp(new Date(selectedEntry.created_at)) : 'an unknown date'}.
                </p>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  3. {linkedStandupCards.length} linked PM card{linkedStandupCards.length === 1 ? '' : 's'} currently carry the work out of this meeting.
                </p>
                <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>
                  4. Current downstream execution mix: {summarizeLinkedExecutionStates(linkedStandupCards)}.
                </p>
              </div>
            </section>

            <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
              <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Linked PM Cards</p>
              {linkedStandupCards.length === 0 ? (
                <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>No PM cards are currently linked to this standup.</p>
              ) : (
                <div style={{ display: 'grid', gap: '12px' }}>
                  {linkedStandupCards.map((item) => {
                    const theme = workspaceBoardTheme(item.boardItem.workspaceKey);
                    const latestExecutionResult = item.card.payload?.latest_execution_result as Record<string, unknown> | undefined;
                    const latestExecutionSummary = typeof latestExecutionResult?.summary === 'string' && latestExecutionResult.summary.trim()
                      ? latestExecutionResult.summary.trim()
                      : null;
                    return (
                      <article
                        key={`${selectedEntry.id}-linked-card-${item.card.id}`}
                        style={{
                          borderRadius: '14px',
                          border: `1px solid ${theme.border}`,
                          backgroundColor: theme.background,
                          padding: '14px',
                          display: 'grid',
                          gap: '10px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                          <div>
                            <p style={{ color: 'white', fontSize: '16px', fontWeight: 700, margin: '0 0 6px' }}>{item.card.title}</p>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', color: '#cbd5f5', fontSize: '12px' }}>
                              <span>{meetingLabelForWorkspace(item.boardItem.workspaceKey)}</span>
                              <span>PM: {displayPmStatusLabel(item.card.status, item.boardItem.lane, item.boardItem.executionState)}</span>
                              <span>Lane: {item.boardItem.lane}</span>
                              <span>Updated: {item.card.updated_at ? formatTimestamp(new Date(item.card.updated_at)) : '-'}</span>
                            </div>
                          </div>
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                            {statusBadge(item.boardItem.lane === 'failed' ? 'blocked' : item.boardItem.lane)}
                            {statusBadge(displayPmStatusLabel(item.card.status, item.boardItem.lane, item.boardItem.executionState))}
                          </div>
                        </div>

                        <div style={{ display: 'grid', gap: '6px', color: '#e2e8f0', fontSize: '13px' }}>
                          <span>Manager: {displayManagerAgent(item.boardItem.workspaceKey, item.boardItem.managerAgent)}</span>
                          <span>Target: {displayTargetAgent(item.boardItem.workspaceKey, item.boardItem.targetAgent)}</span>
                          {item.boardItem.workspaceAgent ? <span>Workspace agent: {displayWorkspaceAgent(item.boardItem.workspaceKey, item.boardItem.workspaceAgent)}</span> : null}
                        </div>

                        <div style={{ display: 'grid', gap: '6px' }}>
                          <p style={{ color: '#f8fafc', fontSize: '13px', margin: 0 }}>{item.guidance.summary}</p>
                          <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{item.guidance.nextAction}</p>
                          {latestExecutionSummary ? <p style={{ color: '#cbd5f5', fontSize: '12px', margin: 0 }}>Latest result: {summarize(latestExecutionSummary, 180)}</p> : null}
                        </div>

                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                          {(item.boardItem.lane === 'ready' || item.boardItem.lane === 'todo') && (
                            <button
                              type="button"
                              disabled={actioningCardId === item.card.id}
                              onClick={() => void handleLinkedCardAction('dispatch', item)}
                              style={meetingActionButtonStyle('primary', actioningCardId === item.card.id)}
                            >
                              {actioningCardId === item.card.id ? 'Opening…' : 'Open SOP'}
                            </button>
                          )}
                          {item.boardItem.lane === 'review' && (
                            <button
                              type="button"
                              disabled={actioningCardId === item.card.id}
                              onClick={() => void handleLinkedCardAction('approve', item)}
                              style={meetingActionButtonStyle('success', actioningCardId === item.card.id)}
                            >
                              Resolve in PM Board
                            </button>
                          )}
                          {['review', 'queued', 'running', 'failed'].includes(item.boardItem.lane) && (
                            <button
                              type="button"
                              disabled={actioningCardId === item.card.id}
                              onClick={() => void handleLinkedCardAction('return', item)}
                              style={meetingActionButtonStyle('secondary', actioningCardId === item.card.id)}
                            >
                              {actioningCardId === item.card.id ? 'Returning…' : 'Return to Jean-Claude'}
                            </button>
                          )}
                          {['review', 'queued', 'running', 'failed'].includes(item.boardItem.lane) && (
                            <button
                              type="button"
                              disabled={actioningCardId === item.card.id}
                              onClick={() => void handleLinkedCardAction('blocked', item)}
                              style={meetingActionButtonStyle('danger', actioningCardId === item.card.id)}
                            >
                              {actioningCardId === item.card.id ? 'Routing…' : 'Mark blocked'}
                            </button>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === 'raw' && (
          <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
            <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '8px' }}>Stored Standup Payload</p>
            <pre
              style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                color: '#e2e8f0',
                fontSize: '12px',
                lineHeight: 1.6,
                margin: 0,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
              }}
            >
              {rawRecord}
            </pre>
          </section>
        )}
      </section>
    </div>
  );
}

function standupParticipantBuckets(entry: StandupEntry): StandupParticipantBuckets {
  const payload = entry.payload ?? {};
  const observed = Array.isArray(payload.participants)
    ? payload.participants
        .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        .map((item) => item.trim())
    : [];
  const roomParticipants = standupRoom(entry)?.participants ?? [];
  const inferred = roomParticipants.filter(
    (participant) => observed.findIndex((candidate) => candidate.toLowerCase() === participant.toLowerCase()) === -1,
  );
  const merged = [...observed, ...inferred].filter(
    (participant, index, all) => all.findIndex((candidate) => candidate.toLowerCase() === participant.toLowerCase()) === index,
  );

  if (merged.length === 0 && entry.owner) {
    return { observed: [entry.owner], inferred: [], merged: [entry.owner] };
  }

  return {
    observed,
    inferred,
    merged,
  };
}

function buildLinkedStandupCards(entry: StandupEntry, pmCards: PMCard[], executionQueue: ExecutionQueueEntry[]): LinkedStandupCard[] {
  const executionByCardId = new Map(executionQueue.map((queueEntry) => [queueEntry.card_id, queueEntry]));
  return linkedCardsForStandup(entry, pmCards)
    .sort((left, right) => {
      const leftDone = (left.status ?? '').toLowerCase() === 'done' ? 1 : 0;
      const rightDone = (right.status ?? '').toLowerCase() === 'done' ? 1 : 0;
      if (leftDone !== rightDone) {
        return leftDone - rightDone;
      }
      const leftTime = left.updated_at ? new Date(left.updated_at).getTime() : 0;
      const rightTime = right.updated_at ? new Date(right.updated_at).getTime() : 0;
      return rightTime - leftTime;
    })
    .map((card) => {
      const queueEntry = executionByCardId.get(card.id) ?? null;
      const boardItem = buildMeetingBoardItem(card, queueEntry);
      return {
        card,
        queueEntry,
        boardItem,
        guidance: boardItemGuidance(boardItem),
      };
    });
}

function buildMeetingBoardItem(card: PMCard, queueEntry: ExecutionQueueEntry | null): UnifiedBoardItem {
  const ownerReviewPayload =
    card.payload?.owner_review && typeof card.payload.owner_review === 'object'
      ? (card.payload.owner_review as OwnerReviewCardPayload)
      : null;
  const normalizedStatus = normalizeStatus(card.status ?? 'todo');
  const lane: UnifiedBoardLaneKey = queueEntry
    ? normalizeExecutionState(queueEntry.execution_state)
    : normalizedStatus === 'in_progress'
      ? 'running'
      : normalizedStatus === 'review'
        ? 'review'
        : normalizedStatus === 'done'
          ? 'done'
          : 'todo';
  return {
    id: `meeting-card-${card.id}`,
    cardId: card.id,
    title: ownerReviewDisplayTitle(card, ownerReviewPayload),
    workspaceKey: workspaceKeyFromCard(card),
    lane,
    pmStatus: card.status ?? 'todo',
    executionState: queueEntry?.execution_state ?? null,
    managerAgent: queueEntry?.manager_agent ?? null,
    targetAgent: queueEntry?.target_agent ?? null,
    workspaceAgent: queueEntry?.workspace_agent ?? null,
    executionMode: queueEntry?.execution_mode ?? null,
    reason: queueEntry?.reason ?? (card.payload?.reason as string | undefined) ?? null,
    source: queueEntry?.source ?? card.source ?? null,
    owner: card.owner ?? null,
    updatedAt: queueEntry?.last_transition_at ?? card.updated_at ?? card.created_at ?? null,
    dueAt: card.due_at ?? null,
    queueEntry,
  };
}

function buildStandupInferenceNotes(entry: StandupEntry, participants: StandupParticipantBuckets): string[] {
  const payload = entry.payload ?? {};
  const source = (entry.source ?? '').toLowerCase();
  const notes: string[] = [];
  if (source === 'standup_prep' || (typeof payload.prep_id === 'string' && payload.prep_id.trim().length > 0)) {
    notes.push('Discussion rounds were synthesized from a standup prep packet before the final meeting record was written.');
  }
  if (source === 'brain_triage') {
    notes.push('Agenda, summary, and participants were shaped from routed Brain signal rather than a literal meeting capture.');
  }
  if (participants.inferred.length > 0) {
    notes.push('The attendee list includes room-default participants that were not explicitly stored on the meeting payload itself.');
  }
  if (extractStandupList(entry.payload, 'owners').length > 0 && (source === 'standup_prep' || source === 'brain_triage')) {
    notes.push('Owners were derived from the workspace and standup contract, not necessarily spoken verbatim in the room.');
  }
  if (Array.isArray(payload.source_paths) && payload.source_paths.length > 0) {
    notes.push('Supporting source paths are context files attached to the record. They are useful evidence, but they do not prove each file was quoted directly during the meeting.');
  }
  return notes;
}

function buildStandupHistoryItems(entry: StandupEntry, linkedCards: LinkedStandupCard[]): MeetingHistoryItem[] {
  const payload = entry.payload ?? {};
  const items: MeetingHistoryItem[] = [];
  if (entry.created_at) {
    items.push({
      label: 'Created',
      detail: `Standup record stored on ${formatTimestamp(new Date(entry.created_at))} with status \`${entry.status ?? 'completed'}\`.`,
      tone: '#e2e8f0',
    });
  }
  if (typeof payload.prep_id === 'string' && payload.prep_id.trim()) {
    items.push({
      label: 'Promoted From Prep',
      detail: `This record was promoted from prep packet \`${payload.prep_id}\`.`,
      tone: '#fbbf24',
    });
  }
  if (typeof payload.recommendation_path === 'string' && payload.recommendation_path.trim()) {
    items.push({
      label: 'Recommendation Packet Attached',
      detail: `A recommendation packet was attached at ${summarizePathForDisplay(payload.recommendation_path)} before or during promotion.`,
      tone: '#38bdf8',
    });
  }
  if (linkedCards.length > 0) {
    const statusCounts = linkedCards.reduce<Record<string, number>>((acc, item) => {
      const key = item.boardItem.lane;
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    }, {});
    const latestCard = [...linkedCards].sort((left, right) => {
      const leftTime = left.card.updated_at ? new Date(left.card.updated_at).getTime() : 0;
      const rightTime = right.card.updated_at ? new Date(right.card.updated_at).getTime() : 0;
      return rightTime - leftTime;
    })[0];
    items.push({
      label: 'Linked Cards Updated',
      detail: `${linkedCards.length} linked PM card${linkedCards.length === 1 ? '' : 's'} currently sit in ${Object.entries(statusCounts)
        .map(([status, count]) => `${status}=${count}`)
        .join(', ')}. Latest linked update: ${latestCard?.card.updated_at ? formatTimestamp(new Date(latestCard.card.updated_at)) : 'unknown'}.`,
      tone: '#38bdf8',
    });
  }
  const postSyncDispatch = payload.post_sync_dispatch;
  if (postSyncDispatch && typeof postSyncDispatch === 'object') {
    const postSync = postSyncDispatch as Record<string, unknown>;
    const linkedCount = Array.isArray(postSync.linked_card_ids) ? postSync.linked_card_ids.length : 0;
    const createdCount = Array.isArray(postSync.created_card_ids) ? postSync.created_card_ids.length : 0;
    items.push({
      label: 'Post-Sync Dispatch',
      detail: `Ran ${postSync.ran_at ? formatTimestamp(new Date(String(postSync.ran_at))) : 'at an unknown time'} with status \`${String(postSync.status || 'unknown')}\`, linking ${linkedCount} card${linkedCount === 1 ? '' : 's'} and creating ${createdCount} new card${createdCount === 1 ? '' : 's'}.`,
      tone: String(postSync.status || '') === 'ok' ? '#22c55e' : '#fbbf24',
    });
  }
  const latestExecution = linkedCards
    .map((item) => ({
      title: item.card.title,
      result: item.card.payload?.latest_execution_result as Record<string, unknown> | undefined,
      updatedAt: item.card.updated_at,
    }))
    .filter((item) => item.result && item.updatedAt)
    .sort((left, right) => new Date(String(right.updatedAt)).getTime() - new Date(String(left.updatedAt)).getTime())[0];
  if (latestExecution?.result) {
    items.push({
      label: 'Latest Execution Result',
      detail: `The most recent result write-back came from \`${latestExecution.title}\` with status \`${String(latestExecution.result.status || 'unknown')}\`.`,
      tone: String(latestExecution.result.status || '') === 'done' ? '#22c55e' : '#fbbf24',
    });
  }
  return items;
}

function buildPmCardHistoryItems(card: PMCard, boardItem: UnifiedBoardItem, linkedStandups: StandupEntry[]): MeetingHistoryItem[] {
  const payload = card.payload ?? {};
  const items: MeetingHistoryItem[] = [];
  const pmStatusLabel = displayPmStatusLabel(card.status, boardItem.lane, boardItem.executionState);
  if (card.created_at) {
    items.push({
      label: 'Created',
      detail: `PM card stored on ${formatTimestamp(new Date(card.created_at))} with status \`${pmStatusLabel}\`.`,
      tone: '#e2e8f0',
    });
  }
  if (linkedStandups.length > 0) {
    const latestStandup = [...linkedStandups].sort((left, right) => standupCreatedAt(right).getTime() - standupCreatedAt(left).getTime())[0];
    items.push({
      label: 'Linked Meetings',
      detail: `${linkedStandups.length} standup record${linkedStandups.length === 1 ? '' : 's'} currently link into this card. Latest linked meeting: ${latestStandup ? `${standupLabel(latestStandup)} on ${latestStandup.created_at ? formatTimestamp(new Date(latestStandup.created_at)) : 'unknown date'}` : 'unknown'}.`,
      tone: '#38bdf8',
    });
  }
  if (typeof payload.created_from_prep_id === 'string' && payload.created_from_prep_id.trim()) {
    items.push({
      label: 'Created From Prep',
      detail: `This PM card was seeded from prep packet \`${payload.created_from_prep_id}\`.`,
      tone: '#fbbf24',
    });
  }
  if (typeof payload.recommendation_path === 'string' && payload.recommendation_path.trim()) {
    items.push({
      label: 'Recommendation Packet Attached',
      detail: `This card carries recommendation evidence from ${summarizePathForDisplay(payload.recommendation_path)}.`,
      tone: '#38bdf8',
    });
  }
  const ownerReview =
    payload.owner_review && typeof payload.owner_review === 'object'
      ? (payload.owner_review as OwnerReviewCardPayload)
      : null;
  if (ownerReview?.queue_id) {
    items.push({
      label: 'Owner Review Linked',
      detail: `This PM card is linked to ${ownerReviewKindLabel(ownerReview).toLowerCase()} \`${ownerReview.entry_kind === 'supplemental' ? ownerReview.title ?? ownerReview.queue_id : ownerReview.queue_id}\`${ownerReview.approval_status ? ` with approval status \`${ownerReview.approval_status}\`` : ''}.`,
      tone: '#fbbf24',
    });
  }
  if (boardItem.queueEntry) {
    items.push({
      label: 'Execution Lane',
      detail: `Execution is currently \`${displayExecutionStateLabel(boardItem.executionState)}\` in lane \`${boardItem.queueEntry.lane}\`, managed by ${displayManagerAgent(boardItem.workspaceKey, boardItem.managerAgent)} and targeting ${displayTargetAgent(boardItem.workspaceKey, boardItem.targetAgent)}.`,
      tone: ['failed', 'blocked'].includes((boardItem.executionState ?? '').toLowerCase()) ? '#f87171' : '#22c55e',
    });
  }
  const latestManualReview =
    payload.latest_manual_review && typeof payload.latest_manual_review === 'object'
      ? (payload.latest_manual_review as Record<string, unknown>)
      : null;
  if (latestManualReview) {
    const resolutionMode = typeof latestManualReview.resolution_mode === 'string' ? String(latestManualReview.resolution_mode) : null;
    const successorTitle = typeof latestManualReview.successor_card_title === 'string' ? String(latestManualReview.successor_card_title) : null;
    items.push({
      label: 'Latest Manual Review',
      detail: `Manual review recorded action \`${String(latestManualReview.action || 'unknown')}\`${resolutionMode ? ` with resolution mode \`${resolutionMode}\`` : ''} from lane \`${String(latestManualReview.from_lane || 'unknown')}\` at ${latestManualReview.reviewed_at ? formatTimestamp(new Date(String(latestManualReview.reviewed_at))) : 'an unknown time'}${successorTitle ? `. Spawned follow-up: ${successorTitle}.` : '.'}`,
      tone: '#fbbf24',
    });
  }
  const latestExecutionResult =
    payload.latest_execution_result && typeof payload.latest_execution_result === 'object'
      ? (payload.latest_execution_result as Record<string, unknown>)
      : null;
  if (latestExecutionResult) {
    items.push({
      label: 'Latest Execution Result',
      detail: `Execution wrote back status \`${humanizeStatusLabel(String(latestExecutionResult.status || 'unknown'))}\`${latestExecutionResult.review_resolution ? ` and review resolution \`${String(latestExecutionResult.review_resolution)}\`` : ''}.`,
      tone: String(latestExecutionResult.status || '') === 'done' ? '#22c55e' : '#fbbf24',
    });
  }
  return items;
}

function summarizeLinkedExecutionStates(items: LinkedStandupCard[]) {
  if (items.length === 0) {
    return 'No linked work yet';
  }
  const counts = items.reduce<Record<string, number>>((acc, item) => {
    acc[item.boardItem.lane] = (acc[item.boardItem.lane] ?? 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts)
    .map(([lane, count]) => `${lane}=${count}`)
    .join(' · ');
}

function meetingActionButtonStyle(tone: 'primary' | 'secondary' | 'success' | 'danger', disabled: boolean) {
  const palette =
    tone === 'primary'
      ? { background: '#38bdf8', border: 'rgba(56,189,248,0.35)', color: '#04111f' }
      : tone === 'success'
        ? { background: '#22c55e', border: 'rgba(34,197,94,0.35)', color: '#04110a' }
        : tone === 'danger'
          ? { background: '#ef4444', border: 'rgba(239,68,68,0.35)', color: '#fff1f2' }
          : { background: '#0f172a', border: '#334155', color: '#e2e8f0' };
  return {
    padding: '8px 12px',
    borderRadius: '999px',
    border: `1px solid ${palette.border}`,
    backgroundColor: disabled ? '#0f172a' : palette.background,
    color: disabled ? '#64748b' : palette.color,
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
  };
}

function MeetingListView({ entries }: { entries: StandupEntry[] }) {
  return (
    <div style={{ display: 'grid', gap: '12px' }}>
      {entries.length === 0 && <EmptyPanel message="No standup transcripts recorded yet." compact />}
      {entries.map((entry) => {
        const discussion = standupDiscussion(entry);
        const decisions = extractStandupList(entry.payload, 'decisions');
        const owners = extractStandupList(entry.payload, 'owners');
        return (
          <article key={`meeting-list-${entry.id}`} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
              <p style={{ color: 'white', fontWeight: 700, margin: 0 }}>{standupLabel(entry)}</p>
              {statusBadge(entry.status ?? 'completed')}
            </div>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
              <span>{meetingLabelForWorkspace(entry.workspace_key ?? 'shared_ops')}</span>
              <span>{entry.created_at ? formatTimestamp(new Date(entry.created_at)) : '-'}</span>
              <span>{discussion.length} rounds</span>
              <span>{decisions.length} decisions</span>
            </div>
            <p style={{ color: '#cbd5f5', fontSize: '13px', margin: '0 0 8px' }}>{standupSummary(entry)}</p>
            <div style={{ color: '#64748b', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span>Owners: {owners.length ? owners.slice(0, 2).join(' | ') : 'Not captured yet'}</span>
              <span>Commitments: {entry.commitments.length}</span>
              <span>Blockers: {entry.blockers.length}</span>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function MeetingWeeklyView({ entries }: { entries: StandupEntry[] }) {
  const days = buildRecentDayBuckets(entries, 7);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '12px' }}>
      {days.map((day) => (
        <article key={`weekly-${day.key}`} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '14px', minHeight: '180px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '10px' }}>
            <p style={{ color: 'white', fontWeight: 700, margin: 0 }}>{day.label}</p>
            <span style={{ color: '#64748b', fontSize: '12px' }}>{day.entries.length}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {day.entries.length === 0 && <p style={{ color: '#475569', fontSize: '13px' }}>No meetings recorded.</p>}
            {day.entries.map((entry) => (
              <div key={`weekly-entry-${entry.id}`} style={{ borderRadius: '12px', border: '1px solid #162033', backgroundColor: '#08101f', padding: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '6px' }}>
                  <p style={{ color: 'white', fontSize: '13px', fontWeight: 600, margin: 0 }}>{standupLabel(entry)}</p>
                  {statusBadge(entry.status ?? 'completed')}
                </div>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>
                  {entry.created_at ? formatTimestamp(new Date(entry.created_at)) : '-'} · {standupDiscussion(entry).length} rounds
                </p>
              </div>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function MeetingMonthlyView({ entries }: { entries: StandupEntry[] }) {
  const days = buildMonthBuckets(entries);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '12px' }}>
      {days.map((day) => (
        <article key={`monthly-${day.key}`} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '12px', minHeight: '120px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
            <p style={{ color: 'white', fontWeight: 700, margin: 0 }}>{day.label}</p>
            <span style={{ color: day.entries.length ? '#38bdf8' : '#475569', fontSize: '12px' }}>{day.entries.length}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {day.entries.slice(0, 3).map((entry) => (
              <p key={`monthly-entry-${entry.id}`} style={{ color: '#94a3b8', fontSize: '11px', margin: 0 }}>
                {standupLabel(entry)}
              </p>
            ))}
            {day.entries.length > 3 && <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>+{day.entries.length - 3} more</p>}
          </div>
        </article>
      ))}
    </div>
  );
}

function WorkspaceHubPanel({
  files,
  selected,
  onSelect,
  cards,
  executionQueue,
  standups,
  executiveFeed,
  plan,
  reactionQueue,
  socialFeed,
  sourceAssets,
  personaReviewSummary,
  longFormRoutes,
  workspaceSnapshotState,
  workspaceSnapshotError,
  workspaceRefreshStatus,
  feedbackSummary,
  onReloadLiveSnapshot,
}: {
  files: WorkspaceFile[];
  selected: WorkspaceFile | null;
  onSelect: (path: string) => void;
  cards: PMCard[];
  executionQueue: ExecutionQueueEntry[];
  standups: StandupEntry[];
  executiveFeed: ExecutiveFeed;
  plan: WeeklyPlan | null;
  reactionQueue: ReactionQueue | null;
  socialFeed: SocialFeed | null;
  sourceAssets: SourceAssetInventory | null;
  personaReviewSummary: PersonaReviewSummary | null;
  longFormRoutes: LongFormRouteSummary | null;
  workspaceSnapshotState: 'loading' | 'live' | 'error';
  workspaceSnapshotError: string | null;
  workspaceRefreshStatus: FeedRefreshStatus | null;
  feedbackSummary: FeedbackSummary | null;
  onReloadLiveSnapshot: () => Promise<void>;
}) {
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<WorkspaceHubKey>('linkedin-os');
  const [selectorOpen, setSelectorOpen] = useState(true);
  const activeWorkspace = WORKSPACE_HUBS.find((item) => item.id === selectedWorkspaceId) ?? WORKSPACE_HUBS[0];
  const workspaceFiles = useMemo(
    () => files.filter((file) => workspaceFileBelongsToHub(file, selectedWorkspaceId)),
    [files, selectedWorkspaceId],
  );
  const workspaceFileCounts = useMemo(() => {
    const counts = {
      docs: 0,
      briefings: 0,
      dispatch: 0,
      analytics: 0,
      memory: 0,
      standups: 0,
      root: 0,
      other: 0,
    };
    workspaceFiles.forEach((file) => {
      const section = workspaceFileSection(file, selectedWorkspaceId);
      if (section === 'docs') {
        counts.docs += 1;
      } else if (section === 'briefings') {
        counts.briefings += 1;
      } else if (section === 'dispatch') {
        counts.dispatch += 1;
      } else if (section === 'analytics') {
        counts.analytics += 1;
      } else if (section === 'memory') {
        counts.memory += 1;
      } else if (section === 'standups') {
        counts.standups += 1;
      } else if (section === 'root') {
        counts.root += 1;
      } else {
        counts.other += 1;
      }
    });
    return counts;
  }, [workspaceFiles, selectedWorkspaceId]);
  const visibleWorkspaceFiles = useMemo(() => {
    const ordered = [...workspaceFiles].sort((left, right) => {
      const priorityDelta = workspaceFilePriority(left, selectedWorkspaceId) - workspaceFilePriority(right, selectedWorkspaceId);
      if (priorityDelta !== 0) {
        return priorityDelta;
      }
      return timestampMs(right.updatedAt) - timestampMs(left.updatedAt);
    });
    const curated = ordered.filter((file) => workspaceFilePriority(file, selectedWorkspaceId) < 90);
    return (curated.length > 0 ? curated : ordered).slice(0, 12);
  }, [workspaceFiles, selectedWorkspaceId]);
  const selectedWorkspaceFile = useMemo(() => {
    if (selected && workspaceFileBelongsToHub(selected, selectedWorkspaceId)) {
      return selected;
    }
    return visibleWorkspaceFiles[0] ?? workspaceFiles[0] ?? null;
  }, [selected, selectedWorkspaceId, visibleWorkspaceFiles, workspaceFiles]);
  const sidebarWorkspaceFiles = useMemo(() => {
    const ordered: WorkspaceFile[] = [];
    const seen = new Set<string>();

    const push = (file: WorkspaceFile | null | undefined) => {
      if (!file || seen.has(file.path)) {
        return;
      }
      seen.add(file.path);
      ordered.push(file);
    };

    push(selectedWorkspaceFile);
    visibleWorkspaceFiles.forEach(push);
    return ordered;
  }, [selectedWorkspaceFile, visibleWorkspaceFiles]);
  const workspaceStandups = useMemo(
    () => sortByTimestampDesc(standups.filter((entry) => normalizeWorkspaceBoardKey(entry.workspace_key ?? 'shared_ops') === selectedWorkspaceId), (entry) => entry.created_at),
    [standups, selectedWorkspaceId],
  );
  const workspacePmCards = useMemo(
    () => sortByTimestampDesc(cards.filter((card) => workspaceKeyFromCard(card) === selectedWorkspaceId), (card) => card.updated_at ?? card.created_at),
    [cards, selectedWorkspaceId],
  );
  const workspaceOpenCards = useMemo(
    () => workspacePmCards.filter((card) => normalizeStatus(card.status) !== 'done'),
    [workspacePmCards],
  );
  const workspaceExecutionEntries = useMemo(
    () =>
      sortByTimestampDesc(
        executionQueue.filter((entry) => normalizeWorkspaceBoardKey(entry.workspace_key) === selectedWorkspaceId),
        (entry) => entry.last_transition_at ?? entry.queued_at,
      ),
    [executionQueue, selectedWorkspaceId],
  );
  const workspaceActiveExecution = useMemo(
    () => workspaceExecutionEntries.filter((entry) => normalizeExecutionState(entry.execution_state) !== 'done'),
    [workspaceExecutionEntries],
  );
  const workspaceChronicleEntries = useMemo(
    () =>
      sortByTimestampDesc(
        executiveFeed.chronicleEntries.filter((entry) => normalizeWorkspaceBoardKey(entry.workspaceKey) === selectedWorkspaceId),
        (entry) => entry.createdAt,
      ),
    [executiveFeed.chronicleEntries, selectedWorkspaceId],
  );
  const workspaceStandupPreps = useMemo(
    () =>
      sortByTimestampDesc(
        executiveFeed.standupPreps.filter((entry) => normalizeWorkspaceBoardKey(entry.workspaceKey) === selectedWorkspaceId),
        (entry) => entry.generatedAt,
      ),
    [executiveFeed.standupPreps, selectedWorkspaceId],
  );
  const workspacePmRecommendations = useMemo(
    () =>
      sortByTimestampDesc(
        executiveFeed.pmRecommendations.filter(
          (entry) =>
            normalizeWorkspaceBoardKey(entry.workspaceKey) === selectedWorkspaceId ||
            entry.items.some((item) => normalizeWorkspaceBoardKey(item.workspaceKey) === selectedWorkspaceId),
        ),
        (entry) => entry.createdAt,
      ),
    [executiveFeed.pmRecommendations, selectedWorkspaceId],
  );
  const workspaceHasActivity =
    workspaceFiles.length > 0 ||
    workspaceStandups.length > 0 ||
    workspacePmCards.length > 0 ||
    workspaceExecutionEntries.length > 0 ||
    workspaceChronicleEntries.length > 0 ||
    workspaceStandupPreps.length > 0 ||
    workspacePmRecommendations.length > 0;
  const latestWorkspaceActivity = useMemo(() => {
    const latest = Math.max(
      ...[
        ...workspaceFiles.map((file) => timestampMs(file.updatedAt)),
        ...workspaceStandups.map((entry) => timestampMs(entry.created_at)),
        ...workspacePmCards.map((card) => timestampMs(card.updated_at ?? card.created_at)),
        ...workspaceExecutionEntries.map((entry) => timestampMs(entry.last_transition_at ?? entry.queued_at)),
        ...workspaceChronicleEntries.map((entry) => timestampMs(entry.createdAt)),
        ...workspaceStandupPreps.map((entry) => timestampMs(entry.generatedAt)),
        ...workspacePmRecommendations.map((entry) => timestampMs(entry.createdAt)),
      ],
      0,
    );
    return latest > 0 ? formatTimestamp(new Date(latest)) : 'No activity yet';
  }, [
    workspaceChronicleEntries,
    workspaceExecutionEntries,
    workspaceFiles,
    workspacePmCards,
    workspacePmRecommendations,
    workspaceStandupPreps,
    workspaceStandups,
  ]);
  const workspaceSummaryCards = useMemo(
    () => [
      {
        label: 'Status',
        value: workspaceLifecycleLabel(activeWorkspace.status),
        detail: workspaceLifecycleDetail(activeWorkspace.status),
      },
      {
        label: 'Last Activity',
        value: latestWorkspaceActivity,
        detail: workspaceHasActivity ? 'latest workspace file, standup, or execution update' : 'no visible workspace artifacts yet',
      },
      {
        label: 'Workspace Files',
        value: `${workspaceFiles.length}`,
        detail: `${workspaceFileCounts.docs} docs · ${workspaceFileCounts.briefings} briefings · ${workspaceFileCounts.analytics} analytics`,
      },
      {
        label: 'Standups',
        value: `${workspaceStandups.length}`,
        detail: `${workspaceStandupPreps.length} prep packet${workspaceStandupPreps.length === 1 ? '' : 's'} captured`,
      },
      {
        label: 'Open PM',
        value: `${workspaceOpenCards.length}`,
        detail: `${workspacePmCards.length} total card${workspacePmCards.length === 1 ? '' : 's'} in this lane`,
      },
      {
        label: 'Execution',
        value: `${workspaceActiveExecution.length}`,
        detail: `${workspaceExecutionEntries.length} queue entr${workspaceExecutionEntries.length === 1 ? 'y' : 'ies'} tied to this workspace`,
      },
      {
        label: 'Dispatch',
        value: `${workspaceFileCounts.dispatch}`,
        detail: `${workspaceChronicleEntries.length} Chronicle entr${workspaceChronicleEntries.length === 1 ? 'y' : 'ies'} routed here`,
      },
      {
        label: 'Memory',
        value: `${workspaceFileCounts.memory}`,
        detail: `${workspacePmRecommendations.length} PM recommendation packet${workspacePmRecommendations.length === 1 ? '' : 's'}`,
      },
    ],
    [
      activeWorkspace.status,
      latestWorkspaceActivity,
      workspaceActiveExecution.length,
      workspaceChronicleEntries.length,
      workspaceExecutionEntries.length,
      workspaceFileCounts.analytics,
      workspaceFileCounts.briefings,
      workspaceFileCounts.dispatch,
      workspaceFileCounts.docs,
      workspaceFileCounts.memory,
      workspaceFiles.length,
      workspaceHasActivity,
      workspaceOpenCards.length,
      workspacePmCards.length,
      workspacePmRecommendations.length,
      workspaceStandupPreps.length,
      workspaceStandups.length,
    ],
  );
  const workspaceActivityCopy = useMemo(() => {
    if (!workspaceHasActivity) {
      return activeWorkspace.status === 'planned'
        ? `${activeWorkspace.label} is defined in the portfolio registry, but no dedicated artifacts are visible yet. When the backend starts writing files, standups, or execution traces here, this surface will expose them.`
        : `${activeWorkspace.label} is standing up. The backend lane exists, but visible artifacts have not accumulated yet. As soon as they do, they will render here instead of being hidden behind scaffold copy.`;
    }
    const clauses = [
      `${workspaceFiles.length} tracked file${workspaceFiles.length === 1 ? '' : 's'}`,
      `${workspaceStandups.length} standup${workspaceStandups.length === 1 ? '' : 's'}`,
      `${workspaceOpenCards.length} open PM card${workspaceOpenCards.length === 1 ? '' : 's'}`,
    ];
    if (workspaceActiveExecution.length > 0) {
      clauses.push(`${workspaceActiveExecution.length} active execution item${workspaceActiveExecution.length === 1 ? '' : 's'}`);
    }
    const joined = clauses.join(', ');
    if (activeWorkspace.status === 'standing_up') {
      return `${activeWorkspace.label} is still marked as standing up in the backend, but it is already generating ${joined}. This surface now reflects that real activity instead of treating the workspace like an empty placeholder.`;
    }
    return `${activeWorkspace.label} is generating ${joined}. This surface mirrors those backend signals directly.`;
  }, [
    activeWorkspace.label,
    activeWorkspace.status,
    workspaceActiveExecution.length,
    workspaceFiles.length,
    workspaceHasActivity,
    workspaceOpenCards.length,
    workspaceStandups.length,
  ]);
  const workspaceStandupItems = useMemo(
    () =>
      workspaceStandups.slice(0, 4).map((entry) => {
        const createdAt = entry.created_at ? formatTimestamp(new Date(entry.created_at)) : 'No timestamp';
        return `${standupLabel(entry)} · ${createdAt} · ${entry.commitments.length} commitments · ${entry.blockers.length} blockers`;
      }),
    [workspaceStandups],
  );
  const workspacePmItems = useMemo(
    () =>
      workspaceOpenCards.slice(0, 4).map((card) => {
        const updatedAt = card.updated_at ?? card.created_at;
        const timestamp = updatedAt ? formatTimestamp(new Date(updatedAt)) : 'No timestamp';
        return `${summarize(card.title, 84)} · ${humanizeStatusLabel(card.status)} · ${timestamp}`;
      }),
    [workspaceOpenCards],
  );
  const workspaceExecutionItems = useMemo(
    () =>
      workspaceActiveExecution.slice(0, 4).map((entry) => {
        const updatedAt = entry.last_transition_at ?? entry.queued_at;
        const timestamp = updatedAt ? formatTimestamp(new Date(updatedAt)) : 'No timestamp';
        return `${summarize(entry.title, 84)} · ${humanizeStatusLabel(entry.execution_state)} · ${timestamp}`;
      }),
    [workspaceActiveExecution],
  );
  const workspaceRoutingItems = useMemo(() => {
    const items: string[] = [];
    workspaceChronicleEntries.slice(0, 2).forEach((entry) => {
      items.push(`Chronicle · ${entry.createdAt ? formatTimestamp(new Date(entry.createdAt)) : 'No timestamp'} · ${summarize(entry.summary, 92)}`);
    });
    workspaceStandupPreps.slice(0, 2).forEach((entry) => {
      items.push(`Standup prep · ${entry.generatedAt ? formatTimestamp(new Date(entry.generatedAt)) : 'No timestamp'} · ${summarize(entry.summary, 92)}`);
    });
    workspacePmRecommendations.slice(0, 2).forEach((entry) => {
      const leadItem = entry.items.find((item) => normalizeWorkspaceBoardKey(item.workspaceKey) === selectedWorkspaceId) ?? entry.items[0];
      items.push(
        `PM packet · ${entry.createdAt ? formatTimestamp(new Date(entry.createdAt)) : 'No timestamp'} · ${summarize(leadItem?.title ?? entry.path, 92)}`,
      );
    });
    return items.slice(0, 6);
  }, [selectedWorkspaceId, workspaceChronicleEntries, workspacePmRecommendations, workspaceStandupPreps]);

  const linkedinSummary = useMemo(
    () => [
      {
        label: 'Snapshot',
        value: workspaceSnapshotState === 'live' ? 'Live' : workspaceSnapshotState === 'loading' ? 'Loading' : 'Error',
        detail: workspaceSnapshotState === 'error' ? workspaceSnapshotError ?? 'Snapshot unavailable' : 'shared feed + pipeline state',
      },
      {
        label: 'Feed Items',
        value: String(socialFeed?.items?.length ?? 0),
        detail: socialFeed?.generated_at ? `updated ${formatTimestamp(new Date(socialFeed.generated_at))}` : 'shared source stream',
      },
      {
        label: 'Post Seeds',
        value: String(reactionQueue?.counts?.post_seeds ?? 0),
        detail: 'save-for-post angles',
      },
      {
        label: 'Feedback',
        value: String(feedbackSummary?.total_events ?? 0),
        detail: 'workspace training events',
      },
    ],
    [feedbackSummary?.total_events, reactionQueue?.counts?.post_seeds, socialFeed?.generated_at, socialFeed?.items?.length, workspaceSnapshotError, workspaceSnapshotState],
  );

  void sourceAssets;
  void personaReviewSummary;
  void longFormRoutes;
  void workspaceRefreshStatus;
  void onReloadLiveSnapshot;

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workspaces</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>Workspace Hub</h2>
        <p style={{ color: '#94a3b8', maxWidth: '820px' }}>
          Each workspace keeps its own operating system, agent, and execution lane. The frontend now reflects the backend state directly: live workspaces stay rich, standing-up workspaces show their actual artifacts, and planned slots stay clearly empty.
        </p>
      </div>

      <section
        style={{
          borderRadius: '22px',
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(17,24,39,0.94), rgba(8,12,24,0.98))',
          border: '1px solid rgba(56,189,248,0.16)',
          boxShadow: '0 26px 72px rgba(0,0,0,0.35)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', marginBottom: '18px' }}>
          <div>
            <p style={{ color: activeWorkspace.accent, letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Selected Workspace</p>
            <h3 style={{ fontSize: '30px', color: 'white', margin: '4px 0' }}>{activeWorkspace.label}</h3>
            <p style={{ color: '#cbd5f5', maxWidth: '760px', fontSize: '14px', lineHeight: 1.6 }}>{activeWorkspace.description}</p>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <button
              onClick={() => setSelectorOpen((current) => !current)}
              style={{
                borderRadius: '12px',
                border: `1px solid ${activeWorkspace.accent}`,
                backgroundColor: `${activeWorkspace.accent}18`,
                color: 'white',
                padding: '10px 14px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {selectorOpen ? 'Hide selector' : 'Choose workspace'}
            </button>
            {activeWorkspace.route && (
              <Link
                href={activeWorkspace.route}
                style={{
                  borderRadius: '12px',
                  border: '1px solid rgba(251,146,60,0.55)',
                  backgroundColor: 'rgba(251,146,60,0.12)',
                  color: '#fed7aa',
                  padding: '10px 14px',
                  fontSize: '13px',
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
              >
                Open full workspace
              </Link>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '18px' }}>
          <MiniMeta label="Workspace" value={activeWorkspace.shortLabel} detail={activeWorkspace.agent} />
          <MiniMeta label="Status" value={workspaceLifecycleLabel(activeWorkspace.status)} detail={workspaceLifecycleDetail(activeWorkspace.status)} />
          <MiniMeta label="Operating Rules" value={`${activeWorkspace.operatingPrinciples.length}`} detail="separate principles per workspace" />
          {selectedWorkspaceId === 'linkedin-os' && (
            <>
              <MiniMeta label="Recommendations" value={`${plan?.recommendations?.length ?? 0}`} detail="live weekly plan candidates" />
              <MiniMeta label="Comments" value={`${reactionQueue?.counts?.comment_opportunities ?? 0}`} detail="reaction queue opportunities" />
              <MiniMeta label="Signals" value={`${socialFeed?.items?.length ?? 0}`} detail="shared feed cards" />
            </>
          )}
          {selectedWorkspaceId !== 'linkedin-os' && (
            <>
              <MiniMeta label="Workspace Files" value={`${workspaceFiles.length}`} detail={`${workspaceFileCounts.docs} docs · ${workspaceFileCounts.briefings} briefings`} />
              <MiniMeta label="Standups" value={`${workspaceStandups.length}`} detail={`${workspaceOpenCards.length} open PM cards`} />
              <MiniMeta label="Execution" value={`${workspaceActiveExecution.length}`} detail={`${workspaceFileCounts.dispatch} dispatch packets captured`} />
            </>
          )}
        </div>

        {selectorOpen && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            {WORKSPACE_HUBS.map((workspace) => {
              const active = workspace.id === selectedWorkspaceId;
              return (
                <button
                  key={workspace.id}
                  onClick={() => setSelectedWorkspaceId(workspace.id)}
                  style={{
                    textAlign: 'left',
                    borderRadius: '16px',
                    border: active ? `1px solid ${workspace.accent}` : '1px solid #1f2937',
                    backgroundColor: active ? `${workspace.accent}12` : '#020617',
                    padding: '16px',
                    cursor: 'pointer',
                    display: 'grid',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start' }}>
                    <div>
                      <p style={{ color: 'white', fontSize: '16px', fontWeight: 700, margin: 0 }}>{workspace.label}</p>
                      <p style={{ color: '#94a3b8', fontSize: '12px', margin: '4px 0 0' }}>{workspace.agent}</p>
                    </div>
                    <span
                      style={{
                        borderRadius: '999px',
                        border: `1px solid ${workspace.accent}66`,
                        backgroundColor: `${workspace.accent}18`,
                        color: workspace.accent,
                        padding: '4px 8px',
                        fontSize: '10px',
                        fontWeight: 700,
                        letterSpacing: '0.08em',
                        textTransform: 'uppercase',
                      }}
                    >
                      {workspaceLifecycleLabel(workspace.status)}
                    </span>
                  </div>
                  <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{workspace.description}</p>
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {workspace.operatingPrinciples.map((principle) => (
                      <p key={principle} style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>
                        • {principle}
                      </p>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {selectedWorkspaceId === 'linkedin-os' ? (
        <section style={{ display: 'grid', gap: '16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px' }}>
            {linkedinSummary.map((item) => (
              <MiniMeta key={item.label} label={item.label} value={item.value} detail={item.detail} />
            ))}
          </div>
          <Suspense fallback={<section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', color: '#94a3b8' }}>Loading FEEZIE OS workspace…</section>}>
            <LinkedinWorkspaceSurface embedded />
          </Suspense>
        </section>
      ) : (
        <WorkspaceActivitySurface
          workspace={activeWorkspace}
          summaryCards={workspaceSummaryCards}
          activityCopy={workspaceActivityCopy}
          sidebarFiles={sidebarWorkspaceFiles}
          selectedFile={selectedWorkspaceFile}
          onSelect={onSelect}
          workspaceStandupItems={workspaceStandupItems}
          workspacePmItems={workspacePmItems}
          workspaceExecutionItems={workspaceExecutionItems}
          workspaceRoutingItems={workspaceRoutingItems}
          hasActivity={workspaceHasActivity}
        />
      )}
    </section>
  );
}

function WorkspaceActivitySurface({
  workspace,
  summaryCards,
  activityCopy,
  sidebarFiles,
  selectedFile,
  onSelect,
  workspaceStandupItems,
  workspacePmItems,
  workspaceExecutionItems,
  workspaceRoutingItems,
  hasActivity,
}: {
  workspace: (typeof WORKSPACE_HUBS)[number];
  summaryCards: Array<{ label: string; value: string; detail: string }>;
  activityCopy: string;
  sidebarFiles: WorkspaceFile[];
  selectedFile: WorkspaceFile | null;
  onSelect: (path: string) => void;
  workspaceStandupItems: string[];
  workspacePmItems: string[];
  workspaceExecutionItems: string[];
  workspaceRoutingItems: string[];
  hasActivity: boolean;
}) {
  return (
    <section
      style={{
        borderRadius: '18px',
        border: '1px solid #1f2937',
        backgroundColor: '#050b19',
        padding: '24px',
        display: 'grid',
        gap: '18px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: workspace.accent, letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workspace Activity</p>
          <h3 style={{ fontSize: '26px', color: 'white', margin: '4px 0' }}>{workspace.label}</h3>
          <p style={{ color: '#94a3b8', maxWidth: '760px', lineHeight: 1.6 }}>{activityCopy}</p>
        </div>
        <div style={{ alignSelf: 'flex-start' }}>{statusBadge(workspace.status)}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
        {summaryCards.map((item) => (
          <MiniMeta key={`${workspace.id}-${item.label}`} label={item.label} value={item.value} detail={item.detail} />
        ))}
      </div>

      {sidebarFiles.length > 0 ? (
        <SplitPane
          sidebar={
            <div style={{ display: 'grid', gap: '10px' }}>
              <div>
                <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '6px' }}>Workspace Files</p>
                <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.6, margin: 0 }}>
                  Prioritized docs, standups, analytics, and memory artifacts for {workspace.label}. Dispatch packets are counted above but deprioritized here so the sidebar stays readable.
                </p>
              </div>
              <div style={{ display: 'grid', gap: '8px' }}>
                {sidebarFiles.map((file) => {
                  const active = selectedFile?.path === file.path;
                  const section = workspaceFileSection(file, workspace.id);
                  return (
                    <button
                      key={file.path}
                      onClick={() => onSelect(file.path)}
                      style={{
                        textAlign: 'left',
                        borderRadius: '14px',
                        border: active ? `1px solid ${workspace.accent}` : '1px solid #1f2937',
                        backgroundColor: active ? `${workspace.accent}14` : '#020617',
                        padding: '12px',
                        cursor: 'pointer',
                        display: 'grid',
                        gap: '6px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center' }}>
                        <span style={{ color: workspace.accent, fontSize: '10px', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{humanizeStatusLabel(section)}</span>
                        <span style={{ color: '#64748b', fontSize: '11px' }}>{formatTimestamp(new Date(file.updatedAt))}</span>
                      </div>
                      <p style={{ color: 'white', fontSize: '13px', fontWeight: 600, margin: 0 }}>{workspaceRelativeFilePath(file.path, workspace.id)}</p>
                      <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{summarize(file.snippet || 'No preview captured.', 96)}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          }
          content={
            selectedFile ? (
              <MarkdownSurface title={selectedFile.name} path={selectedFile.path} updatedAt={selectedFile.updatedAt} content={selectedFile.content} />
            ) : (
              <EmptyPanel message="Select a workspace file to inspect." />
            )
          }
        />
      ) : (
        <div style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <EmptyPanel message="No workspace files are visible yet. This section will populate as the backend writes docs, briefs, and memory artifacts into the workspace root." />
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
          <PanelList title="Recent Standups" items={workspaceStandupItems} emptyLabel="No standups recorded yet." />
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
          <PanelList title="Open PM Lane" items={workspacePmItems} emptyLabel="No open PM cards in this workspace." />
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
          <PanelList title="Execution Queue" items={workspaceExecutionItems} emptyLabel="No active execution queue entries." />
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
          <PanelList title="Routing + Prep" items={workspaceRoutingItems} emptyLabel="No routed Chronicle or prep artifacts yet." />
        </div>
      </div>

      {!hasActivity && (
        <div style={{ borderRadius: '14px', border: '1px dashed rgba(148,163,184,0.22)', padding: '16px', color: '#94a3b8', lineHeight: 1.6 }}>
          The workspace definition, agent, and principles remain visible even before artifacts exist, but the empty-state copy is now explicit instead of implying the backend has no workspace lane.
        </div>
      )}
    </section>
  );
}

function WorkspacePanel({
  files,
  selected,
  onSelect,
  plan,
  reactionQueue,
  socialFeed,
  sourceAssets,
  personaReviewSummary,
  longFormRoutes,
  workspaceSnapshotState,
  workspaceSnapshotError,
  workspaceRefreshStatus,
  feedbackSummary,
  onReloadLiveSnapshot,
}: {
  files: WorkspaceFile[];
  selected: WorkspaceFile | null;
  onSelect: (path: string) => void;
  plan: WeeklyPlan | null;
  reactionQueue: ReactionQueue | null;
  socialFeed: SocialFeed | null;
  sourceAssets: SourceAssetInventory | null;
  personaReviewSummary: PersonaReviewSummary | null;
  longFormRoutes: LongFormRouteSummary | null;
  workspaceSnapshotState: 'loading' | 'live' | 'error';
  workspaceSnapshotError: string | null;
  workspaceRefreshStatus: FeedRefreshStatus | null;
  feedbackSummary: FeedbackSummary | null;
  onReloadLiveSnapshot: () => Promise<void>;
}) {
  const linkedinFiles = useMemo(
    () => files.filter((file) => file.path.includes('/workspaces/linkedin-content-os/') || file.group.startsWith('linkedin-content-os')),
    [files],
  );
  const selectedLinkedin = useMemo(
    () => linkedinFiles.find((file) => file.path === selected?.path) ?? linkedinFiles[0] ?? null,
    [linkedinFiles, selected],
  );
  const groups = useMemo(() => {
    const map = new Map<string, WorkspaceFile[]>();
    linkedinFiles.forEach((file) => {
      const bucket = map.get(file.group) ?? [];
      bucket.push(file);
      map.set(file.group, bucket);
    });
    return Array.from(map.entries());
  }, [linkedinFiles]);
  const workflowDoc = useMemo(() => findWorkspaceFile(linkedinFiles, 'docs/linkedin_curation_workflow.md'), [linkedinFiles]);
  const backlogDoc = useMemo(() => findWorkspaceFile(linkedinFiles, 'backlog.md'), [linkedinFiles]);
  const editorialMixDoc = useMemo(() => findWorkspaceFile(linkedinFiles, 'docs/editorial_mix.md'), [linkedinFiles]);
  const workflowSteps = useMemo(() => (workflowDoc ? parseSubsections(extractSection(workflowDoc.content, 'Core Workflow')) : []), [workflowDoc]);
  const saveRules = useMemo(() => (workflowDoc ? collectSaveRules(workflowDoc.content) : { keep: [], drop: [] }), [workflowDoc]);
  const backlogActive = useMemo(() => (backlogDoc ? parseSubsections(extractSection(backlogDoc.content, 'Active')) : []), [backlogDoc]);
  const editorialMix = useMemo(
    () => (editorialMixDoc ? parseBullets(extractSection(editorialMixDoc.content, 'Starting Mix Hypothesis')) : []),
    [editorialMixDoc],
  );
  const draftFiles = useMemo(
    () => linkedinFiles.filter((file) => file.path.includes('/drafts/') && file.path.endsWith('.md') && !file.path.endsWith('/README.md')),
    [linkedinFiles],
  );
  const docFiles = useMemo(
    () => linkedinFiles.filter((file) => file.path.includes('/docs/') && file.path.endsWith('.md') && !file.path.endsWith('/README.md')),
    [linkedinFiles],
  );
  const [activeLens, setActiveLens] = useState<WorkspaceLensId>('all');
  const sourceAssetRecords = useMemo<SourceAssetRecord[]>(
    () =>
      (sourceAssets?.items ?? []).map((asset) => ({
        assetId: asset.asset_id,
        title: asset.title,
        sourcePath: asset.source_path,
        sourceChannel: asset.source_channel,
        sourceType: asset.source_type,
        sourceClass: asset.source_class,
        summary: asset.summary ?? '',
        responseModes: asset.response_modes ?? [],
        routingStatus: asset.routing_status,
        sourceUrl: asset.source_url,
        wordCount: asset.word_count ?? null,
        capturedAt: asset.captured_at,
        origin: asset.origin,
        tags: asset.tags ?? [],
        topics: asset.topics ?? [],
      })),
    [sourceAssets],
  );
  const personaReviewCounts = personaReviewSummary?.counts ?? {};
  const personaRelationCounts = personaReviewSummary?.belief_relation_counts ?? {};
  const longFormSync = personaReviewSummary?.long_form_sync ?? null;
  const longFormRouteCounts = longFormRoutes?.route_counts ?? {};
  const longFormPrimaryRouteCounts = longFormRoutes?.primary_route_counts ?? {};
  const sourceRecords = useMemo(() => {
    const byPath = new Map<string, SourceRecord>();

    (reactionQueue?.comment_opportunities ?? []).forEach((item) => {
      byPath.set(item.source_path, {
        title: item.title,
        sourcePath: item.source_path,
        priorityLane: item.priority_lane,
        roleAlignment: item.role_alignment,
        summary: item.summary,
        author: item.author,
        sourcePlatform: item.source_platform,
        sourceType: item.source_type,
        sourceUrl: item.source_url,
        hook: item.hook,
      });
    });

    (plan?.market_signals ?? []).forEach((item) => {
      const existing = byPath.get(item.source_path);
      byPath.set(item.source_path, {
        title: item.title,
        sourcePath: item.source_path,
        priorityLane: item.priority_lane,
        roleAlignment: item.role_alignment,
        summary: item.summary,
        author: existing?.author,
        sourcePlatform: existing?.sourcePlatform,
        sourceType: existing?.sourceType,
        sourceUrl: existing?.sourceUrl,
        hook: existing?.hook,
      });
    });

    return Array.from(byPath.values());
  }, [plan?.market_signals, reactionQueue?.comment_opportunities]);
  const lensCounts = useMemo(
    () =>
      WORKSPACE_LENSES.map((lens) => ({
        id: lens.id,
        count:
          (plan?.recommendations ?? []).filter((item) => matchesWorkspaceLens(lens.id, item)).length +
          (plan?.media_post_seeds ?? []).filter((item) => matchesWorkspaceLens(lens.id, item)).length +
          (reactionQueue?.comment_opportunities ?? []).filter((item) => matchesWorkspaceLens(lens.id, item)).length +
          sourceRecords.filter((item) => matchesWorkspaceLens(lens.id, item)).length,
      })),
    [plan?.media_post_seeds, plan?.recommendations, reactionQueue?.comment_opportunities, sourceRecords],
  );
  const filteredRecommendations = useMemo(
    () => (plan?.recommendations ?? []).filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, plan?.recommendations],
  );
  const filteredMediaPostSeeds = useMemo(
    () => (plan?.media_post_seeds ?? []).filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, plan?.media_post_seeds],
  );
  const filteredSignals = useMemo(
    () => sourceRecords.filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, sourceRecords],
  );
  const filteredCommentOpportunities = useMemo(
    () => (reactionQueue?.comment_opportunities ?? []).filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, reactionQueue?.comment_opportunities],
  );
  const filteredPostSeeds = useMemo(
    () => (reactionQueue?.post_seeds ?? []).filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, reactionQueue?.post_seeds],
  );
  const activeLensMeta = WORKSPACE_LENSES.find((lens) => lens.id === activeLens) ?? WORKSPACE_LENSES[0];
  const [postMode, setPostMode] = useState<FeedLensId>('current-role');
  const [selectedRecommendation, setSelectedRecommendation] = useState<PlanCandidate | null>(null);
  const [postDraft, setPostDraft] = useState('');
  const currentSourceRecord = useMemo(
    () => (selectedRecommendation ? sourceRecords.find((record) => record.sourcePath === selectedRecommendation.source_path) : undefined),
    [selectedRecommendation, sourceRecords],
  );
  const [manualFeedItems, setManualFeedItems] = useState<SocialFeedItem[]>([]);
  const feedItems = useMemo(() => socialFeed?.items ?? [], [socialFeed]);
  const visibleFeedItems = useMemo(() => [...manualFeedItems, ...feedItems], [feedItems, manualFeedItems]);
  const tuningDashboard = useMemo(() => buildTuningDashboard(visibleFeedItems), [visibleFeedItems]);
  const [refreshingFeed, setRefreshingFeed] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [ingestUrl, setIngestUrl] = useState('');
  const [ingestText, setIngestText] = useState('');
  const [ingestTitle, setIngestTitle] = useState('');
  const [ingestPriority, setIngestPriority] = useState<FeedLensId>('current-role');
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);
  const [ingestLoading, setIngestLoading] = useState(false);
  const [quoteStatus, setQuoteStatus] = useState<string | null>(null);
  const [isApprovingQuote, setIsApprovingQuote] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [feedbackState, setFeedbackState] = useState<Record<string, string>>({});
  const [feedbackLoading, setFeedbackLoading] = useState<Record<string, boolean>>({});
  const [feedLensSelections, setFeedLensSelections] = useState<Record<string, FeedLensId>>({});
  const normalizeFeedLens = useCallback((value?: string | null): FeedLensId | null => {
    if (!value) {
      return null;
    }
    const normalized = value.trim().toLowerCase();
    return FEED_LENS_ALIASES[normalized] ?? null;
  }, []);
  const getFeedVariant = useCallback(
    (item: SocialFeedItem, lens: FeedLensId) => {
      for (const key of FEED_LENS_VARIANT_KEYS[lens]) {
        const variant = item.lens_variants?.[key];
        if (variant) {
          return variant;
        }
      }
      return null;
    },
    [],
  );
  const resolveFeedLens = useCallback(
    (item: SocialFeedItem): FeedLensId => {
      const selected = feedLensSelections[item.id];
      if (selected) {
        return selected;
      }
      for (const lens of item.lenses ?? []) {
        const normalized = normalizeFeedLens(lens);
        if (normalized) {
          return normalized;
        }
      }
      return postMode;
    },
    [feedLensSelections, normalizeFeedLens, postMode],
  );
  const createCommentDraft = useCallback(
    (item: SocialFeedItem, lens: FeedLensId) => {
      const variant = getFeedVariant(item, lens);
      if (variant?.comment) {
        return variant.comment.trim();
      }
      return `${POST_MODE_OPTIONS.find((mode) => mode.id === lens)?.label ?? 'Comment'} angle: ${item.comment_draft ?? item.summary ?? ''}`.trim();
    },
    [getFeedVariant],
  );
  const createShortCommentDraft = useCallback(
    (item: SocialFeedItem, lens: FeedLensId) => {
      const variant = getFeedVariant(item, lens);
      if (variant?.short_comment) {
        return variant.short_comment.trim();
      }
      return `${POST_MODE_OPTIONS.find((mode) => mode.id === lens)?.label ?? 'Quick'} take.`.trim();
    },
    [getFeedVariant],
  );
  const createRepostDraft = useCallback((item: SocialFeedItem, lens: FeedLensId) => {
    const variant = getFeedVariant(item, lens);
    if (variant?.repost) {
      return variant.repost.trim();
    }
    return `${item.repost_draft ?? item.summary ?? ''}`.trim();
  }, [getFeedVariant]);
  const splitIntoSentences = useCallback((text: string) => {
    return text
      .replace(/\s+/g, ' ')
      .trim()
      .split(/(?<=[.!?])\s+/)
      .map((part) => part.trim())
      .filter(Boolean);
  }, []);
  const shortenToSentenceCount = useCallback((text: string, sentenceCount: number) => {
    const sentences = splitIntoSentences(text);
    if (sentences.length === 0) {
      return '';
    }
    return sentences.slice(0, sentenceCount).join(' ').trim();
  }, [splitIntoSentences]);
  const sanitizeFeedDraft = useCallback((text: string, title?: string) => {
    const normalizedTitle = title?.trim().toLowerCase() ?? '';
    const sentences = splitIntoSentences(text).filter((sentence) => {
      const normalized = sentence.replace(/[.!?]+$/, '').trim().toLowerCase();
      if (!normalized) {
        return false;
      }
      if (normalizedTitle && normalized === normalizedTitle) {
        return false;
      }
      if (/^(belief|anchor|source contract|expression):/i.test(sentence)) {
        return false;
      }
      if (/^(fusion academy market development|ai clone \/ brain system|easy outfit metadata and validation layer)\b/i.test(sentence)) {
        return false;
      }
      return true;
    });
    return sentences.join(' ').trim();
  }, [splitIntoSentences]);
  const scoreBand = useCallback((value?: number | null, mediumFloor = 6.5, highFloor = 8) => {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return 'medium';
    }
    if (value >= highFloor) {
      return 'high';
    }
    if (value >= mediumFloor) {
      return 'medium';
    }
    return 'low';
  }, []);
  const looksBroadConversation = useCallback((item: SocialFeedItem, sourceClass: string, unitKind: string) => {
    const title = item.title.toLowerCase();
    const commaCount = (item.title.match(/,/g) ?? []).length;
    return sourceClass === 'long_form_media' || unitKind === 'section' || commaCount >= 2 || title.includes('podcast') || title.includes('show:') || title.includes(' + ');
  }, []);
  const buildFeedEditorialSummary = useCallback((item: SocialFeedItem, lens: FeedLensId): FeedEditorialSummary => {
    const variant = getFeedVariant(item, lens);
    const evaluation = variant?.evaluation ?? item.evaluation;
    const sourceClass = item.source_class ?? deriveSourceClass(item);
    const unitKind = item.unit_kind ?? deriveUnitKind(item, sourceClass);
    const responseModes = item.response_modes ?? deriveResponseModes(item, sourceClass, unitKind);
    const quickReply = sanitizeFeedDraft(createShortCommentDraft(item, lens), item.title);
    const commentDraft = sanitizeFeedDraft(createCommentDraft(item, lens), item.title);
    const repostDraft = sanitizeFeedDraft(createRepostDraft(item, lens), item.title);
    const broadConversation = looksBroadConversation(item, sourceClass, unitKind);
    const sourceSpecificity = evaluation?.source_expression_quality ?? null;
    const specificityRisk =
      broadConversation || (typeof sourceSpecificity === 'number' && sourceSpecificity < 6.8)
        ? 'high'
        : typeof sourceSpecificity === 'number' && sourceSpecificity < 7.5
          ? 'medium'
          : 'low';
    const commentAllowed = responseModes.includes('comment') && Boolean(commentDraft);
    const repostAllowed = responseModes.includes('repost') && Boolean(repostDraft);
    const postSeedAllowed = responseModes.includes('post_seed');

    let mode: FeedRecommendationMode = 'comment';
    if (postSeedAllowed && (broadConversation || specificityRisk === 'high' || !commentAllowed)) {
      mode = 'post_seed';
    } else if (commentAllowed && typeof sourceSpecificity === 'number' && sourceSpecificity >= 7.2) {
      mode = 'comment';
    } else if (repostAllowed) {
      mode = 'repost';
    } else if (commentAllowed) {
      mode = 'comment';
    } else if (postSeedAllowed) {
      mode = 'post_seed';
    }

    const laneFit = scoreBand(evaluation?.lane_distinctiveness, 6.7, 8.2);
    const voiceFit = scoreBand(evaluation?.voice_match, 6.7, 8.2);
    const bestAngle = shortenToSentenceCount(
      quickReply || item.standout_lines?.[0] || variant?.why_this_angle || item.summary || item.why_it_matters || 'No clear angle yet.',
      1,
    );

    if (mode === 'post_seed') {
      const draft = shortenToSentenceCount(repostDraft || commentDraft || quickReply || item.summary || item.why_it_matters || '', 4);
      const optionalDraft = shortenToSentenceCount(quickReply || commentDraft, 1);
      return {
        mode,
        recommendation: 'Save as post seed, not a direct comment.',
        why: [
          broadConversation
            ? 'Broad conversation with multiple threads, so a direct reaction is likely to read generic.'
            : 'The source is useful, but not specific enough to earn a source-native comment.',
          'You have a better shot extracting a builder lesson than pretending to respond to every topic in the source.',
        ],
        bestAngle,
        draft: draft || bestAngle,
        draftTone: '#fb923c',
        optionalLabel: optionalDraft && optionalDraft !== draft ? 'Optional quick take' : undefined,
        optionalDraft: optionalDraft && optionalDraft !== draft ? optionalDraft : undefined,
        laneFit,
        voiceFit,
        specificityRisk,
        bestUse: 'original post seed',
        avoid: 'generic contrarian comment',
      };
    }

    if (mode === 'repost') {
      const draft = shortenToSentenceCount(repostDraft || commentDraft || quickReply || item.summary || '', 4);
      const optionalDraft = shortenToSentenceCount(commentDraft || quickReply, 2);
      return {
        mode,
        recommendation: 'Use as repost angle, not a direct reply.',
        why: [
          'There is enough signal here to echo and reframe, but not enough source specificity for a strong direct comment.',
          'Your value is the operator framing you add on top of the source, not acting like the source itself is your lane.',
        ],
        bestAngle,
        draft: draft || bestAngle,
        draftTone: '#f472b6',
        optionalLabel: optionalDraft && optionalDraft !== draft ? 'Optional direct reply' : undefined,
        optionalDraft: optionalDraft && optionalDraft !== draft ? optionalDraft : undefined,
        laneFit,
        voiceFit,
        specificityRisk,
        bestUse: 'repost with commentary',
        avoid: 'over-claiming source-level specificity',
      };
    }

    const draft = shortenToSentenceCount(commentDraft || quickReply || repostDraft || item.summary || '', 4);
    const optionalDraft = shortenToSentenceCount(repostDraft || quickReply, 2);
    return {
      mode: 'comment',
      recommendation: 'Comment directly.',
      why: [
        'This is specific enough to answer without sounding detached from the source.',
        'The current angle has enough lane and voice fit to say something useful in public.',
      ],
      bestAngle,
      draft: draft || bestAngle,
      draftTone: '#38bdf8',
      optionalLabel: optionalDraft && optionalDraft !== draft ? 'Optional repost angle' : undefined,
      optionalDraft: optionalDraft && optionalDraft !== draft ? optionalDraft : undefined,
      laneFit,
      voiceFit,
      specificityRisk,
      bestUse: 'direct public comment',
      avoid: 'turning this into a broad manifesto',
    };
  }, [
    createCommentDraft,
    createRepostDraft,
    createShortCommentDraft,
    getFeedVariant,
    looksBroadConversation,
    sanitizeFeedDraft,
    scoreBand,
    shortenToSentenceCount,
  ]);
  const copyToClipboard = useCallback(async (
    text: string,
    label: string,
    feedbackContext?: { item: SocialFeedItem; lens: FeedLensId; variant: FeedVariant | null },
  ) => {
    if (!text) return;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      setCopyStatus(`${label} copied!`);
      if (feedbackContext) {
        const { item, lens, variant } = feedbackContext;
        const payload = {
          feed_item_id: item.id,
          title: item.title,
          platform: item.platform,
          decision: 'copy',
          lens,
          source_url: item.source_url,
          source_path: item.source_path,
          stance: variant?.stance,
          belief_used: variant?.belief_used,
          experience_anchor: variant?.experience_anchor,
          techniques: variant?.techniques ?? [],
          evaluation_overall: variant?.evaluation?.overall,
          source_expression_quality: variant?.evaluation?.source_expression_quality,
          output_expression_quality: variant?.evaluation?.output_expression_quality,
          expression_delta: variant?.evaluation?.expression_delta,
          why_this_angle: variant?.why_this_angle,
          notes: label,
        };
        fetch(`${API_URL}/api/workspace/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }).catch(() => null);
      }
      setTimeout(() => setCopyStatus(null), 1500);
    }
  }, []);
  const waitForFeedRefresh = useCallback(async () => {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const status = await fetchJson<FeedRefreshStatus>(`${API_URL}/api/workspace/refresh-social-feed`);
      if (!status.running) {
        if (status.error) {
          throw new Error(status.error);
        }
        return status;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw new Error('Feed refresh timed out before the live snapshot updated.');
  }, []);
  const refreshSocialFeed = useCallback(async () => {
    setRefreshingFeed(true);
    setRefreshStatus('Refreshing social feed...');
    try {
      const res = await fetch(`${API_URL}/api/workspace/refresh-social-feed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skip_fetch: false, sources: 'safe' }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || 'Unable to queue feed refresh.');
      }
      const data = await res.json();
      setRefreshStatus(`Refresh queued${data.started_at ? ` at ${formatUiTime(data.started_at)}` : ''}`);
      const finalStatus = await waitForFeedRefresh();
      await onReloadLiveSnapshot();
      setRefreshStatus(
        `Feed updated${finalStatus.last_run ? ` at ${formatUiTime(finalStatus.last_run)}` : ''}`,
      );
    } catch (error) {
      setRefreshStatus(error instanceof Error ? error.message : 'Refresh failed.');
    } finally {
      setRefreshingFeed(false);
      setTimeout(() => setRefreshStatus(null), 4500);
    }
  }, [onReloadLiveSnapshot, waitForFeedRefresh]);
  const ingestSignal = useCallback(async () => {
    if (!ingestUrl && !ingestText) {
      setIngestStatus('Provide a link or some text.');
      return;
    }
    setIngestLoading(true);
    setIngestStatus('Starting signal ingestion...');
    try {
      const payload = {
        priority_lane: ingestPriority,
        url: ingestUrl || undefined,
        text: ingestText || undefined,
        title: ingestTitle || undefined,
        run_refresh: true,
      };
      const res = await fetch(`${API_URL}/api/workspace/ingest-signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || 'Ingest failed.');
      }
      const data = await res.json();
      if (data?.preview_item) {
        const previewItem = data.preview_item as SocialFeedItem;
        setManualFeedItems((current: SocialFeedItem[]) => [previewItem, ...current].slice(0, 5));
        const initialLens = normalizeFeedLens(previewItem.lenses?.[0]) ?? ingestPriority;
        setFeedLensSelections((current) => ({ ...current, [previewItem.id]: initialLens }));
      }
      setIngestStatus('Preview generated at the top of the feed.');
      setIngestUrl('');
      setIngestText('');
      setIngestTitle('');
    } catch (error) {
      setIngestStatus(error instanceof Error ? error.message : 'Ingest failed.');
    } finally {
      setIngestLoading(false);
      setTimeout(() => setIngestStatus(null), 4000);
    }
  }, [ingestPriority, ingestUrl, ingestText, ingestTitle, normalizeFeedLens]);
  const approveFeedLine = useCallback(
    async (item: SocialFeedItem, line: string) => {
      const lens = resolveFeedLens(item);
      setQuoteStatus('Approving quote...');
      setIsApprovingQuote(true);
      try {
        const payload = {
          persona_target: 'feeze.core',
          trait: `LinkedIn quote (${item.author})`,
          notes: `${line.trim()}`,
          metadata: {
            target_file: 'identity/VOICE_PATTERNS.md',
            review_source: 'linkedin_workspace.feed_quote',
            approval_state: 'pending_workspace_approval',
            platform: item.platform,
            author: item.author,
            source_url: item.source_url,
            source_path: item.source_path,
            selected_line: line.trim(),
            workspace: 'linkedin-content-os',
            lens,
          },
        };
        const createRes = await fetch(`${API_URL}/api/persona/deltas`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!createRes.ok) {
          const detail = await createRes.text();
          throw new Error(detail || 'Unable to create persona delta.');
        }
        const delta = await createRes.json();
        const patchRes = await fetch(`${API_URL}/api/persona/deltas/${delta.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status: 'approved',
            metadata: {
              approval_state: 'approved_from_workspace',
              last_reviewed_at: new Date().toISOString(),
              review_source: 'linkedin_workspace.feed_quote',
            },
          }),
        });
        if (!patchRes.ok) {
          const detail = await patchRes.text();
          throw new Error(detail || 'Unable to finalize persona delta.');
        }
        setQuoteStatus(`Approved quote "${line.slice(0, 40)}..."`);
      } catch (error) {
        setQuoteStatus(error instanceof Error ? error.message : 'Unable to approve quote right now.');
      } finally {
        setIsApprovingQuote(false);
      }
    },
    [resolveFeedLens],
  );
  const recordFeedback = useCallback(
    async (item: SocialFeedItem, decision: 'like' | 'dislike') => {
      const lens = resolveFeedLens(item);
      const variant = getFeedVariant(item, lens);
      setFeedbackLoading((current) => ({ ...current, [item.id]: true }));
      const label = decision === 'like' ? 'Liked' : 'Disliked';
      try {
        const payload = {
          feed_item_id: item.id,
          title: item.title,
          platform: item.platform,
          decision,
          lens,
          source_url: item.source_url,
          source_path: item.source_path,
          stance: variant?.stance,
          belief_used: variant?.belief_used,
          experience_anchor: variant?.experience_anchor,
          techniques: variant?.techniques ?? [],
          evaluation_overall: variant?.evaluation?.overall,
          source_expression_quality: variant?.evaluation?.source_expression_quality,
          output_expression_quality: variant?.evaluation?.output_expression_quality,
          expression_delta: variant?.evaluation?.expression_delta,
          why_this_angle: variant?.why_this_angle,
        };
        const res = await fetch(`${API_URL}/api/workspace/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const detail = await res.text();
          throw new Error(detail || 'Unable to save preference.');
        }
        setFeedbackState((current) => ({ ...current, [item.id]: `${label}` }));
      } catch (error) {
        setFeedbackState((current) => ({
          ...current,
          [item.id]: error instanceof Error ? error.message : 'Feedback failed.',
        }));
      } finally {
        setFeedbackLoading((current) => ({ ...current, [item.id]: false }));
      }
    },
    [getFeedVariant, resolveFeedLens],
  );

  useEffect(() => {
    if (!selectedRecommendation) {
      setPostDraft('');
      return;
    }
    setPostDraft(generatePostDraft(selectedRecommendation, postMode));
  }, [selectedRecommendation, postMode]);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workspace</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>FEEZIE Strategy Workspace</h2>
        <p style={{ color: '#94a3b8' }}>The Workspace tab now carries the FEEZIE OS strategy surface directly: positioning, weekly plan, reaction queue, and the raw workspace files underneath.</p>
      </div>
      <section
        style={{
          borderRadius: '22px',
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(35,12,56,0.95), rgba(9,7,22,0.98))',
          border: '1px solid rgba(217,70,239,0.22)',
          boxShadow: '0 26px 72px rgba(0,0,0,0.35)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', marginBottom: '18px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>FEEZIE OS</p>
            <h3 style={{ fontSize: '30px', color: 'white', margin: '4px 0' }}>Strategy mission control</h3>
            <p style={{ color: '#d8b4fe', maxWidth: '760px', fontSize: '14px' }}>
              Persona truth, signal capture, weekly recommendations, and engagement moves for `linkedin-content-os` now live inside Workspaces instead of on a separate page.
            </p>
          </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(140px, 1fr))', gap: '12px' }}>
          <MiniMeta label="Plan Refreshed" value={plan?.generated_at ?? '-'} detail="weekly_plan snapshot" />
          <MiniMeta label="Reaction Queue" value={reactionQueue?.generated_at ?? '-'} detail="reaction_queue snapshot" />
          <MiniMeta label="Draft Queue" value={`${draftFiles.length || plan?.source_counts.drafts || 0}`} detail="Ready or in progress" />
          <MiniMeta label="Signals" value={`${plan?.market_signals.length ?? 0}`} detail="Captured market signals" />
          <MiniMeta label="Media Seeds" value={`${plan?.source_counts.media ?? 0}`} detail="Routed long-form post seeds" />
          <MiniMeta label="Belief Evidence" value={`${plan?.source_counts.belief_evidence ?? 0}`} detail="Planner-visible worldview units" />
        </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '18px' }}>
          <MiniMeta
            label="Snapshot Source"
            value={
              workspaceSnapshotState === 'live'
                ? 'Persisted backend'
                : workspaceSnapshotState === 'loading'
                  ? 'Loading'
                  : 'Snapshot error'
            }
            detail={
              workspaceSnapshotState === 'live'
                ? 'postgres-backed workspace state'
                : workspaceSnapshotState === 'loading'
                  ? 'fetching live workspace snapshot'
                  : 'live workspace snapshot unavailable'
            }
          />
          <MiniMeta
            label="Feed Refresh"
            value={workspaceRefreshStatus?.last_run ?? workspaceRefreshStatus?.started_at ?? '-'}
            detail={workspaceRefreshStatus?.running ? 'refresh job running' : workspaceRefreshStatus?.error ? 'refresh reported an error' : 'last backend refresh'}
          />
          <MiniMeta
            label="Feedback Events"
            value={`${feedbackSummary?.total_events ?? 0}`}
            detail="logged copy/like/dislike/approve events"
          />
          <MiniMeta
            label="Avg Eval"
            value={feedbackSummary?.average_evaluation_overall ? feedbackSummary.average_evaluation_overall.toFixed(1) : '-'}
            detail="recent recorded output quality"
          />
          <MiniMeta
            label="Media Assets"
            value={`${sourceAssets?.counts?.total ?? sourceAssetRecords.length}`}
            detail="upstream long-form assets"
          />
          <MiniMeta
            label="Pending Segments"
            value={`${sourceAssets?.counts?.pending_segmentation ?? sourceAssetRecords.filter((item) => item.routingStatus === 'pending_segmentation').length}`}
            detail="not yet routed into feed cards"
          />
          <MiniMeta
            label="Route Candidates"
            value={`${longFormRoutes?.segments_total ?? 0}`}
            detail="claim-sized long-form units"
          />
        </div>
        <section
          style={{
            borderRadius: '16px',
            border: '1px solid rgba(148,163,184,0.2)',
            backgroundColor: 'rgba(2,6,23,0.72)',
            padding: '16px',
            marginBottom: '18px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
            <div>
              <p style={{ color: '#c4b5fd', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Persona Review Lifecycle</p>
              <h4 style={{ color: 'white', fontSize: '22px', margin: 0 }}>One shared approval lane</h4>
              <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '6px', maxWidth: '760px' }}>
                Workspace approvals are already saved into the shared persona-delta system. Brain pending items are the ones that still need nuance, context, or promotion judgment.
              </p>
            </div>
            <div style={{ color: '#94a3b8', fontSize: '12px', textAlign: 'right' }}>
              <p>Total persona deltas: {personaReviewCounts.total ?? 0}</p>
              <p>Updated: {personaReviewSummary?.generated_at ?? '-'}</p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '12px' }}>
            <MiniMeta label="Brain Pending" value={`${personaReviewCounts.brain_pending_review ?? 0}`} detail="still needs judgment" />
            <MiniMeta label="Workspace Saved" value={`${personaReviewCounts.workspace_saved ?? 0}`} detail="approved from feed/workspace" />
            <MiniMeta label="Approved Other" value={`${personaReviewCounts.approved_unpromoted ?? 0}`} detail="saved, not yet promoted" />
            <MiniMeta label="Pending Promotion" value={`${personaReviewCounts.pending_promotion ?? 0}`} detail="selected items queued" />
            <MiniMeta label="Promoted" value={`${personaReviewCounts.committed ?? 0}`} detail="committed to persona flow" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '12px' }}>
            <MiniMeta label="Long-Form Assets" value={`${longFormSync?.assets_considered ?? 0}`} detail="checked during latest sync" />
            <MiniMeta label="New Review Items" value={`${longFormSync?.created_count ?? 0}`} detail="created from source assets" />
            <MiniMeta label="Already Synced" value={`${longFormSync?.skipped_existing ?? 0}`} detail="deduped by review key" />
            <MiniMeta label="Stale Cleared" value={`${longFormSync?.resolved_stale ?? 0}`} detail="outdated draft segments resolved" />
            <MiniMeta label="No Segments" value={`${longFormSync?.skipped_no_segments ?? 0}`} detail="no usable worldview unit" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '12px' }}>
            <MiniMeta label="Agreement" value={`${personaRelationCounts.agreement ?? 0}`} detail="tracks existing belief" />
            <MiniMeta label="Qualified" value={`${personaRelationCounts.qualified_agreement ?? 0}`} detail="agrees, with a caveat" />
            <MiniMeta label="Disagreement" value={`${personaRelationCounts.disagreement ?? 0}`} detail="pushes against current framing" />
            <MiniMeta label="Translation" value={`${personaRelationCounts.translation ?? 0}`} detail="maps source into the work" />
            <MiniMeta label="Experience" value={`${personaRelationCounts.experience_match ?? 0}`} detail="supported by lived context" />
            <MiniMeta label="System" value={`${personaRelationCounts.system_translation ?? 0}`} detail="turns an idea into process" />
          </div>
          <div style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '12px' }}>
            <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Recent Persona Items</p>
            {(personaReviewSummary?.recent ?? []).length === 0 ? (
              <EmptyPanel message="No persona review items have been recorded yet." compact />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {(personaReviewSummary?.recent ?? []).slice(0, 6).map((item) => (
                  <div key={item.id} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                      <span style={{ color: 'white', fontWeight: 600, fontSize: '13px' }}>{summarize(item.trait, 72)}</span>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>{item.stage.replace(/_/g, ' ')}</span>
                    </div>
                    <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                      {item.review_source ?? 'unknown'} · {humanizeBeliefRelation(item.belief_relation)} · {item.target_file ?? 'no target file'} · {item.created_at ? formatTimestamp(new Date(item.created_at)) : '-'}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
        {workspaceSnapshotError && <SectionAlert message={`Workspace snapshot error: ${workspaceSnapshotError}`} />}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          {(plan?.positioning_model ?? []).slice(0, 4).map((item) => (
            <div key={item} style={{ borderRadius: '16px', border: '1px solid rgba(192,132,252,0.25)', backgroundColor: 'rgba(17,24,39,0.68)', padding: '14px' }}>
              <p style={{ color: '#f5d0fe', fontSize: '14px', lineHeight: 1.5 }}>{item}</p>
            </div>
          ))}
          {!(plan?.positioning_model?.length) && <EmptyPanel message="No LinkedIn positioning model available yet." />}
        </div>
        {selectedRecommendation && (
          <section
            style={{
              marginTop: '12px',
              borderRadius: '12px',
              border: '1px solid #334155',
              backgroundColor: '#020617',
              padding: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '12px' }}>
              <div>
                <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase' }}>Post Composer</p>
                <h4 style={{ color: 'white', margin: '6px 0' }}>{selectedRecommendation.title}</h4>
              </div>
              <span style={{ color: '#64748b', fontSize: '12px' }}>
                mode: {POST_MODE_OPTIONS.find((mode) => mode.id === postMode)?.label ?? 'Default'}
              </span>
            </div>
            <textarea
              value={postDraft}
              onChange={(event) => setPostDraft(event.target.value)}
              rows={5}
              style={{
                width: '100%',
                borderRadius: '12px',
                border: '1px solid #1f2937',
                background: '#030712',
                color: '#e2e8f0',
                padding: '12px',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '10px' }}>
              <button
                onClick={async () => {
                  if (!postDraft) return;
                  if (typeof navigator !== 'undefined' && navigator.clipboard) {
                    await navigator.clipboard.writeText(postDraft);
                  }
                }}
                style={{
                  borderRadius: '12px',
                  border: postDraft ? '1px solid rgba(255,255,255,0.5)' : '1px solid rgba(255,255,255,0.2)',
                  background: postDraft ? 'rgba(255,255,255,0.06)' : 'transparent',
                  color: '#f8fafc',
                  padding: '8px 14px',
                  cursor: postDraft ? 'pointer' : 'not-allowed',
                }}
              >
                Copy post draft
              </button>
              <a
                href={currentSourceRecord?.sourceUrl ?? '#'}
                target="_blank"
                rel="noreferrer"
                style={{
                  borderRadius: '12px',
                  border: '1px solid #38bdf8',
                  background: 'rgba(56,189,248,0.15)',
                  color: '#38bdf8',
                  padding: '8px 14px',
                  textDecoration: 'none',
                  fontSize: '13px',
                }}
              >
                Compose on LinkedIn
              </a>
            </div>
          </section>
        )}
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
          <div>
            <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Social Feed</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>High-performing signals</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px' }}>
              Fresh LinkedIn-first posts from key people and topical sources, mixed with reaction-ready Reddit/RSS placeholders. Comment or repost directly from the cards.
            </p>
          </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
          <button
              onClick={refreshSocialFeed}
              disabled={refreshingFeed}
              style={{
                borderRadius: '10px',
                border: '1px solid #38bdf8',
                padding: '8px 14px',
                background: refreshingFeed ? 'rgba(59,130,246,0.2)' : 'rgba(56,189,248,0.16)',
                color: '#38bdf8',
                cursor: refreshingFeed ? 'not-allowed' : 'pointer',
                fontSize: '13px',
              }}
            >
              {refreshingFeed ? 'Refreshing…' : 'Refresh feed'}
            </button>
            <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>
              Updated {socialFeed?.generated_at ?? 'waiting for feed'} · {visibleFeedItems.length} items tracked
            </p>
            {refreshStatus && (
              <p style={{ color: refreshingFeed ? '#38bdf8' : '#34d399', fontSize: '12px', margin: 0 }}>{refreshStatus}</p>
            )}
          </div>
        </div>
        <div style={{ border: '1px solid #334155', borderRadius: '12px', padding: '12px 14px', marginBottom: '16px', backgroundColor: '#030712' }}>
          <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
            Paste a URL or stand-alone copy of a post/text, pick a specific lane, and generate a live preview card that appears at the top of this feed.
          </p>
          <input
            placeholder="https://link.to/post"
            value={ingestUrl}
            onChange={(event) => setIngestUrl(event.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', marginBottom: '6px', fontSize: '12px' }}
          />
          <textarea
            placeholder="Or paste text you want to comment on..."
            value={ingestText}
            onChange={(event) => setIngestText(event.target.value)}
            rows={4}
            style={{ width: '100%', padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', fontSize: '12px', resize: 'vertical', marginBottom: '6px' }}
          />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '6px' }}>
            <input
              placeholder="Signal title (optional)"
              value={ingestTitle}
              onChange={(event) => setIngestTitle(event.target.value)}
              style={{ flex: 1, padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', fontSize: '12px' }}
            />
            <select
              value={ingestPriority}
              onChange={(event) => setIngestPriority(event.target.value as FeedLensId)}
              style={{ padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', fontSize: '12px' }}
            >
              {POST_MODE_OPTIONS.map((mode) => (
                <option key={mode.id} value={mode.id}>
                  {mode.label}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={ingestLoading ? undefined : ingestSignal}
              disabled={ingestLoading}
              style={{
                borderRadius: '10px',
                border: '1px solid #38bdf8',
                padding: '8px 14px',
                background: ingestLoading ? 'rgba(56,189,248,0.2)' : 'rgba(56,189,248,0.16)',
                color: '#38bdf8',
                cursor: ingestLoading ? 'not-allowed' : 'pointer',
                fontSize: '12px',
              }}
            >
              {ingestLoading ? 'Generating…' : 'Generate preview'}
            </button>
            {ingestStatus && <p style={{ color: '#34d399', fontSize: '12px', margin: 0 }}>{ingestStatus}</p>}
          </div>
        </div>
        {tuningDashboard && (
          <TuningDashboardPanel
            dashboard={tuningDashboard}
            feedbackSummary={feedbackSummary}
          />
        )}
        {quoteStatus && (
          <div
            style={{
              marginBottom: '12px',
              padding: '10px 14px',
              borderRadius: '10px',
              backgroundColor: isApprovingQuote ? 'rgba(37, 99, 235, 0.2)' : 'rgba(34,197,94,0.2)',
              border: `1px solid ${isApprovingQuote ? 'rgba(37,99,235,0.6)' : 'rgba(34,197,94,0.6)'}`,
              color: '#e0f2fe',
              fontSize: '13px',
            }}
          >
            {quoteStatus}
          </div>
        )}
        {copyStatus && (
          <p style={{ color: '#34d399', fontSize: '12px', marginTop: '-8px', marginBottom: '12px' }}>{copyStatus}</p>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
          {visibleFeedItems.slice(0, 5).map((item) => {
            const selectedFeedLens = resolveFeedLens(item);
            const activeVariant = getFeedVariant(item, selectedFeedLens);
            const rawQuickReply = createShortCommentDraft(item, selectedFeedLens);
            const rawCommentDraft = createCommentDraft(item, selectedFeedLens);
            const rawRepostDraft = createRepostDraft(item, selectedFeedLens);
            const editorial = buildFeedEditorialSummary(item, selectedFeedLens);
            const evaluation = activeVariant?.evaluation ?? item.evaluation;
            const beliefAssessment = activeVariant ?? item.belief_assessment;
            const techniqueAssessment = activeVariant ?? item.technique_assessment;
            const expressionAssessment = activeVariant?.expression_assessment ?? item.expression_assessment;
            const sourceContractClass = item.source_class ?? deriveSourceClass(item);
            const sourceContractUnit = item.unit_kind ?? deriveUnitKind(item, sourceContractClass);
            const sourceContractModes = item.response_modes ?? deriveResponseModes(item, sourceContractClass, sourceContractUnit);
            return (
            <article key={item.id} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                <span style={{ color: '#38bdf8', fontSize: '12px', border: '1px solid rgba(56,189,248,0.4)', borderRadius: '999px', padding: '2px 10px' }}>{item.platform}</span>
                <span style={{ color: '#fcd34d', fontWeight: 600, fontSize: '12px' }}>score {item.ranking.total.toFixed(1)}</span>
              </div>
              <h4 style={{ color: 'white', fontSize: '18px', margin: '0' }}>{item.title}</h4>
              <p style={{ color: '#94a3b8', margin: 0 }}>{item.author}</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div style={{ display: 'grid', gap: '4px' }}>
                  <p style={{ color: '#64748b', fontSize: '10px', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', margin: 0 }}>Angle</p>
                  <select
                    value={selectedFeedLens}
                    onChange={(event) => setFeedLensSelections((current) => ({ ...current, [item.id]: event.target.value as FeedLensId }))}
                    style={{ width: '220px', padding: '10px 12px', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', fontSize: '13px' }}
                  >
                    {POST_MODE_OPTIONS.map((mode) => (
                      <option key={`${item.id}-${mode.id}`} value={mode.id}>
                        {mode.label}
                      </option>
                    ))}
                  </select>
                </div>
                {item.source_url && (
                  <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                    Open source
                  </a>
                )}
              </div>
              {item.why_it_matters && (
                <div style={{ display: 'grid', gap: '4px' }}>
                  <p style={{ color: '#94a3b8', margin: 0, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Why this is in your feed</p>
                  <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{item.why_it_matters}</p>
                </div>
              )}
              <div style={{ borderRadius: '12px', border: '1px solid #273449', backgroundColor: '#06101f', padding: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'grid', gap: '4px' }}>
                  <p style={{ color: '#94a3b8', margin: 0, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Recommendation</p>
                  <p style={{ color: 'white', fontSize: '18px', fontWeight: 700, margin: 0 }}>{editorial.recommendation}</p>
                </div>
                <div style={{ display: 'grid', gap: '4px' }}>
                  <p style={{ color: '#94a3b8', margin: 0, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Why</p>
                  {editorial.why.map((reason) => (
                    <p key={`${item.id}-${reason}`} style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>
                      {reason}
                    </p>
                  ))}
                </div>
                <div style={{ display: 'grid', gap: '4px' }}>
                  <p style={{ color: '#94a3b8', margin: 0, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Best angle</p>
                  <p style={{ color: '#e2e8f0', fontSize: '13px', margin: 0 }}>{editorial.bestAngle}</p>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
                <div>
                  <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>Draft</p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: `1px solid ${editorial.draftTone}`, margin: 0, color: '#e2e8f0', lineHeight: 1.55 }}>{editorial.draft}</p>
                    <button
                      onClick={() => copyToClipboard(editorial.draft, 'draft', { item, lens: selectedFeedLens, variant: activeVariant })}
                      style={{ borderRadius: '10px', border: `1px solid ${editorial.draftTone}`, background: 'transparent', color: editorial.draftTone, padding: '4px 10px', fontSize: '12px' }}
                    >
                      Copy
                    </button>
                  </div>
                </div>
                {editorial.optionalDraft && editorial.optionalLabel && (
                  <div>
                    <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>{editorial.optionalLabel}</p>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: '1px solid #334155', margin: 0, color: '#e2e8f0', lineHeight: 1.55 }}>{editorial.optionalDraft}</p>
                      <button
                        onClick={() => copyToClipboard(editorial.optionalDraft ?? '', editorial.optionalLabel ?? 'optional draft', { item, lens: selectedFeedLens, variant: activeVariant })}
                        style={{ borderRadius: '10px', border: '1px solid #34d399', background: 'transparent', color: '#34d399', padding: '4px 10px', fontSize: '12px' }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                <button
                  onClick={() => recordFeedback(item, 'like')}
                  disabled={feedbackLoading[item.id]}
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #22c55e',
                    background: feedbackLoading[item.id] ? 'rgba(34,197,94,0.15)' : 'rgba(34,197,94,0.2)',
                    color: '#22c55e',
                    padding: '6px 12px',
                    fontSize: '12px',
                    cursor: feedbackLoading[item.id] ? 'not-allowed' : 'pointer',
                  }}
                >
                  👍 Like
                </button>
                <button
                  onClick={() => recordFeedback(item, 'dislike')}
                  disabled={feedbackLoading[item.id]}
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #f87171',
                    background: feedbackLoading[item.id] ? 'rgba(248,113,113,0.15)' : 'rgba(248,113,113,0.2)',
                    color: '#f87171',
                    padding: '6px 12px',
                    fontSize: '12px',
                    cursor: feedbackLoading[item.id] ? 'not-allowed' : 'pointer',
                  }}
                >
                  👎 Dislike
                </button>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{feedbackState[item.id] ?? 'Tell the feed if this recommendation felt right.'}</p>
              </div>
              <details style={{ borderRadius: '12px', border: '1px solid #273449', backgroundColor: '#030712', padding: '10px 12px' }}>
                <summary style={{ color: '#cbd5f5', cursor: 'pointer', fontSize: '12px', fontWeight: 700 }}>See why</summary>
                <div style={{ display: 'grid', gap: '10px', marginTop: '10px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    <span style={{ borderRadius: '999px', padding: '4px 8px', border: '1px solid rgba(96,165,250,0.35)', color: '#93c5fd', fontSize: '11px' }}>lane fit: {editorial.laneFit}</span>
                    <span style={{ borderRadius: '999px', padding: '4px 8px', border: '1px solid rgba(196,181,253,0.35)', color: '#c4b5fd', fontSize: '11px' }}>voice fit: {editorial.voiceFit}</span>
                    <span style={{ borderRadius: '999px', padding: '4px 8px', border: `1px solid ${editorial.specificityRisk === 'high' ? 'rgba(248,113,113,0.4)' : 'rgba(52,211,153,0.35)'}`, color: editorial.specificityRisk === 'high' ? '#fca5a5' : '#86efac', fontSize: '11px' }}>
                      specificity risk: {editorial.specificityRisk}
                    </span>
                    {beliefAssessment?.role_safety && (
                      <span style={{ borderRadius: '999px', padding: '4px 8px', border: '1px solid rgba(250,204,21,0.35)', color: '#fde68a', fontSize: '11px' }}>
                        role safety: {beliefAssessment.role_safety}
                      </span>
                    )}
                    {(techniqueAssessment?.techniques ?? []).map((technique) => (
                      <span key={`${item.id}-${selectedFeedLens}-${technique}`} style={{ borderRadius: '999px', padding: '4px 8px', border: '1px solid rgba(52,211,153,0.35)', color: '#86efac', fontSize: '11px' }}>
                        {technique}
                      </span>
                    ))}
                  </div>
                  <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                    <span style={{ color: '#94a3b8' }}>Best use:</span> {editorial.bestUse}
                  </p>
                  <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                    <span style={{ color: '#94a3b8' }}>Avoid:</span> {editorial.avoid}
                  </p>
                  {activeVariant?.why_this_angle && <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{activeVariant.why_this_angle}</p>}
                  {beliefAssessment?.belief_summary && (
                    <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                      <span style={{ color: '#94a3b8' }}>Belief:</span> {beliefAssessment.belief_summary}
                    </p>
                  )}
                  {beliefAssessment?.experience_summary && (
                    <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                      <span style={{ color: '#94a3b8' }}>Anchor:</span> {beliefAssessment.experience_summary}
                    </p>
                  )}
                  <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                    <span style={{ color: '#94a3b8' }}>Source contract:</span> {sourceContractClass} · {sourceContractUnit} · {sourceContractModes.join(', ')}
                  </p>
                  {expressionAssessment?.strategy && expressionAssessment?.output_text && (
                    <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                      <span style={{ color: '#94a3b8' }}>Expression:</span> {expressionAssessment.strategy} · {expressionAssessment.output_structure ?? 'plain'}
                    </p>
                  )}
                  {evaluation && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '6px' }}>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>Lane {evaluation.lane_distinctiveness?.toFixed(1)}</span>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>Belief {evaluation.belief_clarity?.toFixed(1)}</span>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>Voice {evaluation.voice_match?.toFixed(1)}</span>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>Expr {evaluation.expression_quality?.toFixed(1) ?? 'n/a'}</span>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>Src {evaluation.source_expression_quality?.toFixed(1) ?? 'n/a'}</span>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>Δ {evaluation.expression_delta?.toFixed(1) ?? '0.0'}</span>
                    </div>
                  )}
                  {(evaluation?.warnings?.length ?? 0) > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {evaluation?.warnings?.map((warning) => (
                        <p key={`${item.id}-${selectedFeedLens}-${warning}`} style={{ color: '#fca5a5', fontSize: '11px', margin: 0 }}>
                          {warning}
                        </p>
                      ))}
                    </div>
                  )}
                  {(rawQuickReply || rawCommentDraft || rawRepostDraft) && (
                    <details style={{ borderRadius: '12px', border: '1px solid #273449', backgroundColor: '#020617', padding: '8px 10px' }}>
                      <summary style={{ color: '#cbd5f5', cursor: 'pointer', fontSize: '12px', fontWeight: 700 }}>Raw variants</summary>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', marginTop: '10px' }}>
                        {rawQuickReply && (
                          <div>
                            <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>Quick reply</p>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: '1px solid #334155', margin: 0, color: '#e2e8f0', lineHeight: 1.55 }}>{rawQuickReply}</p>
                              <button
                                onClick={() => copyToClipboard(rawQuickReply, 'quick reply', { item, lens: selectedFeedLens, variant: activeVariant })}
                                style={{ borderRadius: '10px', border: '1px solid #34d399', background: 'transparent', color: '#34d399', padding: '4px 10px', fontSize: '12px' }}
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                        {rawCommentDraft && (
                          <div>
                            <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>Suggested comment</p>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: '1px solid #334155', margin: 0, color: '#e2e8f0', lineHeight: 1.55 }}>{rawCommentDraft}</p>
                              <button
                                onClick={() => copyToClipboard(rawCommentDraft, 'comment', { item, lens: selectedFeedLens, variant: activeVariant })}
                                style={{ borderRadius: '10px', border: '1px solid #38bdf8', background: 'transparent', color: '#38bdf8', padding: '4px 10px', fontSize: '12px' }}
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                        {rawRepostDraft && (
                          <div>
                            <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>Suggested repost</p>
                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                              <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: '1px solid #334155', margin: 0, color: '#e2e8f0', lineHeight: 1.55 }}>{rawRepostDraft}</p>
                              <button
                                onClick={() => copyToClipboard(rawRepostDraft, 'repost', { item, lens: selectedFeedLens, variant: activeVariant })}
                                style={{ borderRadius: '10px', border: '1px solid #f472b6', background: 'transparent', color: '#f472b6', padding: '4px 10px', fontSize: '12px' }}
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                  )}
                  {item.standout_lines?.map((line: string) => (
                    <div key={`${item.id}-${line}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', borderRadius: '12px', border: '1px solid rgba(148,163,184,0.4)', padding: '8px', backgroundColor: '#030712' }}>
                      <span style={{ color: '#e2e8f0', fontSize: '13px', flex: 1 }}>{line}</span>
                      <button
                        onClick={() => approveFeedLine(item, line)}
                        disabled={isApprovingQuote}
                        style={{ borderRadius: '10px', border: '1px solid #fbbf24', padding: '4px 10px', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: isApprovingQuote ? 'not-allowed' : 'pointer' }}
                      >
                        {isApprovingQuote ? 'Approving…' : 'Approve line'}
                      </button>
                    </div>
                  ))}
                </div>
              </details>
            </article>
          );
          })}
          {visibleFeedItems.length === 0 && <EmptyPanel message="No social feed items available yet. Generate a preview or run a refresh once the live feed pipeline is connected." />}
        </div>
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Perspective Toggle</p>
            <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Shift the strategy lens</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '760px' }}>
              Switch between admissions, entrepreneurship, current job, program leadership, enrollment, AI, ops/PM, therapy, referral, and personal story lenses to re-rank what is visible. This does not regenerate content yet, but it does surface a different cut of the current workspace.
            </p>
          </div>
          <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '12px 14px', minWidth: '220px' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Active Lens</p>
            <p style={{ color: '#f8fafc', fontSize: '20px', fontWeight: 700, margin: '4px 0' }}>{activeLensMeta.label}</p>
            <p style={{ color: '#64748b', fontSize: '13px', lineHeight: 1.45 }}>{activeLensMeta.description}</p>
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          {WORKSPACE_LENSES.map((lens) => {
            const count = lensCounts.find((item) => item.id === lens.id)?.count ?? 0;
            const active = lens.id === activeLens;
            return (
              <button
                key={lens.id}
                onClick={() => setActiveLens(lens.id)}
                style={{
                  borderRadius: '999px',
                  border: active ? '1px solid #fbbf24' : '1px solid #334155',
                  backgroundColor: active ? 'rgba(251,191,36,0.14)' : '#020617',
                  color: active ? '#f8fafc' : '#cbd5f5',
                  padding: '10px 14px',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '13px',
                  fontWeight: 600,
                }}
              >
                <span>{lens.label}</span>
                <span style={{ color: active ? '#fbbf24' : '#64748b', fontSize: '12px' }}>{count}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Long-form Routing</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Where transcript segments go</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '760px' }}>
              This is the first live routing layer over segmented long-form media. It shows whether the system thinks a segment belongs in persona review, post planning, or direct social reaction work.
            </p>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>
            {(longFormRoutes?.candidates ?? []).length} shown / {longFormRoutes?.segments_total ?? 0} routed segments
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '14px' }}>
          <MiniMeta label="Assets Considered" value={`${longFormRoutes?.assets_considered ?? 0}`} detail="long-form sources checked" />
          <MiniMeta label="Segments" value={`${longFormRoutes?.segments_total ?? 0}`} detail="claim-sized units extracted" />
          <MiniMeta label="Comment Ready" value={`${longFormRouteCounts.comment ?? 0}`} detail="segments eligible for comment routing" />
          <MiniMeta label="Repost Ready" value={`${longFormRouteCounts.repost ?? 0}`} detail="segments eligible for repost routing" />
          <MiniMeta label="Post Seeds" value={`${longFormRouteCounts.post_seed ?? 0}`} detail="segments useful for original-post planning" />
          <MiniMeta label="Belief Evidence" value={`${longFormRouteCounts.belief_evidence ?? 0}`} detail="segments useful for Brain/persona review" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', marginBottom: '14px' }}>
          <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
            <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Primary Route Mix</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.entries(longFormPrimaryRouteCounts).length === 0 ? (
                <EmptyPanel message="No routed long-form candidates yet." compact />
              ) : (
                Object.entries(longFormPrimaryRouteCounts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([route, count]) => (
                    <div key={route} style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '13px' }}>
                      <span style={{ color: '#e2e8f0' }}>{route}</span>
                      <span style={{ color: '#93c5fd' }}>{count}</span>
                    </div>
                  ))
              )}
            </div>
          </div>
          <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
            <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Channels</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.entries(longFormRoutes?.by_channel ?? {}).length === 0 ? (
                <EmptyPanel message="No routed channels yet." compact />
              ) : (
                Object.entries(longFormRoutes?.by_channel ?? {})
                  .sort((a, b) => b[1] - a[1])
                  .map(([channel, count]) => (
                    <div key={channel} style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '13px' }}>
                      <span style={{ color: '#e2e8f0' }}>{channel}</span>
                      <span style={{ color: '#c4b5fd' }}>{count}</span>
                    </div>
                  ))
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'grid', gap: '12px' }}>
          {(longFormRoutes?.candidates ?? []).slice(0, 6).map((candidate) => {
            const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, candidate.source_path);
            return (
              <article key={candidate.candidate_id} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                  <div>
                    <p style={{ color: '#f8fafc', fontWeight: 700 }}>{candidate.title}</p>
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                      {[candidate.source_channel, candidate.lane_hint, candidate.stance].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#fbbf24', fontSize: '12px' }}>
                      {candidate.primary_route}
                    </span>
                    <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>
                      score {candidate.route_score ?? 0}
                    </span>
                  </div>
                </div>
                <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.55, marginTop: '10px' }}>{candidate.segment}</p>
                <p style={{ color: '#64748b', fontSize: '12px', marginTop: '8px' }}>{candidate.route_reason}</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
                  {candidate.response_modes.map((mode) => (
                    <span key={`${candidate.candidate_id}-${mode}`} style={{ borderRadius: '999px', border: '1px solid #334155', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>
                      {mode}
                    </span>
                  ))}
                  <span style={{ borderRadius: '999px', border: '1px solid #334155', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>
                    {candidate.target_file}
                  </span>
                </div>
                {candidate.belief_summary ? <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '10px' }}>Belief: {candidate.belief_summary}</p> : null}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{candidate.source_path}</p>
                  {candidate.source_url ? (
                    <a href={candidate.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original source
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
          {(longFormRoutes?.candidates ?? []).length === 0 && <EmptyPanel message="No routed long-form candidates are visible yet." />}
        </div>
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Long-form Planner Feed</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Routed media post seeds</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '760px' }}>
              These are planner-facing post seeds coming from the shared long-form route contract, not a separate transcript planner.
            </p>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>
            {filteredMediaPostSeeds.length} shown / {plan?.media_post_seeds?.length ?? 0} routed seeds
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '14px' }}>
          <MiniMeta label="Assets Considered" value={`${plan?.media_summary?.assets_considered ?? 0}`} detail="shared long-form sources" />
          <MiniMeta label="Segments" value={`${plan?.media_summary?.segments_total ?? 0}`} detail="claim-sized units ranked" />
          <MiniMeta label="Post Seeds" value={`${plan?.media_summary?.primary_route_counts?.post_seed ?? 0}`} detail="primary planner route" />
          <MiniMeta label="Belief Evidence" value={`${plan?.media_summary?.primary_route_counts?.belief_evidence ?? 0}`} detail="persona-facing planner route" />
        </div>
        <div style={{ display: 'grid', gap: '12px' }}>
          {filteredMediaPostSeeds.slice(0, 4).map((item, index) => {
            const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.source_path);
            return (
              <article key={`${item.source_path}-${item.hook}-${index}`} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
                  <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#f8fafc', fontSize: '12px' }}>{index + 1}</span>
                  <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>{item.source_kind}</span>
                  {item.priority_lane ? <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{item.priority_lane}</span> : null}
                  {item.target_file ? <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#86efac', fontSize: '12px' }}>{item.target_file}</span> : null}
                </div>
                <h4 style={{ fontSize: '18px', color: 'white', margin: '0 0 6px' }}>{item.title}</h4>
                <p style={{ color: '#f5d0fe', fontSize: '14px', marginBottom: '8px' }}>{item.hook}</p>
                <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.55 }}>{item.rationale}</p>
                {item.route_reason ? (
                  <p style={{ color: '#64748b', fontSize: '12px', marginTop: '10px' }}>Route reason: {item.route_reason}</p>
                ) : null}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '12px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.source_path}</p>
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original source
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
                <button
                  onClick={() => setSelectedRecommendation(item)}
                  style={{
                    marginTop: '10px',
                    border: '1px solid #38bdf8',
                    borderRadius: '12px',
                    padding: '8px 12px',
                    background: 'rgba(56,189,248,0.08)',
                    color: '#38bdf8',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Create post from this seed
                </button>
              </article>
            );
          })}
          {filteredMediaPostSeeds.length === 0 && <EmptyPanel message={`No long-form post seeds match the ${activeLensMeta.label} lens yet.`} />}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Priority Lanes</p>
          <h3 style={{ fontSize: '22px', color: 'white', margin: '6px 0 12px' }}>What to publish around</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {(plan?.priority_lanes ?? []).map((lane) => (
              <span key={lane} style={{ borderRadius: '999px', border: '1px solid #374151', padding: '8px 12px', color: '#e2e8f0', fontSize: '13px', backgroundColor: '#020617' }}>
                {lane}
              </span>
            ))}
          </div>
          {editorialMix.length > 0 && (
            <>
              <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', margin: '18px 0 8px' }}>Editorial Mix</p>
              <div style={{ display: 'grid', gap: '8px' }}>
                {editorialMix.slice(0, 4).map((item) => (
                  <div key={item} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px 12px', color: '#cbd5f5', fontSize: '13px' }}>
                    {item}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workflow</p>
          <h3 style={{ fontSize: '22px', color: 'white', margin: '6px 0 12px' }}>Capture to publish</h3>
          {workflowSteps.length > 0 ? (
            <div style={{ display: 'grid', gap: '10px' }}>
              {workflowSteps.map((step) => (
                <div key={step.title} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '12px 14px' }}>
                  <p style={{ color: '#f8fafc', fontWeight: 700, marginBottom: '6px' }}>{step.title}</p>
                  <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.5 }}>{summarize(step.body, 180)}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyPanel message="Workflow doc is not mounted in this frontend context yet, but the strategy snapshot below is live." />
          )}
          {saveRules.keep.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '8px' }}>Signal Rules</p>
              <ul style={{ margin: 0, paddingLeft: '18px', color: '#cbd5f5', display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '13px' }}>
                {saveRules.keep.slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Weekly Recommendations</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Recommended LinkedIn posts</h3>
            <p style={{ color: '#64748b', fontSize: '13px' }}>Visible through the <span style={{ color: '#cbd5f5' }}>{activeLensMeta.label}</span> lens.</p>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredRecommendations.length} shown / {plan?.recommendations.length ?? 0} ranked items</span>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            {POST_MODE_OPTIONS.map((mode) => (
              <button
                key={mode.id}
                onClick={() => setPostMode(mode.id)}
                style={{
                  borderRadius: '999px',
                  border: postMode === mode.id ? '1px solid #fbbf24' : '1px solid #1f2937',
                  padding: '6px 14px',
                  background: postMode === mode.id ? 'rgba(251,191,36,0.15)' : 'transparent',
                  color: postMode === mode.id ? '#fbbf24' : '#cbd5f5',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                {mode.label}
              </button>
            ))}
            <span style={{ color: '#64748b', fontSize: '12px' }}>post mode</span>
          </div>
        </div>
        <div style={{ display: 'grid', gap: '12px' }}>
          {filteredRecommendations.slice(0, 4).map((item, index) => {
            const sourceRecord = sourceRecords.find((record) => record.sourcePath === item.source_path);
            const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.source_path);
            return (
            <article key={`${item.source_path}-${index}`} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#f8fafc', fontSize: '12px' }}>{index + 1}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>{item.role_alignment}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#fbbf24', fontSize: '12px' }}>{item.risk_level}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{labelSourceKind(item.source_kind)}</span>
                {item.priority_lane ? <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{item.priority_lane}</span> : null}
              </div>
              <h4 style={{ fontSize: '18px', color: 'white', margin: '0 0 6px' }}>{item.title}</h4>
              <p style={{ color: '#f5d0fe', fontSize: '14px', marginBottom: '8px' }}>{item.hook}</p>
              <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.55 }}>{item.rationale}</p>
              <div style={{ marginTop: '12px', padding: '12px', borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712' }}>
                <p style={{ color: '#64748b', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '6px' }}>Lens Remix</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5 }}>{buildLensRemix(activeLens, item)}</p>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '12px' }}>
                <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.source_path}</p>
                {sourceRecord?.sourceUrl ? (
                  <a href={sourceRecord.sourceUrl} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                    Open original source
                  </a>
                ) : null}
                {mountedSource ? (
                  <button
                    onClick={() => onSelect(mountedSource.path)}
                    style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                  >
                    Open workspace file
                  </button>
                ) : null}
              </div>
              <button
                onClick={() => setSelectedRecommendation(item)}
                style={{
                  marginTop: '10px',
                  border: '1px solid #38bdf8',
                  borderRadius: '12px',
                  padding: '8px 12px',
                  background: 'rgba(56,189,248,0.08)',
                  color: '#38bdf8',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                Create post from this idea
              </button>
            </article>
          );
          })}
          {filteredRecommendations.length === 0 && <EmptyPanel message={`No recommendations match the ${activeLensMeta.label} lens yet.`} />}
        </div>
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Signal Feed</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Source-native market inputs</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '760px' }}>
              These are the actual external signals the workspace is reacting to. This is the evidence lane behind the generated strategy view.
            </p>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredSignals.length} shown / {sourceRecords.length} tracked sources</span>
        </div>
        <div style={{ display: 'grid', gap: '12px' }}>
          {filteredSignals.slice(0, 6).map((item) => {
            const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.sourcePath);
            return (
              <article key={item.sourcePath} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                  <div>
                    <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                      {[item.author, item.sourcePlatform, item.sourceType].filter(Boolean).join(' · ') || 'Workspace signal'}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {item.priorityLane ? <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>{item.priorityLane}</span> : null}
                    <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{item.roleAlignment}</span>
                  </div>
                </div>
                {item.hook ? <p style={{ color: '#f5d0fe', fontSize: '13px', marginTop: '8px' }}>{item.hook}</p> : null}
                <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5, marginTop: '8px' }}>{item.summary}</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.sourcePath}</p>
                  {item.sourceUrl ? (
                    <a href={item.sourceUrl} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original post
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
          {filteredSignals.length === 0 && <EmptyPanel message={`No source-native signals match the ${activeLensMeta.label} lens yet.`} />}
        </div>
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Long-form Assets</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Transcript and media inventory</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '760px' }}>
              These are upstream YouTube, podcast, audio, and transcript assets visible to the system before segmentation. They should feed post seeds and belief evidence first, then graduate into feed cards only after claim-sized units exist.
            </p>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>
            {sourceAssetRecords.length} shown / {sourceAssets?.counts?.total ?? sourceAssetRecords.length} tracked assets
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '14px' }}>
          <MiniMeta
            label="Total Assets"
            value={`${sourceAssets?.counts?.total ?? sourceAssetRecords.length}`}
            detail="long-form source inventory"
          />
          <MiniMeta
            label="Pending Segments"
            value={`${sourceAssets?.counts?.pending_segmentation ?? sourceAssetRecords.filter((item) => item.routingStatus === 'pending_segmentation').length}`}
            detail="needs claim-sized extraction"
          />
          <MiniMeta
            label="Feed Ready"
            value={`${sourceAssets?.counts?.feed_ready ?? sourceAssetRecords.filter((item) => item.responseModes.includes('comment') || item.responseModes.includes('repost')).length}`}
            detail="eligible for direct feed routing"
          />
          <MiniMeta
            label="Channels"
            value={`${Object.keys(sourceAssets?.counts?.by_channel ?? {}).length}`}
            detail="distinct media channels"
          />
        </div>
        {Object.keys(sourceAssets?.counts?.by_channel ?? {}).length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' }}>
            {Object.entries(sourceAssets?.counts?.by_channel ?? {})
              .sort((a, b) => b[1] - a[1])
              .map(([channel, count]) => (
                <span
                  key={channel}
                  style={{
                    borderRadius: '999px',
                    border: '1px solid #334155',
                    padding: '6px 10px',
                    color: '#cbd5f5',
                    fontSize: '12px',
                    backgroundColor: '#020617',
                  }}
                >
                  {channel} · {count}
                </span>
              ))}
          </div>
        )}
        <div style={{ display: 'grid', gap: '12px' }}>
          {sourceAssetRecords.slice(0, 8).map((asset) => {
            const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, asset.sourcePath);
            return (
              <article key={asset.assetId} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                  <div>
                    <p style={{ color: '#f8fafc', fontWeight: 700 }}>{asset.title}</p>
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                      {[asset.sourceChannel, asset.sourceType, asset.origin].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>
                      {asset.sourceClass}
                    </span>
                    {asset.routingStatus ? (
                      <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#fbbf24', fontSize: '12px' }}>
                        {asset.routingStatus}
                      </span>
                    ) : null}
                    {asset.wordCount ? (
                      <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>
                        {formatUiNumber(asset.wordCount)} words
                      </span>
                    ) : null}
                  </div>
                </div>
                {asset.summary ? <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5, marginTop: '8px' }}>{asset.summary}</p> : null}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
                  {asset.responseModes.map((mode) => (
                    <span key={`${asset.assetId}-${mode}`} style={{ borderRadius: '999px', border: '1px solid #334155', padding: '4px 10px', color: '#86efac', fontSize: '11px' }}>
                      {mode}
                    </span>
                  ))}
                  {asset.topics.slice(0, 4).map((topic) => (
                    <span key={`${asset.assetId}-topic-${topic}`} style={{ borderRadius: '999px', border: '1px solid #334155', padding: '4px 10px', color: '#93c5fd', fontSize: '11px' }}>
                      {topic}
                    </span>
                  ))}
                  {asset.tags.slice(0, 4).map((tag) => (
                    <span key={`${asset.assetId}-tag-${tag}`} style={{ borderRadius: '999px', border: '1px solid #334155', padding: '4px 10px', color: '#f5d0fe', fontSize: '11px' }}>
                      {tag}
                    </span>
                  ))}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{asset.sourcePath}</p>
                  {asset.capturedAt ? <span style={{ color: '#64748b', fontSize: '12px' }}>captured {asset.capturedAt}</span> : null}
                  {asset.sourceUrl ? (
                    <a href={asset.sourceUrl} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original source
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
          {sourceAssetRecords.length === 0 && (
            <EmptyPanel message="No transcript or media assets are visible yet. Once the transcript/media adapters are live, this panel becomes the upstream source-of-truth for long-form intake." />
          )}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Reaction Queue</p>
              <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Immediate comment opportunities</h3>
            </div>
            <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredCommentOpportunities.length} shown / {reactionQueue?.counts.comment_opportunities ?? 0}</span>
          </div>
          <div style={{ display: 'grid', gap: '12px' }}>
            {filteredCommentOpportunities.slice(0, 3).map((item) => {
              const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.source_path);
              return (
              <article key={item.source_path} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                  {[item.author, item.source_platform, item.priority_lane, item.role_alignment].filter(Boolean).join(' · ')}
                </p>
                <p style={{ color: '#f5d0fe', fontSize: '13px', marginTop: '8px' }}>{item.hook}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{item.suggested_comment}</p>
                <div style={{ marginTop: '10px', padding: '12px', borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712' }}>
                  <p style={{ color: '#64748b', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '6px' }}>Current Lens Remix</p>
                  <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5 }}>{buildLensRemix(activeLens, item)}</p>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.source_path}</p>
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original post
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
            })}
            {filteredCommentOpportunities.length === 0 && <EmptyPanel message={`No reaction opportunities match the ${activeLensMeta.label} lens yet.`} />}
          </div>
        </section>

        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Draft Inputs</p>
              <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Post seeds and assets</h3>
            </div>
            <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredPostSeeds.length} shown / {reactionQueue?.counts.post_seeds ?? 0} seeds</span>
          </div>
          <div style={{ display: 'grid', gap: '12px', marginBottom: '14px' }}>
            {filteredPostSeeds.slice(0, 3).map((item) => {
              const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.source_path);
              return (
              <article key={`${item.source_path}-seed`} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>{[item.priority_lane, item.role_alignment].filter(Boolean).join(' · ')}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{item.post_angle}</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.source_path}</p>
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original post
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
            })}
            {filteredPostSeeds.length === 0 && <EmptyPanel message={`No post seeds match the ${activeLensMeta.label} lens yet.`} />}
          </div>
          <div style={{ display: 'grid', gap: '8px' }}>
            <MiniMeta label="Workspace Docs" value={`${docFiles.length}`} detail="FEEZIE OS runbooks and models" />
            <MiniMeta label="Backlog Items" value={`${backlogActive.length}`} detail="Active LinkedIn tasks" />
            <MiniMeta label="Draft Files" value={`${draftFiles.length}`} detail="Posts ready to refine" />
          </div>
        </section>
      </div>

      {backlogActive.length > 0 && (
        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ marginBottom: '14px' }}>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Backlog</p>
            <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Active FEEZIE workspace tasks</h3>
          </div>
          <div style={{ display: 'grid', gap: '12px', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
            {backlogActive.slice(0, 4).map((item) => (
              <div key={item.title} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{summarize(item.body, 160)}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <SplitPane
        sidebar={
          linkedinFiles.length === 0 ? (
            <EmptyPanel message="Raw LinkedIn workspace files are not mounted in this frontend context yet. The strategy snapshot above is still live." compact />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {groups.map(([group, items]) => (
                <div key={group}>
                  <p style={{ color: '#64748b', fontSize: '11px', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: '8px' }}>{group}</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {items.map((file) => (
                      <button
                        key={file.path}
                        onClick={() => onSelect(file.path)}
                        style={{
                          textAlign: 'left',
                          padding: '12px',
                          borderRadius: '12px',
                          border: file.path === selectedLinkedin?.path ? '1px solid #fbbf24' : '1px solid #1f2937',
                          background: file.path === selectedLinkedin?.path ? 'rgba(251,191,36,0.12)' : '#050b19',
                          color: 'white',
                          cursor: 'pointer',
                        }}
                      >
                        <p style={{ fontWeight: 600 }}>{file.name}</p>
                        <p style={{ color: '#64748b', fontSize: '12px', marginTop: '4px' }}>{file.snippet || file.path}</p>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        }
        content={selectedLinkedin ? <MarkdownSurface title={selectedLinkedin.name} path={selectedLinkedin.path} updatedAt={selectedLinkedin.updatedAt} content={selectedLinkedin.content} /> : <EmptyPanel message="Select a LinkedIn workspace file to inspect." />}
      />
    </section>
  );
}

function DocsPanel({ docs, selected, onSelect }: { docs: DocReference[]; selected: DocReference | null; onSelect: (path: string) => void }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Docs</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>Specs + runbooks</h2>
        <p style={{ color: '#94a3b8' }}>The docs pane is wired to real local markdown instead of placeholder copy.</p>
      </div>
      <SplitPane
        sidebar={
          docs.length === 0 ? (
            <EmptyPanel message="No docs available." compact />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {docs.map((doc) => (
                <button
                  key={doc.path}
                  onClick={() => onSelect(doc.path)}
                  style={{
                    textAlign: 'left',
                    padding: '12px',
                    borderRadius: '12px',
                    border: doc.path === selected?.path ? '1px solid #fbbf24' : '1px solid #1f2937',
                    background: doc.path === selected?.path ? 'rgba(251,191,36,0.12)' : '#050b19',
                    color: 'white',
                    cursor: 'pointer',
                  }}
                >
                  <p style={{ fontWeight: 600 }}>{doc.name}</p>
                  <p style={{ color: '#64748b', fontSize: '12px', marginTop: '4px' }}>{doc.snippet || doc.path}</p>
                </button>
              ))}
            </div>
          )
        }
        content={selected ? <MarkdownSurface title={selected.name} path={selected.path} updatedAt={selected.updatedAt} content={selected.content} /> : <EmptyPanel message="Select a document to inspect." />}
      />
    </section>
  );
}

function TuningDashboardPanel({
  dashboard,
  feedbackSummary,
}: {
  dashboard: TuningDashboard;
  feedbackSummary: FeedbackSummary | null;
}) {
  return (
    <section
      style={{
        borderRadius: '16px',
        border: '1px solid rgba(56,189,248,0.22)',
        background: 'linear-gradient(180deg, rgba(7,15,30,0.98), rgba(2,6,23,0.98))',
        padding: '16px',
        marginBottom: '16px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>Tuning Dashboard</p>
          <h4 style={{ color: 'white', fontSize: '22px', margin: 0 }}>Where the pipeline is weak</h4>
          <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '6px', maxWidth: '760px' }}>
            {dashboard.sampleMode === 'real-only' ? 'Real-only sample' : 'All-items fallback sample'} across {dashboard.variantCount} lane variants from {dashboard.itemCount} feed items. This is the fastest way to see whether the current problem is source grounding, expression quality, or lane writing.
          </p>
          {dashboard.placeholderExcludedCount > 0 && (
            <p style={{ color: '#64748b', fontSize: '12px', marginTop: '6px' }}>
              Excluded {dashboard.placeholderExcludedCount} placeholder feed item{dashboard.placeholderExcludedCount === 1 ? '' : 's'} from the tuning sample.
            </p>
          )}
        </div>
        <div style={{ color: '#94a3b8', fontSize: '12px', textAlign: 'right' }}>
          <p>Feedback events: {feedbackSummary?.total_events ?? 0}</p>
          <p>
            Human avg expr: {feedbackSummary?.average_output_expression_quality?.toFixed(1) ?? '-'} · Human avg Δ:{' '}
            {feedbackSummary?.average_expression_delta?.toFixed(1) ?? '-'}
          </p>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <MiniMeta label="Avg Overall" value={dashboard.avgOverall.toFixed(1)} detail="Current sample quality" />
        <MiniMeta label="Avg Source" value={dashboard.avgSourceExpressionQuality.toFixed(1)} detail="Source grounding strength" />
        <MiniMeta label="Avg Expr" value={dashboard.avgExpressionQuality.toFixed(1)} detail="Output expression quality" />
        <MiniMeta label="Avg Δ" value={dashboard.avgExpressionDelta.toFixed(1)} detail="Output lift vs source" />
        <MiniMeta label="Weak Source" value={`${dashboard.weakSourceCount}`} detail="Variants with no usable source grounding" />
        <MiniMeta label="Lane Carried" value={`${dashboard.laneDominanceCount}`} detail="High-scoring variants with weak source grounding" />
        <MiniMeta label="Warnings" value={`${dashboard.warningVariantCount}`} detail="Variants currently tripping warnings" />
        <MiniMeta label="Suspect Titles" value={`${dashboard.suspectTitleCount}`} detail="Items that look like mastheads or title surfaces" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Failure Modes</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboard.failureModes.map((mode) => (
              <div key={mode.label} style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '13px' }}>
                <span style={{ color: '#e2e8f0' }}>{mode.label}</span>
                <span style={{ color: '#fda4af' }}>{mode.count}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Warning Hotspots</p>
          {dashboard.warningCounts.length === 0 ? (
            <EmptyPanel message="No warning hotspots in the current sample." compact />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {dashboard.warningCounts.map((warning) => (
                <div key={warning.label} style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '13px' }}>
                  <span style={{ color: '#e2e8f0' }}>{warning.label}</span>
                  <span style={{ color: '#fca5a5' }}>{warning.count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Expression Strategy Mix</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboard.strategyCounts.map((strategy) => (
              <div key={strategy.label} style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '13px' }}>
                <span style={{ color: '#e2e8f0' }}>{strategy.label}</span>
                <span style={{ color: '#93c5fd' }}>{strategy.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Source Class Health</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboard.sourceClassHealth.map((sourceClass) => (
              <div key={sourceClass.sourceClass} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '8px 10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ color: 'white', fontWeight: 600, fontSize: '13px' }}>{sourceClass.sourceClass}</span>
                  <span style={{ color: '#94a3b8', fontSize: '11px' }}>{sourceClass.variants} variants</span>
                </div>
                <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                  overall {sourceClass.avgOverall.toFixed(1)} · src {sourceClass.avgSource.toFixed(1)} · expr {sourceClass.avgExpression.toFixed(1)} · Δ {sourceClass.avgDelta.toFixed(1)} · weak {sourceClass.weakSourceCount}
                </p>
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Unit Kind Health</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboard.unitKindHealth.map((unitKind) => (
              <div key={unitKind.unitKind} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '8px 10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ color: 'white', fontWeight: 600, fontSize: '13px' }}>{unitKind.unitKind}</span>
                  <span style={{ color: '#94a3b8', fontSize: '11px' }}>{unitKind.variants} variants</span>
                </div>
                <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                  src {unitKind.avgSource.toFixed(1)} · expr {unitKind.avgExpression.toFixed(1)} · Δ {unitKind.avgDelta.toFixed(1)} · weak {unitKind.weakSourceCount}
                </p>
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Response Mode Health</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboard.responseModeHealth.map((mode) => (
              <div key={mode.mode} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '8px 10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ color: 'white', fontWeight: 600, fontSize: '13px' }}>{mode.mode}</span>
                  <span style={{ color: '#94a3b8', fontSize: '11px' }}>{mode.itemCount} items · {mode.variants} variants</span>
                </div>
                <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                  src {mode.avgSource.toFixed(1)} · expr {mode.avgExpression.toFixed(1)} · Δ {mode.avgDelta.toFixed(1)} · weak {mode.weakSourceCount}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Platform Health</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboard.platformHealth.map((platform) => (
              <div key={platform.platform} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '8px 10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ color: 'white', fontWeight: 600, fontSize: '13px' }}>{platform.platform}</span>
                  <span style={{ color: '#94a3b8', fontSize: '11px' }}>{platform.variants} variants</span>
                </div>
                <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                  overall {platform.avgOverall.toFixed(1)} · src {platform.avgSource.toFixed(1)} · expr {platform.avgExpression.toFixed(1)} · Δ {platform.avgDelta.toFixed(1)} · weak {platform.weakSourceCount}
                </p>
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Structure Health</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {dashboard.structureHealth.map((structure) => (
              <div key={structure.structure} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '8px 10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ color: 'white', fontWeight: 600, fontSize: '13px' }}>{structure.structure}</span>
                  <span style={{ color: '#94a3b8', fontSize: '11px' }}>{structure.variants} variants</span>
                </div>
                <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                  src {structure.avgSource.toFixed(1)} · expr {structure.avgExpression.toFixed(1)} · Δ {structure.avgDelta.toFixed(1)} · preserve {(structure.preservedRate * 100).toFixed(0)}%
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 0.9fr)', gap: '12px' }}>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Lane Health</p>
          <div style={{ display: 'grid', gap: '8px' }}>
            {dashboard.laneHealth.map((lane) => (
              <div
                key={lane.lane}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(120px, 1.2fr) repeat(5, minmax(0, 0.8fr))',
                  gap: '8px',
                  alignItems: 'center',
                  borderRadius: '12px',
                  border: '1px solid #1f2937',
                  padding: '8px 10px',
                  fontSize: '12px',
                }}
              >
                <span style={{ color: 'white', fontWeight: 600 }}>{lane.laneLabel}</span>
                <span style={{ color: '#94a3b8' }}>O {lane.avgOverall.toFixed(1)}</span>
                <span style={{ color: '#94a3b8' }}>S {lane.avgSource.toFixed(1)}</span>
                <span style={{ color: '#94a3b8' }}>E {lane.avgExpression.toFixed(1)}</span>
                <span style={{ color: '#94a3b8' }}>Δ {lane.avgDelta.toFixed(1)}</span>
                <span style={{ color: lane.weakSourceCount > 0 ? '#fca5a5' : '#64748b' }}>weak {lane.weakSourceCount}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
          <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>Attention Queue</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {dashboard.attentionQueue.map((item) => (
              <div key={`${item.itemId}-${item.laneLabel}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ color: 'white', fontWeight: 600, fontSize: '13px' }}>{summarize(item.title, 58)}</span>
                  <span style={{ color: '#94a3b8', fontSize: '11px' }}>{item.laneLabel}</span>
                </div>
                <p style={{ color: '#fca5a5', fontSize: '12px', margin: '0 0 6px' }}>{item.reason}</p>
                {item.sourceText && (
                  <p style={{ color: '#cbd5f5', fontSize: '11px', margin: '0 0 4px' }}>
                    <span style={{ color: '#64748b' }}>src:</span> {summarize(item.sourceText, 120)}
                  </p>
                )}
                {item.outputText && (
                  <p style={{ color: '#cbd5f5', fontSize: '11px', margin: '0 0 6px' }}>
                    <span style={{ color: '#64748b' }}>out:</span> {summarize(item.outputText, 120)}
                  </p>
                )}
                <p style={{ color: '#64748b', fontSize: '11px', margin: 0 }}>
                  {item.platform} · overall {item.overall.toFixed(1)} · src {item.sourceExpressionQuality.toFixed(1)} · expr {item.expressionQuality.toFixed(1)} · Δ {item.expressionDelta.toFixed(1)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function SplitPane({ sidebar, content }: { sidebar: JSX.Element; content: JSX.Element }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr)', gap: '16px', alignItems: 'start' }}>
      <div style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '16px', minHeight: '520px' }}>{sidebar}</div>
      <div style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px', minHeight: '520px' }}>{content}</div>
    </div>
  );
}

function MarkdownSurface({ title, path, updatedAt, content }: { title: string; path: string; updatedAt: string; content: string }) {
  return (
    <div>
      <div style={{ marginBottom: '16px' }}>
        <p style={{ color: '#64748b', fontSize: '12px' }}>{path}</p>
        <h3 style={{ fontSize: '28px', color: 'white', margin: '6px 0' }}>{title}</h3>
        <p style={{ color: '#94a3b8', fontSize: '13px' }}>Updated {formatTimestamp(new Date(updatedAt))}</p>
      </div>
      <pre
        style={{
          margin: 0,
          whiteSpace: 'pre-wrap',
          color: '#dbe4f4',
          fontSize: '13px',
          lineHeight: 1.65,
          fontFamily: 'ui-monospace, SFMono-Regular, SFMono, Menlo, Consolas, monospace',
        }}
      >
        {content}
      </pre>
    </div>
  );
}

function EmptyPanel({ message, compact = false }: { message: string; compact?: boolean }) {
  return (
    <div style={{ borderRadius: compact ? '0' : '16px', border: compact ? 'none' : '1px dashed #1f2937', padding: compact ? 0 : '18px', color: '#64748b', fontSize: '14px' }}>
      {message}
    </div>
  );
}

function PanelList({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel: string }) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '6px' }}>{title}</p>
      {items.length === 0 ? (
        <p style={{ color: '#475569', fontSize: '13px' }}>{emptyLabel}</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: '18px', color: '#dbe4f4', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {items.map((item) => (
            <li key={`${title}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MiniMeta({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
  );
}

function MiniStat({ label, value, detail, tone }: { label: string; value: number; detail: string; tone: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: tone, fontSize: '22px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
  );
}

function SectionAlert({ message }: { message: string }) {
  return (
    <div
      style={{
        marginBottom: '16px',
        padding: '12px 16px',
        borderRadius: '12px',
        border: '1px solid rgba(248,113,113,0.3)',
        backgroundColor: 'rgba(69,10,10,0.6)',
        color: '#fecaca',
        fontSize: '14px',
      }}
    >
      {message}
    </div>
  );
}

function EventChainStrip({
  title,
  description,
  items,
}: {
  title: string;
  description?: string;
  items: Array<{ label: string; value: string; detail: string; tone?: string }>;
}) {
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#111827', padding: '14px' }}>
      <div style={{ marginBottom: '10px' }}>
        <p style={{ color: '#94a3b8', letterSpacing: '0.14em', fontSize: '11px', textTransform: 'uppercase', marginBottom: '6px' }}>{title}</p>
        {description ? <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>{description}</p> : null}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
        {items.map((item, index) => (
          <div key={`${title}-${item.label}-${index}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '12px', position: 'relative' }}>
            <p style={{ color: item.tone ?? '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>{item.label}</p>
            <p style={{ color: 'white', fontSize: '14px', fontWeight: 700, margin: '0 0 6px' }}>{item.value}</p>
            <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>{item.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusTable({
  title,
  subtitle,
  headers,
  rows,
}: {
  title: string;
  subtitle: string;
  headers: string[];
  rows: (string | JSX.Element)[][];
}) {
  return (
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#94a3b8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>{title}</p>
        <p style={{ color: '#64748b', fontSize: '13px' }}>{subtitle}</p>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {headers.map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length} style={{ padding: '12px 0', color: '#475569' }}>
                  Nothing to show yet.
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr key={idx}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} style={{ padding: '10px 0', color: '#e2e8f0', fontSize: '14px', borderBottom: '1px solid #0f172a' }}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CronTable({ cronJobs }: { cronJobs: Automation[] }) {
  return (
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#94a3b8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Cron Jobs</p>
        <p style={{ color: '#64748b', fontSize: '13px' }}>Isolated sessions mirrored into Brain to Automations</p>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Name', 'Schedule', 'Status', 'Channel', 'Last Run', 'Next Run'].map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cronJobs.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '12px 0', color: '#475569' }}>No cron jobs configured.</td>
              </tr>
            ) : (
              cronJobs.map((job) => (
                <tr key={job.id}>
                  <td style={{ padding: '10px 0', color: '#e2e8f0', fontWeight: 600 }}>
                    <div style={{ display: 'grid', gap: '6px' }}>
                      <span>{job.name}</span>
                      {(() => {
                        const pendingBackfill = Number(job.metrics?.pending_transcript_backfill ?? 0);
                        if (job.id !== 'youtube_watchlist_auto_ingest' || !Number.isFinite(pendingBackfill) || pendingBackfill <= 0) {
                          return null;
                        }
                        return (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              width: 'fit-content',
                              borderRadius: '999px',
                              border: '1px solid rgba(245, 158, 11, 0.35)',
                              backgroundColor: 'rgba(120, 53, 15, 0.35)',
                              color: '#fbbf24',
                              fontSize: '11px',
                              fontWeight: 500,
                              padding: '2px 8px',
                            }}
                          >
                            {pendingBackfill} pending transcript{pendingBackfill === 1 ? '' : 's'}
                          </span>
                        );
                      })()}
                    </div>
                  </td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span>{job.schedule}</span>
                      <span style={{ fontSize: '12px', color: '#475569' }}>{job.cron}</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 0' }}>{statusBadge(job.status)}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{job.channel}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.last_run_at ? formatTimestamp(new Date(job.last_run_at)) : '-'}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.next_run_at ? formatTimestamp(new Date(job.next_run_at)) : '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const highlightColors: Record<OrgNode['highlight'], string> = {
  core: '#f97316',
  ops: '#fbbf24',
  brain: '#38bdf8',
  lab: '#4ade80',
};

const statusLabels: Record<OrgNode['status'], string> = {
  active: 'Live',
  planned: 'Planned',
};

function OrgChartSection({ layers }: { layers: OrgNode[][] }) {
  return (
    <section style={{ border: '1px solid #1f2937', borderRadius: '18px', padding: '24px', backgroundColor: '#0b1324' }}>
      <div style={{ marginBottom: '16px' }}>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '12px', textTransform: 'uppercase' }}>Org Design</p>
        <h2 style={{ fontSize: '28px', fontWeight: 600, color: 'white', margin: '4px 0' }}>Team</h2>
        <p style={{ color: '#94a3b8' }}>Feeze to Neo to module-specific agents. Future slots remain visible without pretending they are live.</p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {layers.map((layer, idx) => (
          <div key={`layer-${idx}`} style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
            {layer.map((node) => (
              <OrgNodeCard key={node.id} node={node} />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function OrgNodeCard({ node }: { node: OrgNode }) {
  const tone = highlightColors[node.highlight] ?? '#38bdf8';
  return (
    <div
      style={{
        flex: '1 1 240px',
        borderRadius: '16px',
        border: '1px solid #1f2937',
        padding: '16px',
        background: 'linear-gradient(135deg, rgba(15,23,42,0.9), rgba(2,6,23,0.9))',
      }}
    >
      <p style={{ color: tone, letterSpacing: '0.2em', fontSize: '10px', textTransform: 'uppercase' }}>{node.role}</p>
      <h3 style={{ color: 'white', fontSize: '18px', fontWeight: 600, margin: '4px 0 8px' }}>{node.name}</h3>
      <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '8px' }}>{node.description}</p>
      {node.responsibilities && node.responsibilities.length > 0 && (
        <ul style={{ color: '#cbd5f5', fontSize: '13px', marginLeft: '16px', marginBottom: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {node.responsibilities.map((item) => (
            <li key={`${node.id}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          borderRadius: '999px',
          border: '1px solid #1f2937',
          padding: '6px 12px',
          color: node.status === 'active' ? '#22c55e' : '#fbbf24',
          fontSize: '12px',
          backgroundColor: '#0f172a',
        }}
      >
        <span style={{ width: '6px', height: '6px', borderRadius: '999px', backgroundColor: node.status === 'active' ? '#22c55e' : tone }} />
        {statusLabels[node.status]}
      </span>
    </div>
  );
}

function groupPmCards(cards: PMCard[]) {
  return cards.reduce(
    (acc, card) => {
      const normalized = normalizeStatus(card.status);
      if (normalized === 'blocked') {
        acc.todo.push(card);
      } else {
        acc[normalized].push(card);
      }
      return acc;
    },
    { todo: [] as PMCard[], in_progress: [] as PMCard[], review: [] as PMCard[], done: [] as PMCard[] },
  );
}

function groupExecutionQueue(entries: ExecutionQueueEntry[]) {
  return entries.reduce(
    (acc, entry) => {
      const normalized = normalizeExecutionState(entry.execution_state);
      acc[normalized].push(entry);
      return acc;
    },
    {
      ready: [] as ExecutionQueueEntry[],
      queued: [] as ExecutionQueueEntry[],
      running: [] as ExecutionQueueEntry[],
      review: [] as ExecutionQueueEntry[],
      failed: [] as ExecutionQueueEntry[],
      done: [] as ExecutionQueueEntry[],
    },
  );
}

function workspaceKeyFromCard(card: PMCard) {
  const payload = (card.payload ?? {}) as Record<string, unknown>;
  for (const key of ['workspace_key', 'workspace', 'belongs_to_workspace']) {
    const value = payload[key];
    if (typeof value === 'string' && value.trim()) {
      return normalizeWorkspaceBoardKey(value);
    }
  }
  return 'shared_ops';
}

function normalizeWorkspaceBoardKey(value?: string | null) {
  const normalized = (value ?? '').trim().toLowerCase();
  if (normalized === 'feezie-os') {
    return 'linkedin-os';
  }
  return (value ?? '').trim() || 'shared_ops';
}

function pmReviewPolicyFromCard(card?: PMCard | null): PMReviewPolicyPayload | null {
  const payload = (card?.payload ?? {}) as Record<string, unknown>;
  if (!payload.pm_review_policy || typeof payload.pm_review_policy !== 'object') {
    return null;
  }
  return payload.pm_review_policy as PMReviewPolicyPayload;
}

function meetingLabelForWorkspace(workspaceKey: string) {
  switch (workspaceKey) {
    case 'shared_ops':
      return 'Executive / Operations';
    case 'linkedin-os':
      return 'FEEZIE OS';
    case 'fusion-os':
      return 'Fusion';
    case 'easyoutfitapp':
      return 'Easy Outfit';
    case 'ai-swag-store':
      return 'AI Swag Store';
    case 'agc':
      return 'AGC';
    default:
      return workspaceKey || 'Shared Ops';
  }
}

const WORKSPACE_BOARD_THEME: Record<string, { accent: string; background: string; border: string }> = {
  shared_ops: { accent: '#f59e0b', background: 'rgba(245, 158, 11, 0.08)', border: 'rgba(245, 158, 11, 0.28)' },
  'linkedin-os': { accent: '#38bdf8', background: 'rgba(56, 189, 248, 0.08)', border: 'rgba(56, 189, 248, 0.28)' },
  'fusion-os': { accent: '#34d399', background: 'rgba(52, 211, 153, 0.08)', border: 'rgba(52, 211, 153, 0.28)' },
  easyoutfitapp: { accent: '#fb7185', background: 'rgba(251, 113, 133, 0.08)', border: 'rgba(251, 113, 133, 0.28)' },
  'ai-swag-store': { accent: '#facc15', background: 'rgba(250, 204, 21, 0.08)', border: 'rgba(250, 204, 21, 0.28)' },
  agc: { accent: '#c084fc', background: 'rgba(192, 132, 252, 0.08)', border: 'rgba(192, 132, 252, 0.28)' },
};

function workspaceBoardTheme(workspaceKey: string) {
  return (
    WORKSPACE_BOARD_THEME[workspaceKey] ?? {
      accent: '#94a3b8',
      background: 'rgba(148, 163, 184, 0.08)',
      border: 'rgba(148, 163, 184, 0.22)',
    }
  );
}

const WORKSPACE_RUNTIME_DISPLAY: Record<string, { targetAgent: string; workspaceAgent: string | null; legacyAliases: string[] }> = {
  'shared_ops': { targetAgent: 'Jean-Claude', workspaceAgent: null, legacyAliases: [] },
  'linkedin-os': { targetAgent: 'Jean-Claude', workspaceAgent: null, legacyAliases: [] },
  'fusion-os': {
    targetAgent: 'Fusion Systems Operator',
    workspaceAgent: 'Fusion Systems Operator',
    legacyAliases: ['Fusion Agent'],
  },
  easyoutfitapp: {
    targetAgent: 'Easy Outfit Product Agent',
    workspaceAgent: 'Easy Outfit Product Agent',
    legacyAliases: ['Easy Outfit Agent'],
  },
  'ai-swag-store': {
    targetAgent: 'Commerce Growth Agent',
    workspaceAgent: 'Commerce Growth Agent',
    legacyAliases: ['AI Swag Store Agent', 'Commerce Agent'],
  },
  agc: {
    targetAgent: 'AGC Strategy Agent',
    workspaceAgent: 'AGC Strategy Agent',
    legacyAliases: ['AGC Agent'],
  },
};

function displayManagerAgent(_workspaceKey: string | null | undefined, managerAgent?: string | null) {
  return managerAgent || 'Jean-Claude';
}

function displayTargetAgent(workspaceKey: string | null | undefined, targetAgent?: string | null) {
  const contract = WORKSPACE_RUNTIME_DISPLAY[workspaceKey ?? ''];
  if (!contract) {
    return targetAgent || 'Jean-Claude';
  }
  if (!targetAgent) {
    return contract.targetAgent;
  }
  const normalized = targetAgent.trim().toLowerCase();
  if (contract.legacyAliases.some((alias) => alias.toLowerCase() === normalized)) {
    return contract.targetAgent;
  }
  return targetAgent;
}

function displayWorkspaceAgent(workspaceKey: string | null | undefined, workspaceAgent?: string | null) {
  const contract = WORKSPACE_RUNTIME_DISPLAY[workspaceKey ?? ''];
  if (!contract) {
    return workspaceAgent || 'Workspace Agent';
  }
  if (!workspaceAgent) {
    return contract.workspaceAgent || 'Workspace Agent';
  }
  const normalized = workspaceAgent.trim().toLowerCase();
  if (contract.legacyAliases.some((alias) => alias.toLowerCase() === normalized)) {
    return contract.workspaceAgent || workspaceAgent;
  }
  return workspaceAgent;
}

function summarizeAutomationSources(automations: Automation[]) {
  return automations.reduce(
    (acc, automation) => {
      acc.total += 1;
      const source = (automation.source ?? '').toLowerCase();
      const runtime = (automation.runtime ?? '').toLowerCase();
      const channel = (automation.channel ?? '').toLowerCase();
      const isOpenclaw = source === 'openclaw_jobs_json' || runtime.includes('openclaw') || channel.startsWith('openclaw');
      const isLaunchd = source.includes('launchd') || runtime.includes('launchd') || runtime.includes('local_launchd');
      const isLocal = isLaunchd || source.includes('local') || runtime.includes('local machine');
      if (isOpenclaw) {
        acc.openclaw += 1;
      }
      if (isLaunchd) {
        acc.launchd += 1;
      }
      if (isLocal) {
        acc.local += 1;
      }
      return acc;
    },
    { openclaw: 0, local: 0, launchd: 0, total: 0 },
  );
}

function buildPmLaneSummary(cards: PMCard[]) {
  const byWorkspace: Record<string, number> = {};
  cards.forEach((card) => {
    const workspaceKey = workspaceKeyFromCard(card);
    byWorkspace[workspaceKey] = (byWorkspace[workspaceKey] ?? 0) + 1;
  });
  const workspaceKeys = Object.keys(byWorkspace);
  return {
    byWorkspace,
    sharedOps: byWorkspace.shared_ops ?? 0,
    workspaceLanes: workspaceKeys.filter((key) => key !== 'shared_ops').length,
  };
}

function buildUnifiedOpsBoard(cards: PMCard[], executionQueue: ExecutionQueueEntry[]) {
  const byCardId = new Map(cards.map((card) => [card.id, card]));
  const seen = new Set<string>();
  const lanes: Record<UnifiedBoardLaneKey, UnifiedBoardItem[]> = {
    todo: [],
    ready: [],
    queued: [],
    running: [],
    review: [],
    failed: [],
    done: [],
  };

  executionQueue.forEach((entry) => {
    const card = byCardId.get(entry.card_id);
    const lane = normalizeExecutionState(entry.execution_state);
    lanes[lane].push({
      id: `execution-${entry.card_id}`,
      cardId: entry.card_id,
      title: entry.title,
      workspaceKey: normalizeWorkspaceBoardKey(entry.workspace_key ?? 'shared_ops'),
      lane,
      pmStatus: entry.pm_status,
      executionState: entry.execution_state,
      managerAgent: entry.manager_agent,
      targetAgent: entry.target_agent,
      workspaceAgent: entry.workspace_agent,
      executionMode: entry.execution_mode,
      reason: entry.reason,
      source: entry.source ?? card?.source ?? null,
      owner: card?.owner ?? null,
      updatedAt: entry.last_transition_at ?? card?.updated_at ?? card?.created_at ?? null,
      dueAt: card?.due_at ?? null,
      queueEntry: entry,
      pmReviewPolicy: pmReviewPolicyFromCard(card),
    });
    seen.add(entry.card_id);
  });

  cards.forEach((card) => {
    if (seen.has(card.id)) {
      return;
    }
    const normalized = normalizeStatus(card.status);
    const lane: UnifiedBoardLaneKey =
      normalized === 'in_progress' ? 'running' : normalized === 'review' ? 'review' : normalized === 'done' ? 'done' : 'todo';
    lanes[lane].push({
      id: `card-${card.id}`,
      cardId: card.id,
      title: card.title,
      workspaceKey: workspaceKeyFromCard(card),
      lane,
      pmStatus: card.status,
      reason: typeof card.payload?.reason === 'string' ? card.payload.reason : null,
      source: card.source ?? null,
      owner: card.owner ?? null,
      updatedAt: card.updated_at ?? card.created_at ?? null,
      dueAt: card.due_at ?? null,
      queueEntry: null,
      pmReviewPolicy: pmReviewPolicyFromCard(card),
    });
  });

  const sortItems = (items: UnifiedBoardItem[]) =>
    items.sort((left, right) => {
      const leftTime = left.updatedAt ? new Date(left.updatedAt).getTime() : 0;
      const rightTime = right.updatedAt ? new Date(right.updatedAt).getTime() : 0;
      return rightTime - leftTime;
    });

  (Object.keys(lanes) as UnifiedBoardLaneKey[]).forEach((key) => {
    sortItems(lanes[key]);
  });

  return lanes;
}

function isOwnerReviewDecisionItem(item: UnifiedBoardItem) {
  return item.lane === 'review' && (item.source ?? '').includes('workspace-owner-review') && item.pmReviewPolicy?.attention_class === 'needs_owner';
}

function applyOwnerReviewWipLimit(board: Record<UnifiedBoardLaneKey, UnifiedBoardItem[]>) {
  const reviewItems = board.review ?? [];
  const visibleOwnerReviewIds = new Set(
    reviewItems.filter(isOwnerReviewDecisionItem).slice(0, OWNER_REVIEW_ACTIVE_WIP_LIMIT).map((item) => item.cardId),
  );
  const hiddenOwnerReviewItems = reviewItems.filter((item) => isOwnerReviewDecisionItem(item) && !visibleOwnerReviewIds.has(item.cardId));
  if (hiddenOwnerReviewItems.length === 0) {
    return { board, hiddenOwnerReviewItems: [] as UnifiedBoardItem[] };
  }
  const hiddenIds = new Set(hiddenOwnerReviewItems.map((item) => item.cardId));
  return {
    board: {
      ...board,
      review: reviewItems.filter((item) => !hiddenIds.has(item.cardId)),
    },
    hiddenOwnerReviewItems,
  };
}

function parseUpdatedAtMillis(value?: string | null) {
  if (!value) {
    return 0;
  }
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function isLikelyStaleBoardItem(item: UnifiedBoardItem) {
  if (item.pmReviewPolicy?.attention_class === 'stale' || item.pmReviewPolicy?.auto_resolve_eligible) {
    return true;
  }
  if (item.lane !== 'review') {
    return false;
  }
  const updatedAt = parseUpdatedAtMillis(item.updatedAt);
  const ageHours = updatedAt > 0 ? (Date.now() - updatedAt) / 3_600_000 : 0;
  const reason = String(item.reason ?? '').toLowerCase();
  const sweepReroute = reason.includes('accountability sweep rerouted this stale');
  return sweepReroute || ageHours >= 72;
}

function buildOwnerAttentionItems(items: UnifiedBoardItem[]): OwnerAttentionItem[] {
  const ranked = items
    .filter((item) => item.lane !== 'done')
    .map((item) => {
      const stale = isLikelyStaleBoardItem(item);
      const attentionClass = item.pmReviewPolicy?.attention_class;
      let kind: OwnerAttentionKind = 'update';
      let summary = 'This lane is moving or parked in the background. You usually do not need to do anything right now.';
      let nextAction = 'Ignore it unless priorities changed.';

      if (attentionClass === 'needs_owner') {
        kind = 'decision';
        summary = item.pmReviewPolicy?.attention_reason ?? 'This card still needs a human decision.';
        const isPendingOwnerReview =
          item.lane === 'review' && String(item.reason ?? '').toLowerCase().includes('owner decision needed');
        nextAction = isPendingOwnerReview
          ? 'Open it and choose approve, request revision, or park.'
          : item.lane === 'review'
            ? 'Open it and resolve the returned result.'
            : 'Open it and decide the next step.';
      } else if (attentionClass === 'needs_host') {
        kind = 'decision';
        summary = item.pmReviewPolicy?.attention_reason ?? 'This card needs a host action outside the runtime.';
        nextAction = 'Open it, complete the host step, and mark it complete.';
      } else if (stale) {
        kind = 'stale';
        summary = item.pmReviewPolicy?.attention_reason ?? 'This card was pulled back up by the system and may already be handled outside PM.';
        nextAction = 'Open it. If already solved, close it. If still real, send it back into work.';
      } else if (attentionClass === 'autonomous') {
        kind = 'update';
        summary = item.pmReviewPolicy?.attention_reason ?? 'This workspace is configured to keep this type of result moving on its own.';
        nextAction =
          item.pmReviewPolicy?.recommended_resolution_mode === 'close_and_spawn_next'
            ? 'Open it only if you want to inspect or override the default follow-up.'
            : 'Ignore it unless you want to inspect or override the default closeout.';
      } else if (item.lane === 'review') {
        kind = 'update';
        summary = 'This review card is visible for context, but PM did not mark it as a required human decision.';
        nextAction = 'Ignore it unless you want to inspect the result or override the default workflow.';
      } else if (item.lane === 'failed') {
        kind = 'update';
        summary = 'This is a system-recovery lane, not a fresh owner decision.';
        nextAction = 'Ignore it unless you want to work the recovery path directly.';
      } else if (item.lane === 'ready') {
        kind = 'update';
        summary = 'This card is ready to start, but nothing is broken if you leave it alone.';
        nextAction = 'Only open it if you want the system to begin that work now.';
      } else if (item.lane === 'todo') {
        kind = 'update';
        summary = 'This is backlog, not an urgent decision.';
        nextAction = 'Ignore it unless you want to reprioritize backlog.';
      }

      const rank = kind === 'decision' ? 0 : kind === 'stale' ? 1 : 2;
      return {
        cardId: item.cardId,
        title: item.title,
        workspaceKey: item.workspaceKey,
        kind,
        attentionClass,
        lane: item.lane,
        summary,
        nextAction,
        updatedAt: item.updatedAt,
        rank,
        updatedAtMillis: parseUpdatedAtMillis(item.updatedAt),
      };
    });

  return ranked
    .sort((left, right) => {
      if (left.rank !== right.rank) {
        return left.rank - right.rank;
      }
      return right.updatedAtMillis - left.updatedAtMillis;
    })
    .map(({ rank: _rank, updatedAtMillis: _updatedAtMillis, ...item }) => item);
}

function describeAutoProgressItem(item: PMAutoProgressItem & { processed_at?: string }) {
  if (item.action === 'return') {
    return `${meetingLabelForWorkspace(item.workspace_key)}: returned to execution because the completion contract was not met yet.`;
  }
  if (item.action === 'blocked') {
    return `${meetingLabelForWorkspace(item.workspace_key)}: escalated for human attention after repeated automatic passes failed.`;
  }
  if (item.host_action_card_title) {
    return `${meetingLabelForWorkspace(item.workspace_key)}: accepted automatically and routed the remaining external step into "${item.host_action_card_title}".`;
  }
  if (item.resolution_mode === 'close_and_spawn_next') {
    const successor = item.successor_card_title ? ` Next card: ${item.successor_card_title}.` : '';
    return `${meetingLabelForWorkspace(item.workspace_key)}: accepted automatically and continued into the next PM lane.${successor}`;
  }
  return `${meetingLabelForWorkspace(item.workspace_key)}: accepted automatically and closed as routine system work.`;
}

function autoProgressSourceTitle(item: PMAutoProgressItem & { processed_at?: string }) {
  return `Source card: ${item.title}`;
}

function describeAutoProgressOutcome(item: PMAutoProgressItem & { processed_at?: string }) {
  if (item.action === 'return') {
    return 'Outcome: sent back into execution. This is a past automatic decision, not a live task.';
  }
  if (item.action === 'blocked') {
    return 'Outcome: escalated for human attention after the automatic path failed. This entry is history, not the action surface.';
  }
  if (item.host_action_card_title) {
    return `Outcome: spawned host step "${item.host_action_card_title}". Work that card from What Needs You if it appears there.`;
  }
  if (item.resolution_mode === 'close_and_spawn_next') {
    if (item.successor_card_title && item.successor_card_title !== item.title) {
      return `Outcome: spawned successor lane "${item.successor_card_title}". This row records the prior automatic decision only.`;
    }
    if (item.successor_card_title) {
      return 'Outcome: spawned a successor lane with the same title. This row is the earlier resolved event, not the current task.';
    }
    return 'Outcome: continued into the next PM lane. This row is history only.';
  }
  return 'Outcome: closed automatically as routine system work.';
}

function boardItemGuidance(item: UnifiedBoardItem): BoardItemGuidance {
  if (item.pmReviewPolicy?.attention_class === 'needs_host') {
    return {
      summary: 'This card is not waiting on more system execution. The runtime finished its side and now needs a host action outside the system.',
      userRole: 'Decide whether you completed the external step. If yes, confirm it and optionally leave one sentence of context.',
      nextAction: 'Open the card, decide yes or no, and only add a note if nuance matters.',
    };
  }
  if ((item.source ?? '').includes('workspace-owner-review') && item.lane === 'review') {
    return {
      summary: 'This card is waiting on an owner decision for a FEEZIE draft, not on more agent execution.',
      userRole: 'Read the draft, decide approve, revise, or park, and let PM mutate the downstream lane from that judgment.',
      nextAction: 'Open the card, review the first-pass copy, and make the owner call from the Actions block.',
    };
  }
  if (item.pmReviewPolicy?.attention_class === 'autonomous' && item.lane === 'review') {
    return {
      summary: 'This workspace is configured to keep accepted review results moving without asking you for routine closure.',
      userRole: 'Only step in if you want to inspect or override the default follow-through.',
      nextAction:
        item.pmReviewPolicy?.recommended_resolution_mode === 'close_and_spawn_next'
          ? 'Use the prefilled resolve settings if you want to accept the result and keep the loop moving.'
          : 'Use the preselected resolve settings if you want to accept the result as routine system work.',
    };
  }
  if (isLikelyStaleBoardItem(item)) {
    return {
      summary: 'This card was resurfaced by the accountability sweep and may already be solved outside PM.',
      userRole: 'Confirm whether this is still real work or just stale system residue.',
      nextAction: 'If it is already handled, close it. If it still matters, resolve it into the next concrete card.',
    };
  }
  switch (item.lane) {
    case 'todo':
      if (isHeldPmLayerStatus(item.pmStatus, item.lane, item.executionState)) {
        return {
          summary: 'This card is being held at the PM layer. A blocking judgment exists, but the work is not currently in an active execution lane.',
          userRole: 'Decide whether the card should remain held, be clarified, or be re-opened into execution.',
          nextAction: 'If the blocker is resolved, move it back toward Ready or return it to Jean-Claude with clearer direction.',
        };
      }
      return {
        summary: 'This card is recognized work on the PM board, but it has not entered the execution loop yet.',
        userRole: 'Decide whether this should stay as backlog, be clarified, or be moved into execution.',
        nextAction: 'If this is mature enough to execute, move it toward Ready by giving it a clear owner and execution path.',
      };
    case 'ready':
      return {
        summary: 'This card is execution-ready. Jean-Claude has enough structure to open the SOP and start the lane.',
        userRole: 'Pressure-test whether the work is framed correctly before the system opens the lane.',
        nextAction: 'Use Open SOP if the card is clear and you want the system to start work now.',
      };
    case 'queued':
      if (normalizeStatus(item.pmStatus) === 'blocked') {
        return {
          summary: 'This card has been marked blocked and rerouted back toward Jean-Claude, but it is still sitting inside an active queue.',
          userRole: 'Treat this as a manager-attention lane. The work needs clarification before normal execution resumes.',
          nextAction: 'Resolve the blocker or return the card to a clean execution path.',
        };
      }
      return {
        summary: 'Jean-Claude has already opened the lane. The work is staged and waiting for pickup or handoff.',
        userRole: 'Mostly observe. Step in only if this queue state is lingering too long.',
        nextAction: 'Let the runner pick it up, or intervene if the queued state starts aging.',
      };
    case 'running':
      return {
        summary: 'The work is actively being executed, either directly by Jean-Claude or by a delegated workspace agent.',
        userRole: 'Watch progress and check for drift, but do not interrupt unless the lane is stuck or the goal changed.',
        nextAction: 'Review the execution context and wait for a result to return into Review.',
      };
    case 'review':
      return {
        summary: 'A result came back from execution. The system is waiting for a closure judgment, not more speculation.',
        userRole: 'Decide whether the result is good enough to close, needs another pass, or should be blocked and rerouted.',
        nextAction: 'Use the returned context to close the card or send it back into execution with clearer direction.',
      };
    case 'failed':
      return {
        summary: 'This is a failed autonomous or execution lane. It belongs on the system-recovery surface, not in the normal owner inbox.',
        userRole: 'Use it when you intentionally want to recover a broken lane by clarifying the blocker or rerunning repo-side work.',
        nextAction: 'Open it only if you want to work recovery directly; otherwise leave it visible as system recovery.',
      };
    case 'done':
      return {
        summary: 'This card is closed. It stays here as traceable history, not as active work.',
        userRole: 'Use it for reference, proof, or context when you want to understand what already got finished.',
        nextAction: 'No action is required unless you are reopening or learning from the completed lane.',
      };
    default:
      return {
        summary: 'This card is part of the PM and execution system.',
        userRole: 'Understand the current state before you change anything.',
        nextAction: 'Use the lane and ownership context to decide the next step.',
      };
  }
}

function findStandupPrepForRoom(
  room: { key: string; workspaceKey: string },
  standupPreps: StandupPrepPacket[],
) {
  const exact = standupPreps.find((prep) => prep.standupKind === room.key);
  if (exact) {
    return exact;
  }
  if (room.workspaceKey === 'shared_ops') {
    return null;
  }
  return standupPreps.find((prep) => prep.workspaceKey === room.workspaceKey) ?? null;
}

function findLiveStandupEntry(
  room: { key: string; workspaceKey: string },
  entries: StandupEntry[],
) {
  const exact = entries.find((entry) => {
    const kind = typeof entry.payload?.standup_kind === 'string' ? entry.payload.standup_kind : null;
    return kind === room.key;
  });
  if (exact) {
    return exact;
  }
  if (room.workspaceKey === 'shared_ops') {
    return null;
  }
  return entries.find((entry) => (entry.workspace_key ?? 'shared_ops') === room.workspaceKey) ?? null;
}

function findRecommendationPacketForRoom(
  room: { workspaceKey: string },
  packets: PMRecommendationPacket[],
) {
  return packets.find((packet) => packet.workspaceKey === room.workspaceKey) ?? null;
}

function buildStandupPromotionPayload(
  prep: StandupPrepPacket,
  recommendationPacket: PMRecommendationPacket | null,
  chronicleEntry: ChronicleEntry | null,
) {
  const includeYoda = shouldIncludeYoda(prep);
  const participants = includeYoda ? ['Jean-Claude', 'Neo', 'Yoda'] : ['Jean-Claude', 'Neo'];
  const pmUpdates =
    recommendationPacket?.items.map((item) => ({
      workspace_key: item.workspaceKey,
      scope: item.scope,
      owner_agent: item.ownerAgent,
      title: item.title,
      status: item.status,
      reason: item.reason,
      payload: {
        recommendation_path: recommendationPacket.path,
        created_from_prep_id: prep.id,
      },
    })) ?? [];
  const decisions = buildStandupDecisions(prep, pmUpdates);
  const owners = buildStandupOwners(prep, includeYoda);
  const discussionRounds = buildStandupDiscussionRounds(prep, chronicleEntry, decisions, owners, includeYoda);

  return {
    standup_kind: prep.standupKind,
    owner: 'Jean-Claude',
    workspace_key: prep.workspaceKey,
    summary: prep.summary,
    agenda: prep.agenda,
    blockers: prep.blockers,
    commitments: prep.commitments,
    needs: prep.needs,
    decisions,
    owners,
    artifact_deltas: prep.artifactDeltas,
    source: 'standup_prep',
    conversation_path: prep.path,
    source_paths: prep.sourcePaths,
    memory_promotions: prep.memoryPromotions,
    pm_snapshot: prep.pmSnapshot ?? {},
    participants,
    discussion_rounds: discussionRounds,
    jean_claude_note: buildJeanClaudeStandupNote(prep),
    neo_note: buildNeoStandupNote(prep, decisions),
    yoda_note: includeYoda ? buildYodaStandupNote(prep, chronicleEntry) : null,
    prep_id: prep.id,
    recommendation_path: recommendationPacket?.path ?? null,
    pm_updates: pmUpdates,
  };
}

function shouldIncludeYoda(prep: StandupPrepPacket) {
  return prep.workspaceKey === 'shared_ops' || prep.workspaceKey === 'linkedin-os';
}

function buildJeanClaudeStandupNote(prep: StandupPrepPacket) {
  const pmLines = extractPmSnapshotLines(prep.pmSnapshot);
  const agendaLead = prep.agenda[0];
  const deltaLead = prep.artifactDeltas[0];
  const parts = [pmLines[0], agendaLead ? `Agenda starts with ${agendaLead}` : null, deltaLead ? `Latest delta: ${deltaLead}` : null]
    .filter((item): item is string => Boolean(item));
  return parts.join(' ') || prep.summary;
}

function buildNeoStandupNote(prep: StandupPrepPacket, decisions: string[]) {
  if (decisions.length > 0) {
    return `Keep the board as the source of truth. Pressure-test ${decisions[0]} and expand scope only if the current lane is actually clear.`;
  }
  return 'Keep the PM board ahead of narrative. If there is no clear board move, say nothing is ready and leave the lane alone.';
}

function buildYodaStandupNote(prep: StandupPrepPacket, chronicleEntry: ChronicleEntry | null) {
  const chronicleContext = chronicleEntry?.summary ? `Current Chronicle signal: ${summarize(chronicleEntry.summary, 110)}` : 'Current Chronicle signal is still consolidating.';
  if (prep.workspaceKey === 'linkedin-os') {
    return `Protect the North Star: FEEZIE OS should strengthen Johnnie's brand, career, and long-term positioning through the current LinkedIn lane and the broader public system it is becoming. ${chronicleContext}`;
  }
  return `Protect the why behind the system: this work should deepen Johnnie's second-brain, preserve his voice, and keep execution aligned with the broader AI project rather than generic automation. ${chronicleContext}`;
}

function buildStandupDecisions(
  prep: StandupPrepPacket,
  pmUpdates: Array<{ title: string }>,
) {
  const lines = extractPmSnapshotLines(prep.pmSnapshot);
  const decisions: string[] = [];
  if (lines.some((line) => line.toLowerCase().includes('blocked'))) {
    decisions.push('Resolve blocked PM work before additional scope enters the lane.');
  }
  pmUpdates.slice(0, 2).forEach((item) => {
    if (item.title.trim()) {
      decisions.push(`Create or queue ${item.title} on the PM board.`);
    }
  });
  if (decisions.length === 0 && prep.commitments.length > 0) {
    decisions.push(`Keep ${prep.commitments[0]} moving and revisit it at the next standup.`);
  }
  if (decisions.length === 0) {
    decisions.push('Nothing to report. Leave the board unchanged and wait for the next real signal.');
  }
  return decisions.slice(0, 5);
}

function buildStandupOwners(prep: StandupPrepPacket, includeYoda: boolean) {
  const owners = ['Jean-Claude — update the PM board, open the next SOP, and carry the lane summary back to leadership.'];
  const workspaceOwners: Record<string, string> = {
    'fusion-os': 'Fusion Systems Operator',
    easyoutfitapp: 'Easy Outfit Product Agent',
    'ai-swag-store': 'Commerce Growth Agent',
    agc: 'AGC Strategy Agent',
  };
  if (!['shared_ops', 'linkedin-os'].includes(prep.workspaceKey)) {
    owners.push(`${workspaceOwners[prep.workspaceKey] ?? 'Workspace Agent'} — execute inside ${prep.workspaceKey} only and report back through workspace memory plus the PM card.`);
  }
  if (includeYoda) {
    owners.push('Yoda — challenge whether the next move still aligns with the North Star before scope expands.');
  }
  return owners;
}

function buildStandupDiscussionRounds(
  prep: StandupPrepPacket,
  chronicleEntry: ChronicleEntry | null,
  decisions: string[],
  owners: string[],
  includeYoda: boolean,
) {
  const rounds: Array<Record<string, unknown>> = [
    {
      round: 1,
      speaker: 'Jean-Claude',
      role: 'workspace-president',
      note: buildJeanClaudeStandupNote(prep),
      focus: 'pm_board_first',
    },
    {
      round: 2,
      speaker: 'Neo',
      role: 'system-operator',
      note: buildNeoStandupNote(prep, decisions),
      focus: 'priority_and_scope',
    },
  ];
  if (includeYoda) {
    rounds.push({
      round: 3,
      speaker: 'Yoda',
      role: 'strategic-overlay',
      note: buildYodaStandupNote(prep, chronicleEntry),
      focus: 'north_star',
    });
  }
  rounds.push({
    round: includeYoda ? 4 : 3,
    speaker: 'Jean-Claude',
    role: 'workspace-president',
    note: `Decision set: ${decisions.slice(0, 2).join('; ')} Owners: ${owners.slice(0, 2).join(' ')}`,
    focus: 'decision_and_handoff',
  });
  return rounds;
}

function extractStandupDiscussion(payload?: Record<string, unknown>) {
  const discussion = Array.isArray(payload?.discussion) ? payload?.discussion : [];
  return discussion
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }
      const round = typeof item.round === 'number' ? `Round ${item.round} · ` : '';
      const speaker = typeof item.speaker === 'string' ? item.speaker : 'Unknown';
      const note = typeof item.note === 'string' ? item.note : '';
      if (!note.trim()) {
        return null;
      }
      return `${round}${speaker}: ${note}`;
    })
    .filter((item): item is string => Boolean(item));
}

function extractStandupList(payload: Record<string, unknown> | undefined, key: string) {
  const items = payload?.[key];
  return Array.isArray(items) ? items.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

function extractStandupSections(payload: Record<string, unknown> | undefined) {
  const raw = payload?.standup_sections;
  const record = raw && typeof raw === 'object' && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  const sectionConfig = [
    ['signals_captured', 'Signals Captured'],
    ['content_produced', 'Content Produced'],
    ['audience_response', 'Audience Response'],
    ['opportunities_created', 'Opportunities Created'],
    ['next_focus', 'Next Focus'],
  ] as const;
  return sectionConfig
    .map(([key, title]) => ({
      key,
      title,
      items: extractStandupList(record, key),
    }))
    .filter((section) => section.items.length > 0);
}

function standupParticipants(entry: StandupEntry) {
  return standupParticipantBuckets(entry).merged;
}

function standupRecordProvenance(entry: StandupEntry): StandupRecordProvenance {
  const payload = entry.payload ?? {};
  const source = (entry.source ?? '').toLowerCase();
  const conversationPath = (entry.conversation_path ?? '').toLowerCase();
  const hasPrepId = typeof payload.prep_id === 'string' && payload.prep_id.trim().length > 0;
  const hasDiscussion = standupDiscussion(entry).length > 0;
  const hasSourcePaths = Array.isArray(payload.source_paths) && payload.source_paths.length > 0;
  const transcriptLikeSource =
    ['transcript', 'meeting_watchdog', 'meeting_transcript', 'room_capture'].some((token) => source.includes(token)) ||
    conversationPath.includes('/transcripts/') ||
    conversationPath.endsWith('.vtt') ||
    conversationPath.endsWith('.srt');

  if (source === 'standup_prep' || hasPrepId) {
    return {
      label: 'Generated from standup prep',
      tone: '#fbbf24',
      background: 'rgba(251, 191, 36, 0.10)',
      border: 'rgba(251, 191, 36, 0.30)',
      description: 'This meeting record was promoted from a prep packet. It is operationally useful, but the attendees and dialogue may be system-shaped rather than a literal transcript.',
    };
  }

  if (source === 'brain_triage') {
    return {
      label: 'Hybrid record',
      tone: '#38bdf8',
      background: 'rgba(56, 189, 248, 0.10)',
      border: 'rgba(56, 189, 248, 0.30)',
      description: 'This record came from routed Brain signal and was structured into a standup shape. It reflects real signal, but not necessarily a verbatim meeting.',
    };
  }

  if (transcriptLikeSource && hasDiscussion) {
    return {
      label: 'Transcript-backed',
      tone: '#22c55e',
      background: 'rgba(34, 197, 94, 0.10)',
      border: 'rgba(34, 197, 94, 0.30)',
      description: 'This record points to transcript-like meeting evidence and stored discussion rounds, so it is the closest thing here to what was actually said in the room.',
    };
  }

  if (hasDiscussion || hasSourcePaths || conversationPath) {
    return {
      label: 'Hybrid record',
      tone: '#38bdf8',
      background: 'rgba(56, 189, 248, 0.10)',
      border: 'rgba(56, 189, 248, 0.30)',
      description: 'This record mixes captured context with operator or system shaping. Treat it as a useful recap, not a word-for-word transcript.',
    };
  }

  return {
    label: 'Sparse record',
    tone: '#94a3b8',
    background: 'rgba(148, 163, 184, 0.08)',
    border: 'rgba(148, 163, 184, 0.22)',
    description: 'Only minimal meeting metadata is stored here, so this should be treated as a placeholder record rather than reliable meeting evidence.',
  };
}

function summarizePathForDisplay(path: string) {
  const parts = path.split('/').filter(Boolean);
  if (parts.length <= 3) {
    return path;
  }
  return `.../${parts.slice(-3).join('/')}`;
}

function normalizePathSegments(path: string) {
  const absolute = path.startsWith('/');
  const segments = path.split('/').filter((segment) => segment.length > 0 && segment !== '.');
  const normalized: string[] = [];
  segments.forEach((segment) => {
    if (segment === '..') {
      if (normalized.length > 0) {
        normalized.pop();
      }
      return;
    }
    normalized.push(segment);
  });
  return `${absolute ? '/' : ''}${normalized.join('/')}`;
}

function stripLeadingRelativeSegments(path: string) {
  return path.replace(/^(?:\.\.\/|\.\/)+/, '');
}

function workspaceRootForKey(workspaceKey?: string | null) {
  return WORKSPACE_ROOT_BY_KEY[normalizeWorkspaceBoardKey(workspaceKey)] ?? REPO_ROOT;
}

function resolveCodexArtifactPath(path: string, workspaceKey?: string | null) {
  const trimmed = path.trim();
  if (!trimmed) {
    return '';
  }
  if (trimmed.startsWith('/')) {
    return normalizePathSegments(trimmed);
  }

  const stripped = stripLeadingRelativeSegments(trimmed);
  if (REPO_RELATIVE_PREFIXES.some((prefix) => stripped.startsWith(prefix))) {
    return normalizePathSegments(`${REPO_ROOT}/${stripped}`);
  }
  if (WORKSPACE_RELATIVE_PREFIXES.some((prefix) => trimmed.startsWith(prefix) || stripped.startsWith(prefix))) {
    return normalizePathSegments(`${workspaceRootForKey(workspaceKey)}/${stripped}`);
  }

  if (trimmed.startsWith('../') || trimmed.startsWith('./')) {
    return normalizePathSegments(`${REPO_ROOT}/${stripped}`);
  }

  return normalizePathSegments(`${workspaceRootForKey(workspaceKey)}/${trimmed}`);
}

function extractPmSnapshotLines(snapshot: unknown) {
  if (!snapshot || typeof snapshot !== 'object') {
    return [];
  }
  const lines = (snapshot as Record<string, unknown>).lines;
  return Array.isArray(lines) ? lines.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

type MarkdownSubsection = {
  title: string;
  body: string;
  fields: Record<string, string>;
};

function findWorkspaceFile(files: WorkspaceFile[], suffix: string) {
  return files.find((file) => file.path.endsWith(suffix)) ?? null;
}

function findWorkspaceFileBySourcePath(files: WorkspaceFile[], sourcePath: string) {
  return files.find((file) => file.path.endsWith(sourcePath)) ?? null;
}

function findDocBySourcePath(docs: DocReference[], sourcePath: string) {
  return docs.find((doc) => doc.path === sourcePath || doc.path.endsWith(sourcePath)) ?? null;
}

function normalizeLensText(value: unknown) {
  return typeof value === 'string'
    ? value
        .toLowerCase()
        .replace(/[`'".,/_-]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
    : '';
}

function collectLensText(item: unknown) {
  if (!item || typeof item !== 'object') {
    return '';
  }
  return Object.values(item as Record<string, unknown>)
    .filter((value) => typeof value === 'string')
    .map((value) => normalizeLensText(value))
    .join(' ');
}

function matchesWorkspaceLens(lens: WorkspaceLensId, item: unknown) {
  if (lens === 'all') {
    return true;
  }

  const text = collectLensText(item);
  if (!text) {
    return false;
  }

  const keywordMap: Record<Exclude<WorkspaceLensId, 'all'>, string[]> = {
    admissions: ['admissions', 'prospective student', 'family', 'outreach', 'school fit', 'higher ed'],
    entrepreneurship: ['entrepreneur', 'founder', 'builder', 'business', 'startup', 'venture', 'operator'],
    'current-role': ['current role', 'current job', 'role-safe', 'inside the current role', 'institution', 'organization', 'staff', 'day-to-day work'],
    'personal-story': ['i ', 'my ', 'lived', 'story', 'journey', 'lesson', 'experience', 'authentic'],
    'program-leadership': ['leadership', 'leader', 'team', 'manager', 'program', 'coaching', 'accountability', 'operator clarity'],
    'enrollment-management': ['enrollment', 'pipeline', 'conversion', 'yield', 'concierge', 'follow up', 'follow-up'],
    ai: ['ai', 'agent', 'model', 'prompt', 'literacy', 'automation', 'system'],
    'ops-pm': ['ops', 'operations', 'project', 'pm', 'workflow', 'handoff', 'ownership', 'cadence', 'delivery'],
    therapy: ['therapy', 'therapist', 'mental health', 'healing', 'emotion', 'nervous system', 'human'],
    referral: ['referral', 'partner', 'consultant', 'counselor', 'handoff', 'trust', 'family referral'],
  };

  return keywordMap[lens].some((keyword) => text.includes(keyword));
}

function buildLensRemix(lens: WorkspaceLensId, item: { title?: string; hook?: string; priority_lane?: string; role_alignment?: string }) {
  const title = item.title ?? 'this idea';
  const hook = item.hook ?? 'the current hook';
  switch (lens) {
    case 'admissions':
      return `Reframe ${title} around student/family reality, frontline outreach, and what admissions teams learn before the rest of the institution sees it.`;
    case 'entrepreneurship':
      return `Reframe ${title} as a leverage story: show how the current role sharpens builder instincts, systems thinking, and founder-adjacent execution.`;
    case 'current-role':
      return `Translate ${title} into something directly usable inside the current job. Emphasize what changes in the work right now for students, families, staff, or execution.`;
    case 'personal-story':
      return `Start from lived experience instead of abstraction. Use ${hook} as the lesson, then connect it to a real moment, change, or identity shift.`;
    case 'program-leadership':
      return `Translate ${title} into a leadership system takeaway. Emphasize team clarity, repeatability, coaching, and what a program leader should do next.`;
    case 'enrollment-management':
      return `Turn ${title} into an enrollment-management post by linking it to pipeline quality, follow-up discipline, and a more legible student journey.`;
    case 'ai':
      return `Push ${title} into a pure AI lens. Make the post about AI literacy, judgment, prompting, evaluation, and what it means to use AI well.`;
    case 'ops-pm':
      return `Translate ${title} into an ops and project-management lesson. Focus on ownership, workflow, handoffs, cadence, and delivery discipline.`;
    case 'therapy':
      return `Angle ${title} toward the therapeutic and human layer. Highlight emotional safety, attunement, and how the experience feels from inside the system.`;
    case 'referral':
      return `Angle ${title} toward referral trust. Focus on partner confidence, handoff quality, and what makes someone comfortable sending the next person your way.`;
    default:
      return `Keep ${title} in its current lane, then tighten the post around the clearest next-step takeaway for the audience.`;
  }
}

function generatePostDraft(item: PlanCandidate, mode: WorkspaceLensId) {
  const intro = buildLensRemix(mode, item).replace(/\s+$/, '');
  const hook = item.hook ? `Hook: ${item.hook}` : '';
  return `${intro} ${hook}`.trim();
}

function labelSourceKind(kind?: string) {
  if (!kind) {
    return 'workspace';
  }
  return kind.replace(/_/g, ' ');
}

function extractSection(raw: string, heading: string) {
  const marker = `## ${heading}`;
  const start = raw.indexOf(marker);
  if (start === -1) {
    return '';
  }
  let section = raw.slice(start + marker.length);
  if (section.startsWith('\n')) {
    section = section.slice(1);
  }
  const nextHeading = section.indexOf('\n## ');
  if (nextHeading !== -1) {
    section = section.slice(0, nextHeading);
  }
  return section.trim();
}

function parseSubsections(section: string): MarkdownSubsection[] {
  if (!section) {
    return [];
  }
  const pattern = /###\s+([^\n]+)\n([\s\S]*?)(?=(?:\n###\s)|$)/g;
  const matches = Array.from(section.matchAll(pattern));
  return matches.map((match) => ({
    title: match[1].trim(),
    body: match[2].trim(),
    fields: parseKeyValueBullets(match[2]),
  }));
}

function parseKeyValueBullets(body: string) {
  const lines = body.split('\n');
  const map: Record<string, string> = {};
  for (const raw of lines) {
    const line = raw.trim();
    if (!line.startsWith('- ')) {
      continue;
    }
    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) {
      continue;
    }
    const key = line.slice(2, colonIndex).trim();
    const value = line.slice(colonIndex + 1).trim();
    map[key] = value;
  }
  return map;
}

function parseBullets(section: string) {
  return section
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => line.slice(2).trim())
    .filter((item) => item.length > 0);
}

function collectSaveRules(raw: string) {
  const section = extractSection(raw, 'Save Rules');
  const keepMatch = section.match(/Keep a signal if:\s*([\s\S]*?)Do not keep a signal if:/);
  const keep = keepMatch ? parseBullets(keepMatch[1]) : parseBullets(section);
  const dropMatch = section.match(/Do not keep a signal if:\s*([\s\S]*)/);
  const drop = dropMatch ? parseBullets(dropMatch[1]) : [];
  return { keep, drop };
}

function deriveSourceClass(item: SocialFeedItem) {
  const explicit = item.source_class?.trim();
  if (explicit) {
    return explicit;
  }
  const sourceType = item.source_type?.toLowerCase() ?? '';
  const captureMethod = item.capture_method?.toLowerCase() ?? '';
  if (item.platform === 'manual' || captureMethod === 'manual') {
    return 'manual';
  }
  if (['video', 'episode', 'transcript', 'audio', 'podcast'].includes(sourceType) || ['youtube', 'podcast'].includes(item.platform)) {
    return 'long_form_media';
  }
  if (['article', 'essay', 'newsletter'].includes(sourceType) || ['rss', 'substack', 'web'].includes(item.platform)) {
    return 'article';
  }
  return 'short_form';
}

function deriveUnitKind(item: SocialFeedItem, sourceClass: string) {
  const explicit = item.unit_kind?.trim();
  if (explicit) {
    return explicit;
  }
  if (sourceClass === 'article') {
    return 'paragraph';
  }
  if (sourceClass === 'long_form_media') {
    return 'section';
  }
  if (sourceClass === 'manual' && (item.summary?.split(/[.!?]+/).filter(Boolean).length ?? 0) <= 2) {
    return 'claim_block';
  }
  return 'full_post';
}

function deriveResponseModes(item: SocialFeedItem, sourceClass: string, unitKind: string) {
  const explicit = (item.response_modes ?? []).map((mode) => mode.trim()).filter(Boolean);
  if (explicit.length > 0) {
    return explicit;
  }
  if (sourceClass === 'long_form_media' && !['segment', 'quote_cluster', 'claim_block'].includes(unitKind)) {
    return ['post_seed', 'belief_evidence'];
  }
  return ['comment', 'repost', 'post_seed', 'belief_evidence'];
}

function buildTuningDashboard(items: SocialFeedItem[]): TuningDashboard | null {
  const placeholderExcludedCount = items.filter((item) => isPlaceholderFeedItem(item)).length;
  const sampledItems = placeholderExcludedCount < items.length ? items.filter((item) => !isPlaceholderFeedItem(item)) : items;
  const sampleMode: TuningDashboard['sampleMode'] = placeholderExcludedCount < items.length ? 'real-only' : 'all-items';
  const variants: TuningVariantRecord[] = [];
  const suspectItemIds = new Set<string>();

  sampledItems.forEach((item) => {
    if (looksLikeSurfaceTitle(item.title)) {
      suspectItemIds.add(item.id);
    }
    const sourceClass = deriveSourceClass(item);
    const unitKind = deriveUnitKind(item, sourceClass);
    const responseModes = deriveResponseModes(item, sourceClass, unitKind);
    const entries = Object.entries(item.lens_variants ?? {}) as Array<[string, FeedVariant | undefined]>;
    if (!entries.length && item.evaluation) {
      const fallbackLane = (item.lenses?.[0] as FeedLensId | undefined) ?? 'current-role';
      variants.push({
        itemId: item.id,
        title: item.title,
        platform: item.platform,
        sourceClass,
        unitKind,
        responseModes,
        lane: fallbackLane,
        laneLabel: POST_MODE_OPTIONS.find((mode) => mode.id === fallbackLane)?.label ?? fallbackLane,
        overall: item.evaluation.overall ?? 0,
        expressionQuality: item.evaluation.expression_quality ?? 0,
        sourceExpressionQuality: item.evaluation.source_expression_quality ?? 0,
        expressionDelta: item.evaluation.expression_delta ?? 0,
        sourceStructure: item.evaluation.source_structure ?? 'none',
        outputStructure: item.evaluation.output_structure ?? 'none',
        structurePreserved: item.evaluation.structure_preserved ?? null,
        strategy: item.expression_assessment?.strategy ?? 'none',
        sourceText: item.expression_assessment?.source_text ?? '',
        outputText: item.expression_assessment?.output_text ?? '',
        overlapRatio: item.expression_assessment?.overlap_ratio ?? 0,
        warnings: item.evaluation.warnings ?? [],
      });
      return;
    }

    entries.forEach(([lane, variant]) => {
      if (!variant?.evaluation) {
        return;
      }
      const normalizedLane = (normalizeFeedLensKey(lane) ?? 'current-role') as FeedLensId;
      variants.push({
        itemId: item.id,
        title: item.title,
        platform: item.platform,
        sourceClass,
        unitKind,
        responseModes,
        lane: normalizedLane,
        laneLabel: variant.label ?? POST_MODE_OPTIONS.find((mode) => mode.id === normalizedLane)?.label ?? normalizedLane,
        overall: variant.evaluation.overall ?? 0,
        expressionQuality: variant.evaluation.expression_quality ?? 0,
        sourceExpressionQuality: variant.evaluation.source_expression_quality ?? 0,
        expressionDelta: variant.evaluation.expression_delta ?? 0,
        sourceStructure: variant.evaluation.source_structure ?? 'none',
        outputStructure: variant.evaluation.output_structure ?? 'none',
        structurePreserved: variant.evaluation.structure_preserved ?? null,
        strategy: variant.expression_assessment?.strategy ?? 'none',
        sourceText: variant.expression_assessment?.source_text ?? '',
        outputText: variant.expression_assessment?.output_text ?? '',
        overlapRatio: variant.expression_assessment?.overlap_ratio ?? 0,
        warnings: variant.evaluation.warnings ?? [],
      });
    });
  });

  if (!variants.length) {
    return null;
  }

  const warningCounts = new Map<string, number>();
  const strategyCounts = new Map<string, number>();
  const platformMap = new Map<string, {
    count: number;
    overallTotal: number;
    sourceTotal: number;
    expressionTotal: number;
    deltaTotal: number;
    weakSourceCount: number;
  }>();
  const sourceClassMap = new Map<string, {
    count: number;
    overallTotal: number;
    sourceTotal: number;
    expressionTotal: number;
    deltaTotal: number;
    weakSourceCount: number;
  }>();
  const unitKindMap = new Map<string, {
    count: number;
    sourceTotal: number;
    expressionTotal: number;
    deltaTotal: number;
    weakSourceCount: number;
  }>();
  const responseModeMap = new Map<string, {
    itemIds: Set<string>;
    count: number;
    sourceTotal: number;
    expressionTotal: number;
    deltaTotal: number;
    weakSourceCount: number;
  }>();
  const structureMap = new Map<string, {
    count: number;
    sourceTotal: number;
    expressionTotal: number;
    deltaTotal: number;
    preservedCount: number;
  }>();
  const laneMap = new Map<FeedLensId, {
    count: number;
    overallTotal: number;
    sourceTotal: number;
    expressionTotal: number;
    deltaTotal: number;
    weakSourceCount: number;
    warningCount: number;
  }>();

  let totalOverall = 0;
  let totalSource = 0;
  let totalExpression = 0;
  let totalDelta = 0;
  let weakSourceCount = 0;
  let warningVariantCount = 0;
  let degradedCount = 0;
  let neutralDeltaCount = 0;
  let lowExpressionCount = 0;
  let structureLossCount = 0;
  let laneDominanceCount = 0;

  variants.forEach((variant) => {
    totalOverall += variant.overall;
    totalSource += variant.sourceExpressionQuality;
    totalExpression += variant.expressionQuality;
    totalDelta += variant.expressionDelta;

    const derivedWarnings = [...variant.warnings];
    if (variant.sourceExpressionQuality <= 0.1) {
      weakSourceCount += 1;
      derivedWarnings.unshift('source grounding missing');
    }
    if (variant.expressionDelta < 0) {
      degradedCount += 1;
    }
    if (variant.expressionDelta === 0) {
      neutralDeltaCount += 1;
    }
    if (variant.expressionQuality < 6.5) {
      lowExpressionCount += 1;
    }
    if (variant.structurePreserved === false) {
      structureLossCount += 1;
      derivedWarnings.push('source structure lost');
    }
    if (variant.sourceExpressionQuality <= 0.1 && variant.overall >= 7.2) {
      laneDominanceCount += 1;
      derivedWarnings.push('lane carries draft without source');
    }
    if (derivedWarnings.length > 0) {
      warningVariantCount += 1;
    }

    derivedWarnings.forEach((warning) => {
      warningCounts.set(warning, (warningCounts.get(warning) ?? 0) + 1);
    });

    const strategy = variant.strategy || 'none';
    strategyCounts.set(strategy, (strategyCounts.get(strategy) ?? 0) + 1);

    const platformEntry = platformMap.get(variant.platform) ?? {
      count: 0,
      overallTotal: 0,
      sourceTotal: 0,
      expressionTotal: 0,
      deltaTotal: 0,
      weakSourceCount: 0,
    };
    platformEntry.count += 1;
    platformEntry.overallTotal += variant.overall;
    platformEntry.sourceTotal += variant.sourceExpressionQuality;
    platformEntry.expressionTotal += variant.expressionQuality;
    platformEntry.deltaTotal += variant.expressionDelta;
    if (variant.sourceExpressionQuality <= 0.1) {
      platformEntry.weakSourceCount += 1;
    }
    platformMap.set(variant.platform, platformEntry);

    const sourceClassEntry = sourceClassMap.get(variant.sourceClass) ?? {
      count: 0,
      overallTotal: 0,
      sourceTotal: 0,
      expressionTotal: 0,
      deltaTotal: 0,
      weakSourceCount: 0,
    };
    sourceClassEntry.count += 1;
    sourceClassEntry.overallTotal += variant.overall;
    sourceClassEntry.sourceTotal += variant.sourceExpressionQuality;
    sourceClassEntry.expressionTotal += variant.expressionQuality;
    sourceClassEntry.deltaTotal += variant.expressionDelta;
    if (variant.sourceExpressionQuality <= 0.1) {
      sourceClassEntry.weakSourceCount += 1;
    }
    sourceClassMap.set(variant.sourceClass, sourceClassEntry);

    const unitKindEntry = unitKindMap.get(variant.unitKind) ?? {
      count: 0,
      sourceTotal: 0,
      expressionTotal: 0,
      deltaTotal: 0,
      weakSourceCount: 0,
    };
    unitKindEntry.count += 1;
    unitKindEntry.sourceTotal += variant.sourceExpressionQuality;
    unitKindEntry.expressionTotal += variant.expressionQuality;
    unitKindEntry.deltaTotal += variant.expressionDelta;
    if (variant.sourceExpressionQuality <= 0.1) {
      unitKindEntry.weakSourceCount += 1;
    }
    unitKindMap.set(variant.unitKind, unitKindEntry);

    variant.responseModes.forEach((mode) => {
      const responseModeEntry = responseModeMap.get(mode) ?? {
        itemIds: new Set<string>(),
        count: 0,
        sourceTotal: 0,
        expressionTotal: 0,
        deltaTotal: 0,
        weakSourceCount: 0,
      };
      responseModeEntry.itemIds.add(variant.itemId);
      responseModeEntry.count += 1;
      responseModeEntry.sourceTotal += variant.sourceExpressionQuality;
      responseModeEntry.expressionTotal += variant.expressionQuality;
      responseModeEntry.deltaTotal += variant.expressionDelta;
      if (variant.sourceExpressionQuality <= 0.1) {
        responseModeEntry.weakSourceCount += 1;
      }
      responseModeMap.set(mode, responseModeEntry);
    });

    const structureKey = variant.sourceStructure || 'none';
    const structureEntry = structureMap.get(structureKey) ?? {
      count: 0,
      sourceTotal: 0,
      expressionTotal: 0,
      deltaTotal: 0,
      preservedCount: 0,
    };
    structureEntry.count += 1;
    structureEntry.sourceTotal += variant.sourceExpressionQuality;
    structureEntry.expressionTotal += variant.expressionQuality;
    structureEntry.deltaTotal += variant.expressionDelta;
    if (variant.structurePreserved !== false) {
      structureEntry.preservedCount += 1;
    }
    structureMap.set(structureKey, structureEntry);

    const laneEntry = laneMap.get(variant.lane) ?? {
      count: 0,
      overallTotal: 0,
      sourceTotal: 0,
      expressionTotal: 0,
      deltaTotal: 0,
      weakSourceCount: 0,
      warningCount: 0,
    };
    laneEntry.count += 1;
    laneEntry.overallTotal += variant.overall;
    laneEntry.sourceTotal += variant.sourceExpressionQuality;
    laneEntry.expressionTotal += variant.expressionQuality;
    laneEntry.deltaTotal += variant.expressionDelta;
    if (variant.sourceExpressionQuality <= 0.1) {
      laneEntry.weakSourceCount += 1;
    }
    if (derivedWarnings.length > 0) {
      laneEntry.warningCount += 1;
    }
    laneMap.set(variant.lane, laneEntry);
  });

  const laneHealth: TuningLaneHealth[] = Array.from(laneMap.entries())
    .map(([lane, metrics]) => ({
      lane,
      laneLabel: POST_MODE_OPTIONS.find((mode) => mode.id === lane)?.label ?? lane,
      variants: metrics.count,
      avgOverall: metrics.overallTotal / metrics.count,
      avgSource: metrics.sourceTotal / metrics.count,
      avgExpression: metrics.expressionTotal / metrics.count,
      avgDelta: metrics.deltaTotal / metrics.count,
      weakSourceCount: metrics.weakSourceCount,
      warningCount: metrics.warningCount,
    }))
    .sort((a, b) => {
      if (a.avgOverall !== b.avgOverall) {
        return a.avgOverall - b.avgOverall;
      }
      return b.weakSourceCount - a.weakSourceCount;
    });

  const platformHealth: TuningPlatformHealth[] = Array.from(platformMap.entries())
    .map(([platform, metrics]) => ({
      platform,
      variants: metrics.count,
      avgOverall: metrics.overallTotal / metrics.count,
      avgSource: metrics.sourceTotal / metrics.count,
      avgExpression: metrics.expressionTotal / metrics.count,
      avgDelta: metrics.deltaTotal / metrics.count,
      weakSourceCount: metrics.weakSourceCount,
    }))
    .sort((a, b) => {
      if (a.avgSource !== b.avgSource) {
        return a.avgSource - b.avgSource;
      }
      return b.variants - a.variants;
    });

  const sourceClassHealth: TuningSourceClassHealth[] = Array.from(sourceClassMap.entries())
    .map(([sourceClass, metrics]) => ({
      sourceClass,
      variants: metrics.count,
      avgOverall: metrics.overallTotal / metrics.count,
      avgSource: metrics.sourceTotal / metrics.count,
      avgExpression: metrics.expressionTotal / metrics.count,
      avgDelta: metrics.deltaTotal / metrics.count,
      weakSourceCount: metrics.weakSourceCount,
    }))
    .sort((a, b) => {
      if (a.avgSource !== b.avgSource) {
        return a.avgSource - b.avgSource;
      }
      return b.variants - a.variants;
    });

  const unitKindHealth: TuningUnitKindHealth[] = Array.from(unitKindMap.entries())
    .map(([unitKind, metrics]) => ({
      unitKind,
      variants: metrics.count,
      avgSource: metrics.sourceTotal / metrics.count,
      avgExpression: metrics.expressionTotal / metrics.count,
      avgDelta: metrics.deltaTotal / metrics.count,
      weakSourceCount: metrics.weakSourceCount,
    }))
    .sort((a, b) => {
      if (a.avgSource !== b.avgSource) {
        return a.avgSource - b.avgSource;
      }
      return b.variants - a.variants;
    });

  const responseModeHealth: TuningResponseModeHealth[] = Array.from(responseModeMap.entries())
    .map(([mode, metrics]) => ({
      mode,
      itemCount: metrics.itemIds.size,
      variants: metrics.count,
      avgSource: metrics.sourceTotal / metrics.count,
      avgExpression: metrics.expressionTotal / metrics.count,
      avgDelta: metrics.deltaTotal / metrics.count,
      weakSourceCount: metrics.weakSourceCount,
    }))
    .sort((a, b) => {
      if (a.avgSource !== b.avgSource) {
        return a.avgSource - b.avgSource;
      }
      return b.itemCount - a.itemCount;
    });

  const structureHealth: TuningStructureHealth[] = Array.from(structureMap.entries())
    .map(([structure, metrics]) => ({
      structure,
      variants: metrics.count,
      avgSource: metrics.sourceTotal / metrics.count,
      avgExpression: metrics.expressionTotal / metrics.count,
      avgDelta: metrics.deltaTotal / metrics.count,
      preservedRate: metrics.preservedCount / metrics.count,
    }))
    .sort((a, b) => {
      if (a.avgDelta !== b.avgDelta) {
        return a.avgDelta - b.avgDelta;
      }
      return b.variants - a.variants;
    });

  const attentionQueue: TuningAttentionItem[] = [...variants]
    .sort((a, b) => {
      const aSeverity = tuningSeverity(a);
      const bSeverity = tuningSeverity(b);
      if (aSeverity !== bSeverity) {
        return bSeverity - aSeverity;
      }
      if (a.overall !== b.overall) {
        return a.overall - b.overall;
      }
      return a.expressionQuality - b.expressionQuality;
    })
    .slice(0, 6)
    .map((variant) => ({
      itemId: variant.itemId,
      title: variant.title,
      platform: variant.platform,
      laneLabel: variant.laneLabel,
      reason: deriveTuningReason(variant),
      overall: variant.overall,
      sourceExpressionQuality: variant.sourceExpressionQuality,
      expressionQuality: variant.expressionQuality,
      expressionDelta: variant.expressionDelta,
      sourceText: variant.sourceText,
      outputText: variant.outputText,
    }));

  return {
    itemCount: sampledItems.length,
    placeholderExcludedCount,
    sampleMode,
    variantCount: variants.length,
    avgOverall: totalOverall / variants.length,
    avgSourceExpressionQuality: totalSource / variants.length,
    avgExpressionQuality: totalExpression / variants.length,
    avgExpressionDelta: totalDelta / variants.length,
    weakSourceCount,
    warningVariantCount,
    degradedCount,
    neutralDeltaCount,
    lowExpressionCount,
    structureLossCount,
    laneDominanceCount,
    suspectTitleCount: suspectItemIds.size,
    strategyCounts: Array.from(strategyCounts.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5),
    warningCounts: Array.from(warningCounts.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6),
    failureModes: [
      { label: 'source grounding missing', count: weakSourceCount },
      { label: 'lane carries draft without source', count: laneDominanceCount },
      { label: 'neutral rewrite with no lift', count: neutralDeltaCount },
      { label: 'output expression still low', count: lowExpressionCount },
      { label: 'rewrite degraded source', count: degradedCount },
      { label: 'source structure lost', count: structureLossCount },
    ],
    laneHealth,
    platformHealth,
    sourceClassHealth,
    unitKindHealth,
    responseModeHealth,
    structureHealth,
    attentionQueue,
  };
}

function normalizeFeedLensKey(value: string): FeedLensId | null {
  const normalized = value.trim().toLowerCase();
  if (normalized === 'ai-entrepreneurship') {
    return 'ai';
  }
  if (normalized === 'therapist-referral') {
    return 'therapy';
  }
  if ((POST_MODE_OPTIONS as Array<{ id: string }>).some((mode) => mode.id === normalized)) {
    return normalized as FeedLensId;
  }
  return null;
}

function tuningSeverity(variant: TuningVariantRecord) {
  let score = 0;
  if (variant.sourceExpressionQuality <= 0.1) score += 4;
  if (variant.structurePreserved === false) score += 3;
  if (variant.expressionDelta < 0) score += 2;
  if (variant.overall < 7.0) score += 2;
  score += Math.min(variant.warnings.length, 3);
  return score;
}

function deriveTuningReason(variant: TuningVariantRecord) {
  if (variant.sourceExpressionQuality <= 0.1 && variant.overall >= 7.2) {
    return 'Lane template is carrying an ungrounded draft';
  }
  if (variant.sourceExpressionQuality <= 0.1) {
    return 'No usable source grounding';
  }
  if (variant.structurePreserved === false) {
    return 'Rewrite lost source structure';
  }
  if (variant.expressionDelta < 0) {
    return 'Expression quality dropped after rewrite';
  }
  if (variant.warnings.length > 0) {
    return variant.warnings[0];
  }
  return 'Lowest current score in sample';
}

function isPlaceholderFeedItem(item: SocialFeedItem) {
  const markerText = [
    item.title,
    item.summary,
    item.comment_draft,
    item.repost_draft,
    item.why_it_matters,
    ...(item.standout_lines ?? []),
    ...Object.values(item.lens_variants ?? {}).flatMap((variant) =>
      variant
        ? [
            variant.comment,
            variant.short_comment ?? '',
            variant.repost,
            variant.expression_assessment?.source_text ?? '',
            variant.expression_assessment?.output_text ?? '',
          ]
        : [],
    ),
  ]
    .join(' ')
    .toLowerCase();

  return (
    markerText.includes('placeholder capture for ') ||
    markerText.includes('# reddit placeholder') ||
    markerText.includes('# rss placeholder') ||
    markerText.includes('rss capture for ')
  );
}

function looksLikeSurfaceTitle(title: string) {
  const cleaned = title.trim();
  if (!cleaned) {
    return false;
  }
  const upperLetters = cleaned.replace(/[^A-Z]/g, '').length;
  const totalLetters = cleaned.replace(/[^A-Za-z]/g, '').length;
  const upperRatio = totalLetters > 0 ? upperLetters / totalLetters : 0;
  const hasDate = /\b(january|february|march|april|may|june|july|august|september|october|november|december)\b/i.test(cleaned) && /\b20\d{2}\b/.test(cleaned);
  return hasDate || upperRatio > 0.72;
}

function normalizeStatus(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === 'in_progress' || normalized === 'in-progress') return 'in_progress';
  if (normalized === 'review') return 'review';
  if (normalized === 'cancelled' || normalized === 'canceled') return 'done';
  if (normalized === 'done') return 'done';
  if (normalized === 'failed' || normalized === 'blocked' || normalized === 'error') return 'blocked';
  return 'todo';
}

function normalizeExecutionState(state: string) {
  const normalized = state.toLowerCase();
  if (normalized === 'queued') return 'queued';
  if (normalized === 'running' || normalized === 'in_progress' || normalized === 'in-progress') return 'running';
  if (normalized === 'review') return 'review';
  if (normalized === 'failed' || normalized === 'blocked') return 'failed';
  if (normalized === 'done' || normalized === 'completed') return 'done';
  return 'ready';
}

function normalizeAutomationRunStatus(status?: string | null) {
  const normalized = (status ?? '').toLowerCase();
  if (normalized === 'success') return 'ok';
  if (normalized === 'error') return 'blocked';
  return normalized || 'unknown';
}

function humanizeStatusLabel(status?: string | null) {
  if (!status) {
    return 'unknown';
  }
  return status.replace(/[_-]+/g, ' ');
}

function dedupeStrings(values: string[]) {
  const ordered: string[] = [];
  const seen = new Set<string>();
  values.forEach((value) => {
    const cleaned = value.trim();
    if (!cleaned || seen.has(cleaned)) return;
    seen.add(cleaned);
    ordered.push(cleaned);
  });
  return ordered;
}

function formatList(values: string[]) {
  if (!values.length) return '';
  if (values.length === 1) return values[0];
  if (values.length === 2) return `${values[0]} and ${values[1]}`;
  return `${values.slice(0, -1).join(', ')}, and ${values[values.length - 1]}`;
}

function activityTimestampForQueue(entry: ExecutionQueueEntry) {
  const raw = entry.last_transition_at || entry.queued_at;
  if (!raw) return undefined;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function runTimestamp(run: AutomationRun) {
  const raw = run.finished_at || run.run_at;
  if (!raw) return undefined;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function extractAutomationRunSummary(run: AutomationRun) {
  const metadata = run.metadata ?? {};
  const value = metadata.summary;
  return typeof value === 'string' ? summarize(value, 140) : '';
}

function workspaceShortLabel(workspaceKey?: string | null) {
  if (!workspaceKey || workspaceKey === 'shared_ops') {
    return 'Shared Ops';
  }
  const hub = WORKSPACE_HUBS.find((item) => item.id === workspaceKey);
  if (hub) {
    return hub.shortLabel;
  }
  return workspaceKey.replace(/[_-]+/g, ' ');
}

function isHeldPmLayerStatus(
  pmStatus?: string | null,
  lane?: UnifiedBoardLaneKey | null,
  executionState?: string | null,
) {
  return normalizeStatus(pmStatus ?? 'todo') === 'blocked' && !executionState && (lane === 'todo' || lane == null);
}

function displayPmStatusLabel(
  pmStatus?: string | null,
  lane?: UnifiedBoardLaneKey | null,
  executionState?: string | null,
) {
  if (isHeldPmLayerStatus(pmStatus, lane, executionState)) {
    return 'held';
  }
  const normalized = normalizeStatus(pmStatus ?? 'todo');
  const raw = (pmStatus ?? '').toLowerCase();
  if (normalized === 'in_progress') return 'in progress';
  if (normalized === 'blocked') return 'blocked';
  if (raw === 'cancelled' || raw === 'canceled') return 'cancelled';
  if (normalized === 'done') return 'done';
  if (normalized === 'review') return 'review';
  return humanizeStatusLabel(pmStatus ?? 'todo');
}

function displayExecutionStateLabel(executionState?: string | null) {
  const normalized = normalizeExecutionState(executionState ?? 'ready');
  if (normalized === 'failed') return 'blocked';
  return humanizeStatusLabel(normalized);
}

function displayWorkerStatusLabel(entry?: ExecutionQueueEntry | null) {
  if (!entry?.executor_status) {
    return null;
  }
  const executionState = normalizeExecutionState(entry.execution_state ?? 'ready');
  const executorStatus = String(entry.executor_status ?? '').trim().toLowerCase();
  const executionMode = String(entry.execution_mode ?? '').trim().toLowerCase();
  const directMode = executionMode === 'direct';

  if (executionState === 'running' && executorStatus === 'queued') {
    return directMode ? 'queued after SOP handoff' : 'queued after delegate handoff';
  }
  if (executionState === 'queued' && executorStatus === 'queued') {
    return directMode ? 'waiting for pickup' : 'waiting for delegate pickup';
  }
  if (executionState === 'running' && executorStatus === 'running') {
    return directMode ? 'running' : 'delegate running';
  }
  if (executionState === 'review' && executorStatus === 'completed') {
    return 'completed; waiting on review';
  }
  return humanizeStatusLabel(executorStatus);
}

function standupKind(entry: StandupEntry) {
  const payload = entry.payload ?? {};
  const value = payload.standup_kind;
  return typeof value === 'string' && value.trim() ? value.trim() : entry.workspace_key || 'shared_ops';
}

function standupLabel(entry: StandupEntry) {
  const room = STANDUP_ROOMS.find((candidate) => candidate.key === standupKind(entry) && candidate.workspaceKey === entry.workspace_key);
  return room?.label ?? standupKind(entry);
}

function standupRoom(entry: StandupEntry) {
  return STANDUP_ROOMS.find((candidate) => candidate.key === standupKind(entry) && candidate.workspaceKey === (entry.workspace_key ?? 'shared_ops')) ?? null;
}

function standupSummary(entry: StandupEntry) {
  const payload = entry.payload ?? {};
  const summary = payload.summary;
  return typeof summary === 'string' && summary.trim() ? summary.trim() : 'Standup transcript recorded.';
}

function standupDiscussion(entry: StandupEntry) {
  const payload = entry.payload ?? {};
  const discussion = payload.discussion;
  return Array.isArray(discussion) ? discussion.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object') : [];
}

function isMeaningfulStandup(entry: StandupEntry) {
  return (
    standupDiscussion(entry).length >= 3 ||
    extractStandupList(entry.payload, 'decisions').length > 0 ||
    entry.commitments.length > 0 ||
    entry.blockers.length > 0
  );
}

function standupCreatedAt(entry: StandupEntry) {
  return entry.created_at ? new Date(entry.created_at) : new Date(0);
}

function isStandupLinkedCard(card: PMCard) {
  const payload = card.payload ?? {};
  return card.link_type === 'standup' || Boolean(payload.created_from_standup_id);
}

function linkedStandupsForCard(card: PMCard, standups: StandupEntry[]) {
  const payload = card.payload ?? {};
  const linkedIds = new Set(
    [card.link_id, payload.created_from_standup_id]
      .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
      .map((value) => value.trim()),
  );
  if (linkedIds.size === 0) {
    return [] as StandupEntry[];
  }
  return standups.filter((entry) => linkedIds.has(entry.id));
}

function linkedCardsForStandup(entry: StandupEntry, pmCards: PMCard[]) {
  return pmCards.filter((card) => {
    const payload = card.payload ?? {};
    return card.link_id === entry.id || payload.created_from_standup_id === entry.id;
  });
}

function liveLinkedCardItems(entry: StandupEntry, pmCards: PMCard[]) {
  return linkedCardsForStandup(entry, pmCards)
    .sort((left, right) => {
      const leftDone = (left.status ?? '').toLowerCase() === 'done' ? 1 : 0;
      const rightDone = (right.status ?? '').toLowerCase() === 'done' ? 1 : 0;
      if (leftDone !== rightDone) {
        return leftDone - rightDone;
      }
      const leftTime = left.updated_at ? new Date(left.updated_at).getTime() : 0;
      const rightTime = right.updated_at ? new Date(right.updated_at).getTime() : 0;
      return rightTime - leftTime;
    })
    .map((card) => {
      const normalized = normalizeStatus(card.status ?? 'todo');
      const lane: UnifiedBoardLaneKey =
        normalized === 'in_progress' ? 'running' : normalized === 'review' ? 'review' : normalized === 'done' ? 'done' : 'todo';
      return `${displayPmStatusLabel(card.status, lane, null)} · ${card.title}`;
    });
}

function buildMeetingOps(
  rooms: Array<{ key: string; label: string; workspaceKey: string }>,
  entries: StandupEntry[],
  pmCards: PMCard[],
  executionQueue: ExecutionQueueEntry[],
): MeetingOpsSummary {
  const sortedEntries = [...entries].sort((left, right) => standupCreatedAt(right).getTime() - standupCreatedAt(left).getTime());
  const now = Date.now();
  const linkedCards = pmCards.filter((card) => isStandupLinkedCard(card));
  const linkedCardCount = linkedCards.filter((card) => (card.status ?? '').toLowerCase() !== 'done').length;
  const resolvedLinkedCardCount = linkedCards.filter((card) => (card.status ?? '').toLowerCase() === 'done').length;

  const orphanStandupCount = sortedEntries.filter((entry) => {
    if (!isMeaningfulStandup(entry)) {
      return false;
    }
    return linkedCardsForStandup(entry, pmCards).length === 0;
  }).length;

  const staleReadyCount = executionQueue.filter((entry) => {
    const timestamp = entry.last_transition_at ?? entry.queued_at;
    return normalizeExecutionState(entry.execution_state) === 'ready' && timestamp && now - new Date(timestamp).getTime() > 90 * 60 * 1000;
  }).length;
  const staleReviewCount = executionQueue.filter((entry) => {
    const timestamp = entry.last_transition_at ?? entry.queued_at;
    return normalizeExecutionState(entry.execution_state) === 'review' && timestamp && now - new Date(timestamp).getTime() > 24 * 60 * 60 * 1000;
  }).length;
  const staleRunningCount = executionQueue.filter((entry) => {
    const normalized = normalizeExecutionState(entry.execution_state);
    const timestamp = entry.last_transition_at ?? entry.queued_at;
    return (normalized === 'queued' || normalized === 'running') && timestamp && now - new Date(timestamp).getTime() > 24 * 60 * 60 * 1000;
  }).length;

  const roomsSummary = rooms.map((room) => {
    const liveEntries = sortedEntries.filter((entry) => standupKind(entry) === room.key && entry.workspace_key === room.workspaceKey);
    const latestEntry = liveEntries[0] ?? null;
    const roundCount = latestEntry ? standupDiscussion(latestEntry).length : 0;
    const isExpected = !['easyoutfitapp', 'ai-swag-store', 'agc'].includes(room.key);
    let status = 'planned';
    let reason = 'Reserved lane. No meeting transcript expected yet.';

    if (latestEntry) {
      const ageMs = now - standupCreatedAt(latestEntry).getTime();
      const maxAgeMs =
        room.key === 'weekly_review' || room.key === 'saturday_vision' ? 8 * 24 * 60 * 60 * 1000 : 36 * 60 * 60 * 1000;
      if (roundCount < 3 || !standupSummary(latestEntry)) {
        status = 'warning';
        reason = 'Transcript exists but the meeting still looks thin.';
      } else if (ageMs > maxAgeMs) {
        status = 'stale';
        reason = 'Latest meeting is older than the target cadence window.';
      } else {
        status = 'ok';
        reason = 'Meeting transcript is fresh and has enough discussion to be useful.';
      }
    } else if (isExpected) {
      status = 'missing';
      reason = 'No meeting transcript recorded for this required lane yet.';
    }

    return {
      key: room.key,
      label: room.label,
      workspaceKey: room.workspaceKey,
      status,
      reason,
      latestEntry,
      roundCount,
    } satisfies MeetingRoomHealth;
  });

  return {
    rooms: roomsSummary,
    byRoomKey: Object.fromEntries(roomsSummary.map((room) => [room.key, room])),
    linkedCardCount,
    resolvedLinkedCardCount,
    orphanStandupCount,
    staleReadyCount,
    staleReviewCount,
    staleRunningCount,
    recentStandups: sortedEntries.slice(0, 40),
  };
}

function buildRecentDayBuckets(entries: StandupEntry[], days: number) {
  const buckets: Array<{ key: string; label: string; entries: StandupEntry[] }> = [];
  const byDay = new Map<string, StandupEntry[]>();
  entries.forEach((entry) => {
    const date = standupCreatedAt(entry);
    const key = date.toISOString().slice(0, 10);
    const current = byDay.get(key) ?? [];
    current.push(entry);
    byDay.set(key, current);
  });
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() - offset);
    const key = date.toISOString().slice(0, 10);
    buckets.push({
      key,
      label: formatUiDateWithWeekday(date),
      entries: (byDay.get(key) ?? []).sort((left, right) => standupCreatedAt(right).getTime() - standupCreatedAt(left).getTime()),
    });
  }
  return buckets;
}

function buildMonthBuckets(entries: StandupEntry[]) {
  const today = new Date();
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  const byDay = new Map<string, StandupEntry[]>();
  entries.forEach((entry) => {
    const date = standupCreatedAt(entry);
    if (date.getFullYear() !== today.getFullYear() || date.getMonth() !== today.getMonth()) {
      return;
    }
    const key = date.toISOString().slice(0, 10);
    const current = byDay.get(key) ?? [];
    current.push(entry);
    byDay.set(key, current);
  });

  const buckets: Array<{ key: string; label: string; entries: StandupEntry[] }> = [];
  for (let day = 1; day <= lastDay.getDate(); day += 1) {
    const current = new Date(today.getFullYear(), today.getMonth(), day);
    const key = current.toISOString().slice(0, 10);
    buckets.push({
      key,
      label: formatUiDate(current),
      entries: (byDay.get(key) ?? []).sort((left, right) => standupCreatedAt(right).getTime() - standupCreatedAt(left).getTime()),
    });
  }
  return buckets;
}

function statusBadge(status?: string) {
  const normalized = status?.toLowerCase();
  let color = '#94a3b8';
  if (normalized === 'healthy' || normalized === 'active' || normalized === 'done' || normalized === 'ok') {
    color = '#22c55e';
  } else if (normalized === 'ready') {
    color = '#a78bfa';
  } else if (normalized === 'queued') {
    color = '#14b8a6';
  } else if (normalized === 'running' || normalized === 'in_progress' || normalized === 'in-progress') {
    color = '#38bdf8';
  } else if (normalized === 'failed' || normalized === 'blocked' || normalized === 'error' || normalized === 'missing') {
    color = '#f87171';
  } else if (normalized === 'warning' || normalized === 'review' || normalized === 'stale' || normalized === 'thin' || normalized === 'held' || normalized === 'standing_up') {
    color = '#fbbf24';
  } else if (normalized === 'planned' || normalized === 'cancelled' || normalized === 'canceled') {
    color = '#64748b';
  }
  return (
    <span style={{ padding: '4px 12px', borderRadius: '999px', backgroundColor: `${color}33`, color, fontSize: '12px', textTransform: 'capitalize' }}>
      {humanizeStatusLabel(status)}
    </span>
  );
}

function formatTimestamp(value: Date) {
  return formatUiTimestamp(value);
}

function humanizeBeliefRelation(value: string | null | undefined) {
  if (!value) return 'Unknown relation';
  if (value === 'agreement') return 'Agreement';
  if (value === 'qualified_agreement') return 'Qualified agreement';
  if (value === 'disagreement') return 'Disagreement';
  if (value === 'translation') return 'Translation';
  if (value === 'experience_match') return 'Experience match';
  if (value === 'system_translation') return 'System translation';
  return value.replace(/[_-]+/g, ' ');
}

function summarize(text: string, maxLength = 120) {
  const trimmed = text.replace(/\s+/g, ' ').trim();
  if (trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, maxLength).trim()}...`;
}

function ownerReviewKindLabel(ownerReview?: OwnerReviewCardPayload | null) {
  if (!ownerReview) return 'Owner review';
  if (ownerReview.entry_kind === 'supplemental' && ownerReview.source_kind === 'latent_transform') return 'Latent transform';
  if (ownerReview.entry_kind === 'supplemental') return 'Supplemental review';
  return 'Queue item';
}

function ownerReviewReferenceLabel(ownerReview?: OwnerReviewCardPayload | null, fallback?: string | null) {
  if (!ownerReview) return fallback ?? 'unknown';
  if (ownerReview.entry_kind === 'supplemental') return ownerReview.title ?? fallback ?? 'supplemental draft';
  return ownerReview.queue_id ?? fallback ?? 'unknown';
}

function ownerReviewDisplayTitle(card: PMCard, ownerReview?: OwnerReviewCardPayload | null) {
  if (ownerReview?.entry_kind === 'supplemental' && ownerReview.title) {
    return `Owner review - ${ownerReview.title}`;
  }
  return card.title;
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

async function postJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    cache: 'no-store',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

function normalizeLogs(payload: LogsResponse | undefined): SystemLog[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.logs)) return payload.logs;
  return [];
}

function normalizeAutomations(payload: AutomationsResponse): Automation[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (typeof payload === 'object' && payload !== null) {
    const maybeData = (payload as { data?: Automation[] }).data;
    if (Array.isArray(maybeData)) return maybeData;
    const maybeAutomations = (payload as { automations?: Automation[] }).automations;
    if (Array.isArray(maybeAutomations)) return maybeAutomations;
  }
  return [];
}

function normalizeAutomationRuns(payload: AutomationsResponse): AutomationRun[] {
  if (!payload || Array.isArray(payload) || typeof payload !== 'object') return [];
  const maybeRuns = (payload as { runs?: AutomationRun[] }).runs;
  return Array.isArray(maybeRuns) ? maybeRuns : [];
}

function buildMissionActivityRows({
  executionQueue,
  automations,
  automationRuns,
  sessions,
}: {
  executionQueue: ExecutionQueueEntry[];
  automations: Automation[];
  automationRuns: AutomationRun[];
  sessions: { component: string; lastMessage: string; lastTimestamp?: Date }[];
}): MissionActivityRow[] {
  const prioritized: Array<MissionActivityRow & { sortTime: number; priority: number }> = [];
  const pushRow = (row: MissionActivityRow, priority: number) => {
    prioritized.push({
      ...row,
      sortTime: row.lastSeen?.getTime() ?? 0,
      priority,
    });
  };

  const executionBuckets = {
    failed: executionQueue.filter((entry) => normalizeExecutionState(entry.execution_state) === 'failed'),
    review: executionQueue.filter((entry) => normalizeExecutionState(entry.execution_state) === 'review'),
    running: executionQueue.filter((entry) => normalizeExecutionState(entry.execution_state) === 'running'),
    queued: executionQueue.filter((entry) => normalizeExecutionState(entry.execution_state) === 'queued'),
    ready: executionQueue.filter((entry) => normalizeExecutionState(entry.execution_state) === 'ready'),
  };

  const summarizeQueueBucket = (entries: ExecutionQueueEntry[], state: string, stream: string, priority: number) => {
    if (!entries.length) return;
    const ordered = [...entries].sort((left, right) => {
      const leftTime = activityTimestampForQueue(left)?.getTime() ?? 0;
      const rightTime = activityTimestampForQueue(right)?.getTime() ?? 0;
      return rightTime - leftTime;
    });
    const latest = ordered[0];
    const workspaces = dedupeStrings(ordered.map((entry) => workspaceShortLabel(entry.workspace_key)));
    const workspaceSummary = workspaces.length ? ` across ${formatList(workspaces)}` : '';
    let activity = '';
    if (state === 'running') {
      activity = `${ordered.length} live execution lane${ordered.length === 1 ? '' : 's'}${workspaceSummary}. Latest: ${summarize(latest.title, 88)}.`;
    } else if (state === 'review') {
      activity = `${ordered.length} card${ordered.length === 1 ? '' : 's'} waiting on review${workspaceSummary}. Latest return: ${summarize(latest.title, 88)}.`;
    } else if (state === 'failed') {
      activity = `${ordered.length} execution lane${ordered.length === 1 ? '' : 's'} blocked${workspaceSummary}. Latest blocker: ${summarize(latest.title, 88)}.`;
    } else if (state === 'queued') {
      activity = `${ordered.length} card${ordered.length === 1 ? '' : 's'} already opened and waiting for pickup${workspaceSummary}. Latest: ${summarize(latest.title, 88)}.`;
    } else {
      activity = `${ordered.length} card${ordered.length === 1 ? '' : 's'} ready for Jean-Claude${workspaceSummary}. Latest: ${summarize(latest.title, 88)}.`;
    }
    pushRow(
      {
        key: `queue-${state}`,
        stream,
        activity,
        status: state === 'failed' ? 'blocked' : state,
        lastSeen: activityTimestampForQueue(latest),
      },
      priority,
    );
  };

  summarizeQueueBucket(executionBuckets.failed, 'failed', 'Execution blockers', 500);
  summarizeQueueBucket(executionBuckets.running, 'running', 'Execution lanes', 470);
  summarizeQueueBucket(executionBuckets.review, 'review', 'Review queue', 450);
  summarizeQueueBucket(executionBuckets.queued, 'queued', 'Delegated queue', 430);
  summarizeQueueBucket(executionBuckets.ready, 'ready', 'Jean-Claude queue', 410);

  const youtubeAutomation = automations.find((item) => item.id === 'youtube_watchlist_auto_ingest') ?? null;
  const pendingBackfill = Number(youtubeAutomation?.metrics?.pending_transcript_backfill ?? 0);
  if (youtubeAutomation && Number.isFinite(pendingBackfill) && pendingBackfill > 0) {
    const transcriptionReady = youtubeAutomation.metrics?.transcription_runtime_ready === 'true';
    pushRow(
      {
        key: 'youtube-pending-transcripts',
        stream: 'YouTube transcript backlog',
        activity: transcriptionReady
          ? `${pendingBackfill} transcript${pendingBackfill === 1 ? '' : 's'} waiting to be written back into the richer media pipeline.`
          : `${pendingBackfill} transcript${pendingBackfill === 1 ? '' : 's'} waiting because the local transcription runtime is not ready yet.`,
        status: transcriptionReady ? 'review' : 'warning',
        lastSeen: youtubeAutomation.last_run_at ? new Date(youtubeAutomation.last_run_at) : undefined,
      },
      480,
    );
  }

  const latestRunByAutomation = new Map<string, AutomationRun>();
  [...automationRuns]
    .sort((left, right) => {
      const leftTime = runTimestamp(left)?.getTime() ?? 0;
      const rightTime = runTimestamp(right)?.getTime() ?? 0;
      return rightTime - leftTime;
    })
    .forEach((run) => {
      if (!run.automation_id || latestRunByAutomation.has(run.automation_id)) return;
      latestRunByAutomation.set(run.automation_id, run);
    });

  const recentCutoff = Date.now() - 6 * 60 * 60 * 1000;
  Array.from(latestRunByAutomation.values()).forEach((run) => {
    const timestamp = runTimestamp(run);
    const summary = extractAutomationRunSummary(run);
    const idleSummary = /found no queued pm cards|no queued cards|nothing to dispatch|no work/i.test(summary);
    if (!run.action_required && idleSummary) {
      return;
    }
    if (!run.action_required && timestamp && timestamp.getTime() < recentCutoff) {
      return;
    }
    if (!summary && !run.action_required) {
      return;
    }
    pushRow(
      {
        key: `automation-run-${run.automation_id}`,
        stream: run.automation_name || humanizeStatusLabel(run.automation_id),
        activity: summary || `${humanizeStatusLabel(run.status)} run completed.`,
        status: run.action_required ? 'warning' : normalizeAutomationRunStatus(run.status),
        lastSeen: timestamp,
      },
      run.action_required ? 460 : 300,
    );
  });

  if (!prioritized.length) {
    sessions.slice(0, 8).forEach((session, index) => {
      pushRow(
        {
          key: `session-${session.component}-${index}`,
          stream: session.component,
          activity: session.lastMessage || '-',
          status: 'active',
          lastSeen: session.lastTimestamp,
        },
        100,
      );
    });
  }

  return prioritized
    .sort((left, right) => {
      if (right.priority !== left.priority) {
        return right.priority - left.priority;
      }
      return right.sortTime - left.sortTime;
    })
    .slice(0, 10)
    .map(({ sortTime: _sortTime, priority: _priority, ...row }) => row);
}

function toErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  return 'Unknown error';
}
