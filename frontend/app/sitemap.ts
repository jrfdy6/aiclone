import type { MetadataRoute } from 'next';

/**
 * The public sitemap stays static and empty because owner control surfaces are
 * authenticated. Public invite access is user-created and is not discoverable.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  return [];
}
