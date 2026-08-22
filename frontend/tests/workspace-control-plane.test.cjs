const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const frontendRoot = path.join(__dirname, '..');
const composerPath = path.join(frontendRoot, 'app', 'workspace', 'workspace-composer.ts');
const composerSource = fs.readFileSync(composerPath, 'utf8');
const postingSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'posting', 'page.tsx'), 'utf8');
const workspaceSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'WorkspaceClient.tsx'), 'utf8');
const opsSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const contentPipelineSource = fs.readFileSync(path.join(frontendRoot, 'app', 'content-pipeline', 'page.tsx'), 'utf8');
const brainSource = fs.readFileSync(path.join(frontendRoot, 'app', 'brain', 'BrainClient.tsx'), 'utf8');
const runtimeChromeSource = fs.readFileSync(path.join(frontendRoot, 'components', 'runtime', 'RuntimeChrome.tsx'), 'utf8');
const inboxSources = [
  fs.readFileSync(path.join(frontendRoot, 'app', 'inbox', 'page.tsx'), 'utf8'),
  fs.readFileSync(path.join(frontendRoot, 'app', 'inbox', 'neo', 'page.tsx'), 'utf8'),
  fs.readFileSync(path.join(frontendRoot, 'app', 'inbox', '[threadId]', 'page.tsx'), 'utf8'),
];
const promotableSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'PromotableInlineText.tsx'), 'utf8');
const generationReceiptSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'GenerationReceiptPanel.tsx'), 'utf8');
const privateRuntimeStatusSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'FeeziePrivateRuntimeStatus.tsx'), 'utf8');
const fragmentUtilsSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'generatedFragmentUtils.ts'), 'utf8');
const localVoiceReviewSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'localVoiceReview.ts'), 'utf8');
const controlApiSource = fs.readFileSync(path.join(frontendRoot, 'lib', 'control-api.ts'), 'utf8');
const feedRefreshPollingSource = fs.readFileSync(path.join(frontendRoot, 'lib', 'feed-refresh-polling.ts'), 'utf8');
const feezieWorkspaceSyncSource = fs.readFileSync(path.join(frontendRoot, 'lib', 'feezie-workspace-sync.ts'), 'utf8');
const compiledGenerationReceipt = ts.transpileModule(generationReceiptSource, {
  compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedGenerationReceipt = { exports: {} };
new Function('module', 'exports', 'require', compiledGenerationReceipt)(
  loadedGenerationReceipt,
  loadedGenerationReceipt.exports,
  (specifier) => {
    if (specifier === '@/app/workspace/generatedFragmentUtils') {
      return {
        criticReviewForOption: (readiness, optionIndex) => readiness?.option_reviews?.find(
          (review) => review.option_index === optionIndex + 1,
        ),
        editorialReadinessLabel: () => 'Test readiness',
      };
    }
    return require(specifier);
  },
);
const {
  buildCriticCoverageLabel,
  buildCriticReceiptState,
  deterministicPlanDraftBlockers,
  isOptionEditoriallyReady,
} = loadedGenerationReceipt.exports;
const compiledFeedRefreshPolling = ts.transpileModule(feedRefreshPollingSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedFeedRefreshPolling = { exports: {} };
new Function('module', 'exports', 'require', compiledFeedRefreshPolling)(
  loadedFeedRefreshPolling,
  loadedFeedRefreshPolling.exports,
  require,
);
const { waitForFeedRefreshAttempt } = loadedFeedRefreshPolling.exports;
const compiledFeezieWorkspaceSync = ts.transpileModule(feezieWorkspaceSyncSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedFeezieWorkspaceSync = { exports: {} };
new Function('module', 'exports', 'require', compiledFeezieWorkspaceSync)(
  loadedFeezieWorkspaceSync,
  loadedFeezieWorkspaceSync.exports,
  require,
);
const { waitForFeezieWorkspaceSync } = loadedFeezieWorkspaceSync.exports;

test('FEEZIE opens with a bounded Today’s Distribution decision surface', () => {
  assert.match(workspaceSource, /Today&apos;s Distribution/);
  assert.match(workspaceSource, /ownerReviewItems\.slice\(0, 2\)/);
  assert.match(workspaceSource, /\.slice\(0, 3\)/);
  assert.match(workspaceSource, /Use it/);
  assert.match(workspaceSource, /Edit it/);
  assert.match(workspaceSource, /Not for me/);
});

test('workspace presents the owner as evidence-led, not a finished expert', () => {
  assert.match(workspaceSource, /Direct, curious, evidence-led\. Student-scientist energy\./);
  assert.doesNotMatch(workspaceSource, /Expert \+ direct/);
});

test('workspace separates transport availability from editorial and performance truth', () => {
  assert.match(workspaceSource, /data-snapshot-editorial-state=/);
  assert.match(workspaceSource, /What FEEZIE can prove right now/);
  assert.match(workspaceSource, /HTTP: \$\{snapshotState === 'live' \? 'available'/);
  assert.match(workspaceSource, /Editorial: \$\{humanizeFeezieWorkspaceLabel\(snapshotEditorialState\)\}/);
  assert.match(workspaceSource, /Performance: \$\{humanizeFeezieWorkspaceLabel\(performanceState\)\}/);
  assert.match(workspaceSource, /Primary KPI/);
  assert.match(workspaceSource, /Learning gate/);
  assert.match(workspaceSource, /Next truth-building actions/);
});

test('both FEEZIE feed controls bind polling to the queued Railway run receipt', () => {
  for (const source of [workspaceSource, opsSource]) {
    assert.match(source, /waitForFeedRefreshAttempt\(\{/);
    assert.match(source, /receipt,/);
    assert.match(source, /waitForFeedRefresh\(data\)/);
    assert.doesNotMatch(source, /if \(!status\.running\)/);
  }
});

test('feed refresh polling ignores stale idle state before the queued run starts', async () => {
  const statuses = [
    {
      running: false,
      state: 'succeeded',
      run_id: 'old-run',
      started_at: '2026-08-16T13:00:01Z',
      completed_at: '2026-08-16T13:03:01Z',
    },
    {
      running: true,
      state: 'running',
      run_id: 'new-run',
      started_at: '2026-08-16T14:00:01Z',
    },
    {
      running: false,
      state: 'succeeded',
      run_id: 'new-run',
      started_at: '2026-08-16T14:00:01Z',
      completed_at: '2026-08-16T14:03:01Z',
      last_run: '2026-08-16T14:03:01Z',
    },
  ];
  let reads = 0;
  let sleeps = 0;
  const result = await waitForFeedRefreshAttempt({
    receipt: { run_id: 'new-run', queued_at: '2026-08-16T14:00:00Z' },
    readStatus: async () => statuses[reads++],
    sleep: async () => {
      sleeps += 1;
    },
    pollIntervalMs: 1,
    timeoutMs: 3,
  });

  assert.equal(reads, 3);
  assert.equal(sleeps, 2);
  assert.equal(result.last_run, '2026-08-16T14:03:01Z');
});

test('feed refresh polling accepts a fast terminal result for the matching run', async () => {
  let reads = 0;
  let sleeps = 0;
  const result = await waitForFeedRefreshAttempt({
    receipt: { run_id: 'fast-run', queued_at: '2026-08-16T14:00:00Z' },
    readStatus: async () => {
      reads += 1;
      return {
        running: false,
        state: 'succeeded',
        run_id: 'fast-run',
        started_at: '2026-08-16T14:00:00.100Z',
        completed_at: '2026-08-16T14:00:00.200Z',
      };
    },
    sleep: async () => {
      sleeps += 1;
    },
    pollIntervalMs: 1,
    timeoutMs: 3,
  });

  assert.equal(result.run_id, 'fast-run');
  assert.equal(reads, 1);
  assert.equal(sleeps, 0);
});

test('feed refresh polling ignores a stale prior error and returns the matching success', async () => {
  const statuses = [
    {
      running: false,
      state: 'failed',
      run_id: 'stale-failure',
      started_at: '2026-08-16T13:00:01Z',
      completed_at: '2026-08-16T13:00:02Z',
      error_type: 'social_feed_refresh_error',
    },
    {
      running: false,
      state: 'succeeded',
      run_id: 'current-success',
      started_at: '2026-08-16T14:00:01Z',
      completed_at: '2026-08-16T14:00:02Z',
    },
  ];
  let reads = 0;
  const result = await waitForFeedRefreshAttempt({
    receipt: { run_id: 'current-success', queued_at: '2026-08-16T14:00:00Z' },
    readStatus: async () => statuses[reads++],
    sleep: async () => {},
    pollIntervalMs: 1,
    timeoutMs: 2,
  });

  assert.equal(result.run_id, 'current-success');
  assert.equal(reads, 2);
});

test('feed refresh polling reports only a terminal failure bound to the current run', async () => {
  const statuses = [
    {
      running: false,
      state: 'failed',
      run_id: 'stale-failure',
      started_at: '2026-08-16T13:00:01Z',
      completed_at: '2026-08-16T13:00:02Z',
      error_type: 'old-private-error',
    },
    {
      running: true,
      state: 'running',
      run_id: 'current-failure',
      started_at: '2026-08-16T14:00:01Z',
    },
    {
      running: false,
      state: 'failed',
      run_id: 'current-failure',
      started_at: '2026-08-16T14:00:01Z',
      completed_at: '2026-08-16T14:00:02Z',
      error_type: 'new-private-error',
    },
  ];
  let reads = 0;

  await assert.rejects(
    waitForFeedRefreshAttempt({
      receipt: { run_id: 'current-failure', queued_at: '2026-08-16T14:00:00Z' },
      readStatus: async () => statuses[reads++],
      sleep: async () => {},
      pollIntervalMs: 1,
      timeoutMs: 3,
    }),
    (error) => {
      assert.match(error.message, /Feed refresh failed/);
      assert.doesNotMatch(error.message, /old-private-error|new-private-error/);
      return true;
    },
  );
  assert.equal(reads, 3);
});

test('FEEZIE refresh waits for the exact signed Mac action before reporting completion', async () => {
  const statuses = [
    {
      job_id: 'card-current',
      card_id: 'card-current',
      status: 'running',
      created_at: '2026-08-17T14:00:00Z',
    },
    {
      job_id: 'card-current',
      card_id: 'card-current',
      status: 'completed',
      created_at: '2026-08-17T14:00:00Z',
      completed_at: '2026-08-17T14:00:03Z',
    },
  ];
  let reads = 0;
  const result = await waitForFeezieWorkspaceSync({
    receipt: {
      action: 'refresh_feezie_workspace',
      card_id: 'card-current',
      card: { id: 'card-current', created_at: '2026-08-17T14:00:00Z' },
    },
    readStatus: async (cardId) => {
      assert.equal(cardId, 'card-current');
      return statuses[reads++];
    },
    sleep: async () => {},
    pollIntervalMs: 1,
    timeoutMs: 2,
  });

  assert.equal(reads, 2);
  assert.equal(result.status, 'completed');
});

test('FEEZIE refresh fails closed on a mismatched or failed local action without exposing runner errors', async () => {
  await assert.rejects(
    waitForFeezieWorkspaceSync({
      receipt: {
        action: 'refresh_feezie_workspace',
        card_id: 'card-current',
        card: { id: 'card-current', created_at: '2026-08-17T14:00:00Z' },
      },
      readStatus: async () => ({
        job_id: 'different-card',
        card_id: 'different-card',
        status: 'completed',
        created_at: '2026-08-17T14:00:00Z',
        completed_at: '2026-08-17T14:00:03Z',
      }),
      pollIntervalMs: 1,
      timeoutMs: 1,
    }),
    /did not match the exact queued action/,
  );

  await assert.rejects(
    waitForFeezieWorkspaceSync({
      receipt: {
        action: 'refresh_feezie_workspace',
        card_id: 'card-current',
        card: { id: 'card-current', created_at: '2026-08-17T14:00:00Z' },
      },
      readStatus: async () => ({
        job_id: 'card-current',
        card_id: 'card-current',
        status: 'failed',
        created_at: '2026-08-17T14:00:00Z',
        message: 'private-canary',
        error_code: 'bounded_local_action_failure',
      }),
      pollIntervalMs: 1,
      timeoutMs: 1,
    }),
    (error) => {
      assert.match(error.message, /failed on the local runner/);
      assert.doesNotMatch(error.message, /private|secret|canary|path/);
      return true;
    },
  );
});

test('the FEEZIE workspace control chains Railway feed refresh to exact Mac sync and freshness proof', () => {
  assert.match(workspaceSource, /\/api\/brain\/refresh-feezie-workspace/);
  assert.match(workspaceSource, /waitForFeezieWorkspaceSync\(\{/);
  assert.match(workspaceSource, /\/api\/brain\/refresh-feezie-workspace\/\$\{encodeURIComponent\(cardId\)\}/);
  assert.doesNotMatch(workspaceSource, /\/api\/pm\/cards\/\$\{encodeURIComponent\(cardId\)\}\/execution-source/);
  assert.match(workspaceSource, /sections\?\.weekly_plan\?\.state !== 'fresh'/);
  assert.match(workspaceSource, /isFeeziePrivateRuntimeContextReady\(refreshedSnapshot\.private_runtime_context_status\)/);
  assert.match(workspaceSource, /Refresh FEEZIE workspace/);
  assert.match(workspaceSource, /signed Mac runner/);
});

test('workspace exposes the bounded critic-guided revision receipt without copy', () => {
  assert.match(generationReceiptSource, /feezie_revision_execution_receipt\/v1/);
  assert.match(fragmentUtilsSource, /contains_post_copy\?: boolean/);
  assert.match(fragmentUtilsSource, /contains_critic_issue_copy\?: boolean/);
  assert.match(generationReceiptSource, /Revision not required · 0 calls/);
  assert.match(generationReceiptSource, /Revision completed/);
  assert.match(generationReceiptSource, /fresh critic/);
  assert.match(generationReceiptSource, /Revision stopped closed/);
  assert.match(generationReceiptSource, /No option can advance without an admissible final critic receipt/);
  assert.match(generationReceiptSource, /Original preserved/);
  assert.match(generationReceiptSource, /Revised once/);
  assert.match(generationReceiptSource, /const ready = isOptionEditoriallyReady\(diagnostics, optionIndex\)/);
  assert.doesNotMatch(generationReceiptSource, /original_post_sha256|final_post_sha256|revision_prompt_sha256/);
});

test('pair-distinctness failure cannot render an editorially ready option badge', () => {
  const review = {
    option_index: 1,
    verdict: 'ready',
    score: 9,
    editorially_ready: true,
    hook_variants: Array.from({ length: 8 }, (_, index) => `Hook ${index + 1}`),
  };
  const diagnostics = {
    draft_contract: {
      schema_version: 'feezie_draft_contract/v1',
      hook_variants_per_option: 8,
    },
    draft_distinctness: { passed: false },
    critic_review: {
      status: 'completed',
      draft_distinctness: { passed: false },
    },
    editorial_readiness: {
      ready: false,
      status: 'revision_required',
      critic_status: 'completed',
      semantic_distinctness_passed: false,
      option_reviews: [review],
    },
  };

  assert.equal(isOptionEditoriallyReady(diagnostics, 0), false);
});

test('generation receipt separates deterministic plan and draft blockers from critic availability', () => {
  const blockers = deterministicPlanDraftBlockers({
    quality_gate: {
      failed_reasons: [
        'planned_application_decision_gate_missing',
        'role_a1_application_rule_not_leading',
      ],
    },
    draft_distinctness: {
      failed_reasons: [
        'planned_application_decision_gate_missing',
        'drafts_too_similar',
      ],
    },
  });

  assert.deepEqual(blockers, [
    { code: 'planned_application_decision_gate_missing', stage: 'Plan' },
    { code: 'role_a1_application_rule_not_leading', stage: 'Draft' },
    { code: 'drafts_too_similar', stage: 'Draft' },
  ]);
  assert.match(generationReceiptSource, /Deterministic plan\/draft blockers/);
  assert.match(generationReceiptSource, /Critic availability:/);
  assert.match(generationReceiptSource, /Other editorial blockers:/);
});

test('failed revision receipt states exactly which critic stage is unavailable or did not run', () => {
  const baseDiagnostics = {
    revision_contract: { schema_version: 'feezie_critic_guided_revision_contract/v1' },
    draft_contract: {
      schema_version: 'feezie_draft_contract/v1',
      required_option_count: 2,
      hook_variants_per_option: 8,
    },
    critic_review: {
      status: 'unavailable',
      reason: 'revision_failed_before_final_critic',
      reviews: [
        { option_index: 1, hook_variants: Array.from({ length: 8 }, (_, index) => `Stale hook 1.${index}`) },
        { option_index: 2, hook_variants: Array.from({ length: 8 }, (_, index) => `Stale hook 2.${index}`) },
      ],
    },
    editorial_readiness: { critic_status: 'unavailable' },
  };

  const revisionFailed = {
    ...baseDiagnostics,
    revision_execution: {
      schema_version: 'feezie_revision_execution_receipt/v1',
      status: 'failed',
      failure_code: 'revision_option_2_timeout',
      initial_critic_call_count: 1,
      revision_call_count: 1,
      final_critic_call_count: 0,
    },
  };
  const revisionFailedState = buildCriticReceiptState(revisionFailed);
  assert.deepEqual(revisionFailedState.badges, [
    'Initial critic completed',
    'Final critic not run after revision failure',
  ]);
  assert.equal(revisionFailedState.reviewReceiptUsable, false);
  assert.equal(buildCriticCoverageLabel(revisionFailed, revisionFailedState), 'Final reviews unavailable · hooks unavailable');

  const initialUnavailableState = buildCriticReceiptState({
    ...baseDiagnostics,
    revision_execution: {
      schema_version: 'feezie_revision_execution_receipt/v1',
      status: 'failed',
      failure_code: 'initial_critic_failed',
      initial_critic_call_count: 1,
      revision_call_count: 0,
      final_critic_call_count: 0,
    },
  });
  assert.deepEqual(initialUnavailableState.badges, [
    'Initial critic unavailable',
    'Final critic not run after revision failure',
  ]);

  const initialNotRunState = buildCriticReceiptState({
    ...baseDiagnostics,
    revision_execution: {
      schema_version: 'feezie_revision_execution_receipt/v1',
      status: 'failed',
      failure_code: 'revision_orchestration_failed',
      initial_critic_call_count: 0,
      revision_call_count: 0,
      final_critic_call_count: 0,
    },
  });
  assert.deepEqual(initialNotRunState.badges, [
    'Initial critic not run',
    'Final critic not run after revision failure',
  ]);

  const finalUnavailableState = buildCriticReceiptState({
    ...baseDiagnostics,
    critic_review: { status: 'unavailable', reason: 'final_critic_timeout', reviews: [] },
    revision_execution: {
      schema_version: 'feezie_revision_execution_receipt/v1',
      status: 'failed',
      failure_code: 'final_critic_failed',
      initial_critic_call_count: 1,
      revision_call_count: 1,
      final_critic_call_count: 1,
    },
  });
  assert.deepEqual(finalUnavailableState.badges, [
    'Initial critic completed',
    'Final critic unavailable after revision',
  ]);

  const rejectedFinalReceipt = {
    ...baseDiagnostics,
    critic_review: { ...baseDiagnostics.critic_review, status: 'completed' },
    editorial_readiness: { critic_status: 'completed' },
    revision_execution: {
      schema_version: 'feezie_revision_execution_receipt/v1',
      status: 'failed',
      failure_code: 'final_critic_not_independent',
      initial_critic_call_count: 1,
      revision_call_count: 1,
      final_critic_call_count: 1,
    },
  };
  const rejectedFinalState = buildCriticReceiptState(rejectedFinalReceipt);
  assert.deepEqual(rejectedFinalState.badges, [
    'Initial critic completed',
    'Final critic receipt rejected after revision',
  ]);
  assert.equal(rejectedFinalState.reviewReceiptUsable, false);
  assert.equal(buildCriticCoverageLabel(rejectedFinalReceipt, rejectedFinalState), 'Final reviews unavailable · hooks unavailable');
});

test('generation receipt reports complete review and hook coverage only from an admissible critic receipt', () => {
  const reviews = [1, 2].map((optionIndex) => ({
    option_index: optionIndex,
    hook_variants: Array.from({ length: 8 }, (_, hookIndex) => `Hook ${optionIndex}.${hookIndex}`),
  }));
  const diagnostics = {
    revision_contract: { schema_version: 'feezie_critic_guided_revision_contract/v1' },
    revision_execution: {
      schema_version: 'feezie_revision_execution_receipt/v1',
      status: 'completed',
      initial_critic_call_count: 1,
      revision_call_count: 1,
      final_critic_call_count: 1,
    },
    draft_contract: {
      schema_version: 'feezie_draft_contract/v1',
      required_option_count: 2,
      hook_variants_per_option: 8,
    },
    critic_review: { status: 'completed', reviews },
    editorial_readiness: { critic_status: 'completed', option_reviews: reviews },
  };
  const state = buildCriticReceiptState(diagnostics);

  assert.equal(state.reviewReceiptUsable, true);
  assert.equal(buildCriticCoverageLabel(diagnostics, state), 'Final reviews 2/2 · 8 hooks each');
  assert.match(generationReceiptSource, /Hook lab complete/);
  assert.match(generationReceiptSource, /Hook lab incomplete/);
  assert.doesNotMatch(generationReceiptSource, /Critic \+ hooks/);
});

test('generation receipts disclose the effective grounding mode without private context', () => {
  assert.match(fragmentUtilsSource, /grounding_mode\?: string/);
  assert.match(generationReceiptSource, /Grounding \$\{humanize\(diagnostics\.grounding_mode\)\}/);
  assert.match(generationReceiptSource, /Grounding unavailable/);
  assert.doesNotMatch(generationReceiptSource, /raw_context|persona_chunks|proof_records/);
});

test('workspace renders only aggregate grounding inventory in the browser', () => {
  assert.match(workspaceSource, /Private grounding inventory/);
  assert.match(workspaceSource, /authenticated Railway private storage/);
  assert.match(workspaceSource, /authenticated Railway private context/);
  assert.match(workspaceSource, /aggregate-only browser projection/);
  assert.match(workspaceSource, /raw source bodies, filenames, snippets, and local paths stay outside the browser/);
  assert.doesNotMatch(workspaceSource, /workspaceRelativePath/);
  assert.doesNotMatch(workspaceSource, /file\.snippet|file\.content|workspace_files\?:|doc_entries\?:/);
});

test('both FEEZIE composers show the same aggregate private-runtime readiness receipt', () => {
  assert.match(workspaceSource, /<FeeziePrivateRuntimeStatusBadge/);
  assert.match(postingSource, /<FeeziePrivateRuntimeStatusBadge/);
  assert.match(postingSource, /controlApiGet<PostingWorkspaceSnapshot>\('\/api\/workspace\/linkedin-os-snapshot'\)/);
  assert.match(privateRuntimeStatusSource, /feezie_private_runtime_context_status\/v1/);
  assert.match(privateRuntimeStatusSource, /Private context ready/);
  assert.match(privateRuntimeStatusSource, /Persona .* · Voice .* · Proof .* · Source/);
  assert.match(workspaceSource, /data-feezie-private-runtime-context-detail="true"/);
  assert.match(workspaceSource, /Approved voice examples/);
  assert.match(workspaceSource, /Anonymized proof/);
  assert.doesNotMatch(privateRuntimeStatusSource, /raw_context|persona_chunks|proof_records|filename|filepath|absolute_path|excerpt/);
});

test('legacy banked posts seed the privacy-safe performance recorder only behind rollback compatibility', () => {
  assert.match(workspaceSource, /legacyTwoOptionCompatibilityEnabled \? \(\s*<section id="linkedin-performance-recorder" data-legacy-performance-compatibility="true"/s);
  assert.match(workspaceSource, /Track evidence/);
  assert.match(workspaceSource, /first_pass_draft\?\.replace\(\/\\r\\n\/g, '\\n'\)\.replace\(\/\\r\/g, '\\n'\)\.trim\(\)/);
  assert.match(workspaceSource, /window\.crypto\.subtle\.digest\('SHA-256'/);
  assert.match(workspaceSource, /\/api\/workspace\/linkedin-performance\/lifecycle\?\$\{query\.toString\(\)\}/);
  assert.match(workspaceSource, /initialContentVersionSha256=\{performanceRecorderSeed\?\.digest\}/);
  assert.match(workspaceSource, /initialClassification=\{performanceRecorderSeed \? ownerReviewPerformanceClassification/);
  assert.match(workspaceSource, /verifiedLifecycle=\{performanceRecorderSeed\?\.verifiedLifecycle\}/);
  assert.match(workspaceSource, /only its ID and SHA-256 were used for lifecycle verification/);
  assert.match(workspaceSource, /Exact lifecycle verification is unavailable/);
  assert.doesNotMatch(workspaceSource, /recent_publications\?:/);
  assert.doesNotMatch(workspaceSource, /publication_url\?:/);
});

test('weekly plan strategy metadata stays optional while current contracts are visible', () => {
  assert.match(workspaceSource, /strategy_contract\?: WeeklyPlanStrategyContract/);
  assert.match(workspaceSource, /strategy_contract_freshness\?: WeeklyPlanContractFreshness/);
  assert.match(workspaceSource, /pillar_coverage\?: WeeklyPlanPillarCoverage/);
  assert.match(workspaceSource, /Legacy plan · contract metadata unavailable/);
  assert.match(workspaceSource, /data-weekly-plan-contract-status="true"/);
  assert.match(workspaceSource, /Contract hash:/);
  assert.match(workspaceSource, /data-weekly-plan-coverage-warnings="true"/);
});

test('weekly plan highlights prefer develop-now work and expose recommendation safeguards', () => {
  assert.match(workspaceSource, /developNowRecommendations/);
  assert.match(workspaceSource, /developNowRecommendations\.length === 0/);
  assert.match(workspaceSource, /const suggested = topRecommendations\[0\]/);
  assert.match(workspaceSource, /Pillar: \$\{item\.canonical_pillar\}/);
  assert.match(workspaceSource, /Safety: \$\{humanizeFeezieWorkspaceLabel\(item\.employer_safety\)\}/);
  assert.match(workspaceSource, /Proof: \$\{humanizeFeezieWorkspaceLabel\(item\.proof_posture\)\}/);
  assert.match(workspaceSource, /Development: \$\{humanizeFeezieWorkspaceLabel\(item\.development_status\)\}/);
  assert.match(workspaceSource, /Audience consequence:/);
});

test('workspace exposes the seven-day publishing board and bounded learning truth', () => {
  assert.match(workspaceSource, /publishing_board\?: WeeklyPlanPublishingBoard/);
  assert.match(workspaceSource, /portfolio_learning\?: WeeklyPlanPortfolioLearning/);
  assert.match(workspaceSource, /data-seven-day-publishing-board="true"/);
  assert.match(workspaceSource, /data-publishing-board-lane=/);
  assert.match(workspaceSource, /Publication authority: owner only/);
  assert.match(workspaceSource, /Exact copy: \$\{card\.exact_copy_bound \? 'bound' : 'unbound'\}/);
  assert.match(workspaceSource, /Critic: \$\{humanizeFeezieWorkspaceLabel\(card\.critic_status \|\| 'not_run'\)\}/);
  assert.match(workspaceSource, /data-weekly-plan-learning-gate="true"/);
  assert.match(workspaceSource, /Collect-only: results cannot influence ranking yet/);
  assert.match(workspaceSource, /Safety, proof, critic, and owner-approval gates remain fixed/);
});

test('workspace and inbox own their runtime identity instead of appearing as Ops', () => {
  const moduleDeclaration = runtimeChromeSource.match(/export type RuntimeModule\s*=\s*([^;]+);/);
  assert.ok(moduleDeclaration, 'expected the RuntimeModule declaration');
  assert.match(moduleDeclaration[1], /'workspace'/);
  assert.match(moduleDeclaration[1], /'inbox'/);
  assert.match(runtimeChromeSource, /workspace:\s*['"][^'"]+['"]/);
  assert.match(runtimeChromeSource, /inbox:\s*['"][^'"]+['"]/);
  assert.match(runtimeChromeSource, /active === (?:workspaceLink\.id|'workspace')/);
  assert.match(runtimeChromeSource, /active === (?:inboxLink\.id|'inbox')/);

  for (const source of [workspaceSource, postingSource]) {
    assert.match(source, /<RuntimePage module="workspace"/);
    assert.doesNotMatch(source, /<RuntimePage module="ops"/);
  }
  for (const source of inboxSources) {
    assert.match(source, /<RuntimePage module="inbox"/);
    assert.doesNotMatch(source, /<RuntimePage module="ops"/);
  }
});

const compiledComposer = ts.transpileModule(composerSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedComposer = { exports: {} };
new Function('module', 'exports', 'require', compiledComposer)(loadedComposer, loadedComposer.exports, require);
const {
  buildFallbackText,
  mapAudienceFromLane,
  normalizeContentCategory,
  normalizeWorkspaceReturnUrl,
  readWorkspaceComposerQuery,
  toWorkspaceSourceCard,
} = loadedComposer.exports;

const compiledLocalVoiceReview = ts.transpileModule(localVoiceReviewSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedLocalVoiceReview = { exports: {} };
new Function('module', 'exports', 'require', compiledLocalVoiceReview)(
  loadedLocalVoiceReview,
  loadedLocalVoiceReview.exports,
  require,
);
const {
  buildLocalVoiceReviewPacket,
  isExactOperationalVoiceReviewCopy,
  localVoiceReviewFilename,
  normalizeLocalVoiceReviewText,
} = loadedLocalVoiceReview.exports;

test('parses a complete Brain card handoff with exact origin and owner reaction', () => {
  const query = readWorkspaceComposerQuery(new URLSearchParams({
    mode: 'comment',
    autoplay: '1',
    itemKey: ' item-7 ',
    brief_id: ' brief-4 ',
    origin_type: 'daily_brief_item',
    originId: 'brief-4:item-7',
    returnUrl: '/brain?date=2026-07-20#brain-section-briefs',
    owner_reaction: ' This belongs in my framework. ',
    title: ' A sharper operating principle ',
    summary: 'Connect the source to a durable belief.',
    hook: 'Start with the tension.',
    source_url: 'https://example.com/watch?v=1',
    sourcePath: 'knowledge/signals/example.md',
    priority_lane: 'ai',
    sourceKind: 'youtube',
    route_reason: 'Matches the active thesis.',
    targetFile: 'knowledge/persona/feeze/identity/claims.md',
    section: 'daily_brief',
  }));

  assert.equal(query.mode, 'comment');
  assert.equal(query.autoplay, true);
  assert.equal(query.itemKey, 'item-7');
  assert.equal(query.briefId, 'brief-4');
  assert.equal(query.originType, 'daily_brief_item');
  assert.equal(query.originId, 'brief-4:item-7');
  assert.equal(query.returnUrl, '/brain?date=2026-07-20#brain-section-briefs');
  assert.equal(query.ownerReaction, 'This belongs in my framework.');
  assert.equal(query.title, 'A sharper operating principle');
  assert.equal(query.sourceUrl, 'https://example.com/watch?v=1');
  assert.equal(query.sourcePath, 'knowledge/signals/example.md');
  assert.equal(query.priorityLane, 'ai');
  assert.equal(query.sourceKind, 'youtube');
  assert.equal(query.routeReason, 'Matches the active thesis.');
  assert.equal(query.targetFile, 'knowledge/persona/feeze/identity/claims.md');
  assert.equal(query.section, 'daily_brief');
});

test('infers a Daily Brief origin and return target for historical item-key links', () => {
  const query = readWorkspaceComposerQuery(new URLSearchParams({ item_key: 'brief-item-12' }));

  assert.equal(query.originType, 'daily_brief_item');
  assert.equal(query.originId, 'brief-item-12');
  assert.equal(query.returnUrl, '/brain#brain-section-briefs');
});

test('keeps return navigation same-origin', () => {
  for (const unsafeTarget of [
    'https://example.com',
    '//example.com',
    '/\\example.com',
    '/%2f%2fexample.com',
    '/%5cexample.com',
    'javascript:alert(1)',
    '/brain\nhttps://example.com',
  ]) {
    assert.equal(normalizeWorkspaceReturnUrl(unsafeTarget), '/brain', unsafeTarget);
  }
  assert.equal(
    normalizeWorkspaceReturnUrl('/brain?delta_id=delta-1#brain-section-persona'),
    '/brain?delta_id=delta-1#brain-section-persona',
  );
});

test('converts a handoff into a compact structured source card', () => {
  const query = readWorkspaceComposerQuery(new URLSearchParams({
    itemKey: 'item-7',
    briefId: 'brief-4',
    originType: 'daily_brief_item',
    originId: 'brief-4:item-7',
    returnUrl: '/brain#brain-section-briefs',
    ownerReaction: 'This supports my operating framework.',
    title: 'Source title',
    summary: 'Source summary',
    sourceUrl: 'https://example.com/source',
    priorityLane: 'leadership',
  }));

  assert.deepEqual(toWorkspaceSourceCard(query), {
    item_key: 'item-7',
    brief_id: 'brief-4',
    origin_type: 'daily_brief_item',
    origin_id: 'brief-4:item-7',
    owner_reaction: 'This supports my operating framework.',
    title: 'Source title',
    summary: 'Source summary',
    source_url: 'https://example.com/source',
    priority_lane: 'leadership',
  });
  assert.equal(Object.hasOwn(toWorkspaceSourceCard(query), 'return_url'), false);
  assert.equal(toWorkspaceSourceCard(readWorkspaceComposerQuery(new URLSearchParams())), null);
});

test('preserves weekly recommendation classification while normalizing only the generator audience', () => {
  const query = readWorkspaceComposerQuery(new URLSearchParams({
    title: 'AI systems need operating context',
    sourcePath: 'workspaces/linkedin-content-os/research/example.md',
    priorityLane: 'AI systems and operator clarity',
    publishPosture: 'owner_review_required',
    canonicalPillar: 'AI-native intrapreneurship in education',
    careerSignal: 'tech_ambition_visible',
    employerProximity: 'current_role_adjacent',
    employerSafety: 'owner_review_required',
    proofPosture: 'operator_evidence_required',
    audience: 'ai_systems_operators',
    audienceConsequence: 'Show operators how context changes system reliability.',
    distinctThesis: 'Most agent failures are operating-context failures.',
    whyNow: 'Teams are moving from demos to durable workflows.',
    developmentStatus: 'develop_now',
  }));

  assert.deepEqual(toWorkspaceSourceCard(query), {
    title: 'AI systems need operating context',
    source_path: 'workspaces/linkedin-content-os/research/example.md',
    priority_lane: 'AI systems and operator clarity',
    publish_posture: 'owner_review_required',
    canonical_pillar: 'AI-native intrapreneurship in education',
    career_signal: 'tech_ambition_visible',
    employer_proximity: 'current_role_adjacent',
    employer_safety: 'owner_review_required',
    proof_posture: 'operator_evidence_required',
    audience: 'ai_systems_operators',
    audience_consequence: 'Show operators how context changes system reliability.',
    distinct_thesis: 'Most agent failures are operating-context failures.',
    why_now: 'Teams are moving from demos to durable workflows.',
    development_status: 'develop_now',
  });
  assert.equal(mapAudienceFromLane(query.audience), 'tech_ai');
  assert.equal(mapAudienceFromLane('education_leaders'), 'education_admissions');
  assert.equal(mapAudienceFromLane('Admissions, outreach, and trust'), 'education_admissions');
  assert.equal(mapAudienceFromLane('AI systems and operator clarity'), 'tech_ai');
});

test('canonicalizes legacy sales intent without allowing unknown request categories', () => {
  assert.equal(normalizeContentCategory('value'), 'value');
  assert.equal(normalizeContentCategory(' invitation '), 'invitation');
  assert.equal(normalizeContentCategory('sales'), 'invitation');
  assert.equal(normalizeContentCategory('personal'), 'personal');
  assert.equal(normalizeContentCategory('promotion'), null);

  assert.match(workspaceSource, /normalizeStoredContentItems/);
  assert.match(workspaceSource, /normalizeContentCategory\(candidate\.category\)/);
  assert.match(workspaceSource, /window\.localStorage\.setItem\(STORAGE_KEY, normalizedPayload\)/);
  assert.equal((workspaceSource.match(/category:\s*normalizeContentCategory\(activeCategory\) \?\? 'value'/g) ?? []).length, 1);
  assert.equal((postingSource.match(/category:\s*normalizeContentCategory\(category\) \?\? 'value'/g) ?? []).length, 1);
  assert.doesNotMatch(workspaceSource, /\bSales\b|category === 'sales'/);
  assert.doesNotMatch(postingSource, /\bSales\b|'sales'/);
});

test('preserves shared audience mapping and fallback-text behavior', () => {
  assert.equal(mapAudienceFromLane('AI'), 'tech_ai');
  assert.equal(mapAudienceFromLane('program-leadership'), 'leadership');
  assert.equal(buildFallbackText([' first ', '', undefined, 'second']), 'first\n\nsecond');
});

test('routes both workspace surfaces through the authenticated control plane', () => {
  for (const source of [postingSource, workspaceSource]) {
    assert.doesNotMatch(source, /from ['"]@\/lib\/api-client['"]/);
    assert.doesNotMatch(source, /\bapi(?:Fetch|Get|Post)\b/);
    assert.doesNotMatch(source, /\bfetch\s*\(/);
  }
  assert.match(postingSource, /controlApiGet/);
  assert.match(postingSource, /controlApiPost/);
  assert.match(workspaceSource, /controlApiGet/);
  assert.match(workspaceSource, /controlApiPost/);
  assert.match(workspaceSource, /controlApiPatch/);
  assert.match(controlApiSource, /export async function controlApiPatch/);
  assert.match(controlApiSource, /method: 'PATCH'/);
});

test('uses the shared handoff parser and returns to the originating Brain view', () => {
  assert.match(postingSource, /readWorkspaceComposerQuery\(searchParams\)/);
  assert.match(postingSource, /toWorkspaceSourceCard\(initialQuery\)/);
  assert.match(postingSource, /href=\{initialQuery\.returnUrl\}/);
  assert.match(postingSource, /initialQuery\.ownerReaction/);
});

test('dedicated composer distinguishes manual ideas from source-backed drafting', () => {
  assert.match(postingSource, /function isHttpSourceUrl/);
  assert.match(postingSource, /That link is a source, not a manual topic/);
  assert.match(postingSource, /Open source intake/);
  assert.match(postingSource, /manualTopicIsSourceUrl \|\| postLoading/);
  assert.match(postingSource, /disabled=\{commentLoading \|\| !sourceCardAvailable\}/);
  assert.match(postingSource, /hidden=\{activeMode !== 'post'\}/);
  assert.match(postingSource, /hidden=\{activeMode !== 'comment'\}/);
  assert.match(postingSource, /planner manages the rolling 4\/4\/2 topic mix/);
  assert.match(postingSource, /Category sets this post&apos;s 9:1:1 intent/);
  assert.match(postingSource, /readOnly=\{topicSourceMode === 'source_card'\}/);
  assert.match(postingSource, /disabled=\{topicSourceMode === 'source_card'\}/);
  assert.match(postingSource, /Source-card mode keeps the attached source identity and uses selected-source grounding/);
  assert.match(postingSource, /initialQuery\.canonicalPillar/);
  assert.match(postingSource, /initialQuery\.careerSignal/);
  assert.match(postingSource, /initialQuery\.employerSafety/);
  assert.match(postingSource, /initialQuery\.proofPosture/);
  assert.match(postingSource, /initialQuery\.audienceConsequence/);
  assert.match(postingSource, /initialQuery\.distinctThesis/);
  assert.match(postingSource, /initialQuery\.whyNow/);
});

test('attaches the source card to both local Codex queue requests only while source-card mode is active', () => {
  const queueRequests = postingSource.match(
    /controlApiPost<LocalCodexJobCreateResponse>\('\/api\/content-generation\/codex-jobs'/g,
  ) ?? [];
  const sourceCardPayloads = postingSource.match(/source_card:\s*activeSourceCard/g) ?? [];

  assert.equal(queueRequests.length, 1);
  assert.equal(sourceCardPayloads.length, 1);
  assert.match(postingSource, /const activeSourceCard = topicSourceMode === 'source_card' \? sourceCard : null/);
  assert.doesNotMatch(postingSource, /\.\.\.\(sourceCard \? \{ source_card: sourceCard \} : \{\}\)/);
});

test('the full FEEZIE workspace also preserves structured source identity', () => {
  assert.match(workspaceSource, /readWorkspaceComposerQuery\(searchParams\)/);
  assert.match(workspaceSource, /toWorkspaceSourceCard\(composerQuery\)/);
  const sourceCardPayloads = workspaceSource.match(/source_card:\s*activeSourceCard/g) ?? [];
  assert.equal(sourceCardPayloads.length, 1);
  assert.match(workspaceSource, /origin_type:\s*'feezie_feed_item'/);
  assert.match(workspaceSource, /origin_type:\s*'feezie_weekly_recommendation'/);
  for (const field of [
    'canonical_pillar',
    'career_signal',
    'employer_proximity',
    'employer_safety',
    'proof_posture',
    'audience',
    'audience_consequence',
    'distinct_thesis',
    'why_now',
    'development_status',
  ]) {
    assert.match(workspaceSource, new RegExp(`${field}: suggested\\.`));
  }
  assert.match(workspaceSource, /mapAudienceFromLane\(suggested\.audience \|\| suggested\.priority_lane \|\| ''\)/);
});

test('both FEEZIE composers fail closed into one-question evidence clarification', () => {
  for (const source of [postingSource, workspaceSource]) {
    assert.match(source, /response\?\.status === 'clarification_required'/);
    assert.match(source, /response\.clarification_key/);
    assert.match(source, /response\.clarification_question/);
    assert.match(source, /evidence_answers: answers/);
    assert.match(source, /Continue evidence check/);
    assert.match(source, /concrete action, exact problem, and observable lesson/);
    assert.match(source, /searching AI Clone \/ FEEZIE records/);
    assert.match(source, /tone: 'conversational'/);
    assert.match(source, /Generalize employer-linked names, systems, and metrics before submitting/);
    assert.doesNotMatch(source, /anonymized server-side/);
    assert.doesNotMatch(source, /topicToSend:\s*topic\s*\|\|\s*'operator insight'/);
  }
});

test('both FEEZIE composers expose truthful process and recovery receipts', () => {
  for (const source of [postingSource, workspaceSource]) {
    assert.match(source, /Process trace:/);
    assert.match(source, /Job ID: \{codexJobId\}/);
    assert.doesNotMatch(source, /Model trace:/);
  }
  assert.match(postingSource, /Check evidence \+ queue/);
  assert.match(postingSource, /Executed by Codex CLI/);
  assert.doesNotMatch(postingSource, /Escalated to Codex Terminal/);
});

test('Brain weekly-plan handoff carries the complete recommendation receipt', () => {
  for (const field of [
    'canonicalPillar',
    'careerSignal',
    'employerProximity',
    'employerSafety',
    'proofPosture',
    'audience',
    'audienceConsequence',
    'distinctThesis',
    'whyNow',
    'developmentStatus',
  ]) {
    assert.match(brainSource, new RegExp(`setPostingParam\\(params, '${field}', seed\\.${field}\\)`));
  }
});

test('legacy content pipeline redirects before any generation or copy bypass can render', () => {
  assert.match(contentPipelineSource, /redirect\('\/workspace'\)/);
  assert.doesNotMatch(contentPipelineSource, /controlApiPost|localStorage|getTemplates|clipboard|Copy|Save/);
});

test('completed options enter durable owner review by server-side option index', () => {
  for (const source of [postingSource, workspaceSource]) {
    assert.match(source, /codex-jobs\/\$\{encodeURIComponent\(codexJobId\)\}\/send-to-review/);
    assert.match(source, /\{ option_index: optionIndex \}/);
    assert.doesNotMatch(source, /send-to-review[\s\S]{0,180}(?:option_text|draft_text|content):/);
    assert.match(source, /Send to owner review/);
    assert.match(source, /Open owner review/);
  }
});

test('generated owner review captures exact edits as a local-only download without posting them', () => {
  const packet = buildLocalVoiceReviewPacket(
    {
      queueId: 'FEEZIE-CODEX-123',
      generatedText: 'The generated draft starts here.',
      editedText: 'I would say it this way instead.',
      decision: 'revise',
      generationJobId: 'job-123',
      generationOptionIndex: 1,
      topic: 'Voice fidelity',
      lane: 'ai',
      ownerNotes: 'Keep the opening conversational.',
    },
    '2026-07-25T12:00:00.000Z',
  );

  assert.equal(packet.schema_version, 'ai_clone_voice_review/v1');
  assert.equal(packet.source, 'feezie_owner_review');
  assert.equal(packet.privacy, 'local_only');
  assert.equal(packet.promote_edited, false);
  assert.equal(packet.generated_text, 'The generated draft starts here.');
  assert.equal(packet.edited_text, 'I would say it this way instead.');
  assert.deepEqual(packet.rejected_texts, []);
  assert.equal(localVoiceReviewFilename(packet.queue_id), 'ai-clone-voice-review-FEEZIE-CODEX-123.json');
  assert.doesNotMatch(localVoiceReviewSource, /\bfetch\s*\(|controlApi(?:Get|Post|Patch)/);
  assert.match(workspaceSource, /Private voice-learning edit/);
  assert.match(workspaceSource, /downloadLocalVoiceReviewPacket\(packet\)/);
  assert.match(workspaceSource, /This field is browser-local feedback/);

  const ownerDecisionRequest = workspaceSource.match(
    /controlApiPost<OwnerReviewPayload>\(`\/api\/workspace\/linkedin-os-owner-review\/\$\{item\.queue_id\}\?legacy_compatibility=true`,[\s\S]{0,260}?\}\);/,
  );
  assert.ok(ownerDecisionRequest, 'expected the existing owner-review request');
  assert.doesNotMatch(ownerDecisionRequest[0], /editedText|edited_text|generatedText|generated_text|voice/);
});

test('exact-copy approval normalizes line endings and outer whitespace without hiding real edits', () => {
  assert.equal(normalizeLocalVoiceReviewText('  First line\r\nSecond line\r  '), 'First line\nSecond line');
  assert.equal(isExactOperationalVoiceReviewCopy('First line\r\nSecond line', '  First line\nSecond line  '), true);
  assert.equal(isExactOperationalVoiceReviewCopy('First line\nSecond line', 'First line \nSecond line'), false);
  assert.equal(isExactOperationalVoiceReviewCopy('First line', 'first line'), false);
  assert.equal(isExactOperationalVoiceReviewCopy('', ''), false);
});

test('a changed browser-local voice edit fails closed before exact-copy approval', () => {
  assert.match(workspaceSource, /data-owner-review-exact-copy-status=\{exactCopyApprovalBlocked \? 'blocked' : 'ready'\}/);
  assert.match(workspaceSource, /disabled=\{actioning \|\| exactCopyApprovalBlocked\}/);
  assert.match(workspaceSource, /decision === 'approve'[\s\S]{0,220}!isExactOperationalVoiceReviewCopy/);
  assert.match(workspaceSource, /Exact-copy Approve is disabled because this browser-local edit is not the operational draft/);
  assert.match(workspaceSource, /Exact-copy Approve is disabled because the operational first-pass draft is unavailable/);
  assert.match(workspaceSource, /start a new two-option generation and independent critic cycle/);
  assert.match(workspaceSource, /browser-local edit was not saved operationally/);

  const guardIndex = workspaceSource.indexOf("decision === 'approve'");
  const ownerDecisionPostIndex = workspaceSource.indexOf(
    'controlApiPost<OwnerReviewPayload>(`/api/workspace/linkedin-os-owner-review/${item.queue_id}?legacy_compatibility=true`',
  );
  assert.ok(guardIndex >= 0, 'expected an exact-copy guard in the owner-review submit handler');
  assert.ok(ownerDecisionPostIndex > guardIndex, 'the exact-copy guard must run before the Railway owner-review request');
});

test('parking a generated draft makes the exact draft an explicit local rejection', () => {
  const packet = buildLocalVoiceReviewPacket({
    queueId: 'FEEZIE-CODEX-456',
    generatedText: 'This is not how I want to sound.',
    editedText: 'This value must be ignored for a parked draft.',
    decision: 'park',
  });

  assert.equal(packet.edited_text, null);
  assert.deepEqual(packet.rejected_texts, ['This is not how I want to sound.']);
  assert.equal(packet.promote_edited, false);
});

test('the queue tells the owner that Codex Terminal runs on the Mac', () => {
  assert.match(fragmentUtilsSource, /Codex Terminal is generating two meaningfully different drafts through the signed-in Codex session on this Mac/);
  assert.doesNotMatch(fragmentUtilsSource, /only escalate to Codex Terminal if the local quality gate fails/);
});

test('generated fragments are presented as review proposals, not canonical writes', () => {
  assert.match(promotableSource, /Propose to Brain/);
  assert.match(promotableSource, /Awaiting review/);
  assert.doesNotMatch(promotableSource, /Saved to/);
  for (const source of [postingSource, workspaceSource]) {
    assert.match(source, /Queued for owner review/);
    assert.doesNotMatch(source, /`Saved to \$\{humanizeBrainTargetLabel/);
  }
});
