const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const sourcePath = path.join(__dirname, '..', 'lib', 'executive-decisions.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const queueSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'ops', 'ExecutiveDecisionQueue.tsx'), 'utf8');
const opsSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loadedModule, loadedModule.exports, require);

const {
  executiveDecisionActionEndpoint,
  executiveDecisionCoverage,
  executableDecisionActions,
  normalizeExecutiveDecisionResponse,
  safeExecutiveContextHref,
} = loadedModule.exports;

test('redacts every executive decision field before display', () => {
  for (const field of [
    'decision.title',
    'decision.what_changed',
    'decision.why_it_matters',
    'decision.recommendation',
  ]) {
    assert.match(queueSource, new RegExp(`normalizeDisplayText\\(${field.replace('.', '\\.')}\\)`));
  }
  assert.match(queueSource, /normalizeDisplayText\(item\)/);
  assert.match(queueSource, /normalizeDisplayText\(feedback\)/);
  assert.match(queueSource, /normalizeDisplayText\(error\)/);
});

function decision(overrides = {}) {
  return {
    id: 'pm:card-123',
    dedupe_key: 'pm:card-123',
    source_type: 'pm',
    source_id: 'card-123',
    workspace_key: 'shared_ops',
    title: 'Approve the returned implementation',
    what_changed: 'The runner attached a verified result.',
    why_it_matters: 'The work is blocked in review.',
    recommendation: 'Approve and close it.',
    priority: 'critical',
    priority_score: 98,
    freshness: 'today',
    updated_at: '2026-07-20T12:00:00Z',
    evidence: ['Tests passed', 'Artifact attached'],
    context_href: '/ops?focus=pm&card_id=card-123',
    actions: [
      {
        id: 'approve',
        label: 'Approve',
        kind: 'delegate',
        method: 'POST',
        href: '/api/executive/decisions/pm%3Acard-123/actions/approve',
        requires_confirmation: true,
        requires_note: false,
      },
      {
        id: 'context',
        label: 'Open PM card',
        kind: 'open_context',
        method: 'GET',
        href: '/ops?focus=pm&card_id=card-123',
        requires_confirmation: false,
        requires_note: false,
      },
    ],
    ...overrides,
  };
}

test('normalizes ranked Today and All payloads without reordering them', () => {
  const first = decision();
  const second = decision({ id: 'standup:s-1', title: 'Review a standup exception', source_type: 'standup' });
  const payload = normalizeExecutiveDecisionResponse({
    generated_at: '2026-07-20T12:05:00Z',
    summary: { total_pending: 2, today_count: 1, verification_status: 'partial', verified_clear: false },
    today: [first],
    all_pending: [first, second],
    source_status: { pm: 'ok', standup: 'degraded' },
    source_errors: [{ source_type: 'standup', message: 'Only a partial standup window was available.' }],
  });

  assert.deepEqual(payload.today.map((item) => item.id), ['pm:card-123']);
  assert.deepEqual(payload.all_pending.map((item) => item.id), ['pm:card-123', 'standup:s-1']);
  assert.equal(payload.all_pending[0].priority, 'critical');
  assert.equal(payload.source_status.standup, 'degraded');
  assert.deepEqual(executiveDecisionCoverage(payload), {
    partial: true,
    failedSources: [],
    degradedSources: ['standup'],
  });
});

test('never treats missing or failed source coverage as a verified clear', () => {
  const missing = normalizeExecutiveDecisionResponse({ today: [], all_pending: [] });
  assert.equal(executiveDecisionCoverage(missing).partial, true);

  const failed = normalizeExecutiveDecisionResponse({
    summary: { verification_status: 'partial', verified_clear: false },
    today: [],
    all_pending: [],
    source_status: { pm: 'ok', email: 'error' },
    source_errors: [{ source_type: 'email', message: 'Inbox timed out.' }],
  });
  assert.deepEqual(executiveDecisionCoverage(failed).failedSources, ['email']);
});

test('exposes only confirmed POST delegates as direct Home actions', () => {
  const payload = normalizeExecutiveDecisionResponse({
    today: [decision({
      actions: [
        ...decision().actions,
        {
          id: 'unsafe-no-confirm',
          label: 'Unsafe delegate',
          kind: 'delegate',
          method: 'POST',
          href: '/api/executive/decisions/x/actions/y',
          requires_confirmation: false,
        },
        {
          id: 'unsafe-get',
          label: 'Unsafe GET',
          kind: 'delegate',
          method: 'GET',
          href: '/api/executive/decisions/x/actions/y',
          requires_confirmation: true,
          requires_note: false,
        },
        {
          id: 'requires-note',
          label: 'Return with note',
          kind: 'delegate',
          method: 'POST',
          href: '/api/executive/decisions/x/actions/return',
          requires_confirmation: true,
          requires_note: true,
        },
      ],
    })],
    all_pending: [],
    source_status: { pm: 'ok' },
    source_errors: [],
  });

  assert.deepEqual(executableDecisionActions(payload.today[0]).map((action) => action.id), ['approve']);
});

test('keeps navigation internal and action posts under authenticated API paths', () => {
  assert.equal(safeExecutiveContextHref('/brain?tab=persona&delta_id=d-1'), '/brain?tab=persona&delta_id=d-1');
  assert.equal(safeExecutiveContextHref('//example.com'), null);
  assert.equal(safeExecutiveContextHref('javascript:alert(1)'), null);

  assert.equal(
    executiveDecisionActionEndpoint(
      { id: 'pm:card-123' },
      { id: 'approve', href: '/api/executive/decisions/pm%3Acard-123/actions/approve' },
    ),
    '/api/executive/decisions/pm%3Acard-123/actions/approve',
  );
  assert.equal(
    executiveDecisionActionEndpoint(
      { id: 'pm:card/123' },
      { id: 'approve now', href: 'https://example.com/unsafe' },
    ),
    '/api/executive/decisions/pm%3Acard%2F123/actions/approve%20now',
  );
  assert.equal(
    executiveDecisionActionEndpoint(
      { id: 'email:thread-1' },
      { id: 'send', href: '/api/email/threads/thread-1/send' },
    ),
    '/api/executive/decisions/email%3Athread-1/actions/send',
  );
});

test('submits explicit confirmation while leaving actor identity to the server', () => {
  assert.match(queueSource, /confirmed:\s*true/);
  assert.doesNotMatch(queueSource, /requested_by/);
});

test('hides historical workspace-review decisions unless rollback compatibility is explicit', () => {
  assert.match(
    queueSource,
    /legacyOwnerReviewCompatibilityEnabled \|\| decision\.source_type !== 'workspace_review'/,
  );
  assert.match(queueSource, /decision\.source_type === 'workspace_review'/);
  assert.match(queueSource, /\?legacy_compatibility=true/);
  assert.match(opsSource, /legacyOwnerReviewCompatibilityEnabled=\{legacyOwnerReviewCompatibilityEnabled\}/);
});

test('defers workspace and canonical docs reads until their consuming panel is active', () => {
  assert.match(
    opsSource,
    /if \(activePanel === 'workspace'\) \{\s*void loadWorkspaceSnapshot\(\);\s*\}/,
  );
  assert.match(
    opsSource,
    /if \(activePanel === 'docs'\) \{\s*void loadDocsIndex\(\);\s*\}/,
  );
  assert.match(
    opsSource,
    /controlApiGet<BrainDocsIndexPayload>\('\/api\/brain\/docs'/,
  );
  assert.match(
    opsSource,
    /if \(activePanel !== 'workspace'\) \{\s*return;\s*\}\s*void loadFeezieOwnerReview\(\);/,
  );
  assert.match(
    opsSource,
    /const reloadFeezieWorkspaceSnapshot = useCallback\(async \(\) => \{\s*await Promise\.all\(\[loadWorkspaceSnapshot\(\), loadFeezieOwnerReview\(\)\]\);/,
  );
});
