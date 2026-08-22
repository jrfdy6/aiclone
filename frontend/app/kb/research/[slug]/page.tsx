import type { Metadata } from "next";
import Link from "next/link";

import { fetchResearchBySlug } from "@/lib/research-backend";
import { safeJsonLd } from "@/lib/safe-json-ld";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params;
  const result = await fetchResearchBySlug(slug);
  const research = result.research;

  return {
    title: research ? `${research.title} - Research` : "Research",
    description: research?.summary || "Research artifact from the owner",
    robots: { index: false, follow: false },
    openGraph: {
      title: research ? research.title : "Research",
      description: research?.summary || "Research insights",
      type: "article",
    },
  };
}

export default async function ResearchDetailPage(
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const result = await fetchResearchBySlug(slug);
  const research = result.research;

  if (result.state === "degraded" && !research) {
    return (
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif" }}>
        <article>
          <header style={{ marginBottom: "24px" }}>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "12px" }}>
              Research Temporarily Unavailable
            </h1>
            <p role="status" style={{ color: "#92400e" }}>
              The live research store could not be read. This is a degraded dependency state, not evidence that the requested research is missing.
            </p>
          </header>
          <p>
            <Link href="/kb/research" style={{ color: "#2563eb", textDecoration: "underline" }}>
              ← Back to research library
            </Link>
          </p>
        </article>
      </main>
    );
  }

  if (!research) {
    return (
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif" }}>
        <article>
          <header style={{ marginBottom: "24px" }}>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "12px" }}>
              Research Not Found
            </h1>
            <p style={{ color: "#666" }}>
              Could not find research for slug: <code style={{ backgroundColor: "#f3f4f6", padding: "2px 6px", borderRadius: "4px" }}>{slug}</code>
            </p>
          </header>
          <p>
            <Link href="/kb/research" style={{ color: "#2563eb", textDecoration: "underline" }}>
              ← Back to research library
            </Link>
          </p>
        </article>
      </main>
    );
  }

  // Schema.org structured data for ResearchProject
  const schemaData = {
    "@context": "https://schema.org",
    "@type": "ResearchProject",
    name: research.title,
    description: research.summary,
    author: {
      "@type": "Person",
      name: "the owner",
    },
    datePublished: research.date,
    keywords: research.keywords?.join(", "),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLd(schemaData) }}
      />
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif", lineHeight: 1.6 }}>
        <article>
          {result.state === "degraded" && (
            <aside role="status" style={{ marginBottom: "24px", padding: "14px", border: "1px solid #f59e0b", background: "#fffbeb", color: "#92400e" }}>
              This verified result loaded, but another research dependency is degraded. Reason codes: {result.reasonCodes.join(", ") || "backend_dependency_degraded"}.
            </aside>
          )}
          <header style={{ marginBottom: "32px" }}>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "8px" }}>
              {research.title}
            </h1>
            <p style={{ color: "#666", fontSize: "14px" }}>
              <small>{research.date}</small> — {research.type}
            </p>
          </header>

          <section style={{ marginBottom: "32px" }}>
            <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "12px" }}>
              Summary
            </h2>
            <p style={{ color: "#333" }}>{research.summary}</p>
          </section>

          {research.prospectIntelligence && (
            <section style={{ marginBottom: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
                Prospect Intelligence
              </h2>
              
              {(research.prospectIntelligence.target_personas?.length || 0) > 0 && (
                <>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "8px" }}>
                    Target Personas
                  </h3>
                  <ul style={{ listStyle: "disc", paddingLeft: "24px", marginBottom: "16px" }}>
                    {(research.prospectIntelligence.target_personas || []).map((p: string, i: number) => (
                      <li key={i} style={{ marginBottom: "4px", color: "#333" }}>{p}</li>
                    ))}
                  </ul>
                </>
              )}

              {(research.prospectIntelligence.pain_points?.length || 0) > 0 && (
                <>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "8px" }}>
                    Pain Points
                  </h3>
                  <ul style={{ listStyle: "disc", paddingLeft: "24px", marginBottom: "16px" }}>
                    {(research.prospectIntelligence.pain_points || []).map((p: string, i: number) => (
                      <li key={i} style={{ marginBottom: "4px", color: "#333" }}>{p}</li>
                    ))}
                  </ul>
                </>
              )}

              {(research.prospectIntelligence.language_patterns?.length || 0) > 0 && (
                <>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "8px" }}>
                    Language Patterns
                  </h3>
                  <ul style={{ listStyle: "disc", paddingLeft: "24px", marginBottom: "16px" }}>
                    {(research.prospectIntelligence.language_patterns || []).map((p: string, i: number) => (
                      <li key={i} style={{ marginBottom: "4px", color: "#333" }}>{p}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}

          {research.outreachTemplates && research.outreachTemplates.length > 0 && (
            <section style={{ marginBottom: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
                Outreach Templates
              </h2>
              {research.outreachTemplates.map((template: any, i: number) => (
                <div key={i} style={{ marginBottom: "24px", padding: "16px", backgroundColor: "#f9fafb", borderRadius: "8px" }}>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "8px" }}>
                    {template.channel} - {template.hook}
                  </h3>
                  <p style={{ whiteSpace: "pre-wrap", color: "#333", fontSize: "14px" }}>
                    {template.body}
                  </p>
                </div>
              ))}
            </section>
          )}

          {research.contentIdeas && research.contentIdeas.length > 0 && (
            <section style={{ marginBottom: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
                Content Ideas
              </h2>
              {research.contentIdeas.map((idea: any, i: number) => (
                <div key={i} style={{ marginBottom: "20px" }}>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "4px" }}>
                    {idea.title}
                  </h3>
                  <p style={{ fontSize: "14px", color: "#666", marginBottom: "8px" }}>
                    <strong>Platform:</strong> {idea.platform}
                  </p>
                  <p style={{ color: "#333" }}>{idea.description}</p>
                  {i < (research.contentIdeas?.length || 0) - 1 && (
                    <hr style={{ border: "none", borderTop: "1px solid #e5e7eb", margin: "16px 0" }} />
                  )}
                </div>
              ))}
            </section>
          )}

          {research.opportunityInsights && research.opportunityInsights.length > 0 && (
            <section style={{ marginBottom: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
                Opportunity Insights
              </h2>
              <ul style={{ listStyle: "disc", paddingLeft: "24px" }}>
                {research.opportunityInsights.map((insight: any, i: number) => (
                  <li key={i} style={{ marginBottom: "8px", color: "#333" }}>
                    <strong>{insight.opportunity}:</strong> {insight.description}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {research.keywords && research.keywords.length > 0 && (
            <section style={{ marginBottom: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "12px" }}>
                Keywords
              </h2>
              <p style={{ color: "#333" }}>{research.keywords.join(", ")}</p>
            </section>
          )}

          {research.trendingTopics && research.trendingTopics.length > 0 && (
            <section style={{ marginBottom: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "12px" }}>
                Trending Topics
              </h2>
              <p style={{ color: "#333" }}>{research.trendingTopics.join(", ")}</p>
            </section>
          )}

          <footer style={{ marginTop: "40px", paddingTop: "24px", borderTop: "1px solid #e5e7eb" }}>
            <p>
              <Link href="/kb/research" style={{ color: "#2563eb", textDecoration: "underline" }}>
                ← Back to research library
              </Link>
            </p>
          </footer>
        </article>
      </main>
    </>
  );
}
