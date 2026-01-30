import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Research Library - Johnnie Fields",
  description: "Browse topic intelligence and prospect discovery research. All content is PII-filtered for public crawling.",
  robots: { index: true, follow: true },
  openGraph: {
    title: "Research Library - Johnnie Fields",
    description: "Topic intelligence and prospect discovery research",
    type: "website",
  },
};

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

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + "...";
}

export default async function ResearchIndexPage() {
  const userId = process.env.DEFAULT_USER_ID || "default-user";

  let topics: any[] = [];
  let discoveries: any[] = [];

  try {
    const { db } = await import("@/lib/firestore-server");

    // Fetch topic intelligence
    const topicDocs = await db
      .collection("users")
      .doc(userId)
      .collection("topic_intelligence")
      .orderBy("created_at", "desc")
      .limit(20)
      .get();

    topics = topicDocs.docs.map((doc) => {
      const data = doc.data();
      return {
        id: doc.id,
        slug: generateSlug(data.theme_display || data.theme, data.created_at),
        title: data.theme_display || data.theme,
        date: new Date(data.created_at * 1000).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        }),
        summary: truncate(data.summary || "", 150),
      };
    });

    // Fetch prospect discoveries
    const discoveryDocs = await db
      .collection("users")
      .doc(userId)
      .collection("prospect_discoveries")
      .orderBy("created_at", "desc")
      .limit(20)
      .get();

    discoveries = discoveryDocs.docs.map((doc) => {
      const data = doc.data();
      return {
        id: doc.id,
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
        count: data.prospects?.length || 0,
      };
    });
  } catch (error) {
    console.error("Error fetching research:", error);
  }

  // Schema.org structured data for CollectionPage
  const schemaData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Research Library",
    description: "Topic intelligence and prospect discovery research by Johnnie Fields",
    author: {
      "@type": "Person",
      name: "Johnnie Fields",
    },
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
              Research Library
            </h1>
            <p style={{ fontSize: "18px", color: "#666" }}>
              Browse topic intelligence and prospect discovery research. All
              content is PII-filtered for public crawling.
            </p>
          </header>

          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
              Topic Intelligence
            </h2>
            {topics.length > 0 ? (
              <ul style={{ listStyle: "none", padding: 0 }}>
                {topics.map((item) => (
                  <li key={item.id} style={{ marginBottom: "20px" }}>
                    <Link
                      href={`/kb/research/${item.slug}`}
                      style={{ color: "#2563eb", textDecoration: "underline", fontSize: "18px", fontWeight: "500" }}
                    >
                      {item.title}
                    </Link>
                    <p style={{ margin: "4px 0 0 0", color: "#666", fontSize: "14px" }}>
                      <small>{item.date}</small>
                      {item.summary && (
                        <>
                          {" — "}
                          {item.summary}
                        </>
                      )}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "#666" }}>No topic intelligence research available.</p>
            )}
          </section>

          <section style={{ marginBottom: "40px" }}>
            <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
              Prospect Discoveries
            </h2>
            {discoveries.length > 0 ? (
              <ul style={{ listStyle: "none", padding: 0 }}>
                {discoveries.map((item) => (
                  <li key={item.id} style={{ marginBottom: "20px" }}>
                    <Link
                      href={`/kb/research/${item.slug}`}
                      style={{ color: "#2563eb", textDecoration: "underline", fontSize: "18px", fontWeight: "500" }}
                    >
                      {item.title}
                    </Link>
                    <p style={{ margin: "4px 0 0 0", color: "#666", fontSize: "14px" }}>
                      <small>{item.date}</small> — {item.count} prospects found
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "#666" }}>No prospect discoveries available.</p>
            )}
          </section>

          <footer style={{ marginTop: "40px", paddingTop: "24px", borderTop: "1px solid #e5e7eb" }}>
            <p>
              <Link href="/kb" style={{ color: "#2563eb", textDecoration: "underline" }}>
                ← Back to knowledge base
              </Link>
            </p>
          </footer>
        </article>
      </main>
    </>
  );
}
