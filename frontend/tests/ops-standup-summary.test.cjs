const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

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

function compileOpsSummaryComponent() {
  const compiled = ts.transpileModule(component, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText;
  const module = { exports: {} };
  const localRequire = (id) => {
    if (id === 'react' || id === 'react/jsx-runtime') return require(id);
    if (id === '@/lib/control-api') return { controlApiGet: async () => ({}) };
    if (id === '@/lib/display-privacy') return { normalizeDisplayText: (value) => value, safeExternalHttpsUrl: () => null };
    if (id === '@/lib/ops-canonical-decision') {
      return { opsCanonicalDecisionDisplay: () => ({ title: 'Decision', status: null, stateVersion: null, resolvedChoice: null }) };
    }
    throw new Error(`Unexpected Ops summary dependency: ${id}`);
  };
  new Function('require', 'module', 'exports', compiled)(localRequire, module, module.exports);
  return module.exports;
}

test('workspace renders the canonical final Ops artifact from its bounded API', () => {
  assert.match(workspace, /<OpsStandupSummary \/>/);
  assert.match(component, /Ops Standup Summary and Conclusion/);
  assert.match(component, /\/api\/workspace\/ops-standup/);
  assert.match(component, /conclusion attempt \$\{data\.ops_conclusion_attempt_number/);
});

test('Ops panel exposes required decisions, owner calls, health, and degraded state', () => {
  const itemListSections = ['Workspace updates', 'Urgent escalations', 'Owner calls', 'Blockers', 'Work underway', 'Completed work', 'Workspace decisions', 'Ops decisions', 'Supporting evidence'];
  for (const title of itemListSections) {
    assert.equal(component.match(new RegExp(`<ItemList title="${title}"`, 'g'))?.length, 1, `${title} must render exactly once`);
  }
  for (const required of ['AI Clone process updates', 'Recommended next actions', 'Endpoint and subsystem diagnostics are available in System', 'Portfolio conclusion degraded', 'What remains healthy', 'Next Dream consumes']) assert.match(component, new RegExp(required));
  assert.equal(component.match(/<ProcessUpdates updates=/g)?.length, 1, 'process updates must render exactly once');
  assert.equal(component.match(/<CanonicalDecisionList items=/g)?.length, 1, 'canonical decisions must render exactly once');
  assert.match(component, /role="alert"/);
  assert.match(component, /evidenceUrl/);
  assert.match(component, /target="_blank"/);
});

test('unrelated subsystem warnings remain visible while canonical decisions are ready', () => {
  assert.match(component, /data && data\.degraded_system_warnings\.length > 0/);
  assert.match(component, /data-ops-subsystem-warnings="visible"/);
  assert.match(component, /<strong>What is affected<\/strong>/);
  assert.match(component, /data\.degraded_system_warnings\.slice\(0, 5\)\.map/);
  assert.doesNotMatch(
    component,
    /\(data\.state === 'degraded' \|\| data\.state === 'error'\)[^?]+\?[^:]+data\.degraded_system_warnings/,
  );
  assert.match(component, /decision_readiness\?\.state === 'ready'/);
});

test('Ops panel renders bounded workspace recursion truth and structured recommendation resolutions', () => {
  assert.match(component, /type WorkspaceRecursion = \{/);
  assert.match(component, /display_name: string/);
  assert.match(component, /workspace_recursion: WorkspaceRecursion\[\]/);
  assert.match(component, /shared_ops_reconciliation\?: SharedOpsReconciliation \| null/);
  assert.match(component, /recommended_next_actions: Item\[\]/);
  assert.match(component, /<WorkspaceRecursionList items=\{data\.workspace_recursion \?\? \[\]\} \/>/);
  assert.match(component, /\{ownerText\(workspace\.display_name \|\| workspace\.workspace_key\)\}/);
  for (const label of [
    'Goal',
    'What changed',
    'AI Clone decided',
    'AI Clone did',
    'Completed',
    'Failed',
    'Carried forward',
    'Needs owner',
    'Blocked',
    'No eligible change',
    'AI Clone recommends',
    'Reference only',
    'Next-cycle input',
    'Recommendation resolution',
  ]) {
    assert.match(component, new RegExp(label));
  }
  assert.match(component, /title="No eligible change"[\s\S]*detailKeys=\{\['trigger'\]\}/);
  assert.match(component, /title="Recommendation resolution"[\s\S]*detailKeys=\{\['state', 'explanation', 'future_trigger'\]\}/);
  assert.match(component, /<ItemList title="Recommended next actions" items=\{data\.recommended_next_actions \?\? \[\]\}/);
  assert.doesNotMatch(component, /recommended_next_actions\.map\(\(item\) => <li key=\{item\}>/);
});

test('Shared Ops renders as a read-only reconciler summary, not a seventh project row', () => {
  const { SharedOpsReconciliationSummary } = compileOpsSummaryComponent();
  const html = renderToStaticMarkup(React.createElement(SharedOpsReconciliationSummary, {
    summary: {
      display_name: 'Executive Standup',
      role: 'portfolio_reconciler',
      summary: 'Reconciled all six project conclusions.',
      goal: { goal: 'Keep the active portfolio legible.' },
      evaluated: [{ summary: 'Six project conclusions.' }],
      system_decisions: [{ summary: 'Preserve project ownership.' }],
      actions_taken: [{ summary: 'Reconciled dependencies.' }],
      owner_calls: [],
      blocked: [],
      no_action: [],
      recommendations: [{ summary: 'Review one bounded conflict.' }],
      reference_only: [{ summary: 'Prior static plan.' }],
      next_cycle_inputs: [{ summary: 'Later Dream reads the receipt.' }],
    },
  }));

  assert.match(html, /Shared Ops reconciliation/);
  assert.match(html, /data-shared-ops-role="portfolio_reconciler"/);
  assert.match(html, /AI Clone recommends/);
  assert.match(html, /Reference only/);
  assert.match(html, /Next Dream consumes/);
  assert.match(html, /does not execute project work or become a seventh project workspace/);
  assert.doesNotMatch(html, /recursion-shared_ops/);
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
