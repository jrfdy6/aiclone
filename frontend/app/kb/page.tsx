import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Johnnie Fields - Digital Knowledge Base",
  description: "AI-readable knowledge base containing Johnnie's voice patterns, professional background, and research insights. Optimized for Microsoft Copilot and AI assistants.",
  robots: { index: true, follow: true },
  openGraph: {
    title: "Johnnie Fields - Digital Knowledge Base",
    description: "Professional knowledge, voice patterns, and research insights",
    type: "website",
  },
};

// Helper to fetch recent research from Firestore
async function fetchRecentResearch() {
  try {
    const { db } = await import("@/lib/firestore-server");
    const userId = process.env.DEFAULT_USER_ID || "default-user";

    // Fetch recent topic intelligence
    const topicDocs = await db
      .collection("users")
      .doc(userId)
      .collection("topic_intelligence")
      .orderBy("created_at", "desc")
      .limit(5)
      .get();

    const topics = topicDocs.docs.map((doc) => {
      const data = doc.data();
      return {
        slug: generateSlug(data.theme_display || data.theme, data.created_at),
        title: data.theme_display || data.theme,
        date: new Date(data.created_at * 1000).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        }),
        type: "Topic Intelligence",
      };
    });

    // Fetch recent prospect discoveries
    const discoveryDocs = await db
      .collection("users")
      .doc(userId)
      .collection("prospect_discoveries")
      .orderBy("created_at", "desc")
      .limit(5)
      .get();

    const discoveries = discoveryDocs.docs.map((doc) => {
      const data = doc.data();
      return {
        slug: generateSlug(
          `${data.source || "prospects"}-${data.location || "discovery"}`,
          data.created_at
        ),
        title: `${data.source || "Prospect"} Discovery - ${data.location || "Unknown"}`,
        date: new Date(data.created_at * 1000).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        }),
        type: "Prospect Discovery",
      };
    });

    return [...topics, ...discoveries].sort((a, b) => {
      return new Date(b.date).getTime() - new Date(a.date).getTime();
    });
  } catch (error) {
    console.error("Error fetching recent research:", error);
    return [];
  }
}

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

export default async function KbLandingPage() {
  const recentResearch = await fetchRecentResearch();

  // Schema.org structured data
  const schemaData = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: "Johnnie Fields",
    jobTitle: "Director of Admissions",
    worksFor: {
      "@type": "Organization",
      name: "Fusion Academy DC",
    },
    alumniOf: [
      {
        "@type": "CollegeOrUniversity",
        name: "Georgetown University",
      },
      {
        "@type": "CollegeOrUniversity",
        name: "University of Southern California",
      },
      {
        "@type": "CollegeOrUniversity",
        name: "University of Missouri",
      },
    ],
    knowsAbout: [
      "Admissions",
      "Enrollment Management",
      "Neurodivergent Education",
      "Data Science",
      "Leadership",
      "Educational Consulting",
    ],
    url: process.env.NEXT_PUBLIC_SITE_URL
      ? `${process.env.NEXT_PUBLIC_SITE_URL}/kb`
      : undefined,
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaData) }}
      />
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif", lineHeight: 1.6 }}>
        <article>
          <header style={{ marginBottom: "40px" }}>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "16px" }}>
              Johnnie Fields - Digital Knowledge Base
            </h1>
            <p style={{ fontSize: "18px", color: "#666" }}>
              This is a crawl-friendly interface to Johnnie's professional knowledge,
              voice patterns, and research insights. Use natural language queries to
              search, or browse recent research below.
            </p>
          </header>

          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
              Example Queries
            </h2>
            <p style={{ marginBottom: "12px" }}>Try asking about:</p>
            <ul style={{ listStyle: "disc", paddingLeft: "24px", lineHeight: 1.8 }}>
              <li>
                <Link href="/kb/voice-patterns-linkedin" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  Voice patterns and signature phrases
                </Link>
              </li>
              <li>
                <Link href="/kb/career-background-education" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  Career background in education admissions
                </Link>
              </li>
              <li>
                <Link href="/kb/neurodivergent-students-approach" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  Approach to working with neurodivergent students
                </Link>
              </li>
              <li>
                <Link href="/kb/k12-outreach-strategy" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  K-12 outreach and enrollment strategy
                </Link>
              </li>
              <li>
                <Link href="/kb/data-driven-decision-making" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  Data-driven decision making philosophy
                </Link>
              </li>
              <li>
                <Link href="/kb/leadership-philosophy" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  Leadership and management philosophy
                </Link>
              </li>
              <li>
                <Link href="/kb/how-johnnie-talks-to-parents" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  How Johnnie communicates with parents
                </Link>
              </li>
            </ul>
          </section>

          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
              Recent Research
            </h2>
            {recentResearch.length > 0 ? (
              <ul style={{ listStyle: "none", padding: 0 }}>
                {recentResearch.map((item) => (
                  <li key={item.slug} style={{ marginBottom: "12px" }}>
                    <Link
                      href={`/kb/research/${item.slug}`}
                      style={{ color: "#2563eb", textDecoration: "underline", fontSize: "16px" }}
                    >
                      {item.title}
                    </Link>
                    <span style={{ color: "#666", fontSize: "14px", marginLeft: "8px" }}>
                      — {item.date} ({item.type})
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "#666" }}>No research artifacts available yet.</p>
            )}
            <p style={{ marginTop: "16px" }}>
              <Link href="/kb/research" style={{ color: "#2563eb", textDecoration: "underline" }}>
                Browse all research →
              </Link>
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
              About This Knowledge Base
            </h2>
            <p style={{ marginBottom: "12px" }}>
              This knowledge base is optimized for AI assistants like Microsoft Copilot.
              All content is server-rendered, semantically structured, and PII-filtered.
            </p>
            <p>
              <strong>Content includes:</strong> Professional background, voice patterns,
              leadership philosophy, research insights, and contextual communication examples.
            </p>
          </section>
        </article>
      </main>
    </>
  );
}
