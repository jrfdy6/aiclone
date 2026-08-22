const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(frontendRoot, relativePath), 'utf8');
}

test('frontend Firebase Admin authority is fully retired', () => {
  const packageJson = JSON.parse(read('package.json'));

  assert.equal(fs.existsSync(path.join(frontendRoot, 'lib/firestore-server.ts')), false);
  assert.equal(fs.existsSync(path.join(frontendRoot, 'app/kb/page-original.tsx')), false);
  assert.equal(Boolean(packageJson.dependencies?.['firebase-admin']), false);
  assert.doesNotMatch(read('package-lock.json'), /node_modules\/firebase-admin/);
});

test('active research pages use the authenticated backend as the Firestore credential boundary', () => {
  const indexSource = read('app/kb/research/page.tsx');
  const detailSource = read('app/kb/research/[slug]/page.tsx');
  const healthSource = read('app/kb/health/page.tsx');
  const backendSource = read('lib/research-backend.ts');

  assert.match(indexSource, /fetchResearchLibrary/);
  assert.match(detailSource, /fetchResearchBySlug/);
  assert.doesNotMatch(indexSource, /firebase-admin|firestore-server|FIREBASE_SERVICE_ACCOUNT/);
  assert.doesNotMatch(detailSource, /firebase-admin|firestore-server|FIREBASE_SERVICE_ACCOUNT/);
  assert.doesNotMatch(healthSource, /firebase-admin|firestore-server|FIREBASE_SERVICE_ACCOUNT|NEXT_PUBLIC_API_URL/);
  assert.match(healthSource, /fetchResearchLibrary/);
  assert.match(backendSource, /CONTROL_PLANE_SERVICE_TOKEN/);
  assert.match(backendSource, /BACKEND_API_URL/);
  assert.match(backendSource, /Authorization: `Bearer \$\{token\}`/);
  assert.match(backendSource, /backend_timeout|backend_unavailable/);
  assert.match(backendSource, /boundedText/);
  assert.match(backendSource, /boundedStringArray/);
});

test('research pages distinguish degraded dependency state from verified empty or not-found state', () => {
  const indexSource = read('app/kb/research/page.tsx');
  const detailSource = read('app/kb/research/[slug]/page.tsx');

  assert.match(indexSource, /firestoreState === "degraded"/);
  assert.match(indexSource, /not claiming that the research library is empty/);
  assert.match(indexSource, /No verified topic-intelligence rows loaded/);
  assert.match(detailSource, /result.state === "degraded" && !research/);
  assert.match(detailSource, /not evidence that the requested research is missing/);
  assert.match(detailSource, /Research Not Found/);
  assert.match(indexSource, /robots: \{ index: false, follow: false \}/);
});

test('public sitemap is static and cannot enumerate Firestore-derived research records', () => {
  const sitemapSource = read('app/sitemap.ts');

  assert.doesNotMatch(sitemapSource, /firebase-admin|firestore-server|FIREBASE_SERVICE_ACCOUNT/);
  assert.doesNotMatch(sitemapSource, /topic_intelligence|prospect_discoveries|\/kb\/research/);
  assert.match(sitemapSource, /sitemap stays static/i);
});

test('Firestore-derived JSON-LD escapes script-closing input', () => {
  const indexSource = read('app/kb/research/page.tsx');
  const detailSource = read('app/kb/research/[slug]/page.tsx');
  const querySource = read('app/kb/[query]/page.tsx');
  const helperSource = read('lib/safe-json-ld.ts');

  assert.match(indexSource, /safeJsonLd\(schemaData\)/);
  assert.match(detailSource, /safeJsonLd\(schemaData\)/);
  assert.match(querySource, /safeJsonLd\(schemaData\)/);
  assert.doesNotMatch(indexSource, /__html: JSON\.stringify/);
  assert.doesNotMatch(detailSource, /__html: JSON\.stringify/);
  assert.doesNotMatch(querySource, /__html: JSON\.stringify/);
  assert.ok(helperSource.includes(".replace(/</g, '\\\\u003c')"));

  const serialized = JSON.stringify({ title: '</script><script>alert(1)</script>' })
    .replace(/</g, '\\u003c');
  assert.equal(serialized.includes('</script>'), false);
  assert.equal(serialized.includes('\\u003c/script>'), true);
});
