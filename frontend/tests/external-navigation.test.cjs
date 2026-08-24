const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '..', 'lib', 'display-privacy.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', compiled)(loadedModule, loadedModule.exports);
const { safeExternalHttpsUrl } = loadedModule.exports;

test('external navigation permits normalized credential-free HTTPS URLs', () => {
  assert.equal(
    safeExternalHttpsUrl('  https://example.com/source?q=bounded#section  '),
    'https://example.com/source?q=bounded#section',
  );
  assert.equal(
    safeExternalHttpsUrl('https://news.example.com/item', {
      allowedHosts: ['example.com'],
      allowSubdomains: true,
    }),
    'https://news.example.com/item',
  );
});

test('external navigation rejects active schemes, insecure transport, and credentials', () => {
  const rejected = [
    'javascript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'file:///private/tmp/owner.txt',
    'http://example.com/source',
    ['https://', 'user', ':', 'password', '@', 'example.com/source'].join(''),
    '//example.com/source',
    'not a URL',
    '',
    null,
  ];
  for (const candidate of rejected) {
    assert.equal(safeExternalHttpsUrl(candidate), null, String(candidate));
  }
});

test('external navigation rejects parser-normalized control characters and host confusion', () => {
  assert.equal(safeExternalHttpsUrl('https://exa\nmple.com/source'), null);
  assert.equal(safeExternalHttpsUrl('https://evil-example.com/source', {
    allowedHosts: ['example.com'],
    allowSubdomains: true,
  }), null);
  assert.equal(safeExternalHttpsUrl('https://example.com.evil.test/source', {
    allowedHosts: ['example.com'],
    allowSubdomains: true,
  }), null);
});
