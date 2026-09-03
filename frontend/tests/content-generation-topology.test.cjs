const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const frontendRoot = path.join(__dirname, '..');
const helperSource = fs.readFileSync(path.join(frontendRoot, 'lib', 'content-generation-topology.ts'), 'utf8');
const workspaceSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'WorkspaceClient.tsx'), 'utf8');
const postingSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'posting', 'page.tsx'), 'utf8');
const opsSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const executiveDecisionQueueSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'ExecutiveDecisionQueue.tsx'), 'utf8');

const compiled = ts.transpileModule(helperSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const {
  LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_KEY,
  LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_VALUE,
  legacyTwoOptionCompatibilityRequested,
} = loaded.exports;

test('canonical lifecycle is the default and the former comparator needs the exact rollback switch', () => {
  assert.equal(legacyTwoOptionCompatibilityRequested(new URLSearchParams()), false);
  assert.equal(
    legacyTwoOptionCompatibilityRequested(new URLSearchParams('content_topology=canonical_content_lifecycle')),
    false,
  );
  assert.equal(
    legacyTwoOptionCompatibilityRequested(
      new URLSearchParams(`${LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_KEY}=${LEGACY_TWO_OPTION_COMPATIBILITY_QUERY_VALUE}`),
    ),
    true,
  );
});

test('both owner-facing surfaces isolate the legacy writer and expose the integrated authority by default', () => {
  for (const source of [workspaceSource, postingSource]) {
    assert.match(source, /legacyTwoOptionCompatibilityRequested/);
    assert.match(source, /legacyTwoOptionCompatibilityEnabled \? \(/);
    assert.match(source, /data-content-generation-authority="legacy_two_option_compatibility"/);
    assert.match(source, /data-content-generation-authority="canonical_content_lifecycle"/);
    assert.match(source, /option_count: 2/);
  }
  assert.match(postingSource, /<IntegratedContentPortfolio\s*\/>/);
  assert.match(postingSource, /if \(!legacyTwoOptionCompatibilityEnabled\) \{\s*return;/);
  assert.match(workspaceSource, /One base post, linked revisions/);
  assert.match(postingSource, /Create one base post, then request linked variants/);
});

test('default Workspace and Ops neither load nor render the historical owner-review lane', () => {
  assert.match(
    workspaceSource,
    /if \(!legacyTwoOptionCompatibilityEnabled\) \{[\s\S]{0,260}setOwnerReviewItems\(\[\]\);[\s\S]{0,260}return;[\s\S]{0,220}linkedin-os-owner-review\?include_resolved=true/,
  );
  assert.match(
    workspaceSource,
    /\{legacyTwoOptionCompatibilityEnabled \? \(\s*<section id="owner-review-lane" data-legacy-owner-review-compatibility="true"/,
  );
  assert.match(opsSource, /legacyTwoOptionCompatibilityRequested\(searchParams\)/);
  assert.match(
    opsSource,
    /legacyOwnerReviewCompatibilityEnabled\s*\? pmCards\s*:\s*pmCards\.filter\(\(card\) => !legacyOwnerReviewCardIds\.has\(card\.id\)\)/,
  );
  assert.doesNotMatch(opsSource, /loadFeezieOwnerReview|setFeezieOwnerReviewItems|<LinkedinWorkspaceSurface/);
  assert.match(opsSource, /Open FEEZIE workspace/);
});

test('legacy owner-review requests carry the rollback marker only behind the compatibility switch', () => {
  for (const source of [workspaceSource, postingSource]) {
    assert.match(source, /if \(!legacyTwoOptionCompatibilityEnabled\)/);
    assert.match(source, /send-to-review\?legacy_compatibility=true/);
  }
  assert.match(workspaceSource, /linkedin-os-owner-review\/\$\{item\.queue_id\}\?legacy_compatibility=true/);
  assert.doesNotMatch(
    opsSource,
    /owner-review\/sync/,
    'passive Ops reads must never trigger the legacy owner-review writer',
  );
  assert.match(opsSource, /cards\/\$\{cardId\}\/owner-review\?legacy_compatibility=true/);
  assert.match(
    opsSource,
    /const compatibilityQuery = legacyOwnerReviewCompatibilityEnabled \? '\?legacy_compatibility=true' : '';/,
  );
  for (const endpoint of [
    /cards\/\$\{cardId\}\/dispatch\$\{compatibilityQuery\}/,
    /cards\/\$\{cardId\}\/actions\$\{compatibilityQuery\}/,
    /cards\/\$\{cardId\}\/host-action\/run\$\{compatibilityQuery\}/,
  ]) {
    assert.match(opsSource, endpoint);
  }
  assert.match(
    opsSource,
    /if \(!legacyOwnerReviewCompatibilityEnabled\)[\s\S]{0,300}?historical owner-review decision writer/,
  );
  assert.match(
    executiveDecisionQueueSource,
    /legacyOwnerReviewCompatibilityEnabled \|\| decision\.source_type !== 'workspace_review'/,
  );
  assert.match(executiveDecisionQueueSource, /\?legacy_compatibility=true/);
});
