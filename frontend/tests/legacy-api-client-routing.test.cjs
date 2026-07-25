const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.resolve(__dirname, '..');
const apiClientSource = fs.readFileSync(
  path.join(frontendRoot, 'lib', 'api-client.ts'),
  'utf8'
);

test('legacy API client always uses the authenticated same-origin proxy', () => {
  assert.match(apiClientSource, /const CONTROL_API_BASE = ['"]\/api\/control['"]/);
  assert.match(apiClientSource, /return CONTROL_API_BASE/);
  assert.doesNotMatch(apiClientSource, /NEXT_PUBLIC_API_URL/);
  assert.doesNotMatch(apiClientSource, /localhost:3001/);
});

test('legacy API client rejects absolute backend URLs', () => {
  assert.match(apiClientSource, /\/\^https\?:\\\/\\\/\$?\/i\.test\(endpoint\)/);
  assert.match(
    apiClientSource,
    /Absolute backend URLs are not supported in the browser client/
  );
  assert.doesNotMatch(apiClientSource, /endpoint\.startsWith\(['"]http['"]\)\s*\?/);
});
