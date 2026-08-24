const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const frontendRoot = path.resolve(__dirname, '..');
const clientSource = fs.readFileSync(path.join(frontendRoot, 'lib', 'client-error-reporting.ts'), 'utf8');
const routeSource = fs.readFileSync(path.join(frontendRoot, 'app', 'api', 'client-errors', 'route.ts'), 'utf8');
const reporterSource = fs.readFileSync(path.join(frontendRoot, 'components', 'runtime', 'ClientErrorReporter.tsx'), 'utf8');
const compiled = ts.transpileModule(clientSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', compiled)(loadedModule, loadedModule.exports);
const {
  normalizeClientRouteTemplate,
  normalizeRejectionReason,
  normalizeWindowError,
} = loadedModule.exports;

test('client telemetry reduces concrete URLs to stable route templates', () => {
  assert.equal(normalizeClientRouteTemplate('/ops?token=private-value'), '/ops');
  assert.equal(normalizeClientRouteTemplate('/inbox/thread-private-123?secret=yes'), '/inbox/:id');
  assert.equal(normalizeClientRouteTemplate('/not-an-approved-route/private-name'), '/:route');
});

test('client telemetry derives a reason code without carrying messages or stacks', () => {
  const absolutePathCanary = ['', 'Users', 'owner', 'project', 'file.ts'].join('/');
  const secretError = new Error(['Bearer', 'private-token', 'at', absolutePathCanary].join(' '));
  secretError.stack = 'STACK WITH PRIVATE_VALUE';
  assert.deepEqual(normalizeWindowError(secretError, 'private fallback'), { reasonCode: 'window_error' });
  assert.deepEqual(normalizeRejectionReason('PRIVATE_VALUE'), { reasonCode: 'unhandled_rejection' });
});

test('browser and server telemetry use a strict metadata allowlist', () => {
  for (const forbidden of ['userAgent', 'forwardedFor', 'x-forwarded-for', 'requestId', 'event.filename']) {
    assert.doesNotMatch(`${clientSource}\n${routeSource}\n${reporterSource}`, new RegExp(forbidden.replaceAll('-', '\\-'), 'i'));
  }
  assert.doesNotMatch(reporterSource, /window\.location\.href|\.stack|\.message/);
  assert.doesNotMatch(routeSource, /payload\.(?:message|stack|href|userAgent|detail)/);
  for (const allowed of ['reasonCode', 'digest', 'route', 'release', 'environment', 'service', 'line', 'column', 'capturedAt']) {
    assert.match(routeSource, new RegExp(allowed));
  }
});
