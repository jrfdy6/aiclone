import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Johnnie Fields - Digital Knowledge Base",
  description: "AI-readable knowledge base",
  robots: { index: true, follow: true },
};

export default async function KbLandingPage() {
  return (
    <main style={{ maxWidth: "800px", margin: "0 auto", padding: "40px 24px", fontFamily: "system-ui, sans-serif", lineHeight: 1.6 }}>
      <article>
        <header style={{ marginBottom: "40px" }}>
          <h1 style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "16px" }}>
            Johnnie Fields - Digital Knowledge Base
          </h1>
          <p style={{ fontSize: "18px", color: "#666" }}>
            This is a crawl-friendly interface to Johnnie's professional knowledge,
            voice patterns, and research insights.
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
          </ul>
        </section>

        <section>
          <h2 style={{ fontSize: "24px", fontWeight: "600", marginBottom: "16px" }}>
            Status
          </h2>
          <p>✅ Knowledge base is operational</p>
          <p>
            <Link href="/kb/health" style={{ color: "#2563eb", textDecoration: "underline" }}>
              Check system health →
            </Link>
          </p>
        </section>
      </article>
    </main>
  );
}
