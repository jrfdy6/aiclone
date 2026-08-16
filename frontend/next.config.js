/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // This service has its own lockfile and is deployed from the frontend
  // directory. Pin tracing here so a parent lockfile cannot widen the Railway
  // build context or influence dependency discovery.
  outputFileTracingRoot: __dirname,
};

module.exports = nextConfig;
