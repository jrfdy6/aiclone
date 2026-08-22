const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');


const frontendRoot = path.join(__dirname, '..');
const repoRoot = path.join(frontendRoot, '..');
const harness = fs.readFileSync(
  path.join(repoRoot, 'scripts', 'run_integrated_owner_acceptance.py'),
  'utf8',
);
const content = fs.readFileSync(
  path.join(frontendRoot, 'app', 'workspace', 'IntegratedContentPortfolio.tsx'),
  'utf8',
);
const ops = fs.readFileSync(
  path.join(frontendRoot, 'app', 'workspace', 'OpsStandupSummary.tsx'),
  'utf8',
);
const decisions = fs.readFileSync(
  path.join(frontendRoot, 'app', 'workspace', 'OwnerDecisionSurface.tsx'),
  'utf8',
);


test('isolated acceptance browser contract names only real owner-surface selectors', () => {
  const mappings = [
    ['#integrated-content-portfolio', content, 'id="integrated-content-portfolio"'],
    ['#ops-standup-summary', ops, 'id="ops-standup-summary"'],
    ['#owner-decision-surface', decisions, 'id="owner-decision-surface"'],
  ];
  for (const [selector, source, exactId] of mappings) {
    assert.ok(harness.includes(`"${selector}"`));
    assert.ok(source.includes(exactId));
  }
  for (const visibleText of [
    'Sources → Opportunities → Posts',
    'Ops Standup Summary and Conclusion',
    'Owner Decisions',
    'LinkedIn variant',
    'Instagram variant',
    'Complete source-to-decision lineage',
  ]) {
    assert.ok(harness.includes(visibleText));
    assert.ok(`${content}\n${ops}\n${decisions}`.includes(visibleText));
  }
});

test('acceptance receipt cannot masquerade as owner history or production browser proof', () => {
  assert.match(harness, /canonical_owner_state_mutated["']:\s*False/);
  assert.match(harness, /canonical_owner_fact_claims["']:\s*False/);
  assert.match(harness, /production_release_evidence["']:\s*False/);
  assert.match(harness, /production_browser_verified["']:\s*False/);
  assert.match(harness, /external_social_actions["']:\s*False/);
  assert.match(harness, /SYNTHETIC ACCEPTANCE CANARY — NOT OWNER HISTORY/);
  assert.match(harness, /build_integrated_content_projection/);
  assert.match(harness, /build_ops_standup_projection/);
  assert.match(harness, /verify_projection_story\(content, ops\)/);
});
