import type { MetadataRoute } from "next";

function generateSlug(title: string, timestamp: number): string {
  const date = new Date(timestamp * 1000);
  const month = date.toLocaleString("en", { month: "short" }).toLowerCase();
  const year = date.getFullYear();
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `${slug}-${month}-${year}`;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl =
    process.env.NEXT_PUBLIC_SITE_URL ||
    "https://your-frontend.up.railway.app";
  const userId = process.env.DEFAULT_USER_ID || "default-user";

  // Static KB pages
  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: `${baseUrl}/kb`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1.0,
    },
    {
      url: `${baseUrl}/kb/research`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 0.9,
    },
  ];

  // Common knowledge queries (pre-seed for Copilot)
  const commonQueries = [
    "voice-patterns-linkedin",
    "career-background-education",
    "neurodivergent-students-approach",
    "k12-outreach-strategy",
    "data-driven-decision-making",
    "admissions-enrollment-expertise",
    "leadership-philosophy",
    "fusion-academy-director",
    "how-johnnie-talks-to-parents",
    "how-johnnie-handles-objections",
    "coaching-team-members",
    "usc-graduate-school",
    "georgetown-data-science",
    "define-socks-entrepreneurship",
    "easy-outfit-app",
  ];

  const queryRoutes: MetadataRoute.Sitemap = commonQueries.map((query) => ({
    url: `${baseUrl}/kb/${query}`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  // Dynamic research pages from Firestore
  let researchRoutes: MetadataRoute.Sitemap = [];

  try {
    const { db } = await import("@/lib/firestore-server");

    // Topic intelligence
    const topicDocs = await db
      .collection("users")
      .doc(userId)
      .collection("topic_intelligence")
      .orderBy("created_at", "desc")
      .limit(50)
      .get();

    const topicRoutes = topicDocs.docs.map((doc) => {
      const data = doc.data();
      const slug = generateSlug(
        data.theme_display || data.theme,
        data.created_at
      );
      return {
        url: `${baseUrl}/kb/research/${slug}`,
        lastModified: new Date(data.created_at * 1000),
        changeFrequency: "monthly" as const,
        priority: 0.7,
      };
    });

    // Prospect discoveries
    const discoveryDocs = await db
      .collection("users")
      .doc(userId)
      .collection("prospect_discoveries")
      .orderBy("created_at", "desc")
      .limit(50)
      .get();

    const discoveryRoutes = discoveryDocs.docs.map((doc) => {
      const data = doc.data();
      const slug = generateSlug(
        `${data.source || "prospects"}-${data.location || "discovery"}`,
        data.created_at
      );
      return {
        url: `${baseUrl}/kb/research/${slug}`,
        lastModified: new Date(data.created_at * 1000),
        changeFrequency: "monthly" as const,
        priority: 0.6,
      };
    });

    researchRoutes = [...topicRoutes, ...discoveryRoutes];
  } catch (error) {
    console.error("Error generating dynamic sitemap:", error);
    // Fail gracefully - return static routes only
  }

  return [...staticRoutes, ...queryRoutes, ...researchRoutes];
}
