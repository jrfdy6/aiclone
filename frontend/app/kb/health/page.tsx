export const dynamic = "force-dynamic";

export default function KbHealthPage() {
  const envCheck = {
    hasApiUrl: !!process.env.NEXT_PUBLIC_API_URL,
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "not set",
    hasFirebase: !!process.env.FIREBASE_SERVICE_ACCOUNT,
    hasUserId: !!process.env.DEFAULT_USER_ID,
    userId: process.env.DEFAULT_USER_ID || "not set",
    hasSiteUrl: !!process.env.NEXT_PUBLIC_SITE_URL,
    siteUrl: process.env.NEXT_PUBLIC_SITE_URL || "not set",
    nodeEnv: process.env.NODE_ENV,
  };

  return (
    <html>
      <body style={{ fontFamily: "monospace", padding: "20px", backgroundColor: "#1a1a1a", color: "#00ff00" }}>
        <h1>KB Health Check</h1>
        <pre>{JSON.stringify(envCheck, null, 2)}</pre>
        <hr />
        <p>If you see this page, Next.js is working!</p>
        <p>Status: ✅ OK</p>
      </body>
    </html>
  );
}
