import Link from "next/link";
import type { Metadata } from "next";

import { fetchResearchLibrary } from "@/lib/research-backend";
import { safeJsonLd } from "@/lib/safe-json-ld";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Research Library - the owner",
  description: "Review topic intelligence and prospect discovery research in the authenticated owner workspace.",
  robots: { index: false, follow: false },
  openGraph: {
    title: "Research Library - the owner",
    description: "Topic intelligence and prospect discovery research",
    type: "website",
  },
};

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + "...";
}

export default async function ResearchIndexPage() {
  const library = await fetchResearchLibrary();
  const topics = library.topics.map((item) => ({ ...item, summary: truncate(item.summary, 150) }));
  return renderPage(topics, library.discoveries, library.state, library.reasonCodes);
}

function renderPage(topics: any[], discoveries: any[], firestoreState: "ready" | "degraded", reasonCodes: string[]) {
  // Schema.org structured data for CollectionPage
  const schemaData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Research Library",
    description: "Topic intelligence and prospect discovery research by the owner",
    author: {
      "@type": "Person",
      name: "the owner",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(schemaData) }}
      />
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif", lineHeight: 1.6 }}>
        <article>
          <header style={{ marginBottom: "40px" }}>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "16px" }}>
              Research Library
            </h1>
            <p style={{ fontSize: "18px", color: "#666" }}>
              Review topic intelligence and prospect discovery research through the authenticated backend control plane.
            </p>
          </header>

          {firestoreState === "degraded" && (
            <aside
              role="status"
              style={{ marginBottom: "32px", padding: "16px", border: "1px solid #f59e0b", background: "#fffbeb", color: "#92400e" }}
            >
              Live research data is temporarily unavailable. The knowledge base remains available, but this page is not claiming that the research library is empty.
              {reasonCodes.length > 0 && <small style={{ display: "block", marginTop: "6px" }}>Reason codes: {reasonCodes.join(", ")}</small>}
            </aside>
          )}

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
              <p style={{ color: "#666" }}>{firestoreState === "degraded" ? "No verified topic-intelligence rows loaded." : "No topic intelligence research available."}</p>
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
              <p style={{ color: "#666" }}>{firestoreState === "degraded" ? "No verified prospect-discovery rows loaded." : "No prospect discoveries available."}</p>
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
