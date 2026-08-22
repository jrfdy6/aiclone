const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '..', 'lib', 'control-cookie-policy.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleValue = { exports: {} };
new Function('module', 'exports', compiled)(moduleValue, moduleValue.exports);
const { shouldUseSecureSessionCookie } = moduleValue.exports;

test('production session cookies stay secure by default', () => {
  assert.equal(shouldUseSecureSessionCookie({
    nodeEnv: 'production', protocol: 'http:', hostname: '192.168.68.75',
  }), true);
  assert.equal(shouldUseSecureSessionCookie({
    nodeEnv: 'production', localBetaMode: '1', allowHttpCookie: '1', protocol: 'https:', hostname: 'example.com',
  }), true);
});

test('the explicit beta exception is limited to private local HTTP hosts', () => {
  const enabled = { nodeEnv: 'production', localBetaMode: '1', allowHttpCookie: '1', protocol: 'http:' };
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: '192.168.68.75' }), false);
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: '192.168.68.75:3000' }), false);
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: '127.0.0.1' }), false);
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: 'localhost:3000' }), false);
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: '10.0.0.4' }), false);
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: '172.20.0.4' }), false);
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: '203.0.113.9' }), true);
  assert.equal(shouldUseSecureSessionCookie({ ...enabled, hostname: 'owner.example.com' }), true);
});

test('development cookies remain usable over local HTTP without weakening production defaults', () => {
  assert.equal(shouldUseSecureSessionCookie({
    nodeEnv: 'development', protocol: 'http:', hostname: 'localhost',
  }), false);
});
