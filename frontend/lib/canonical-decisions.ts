export type CanonicalDecisionStatus = 'open' | 'in_session' | 'blocked' | 'resolved' | 'canceled' | 'superseded';
export type PMOwnerDecisionChoice =
  | 'approve_bounded_internal_action'
  | 'reject_recommendation'
  | 'retain_until_trigger';

export const PM_OWNER_DECISION_CHOICES: Array<{ value: PMOwnerDecisionChoice; label: string }> = [
  { value: 'approve_bounded_internal_action', label: 'Approve bounded internal action' },
  { value: 'reject_recommendation', label: 'Reject recommendation' },
  { value: 'retain_until_trigger', label: 'Retain until future trigger' },
];

const AUTOMATIC_SYSTEM_DECISION_TYPES = new Set([
  'standup_async_system_decision',
]);
const OWNER_DECISION_TYPES = new Set([
  'owner_call',
  'pm_owner_decision',
  'content',
  'architecture',
  'simple',
]);

export type CanonicalDecision = {
  decision_id: string;
  decision_type: string;
  title: string;
  status: CanonicalDecisionStatus;
  state_version: number;
  interaction_mode: 'simple' | 'complex';
  route: 'ops' | 'workspace' | 'content' | 'feezie-os' | 'fusion-os' | 'easyoutfitapp' | 'ai-swag-store' | 'agc' | 'work-life-tools';
  resolution: Record<string, unknown>;
  session_ref?: string | null;
  updated_at: string;
  links: Array<{ surface: string; external_ref: string }>;
};

export type ReconciledCanonicalDecision = CanonicalDecision & {
  visible_in: Array<'content' | 'ops'>;
  projection_conflict: boolean;
};

export type CanonicalDecisionJobReceipt = {
  job_id: string;
  card_id?: string;
};

export type CanonicalDecisionJobStatus = {
  job_id: string;
  card_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  message?: string | null;
  error?: string | null;
};

function isDecision(value: unknown): value is CanonicalDecision {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<CanonicalDecision>;
  return Boolean(
    String(item.decision_id || '').trim()
    && String(item.decision_type || '').trim()
    && String(item.title || '').trim()
    && Number.isInteger(item.state_version)
    && Number(item.state_version) > 0
    && ['open', 'in_session', 'blocked', 'resolved', 'canceled', 'superseded'].includes(String(item.status)),
  );
}

export function isAutomaticSystemDecisionType(value: unknown) {
  return typeof value === 'string'
    && AUTOMATIC_SYSTEM_DECISION_TYPES.has(value.replace(/\s+/g, ' ').trim().toLowerCase());
}

export function isCanonicalOwnerDecisionType(value: unknown) {
  return typeof value === 'string'
    && OWNER_DECISION_TYPES.has(value.replace(/\s+/g, ' ').trim().toLowerCase());
}

export function reconcileCanonicalDecisionViews(
  content: unknown[],
  ops: unknown[],
): ReconciledCanonicalDecision[] {
  const rows = new Map<string, { content?: CanonicalDecision; ops?: CanonicalDecision }>();
  for (const [surface, values] of [['content', content], ['ops', ops]] as const) {
    for (const value of values) {
      if (!isDecision(value)) continue;
      const current = rows.get(value.decision_id) ?? {};
      current[surface] = value;
      rows.set(value.decision_id, current);
    }
  }
  return [...rows.values()]
    .map((views) => {
      const contentDecision = views.content;
      const opsDecision = views.ops;
      const selected = !contentDecision
        ? opsDecision!
        : !opsDecision
          ? contentDecision
          : contentDecision.state_version >= opsDecision.state_version
            ? contentDecision
            : opsDecision;
      const visibleIn: Array<'content' | 'ops'> = [
        ...(contentDecision ? ['content' as const] : []),
        ...(opsDecision ? ['ops' as const] : []),
      ];
      return {
        ...selected,
        visible_in: visibleIn,
        projection_conflict: !contentDecision
          || !opsDecision
          || contentDecision.state_version !== opsDecision.state_version
          || contentDecision.status !== opsDecision.status
          || contentDecision.decision_type !== opsDecision.decision_type,
      };
    })
    .sort((left, right) => right.updated_at.localeCompare(left.updated_at) || left.decision_id.localeCompare(right.decision_id));
}

export function reconcileCanonicalOwnerDecisionViews(
  content: unknown[],
  ops: unknown[],
): ReconciledCanonicalDecision[] {
  // Any non-owner type on either canonical projection excludes the identity
  // from Owner Decisions. Generic reconciliation remains available to neutral
  // Ops/system-decision views, preserving the exact type.
  const nonOwnerIds = new Set<string>();
  for (const value of [...content, ...ops]) {
    if (!value || typeof value !== 'object') continue;
    const item = value as Partial<CanonicalDecision>;
    const decisionId = String(item.decision_id || '').trim();
    if (decisionId && !isCanonicalOwnerDecisionType(item.decision_type)) {
      nonOwnerIds.add(decisionId);
    }
  }
  return reconcileCanonicalDecisionViews(content, ops).filter(
    (decision) => !nonOwnerIds.has(decision.decision_id),
  );
}

export function canonicalDecisionActionRequest(
  decision: CanonicalDecision,
  action: 'begin_session' | 'resolve' | 'block' | 'reopen' | 'cancel',
  resolutionText = '',
) {
  if (isAutomaticSystemDecisionType(decision.decision_type)) {
    throw new Error('Automatic system decisions are read-only on the Owner Decisions surface.');
  }
  if (!isCanonicalOwnerDecisionType(decision.decision_type)) {
    throw new Error('Unverified decision types are read-only on the Owner Decisions surface.');
  }
  if (decision.status === 'resolved' || decision.status === 'canceled' || decision.status === 'superseded') {
    throw new Error('Terminal decisions cannot be changed.');
  }
  if (action === 'begin_session' && (decision.interaction_mode !== 'complex' || decision.status === 'in_session')) {
    throw new Error('Only an open or blocked complex decision can begin a shared session.');
  }
  if (decision.decision_type === 'pm_owner_decision' && action !== 'resolve') {
    throw new Error('PM owner decisions use one bounded PM recommendation choice.');
  }
  if (action === 'resolve') {
    const choice = resolutionText.trim();
    if (!choice) throw new Error('Record the canonical resolution before resolving.');
    if (decision.interaction_mode === 'complex' && decision.status !== 'in_session') {
      throw new Error('Complex decisions must use the shared session before resolution.');
    }
    if (
      decision.decision_type === 'pm_owner_decision'
      && !PM_OWNER_DECISION_CHOICES.some((candidate) => candidate.value === choice)
    ) {
      throw new Error('Choose one of the bounded PM recommendation outcomes.');
    }
    return { expected_version: decision.state_version, action, resolution: { choice } };
  }
  return { expected_version: decision.state_version, action };
}

export function canonicalDecisionActionEndpoint(decisionId: string) {
  const normalized = String(decisionId || '').trim();
  if (!normalized) throw new Error('A canonical decision identity is required.');
  return `/api/workspace/decisions/${encodeURIComponent(normalized)}/actions`;
}

export async function waitForCanonicalDecisionJob({
  receipt,
  readStatus,
  sleep = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  pollIntervalMs = 2_500,
  timeoutMs = 120_000,
}: {
  receipt: CanonicalDecisionJobReceipt;
  readStatus: (jobId: string) => Promise<CanonicalDecisionJobStatus>;
  sleep?: (milliseconds: number) => Promise<void>;
  pollIntervalMs?: number;
  timeoutMs?: number;
}) {
  const jobId = String(receipt.job_id || '').trim();
  if (!jobId || (receipt.card_id && receipt.card_id !== jobId)) {
    throw new Error('The decision receipt did not identify one exact signed local action.');
  }
  const attempts = Math.max(1, Math.ceil(timeoutMs / pollIntervalMs));
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const status = await readStatus(jobId);
    if (status.job_id !== jobId || status.card_id !== jobId) {
      throw new Error('The decision status did not match the exact queued action.');
    }
    if (status.status === 'completed') return status;
    if (status.status === 'failed') {
      throw new Error(status.error || status.message || 'The canonical decision action failed.');
    }
    if (attempt + 1 < attempts) await sleep(pollIntervalMs);
  }
  throw new Error('The canonical decision action did not complete within two minutes.');
}
