const INTERNAL_REDIRECT_ORIGIN = 'https://ai-clone.invalid';

export function safeInternalRedirect(candidate: string | null | undefined, fallback = '/ops'): string {
  const value = candidate?.trim();
  if (!value || !value.startsWith('/')) return fallback;

  // Reject protocol-relative and backslash-equivalent forms before resolving.
  // Encoded leading separators are rejected too so later decoding cannot turn
  // an internal path into an external navigation target.
  if (/^\/(?:\/|\\|%2f|%5c)/i.test(value)) return fallback;

  try {
    const resolved = new URL(value, INTERNAL_REDIRECT_ORIGIN);
    if (resolved.origin !== INTERNAL_REDIRECT_ORIGIN) return fallback;
    const destination = `${resolved.pathname}${resolved.search}${resolved.hash}`;
    return destination.startsWith('/') && !destination.startsWith('//') ? destination : fallback;
  } catch {
    return fallback;
  }
}
