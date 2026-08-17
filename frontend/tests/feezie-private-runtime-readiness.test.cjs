const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const frontendRoot = path.join(__dirname, '..');
const statusSource = fs.readFileSync(
  path.join(frontendRoot, 'app', 'workspace', 'FeeziePrivateRuntimeStatus.tsx'),
  'utf8',
);
const workspaceSource = fs.readFileSync(
  path.join(frontendRoot, 'app', 'workspace', 'WorkspaceClient.tsx'),
  'utf8',
);
const postingSource = fs.readFileSync(
  path.join(frontendRoot, 'app', 'workspace', 'posting', 'page.tsx'),
  'utf8',
);

const compiledStatus = ts.transpileModule(statusSource, {
  compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedStatus = { exports: {} };
new Function('module', 'exports', 'require', compiledStatus)(
  loadedStatus,
  loadedStatus.exports,
  require,
);
const { isFeeziePrivateRuntimeContextReady } = loadedStatus.exports;

function readyStatus() {
  return {
    schema_version: 'feezie_private_runtime_context_status/v1',
    checked_at: '2026-08-16T12:00:00Z',
    context_generated_at: '2026-08-16T11:00:00Z',
    age_seconds: 3600,
    stale_after_seconds: 129600,
    state: 'ready',
    ready: true,
    reason_codes: [],
    persona_canon: { ready: true, count: 2 },
    approved_voice_examples: { ready: true, count: 1 },
    anonymized_proof: { ready: true, count: 3 },
    source_grounding: {
      ready: true,
      strategy_contract_present: true,
      content_integrity_valid: true,
    },
    data_policy: {
      aggregate_only: true,
      private_context_included: false,
    },
  };
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

test('private-runtime readiness accepts only a complete, internally consistent v1 aggregate receipt', () => {
  assert.equal(isFeeziePrivateRuntimeContextReady(readyStatus()), true);

  const invalidCases = [
    ['missing receipt', () => null],
    ['wrong schema', (value) => { value.schema_version = 'feezie_private_runtime_context_status/v2'; }],
    ['missing check time', (value) => { delete value.checked_at; }],
    ['naive check time', (value) => { value.checked_at = '2026-08-16T12:00:00'; }],
    ['missing context time', (value) => { value.context_generated_at = null; }],
    ['missing age', (value) => { value.age_seconds = null; }],
    ['future beyond skew', (value) => { value.age_seconds = -301; }],
    ['stale age', (value) => { value.age_seconds = 129601; }],
    ['fractional age', (value) => { value.age_seconds = 1.5; }],
    ['age disagrees with source times', (value) => { value.age_seconds = 7200; }],
    ['wrong stale threshold', (value) => { value.stale_after_seconds = 86400; }],
    ['degraded state with ready boolean', (value) => { value.state = 'degraded'; }],
    ['ready state with false boolean', (value) => { value.ready = false; }],
    ['missing reason codes', (value) => { delete value.reason_codes; }],
    ['nonempty reason codes', (value) => { value.reason_codes = ['facet_missing']; }],
    ['missing data policy', (value) => { delete value.data_policy; }],
    ['nonaggregate policy', (value) => { value.data_policy.aggregate_only = false; }],
    ['private context included', (value) => { value.data_policy.private_context_included = true; }],
    ['missing persona facet', (value) => { delete value.persona_canon; }],
    ['persona facet not ready', (value) => { value.persona_canon.ready = false; }],
    ['voice facet not ready', (value) => { value.approved_voice_examples.ready = false; }],
    ['proof facet not ready', (value) => { value.anonymized_proof.ready = false; }],
    ['zero persona count', (value) => { value.persona_canon.count = 0; }],
    ['negative voice count', (value) => { value.approved_voice_examples.count = -1; }],
    ['fractional proof count', (value) => { value.anonymized_proof.count = 1.5; }],
    ['string count', (value) => { value.persona_canon.count = '2'; }],
    ['missing source facet', (value) => { delete value.source_grounding; }],
    ['source facet not ready', (value) => { value.source_grounding.ready = false; }],
    ['strategy contract missing', (value) => { value.source_grounding.strategy_contract_present = false; }],
    ['content integrity invalid', (value) => { value.source_grounding.content_integrity_valid = false; }],
  ];

  for (const [label, mutate] of invalidCases) {
    const candidate = clone(readyStatus());
    const replacement = mutate(candidate);
    assert.equal(
      isFeeziePrivateRuntimeContextReady(replacement === undefined ? candidate : replacement),
      false,
      label,
    );
  }
});

test('both FEEZIE post queues fail closed while unrelated comment and ingest actions stay available', () => {
  assert.match(statusSource, /export function isFeeziePrivateRuntimeContextReady/);
  assert.match(statusSource, /FEEZIE generation stays closed until private runtime context is fully ready\./);

  for (const source of [workspaceSource, postingSource]) {
    assert.match(source, /isFeeziePrivateRuntimeContextReady/);
    assert.match(source, /const feezieGenerationReady =/);
    assert.match(source, /if \(!feezieGenerationReady\) \{\s*throw new Error\('FEEZIE generation stays closed until private runtime context is fully ready\.'\);/s);
    assert.match(source, /disabled=\{!feezieGenerationReady \|\|/);
  }

  assert.match(postingSource, /privateRuntimeLoadState === 'live'\s*&& isFeeziePrivateRuntimeContextReady\(privateRuntimeStatus\)/s);
  assert.match(workspaceSource, /snapshotState === 'live'\s*&& snapshotError === null\s*&& isFeeziePrivateRuntimeContextReady/s);
  assert.match(postingSource, /initialQuery\.mode === 'comment'[\s\S]*?handleGenerateComment\(\);[\s\S]*?if \(!feezieGenerationReady\)/);
  assert.match(postingSource, /onClick=\{\(\) => void handleGenerateComment\(\)\} disabled=\{commentLoading\}/);
  assert.match(workspaceSource, /onClick=\{\(\) => void ingestSignal\(\)\} disabled=\{ingestLoading\}/);
});
