export type WorkspaceStatus = 'live' | 'standing_up' | 'planned';
export type WorkspaceKind = 'executive' | 'workspace';

export type WorkspaceRegistryEntry = {
  key: string;
  kind: WorkspaceKind;
  display_name: string;
  short_label: string;
  brief_heading: string;
  workspace_root: string;
  status: WorkspaceStatus;
  priority_order: number;
  operator_name: string;
  manager_agent: string;
  target_agent: string;
  workspace_agent: string | null;
  execution_mode: 'direct' | 'delegated';
  default_standup_kind: string;
  workspace_sync_participants: string[];
  description: string;
  operating_principles: string[];
  aliases: string[];
  route: string | null;
  accent: string;
  snapshot_mode: 'live' | 'scaffold';
  portfolio_visible: boolean;
};

export type WorkspaceRegistryResponse = {
  generated_at?: string;
  workspaces: WorkspaceRegistryEntry[];
};

export const fallbackWorkspaceRegistry = [
  {
    key: 'shared_ops',
    kind: 'executive',
    display_name: 'Executive',
    short_label: 'Executive',
    brief_heading: 'Executive Interpretation Rule',
    workspace_root: 'shared-ops',
    status: 'live',
    priority_order: 0,
    operator_name: 'Jean-Claude',
    manager_agent: 'Jean-Claude',
    target_agent: 'Jean-Claude',
    workspace_agent: null,
    execution_mode: 'direct',
    default_standup_kind: 'executive_ops',
    workspace_sync_participants: ['Jean-Claude', 'Neo', 'Yoda'],
    description: 'Executive interpretation, operating review, and cross-workspace decision-making for the full portfolio.',
    operating_principles: [
      'Keep the portfolio legible before expanding it',
      'Let cross-workspace signals route through one executive lane',
      'Promote only what should become real work',
    ],
    aliases: ['shared_ops', 'shared-ops', 'shared ops'],
    route: null,
    accent: '#f59e0b',
    snapshot_mode: 'scaffold',
    portfolio_visible: false,
  },
  {
    key: 'feezie-os',
    kind: 'workspace',
    display_name: 'FEEZIE OS',
    short_label: 'FEEZIE',
    brief_heading: 'FEEZIE OS',
    workspace_root: 'linkedin-content-os',
    status: 'live',
    priority_order: 1,
    operator_name: 'FEEZIE Operator',
    manager_agent: 'Jean-Claude',
    target_agent: 'Jean-Claude',
    workspace_agent: null,
    execution_mode: 'direct',
    default_standup_kind: 'workspace_sync',
    workspace_sync_participants: ['Jean-Claude', 'Neo', 'Yoda'],
    description:
      'Public-signal execution system for source intake, reaction loops, content generation, and persona-grounded visibility, currently operating through the LinkedIn lane.',
    operating_principles: [
      'Persona truth first, posting second',
      'Use live source signals before generic ideation',
      'Turn reactions into reusable visibility assets',
    ],
    aliases: ['feezie-os', 'feezie os', 'feezie', 'linkedin-os', 'linkedin-content-os'],
    route: '/workspace',
    accent: '#38bdf8',
    snapshot_mode: 'live',
    portfolio_visible: true,
  },
  {
    key: 'fusion-os',
    kind: 'workspace',
    display_name: 'Fusion OS',
    short_label: 'Fusion',
    brief_heading: 'Fusion OS',
    workspace_root: 'fusion-os',
    status: 'standing_up',
    priority_order: 2,
    operator_name: 'Fusion Systems Operator',
    manager_agent: 'Jean-Claude',
    target_agent: 'Fusion Systems Operator',
    workspace_agent: 'Fusion Systems Operator',
    execution_mode: 'delegated',
    default_standup_kind: 'workspace_sync',
    workspace_sync_participants: ['Jean-Claude', 'Fusion Systems Operator'],
    description: 'Admissions, enrollment, school operations, referral systems, and leadership execution for Fusion-adjacent work.',
    operating_principles: [
      'Protect trust with families and partners',
      'Let frontline signals drive process changes',
      'Make execution clearer before scaling it',
    ],
    aliases: ['fusion-os', 'fusion os', 'fusion'],
    route: null,
    accent: '#22c55e',
    snapshot_mode: 'scaffold',
    portfolio_visible: true,
  },
  {
    key: 'easyoutfitapp',
    kind: 'workspace',
    display_name: 'Easy Outfit App',
    short_label: 'Easy Outfit',
    brief_heading: 'Easy Outfit App',
    workspace_root: 'easyoutfitapp',
    status: 'live',
    priority_order: 3,
    operator_name: 'Easy Outfit App Operator Agent',
    manager_agent: 'Jean-Claude',
    target_agent: 'Easy Outfit App Operator Agent',
    workspace_agent: 'Easy Outfit App Operator Agent',
    execution_mode: 'delegated',
    default_standup_kind: 'workspace_sync',
    workspace_sync_participants: ['Jean-Claude', 'Easy Outfit App Operator Agent'],
    description: 'Context-aware wardrobe decision engine focused on restoring, improving, and growing Easy Outfit App without drifting into generic fashion content.',
    operating_principles: [
      'Reduce decision fatigue with context-aware outfit help',
      'Prioritize owned-wardrobe trust over shopping pressure',
      'Make recommendation quality and reasoning legible',
    ],
    aliases: ['easyoutfitapp', 'easy outfit app', 'easy outfit'],
    route: null,
    accent: '#f472b6',
    snapshot_mode: 'live',
    portfolio_visible: true,
  },
  {
    key: 'ai-swag-store',
    kind: 'workspace',
    display_name: 'AI Swag Store',
    short_label: 'Swag Store',
    brief_heading: 'AI Swag Store',
    workspace_root: 'ai-swag-store',
    status: 'standing_up',
    priority_order: 4,
    operator_name: 'AI Swag Store Operator Agent',
    manager_agent: 'Jean-Claude',
    target_agent: 'AI Swag Store Operator Agent',
    workspace_agent: 'AI Swag Store Operator Agent',
    execution_mode: 'delegated',
    default_standup_kind: 'workspace_sync',
    workspace_sync_participants: ['Jean-Claude', 'AI Swag Store Operator Agent'],
    description: 'Differentiated merch and storefront operating system for AI swag that learns from traffic and demand before scaling the catalog.',
    operating_principles: [
      'Test demand before expanding catalog',
      'Use differentiated creative instead of generic AI merch filler',
      'Optimize for traffic and learning before catalog breadth',
      'Keep fulfillment and operations simple enough to repeat',
    ],
    aliases: ['ai-swag-store', 'ai swag store', 'swag store'],
    route: null,
    accent: '#f59e0b',
    snapshot_mode: 'scaffold',
    portfolio_visible: true,
  },
  {
    key: 'agc',
    kind: 'workspace',
    display_name: 'AGC',
    short_label: 'AGC',
    brief_heading: 'AGC',
    workspace_root: 'agc',
    status: 'standing_up',
    priority_order: 5,
    operator_name: 'AGC Operator Agent',
    manager_agent: 'Jean-Claude',
    target_agent: 'AGC Operator Agent',
    workspace_agent: 'AGC Operator Agent',
    execution_mode: 'delegated',
    default_standup_kind: 'workspace_sync',
    workspace_sync_participants: ['Jean-Claude', 'AGC Operator Agent'],
    description: 'Government-contracting-first operating system for AGC, starting with AI consulting and optimizing for qualified inbound email conversations.',
    operating_principles: [
      'Lead with a government-contracting-first AI consulting posture',
      'Earn credibility without inventing capability claims',
      'Optimize for qualified inbound email from real buyers',
    ],
    aliases: ['agc'],
    route: null,
    accent: '#a78bfa',
    snapshot_mode: 'scaffold',
    portfolio_visible: true,
  },
] as const satisfies readonly WorkspaceRegistryEntry[];

export function normalizeWorkspaceRegistry(entries: readonly WorkspaceRegistryEntry[] | null | undefined): WorkspaceRegistryEntry[] {
  const source = Array.isArray(entries) && entries.length > 0 ? entries : fallbackWorkspaceRegistry;
  return [...source].sort((left, right) => {
    const orderDelta = (left.priority_order ?? 999) - (right.priority_order ?? 999);
    if (orderDelta !== 0) {
      return orderDelta;
    }
    return left.key.localeCompare(right.key);
  });
}

export function portfolioWorkspaceRegistry(entries: readonly WorkspaceRegistryEntry[] | null | undefined): WorkspaceRegistryEntry[] {
  return normalizeWorkspaceRegistry(entries).filter((entry) => entry.kind === 'workspace' && entry.portfolio_visible);
}

export function workspaceRegistryMap(entries: readonly WorkspaceRegistryEntry[] | null | undefined): Record<string, WorkspaceRegistryEntry> {
  return Object.fromEntries(normalizeWorkspaceRegistry(entries).map((entry) => [entry.key, entry]));
}

export function canonicalWorkspaceRegistryKey(
  value: string | null | undefined,
  entries: readonly WorkspaceRegistryEntry[] | null | undefined = fallbackWorkspaceRegistry,
): string | null {
  const raw = String(value ?? '').trim();
  if (!raw) {
    return null;
  }
  const lowered = raw.toLowerCase().trim();
  const variants = new Set([lowered, lowered.replace(/_/g, '-'), lowered.replace(/[-_]/g, ' ')]);
  for (const entry of normalizeWorkspaceRegistry(entries)) {
    if (entry.key === raw) {
      return entry.key;
    }
    if (variants.has(entry.key.toLowerCase())) {
      return entry.key;
    }
    for (const alias of entry.aliases ?? []) {
      const aliasNormalized = alias.toLowerCase().trim();
      if (variants.has(aliasNormalized)) {
        return entry.key;
      }
    }
  }
  return raw;
}

export function workspaceRegistryEntryForKey(
  value: string | null | undefined,
  entries: readonly WorkspaceRegistryEntry[] | null | undefined = fallbackWorkspaceRegistry,
): WorkspaceRegistryEntry | null {
  const canonical = canonicalWorkspaceRegistryKey(value, entries);
  if (!canonical) {
    return null;
  }
  return normalizeWorkspaceRegistry(entries).find((entry) => entry.key === canonical) ?? null;
}

export function workspaceRootSlugForKey(
  value: string | null | undefined,
  entries: readonly WorkspaceRegistryEntry[] | null | undefined = fallbackWorkspaceRegistry,
): string | null {
  return workspaceRegistryEntryForKey(value, entries)?.workspace_root ?? null;
}

export function workspacePathMarkersForKey(
  value: string | null | undefined,
  entries: readonly WorkspaceRegistryEntry[] | null | undefined = fallbackWorkspaceRegistry,
): string[] {
  const entry = workspaceRegistryEntryForKey(value, entries);
  if (!entry) {
    return [];
  }
  const markers = new Set<string>();
  markers.add(entry.key);
  markers.add(entry.workspace_root);
  for (const alias of entry.aliases ?? []) {
    markers.add(alias);
  }
  return Array.from(markers)
    .map((marker) => String(marker || '').trim())
    .filter(Boolean);
}

export function workspaceFileMatchesKey(
  file: { path?: string | null; group?: string | null },
  value: string | null | undefined,
  entries: readonly WorkspaceRegistryEntry[] | null | undefined = fallbackWorkspaceRegistry,
): boolean {
  const markers = workspacePathMarkersForKey(value, entries);
  if (markers.length === 0) {
    return false;
  }
  const normalizedPath = String(file.path ?? '').replace(/\\/g, '/').toLowerCase();
  const normalizedGroup = String(file.group ?? '').replace(/\\/g, '/').toLowerCase();
  return markers.some((marker) => {
    const normalizedMarker = marker.toLowerCase();
    return (
      normalizedPath.includes(`/workspaces/${normalizedMarker}/`) ||
      normalizedPath.includes(`${normalizedMarker}/`) ||
      normalizedGroup === normalizedMarker ||
      normalizedGroup.startsWith(`${normalizedMarker}/`) ||
      normalizedGroup.endsWith(`/${normalizedMarker}`) ||
      normalizedGroup.includes(`/${normalizedMarker}/`)
    );
  });
}

export function workspaceRelativePathForKey(
  path: string,
  value: string | null | undefined,
  entries: readonly WorkspaceRegistryEntry[] | null | undefined = fallbackWorkspaceRegistry,
): string {
  const normalizedPath = String(path ?? '').replace(/\\/g, '/');
  for (const marker of workspacePathMarkersForKey(value, entries)) {
    const normalizedMarker = marker.replace(/\\/g, '/');
    const markerWithSlash = `${normalizedMarker}/`;
    const index = normalizedPath.indexOf(markerWithSlash);
    if (index >= 0) {
      return normalizedPath.slice(index + markerWithSlash.length);
    }
  }
  return normalizedPath;
}

export function workspaceStatusLabel(status: WorkspaceStatus | string): string {
  if (status === 'standing_up') {
    return 'Standing Up';
  }
  if (status === 'live') {
    return 'Live';
  }
  return 'Planned';
}
