const CANONICAL_DECISION_STATUSES = new Set([
  'open',
  'in_session',
  'blocked',
  'resolved',
  'canceled',
  'superseded',
]);

export type OpsCanonicalDecisionDisplay = {
  title: string;
  status: string | null;
  stateVersion: number | null;
  resolvedChoice: string | null;
};

function boundedText(value: unknown, limit: number) {
  if (typeof value !== 'string') return null;
  const normalized = value.replace(/\s+/g, ' ').trim();
  return normalized ? normalized.slice(0, limit) : null;
}

export function opsCanonicalDecisionDisplay(
  item: Record<string, unknown>,
): OpsCanonicalDecisionDisplay {
  const status = typeof item.status === 'string' && CANONICAL_DECISION_STATUSES.has(item.status)
    ? item.status
    : null;
  const stateVersion = typeof item.state_version === 'number'
    && Number.isSafeInteger(item.state_version)
    && item.state_version >= 1
    ? item.state_version
    : null;
  const resolution = item.resolution && typeof item.resolution === 'object' && !Array.isArray(item.resolution)
    ? item.resolution as Record<string, unknown>
    : {};
  return {
    title: boundedText(item.title, 200) ?? 'Recorded decision',
    status,
    stateVersion,
    resolvedChoice: status === 'resolved' ? boundedText(resolution.choice, 300) : null,
  };
}
