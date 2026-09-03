const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../lib/ops-owner-truth.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleRef = { exports: {} };
new Function('require', 'module', 'exports', compiled)((id) => {
  if (id === '@/lib/display-privacy') return { normalizeDisplayText: (value) => value };
  throw new Error(`Unexpected owner-truth dependency: ${id}`);
}, moduleRef, moduleRef.exports);

const {
  ownerItemText,
  projectOpsWorkspaceGoals,
  projectPortfolioOwnerTruth,
  projectWorkspaceOwnerTruth,
} = moduleRef.exports;

function validGoal(name = 'AGC') {
  return {
    schema_version: 'workspace_goal_contract/v1',
    goal: `${name} canonical goal`,
    progress_signals: [`${name} verified progress`],
    phase_gate: `${name} completion gate`,
    no_action_trigger: `${name} evidence changes`,
  };
}

function baseProjection() {
  return {
    schema_version: 'ops_standup_summary_conclusion/v3',
    state: 'degraded',
    workspace_updates: [
      { workspace_key: 'agc', display_name: 'AGC', state: 'returned' },
      { workspace_key: 'feezie-os', display_name: 'FEEZIE OS', state: 'missing', summary: 'No conclusion receipt received.' },
    ],
    workspace_recursion: [
      {
        workspace_key: 'agc',
        display_name: 'AGC',
        goal: validGoal(),
        changes_since_prior: [{
          summary: 'Workspace cycle plan (no meeting held): generic internal payload.',
          commitment: 'Qualified one market signal against the canonical proof boundary.',
        }],
        system_decisions: [],
        actions_taken: [{ summary: 'Completed the bounded internal qualification.' }],
        completed_work: [{ summary: 'Qualification receipt stored.' }],
        failed_work: [],
        carried_forward: [],
        owner_decisions: [],
        blocked: [{ summary: 'participant_receipt_unavailable', reason_code: 'participant_receipt_unavailable' }],
        no_action: [],
        recommendations: [],
        reference_only: [{ summary: '[private-workspace-context]', ref: 'coordination-record:record' }],
        next_cycle_inputs: [{ summary: 'Consume the failed handoff as a completed update.' }],
        recommendation_resolutions: [
          {
            title: 'Prepare the internal qualification',
            state: 'executed_automatically',
            explanation: 'A verified internal result exists.',
            future_trigger: 'Owner review is requested.',
          },
        ],
      },
    ],
    owner_calls: [{ summary: 'Recovery verification requires attention.' }],
    canonical_decisions: [{ title: 'Choose the recovery policy', status: 'open' }],
    recommended_next_actions: [{ summary: 'Repair the governed handoff.' }],
  };
}

function goalProjection() {
  return {
    schema_version: 'ops_workspace_goal_projection/v1',
    state: 'ready',
    workspaces: [
      { workspace_key: 'agc', display_name: 'AGC', goal: validGoal('AGC') },
      { workspace_key: 'feezie-os', display_name: 'FEEZIE OS', goal: validGoal('FEEZIE OS') },
    ],
  };
}

test('one shared projection validates the goal contract before exposing it', () => {
  const projection = baseProjection();
  const goals = projectOpsWorkspaceGoals(projection);
  assert.deepEqual(goals.get('agc'), {
    schemaVersion: 'workspace_goal_contract/v1',
    goal: 'AGC canonical goal',
    progressSignals: ['AGC verified progress'],
    phaseGate: 'AGC completion gate',
    noActionTrigger: 'AGC evidence changes',
  });

  projection.workspace_recursion[0].goal = {
    ...validGoal(),
    schema_version: 'workspace_goal_contract/v999',
  };
  assert.equal(projectOpsWorkspaceGoals(projection).size, 0);
  const invalidTruth = projectWorkspaceOwnerTruth(projection, 'agc');
  assert.equal(invalidTruth.goal, null);
  assert.equal(invalidTruth.state, 'blocked', 'the existing participant failure remains the dominant state');
});

test('a malformed goal contract cannot be presented as a healthy workspace', () => {
  const projection = baseProjection();
  projection.workspace_recursion[0].blocked = [];
  projection.workspace_recursion[0].goal = { schema_version: 'workspace_goal_contract/v1' };
  const truth = projectWorkspaceOwnerTruth(projection, 'agc');
  assert.equal(truth.state, 'degraded');
  assert.match(truth.currentState, /goal contract is unavailable or malformed/i);
  assert.match(truth.affected, /goal, progress criteria, phase gate, and no-action trigger/i);
});

test('meaningful commitment is surfaced instead of generic cycle-planning prose', () => {
  const truth = projectWorkspaceOwnerTruth(baseProjection(), 'agc');
  assert.equal(truth.changes[0], 'Qualified one market signal against the canonical proof boundary.');
  assert.doesNotMatch(String(truth.changes), /generic internal payload/);
});

test('failed participant handoff is translated and cannot become next-Dream success', () => {
  const truth = projectWorkspaceOwnerTruth(baseProjection(), 'agc');
  assert.equal(truth.state, 'blocked');
  assert.match(truth.blockers[0], /did not receive every required signed participant receipt/i);
  assert.match(truth.nextDream[0], /will not consume this failed handoff as a completed update/i);
  assert.doesNotMatch(JSON.stringify(truth), /participant_receipt_unavailable|private-workspace-context|coordination-record/);
});

test('missing workspace remains distinct from an empty or healthy result', () => {
  const truth = projectWorkspaceOwnerTruth(baseProjection(), 'feezie-os');
  assert.equal(truth.hasCurrentConclusion, false);
  assert.equal(truth.state, 'blocked');
  assert.equal(truth.goal, null);
  assert.match(truth.currentState, /not treating this as a successful cycle/i);
  assert.match(truth.remainsHealthy, /previously accepted FEEZIE OS records/i);
});

test('cycle-independent goal authority survives a missing workspace conclusion', () => {
  const truth = projectWorkspaceOwnerTruth(
    baseProjection(),
    'feezie-os',
    goalProjection(),
  );

  assert.equal(truth.hasCurrentConclusion, false);
  assert.equal(truth.state, 'blocked');
  assert.equal(truth.goal, 'FEEZIE OS canonical goal');
  assert.deepEqual(truth.progressSignals, ['FEEZIE OS verified progress']);
  assert.match(truth.remainsHealthy, /canonical goal/i);
  assert.match(truth.currentState, /not treating this as a successful cycle/i);
});

test('Shared Ops reuses its reconciler goal without becoming project seven', () => {
  const projection = baseProjection();
  projection.shared_ops_reconciliation = {
    role: 'portfolio_reconciler',
    goal: validGoal('Shared Ops'),
  };

  const goals = projectOpsWorkspaceGoals(projection);
  const portfolio = projectPortfolioOwnerTruth(projection);

  assert.equal(goals.get('shared_ops').goal, 'Shared Ops canonical goal');
  assert.equal(portfolio.workspaces.length, 2);
  assert.equal(portfolio.workspaces.some((item) => item.workspaceKey === 'shared_ops'), false);
});

test('portfolio separates open decisions from non-decision owner attention', () => {
  const truth = projectPortfolioOwnerTruth(baseProjection());
  assert.deepEqual(truth.ownerDecisions, ['Choose the recovery policy']);
  assert.deepEqual(truth.attention, ['Recovery verification requires attention.']);
  assert.match(truth.whatChanged, /1 of 2 workspace conclusions returned/i);
  assert.match(truth.whatChanged, /FEEZIE OS did not return/i);
  assert.equal(truth.workspaces.length, 2);
  assert.match(truth.remainsHealthy, /1 bounded workspace report remains readable/i);
  assert.match(truth.remainsHealthy, /Of those, 0 are accepted as current conclusions/i);
});

test('portfolio counts all independently projected goals without inflating cycle success', () => {
  const truth = projectPortfolioOwnerTruth(baseProjection(), [], goalProjection());

  assert.equal(truth.workspaces.length, 2);
  assert.match(truth.remainsHealthy, /2 governed workspace goals/i);
  assert.match(truth.remainsHealthy, /1 bounded workspace report remains readable/i);
  assert.match(truth.remainsHealthy, /Of those, 0 are accepted as current conclusions/i);
});

test('a contradictory ready projection cannot erase a blocked workspace', () => {
  const projection = baseProjection();
  projection.state = 'ready';
  const truth = projectPortfolioOwnerTruth(projection);
  assert.equal(truth.state, 'degraded');
  assert.match(truth.currentState, /top-level conclusion says ready/i);
  assert.doesNotMatch(truth.currentState, /^Ready\./);
});

test('recommendation resolution states are translated into owner-facing outcomes', () => {
  const truth = projectWorkspaceOwnerTruth(baseProjection(), 'agc');
  assert.match(truth.recommendationResolutions[0], /completed through the authorized internal lane/i);
  assert.match(truth.recommendationResolutions[0], /A verified internal result exists/i);
  assert.match(truth.recommendationResolutions[0], /Reevaluate when: Owner review is requested/i);
  assert.doesNotMatch(truth.recommendationResolutions[0], /executed_automatically/);
});

test('raw private placeholders remain bounded even when supplied as item summaries', () => {
  assert.match(ownerItemText({ summary: '[private-workspace-context]' }, 'AGC'), /confined to its authorized workspace lane/i);
  assert.doesNotMatch(ownerItemText({ summary: '[private-workspace-context]' }, 'AGC'), /private-workspace-context/);
});
