import { normalizeDisplayText } from '@/lib/display-privacy';

/**
 * Treat every backend string as untrusted display data. Brain may summarize local
 * files, runner output, or old records; none of those should reveal host paths or
 * credential identifiers in the browser.
 */
export function normalizeBrainDisplayText(value: string) {
  return normalizeDisplayText(value);
}
