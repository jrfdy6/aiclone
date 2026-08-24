const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(frontendRoot, relativePath), 'utf8');
}

test('Ops page never serializes repository or private-runtime files into React props', () => {
  const source = read('app/ops/page.tsx');

  assert.match(source, /workspaceFiles=\{\[\]\}/);
  assert.match(source, /docEntries=\{\[\]\}/);
  assert.match(source, /artifacts: \[\]/);
  assert.match(source, /chronicleEntries: \[\]/);
  assert.match(source, /standupPreps: \[\]/);
  assert.match(source, /pmRecommendations: \[\]/);
  assert.doesNotMatch(source, /(?:from|require\()["'](?:node:)?fs["']/);
  assert.doesNotMatch(source, /(?:from|require\()["'](?:node:)?path["']/);
  assert.doesNotMatch(
    source,
    /readFile|readJson|existsSync|statSync|readdir|process\.cwd|AI_CLONE_ROOT|resolveWorkspaceRoot|loadWorkspaceFiles|loadDocEntries|loadExecutiveFeed/,
  );
});

const compatibilityRoutes = new Map([
  ['app/activity/page.tsx', '/ops'],
  ['app/calendar/page.tsx', '/prospects'],
  ['app/dashboard/page.tsx', '/ops'],
  ['app/outreach/page.tsx', '/prospects'],
  ['app/outreach/[prospectId]/page.tsx', '/prospects'],
  ['app/personas/page.tsx', '/brain#brain-section-persona'],
  ['app/research-tasks/page.tsx', '/brain#brain-section-briefs'],
  ['app/templates/page.tsx', '/workspace'],
  ['app/vault/page.tsx', '/brain#brain-section-docs'],
  ['app/playbooks/page.tsx', '/ops'],
  ['app/api-test/page.tsx', '/ops'],
  ['app/test-simple/page.tsx', '/ops'],
  ['app/kb/page.tsx', '/brain#brain-section-docs'],
  ['app/kb/[query]/page.tsx', '/brain#brain-section-docs'],
  ['app/(pages)/knowledge/page.tsx', '/brain#brain-section-docs'],
]);

test('retired mock and debug routes only redirect to canonical owner surfaces', () => {
  for (const [relativePath, target] of compatibilityRoutes) {
    const source = read(relativePath);
    const escapedTarget = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    assert.match(source, /import \{ redirect \} from ['"]next\/navigation['"]/);
    assert.match(source, new RegExp(`redirect\\(['"]${escapedTarget}['"]\\)`));
    assert.doesNotMatch(source, /['"]use client['"]/);
    assert.doesNotMatch(source, /useState|useEffect|fetch\(|apiFetch|NEXT_PUBLIC_API_URL|localhost|dev-user/);
    assert.doesNotMatch(
      source,
      /Example Prospect|Sarah Johnson|Emily Rodriguez|TechEd Solutions|status:\s*['"]success['"]|Knowledge base is operational|Test Passed|Backend API<|Firestore<|AI Services</,
    );
  }
});

test('authenticated owner routes are not advertised in the public sitemap', () => {
  const source = read('app/sitemap.ts');

  assert.match(source, /return \[\]/);
  assert.doesNotMatch(source, /\/kb|\/ops|\/brain|\/workspace|\/prospects/);
});
