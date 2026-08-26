export type PersonaReviewDeltaLike = {
  id: string;
  created_at?: string | null;
  metadata?: Record<string, unknown>;
};

export type PersonaReviewSourceGroup<T extends PersonaReviewDeltaLike> = {
  key: string;
  deltas: T[];
};

export type PersonaReviewPosition<T extends PersonaReviewDeltaLike> = {
  sourceIndex: number;
  claimIndex: number;
  source: PersonaReviewSourceGroup<T>;
};

export type PersonaReviewResponseKind = 'agree' | 'disagree' | 'nuance' | 'story' | 'language';

export function personaResponsePlaceholder(kind: PersonaReviewResponseKind): string {
  if (kind === 'agree') return 'What do you agree with, and why? Type or dictate your own words…';
  if (kind === 'disagree') return 'What do you disagree with, and why? Type or dictate your own words…';
  if (kind === 'story') return 'Share a real personal story or example in your own words…';
  if (kind === 'language') return 'What wording sounds more like you? Type or dictate it here…';
  return 'What nuance or qualification should be preserved? Type or dictate your own words…';
}

function metadataText(metadata: Record<string, unknown> | undefined, key: string): string | null {
  const value = metadata?.[key];
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text || null;
}

function segmentIndex(delta: PersonaReviewDeltaLike): number {
  const raw = delta.metadata?.segment_index;
  const parsed = typeof raw === 'number' ? raw : Number.parseInt(String(raw ?? ''), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : Number.MAX_SAFE_INTEGER;
}

function sourceKey(delta: PersonaReviewDeltaLike): string {
  const reviewSource = metadataText(delta.metadata, 'review_source');
  if (reviewSource !== 'long_form_media.segment') return `delta:${delta.id}`;
  return (
    metadataText(delta.metadata, 'source_asset_id') ??
    metadataText(delta.metadata, 'source_url') ??
    metadataText(delta.metadata, 'source_path') ??
    `delta:${delta.id}`
  );
}

export function groupPersonaReviewDeltas<T extends PersonaReviewDeltaLike>(deltas: T[]): PersonaReviewSourceGroup<T>[] {
  const groups = new Map<string, PersonaReviewSourceGroup<T>>();
  const ordered: PersonaReviewSourceGroup<T>[] = [];

  for (const delta of deltas) {
    const key = sourceKey(delta);
    let group = groups.get(key);
    if (!group) {
      group = { key, deltas: [] };
      groups.set(key, group);
      ordered.push(group);
    }
    group.deltas.push(delta);
  }

  for (const group of ordered) {
    group.deltas.sort((left, right) => {
      const indexDifference = segmentIndex(left) - segmentIndex(right);
      if (indexDifference !== 0) return indexDifference;
      const leftCreated = Date.parse(left.created_at ?? '');
      const rightCreated = Date.parse(right.created_at ?? '');
      return (Number.isFinite(leftCreated) ? leftCreated : 0) - (Number.isFinite(rightCreated) ? rightCreated : 0);
    });
  }

  return ordered;
}

export function findPersonaReviewPosition<T extends PersonaReviewDeltaLike>(
  groups: PersonaReviewSourceGroup<T>[],
  deltaId: string | null | undefined,
): PersonaReviewPosition<T> | null {
  if (!deltaId) return null;
  for (let sourceIndex = 0; sourceIndex < groups.length; sourceIndex += 1) {
    const source = groups[sourceIndex];
    const claimIndex = source.deltas.findIndex((delta) => delta.id === deltaId);
    if (claimIndex >= 0) return { sourceIndex, claimIndex, source };
  }
  return null;
}

export function resolvePersonaReviewSelection<T extends PersonaReviewDeltaLike>(
  deltas: T[],
  selectedDeltaId: string | null | undefined,
  pendingAdvanceDeltaId?: string | null,
): T | null {
  // A successful save removes the current claim from the active queue before
  // the no-store refresh finishes. The explicit transition target outranks
  // any transient fallback selection until that target is confirmed.
  if (pendingAdvanceDeltaId !== undefined) {
    return pendingAdvanceDeltaId
      ? deltas.find((delta) => delta.id === pendingAdvanceDeltaId) ?? null
      : null;
  }

  const selected = deltas.find((delta) => delta.id === selectedDeltaId);
  if (selected) return selected;
  return deltas[0] ?? null;
}

export function personaReviewAdvanceIsSettled<T extends PersonaReviewDeltaLike>(
  deltas: T[],
  selectedDeltaId: string | null | undefined,
  pendingAdvanceDeltaId?: string | null,
): boolean {
  if (pendingAdvanceDeltaId === undefined) return true;
  if (pendingAdvanceDeltaId === null) return !selectedDeltaId;
  return selectedDeltaId === pendingAdvanceDeltaId && deltas.some((delta) => delta.id === pendingAdvanceDeltaId);
}

export function adjacentPersonaReviewDeltaId<T extends PersonaReviewDeltaLike>(
  groups: PersonaReviewSourceGroup<T>[],
  deltaId: string | null | undefined,
  direction: 'previous' | 'next',
): string | null {
  const position = findPersonaReviewPosition(groups, deltaId);
  if (!position) return groups[0]?.deltas[0]?.id ?? null;

  if (direction === 'previous') {
    if (position.claimIndex > 0) return position.source.deltas[position.claimIndex - 1]?.id ?? null;
    const previousSource = groups[position.sourceIndex - 1];
    return previousSource?.deltas[previousSource.deltas.length - 1]?.id ?? null;
  }

  if (position.claimIndex < position.source.deltas.length - 1) {
    return position.source.deltas[position.claimIndex + 1]?.id ?? null;
  }
  return groups[position.sourceIndex + 1]?.deltas[0]?.id ?? null;
}

export function nextPersonaReviewSourceDeltaId<T extends PersonaReviewDeltaLike>(
  groups: PersonaReviewSourceGroup<T>[],
  deltaId: string | null | undefined,
): string | null {
  const position = findPersonaReviewPosition(groups, deltaId);
  if (!position) return groups[0]?.deltas[0]?.id ?? null;
  return groups[position.sourceIndex + 1]?.deltas[0]?.id ?? null;
}

export function youtubeVideoId(sourceUrl: string | null | undefined): string | null {
  if (!sourceUrl) return null;
  try {
    const parsed = new URL(sourceUrl);
    const hostname = parsed.hostname.toLowerCase().replace(/^www\./, '');
    if (hostname === 'youtu.be') return parsed.pathname.split('/').filter(Boolean)[0] ?? null;
    if (hostname === 'youtube.com' || hostname.endsWith('.youtube.com')) {
      if (parsed.pathname === '/watch') return parsed.searchParams.get('v');
      const parts = parsed.pathname.split('/').filter(Boolean);
      if (parts[0] === 'shorts' || parts[0] === 'embed' || parts[0] === 'live') return parts[1] ?? null;
    }
  } catch {
    return null;
  }
  return null;
}

export function youtubeThumbnailUrl(sourceUrl: string | null | undefined): string | null {
  const videoId = youtubeVideoId(sourceUrl);
  return videoId ? `https://i.ytimg.com/vi/${encodeURIComponent(videoId)}/hqdefault.jpg` : null;
}
