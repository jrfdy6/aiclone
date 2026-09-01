const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'lib', 'canonical-decisions.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleValue = { exports: {} };
new Function('module', 'exports', compiled)(moduleValue, moduleValue.exports);
const {
  PM_OWNER_DECISION_CHOICES,
  canonicalDecisionActionEndpoint,
  canonicalDecisionActionRequest,
  isAutomaticSystemDecisionType,
  isCanonicalOwnerDecisionType,
  reconcileCanonicalDecisionViews,
  reconcileCanonicalOwnerDecisionViews,
  waitForCanonicalDecisionJob,
} = moduleValue.exports;

function decision(overrides = {}) {
  return {
    decision_id: 'decision-1',
    decision_type: 'owner_call',
    title: 'Choose the cutover',
    status: 'open',
    state_version: 1,
    interaction_mode: 'simple',
    route: 'ops',
    resolution: {},
    session_ref: null,
    updated_at: '2026-08-20T12:00:00Z',
    links: [{ surface: 'ops', external_ref: 'decision:decision-1' }],
    ...overrides,
  };
}

test('the same canonical decision in Content and Ops becomes one owner row', () => {
  const content = decision();
  const ops = decision();
  const rows = reconcileCanonicalDecisionViews([content], [ops]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].decision_id, 'decision-1');
  assert.deepEqual(rows[0].visible_in, ['content', 'ops']);
  assert.equal(rows[0].projection_conflict, false);
});

test('a stale or missing projection is visible and cannot masquerade as synchronized', () => {
  const stale = reconcileCanonicalDecisionViews(
    [decision({ state_version: 2, status: 'in_session' })],
    [decision({ state_version: 1, status: 'open' })],
  );
  assert.equal(stale[0].state_version, 2);
  assert.equal(stale[0].projection_conflict, true);
  assert.equal(reconcileCanonicalDecisionViews([decision()], [])[0].projection_conflict, true);
});

test('FEEZIE async system decisions retain their type in neutral truth but never enter Owner Decisions', () => {
  const openSystemDecision = decision({
    decision_id: 'feezie-system-open',
    decision_type: 'standup_async_system_decision',
    title: 'Admit Neo signed async contribution',
    route: 'feezie-os',
  });
  const resolvedSystemDecision = decision({
    decision_id: 'feezie-system-resolved',
    decision_type: 'standup_async_system_decision',
    title: 'Admit Yoda signed async contribution',
    route: 'feezie-os',
    status: 'resolved',
    state_version: 2,
    resolution: { choice: 'admit_to_existing_pm_and_cycle_authorities' },
  });
  const existingOwnerType = decision({
    decision_id: 'existing-architecture-call',
    decision_type: 'architecture',
  });

  const neutral = reconcileCanonicalDecisionViews(
    [openSystemDecision, resolvedSystemDecision, existingOwnerType],
    [openSystemDecision, resolvedSystemDecision, existingOwnerType],
  );
  assert.deepEqual(
    neutral.map((item) => item.decision_type),
    ['architecture', 'standup_async_system_decision', 'standup_async_system_decision'],
  );
  assert.equal(isAutomaticSystemDecisionType('standup_async_system_decision'), true);
  assert.equal(isAutomaticSystemDecisionType('owner_call'), false);
  assert.equal(isCanonicalOwnerDecisionType('architecture'), true);
  assert.equal(isCanonicalOwnerDecisionType('future_unknown_decision'), false);

  const ownerRows = reconcileCanonicalOwnerDecisionViews(
    [openSystemDecision, resolvedSystemDecision, existingOwnerType],
    [openSystemDecision, resolvedSystemDecision, existingOwnerType],
  );
  assert.deepEqual(ownerRows.map((item) => item.decision_id), ['existing-architecture-call']);
  assert.throws(
    () => canonicalDecisionActionRequest(openSystemDecision, 'resolve', 'owner override'),
    /read-only on the Owner Decisions surface/,
  );
});

test('unknown decision authority remains neutral and read-only rather than becoming an owner call', () => {
  const unknown = decision({
    decision_id: 'unknown-authority',
    decision_type: 'future_unknown_decision',
  });
  assert.equal(reconcileCanonicalDecisionViews([unknown], [unknown]).length, 1);
  assert.deepEqual(reconcileCanonicalOwnerDecisionViews([unknown], [unknown]), []);
  assert.throws(
    () => canonicalDecisionActionRequest(unknown, 'resolve', 'owner override'),
    /Unverified decision types are read-only/,
  );
});

test('a system type on either projection fails closed outside Owner Decisions', () => {
  const ownerProjection = decision({ decision_id: 'mixed-authority', decision_type: 'owner_call' });
  const systemProjection = decision({
    decision_id: 'mixed-authority',
    decision_type: 'standup_async_system_decision',
  });
  const neutral = reconcileCanonicalDecisionViews([ownerProjection], [systemProjection]);
  assert.equal(neutral[0].projection_conflict, true);
  assert.deepEqual(
    reconcileCanonicalOwnerDecisionViews([ownerProjection], [systemProjection]),
    [],
  );
});

test('simple calls resolve inline while complex calls require one shared session', () => {
  assert.deepEqual(canonicalDecisionActionRequest(decision(), 'resolve', 'Approve controlled cutover'), {
    expected_version: 1,
    action: 'resolve',
    resolution: { choice: 'Approve controlled cutover' },
  });
  const complex = decision({ interaction_mode: 'complex' });
  assert.throws(() => canonicalDecisionActionRequest(complex, 'resolve', 'Approve'), /shared session/);
  assert.deepEqual(canonicalDecisionActionRequest(complex, 'begin_session'), {
    expected_version: 1,
    action: 'begin_session',
  });
  assert.deepEqual(
    canonicalDecisionActionRequest(decision({ interaction_mode: 'complex', status: 'in_session', state_version: 2 }), 'resolve', 'Approve'),
    { expected_version: 2, action: 'resolve', resolution: { choice: 'Approve' } },
  );
  assert.throws(() => canonicalDecisionActionRequest(decision({ status: 'resolved' }), 'block'), /Terminal/);
});

test('PM owner decisions expose only the three bounded outcomes while generic calls stay free-form', () => {
  const pmDecision = decision({
    decision_type: 'pm_owner_decision',
    title: 'Choose the linked PM outcome',
  });
  assert.deepEqual(PM_OWNER_DECISION_CHOICES.map((choice) => choice.value), [
    'approve_bounded_internal_action',
    'reject_recommendation',
    'retain_until_trigger',
  ]);
  assert.deepEqual(
    canonicalDecisionActionRequest(pmDecision, 'resolve', 'retain_until_trigger'),
    {
      expected_version: 1,
      action: 'resolve',
      resolution: { choice: 'retain_until_trigger' },
    },
  );
  assert.throws(
    () => canonicalDecisionActionRequest(pmDecision, 'resolve', 'do whatever seems best'),
    /bounded PM recommendation outcomes/,
  );
  assert.throws(
    () => canonicalDecisionActionRequest(pmDecision, 'cancel'),
    /bounded PM recommendation choice/,
  );
  assert.deepEqual(
    canonicalDecisionActionRequest(decision(), 'resolve', 'A genuinely free-form generic choice'),
    {
      expected_version: 1,
      action: 'resolve',
      resolution: { choice: 'A genuinely free-form generic choice' },
    },
  );
});

test('action endpoints encode canonical identity and exact jobs are polled to completion', async () => {
  assert.equal(
    canonicalDecisionActionEndpoint('decision/with spaces'),
    '/api/workspace/decisions/decision%2Fwith%20spaces/actions',
  );
  const states = ['queued', 'running', 'completed'];
  const status = await waitForCanonicalDecisionJob({
    receipt: { job_id: 'job-1', card_id: 'job-1' },
    readStatus: async () => ({ job_id: 'job-1', card_id: 'job-1', status: states.shift() }),
    sleep: async () => {},
    pollIntervalMs: 1,
    timeoutMs: 3,
  });
  assert.equal(status.status, 'completed');
  await assert.rejects(
    waitForCanonicalDecisionJob({
      receipt: { job_id: 'job-1' },
      readStatus: async () => ({ job_id: 'different-job', card_id: 'different-job', status: 'completed' }),
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 1,
    }),
    /exact queued action/,
  );
});

test('workspace exposes authenticated canonical create, session, resolve, and retry-safe controls', () => {
  const component = fs.readFileSync(path.join(root, 'app', 'workspace', 'OwnerDecisionSurface.tsx'), 'utf8');
  const workspace = fs.readFileSync(path.join(root, 'app', 'workspace', 'WorkspaceClient.tsx'), 'utf8');
  const ops = fs.readFileSync(path.join(root, 'app', 'workspace', 'OpsStandupSummary.tsx'), 'utf8');
  assert.match(workspace, /<OwnerDecisionSurface\s*\/>/);
  assert.match(component, /\/api\/workspace\/decisions/);
  assert.match(component, /Open shared decision session/);
  assert.match(component, /Resolve canonical decision/);
  assert.match(component, /Bounded PM outcome/);
  assert.match(component, /Apply bounded PM choice/);
  assert.match(source, /approve_bounded_internal_action/);
  assert.match(source, /reject_recommendation/);
  assert.match(source, /retain_until_trigger/);
  assert.match(component, /never publishes, messages, schedules, spends, promotes Persona canon, or mutates a platform/);
  assert.match(component, /expected_version|canonicalDecisionActionRequest/);
  assert.match(component, /Keep createRequestId stable/);
  assert.match(component, /projection_conflict/);
  assert.match(component, /controller_capabilities\?\.decision_resolution === true/);
  assert.match(component, /reconcileCanonicalOwnerDecisionViews/);
  assert.doesNotMatch(component, /reconcileCanonicalDecisionViews\(/);
  assert.match(component, /projectionReadIsCurrent\(content/);
  assert.match(component, /opsDecisionReadIsCurrent\(ops/);
  assert.match(component, /ops_standup_summary_conclusion\/v2/);
  assert.match(component, /ops_standup_summary_conclusion\/v1/);
  assert.match(component, /canonical_decision_projection_readiness\/v1/);
  assert.match(component, /clock_authority === 'ai_clone_utc'/);
  assert.match(component, /value="feezie-os"/);
  assert.match(component, /route: decisionRoute/);
  assert.match(component, /mutationGateRef\.current/);
  assert.match(component, /currentDecision\.state_version !== decision\.state_version/);
  assert.match(component, /This decision view is stale/);
  assert.match(component, /controlApiGet/);
  assert.match(component, /controlApiPost/);
  assert.match(component, /ownerSafeErrorMessage\(caught/);
  assert.doesNotMatch(component, /\bfetch\s*\(/);
  assert.match(component, /no publishing, messaging, or external communication occurs here/);
  assert.match(ops, /Canonical decisions/);
  assert.match(ops, /Canonical owner decisions were checked/);
  assert.match(ops, /AI Clone UTC/);
});

test('phone actions are synchronously claimed and buttons stay disabled for the exact pending job', () => {
  const component = fs.readFileSync(path.join(root, 'app', 'workspace', 'OwnerDecisionSurface.tsx'), 'utf8');
  assert.match(component, /createPendingRef\.current/);
  assert.match(component, /pendingDecisionIdsRef\.current\.has\(decision\.decision_id\)/);
  assert.match(component, /pendingDecisionIdsRef\.current\.add\(decision\.decision_id\)/);
  assert.match(component, /pendingDecisionIdsRef\.current\.delete\(decision\.decision_id\)/);
  assert.match(component, /setCreatePendingJob\(receipt\.job_id/);
  assert.match(component, /setPendingJobByDecisionId/);
  assert.match(component, /disabled=\{!controlsReady \|\| createPendingJob !== null\}/);
  assert.match(component, /disabled=\{decisionControlsDisabled\}/);
  assert.match(component, /aria-busy=\{Boolean\(decisionPendingJob\)\}/);
  assert.match(component, /Waiting for this exact signed decision job/);
  assert.match(component, /touchAction: 'manipulation'/);
});

test('failed decision-specific reads leave every mutation fail-closed without conflating unrelated Ops warnings', () => {
  const component = fs.readFileSync(path.join(root, 'app', 'workspace', 'OwnerDecisionSurface.tsx'), 'utf8');
  assert.match(component, /projection\.state === 'ready' \|\| projection\.state === 'empty'/);
  assert.match(component, /readiness\.state === 'ready'/);
  assert.match(component, /readiness\.blocking_reason_codes\.length === 0/);
  assert.match(component, /projection\.state === 'degraded'/);
  assert.match(component, /readReady: false,[\s\S]*controllerReady: false/);
  assert.match(component, /Content and Ops could not both be verified/);
  assert.match(component, /const controlsReady = mutationGate\.readReady && mutationGate\.controllerReady && !loading/);
  assert.match(component, /if \(!gate\.readReady \|\| !gate\.controllerReady\)/);
  assert.match(component, /!loading && mutationGate\.readReady && !decisions\.length/);
});
