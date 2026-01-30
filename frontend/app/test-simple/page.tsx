export default function TestSimplePage() {
  console.log("🔍 TEST-SIMPLE: Function called at", new Date().toISOString());
  console.log("🔍 TEST-SIMPLE: Environment:", {
    NODE_ENV: process.env.NODE_ENV,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  });
  
  return (
    <html>
      <head>
        <title>Test Simple</title>
      </head>
      <body>
        <h1>✅ Success!</h1>
        <p>If you can see this, Next.js is working.</p>
        <p>Timestamp: {new Date().toISOString()}</p>
        <p>NODE_ENV: {process.env.NODE_ENV}</p>
        <p>API URL: {process.env.NEXT_PUBLIC_API_URL || "not set"}</p>
      </body>
    </html>
  );
}
