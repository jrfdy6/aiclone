export default function TestSimplePage() {
  return (
    <html>
      <head>
        <title>Test Simple</title>
      </head>
      <body>
        <h1>✅ Success!</h1>
        <p>If you can see this, Next.js is working.</p>
        <p>Timestamp rendering disabled to keep this route hydration-safe.</p>
        <p>NODE_ENV: {process.env.NODE_ENV}</p>
        <p>API URL: {process.env.NEXT_PUBLIC_API_URL || "not set"}</p>
      </body>
    </html>
  );
}
