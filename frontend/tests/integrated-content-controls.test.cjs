const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const sourcePath = path.join(__dirname, '..', 'lib', 'integrated-content-controls.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleValue = { exports: {} };
new Function('module', 'exports', compiled)(moduleValue, moduleValue.exports);
const {
  buildVariantRequestControls,
  initializeVariantControls,
  updateVariantControl,
} = moduleValue.exports;

const options = [
  { key: 'hook', label: 'Hook', values: ['direct', 'question'], default: 'direct' },
  { key: 'length', label: 'Length', values: ['short', 'medium', 'long'], default: 'medium' },
  { key: 'audience_emphasis', label: 'Audience emphasis', values: ['AI systems operators'], default: '' },
  { key: 'evidence_emphasis', label: 'Evidence emphasis', values: ['source claim'], default: '' },
];

test('owner interaction changes only controls the canonical projection made relevant', () => {
  const initial = initializeVariantControls(options, { call_to_action: 'invented', hook: 'unsupported' });
  assert.deepEqual(initial, {
    hook: 'direct',
    length: 'medium',
    audience_emphasis: '',
    evidence_emphasis: '',
  });

  const audience = updateVariantControl(options, initial, 'audience_emphasis', 'AI systems operators');
  const evidence = updateVariantControl(options, audience, 'evidence_emphasis', 'source claim');
  assert.deepEqual(buildVariantRequestControls(options, evidence, 'linkedin'), {
    hook: 'direct',
    length: 'medium',
    audience_emphasis: 'AI systems operators',
    evidence_emphasis: 'source claim',
  });
});

test('unsupported or contextually absent controls fail before a request is built', () => {
  assert.throws(
    () => updateVariantControl(options, initializeVariantControls(options), 'call_to_action', 'publish now'),
    /not available/,
  );
  const cleared = { hook: '', length: '', audience_emphasis: '', evidence_emphasis: '' };
  assert.deepEqual(buildVariantRequestControls(options, cleared, 'instagram'), { hook: 'direct', length: 'short' });
});

test('Instagram preserves an explicit medium or long length selection', () => {
  const medium = initializeVariantControls(options);
  assert.equal(buildVariantRequestControls(options, medium, 'instagram').length, 'medium');
  const long = updateVariantControl(options, medium, 'length', 'long');
  assert.equal(buildVariantRequestControls(options, long, 'instagram').length, 'long');
});
