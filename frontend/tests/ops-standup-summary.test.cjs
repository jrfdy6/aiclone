const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const component = fs.readFileSync(path.join(__dirname, '../app/workspace/OpsStandupSummary.tsx'), 'utf8');
const workspace = fs.readFileSync(path.join(__dirname, '../app/workspace/WorkspaceClient.tsx'), 'utf8');
const decisionProjectionSource = fs.readFileSync(path.join(__dirname, '../lib/ops-canonical-decision.ts'), 'utf8');
const decisionProjectionCompiled = ts.transpileModule(decisionProjectionSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const decisionProjectionModule = { exports: {} };
new Function('module', 'exports', decisionProjectionCompiled)(
  decisionProjectionModule,
  decisionProjectionModule.exports,
);
const { opsCanonicalDecisionDisplay } = decisionProjectionModule.exports;

test('workspace renders the canonical final Ops artifact from its bounded API', () => {
  assert.match(workspace, /<OpsStandupSummary \/>/);
  assert.match(component, /Ops Standup Summary and Conclusion/);
  assert.match(component, /\/api\/workspace\/ops-standup/);
});

test('Ops panel exposes required decisions, owner calls, health, and degraded state', () => {
  const itemListSections = ['Workspace updates', 'Urgent escalations', 'Owner calls', 'Blockers', 'Work underway', 'Completed work', 'Workspace decisions', 'Ops decisions', 'Supporting evidence'];
  for (const title of itemListSections) {
    assert.equal(component.match(new RegExp(`<ItemList title="${title}"`, 'g'))?.length, 1, `${title} must render exactly once`);
  }
  for (const required of ['AI Clone process updates', 'Recommended next actions', 'Endpoint and subsystem health', 'Degraded system']) assert.match(component, new RegExp(required));
  assert.equal(component.match(/<ProcessUpdates updates=/g)?.length, 1, 'process updates must render exactly once');
  assert.equal(component.match(/<CanonicalDecisionList items=/g)?.length, 1, 'canonical decisions must render exactly once');
  assert.match(component, /role="alert"/);
  assert.match(component, /evidenceUrl/);
  assert.match(component, /target="_blank"/);
});

test('canonical decisions show only bounded status, version, and resolved choice beneath the title', () => {
  assert.match(component, /<CanonicalDecisionList items=\{data\.canonical_decisions\} \/>/);
  assert.match(component, /Resolved choice:/);
  assert.doesNotMatch(component, /<ItemList title="Canonical decisions"/);

  assert.deepEqual(opsCanonicalDecisionDisplay({
    title: 'Choose the beta cutover',
    status: 'resolved',
    state_version: 4,
    resolution: {
      choice: 'Proceed with the bounded private beta.',
      private_notes: 'must never render',
      transcript: 'must never render',
    },
    payload: { opaque_value: 'must never render' },
  }), {
    title: 'Choose the beta cutover',
    status: 'resolved',
    stateVersion: 4,
    resolvedChoice: 'Proceed with the bounded private beta.',
  });
  assert.deepEqual(opsCanonicalDecisionDisplay({
    title: 'Open owner call',
    status: 'open',
    state_version: 1,
    resolution: { choice: 'Premature nested value', private_notes: 'hidden' },
  }), {
    title: 'Open owner call',
    status: 'open',
    stateVersion: 1,
    resolvedChoice: null,
  });
});
