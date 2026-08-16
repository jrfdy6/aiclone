export const EXECUTIVE_DECISIONS_ENDPOINT = '/api/executive/decisions';

export type ExecutiveDecisionPriority = 'critical' | 'high' | 'medium' | 'low';
export type ExecutiveDecisionFreshness = 'today' | 'recent' | 'aging' | 'stale' | 'unknown';
export type ExecutiveDecisionSourceStatus = 'ok' | 'degraded' | 'error';

export type ExecutiveDecisionSourceError = {
  source_type: string;
  message: string;
};

export type ExecutiveDecisionAction = {
  id: string;
  label: string;
  kind: 'open_context' | 'delegate';
  method: 'GET' | 'POST';
  href: string;
  source_href?: string | null;
  requires_confirmation: boolean;
  requires_note: boolean;
};

export type ExecutiveDecision = {
  id: string;
  dedupe_key: string;
  source_type: string;
  source_id: string;
  workspace_key: string;
  title: string;
  what_changed: string;
  why_it_matters: string;
  recommendation: string;
  priority: ExecutiveDecisionPriority;
  priority_score: number;
  freshness: ExecutiveDecisionFreshness;
  updated_at?: string;
  evidence: string[];
  context_href: string;
  actions: ExecutiveDecisionAction[];
};

export type ExecutiveDecisionSummary = {
  total_pending?: number;
  today_count?: number;
  today_candidate_count?: number;
  priority_counts?: Record<string, number>;
  source_counts?: Record<string, number>;
  verification_status?: 'verified' | 'partial';
  verified_clear?: boolean;
};

export type ExecutiveDecisionQueueResponse = {
  generated_at?: string;
  summary: ExecutiveDecisionSummary;
  today: ExecutiveDecision[];
  all_pending: ExecutiveDecision[];
  source_status: Record<string, ExecutiveDecisionSourceStatus>;
  source_errors: ExecutiveDecisionSourceError[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function stringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function numberRecord(value: unknown): Record<string, number> | undefined {
  if (!isRecord(value)) return undefined;
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, entry]) => {
      const number = Number(entry);
      return Number.isFinite(number) ? [[key, number]] : [];
    }),
  );
}

function normalizePriority(value: unknown): ExecutiveDecisionPriority {
  const priority = stringValue(value).toLowerCase();
  return priority === 'critical' || priority === 'high' || priority === 'medium' || priority === 'low'
    ? priority
    : 'low';
}

function normalizeFreshness(value: unknown): ExecutiveDecisionFreshness {
  const freshness = stringValue(value).toLowerCase();
  return freshness === 'today' || freshness === 'recent' || freshness === 'aging' || freshness === 'stale'
    ? freshness
    : 'unknown';
}

function normalizeAction(value: unknown): ExecutiveDecisionAction | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id);
  const label = stringValue(value.label);
  const kind = stringValue(value.kind).toLowerCase();
  const method = stringValue(value.method).toUpperCase();
  const href = kind === 'open_context'
    ? safeExecutiveContextHref(stringValue(value.href))
    : safeExecutiveActionHref(stringValue(value.href));
  if (
    !id ||
    !label ||
    (kind !== 'open_context' && kind !== 'delegate') ||
    (method !== 'GET' && method !== 'POST') ||
    !href
  ) {
    return null;
  }
  const sourceHref = safeExecutiveContextHref(stringValue(value.source_href));
  return {
    id,
    label,
    kind,
    method,
    href,
    ...(sourceHref ? { source_href: sourceHref } : {}),
    requires_confirmation: value.requires_confirmation === true,
    requires_note: value.requires_note === true,
  } as ExecutiveDecisionAction;
}

function normalizeDecision(value: unknown): ExecutiveDecision | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id);
  const title = stringValue(value.title);
  if (!id || !title) return null;
  const priorityScore = Number(value.priority_score);
  return {
    id,
    dedupe_key: stringValue(value.dedupe_key, id),
    source_type: stringValue(value.source_type, 'unknown'),
    source_id: stringValue(value.source_id, id),
    workspace_key: stringValue(value.workspace_key, 'shared_ops'),
    title,
    what_changed: stringValue(value.what_changed, 'A source item is waiting for your decision.'),
    why_it_matters: stringValue(value.why_it_matters, 'The underlying workflow cannot move forward without a decision.'),
    recommendation: stringValue(value.recommendation, 'Open the source context before deciding.'),
    priority: normalizePriority(value.priority),
    priority_score: Number.isFinite(priorityScore) ? priorityScore : 0,
    freshness: normalizeFreshness(value.freshness),
    ...(stringValue(value.updated_at) ? { updated_at: stringValue(value.updated_at) } : {}),
    evidence: Array.isArray(value.evidence)
      ? value.evidence.filter((entry): entry is string => typeof entry === 'string' && Boolean(entry.trim())).map((entry) => entry.trim())
      : [],
    context_href: safeExecutiveContextHref(stringValue(value.context_href)) || '/ops',
    actions: Array.isArray(value.actions)
      ? value.actions.map(normalizeAction).filter((action): action is ExecutiveDecisionAction => Boolean(action))
      : [],
  };
}

function normalizeDecisionList(value: unknown): ExecutiveDecision[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.flatMap((entry) => {
    const decision = normalizeDecision(entry);
    if (!decision || seen.has(decision.id)) return [];
    seen.add(decision.id);
    return [decision];
  });
}

export function normalizeExecutiveDecisionResponse(value: unknown): ExecutiveDecisionQueueResponse {
  const payload = isRecord(value) ? value : {};
  const rawSummary = isRecord(payload.summary) ? payload.summary : {};
  const rawStatus = isRecord(payload.source_status) ? payload.source_status : {};
  const sourceStatus = Object.fromEntries(
    Object.entries(rawStatus).map(([source, status]) => [
      source,
      status === 'ok' || status === 'degraded' ? status : 'error',
    ]),
  ) as Record<string, ExecutiveDecisionSourceStatus>;

  return {
    ...(stringValue(payload.generated_at) ? { generated_at: stringValue(payload.generated_at) } : {}),
    summary: {
      ...(Number.isFinite(Number(rawSummary.total_pending)) ? { total_pending: Number(rawSummary.total_pending) } : {}),
      ...(Number.isFinite(Number(rawSummary.today_count)) ? { today_count: Number(rawSummary.today_count) } : {}),
      ...(Number.isFinite(Number(rawSummary.today_candidate_count)) ? { today_candidate_count: Number(rawSummary.today_candidate_count) } : {}),
      ...(numberRecord(rawSummary.priority_counts) ? { priority_counts: numberRecord(rawSummary.priority_counts) } : {}),
      ...(numberRecord(rawSummary.source_counts) ? { source_counts: numberRecord(rawSummary.source_counts) } : {}),
      ...(rawSummary.verification_status === 'verified' || rawSummary.verification_status === 'partial'
        ? { verification_status: rawSummary.verification_status }
        : {}),
      ...(typeof rawSummary.verified_clear === 'boolean' ? { verified_clear: rawSummary.verified_clear } : {}),
    },
    today: normalizeDecisionList(payload.today),
    all_pending: normalizeDecisionList(payload.all_pending),
    source_status: sourceStatus,
    source_errors: Array.isArray(payload.source_errors)
      ? payload.source_errors.flatMap((entry) => {
          if (!isRecord(entry)) return [];
          return [{
            source_type: stringValue(entry.source_type, 'unknown source'),
            message: stringValue(entry.message, 'Source verification failed.'),
          }];
        })
      : [],
  };
}

export function executiveDecisionCoverage(response: ExecutiveDecisionQueueResponse): {
  partial: boolean;
  failedSources: string[];
  degradedSources: string[];
} {
  const failedSources = new Set<string>();
  const degradedSources = new Set<string>();
  Object.entries(response.source_status).forEach(([source, status]) => {
    if (status === 'error') failedSources.add(source);
    if (status === 'degraded') degradedSources.add(source);
  });
  response.source_errors.forEach((error) => {
    if (response.source_status[error.source_type] === 'degraded') {
      degradedSources.add(error.source_type);
    } else {
      failedSources.add(error.source_type);
    }
  });
  const partial =
    response.summary.verification_status === 'partial' ||
    Object.keys(response.source_status).length === 0 ||
    failedSources.size > 0 ||
    degradedSources.size > 0;
  return {
    partial,
    failedSources: Array.from(failedSources),
    degradedSources: Array.from(degradedSources),
  };
}

export function executableDecisionActions(decision: Pick<ExecutiveDecision, 'actions'>): ExecutiveDecisionAction[] {
  return decision.actions.filter(
    (action) =>
      action.kind === 'delegate' &&
      action.method === 'POST' &&
      action.requires_confirmation &&
      !action.requires_note,
  );
}

export function executiveDecisionActionEndpoint(
  decision: Pick<ExecutiveDecision, 'id'>,
  action: Pick<ExecutiveDecisionAction, 'id' | 'href'>,
): string {
  return safeExecutiveActionHref(action.href) ||
    `${EXECUTIVE_DECISIONS_ENDPOINT}/${encodeURIComponent(decision.id)}/actions/${encodeURIComponent(action.id)}`;
}

export function safeExecutiveContextHref(candidate: string | null | undefined): string | null {
  const value = candidate?.trim();
  if (!value || !value.startsWith('/') || /^\/(?:\/|\\|%2f|%5c)/i.test(value)) return null;
  try {
    const origin = 'https://ai-clone.invalid';
    const resolved = new URL(value, origin);
    return resolved.origin === origin ? `${resolved.pathname}${resolved.search}${resolved.hash}` : null;
  } catch {
    return null;
  }
}

function safeExecutiveActionHref(candidate: string | null | undefined): string | null {
  const href = safeExecutiveContextHref(candidate);
  if (!href) return null;
  try {
    const parsed = new URL(href, 'https://ai-clone.invalid');
    const decodedPath = decodeURIComponent(parsed.pathname);
    return /^\/api\/executive\/decisions\/[^/]+\/actions\/[^/]+\/?$/.test(decodedPath)
      ? `${parsed.pathname}${parsed.search}`
      : null;
  } catch {
    return null;
  }
}
