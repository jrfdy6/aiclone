import type { Metadata } from "next";
import Link from "next/link";

export const dynamic = "force-dynamic";
export const revalidate = 0;

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

async function fetchResearchBySlug(slug: string) {
  try {
    const { db } = await import("@/lib/firestore-server");
    const userId = process.env.DEFAULT_USER_ID || "default-user";

    // Try topic_intelligence first
    const topicDocs = await db
      .collection("users")
      .doc(userId)
      .collection("topic_intelligence")
      .get();

    for (const doc of topicDocs.docs) {
      const data = doc.data();
      const docSlug = generateSlug(
        data.theme_display || data.theme,
        data.created_at
      );
      if (docSlug === slug) {
        return {
          id: doc.id,
          type: "Topic Intelligence",
          title: data.theme_display || data.theme,
          date: new Date(data.created_at * 1000).toLocaleDateString("en-US", {
            month: "long",
            day: "numeric",
            year: "numeric",
          }),
          summary: data.summary,
          prospectIntelligence: data.prospect_intelligence,
          outreachTemplates: data.outreach_templates,
          contentIdeas: data.content_ideas,
          opportunityInsights: data.opportunity_insights,
          keywords: data.keywords,
          trendingTopics: data.trending_topics,
        };
      }
    }

    // Try prospect_discoveries
    const discoveryDocs = await db
      .collection("users")
      .doc(userId)
      .collection("prospect_discoveries")
      .get();

    for (const doc of discoveryDocs.docs) {
      const data = doc.data();
      const docSlug = generateSlug(
        `${data.source || "prospects"}-${data.location || "discovery"}`,
        data.created_at
      );
      if (docSlug === slug) {
        // Filter out PII from prospects
        const prospects = (data.prospects || []).map((p: any) => ({
          name: p.name || "Anonymous",
          title: p.title,
          specialty: p.specialty,
          // EXCLUDE: email, phone, website
        }));

        return {
          id: doc.id,
          type: "Prospect Discovery",
          title: `${data.source || "Prospect"} Discovery - ${data.location || "Unknown"}`,
          date: new Date(data.created_at * 1000).toLocaleDateString("en-US", {
            month: "long",
            day: "numeric",
            year: "numeric",
          }),
          summary: `Found ${prospects.length} prospects in ${data.location || "unknown location"} using ${data.source || "unknown source"}.`,
          prospects: prospects.slice(0, 10), // Limit to first 10 for crawling
          keywords: [data.source, data.location, data.specialty].filter(Boolean),
          source: data.source,
          location: data.location,
        };
      }
    }

    return null;
  } catch (error) {
    console.error("Error fetching research:", error);
    return null;
  }
}

export async function generateMetadata(
  { params }: { params: { slug: string } }
): Promise<Metadata> {
  const research = await fetchResearchBySlug(params.slug);

  return {
    title: research ? `${research.title} - Research` : "Research",
    description: research?.summary || "Research artifact from Johnnie Fields",
    robots: { index: true, follow: true },
    openGraph: {
      title: research ? research.title : "Research",
      description: research?.summary || "Research insights",
      type: "article",
    },
  };
}

export default async function ResearchDetailPage(
  { params }: { params: { slug: string } }
) {
  const research = await fetchResearchBySlug(params.slug);

  if (!research) {
    return (
      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif" }}>
        <article>
          <header style={{ marginBottom: "24px" }}>
            <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "12px" }}>
              Research Not Found
            </h1>
            <p style={{ color: "#666" }}>
              Could not find research for slug: <code style={{ backgroundColor: "#f3f4f6", padding: "2px 6px", borderRadius: "4px" }}>{params.slug}</code>
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
      name: "Johnnie Fields",
    },
    datePublished: research.date,
    keywords: research.keywords?.join(", "),
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
              
              {research.prospectIntelligence.target_personas?.length > 0 && (
                <>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "8px" }}>
                    Target Personas
                  </h3>
                  <ul style={{ listStyle: "disc", paddingLeft: "24px", marginBottom: "16px" }}>
                    {research.prospectIntelligence.target_personas.map((p: string, i: number) => (
                      <li key={i} style={{ marginBottom: "4px", color: "#333" }}>{p}</li>
                    ))}
                  </ul>
                </>
              )}

              {research.prospectIntelligence.pain_points?.length > 0 && (
                <>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "8px" }}>
                    Pain Points
                  </h3>
                  <ul style={{ listStyle: "disc", paddingLeft: "24px", marginBottom: "16px" }}>
                    {research.prospectIntelligence.pain_points.map((p: string, i: number) => (
                      <li key={i} style={{ marginBottom: "4px", color: "#333" }}>{p}</li>
                    ))}
                  </ul>
                </>
              )}

              {research.prospectIntelligence.language_patterns?.length > 0 && (
                <>
                  <h3 style={{ fontSize: "18px", fontWeight: "600", marginBottom: "8px" }}>
                    Language Patterns
                  </h3>
                  <ul style={{ listStyle: "disc", paddingLeft: "24px", marginBottom: "16px" }}>
                    {research.prospectIntelligence.language_patterns.map((p: string, i: number) => (
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
                  {i < research.contentIdeas.length - 1 && (
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

          {research.prospects && research.prospects.length > 0 && (
            <section style={{ marginBottom: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
                Sample Prospects (PII Filtered)
              </h2>
              <p style={{ color: "#666", fontSize: "14px", marginBottom: "16px" }}>
                Showing first {research.prospects.length} prospects. Contact information removed for privacy.
              </p>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {research.prospects.map((prospect: any, i: number) => (
                  <li key={i} style={{ marginBottom: "12px", padding: "12px", backgroundColor: "#f9fafb", borderRadius: "6px" }}>
                    <strong>{prospect.name}</strong>
                    {prospect.title && <span style={{ color: "#666" }}> — {prospect.title}</span>}
                    {prospect.specialty && (
                      <p style={{ margin: "4px 0 0 0", fontSize: "14px", color: "#666" }}>
                        Specialty: {prospect.specialty}
                      </p>
                    )}
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
