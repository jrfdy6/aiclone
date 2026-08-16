export const BRAIN_TABS = ['dashboard', 'briefs', 'persona', 'automations', 'docs'] as const;

export type BrainTab = (typeof BRAIN_TABS)[number];
export type BrainLifecycleView = 'pending_promotion' | 'workspace_saved' | 'committed' | 'resolved';

export type BrainLocationState = {
  tab: BrainTab;
  deltaId: string | null;
};

const BRAIN_SECTION_PREFIX = 'brain-section-';

export function parseBrainLocation(search: string, hash: string): BrainLocationState {
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const rawDeltaId = params.get('delta_id')?.trim() ?? '';
  const deltaId = rawDeltaId || null;
  const hashValue = hash.startsWith('#') ? hash.slice(1) : hash;
  const hashTab = hashValue.startsWith(BRAIN_SECTION_PREFIX)
    ? hashValue.slice(BRAIN_SECTION_PREFIX.length)
    : '';

  return {
    tab: isBrainTab(hashTab) ? hashTab : deltaId ? 'persona' : 'dashboard',
    deltaId,
  };
}

export function buildBrainSectionHref(tab: BrainTab, search = ''): string {
  const normalizedSearch = search.trim().replace(/^\?/, '');
  return `/brain${normalizedSearch ? `?${normalizedSearch}` : ''}#${BRAIN_SECTION_PREFIX}${tab}`;
}

export function lifecycleViewForDeltaStage(stage: string | null | undefined): BrainLifecycleView | null {
  if (stage === 'pending_promotion') return 'pending_promotion';
  if (stage === 'workspace_saved') return 'workspace_saved';
  if (stage === 'committed') return 'committed';
  if (stage === 'resolved' || stage === 'approved_unpromoted' || stage === 'reviewed') return 'resolved';
  return null;
}

export function personaDeltaElementId(deltaId: string): string {
  return `brain-persona-delta-${encodeURIComponent(deltaId)}`;
}

function isBrainTab(value: string): value is BrainTab {
  return (BRAIN_TABS as readonly string[]).includes(value);
}
