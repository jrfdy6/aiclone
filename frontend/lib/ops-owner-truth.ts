import { normalizeDisplayText } from '@/lib/display-privacy';

export type OpsOwnerItem = Record<string, unknown>;

export type OpsWorkspaceRecursion = {
  workspace_key?: string;
  display_name?: string;
  goal?: Record<string, unknown>;
  changes_since_prior?: OpsOwnerItem[];
  system_decisions?: OpsOwnerItem[];
  actions_taken?: OpsOwnerItem[];
  completed_work?: OpsOwnerItem[];
  failed_work?: OpsOwnerItem[];
  carried_forward?: OpsOwnerItem[];
  owner_decisions?: OpsOwnerItem[];
  blocked?: OpsOwnerItem[];
  no_action?: OpsOwnerItem[];
  recommendations?: OpsOwnerItem[];
  reference_only?: OpsOwnerItem[];
  next_cycle_inputs?: OpsOwnerItem[];
  recommendation_resolutions?: OpsOwnerItem[];
};

export type OpsSharedReconciliation = {
  display_name?: string;
  role?: 'portfolio_reconciler';
  summary?: string;
  goal?: Record<string, unknown>;
  evaluated?: OpsOwnerItem[];
  system_decisions?: OpsOwnerItem[];
  actions_taken?: OpsOwnerItem[];
  owner_calls?: OpsOwnerItem[];
  blocked?: OpsOwnerItem[];
  no_action?: OpsOwnerItem[];
  recommendations?: OpsOwnerItem[];
  reference_only?: OpsOwnerItem[];
  next_cycle_inputs?: OpsOwnerItem[];
};

export type OpsOwnerProjection = {
  schema_version?: string;
  generated_at?: string;
  observed_at?: string | null;
  portfolio_cycle_id?: string | null;
  ops_conclusion_attempt_number?: number | null;
  cycle_date?: string | null;
  clock?: Record<string, unknown> | null;
  state?: 'ready' | 'empty' | 'degraded' | 'error';
  reason_codes?: string[];
  status?: string;
  workspace_updates?: OpsOwnerItem[];
  workspace_recursion?: OpsWorkspaceRecursion[];
  workspace_cycle_evaluations?: Array<Record<string, unknown>>;
  shared_ops_reconciliation?: OpsSharedReconciliation | null;
  ai_clone_process_updates?: Record<string, unknown>;
  endpoint_and_subsystem_health?: Record<string, unknown>;
  work_underway?: OpsOwnerItem[];
  completed_work?: OpsOwnerItem[];
  blockers?: OpsOwnerItem[];
  urgent_escalations?: OpsOwnerItem[];
  workspace_decisions?: OpsOwnerItem[];
  ops_decisions?: OpsOwnerItem[];
  owner_calls?: OpsOwnerItem[];
  canonical_decisions?: OpsOwnerItem[];
  decision_readiness?: {
    state?: 'ready' | 'degraded';
    clock_authority?: string;
    checked_at?: string;
    source_updated_at?: string | null;
    blocking_reason_codes?: string[];
    context_warnings?: string[];
  };
  degraded_system_warnings?: string[];
  supporting_evidence_links?: OpsOwnerItem[];
  recommended_next_actions?: OpsOwnerItem[];
};

export type OpsWorkspaceGoalProjection = {
  schema_version?: string;
  generated_at?: string;
  observed_at?: string | null;
  state?: 'ready' | 'unavailable';
  reason_codes?: string[];
  authority_sha256?: string | null;
  projected_contracts_sha256?: string | null;
  workspaces?: Array<{
    workspace_key?: string;
    display_name?: string;
    goal?: Record<string, unknown>;
  }>;
};

export type WorkspaceOwnerTruthState =
  | 'healthy'
  | 'no_change'
  | 'blocked'
  | 'degraded'
  | 'empty'
  | 'unavailable';

export type WorkspaceGoalContractProjection = {
  schemaVersion: 'workspace_goal_contract/v1';
  goal: string;
  progressSignals: string[];
  phaseGate: string;
  noActionTrigger: string;
};

export type WorkspaceOwnerTruth = {
  workspaceKey: string;
  displayName: string;
  state: WorkspaceOwnerTruthState;
  currentState: string;
  affected: string | null;
  remainsHealthy: string;
  goal: string | null;
  progressSignals: string[];
  phaseGate: string | null;
  reevaluateWhen: string | null;
  changes: string[];
  decisions: string[];
  actions: string[];
  completed: string[];
  failed: string[];
  carried: string[];
  ownerDecisions: string[];
  blockers: string[];
  noChange: string[];
  recommendations: string[];
  nextDream: string[];
  recommendationResolutions: string[];
  referenceCount: number;
  hasCurrentConclusion: boolean;
};

export type PortfolioOwnerTruth = {
  state: WorkspaceOwnerTruthState;
  currentState: string;
  affected: string | null;
  remainsHealthy: string;
  whatChanged: string;
  actions: string[];
  ownerDecisions: string[];
  attention: string[];
  blockers: string[];
  recommendations: string[];
  nextDream: string;
  workspaces: WorkspaceOwnerTruth[];
};

const INTERNAL_UUID_PATTERN = /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi;
const PRIVATE_PLACEHOLDER_PATTERN = /\[(?:private-workspace-context|private-local-reference-removed)\]/gi;
const PRIVATE_PLACEHOLDER_TEST_PATTERN = /\[(?:private-workspace-context|private-local-reference-removed)\]/i;
const GENERIC_CYCLE_PLAN_PATTERN = /^Workspace cycle plan \(no meeting held\):/i;
const INTERNAL_ONLY_PATTERN = /^(?:coordination-record:|automation-run:|[a-z0-9]+(?:_[a-z0-9]+){2,})$/i;

const WORKSPACE_DISPLAY_NAMES: Record<string, string> = {
  agc: 'AGC',
  'ai-swag-store': 'AI Swag Store',
  easyoutfitapp: 'Easy Outfit App',
  'feezie-os': 'FEEZIE OS',
  'fusion-os': 'Fusion OS',
  'work-life-tools': 'Work Life Tools',
};

function arrayOfItems(value: unknown): OpsOwnerItem[] {
  return Array.isArray(value)
    ? value.filter((item): item is OpsOwnerItem => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
    : [];
}

export function normalizeOpsWorkspaceKey(value: unknown): string {
  const key = String(value ?? '').trim().toLowerCase().replaceAll(' ', '-');
  if (key === 'linkedin-os' || key === 'linkedin-content-os' || key === 'feezie') return 'feezie-os';
  if (key === 'easy-outfit-app' || key === 'easy-outfit') return 'easyoutfitapp';
  if (key === 'ai-swag' || key === 'swag-store') return 'ai-swag-store';
  return key;
}

function displayName(workspaceKey: string, projectedName?: unknown): string {
  const safeProjected = ownerSafeOpsText(projectedName, 120);
  return safeProjected || WORKSPACE_DISPLAY_NAMES[workspaceKey] || 'Workspace';
}

export function ownerSafeOpsText(value: unknown, limit = 360): string {
  const normalized = normalizeDisplayText(String(value ?? ''))
    .replace(PRIVATE_PLACEHOLDER_PATTERN, '')
    .replace(INTERNAL_UUID_PATTERN, 'record')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
  if (!normalized || INTERNAL_ONLY_PATTERN.test(normalized)) return '';
  return normalized.slice(0, limit);
}

function rawField(item: OpsOwnerItem, key: string): string {
  const value = item[key];
  return typeof value === 'string' || typeof value === 'number'
    ? String(value).trim()
    : '';
}

function boundedSentence(value: string, limit = 300): string {
  const firstSentence = value.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim();
  const candidate = firstSentence && firstSentence.length >= 28 ? firstSentence : value;
  if (candidate.length <= limit) return candidate;
  return `${candidate.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

function participantReceiptCopy(workspaceName: string): string {
  return `${workspaceName} did not receive every required signed participant receipt, so this cycle could not accept a new workspace conclusion.`;
}

function privateContextCopy(workspaceName: string): string {
  return `${workspaceName}'s current conclusion could not be verified through the bounded public projection. Private source material remains confined to its authorized workspace lane.`;
}

export function ownerItemText(item: OpsOwnerItem, workspaceName = 'This workspace'): string {
  const rawSummary = rawField(item, 'summary');
  const rawReason = rawField(item, 'reason_code') || rawField(item, 'kind');
  if (rawSummary === 'participant_receipt_unavailable' || rawReason === 'participant_receipt_unavailable') {
    return participantReceiptCopy(workspaceName);
  }
  if (
    PRIVATE_PLACEHOLDER_TEST_PATTERN.test(rawSummary)
    || PRIVATE_PLACEHOLDER_TEST_PATTERN.test(rawReason)
    || rawSummary === 'private workspace context'
  ) {
    return privateContextCopy(workspaceName);
  }
  if (rawSummary === 'No conclusion receipt received.') {
    return `${workspaceName} did not return a current conclusion receipt.`;
  }

  const candidates = [
    rawField(item, 'commitment'),
    rawField(item, 'decision'),
    rawField(item, 'title'),
    rawField(item, 'label'),
    GENERIC_CYCLE_PLAN_PATTERN.test(rawSummary) ? '' : rawSummary,
    rawField(item, 'impact'),
    rawField(item, 'reason'),
    rawField(item, 'explanation'),
    rawField(item, 'next_step'),
  ];
  for (const candidate of candidates) {
    const safe = ownerSafeOpsText(candidate);
    if (safe) return boundedSentence(safe);
  }
  if (GENERIC_CYCLE_PLAN_PATTERN.test(rawSummary)) {
    return 'AI Clone evaluated the current PM, memory, Brain, and workspace context without claiming that a meeting occurred.';
  }
  return '';
}

function uniqueFacts(items: unknown, workspaceName: string, limit = 8): string[] {
  const seen = new Set<string>();
  const facts: string[] = [];
  for (const item of arrayOfItems(items)) {
    const fact = ownerItemText(item, workspaceName);
    const key = fact.toLowerCase();
    if (!fact || seen.has(key)) continue;
    seen.add(key);
    facts.push(fact);
    if (facts.length >= limit) break;
  }
  return facts;
}

function goalText(goal: Record<string, unknown> | undefined, key: string, limit = 900): string | null {
  const text = ownerSafeOpsText(goal?.[key], limit);
  return text || null;
}

function projectedProgressSignals(goal: Record<string, unknown> | undefined): string[] {
  const values = Array.isArray(goal?.progress_signals) ? goal.progress_signals : [];
  const seen = new Set<string>();
  return values.flatMap((value) => {
    const text = ownerSafeOpsText(value, 500);
    const key = text.toLowerCase();
    if (!text || seen.has(key)) return [];
    seen.add(key);
    return [text];
  }).slice(0, 6);
}

export function projectWorkspaceGoalContract(
  value: unknown,
): WorkspaceGoalContractProjection | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  const goal = goalText(raw, 'goal');
  const phaseGate = goalText(raw, 'phase_gate');
  const noActionTrigger = goalText(raw, 'no_action_trigger');
  const progressSignals = projectedProgressSignals(raw);
  if (
    raw.schema_version !== 'workspace_goal_contract/v1'
    || !goal
    || !phaseGate
    || !noActionTrigger
    || progressSignals.length === 0
  ) {
    return null;
  }
  return {
    schemaVersion: 'workspace_goal_contract/v1',
    goal,
    progressSignals,
    phaseGate,
    noActionTrigger,
  };
}

export function projectOpsWorkspaceGoals(
  projection: OpsOwnerProjection | null | undefined,
  goalProjection?: OpsWorkspaceGoalProjection | null,
): Map<string, WorkspaceGoalContractProjection> {
  const goals = new Map<string, WorkspaceGoalContractProjection>();
  if (
    goalProjection?.schema_version === 'ops_workspace_goal_projection/v1'
    && goalProjection.state === 'ready'
    && Array.isArray(goalProjection.workspaces)
  ) {
    for (const row of goalProjection.workspaces) {
      const workspaceKey = normalizeOpsWorkspaceKey(row.workspace_key);
      const goal = projectWorkspaceGoalContract(row.goal);
      if (workspaceKey in WORKSPACE_DISPLAY_NAMES && goal && !goals.has(workspaceKey)) {
        goals.set(workspaceKey, goal);
      }
    }
  }
  if (
    projection?.schema_version !== 'ops_standup_summary_conclusion/v3'
    || !Array.isArray(projection.workspace_recursion)
  ) {
    return goals;
  }
  const sharedGoal = projectWorkspaceGoalContract(
    projection.shared_ops_reconciliation?.goal,
  );
  if (sharedGoal) goals.set('shared_ops', sharedGoal);
  for (const row of projection.workspace_recursion) {
    const workspaceKey = normalizeOpsWorkspaceKey(row.workspace_key);
    const goal = projectWorkspaceGoalContract(row.goal);
    if (workspaceKey && goal && !goals.has(workspaceKey)) goals.set(workspaceKey, goal);
  }
  return goals;
}

function recommendationResolutionText(item: OpsOwnerItem): string {
  const title = ownerItemText(item, 'This workspace') || 'A bounded recommendation';
  const state = rawField(item, 'state') || rawField(item, 'resolution_state');
  const stateCopy: Record<string, string> = {
    executed_automatically: 'completed through the authorized internal lane',
    placed_in_execution_queue: 'entered the governed execution lane',
    bounded_owner_decision: 'requires an explicit owner decision',
    retained: 'was retained for later review',
    rejected: 'was not accepted',
    closed_without_execution: 'was closed without execution',
    superseded: 'was superseded by newer accepted evidence',
  };
  const disposition = stateCopy[state] || ownerSafeOpsText(state, 80).replaceAll('_', ' ');
  const explanation = ownerSafeOpsText(rawField(item, 'explanation'), 240);
  const futureTrigger = ownerSafeOpsText(rawField(item, 'future_trigger'), 240);
  return [
    disposition ? `${title} — ${disposition}.` : title,
    explanation,
    futureTrigger ? `Reevaluate when: ${futureTrigger}` : '',
  ].filter(Boolean).join(' ');
}

function uniqueRecommendationResolutions(items: unknown, limit = 8): string[] {
  const seen = new Set<string>();
  const facts: string[] = [];
  for (const item of arrayOfItems(items)) {
    const fact = recommendationResolutionText(item);
    const key = fact.toLowerCase();
    if (!fact || seen.has(key)) continue;
    seen.add(key);
    facts.push(fact);
    if (facts.length >= limit) break;
  }
  return facts;
}

function updateWorkspaceKey(item: OpsOwnerItem): string {
  return normalizeOpsWorkspaceKey(item.workspace_key ?? item.workspace ?? item.display_name ?? '');
}

function missingWorkspaceUpdate(projection: OpsOwnerProjection, workspaceKey: string): OpsOwnerItem | undefined {
  return arrayOfItems(projection.workspace_updates).find((item) => (
    updateWorkspaceKey(item) === workspaceKey && String(item.state ?? '').toLowerCase() === 'missing'
  ));
}

function missingWorkspaceTruth(
  projection: OpsOwnerProjection,
  workspaceKey: string,
  projectedName?: unknown,
  goalContract?: WorkspaceGoalContractProjection | null,
): WorkspaceOwnerTruth {
  const name = displayName(workspaceKey, projectedName);
  const missingUpdate = missingWorkspaceUpdate(projection, workspaceKey);
  const missingReason = missingUpdate ? ownerItemText(missingUpdate, name) : '';
  return {
    workspaceKey,
    displayName: name,
    state: projection.state === 'empty' ? 'empty' : projection.state === 'error' ? 'unavailable' : 'blocked',
    currentState: projection.state === 'empty'
      ? `No current ${name} conclusion exists yet.`
      : `${missingReason || `${name} has no current bounded conclusion.`} The system is not treating this as a successful cycle.`,
    affected: `This cycle's ${name} conclusion and any downstream update that requires it.`,
    remainsHealthy: `${goalContract ? 'The canonical goal, ' : ''}previously accepted ${name} records, its PM lane, and existing execution receipts remain readable; they are not being relabeled as current.`,
    goal: goalContract?.goal ?? null,
    progressSignals: goalContract?.progressSignals ?? [],
    phaseGate: goalContract?.phaseGate ?? null,
    reevaluateWhen: goalContract?.noActionTrigger ?? null,
    changes: ['No new canonical workspace change was accepted in this cycle.'],
    decisions: [],
    actions: [],
    completed: [],
    failed: [missingReason || `${name} did not return a current conclusion receipt.`],
    carried: [`The last accepted ${name} truth and unresolved PM/execution state remain in place.`],
    ownerDecisions: [],
    blockers: [missingReason || `${name}'s current conclusion is unavailable.`],
    noChange: [],
    recommendations: ['Keep using the prior accepted workspace truth while the governed conclusion path is repaired. No owner decision is implied by this system failure.'],
    nextDream: [`The next Dream cycle may consume prior accepted ${name} truth and unresolved PM/execution state, but it must not treat this missing conclusion as completed work.`],
    recommendationResolutions: [],
    referenceCount: 0,
    hasCurrentConclusion: false,
  };
}

export function projectWorkspaceOwnerTruth(
  projection: OpsOwnerProjection | null | undefined,
  requestedWorkspaceKey: string,
  goalSource?: OpsWorkspaceGoalProjection | Map<string, WorkspaceGoalContractProjection> | null,
): WorkspaceOwnerTruth {
  const workspaceKey = normalizeOpsWorkspaceKey(requestedWorkspaceKey);
  const workspaceGoals = goalSource instanceof Map
    ? goalSource
    : projectOpsWorkspaceGoals(projection, goalSource);
  const projectedGoal = workspaceGoals.get(workspaceKey) ?? null;
  if (!projection) {
    return missingWorkspaceTruth({ state: 'error' }, workspaceKey, undefined, projectedGoal);
  }
  if (projection.schema_version !== 'ops_standup_summary_conclusion/v3') {
    return missingWorkspaceTruth({ state: 'error' }, workspaceKey, undefined, projectedGoal);
  }
  const recursion = Array.isArray(projection.workspace_recursion) ? projection.workspace_recursion : [];
  const row = recursion.find((candidate) => normalizeOpsWorkspaceKey(candidate.workspace_key) === workspaceKey);
  if (!row) return missingWorkspaceTruth(projection, workspaceKey, undefined, projectedGoal);

  const name = displayName(workspaceKey, row.display_name);
  const changes = uniqueFacts(row.changes_since_prior, name);
  const decisions = uniqueFacts(row.system_decisions, name);
  const actions = uniqueFacts(row.actions_taken, name);
  const completed = uniqueFacts(row.completed_work, name);
  const failed = uniqueFacts(row.failed_work, name);
  const carried = uniqueFacts(row.carried_forward, name);
  const ownerDecisions = uniqueFacts(row.owner_decisions, name);
  const blockers = uniqueFacts(row.blocked, name);
  const noChange = uniqueFacts(row.no_action, name);
  const recommendations = uniqueFacts(row.recommendations, name);
  const recommendationResolutions = uniqueRecommendationResolutions(row.recommendation_resolutions);
  let nextDream = uniqueFacts(row.next_cycle_inputs, name);
  const receiptBlocked = [...blockers, ...failed].some((fact) => /required signed participant receipt|conclusion receipt/i.test(fact));
  if (receiptBlocked) {
    nextDream = [`The next Dream cycle will retain prior accepted ${name} truth and unresolved PM/execution state; it will not consume this failed handoff as a completed update.`];
  }

  const goalContract = projectedGoal ?? projectWorkspaceGoalContract(row.goal);
  let state: WorkspaceOwnerTruthState = 'healthy';
  if (blockers.length || failed.length) state = 'blocked';
  else if (!goalContract) state = 'degraded';
  else if (noChange.length && !actions.length && !completed.length) state = 'no_change';
  else if (!changes.length && !actions.length && !completed.length && !decisions.length) state = 'empty';

  const goal = goalContract?.goal ?? null;
  const phaseGate = goalContract?.phaseGate ?? null;
  const reevaluateWhen = goalContract?.noActionTrigger ?? null;
  const firstProblem = blockers[0] || failed[0] || null;
  const currentState = state === 'blocked'
    ? `Blocked for this cycle. ${firstProblem || 'A required conclusion step failed.'}`
    : state === 'degraded'
      ? 'Degraded. The current conclusion is present, but its governed goal contract is unavailable or malformed.'
    : state === 'no_change'
      ? `Healthy — no eligible change. ${noChange[0] || 'The existing canonical update remains current.'}`
      : state === 'empty'
        ? 'No new activity was recorded in the current conclusion.'
        : actions.length || completed.length
          ? 'Current. The workspace returned a bounded conclusion with recorded activity.'
          : 'Current. The workspace returned a bounded conclusion without claiming new work.';

  return {
    workspaceKey,
    displayName: name,
    state,
    currentState,
    affected: firstProblem
      ? `This cycle's ${name} conclusion and downstream updates that require a newly accepted receipt.`
      : state === 'degraded'
        ? `${name}'s goal, progress criteria, phase gate, and no-action trigger in this cycle projection.`
        : null,
    remainsHealthy: goal
      ? `The canonical goal, previously accepted workspace records, PM state, and existing execution receipts remain readable.`
      : `Previously accepted workspace records, PM state, and existing execution receipts remain readable.`,
    goal,
    progressSignals: goalContract?.progressSignals ?? [],
    phaseGate,
    reevaluateWhen,
    changes: changes.length ? changes : ['No new canonical change was claimed by this conclusion.'],
    decisions,
    actions,
    completed,
    failed,
    carried,
    ownerDecisions,
    blockers,
    noChange,
    recommendations: recommendations.length
      ? recommendations
      : receiptBlocked
        ? ['Repair the governed participant handoff, then let the next natural cycle produce a fresh conclusion. No replay is being used to manufacture success.']
        : [],
    nextDream: nextDream.length
      ? nextDream
      : [`The next Dream cycle may consume this accepted ${name} conclusion together with unresolved PM and execution state.`],
    recommendationResolutions,
    referenceCount: arrayOfItems(row.reference_only).length,
    hasCurrentConclusion: true,
  };
}

function workspaceKeysInProjection(projection: OpsOwnerProjection): string[] {
  const keys = new Set<string>();
  for (const row of projection.workspace_recursion ?? []) {
    const key = normalizeOpsWorkspaceKey(row.workspace_key);
    if (key && key !== 'shared_ops' && key !== 'shared-ops') keys.add(key);
  }
  for (const item of arrayOfItems(projection.workspace_updates)) {
    const key = updateWorkspaceKey(item);
    if (key && key !== 'shared_ops' && key !== 'shared-ops') keys.add(key);
  }
  return [...keys];
}

function allFacts(items: unknown, workspaceName: string, limit = 8): string[] {
  return uniqueFacts(items, workspaceName, limit);
}

function canonicalOpenDecisionFacts(projection: OpsOwnerProjection): string[] {
  return arrayOfItems(projection.canonical_decisions).flatMap((item) => {
    const status = String(item.status ?? '').toLowerCase();
    if (status && !['open', 'pending', 'needs_owner', 'awaiting_owner'].includes(status)) return [];
    const text = ownerItemText(item, 'The portfolio');
    return text ? [text] : [];
  });
}

export function projectPortfolioOwnerTruth(
  projection: OpsOwnerProjection,
  knownWorkspaceKeys: string[] = [],
  goalProjection?: OpsWorkspaceGoalProjection | null,
): PortfolioOwnerTruth {
  const workspaceGoals = projectOpsWorkspaceGoals(projection, goalProjection);
  const workspaceKeys = [...new Set([
    ...knownWorkspaceKeys.map(normalizeOpsWorkspaceKey),
    ...workspaceGoals.keys(),
    ...workspaceKeysInProjection(projection),
  ].filter((key) => Boolean(key) && key !== 'shared_ops' && key !== 'shared-ops'))];
  const workspaces = workspaceKeys.map((key) => projectWorkspaceOwnerTruth(projection, key, workspaceGoals));
  const blockedWorkspaces = workspaces.filter((workspace) => workspace.state === 'blocked' || workspace.state === 'unavailable');
  const missingWorkspaces = workspaces.filter((workspace) => !workspace.hasCurrentConclusion);
  const shared = projection.shared_ops_reconciliation;
  const sharedActions = allFacts(shared?.actions_taken, 'Shared Ops');
  const topActions = allFacts(projection.completed_work, 'AI Clone');
  const attention = [...new Set([
    ...allFacts(projection.owner_calls, 'The portfolio'),
    ...allFacts(shared?.owner_calls, 'Shared Ops'),
  ])];
  const ownerDecisions = [...new Set([
    ...canonicalOpenDecisionFacts(projection),
    ...workspaces.flatMap((workspace) => workspace.ownerDecisions),
  ])];
  const recommendations = allFacts(projection.recommended_next_actions, 'The portfolio');
  const explicitDream = allFacts(shared?.next_cycle_inputs, 'Shared Ops')
    .find((fact) => /^The next Dream\b/i.test(fact));
  const acceptedCount = workspaces.filter((workspace) => (
    workspace.hasCurrentConclusion
    && workspace.state !== 'blocked'
    && workspace.state !== 'unavailable'
    && workspace.state !== 'degraded'
  )).length;
  const goalCount = workspaces.filter((workspace) => Boolean(workspace.goal)).length;
  const names = blockedWorkspaces.map((workspace) => workspace.displayName);
  const blockers = blockedWorkspaces.length
    ? [`${blockedWorkspaces.length} of ${workspaces.length || blockedWorkspaces.length} project workspace conclusion${blockedWorkspaces.length === 1 ? '' : 's'} are blocked or missing${names.length ? `: ${names.join(', ')}` : ''}.`]
    : [];
  const validProjection = projection.schema_version === 'ops_standup_summary_conclusion/v3';
  const projectionState = validProjection ? projection.state ?? 'error' : 'error';
  const state: WorkspaceOwnerTruthState = projectionState === 'ready'
    ? blockedWorkspaces.length
      ? 'degraded'
      : 'healthy'
    : projectionState === 'empty'
      ? 'empty'
      : projectionState === 'error'
        ? 'unavailable'
        : 'degraded';
  const returnedCount = workspaces.filter((workspace) => workspace.hasCurrentConclusion).length;

  return {
    state,
    currentState: state === 'healthy'
      ? 'Ready. Every required project conclusion returned and the bounded portfolio conclusion is available.'
      : state === 'empty'
        ? 'Empty. No final portfolio conclusion has been recorded yet.'
        : state === 'unavailable'
          ? 'Unavailable. The final portfolio conclusion could not be loaded, so no readiness claim is being made.'
          : projectionState === 'ready' && blockedWorkspaces.length
            ? 'Degraded. The top-level conclusion says ready, but one or more workspace conclusions are blocked, missing, or malformed; the contradiction is not being presented as an all-clear.'
            : 'Degraded. The current portfolio conclusion is incomplete and is not being presented as an all-clear.',
    affected: blockedWorkspaces.length
      ? `A complete current portfolio conclusion and the ${names.join(', ')} cycle lane${names.length === 1 ? '' : 's'}.`
      : null,
    remainsHealthy: `${returnedCount} bounded workspace report${returnedCount === 1 ? '' : 's'} ${returnedCount === 1 ? 'remains' : 'remain'} readable, including scoped failures. Of those, ${acceptedCount} ${acceptedCount === 1 ? 'is accepted as a current conclusion' : 'are accepted as current conclusions'}. ${goalCount} governed workspace goal${goalCount === 1 ? '' : 's'}, prior accepted evidence, and separately verified decision readiness remain available.`,
    whatChanged: missingWorkspaces.length
      ? `${returnedCount} of ${workspaces.length || returnedCount} workspace conclusions returned; ${missingWorkspaces.map((workspace) => workspace.displayName).join(', ')} did not return a current conclusion.`
      : returnedCount
        ? `${returnedCount} workspace conclusion${returnedCount === 1 ? '' : 's'} returned in this cycle.`
        : 'No new workspace conclusion is claimed by this cycle.',
    actions: [...new Set([...sharedActions, ...topActions])],
    ownerDecisions,
    attention,
    blockers,
    recommendations,
    nextDream: explicitDream
      || (blockedWorkspaces.length
        ? 'The next Dream cycle can consume the accepted workspace conclusions and unresolved PM/execution state, but it must not treat missing or failed lanes as completed work.'
        : 'The next Dream cycle can consume this bounded Ops conclusion and its linked workspace receipts through the existing structured-memory lane.'),
    workspaces,
  };
}
