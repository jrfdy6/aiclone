import type { MetadataRoute } from "next";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl =
    process.env.NEXT_PUBLIC_SITE_URL ||
    "https://aiclone-frontend-production.up.railway.app";

  // Static KB pages
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: `${baseUrl}/kb`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1.0,
    },
  ];

  // Common knowledge queries (pre-seed for Copilot)
  const commonQueries = [
    "voice-patterns-linkedin",
    "career-background",
    "technology-implementation",
    "data-driven-decision-making",
    "leadership-philosophy",
    "how-owner-communicates-with-clients",
    "how-owner-handles-objections",
    "coaching-team-members",
    "entrepreneurship-lessons",
    "product-building",
  ];

  const queryRoutes: MetadataRoute.Sitemap = commonQueries.map((query) => ({
    url: `${baseUrl}/kb/${query}`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  // Authenticated research pages are intentionally excluded. The public
  // sitemap stays static and cannot expose private Firestore-derived records.
  return [...staticRoutes, ...queryRoutes];
}
