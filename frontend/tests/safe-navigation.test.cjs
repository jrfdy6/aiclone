const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const sourcePath = path.join(__dirname, '..', 'lib', 'safe-navigation.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loadedModule, loadedModule.exports, require);
const { safeInternalRedirect } = loadedModule.exports;

test('keeps same-origin paths and their query strings', () => {
  assert.equal(safeInternalRedirect('/ops?tab=queue'), '/ops?tab=queue');
  assert.equal(safeInternalRedirect('/workspace#active'), '/workspace#active');
});

test('rejects protocol-relative and external login redirects', () => {
  const unsafeTargets = [
    '//example.com',
    '///example.com',
    '/\\example.com',
    '/%2f%2fexample.com',
    '/%5cexample.com',
    'https://example.com',
    'javascript:alert(1)',
  ];

  for (const target of unsafeTargets) {
    assert.equal(safeInternalRedirect(target), '/ops', target);
  }
});

test('uses the fallback for empty and malformed targets', () => {
  assert.equal(safeInternalRedirect(null), '/ops');
  assert.equal(safeInternalRedirect('not-a-path'), '/ops');
  assert.equal(safeInternalRedirect('//example.com', '/brain'), '/brain');
});
