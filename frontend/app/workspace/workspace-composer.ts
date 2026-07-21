export type PostingAudience = 'general' | 'education_admissions' | 'tech_ai' | 'leadership' | 'entrepreneurs';
export type ComposerMode = 'post' | 'comment';

export type WorkspaceComposerQuery = {
  mode: ComposerMode;
  autoplay: boolean;
  itemKey: string;
  briefId: string;
  originType: string;
  originId: string;
  returnUrl: string;
  ownerReaction: string;
  title: string;
  summary: string;
  hook: string;
  sourceUrl: string;
  sourcePath: string;
  priorityLane: string;
  sourceKind: string;
  routeReason: string;
  targetFile: string;
  section: string;
};

export type WorkspaceQuerySeed = Pick<
  WorkspaceComposerQuery,
  | 'itemKey'
  | 'briefId'
  | 'originType'
  | 'originId'
  | 'returnUrl'
  | 'ownerReaction'
  | 'title'
  | 'summary'
  | 'hook'
  | 'sourceUrl'
  | 'sourcePath'
  | 'priorityLane'
  | 'sourceKind'
  | 'routeReason'
  | 'targetFile'
  | 'section'
>;

export type WorkspaceSourceCard = {
  item_key?: string;
  brief_id?: string;
  origin_type?: string;
  origin_id?: string;
  owner_reaction?: string;
  title?: string;
  summary?: string;
  hook?: string;
  source_url?: string;
  source_path?: string;
  priority_lane?: string;
  source_kind?: string;
  route_reason?: string;
  target_file?: string;
  section?: string;
};

type SearchParamsLike = {
  get(name: string): string | null;
} | null | undefined;

function cleanParam(value: string | null) {
  return value?.trim() ?? '';
}

export function normalizeWorkspaceReturnUrl(value: string | null | undefined, fallback = '/brain') {
  const candidate = value?.trim() ?? '';
  if (!candidate.startsWith('/') || /^\/(?:\/|\\|%2f|%5c)/i.test(candidate) || /[\r\n]/.test(candidate)) {
    return fallback;
  }
  try {
    const origin = 'https://ai-clone.invalid';
    const resolved = new URL(candidate, origin);
    if (resolved.origin !== origin) {
      return fallback;
    }
    return `${resolved.pathname}${resolved.search}${resolved.hash}`;
  } catch {
    return fallback;
  }
}

export function readWorkspaceComposerQuery(searchParams: SearchParamsLike): WorkspaceComposerQuery {
  const params = searchParams ?? new URLSearchParams();
  const itemKey = cleanParam(params.get('itemKey') ?? params.get('item_key'));
  const briefId = cleanParam(params.get('briefId') ?? params.get('brief_id'));
  const explicitOriginType = cleanParam(params.get('originType') ?? params.get('origin_type'));
  const explicitOriginId = cleanParam(params.get('originId') ?? params.get('origin_id'));
  const isBriefOrigin = Boolean(itemKey || briefId);
  const defaultReturnUrl = isBriefOrigin ? '/brain#brain-section-briefs' : '/brain';
  return {
    mode: params.get('mode') === 'comment' ? 'comment' : 'post',
    autoplay: params.get('autoplay') === '1',
    itemKey,
    briefId,
    originType: explicitOriginType || (isBriefOrigin ? 'daily_brief_item' : ''),
    originId: explicitOriginId || itemKey || briefId,
    returnUrl: normalizeWorkspaceReturnUrl(params.get('returnUrl') ?? params.get('return_url'), defaultReturnUrl),
    ownerReaction: cleanParam(params.get('ownerReaction') ?? params.get('owner_reaction')),
    title: cleanParam(params.get('title')),
    summary: cleanParam(params.get('summary')),
    hook: cleanParam(params.get('hook')),
    sourceUrl: cleanParam(params.get('sourceUrl') ?? params.get('source_url')),
    sourcePath: cleanParam(params.get('sourcePath') ?? params.get('source_path')),
    priorityLane: cleanParam(params.get('priorityLane') ?? params.get('priority_lane')),
    sourceKind: cleanParam(params.get('sourceKind') ?? params.get('source_kind')),
    routeReason: cleanParam(params.get('routeReason') ?? params.get('route_reason')),
    targetFile: cleanParam(params.get('targetFile') ?? params.get('target_file')),
    section: cleanParam(params.get('section')),
  };
}

export function toWorkspaceQuerySeed(query: WorkspaceComposerQuery): WorkspaceQuerySeed {
  return {
    itemKey: query.itemKey,
    briefId: query.briefId,
    originType: query.originType,
    originId: query.originId,
    returnUrl: query.returnUrl,
    ownerReaction: query.ownerReaction,
    title: query.title,
    summary: query.summary,
    hook: query.hook,
    sourceUrl: query.sourceUrl,
    sourcePath: query.sourcePath,
    priorityLane: query.priorityLane,
    sourceKind: query.sourceKind,
    routeReason: query.routeReason,
    targetFile: query.targetFile,
    section: query.section,
  };
}

export function hasSeededSource(
  query: Pick<WorkspaceComposerQuery, 'itemKey' | 'briefId' | 'originId' | 'title' | 'sourceUrl' | 'sourcePath' | 'summary'>,
) {
  return Boolean(query.itemKey || query.briefId || query.originId || query.title || query.sourceUrl || query.sourcePath || query.summary);
}

export function toWorkspaceSourceCard(query: WorkspaceComposerQuery): WorkspaceSourceCard | null {
  if (!hasSeededSource(query)) {
    return null;
  }

  const entries: Array<[keyof WorkspaceSourceCard, string]> = [
    ['item_key', query.itemKey],
    ['brief_id', query.briefId],
    ['origin_type', query.originType],
    ['origin_id', query.originId],
    ['owner_reaction', query.ownerReaction],
    ['title', query.title],
    ['summary', query.summary],
    ['hook', query.hook],
    ['source_url', query.sourceUrl],
    ['source_path', query.sourcePath],
    ['priority_lane', query.priorityLane],
    ['source_kind', query.sourceKind],
    ['route_reason', query.routeReason],
    ['target_file', query.targetFile],
    ['section', query.section],
  ];
  return Object.fromEntries(entries.filter(([, value]) => value.trim().length > 0)) as WorkspaceSourceCard;
}

export function mapAudienceFromLane(lane: string): PostingAudience {
  const normalized = lane.trim().toLowerCase();
  if (['ai', 'ops-pm', 'tech_ai'].includes(normalized)) return 'tech_ai';
  if (['admissions', 'enrollment-management', 'education'].includes(normalized)) return 'education_admissions';
  if (['program-leadership', 'current-role', 'leadership'].includes(normalized)) return 'leadership';
  if (['entrepreneurship', 'entrepreneurs'].includes(normalized)) return 'entrepreneurs';
  return 'general';
}

export function buildFallbackText(parts: Array<string | null | undefined>) {
  return parts.map((part) => (part ?? '').trim()).filter(Boolean).join('\n\n');
}
