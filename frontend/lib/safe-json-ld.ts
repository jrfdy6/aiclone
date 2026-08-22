/** Serialize JSON-LD without allowing Firestore-derived text to close the script tag. */
export function safeJsonLd(value: unknown): string {
  return JSON.stringify(value).replace(/</g, '\\u003c');
}
