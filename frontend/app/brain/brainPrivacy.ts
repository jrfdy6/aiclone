const SAFE_PATH_ANCHORS = ['workspaces/', 'knowledge/', 'docs/', 'memory/', 'SOPs/'] as const;

const CREDENTIAL_NAME_PATTERN = /\b[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)\b(?:\s*=\s*[^\s,;]+)?/g;
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

/**
 * Treat every backend string as untrusted display data. Brain may summarize local
 * files, runner output, or old records; none of those should reveal host paths or
 * credential identifiers in the browser.
 */
export function normalizeBrainDisplayText(value: string) {
  return value
    .replace(CREDENTIAL_NAME_PATTERN, '[credential]')
    .replace(LOCAL_ABSOLUTE_PATH_PATTERN, (match) => safeRelativePath(match))
    .replace(LOCAL_HIDDEN_PATH_PATTERN, (_match, prefix: string) => `${prefix}[local runtime path]`);
}
