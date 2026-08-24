const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '..', 'lib', 'control-login-rate-limit.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleValue = { exports: {} };
new Function('module', 'exports', compiled)(moduleValue, moduleValue.exports);
const {
  LOGIN_FAILURE_LIMIT,
  LOGIN_WINDOW_MS,
  loginRateStatus,
  recordLoginFailure,
  resetLoginRateLimit,
} = moduleValue.exports;

test('login limiter blocks parallel guessing after a bounded number of failures', () => {
  resetLoginRateLimit();
  const now = 1_000_000;
  for (let index = 1; index < LOGIN_FAILURE_LIMIT; index += 1) {
    assert.equal(recordLoginFailure(now + index).blocked, false);
  }
  const blocked = recordLoginFailure(now + LOGIN_FAILURE_LIMIT);
  assert.equal(blocked.blocked, true);
  assert.equal(blocked.retryAfterSeconds, LOGIN_WINDOW_MS / 1000);
  assert.equal(loginRateStatus(now + LOGIN_FAILURE_LIMIT + 1).blocked, true);
});

test('login limiter expires deterministically and success can reset it', () => {
  resetLoginRateLimit();
  const now = 2_000_000;
  for (let index = 0; index < LOGIN_FAILURE_LIMIT; index += 1) recordLoginFailure(now + index);
  assert.equal(loginRateStatus(now + LOGIN_WINDOW_MS + LOGIN_FAILURE_LIMIT).blocked, false);
  recordLoginFailure(now + LOGIN_WINDOW_MS + LOGIN_FAILURE_LIMIT + 1);
  resetLoginRateLimit();
  assert.equal(loginRateStatus(now + LOGIN_WINDOW_MS + LOGIN_FAILURE_LIMIT + 2).remainingFailures, LOGIN_FAILURE_LIMIT);
});

test('login route exposes a bounded 429 contract without client or credential identifiers', () => {
  const route = fs.readFileSync(path.join(__dirname, '..', 'app', 'api', 'auth', 'login', 'route.ts'), 'utf8');
  assert.match(route, /status:\s*429/);
  assert.match(route, /'Retry-After'/);
  assert.doesNotMatch(route, /x-forwarded-for|request\.ip|password.*Map/i);
});
