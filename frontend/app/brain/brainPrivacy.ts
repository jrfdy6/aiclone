import { normalizeDisplayText } from '@/lib/display-privacy';

const INTERNAL_UUID_PATTERN = /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi;
const SHELL_COMMAND_PATTERN = /#!\/(?:usr\/bin\/env\s+)?(?:bin\/)?(?:zsh|bash|sh)\b[^\n]*/gi;
const RUNTIME_EXPRESSION_PATTERN = /\$\{[^}\n]{1,160}\}/g;

/**
 * Treat every backend string as untrusted display data. Brain may summarize local
 * files, runner output, or old records; none of those should reveal host paths or
 * credential identifiers in the browser.
 */
export function normalizeBrainDisplayText(value: string) {
  return normalizeDisplayText(value);
}

/**
 * Historical briefs can contain legacy runner excerpts and persistence IDs.
 * Keep those canonical bytes intact while translating their owner-facing view
 * into plain language; System remains the place for raw runtime diagnostics.
 */
export function normalizeBrainOwnerGuidanceText(value: string) {
  return normalizeDisplayText(value)
    .replace(SHELL_COMMAND_PATTERN, '[Internal automation detail is available in Ops System.]')
    .replace(RUNTIME_EXPRESSION_PATTERN, '[runtime value]')
    .replace(INTERNAL_UUID_PATTERN, 'record')
    .replace(/\[(?:local path|local runtime path)\]/gi, '[technical reference hidden]')
    .replace(/`([^`\n]+)`/g, '$1')
    .replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g, (match) => match.replaceAll('_', ' '));
}
