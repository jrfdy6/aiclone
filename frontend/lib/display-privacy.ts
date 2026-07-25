const SAFE_PATH_ANCHORS = ['workspaces/', 'knowledge/', 'docs/', 'memory/', 'SOPs/'] as const;

const CREDENTIAL_NAME_PATTERN = /\b[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)\b(?:\s*=\s*[^\s,;]+)?/g;
const SENSITIVE_FILE_PATTERN = /\b(?:control_plane\.env|credentials?\.json|secrets?\.json)\b/gi;
const LOCAL_ABSOLUTE_PATH_PATTERN = /(?<![A-Za-z0-9:])(?:\/(?:Users|home)\/[^/\s]+(?:\/[^\s]*)?|\/(?:private\/(?:tmp|var)|var\/folders|opt\/homebrew)(?:\/[^\s]*)?|\/app(?:\/[^\s]*)?)/gi;
const LOCAL_HIDDEN_PATH_PATTERN = /(^|[\s([{"'])\.[a-z][a-z0-9_-]*(?:\/[^\s]*)*/gi;
const TRAILING_PATH_PUNCTUATION = /[\])}>.,;:'"`]+$/;

function safeRelativePath(value: string) {
  const trailing = value.match(TRAILING_PATH_PUNCTUATION)?.[0] ?? '';
  const path = trailing ? value.slice(0, -trailing.length) : value;
  const anchor = SAFE_PATH_ANCHORS
    .map((candidate) => ({ candidate, index: path.indexOf(candidate) }))
    .filter((entry) => entry.index >= 0)
    .sort((left, right) => left.index - right.index)[0];
  return `${anchor ? path.slice(anchor.index) : '[local path]'}${trailing}`;
}

function decodeCommonHtmlEntities(value: string) {
  return value
    .replace(/&nbsp;/gi, ' ')
    .replace(/&gt;/gi, '>')
    .replace(/&lt;/gi, '<')
    .replace(/&quot;/gi, '"')
    .replace(/&#0*39;|&apos;/gi, "'")
    .replace(/&amp;/gi, '&');
}

/**
 * Treat backend strings as untrusted display data. The runtime summarizes local
 * files, runner output, email, and old records; none of those should reveal host
 * paths or credential identifiers in a browser or screen recording.
 */
export function normalizeDisplayText(value: string) {
  return decodeCommonHtmlEntities(
    value
      .replace(CREDENTIAL_NAME_PATTERN, '[credential]')
      .replace(SENSITIVE_FILE_PATTERN, '[credential file]')
      .replace(LOCAL_ABSOLUTE_PATH_PATTERN, (match) => safeRelativePath(match))
      .replace(LOCAL_HIDDEN_PATH_PATTERN, (_match, prefix: string) => `${prefix}[local runtime path]`),
  );
}
