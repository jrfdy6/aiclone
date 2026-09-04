const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const component = fs.readFileSync(path.join(__dirname, '../app/workspace/OpsStandupSummary.tsx'), 'utf8');
const workspace = fs.readFileSync(path.join(__dirname, '../app/workspace/WorkspaceClient.tsx'), 'utf8');

function compileModule(source, localRequire) {
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText;
  const moduleRef = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(localRequire, moduleRef, moduleRef.exports);
  return moduleRef.exports;
}

function compileOwnerTruth() {
  const source = fs.readFileSync(path.join(__dirname, '../lib/ops-owner-truth.ts'), 'utf8');
  return compileModule(source, (id) => {
    if (id === '@/lib/display-privacy') return { normalizeDisplayText: (value) => value };
    throw new Error(`Unexpected owner-truth dependency: ${id}`);
  });
}

function compileDecisionProjection() {
  const source = fs.readFileSync(path.join(__dirname, '../lib/ops-canonical-decision.ts'), 'utf8');
  return compileModule(source, (id) => {
    throw new Error(`Unexpected decision dependency: ${id}`);
  });
}

function compileOpsSummaryComponent() {
  const ownerTruth = compileOwnerTruth();
  const decisionProjection = compileDecisionProjection();
  return compileModule(component, (id) => {
    if (id === 'react' || id === 'react/jsx-runtime') return require(id);
    if (id === 'next/link') {
      return {
        __esModule: true,
        default: ({ children, href, ...props }) => React.createElement('a', { href, ...props }, children),
      };
    }
    if (id === '@/lib/control-api') return { controlApiGet: async () => ({}) };
    if (id === '@/lib/display-privacy') {
      return {
        safeExternalHttpsUrl: (value) => typeof value === 'string' && value.startsWith('https://') ? value : null,
      };
    }
    if (id === '@/lib/ops-canonical-decision') return decisionProjection;
    if (id === '@/lib/ops-owner-truth') return ownerTruth;
    throw new Error(`Unexpected Ops summary dependency: ${id}`);
  });
}

function goal(name) {
  return {
    schema_version: 'workspace_goal_contract/v1',
    goal: `${name} canonical owner goal.`,
    progress_signals: [`One verified ${name} progress signal.`],
    phase_gate: `${name} completion gate.`,
    no_action_trigger: `${name} evidence changes.`,
  };
}

function projectionFixture() {
  const keys = [
    ['agc', 'AGC'],
    ['ai-swag-store', 'AI Swag Store'],
    ['easyoutfitapp', 'Easy Outfit App'],
    ['fusion-os', 'Fusion OS'],
    ['work-life-tools', 'Work Life Tools'],
  ];
  return {
    schema_version: 'ops_standup_summary_conclusion/v3',
    state: 'degraded',
    cycle_date: '2026-09-03',
    observed_at: '2026-09-03T10:15:00Z',
    ops_conclusion_attempt_number: 1,
    workspace_updates: [
      ...keys.map(([workspace_key, display_name]) => ({ workspace_key, display_name, state: 'returned' })),
      { workspace_key: 'feezie-os', display_name: 'FEEZIE OS', state: 'missing', summary: 'No conclusion receipt received.' },
    ],
    workspace_recursion: keys.map(([workspace_key, display_name], index) => ({
      workspace_key,
      display_name,
      goal: goal(display_name),
      changes_since_prior: index === 0
        ? [{
          summary: 'Workspace cycle plan (no meeting held): generic internal plumbing detail that should not lead.',
          commitment: 'Qualified one GDIT opportunity against the existing proof boundary.',
        }]
        : [{ summary: `Verified one bounded ${display_name} change.` }],
      system_decisions: [],
      actions_taken: [{ summary: `Evaluated the current ${display_name} evidence.` }],
      completed_work: [],
      failed_work: [],
      carried_forward: [{ summary: `Retained the prior ${display_name} PM state.` }],
      owner_decisions: [],
      blocked: [],
      no_action: [],
      recommendations: [{ summary: `Review the bounded ${display_name} result when its evidence changes.` }],
      reference_only: [{ summary: '[private-workspace-context]', ref: 'coordination-record:record' }],
      next_cycle_inputs: [{ summary: `The next Dream cycle consumes the accepted ${display_name} conclusion.` }],
      recommendation_resolutions: [],
    })),
    owner_calls: [{ summary: 'Recovery verification requires attention.' }],
    canonical_decisions: [
      {
        title: 'Confirm the recovery gate',
        status: 'open',
        state_version: 2,
      },
    ],
    recommended_next_actions: [{ summary: 'Repair the missing FEEZIE conclusion through the governed cycle.' }],
    shared_ops_reconciliation: {
      display_name: 'Executive Standup',
      role: 'portfolio_reconciler',
      summary: 'Reconciled five of six project conclusions.',
      actions_taken: [{ summary: 'Reconciled the five accepted project conclusions without executing project work.' }],
      recommendations: [{ summary: 'Repair the missing project handoff.' }],
      next_cycle_inputs: [{ summary: 'The next Dream cycle consumes only accepted workspace conclusions.' }],
    },
    supporting_evidence_links: [{ title: 'Bounded evidence', url: 'https://example.com/evidence' }],
    ai_clone_process_updates: { memory_readiness: { status: 'ready' } },
  };
}

function goalProjectionFixture() {
  const keys = [
    ['feezie-os', 'FEEZIE OS'],
    ['fusion-os', 'Fusion OS'],
    ['easyoutfitapp', 'Easy Outfit App'],
    ['ai-swag-store', 'AI Swag Store'],
    ['agc', 'AGC'],
    ['work-life-tools', 'Work Life Tools'],
  ];
  return {
    schema_version: 'ops_workspace_goal_projection/v1',
    state: 'ready',
    workspaces: keys.map(([workspace_key, display_name]) => ({
      workspace_key,
      display_name,
      goal: goal(display_name),
    })),
  };
}

test('workspace uses the existing bounded projection and scopes it to FEEZIE', () => {
  assert.match(workspace, /<OpsStandupSummary workspaceKey="feezie-os" \/>/);
  assert.match(component, /\/api\/workspace\/ops-standup/);
  assert.match(component, /\/api\/workspace\/ops-workspace-goals/);
  assert.match(component, /projectWorkspaceOwnerTruth\(data, workspaceKey, goalProjection\)/);
  assert.match(component, /projection !== undefined/);
  assert.match(component, /goalProjection !== undefined/);
});

test('portfolio renders one bounded status per project without the recursive data dump', () => {
  const { default: OpsStandupSummary } = compileOpsSummaryComponent();
  const html = renderToStaticMarkup(React.createElement(OpsStandupSummary, {
    projection: projectionFixture(),
  }));

  assert.match(html, /5 of 6 workspace conclusions returned/);
  assert.match(html, /FEEZIE OS/);
  assert.match(html, /AGC canonical owner goal/);
  assert.match(html, /Needs your decision/);
  assert.match(html, /Needs your attention/);
  assert.match(html, /What remains healthy/);
  assert.match(html, /Next Dream consumes/);
  assert.match(html, /Supporting cycle evidence/);
  assert.doesNotMatch(html, /generic internal plumbing detail/);
  assert.doesNotMatch(html, /participant_receipt_unavailable|private-workspace-context|coordination-record|workspace key|reason codes/i);
  assert.doesNotMatch(component, /WorkspaceRecursionList|JSON\.stringify\(data\.endpoint_and_subsystem_health/);
});

test('selected workspace renders the canonical goal and current cycle truth only', () => {
  const { default: OpsStandupSummary } = compileOpsSummaryComponent();
  const html = renderToStaticMarkup(React.createElement(OpsStandupSummary, {
    projection: projectionFixture(),
    workspaceKey: 'agc',
  }));

  assert.match(html, /AGC canonical owner goal/);
  assert.match(html, /Qualified one GDIT opportunity/);
  assert.match(html, /Evaluated the current AGC evidence/);
  assert.match(html, /Retained the prior AGC PM state/);
  assert.match(html, /Open AGC in Ops/);
  assert.doesNotMatch(html, /AI Swag Store canonical owner goal|generic internal plumbing detail/);
});

test('missing workspace remains visibly blocked without inventing a goal or success', () => {
  const { default: OpsStandupSummary } = compileOpsSummaryComponent();
  const html = renderToStaticMarkup(React.createElement(OpsStandupSummary, {
    projection: projectionFixture(),
    workspaceKey: 'feezie-os',
  }));

  assert.match(html, /FEEZIE OS did not return a current conclusion receipt/);
  assert.match(html, /The system is not treating this as a successful cycle/);
  assert.match(html, /canonical goal is unavailable/i);
  assert.match(html, /prior accepted FEEZIE OS truth/i);
  assert.doesNotMatch(html, /Ready\. Every required|Current\. The workspace returned/);
});

test('missing cycle conclusion still renders its independently projected canonical goal', () => {
  const { default: OpsStandupSummary } = compileOpsSummaryComponent();
  const html = renderToStaticMarkup(React.createElement(OpsStandupSummary, {
    projection: projectionFixture(),
    goalProjection: goalProjectionFixture(),
    workspaceKey: 'feezie-os',
  }));

  assert.match(html, /FEEZIE OS canonical owner goal/);
  assert.match(html, /FEEZIE OS did not return a current conclusion receipt/);
  assert.match(html, /The system is not treating this as a successful cycle/);
  assert.doesNotMatch(html, /canonical goal is unavailable/i);
  assert.doesNotMatch(html, /Ready\. Every required|Current\. The workspace returned/);
});

test('Shared Ops remains a read-only reconciler, not a seventh project workspace', () => {
  const { SharedOpsReconciliationSummary } = compileOpsSummaryComponent();
  const html = renderToStaticMarkup(React.createElement(SharedOpsReconciliationSummary, {
    summary: projectionFixture().shared_ops_reconciliation,
  }));

  assert.match(html, /Shared Ops reconciliation/);
  assert.match(html, /data-shared-ops-role="portfolio_reconciler"/);
  assert.match(html, /read-only portfolio reconciliation/i);
  assert.match(html, /does not execute project work or become a seventh project workspace/);
  assert.match(html, /AI Clone did/);
  assert.match(html, /Recommendation/);
  assert.match(html, /Next Dream/);
});

test('canonical decisions expose only bounded owner-facing fields', () => {
  const { opsCanonicalDecisionDisplay } = compileDecisionProjection();
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
});
