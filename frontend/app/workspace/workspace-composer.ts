export type PostingAudience = 'general' | 'education_admissions' | 'tech_ai' | 'leadership' | 'entrepreneurs';
export type ContentCategory = 'value' | 'invitation' | 'personal';
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
  publishPosture: string;
  canonicalPillar: string;
  careerSignal: string;
  employerProximity: string;
  employerSafety: string;
  proofPosture: string;
  concreteAction: string;
  exactProblem: string;
  observableLesson: string;
  qualificationRoute: string;
  ownerQuestion: string;
  proofPrompt: string;
  audience: string;
  audienceConsequence: string;
  distinctThesis: string;
  whyNow: string;
  developmentStatus: string;
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
  | 'publishPosture'
  | 'canonicalPillar'
  | 'careerSignal'
  | 'employerProximity'
  | 'employerSafety'
  | 'proofPosture'
  | 'concreteAction'
  | 'exactProblem'
  | 'observableLesson'
  | 'qualificationRoute'
  | 'ownerQuestion'
  | 'proofPrompt'
  | 'audience'
  | 'audienceConsequence'
  | 'distinctThesis'
  | 'whyNow'
  | 'developmentStatus'
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
  publish_posture?: string;
  canonical_pillar?: string;
  career_signal?: string;
  employer_proximity?: string;
  employer_safety?: string;
  proof_posture?: string;
  concrete_action?: string;
  exact_problem?: string;
  observable_lesson?: string;
  qualification_route?: string;
  owner_question?: string;
  proof_prompt?: string;
  audience?: string;
  audience_consequence?: string;
  distinct_thesis?: string;
  why_now?: string;
  development_status?: string;
  source_published_at?: string;
  source_observed_at?: string;
  freshness_state?: string;
  source_temporality?: string;
  provenance?: Record<string, unknown>;
  target_file?: string;
  section?: string;
};

type SearchParamsLike = {
  get(name: string): string | null;
} | null | undefined;

function cleanParam(value: string | null) {
  return value?.trim() ?? '';
}

export function normalizeContentCategory(value: unknown): ContentCategory | null {
  const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
  if (normalized === 'sales') return 'invitation';
  if (normalized === 'value' || normalized === 'invitation' || normalized === 'personal') return normalized;
  return null;
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
    publishPosture: cleanParam(params.get('publishPosture') ?? params.get('publish_posture')),
    canonicalPillar: cleanParam(params.get('canonicalPillar') ?? params.get('canonical_pillar')),
    careerSignal: cleanParam(params.get('careerSignal') ?? params.get('career_signal')),
    employerProximity: cleanParam(params.get('employerProximity') ?? params.get('employer_proximity')),
    employerSafety: cleanParam(params.get('employerSafety') ?? params.get('employer_safety')),
    proofPosture: cleanParam(params.get('proofPosture') ?? params.get('proof_posture')),
    concreteAction: cleanParam(params.get('concreteAction') ?? params.get('concrete_action')),
    exactProblem: cleanParam(params.get('exactProblem') ?? params.get('exact_problem')),
    observableLesson: cleanParam(params.get('observableLesson') ?? params.get('observable_lesson')),
    qualificationRoute: cleanParam(params.get('qualificationRoute') ?? params.get('qualification_route')),
    ownerQuestion: cleanParam(params.get('ownerQuestion') ?? params.get('owner_question')),
    proofPrompt: cleanParam(params.get('proofPrompt') ?? params.get('proof_prompt')),
    audience: cleanParam(params.get('audience')),
    audienceConsequence: cleanParam(params.get('audienceConsequence') ?? params.get('audience_consequence')),
    distinctThesis: cleanParam(params.get('distinctThesis') ?? params.get('distinct_thesis')),
    whyNow: cleanParam(params.get('whyNow') ?? params.get('why_now')),
    developmentStatus: cleanParam(params.get('developmentStatus') ?? params.get('development_status')),
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
    publishPosture: query.publishPosture,
    canonicalPillar: query.canonicalPillar,
    careerSignal: query.careerSignal,
    employerProximity: query.employerProximity,
    employerSafety: query.employerSafety,
    proofPosture: query.proofPosture,
    concreteAction: query.concreteAction,
    exactProblem: query.exactProblem,
    observableLesson: query.observableLesson,
    qualificationRoute: query.qualificationRoute,
    ownerQuestion: query.ownerQuestion,
    proofPrompt: query.proofPrompt,
    audience: query.audience,
    audienceConsequence: query.audienceConsequence,
    distinctThesis: query.distinctThesis,
    whyNow: query.whyNow,
    developmentStatus: query.developmentStatus,
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
    ['publish_posture', query.publishPosture],
    ['canonical_pillar', query.canonicalPillar],
    ['career_signal', query.careerSignal],
    ['employer_proximity', query.employerProximity],
    ['employer_safety', query.employerSafety],
    ['proof_posture', query.proofPosture],
    ['concrete_action', query.concreteAction],
    ['exact_problem', query.exactProblem],
    ['observable_lesson', query.observableLesson],
    ['qualification_route', query.qualificationRoute],
    ['owner_question', query.ownerQuestion],
    ['proof_prompt', query.proofPrompt],
    ['audience', query.audience],
    ['audience_consequence', query.audienceConsequence],
    ['distinct_thesis', query.distinctThesis],
    ['why_now', query.whyNow],
    ['development_status', query.developmentStatus],
    ['target_file', query.targetFile],
    ['section', query.section],
  ];
  return Object.fromEntries(entries.filter(([, value]) => value.trim().length > 0)) as WorkspaceSourceCard;
}

export function mapAudienceFromLane(lane: string): PostingAudience {
  const normalized = lane.trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (['education_leaders', 'education_admissions', 'admissions', 'enrollment_management', 'education'].includes(normalized)) {
    return 'education_admissions';
  }
  if (['ai_systems_operators', 'ai', 'ops_pm', 'tech_ai'].includes(normalized)) return 'tech_ai';
  if (['program_leadership', 'current_role', 'leadership'].includes(normalized)) return 'leadership';
  if (['entrepreneurship', 'entrepreneurs'].includes(normalized)) return 'entrepreneurs';
  if (/\b(admissions?|enrollment|education|outreach)\b/.test(normalized.replace(/_/g, ' '))) return 'education_admissions';
  if (/\b(ai|artificial intelligence|tech|technology)\b/.test(normalized.replace(/_/g, ' '))) return 'tech_ai';
  return 'general';
}

export function buildFallbackText(parts: Array<string | null | undefined>) {
  return parts.map((part) => (part ?? '').trim()).filter(Boolean).join('\n\n');
}
