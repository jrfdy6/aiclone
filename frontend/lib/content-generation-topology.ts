export const LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_KEY = 'content_topology';
export const LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_VALUE = 'legacy_two_option_compatibility';

type SearchParamsReader = {
  get(name: string): string | null;
};

/**
 * The approved owner-facing topology is the integrated canonical lifecycle.
 * The former two-option comparator remains reachable only through this exact,
 * deliberate rollback switch so ordinary workspace navigation cannot create a
 * second writable content lane.
 */
export function legacyTwoOptionCompatibilityRequested(
  searchParams: SearchParamsReader | null | undefined,
): boolean {
  return searchParams?.get(LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_KEY)
    === LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_VALUE;
}
