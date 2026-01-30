import type { Metadata } from "next";
import Link from "next/link";

type KnowledgeResult = {
  source_id?: string;
  source_file_id?: string;
  chunk_index?: number;
  chunk?: string;
  similarity_score?: number;
  metadata?: Record<string, unknown>;
};

type KnowledgeSearchResponse = {
  success: boolean;
  query: string;
  results: KnowledgeResult[];
};

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001";
}

function normalizeQuery(raw: string): string {
  // Convert URL-friendly slug to natural language
  // "voice-patterns-linkedin" → "voice patterns linkedin"
  return decodeURIComponent(raw).replace(/-/g, " ").trim();
}

async function fetchKnowledge(searchQuery: string): Promise<KnowledgeSearchResponse> {
  const apiUrl = getApiUrl();

  const res = await fetch(`${apiUrl}/api/knowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: process.env.DEFAULT_USER_ID || "default-user",
      search_query: searchQuery,
      top_k: 8,
    }),
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Backend failed: ${res.status} ${text}`);
  }

  return res.json();
}

export async function generateMetadata(
  { params }: { params: { query: string } }
): Promise<Metadata> {
  const q = normalizeQuery(params.query || "");

  return {
    title: q ? `${q} - Johnnie Fields KB` : "Johnnie Fields KB",
    description: q
      ? `Knowledge about: ${q}`
      : "Johnnie Fields digital knowledge base",
    robots: { index: true, follow: true },
    openGraph: {
      title: q ? `${q} - Johnnie Fields` : "Johnnie Fields",
      description: `Professional knowledge and insights about ${q}`,
      type: "article",
    },
  };
}

export default async function KbQueryPage(
  { params }: { params: { query: string } }
) {
  const q = normalizeQuery(params.query || "");

  if (!q) {
    return (
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif" }}>
        <article>
          <header>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "16px" }}>
              Knowledge Base Search
            </h1>
            <p style={{ color: "#666" }}>
              No query provided. Try <Link href="/kb" style={{ color: "#2563eb", textDecoration: "underline" }}>returning to the index</Link>.
            </p>
          </header>
        </article>
      </main>
    );
  }

  try {
    const data = await fetchKnowledge(q);

    // Schema.org structured data for ProfilePage
    const schemaData = {
      "@context": "https://schema.org",
      "@type": "ProfilePage",
      mainEntity: {
        "@type": "Person",
        name: "Johnnie Fields",
      },
      about: q,
      datePublished: new Date().toISOString(),
    };

    return (
      <>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaData) }}
        />
        <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif", lineHeight: 1.6 }}>
          <article>
            <header style={{ marginBottom: "32px" }}>
              <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "12px" }}>
                {data.query}
              </h1>
              <p style={{ color: "#666", fontSize: "16px" }}>
                Search results from Johnnie's knowledge base. This content is
                server-rendered for AI crawlers.
              </p>
            </header>

            {data.results?.length ? (
              data.results.map((item, idx) => {
                const source =
                  (item.metadata?.file_name as string) ||
                  (item.metadata?.source as string) ||
                  "Knowledge chunk";

                const chunk = item.chunk || "";
                const paragraphs = chunk
                  .split(/\n{2,}/g)
                  .map((p) => p.trim())
                  .filter(Boolean);

                return (
                  <section key={`${source}-${idx}`} style={{ marginBottom: "32px" }}>
                    <h2 style={{ fontSize: "20px", fontWeight: "600", marginBottom: "8px" }}>
                      {source}
                    </h2>
                    <p style={{ fontSize: "14px", color: "#666", marginBottom: "12px" }}>
                      <small>
                        Relevance:{" "}
                        {typeof item.similarity_score === "number"
                          ? (item.similarity_score * 100).toFixed(1) + "%"
                          : "n/a"}
                      </small>
                    </p>

                    {paragraphs.length > 1 ? (
                      paragraphs.map((p, pIdx) => (
                        <p key={pIdx} style={{ marginBottom: "12px", color: "#333" }}>
                          {p}
                        </p>
                      ))
                    ) : (
                      <p style={{ whiteSpace: "pre-wrap", marginBottom: "12px", color: "#333" }}>
                        {chunk}
                      </p>
                    )}

                    {idx < data.results.length - 1 && (
                      <hr style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "24px 0" }} />
                    )}
                  </section>
                );
              })
            ) : (
              <section>
                <h2 style={{ fontSize: "20px", fontWeight: "600", marginBottom: "12px" }}>
                  No results
                </h2>
                <p style={{ color: "#666" }}>
                  No knowledge chunks matched this query. Try a different search term.
                </p>
              </section>
            )}

            <footer style={{ marginTop: "40px", paddingTop: "24px", borderTop: "1px solid #e5e7eb" }}>
              <p>
                <Link href="/kb" style={{ color: "#2563eb", textDecoration: "underline" }}>
                  ← Back to knowledge base index
                </Link>
              </p>
            </footer>
          </article>
        </main>
      </>
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";

    return (
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif" }}>
        <article>
          <header style={{ marginBottom: "24px" }}>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "12px" }}>
              {q}
            </h1>
            <p style={{ color: "#dc2626" }}>Failed to load knowledge.</p>
          </header>
          <section>
            <h2 style={{ fontSize: "20px", fontWeight: "600", marginBottom: "12px" }}>
              Error
            </h2>
            <p style={{ whiteSpace: "pre-wrap", color: "#666", fontFamily: "monospace", fontSize: "14px" }}>
              {message}
            </p>
          </section>
          <footer style={{ marginTop: "24px" }}>
            <p>
              <Link href="/kb" style={{ color: "#2563eb", textDecoration: "underline" }}>
                ← Back to knowledge base index
              </Link>
            </p>
          </footer>
        </article>
      </main>
    );
  }
}
