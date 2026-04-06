export type PostingAudience = 'general' | 'education_admissions' | 'tech_ai' | 'leadership' | 'entrepreneurs';
export type ComposerMode = 'post' | 'comment';

export type WorkspaceComposerQuery = {
  mode: ComposerMode;
  autoplay: boolean;
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
  'title' | 'summary' | 'hook' | 'sourceUrl' | 'sourcePath' | 'priorityLane' | 'routeReason'
>;

type SearchParamsLike = {
  get(name: string): string | null;
} | null | undefined;

export function readWorkspaceComposerQuery(searchParams: SearchParamsLike): WorkspaceComposerQuery {
  const params = searchParams ?? new URLSearchParams();
  return {
    mode: params.get('mode') === 'comment' ? 'comment' : 'post',
    autoplay: params.get('autoplay') === '1',
    title: params.get('title') ?? '',
    summary: params.get('summary') ?? '',
    hook: params.get('hook') ?? '',
    sourceUrl: params.get('sourceUrl') ?? '',
    sourcePath: params.get('sourcePath') ?? '',
    priorityLane: params.get('priorityLane') ?? '',
    sourceKind: params.get('sourceKind') ?? '',
    routeReason: params.get('routeReason') ?? '',
    targetFile: params.get('targetFile') ?? '',
    section: params.get('section') ?? '',
  };
}

export function toWorkspaceQuerySeed(query: WorkspaceComposerQuery): WorkspaceQuerySeed {
  return {
    title: query.title,
    summary: query.summary,
    hook: query.hook,
    sourceUrl: query.sourceUrl,
    sourcePath: query.sourcePath,
    priorityLane: query.priorityLane,
    routeReason: query.routeReason,
  };
}

export function hasSeededSource(query: Pick<WorkspaceComposerQuery, 'title' | 'sourceUrl' | 'summary'>) {
  return Boolean(query.title || query.sourceUrl || query.summary);
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
