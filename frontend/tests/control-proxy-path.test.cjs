const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const sourcePath = path.join(__dirname, '..', 'lib', 'control-proxy.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loadedModule, loadedModule.exports, require);
const { isSupportedControlProxyRequest } = loadedModule.exports;

test('permits authenticated API routes for supported methods', () => {
  for (const method of ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']) {
    assert.equal(isSupportedControlProxyRequest('api/pm/cards', method), true, method);
  }
});

test('permits only GET for the exact backend health route', () => {
  assert.equal(isSupportedControlProxyRequest('health', 'GET'), true);
  assert.equal(isSupportedControlProxyRequest('health', 'POST'), false);
  assert.equal(isSupportedControlProxyRequest('health', 'DELETE'), false);
});

test('rejects unsupported backend root and lookalike routes', () => {
  for (const candidate of [
    '',
    'api',
    'apiary/status',
    'health/check',
    'healthcheck',
    'test',
    'docs',
    'redoc',
    'openapi.json',
  ]) {
    assert.equal(isSupportedControlProxyRequest(candidate, 'GET'), false, candidate);
  }
});
