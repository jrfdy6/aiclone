const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.join(__dirname, '..');
const opsSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const opsPageSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'page.tsx'), 'utf8');
const brainSource = fs.readFileSync(path.join(frontendRoot, 'app', 'brain', 'BrainClient.tsx'), 'utf8');

test('Ops puts SOURCE_OF_TRUTH first without a filesystem-backed server fallback', () => {
  assert.match(opsSource, /const PINNED_DOC_PATHS = \[\s*'SOURCE_OF_TRUTH\.md'/);
  assert.match(opsPageSource, /docEntries=\{\[\]\}/);
  assert.doesNotMatch(opsPageSource, /PINNED_DOC_PATHS|readFile|existsSync|(?:node:)?fs|(?:node:)?path/);
});

test('Ops consumes the shared authenticated Brain Docs contract', () => {
  assert.match(opsSource, /controlApiGet<BrainDocsIndexPayload>\('\/api\/brain\/docs'/);
  assert.match(opsSource, /controlApiGet<DocReference>\(`\/api\/brain\/docs\/content\?path=/);
  assert.doesNotMatch(opsSource, /doc\.path === PINNED_DOC_PATHS\[0\]/);
  assert.match(opsSource, /doc\.path === ARCHITECTURE_DOC_PATH/);
});

test('Brain preserves backend read order and displays authority metadata', () => {
  assert.match(brainSource, /items: items\.sort\(compareDocEntries\)/);
  assert.match(brainSource, /typeof left\.readOrder === 'number'/);
  assert.match(brainSource, /doc\.authority === 'binding'/);
});
