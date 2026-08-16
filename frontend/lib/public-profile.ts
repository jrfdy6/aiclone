function boundedPublicValue(value: string | undefined, fallback: string, maxLength = 180) {
  const normalized = String(value || '').replace(/\s+/g, ' ').trim();
  if (!normalized || normalized.length > maxLength || /[\r\n<>]/.test(normalized)) return fallback;
  return normalized;
}

export const publicOwnerDisplayName = boundedPublicValue(
  process.env.NEXT_PUBLIC_AI_CLONE_OWNER_DISPLAY_NAME,
  'the owner',
  120,
);

export const publicOwnerId = boundedPublicValue(
  process.env.NEXT_PUBLIC_AI_CLONE_OWNER_ID,
  'owner',
  64,
).toLowerCase().replace(/[^a-z0-9_-]+/g, '_');

export const publicOwnerRoleLabel = boundedPublicValue(
  process.env.NEXT_PUBLIC_AI_CLONE_OWNER_ROLE_LABEL,
  'Education operations leader and technology builder',
);

export const publicOwnerNorthStar = boundedPublicValue(
  process.env.NEXT_PUBLIC_AI_CLONE_OWNER_NORTH_STAR,
  'I build practical technology and AI systems against real operating problems.',
  320,
);

export function possessivePublicName(value = publicOwnerDisplayName) {
  return /s$/i.test(value) ? `${value}'` : `${value}'s`;
}
