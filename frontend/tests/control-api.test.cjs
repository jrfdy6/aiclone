const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '..', 'lib', 'control-api.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleValue = { exports: {} };
new Function('module', 'exports', compiled)(moduleValue, moduleValue.exports);
const { ControlApiError, ownerSafeErrorMessage, readSafeControlError } = moduleValue.exports;

test('structured bounded backend failures remain useful to the owner', async () => {
  const error = await readSafeControlError(new Response(JSON.stringify({
    detail: {
      reason_code: 'variant_parent_remote_binding_missing',
      message: 'Choose a generated revision whose approved remote-safe input binding is retained.',
    },
  }), { status: 409, headers: { 'content-type': 'application/json' } }));
  assert.ok(error instanceof ControlApiError);
  assert.equal(error.status, 409);
  assert.equal(error.reasonCode, 'variant_parent_remote_binding_missing');
  assert.equal(error.message, 'Choose a generated revision whose approved remote-safe input binding is retained.');
});

test('raw upstream diagnostics and arbitrary text never reach the owner surface', async () => {
  const raw = await readSafeControlError(new Response(JSON.stringify({
    detail: {
      reason_code: 'worker_failed',
      message: `Traceback: ${['', 'Users', 'test-owner', 'private.py'].join('/')} PRIVATE_VALUE=abc`,
    },
  }), { status: 503, headers: { 'content-type': 'application/json' } }));
  assert.equal(raw.message, 'The local content worker is temporarily unavailable. Your content was not changed.');
  assert.doesNotMatch(raw.message, /Users|SECRET|Traceback/);

  const html = await readSafeControlError(new Response('<html>proxy internals</html>', { status: 502 }));
  assert.equal(html.message, 'The action could not be completed. Your content was not changed.');
});

test('authentication failures provide one actionable bounded message', async () => {
  const error = await readSafeControlError(new Response('{}', {
    status: 401,
    headers: { 'content-type': 'application/json' },
  }));
  assert.equal(error.reasonCode, 'control_http_401');
  assert.match(error.message, /session expired/i);
});

test('non-HTTP job errors are bounded before a component renders them', () => {
  assert.equal(
    ownerSafeErrorMessage(new Error('The exact decision version changed.'), 'Decision failed safely.'),
    'The exact decision version changed.',
  );
  assert.equal(
    ownerSafeErrorMessage(new Error('Traceback from /private/tmp/decision.py'), 'Decision failed safely.'),
    'Decision failed safely.',
  );
});
