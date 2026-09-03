const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const opsSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const clientLocationSource = fs.readFileSync(path.join(__dirname, '..', 'lib', 'use-client-location.ts'), 'utf8');
const uiDatesSource = fs.readFileSync(path.join(__dirname, '..', 'lib', 'ui-dates.ts'), 'utf8');

test('runtime location state hydrates from a stable empty snapshot', () => {
  assert.match(clientLocationSource, /hash: ''/);
  assert.match(clientLocationSource, /const syncLocation = \(\) => setLocation\(readLocation\(\)\)/);
  assert.doesNotMatch(clientLocationSource, /useState<ClientLocation>\(\(\) => readLocation\(\)\)/);
});

test('Ops separates Today decisions from the detailed execution surface', () => {
  assert.match(opsSource, /\{ key: 'pm', label: 'Today'/);
  assert.match(opsSource, /\{ key: 'execution', label: 'Execution'/);
  assert.match(opsSource, /<TodayOpsPanel/);
  assert.match(opsSource, /activePanel === 'execution'/);
  assert.match(
    opsSource,
    /<PortfolioPulseSection[\s\S]{0,180}?snapshot=\{portfolioPulse\}[\s\S]{0,180}?workspaceGoals=\{workspaceGoals\}/,
  );
});

test('Ops Today exposes the canonical final daily conclusion without creating a second authority', () => {
  assert.match(opsSource, /import OpsStandupSummary from '@\/app\/workspace\/OpsStandupSummary'/);
  const todayPanel = opsSource.match(/function TodayOpsPanel\([\s\S]*?\n}\n\nfunction PortfolioPulseSection/);
  assert.ok(todayPanel, 'expected the bounded Today panel implementation');
  assert.match(todayPanel[0], /<PortfolioPulseSection[\s\S]*<OpsStandupSummary projection=\{opsProjection\} goalProjection=\{goalProjection\} \/>[\s\S]*<ExecutiveDecisionQueue/);
  assert.equal((todayPanel[0].match(/<OpsStandupSummary projection=\{opsProjection\} goalProjection=\{goalProjection\} \/>/g) ?? []).length, 1);
});

test('project cards and direct links keep the selected workspace in one shared state', () => {
  assert.match(opsSource, /const \[selectedWorkspaceId, setSelectedWorkspaceId\] = useState/);
  assert.match(opsSource, /searchParams\.get\('workspace'\)/);
  assert.match(opsSource, /searchParams\.set\('workspace', normalizedKey\)/);
  assert.match(opsSource, /selectWorkspace\(workspace\.workspace_key\)/);
  assert.match(opsSource, /selectedWorkspaceId=\{selectedWorkspaceId\}/);
  assert.match(opsSource, /onWorkspaceChange=\{selectWorkspace\}/);
  assert.doesNotMatch(opsSource, /useState<WorkspaceHubKey>\('feezie-os'\)/);
});

test('the selected workspace leads with owner truth while selector cards stay bounded', () => {
  const workspaceHub = opsSource.match(/function WorkspaceHubPanel\([\s\S]*?\n}\n\nfunction WorkspaceActivitySurface/);
  assert.ok(workspaceHub, 'expected the canonical workspace hub');
  assert.match(workspaceHub[0], /projectWorkspaceOwnerTruth\(opsProjection, selectedWorkspaceId, goalProjection\)/);
  assert.match(workspaceHub[0], /data-workspace-owner-truth=/);
  assert.match(workspaceHub[0], /Current meaningful state/);
  assert.match(workspaceHub[0], /Latest governed cycle/);
  assert.match(workspaceHub[0], /activeReadinessLabel/);
  assert.match(workspaceHub[0], /activeOwnerTruth\.currentState/);
  assert.match(workspaceHub[0], /What changed/);
  assert.match(workspaceHub[0], /AI Clone did this/);
  assert.match(workspaceHub[0], /AI Clone recommends/);
  assert.match(workspaceHub[0], /Needs your decision/);
  assert.match(workspaceHub[0], /Next Dream consumes/);
  assert.match(workspaceHub[0], /Goal criteria, operating rules, and cycle receipt/);
  assert.match(workspaceHub[0], /const \[selectorOpen, setSelectorOpen\] = useState\(false\)/);
  const selectorStart = workspaceHub[0].indexOf('data-workspace-selector="projects"');
  const selectorEnd = workspaceHub[0].indexOf("{selectedWorkspaceId === 'feezie-os'", selectorStart);
  assert.ok(selectorStart >= 0 && selectorEnd > selectorStart, 'expected bounded project selector');
  const selector = workspaceHub[0].slice(selectorStart, selectorEnd);
  assert.match(selector, /No owner action reported/);
  assert.doesNotMatch(selector, /workspace\.operatingPrinciples\.map/);
  assert.doesNotMatch(selector, /Last canonical observation|Cycle checked/);
  assert.match(workspaceHub[0], /Browser receipt time never replaces a workspace artifact date/);
});

test('workspace cycle outcomes come from the durable Ops conclusion before transient automation history', () => {
  assert.match(opsSource, /controlApiGet<OpsWorkspaceCycleProjection>\('\/api\/workspace\/ops-standup'/);
  assert.match(opsSource, /workspace_cycle_evaluations/);
  assert.match(opsSource, /projected\.size > 0 \? projected : latestWorkspaceCycleEvaluations/);
});

test('one-role FEEZIE UX names the signed async action without claiming a meeting or authority transfer', () => {
  assert.match(opsSource, /one role runs as a signed asynchronous contribution/);
  assert.match(opsSource, /canonical_pm_execution_authority/);
  assert.match(opsSource, /pm_execution_authority_transferred/);
  assert.match(opsSource, /async_recommendation_terminal_dispositions/);
  const helper = opsSource.match(
    /function workspaceCycleEvaluationCopy[\s\S]*?(?=\nfunction buildMissionActivityRows)/,
  );
  assert.ok(helper, 'expected the one-role owner explanation helper');
  const compiled = ts.transpileModule(
    `type WorkspaceCycleEvaluation = Record<string, any>;
     const humanizeStatusLabel = (value: string) => value.replaceAll('_', ' ');
     ${helper[0]}
     module.exports = { workspaceCycleEvaluationCopy };`,
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
  ).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
  const { workspaceCycleEvaluationCopy } = moduleRef.exports;
  const evaluation = {
    status: 'async_contribution',
    asyncRole: 'Neo',
    canonicalPmExecutionAuthority: 'Jean-Claude',
    authorityTransferred: false,
    terminalDispositions: ['placed_in_execution_queue'],
    ownerDecisionCount: 0,
  };

  const copy = workspaceCycleEvaluationCopy(evaluation);
  assert.match(copy, /Neo ran independently/);
  assert.match(copy, /no meeting was held/);
  assert.match(copy, /Jean-Claude retained PM\/execution authority/);
  assert.match(copy, /1 recommendation disposition reached canonical terminal state/);
  assert.doesNotMatch(copy, /attended|transcript|consensus/i);

  const invalid = workspaceCycleEvaluationCopy({
    ...evaluation,
    authorityTransferred: true,
  });
  assert.match(invalid, /^Blocked:/);
  assert.match(invalid, /No such transfer is valid/);
});

test('cycle evaluations remain separate from meetings and named-agent participation claims', () => {
  assert.match(opsSource, /function isMeetingStandupRecord/);
  assert.match(opsSource, /payload\.record_kind === 'standup'/);
  assert.match(opsSource, /payload\.meeting_held === true/);
  assert.match(opsSource, /payload\.meeting_evidence_state === 'verified_independent_agent_meeting'/);
  assert.match(opsSource, /evidenceRecord\.schema_version === 'standup_meeting_evidence\/v1'/);
  assert.match(opsSource, /evidenceRecord\.transcript_provenance === 'compiled_from_signed_canonical_participant_reports'/);
  assert.match(opsSource, /report\.provenance === 'independent_codex_agent_run'/);
  assert.match(opsSource, /round\.provenance === 'independent_codex_agent_run'/);
  assert.match(opsSource, /participant_report_run_ids/);
  assert.match(opsSource, /round\.participant_report_run_id === report\?\.agent_run_id/);
  assert.doesNotMatch(opsSource, /payload\.meeting_held !== false/);
  assert.match(opsSource, /\.filter\(isMeetingStandupRecord\)/);
  assert.match(opsSource, /Server-verified independent-agent meeting/);
  assert.match(opsSource, /Workspace cycle plan/);
  assert.match(opsSource, /Cycle evaluation/);
  assert.match(opsSource, /Recorded Participant Roles/);
  assert.match(opsSource, /Stored roles do not by themselves prove attendance or an independent agent run/);
  assert.match(opsSource, /System-synthesized role lens/);
  assert.match(opsSource, /Room contract roles — eligibility, not attendance/);
  assert.match(opsSource, /Transcript-referenced/);
  assert.match(opsSource, /separate provenance is still required/);
  assert.match(opsSource, /Zero selected roles means no meeting/);
  assert.match(opsSource, /no changed eligible input required a meeting or internal work/);
  assert.doesNotMatch(opsSource, /inputs matched an already-handled decision/);
  assert.doesNotMatch(opsSource, /merged\.length} attendees/);
  assert.match(opsSource, /recorded\.length} recorded role/);
  assert.doesNotMatch(opsSource, /Observed Attendees/);
  assert.doesNotMatch(opsSource, /observed attendee/);
});

test('verified meeting recognition follows canonical closer-last report order', () => {
  const helperBlock = opsSource.match(
    /function standupDiscussion[\s\S]*?(?=\nfunction coordinationRecordLabel)/,
  );
  assert.ok(helperBlock, 'expected the bounded meeting-truth helper block');
  assert.match(helperBlock[0], /const canonicalCloser = 'Jean-Claude'/);
  assert.match(helperBlock[0], /participant !== canonicalCloser/);
  assert.match(helperBlock[0], /participantSet\.has\(canonicalCloser\)/);
  assert.doesNotMatch(helperBlock[0], /participants\.slice\(1\)/);
  assert.doesNotMatch(helperBlock[0], /participants\[0\]/);
  const compiled = ts.transpileModule(
    `type StandupEntry = { source?: string; workspace_key?: string; payload?: Record<string, any> };\n${helperBlock[0]}\nmodule.exports = { isMeetingStandupRecord };`,
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
  ).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
  const { isMeetingStandupRecord } = moduleRef.exports;
  const participants = ['Jean-Claude', 'Neo', 'Yoda'];
  const phases = ['status', 'analysis', 'commitments_resolution'];
  const digest = 'a'.repeat(64);

  const entryForFinalOrder = (finalOrder) => {
    const reportOrder = [participants, participants, finalOrder];
    const reports = reportOrder.flatMap((phaseParticipants, phaseOffset) =>
      phaseParticipants.map((displayName) => ({
        schema_version: 'standup_participant_report/v1',
        provenance: 'independent_codex_agent_run',
        agent_run_id: `run-${phaseOffset + 1}-${displayName}`,
        display_name: displayName,
        generated_at: '2026-08-27T12:00:00Z',
        phase_index: phaseOffset + 1,
        phase: phases[phaseOffset],
        input_sha256: digest,
        identity_pack_sha256: digest,
        report_sha256: digest,
      })),
    );
    const reportRunIds = reports.map((report) => report.agent_run_id);
    const discussion = reports.map((report, index) => ({
      round: index + 1,
      phase: report.phase,
      phase_index: report.phase_index,
      speaker: report.display_name,
      note: `${report.display_name} supplied a bounded report.`,
      participant_report_run_id: report.agent_run_id,
      provenance: 'independent_codex_agent_run',
    }));
    return {
      source: 'independent_agent_meeting_worker',
      workspace_key: 'shared_ops',
      payload: {
        record_kind: 'standup',
        meeting_held: true,
        evaluation_only: false,
        meeting_evidence_state: 'verified_independent_agent_meeting',
        cycle_id: 'daily-test',
        meeting_id: 'meeting-test',
        standup_kind: 'executive_ops',
        participants,
        discussion,
        meeting_evidence: {
          schema_version: 'standup_meeting_evidence/v1',
          transcript_provenance: 'compiled_from_signed_canonical_participant_reports',
          transcript_sha256: digest,
          cycle_id: 'daily-test',
          meeting_id: 'meeting-test',
          standup_kind: 'executive_ops',
          workspace_key: 'shared_ops',
          participant_reports: reports,
          participant_report_run_ids: reportRunIds,
        },
      },
    };
  };

  assert.equal(
    isMeetingStandupRecord(entryForFinalOrder(['Neo', 'Yoda', 'Jean-Claude'])),
    true,
    'the canonical final phase places Jean-Claude last after both signed resolutions',
  );
  assert.equal(
    isMeetingStandupRecord(entryForFinalOrder(['Jean-Claude', 'Neo', 'Yoda'])),
    false,
    'a closer-first final phase must not be accepted as canonical evidence',
  );
});

test('manual standup promotion preserves the canonical participant contract', () => {
  const promotion = opsSource.match(/function buildStandupPromotionPayload\([\s\S]*?\n}\n\nfunction buildJeanClaudeStandupNote/);
  assert.ok(promotion, 'expected the bounded standup promotion implementation');
  assert.match(promotion[0], /standupPromotionParticipants\(prep\)/);
  assert.match(promotion[0], /standup_relevance: relevance/);
  assert.match(promotion[0], /FEEZIE standup promotion requires an authoritative relevance result/);
  assert.match(promotion[0], /cycle_id: cycleId/);
  assert.match(promotion[0], /recursion: \{/);
  assert.match(promotion[0], /authority !== 'ai_clone_utc'/);
  assert.match(promotion[0], /participants: \[\.\.\.room\.participants\]/);
  assert.doesNotMatch(promotion[0], /includeYoda \? \['Jean-Claude', 'Neo', 'Yoda'\]/);
  assert.doesNotMatch(opsSource, /const closer = participants\[0\]/);
  assert.match(opsSource, /const closer = 'Jean-Claude'/);
  assert.match(opsSource, /provenance: 'synthesized_role_lens'/);
});

test('FEEZIE relevance lenses cannot acquire Jean-Claude closure authority', () => {
  const selection = opsSource.match(
    /function standupPromotionParticipants[\s\S]*?(?=\nfunction buildJeanClaudeStandupNote)/,
  );
  assert.ok(selection, 'expected the bounded participant selection helper');
  assert.match(selection[0], /const effectiveMeetingParticipants = \[/);
  assert.match(selection[0], /'Jean-Claude'/);
  assert.match(selection[0], /participants\.filter\(\(participant\) => participant !== 'Jean-Claude'\)/);
  assert.match(selection[0], /return \{ participants: effectiveMeetingParticipants, relevance \}/);
  assert.doesNotMatch(selection[0], /participants\[0\].*closer/);
});

test('FEEZIE multi-role prep cannot bypass the verified meeting and terminal closer', () => {
  const guard = opsSource.match(/function prepRequiresVerifiedMeeting[\s\S]*?\n}/);
  assert.ok(guard, 'expected a bounded FEEZIE verified-meeting guard');
  assert.match(guard[0], /normalizeWorkspaceBoardKey\(prep\.workspaceKey\) === 'feezie-os'/);
  assert.match(guard[0], /prep\.standupRelevance\?\.disposition === 'run'/);
  assert.equal(
    (opsSource.match(/prepRequiresVerifiedMeeting\(prep\) \? \(/g) ?? []).length,
    2,
    'both Today and room diagnostics must withhold the FEEZIE route action',
  );
  assert.match(opsSource, /data-standup-authority-state="awaiting-verified-meeting"/);
  assert.match(opsSource, /Jean-Claude&(?:rsquo|#39);s terminal close must be verified/);
  assert.match(opsSource, /terminal close must be verified before this prep can seed PM work/);
});

test('Ops routes browser requests through the authenticated same-origin control plane', () => {
  assert.doesNotMatch(opsSource, /from ['"]@\/lib\/api-client['"]/);
  assert.doesNotMatch(opsSource, /\bapi(?:Get|Post)\b/);
  assert.match(opsSource, /const API_URL = '\/api\/control'/);
  assert.match(opsSource, /controlApiGet/);
  assert.match(opsSource, /controlApiPost/);
  assert.doesNotMatch(opsSource, /NEXT_PUBLIC_API_URL/);
});

test('standup rooms distinguish current work from quiet and on-demand history', () => {
  assert.match(opsSource, /operatingMode: 'core' \| 'on_demand'/);
  assert.match(opsSource, /status = 'quiet'/);
  assert.match(opsSource, /On-demand room\. No meeting is due/);
  assert.doesNotMatch(opsSource, /const isExpected = true/);
  assert.doesNotMatch(opsSource, /No meeting transcript recorded for this required lane yet/);
});

test('meeting freshness is separate from current carry-forward action', () => {
  assert.match(opsSource, /ageMs <= maxAgeMs \|\| carryForwardActivityAt >= currentOwnerActionCutoff/);
  assert.match(opsSource, /freshness: 'current' \| 'quiet'/);
  assert.match(opsSource, /freshness = ageMs <= maxAgeMs \? 'current' : 'quiet'/);
  assert.match(opsSource, /meetingOps\.rooms\.filter\(\(room\) => room\.freshness === 'current'\)/);
  assert.match(opsSource, /label="Verified rooms"/);
  assert.match(opsSource, /label="Verified Meeting Evidence"/);
  assert.match(opsSource, /label="Outcome Clear"/);
});

test('cycle-plan routing stays outside verified meeting freshness and reader metrics', () => {
  assert.match(opsSource, /function findLatestCoordinationEntry/);
  assert.match(opsSource, /latestCoordinationEntry/);
  assert.match(opsSource, /Route current cycle plan/);
  assert.match(opsSource, /No meeting is claimed without separate verified agent evidence/);
  assert.match(opsSource, /Cycle plans, prep packets, and verified meeting records/);
  assert.match(opsSource, /const verifiedMeeting = isMeetingStandupRecord\(entry\)/);
  assert.match(opsSource, /No server-verified meeting transcripts recorded yet/);
  assert.match(opsSource, /label="Verified Meetings"/);
  assert.doesNotMatch(opsSource, /Create current standup/);
  assert.doesNotMatch(opsSource, /label="Standups Run"/);
});

test('Ops uses the AI Clone server observation for freshness instead of browser time', () => {
  assert.match(opsSource, /const aiCloneObservedAtMs = aiClonePortfolioObservedAtMillis\(portfolioPulse\)/);
  assert.match(opsSource, /schemaVersion !== 'ai_clone_clock\/v1'/);
  assert.match(opsSource, /authority !== 'ai_clone_utc'/);
  assert.match(opsSource, /timezoneName !== 'UTC'/);
  assert.match(opsSource, /checkedAtMs === clockObservedAtMs \? clockObservedAtMs : 0/);
  assert.match(opsSource, /Browser received:/);
  assert.match(opsSource, /System checked .* on the AI Clone UTC clock/);
  assert.match(opsSource, /Card dates below remain their own source, processing, or action times/);
  assert.match(opsSource, /Waiting for the AI Clone server observation time before evaluating meeting freshness/);
  assert.doesNotMatch(opsSource, /Date\.now\(\)/);
});

test('AI Clone UTC labels render the canonical UTC instant, never the owner-calendar projection', () => {
  const compiled = ts.transpileModule(uiDatesSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
  const { formatUiTimestamp, formatUiUtcTimestamp } = moduleRef.exports;
  const observedAt = '2026-09-02T10:15:00.627486Z';

  assert.equal(formatUiTimestamp(observedAt), 'Sep 2, 6:15 AM');
  assert.equal(formatUiUtcTimestamp(observedAt), 'Sep 2, 10:15 AM');
  assert.match(opsSource, /formatUiUtcTimestamp/);
  assert.ok((opsSource.match(/formatUiUtcTimestamp\([^\n]+?\).*AI Clone UTC/g) ?? []).length >= 2);
  assert.doesNotMatch(opsSource, /formatUiTimestamp\([^\n]+?\).*AI Clone UTC/);
});

test('workspace cycle labels never substitute automation execution time for semantic observation', () => {
  const semanticHelpers = opsSource.match(
    /function standupTimeRecord[\s\S]*?(?=\nfunction standupSemanticObservedAtText)/,
  );
  const automationHelper = opsSource.match(
    /function automationCycleSemanticObservedAt[\s\S]*?(?=\nfunction opsProjectionSemanticObservedAt)/,
  );
  const projectionHelper = opsSource.match(
    /function opsProjectionSemanticObservedAt[\s\S]*?(?=\nfunction latestSemanticDailyCycle)/,
  );
  const selectionHelper = opsSource.match(
    /function latestSemanticDailyCycle[\s\S]*?(?=\nfunction latestWorkspaceCycleEvaluations)/,
  );
  assert.ok(semanticHelpers, 'expected semantic ai_clone_utc observation helpers');
  assert.ok(automationHelper, 'expected the automation-cycle observation gate');
  assert.ok(projectionHelper, 'expected the Ops projection observation gate');
  assert.ok(selectionHelper, 'expected semantic daily-cycle selection');
  const compiled = ts.transpileModule(
    `type OpsWorkspaceCycleProjection = Record<string, any>;
     type AutomationRun = { automation_id: string; run_at?: string | null; finished_at?: string | null; metadata?: Record<string, unknown> };
     const timestampMs = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value)) ? Date.parse(value) : 0;
     ${semanticHelpers[0]}\n${automationHelper[0]}\n${projectionHelper[0]}\n${selectionHelper[0]}
     module.exports = { automationCycleSemanticObservedAt, opsProjectionSemanticObservedAt, latestSemanticDailyCycle };`,
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
  ).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
  const { automationCycleSemanticObservedAt, opsProjectionSemanticObservedAt, latestSemanticDailyCycle } = moduleRef.exports;
  const valid = {
    cycle_id: 'daily-2026-08-27@20260827T120000482752Z',
    observed_at: '2026-08-27T12:00:00Z',
    clock: { authority: 'ai_clone_utc', timezone: 'UTC', observed_at: '2026-08-27T12:00:00Z' },
  };

  assert.equal(automationCycleSemanticObservedAt(valid), '2026-08-27T12:00:00.000Z');
  assert.equal(automationCycleSemanticObservedAt({}), null);
  assert.equal(
    automationCycleSemanticObservedAt({
      ...valid,
      observed_at: '2026-08-27T11:59:59Z',
    }),
    null,
  );
  const semanticSelection = latestSemanticDailyCycle([
    {
      automation_id: 'daily_integrated_cycle',
      run_at: '2026-08-28T15:00:00Z',
      metadata: {
        cycle_id: 'daily-2026-08-26@20260826T120000000000Z',
        observed_at: '2026-08-26T12:00:00Z',
        clock: { authority: 'ai_clone_utc', timezone: 'UTC', observed_at: '2026-08-26T12:00:00Z' },
      },
    },
    {
      automation_id: 'daily_integrated_cycle',
      run_at: '2026-08-27T13:00:00Z',
      metadata: {
        cycle_id: 'daily-2026-08-27@20260827T120000000000Z',
        observed_at: '2026-08-27T12:00:00Z',
        clock: { authority: 'ai_clone_utc', timezone: 'UTC', observed_at: '2026-08-27T12:00:00Z' },
      },
    },
    {
      automation_id: 'daily_integrated_cycle',
      run_at: '2026-08-29T13:00:00Z',
      metadata: {
        cycle_id: 'daily-2026-08-29@20260829T120000000000Z',
        observed_at: '2026-08-29T12:00:00Z',
        clock: { authority: 'invalid_clock', timezone: 'UTC', observed_at: '2026-08-29T12:00:00Z' },
      },
    },
  ]);
  assert.equal(semanticSelection.observedAt, '2026-08-27T12:00:00.000Z');
  const validProjection = {
    schema_version: 'ops_standup_summary_conclusion/v3',
    portfolio_cycle_id: 'daily-2026-08-27@20260827T120000482752Z',
    cycle_date: '2026-08-27',
    observed_at: '2026-08-27T12:00:00Z',
    clock: {
      schema_version: 'ai_clone_clock/v1',
      authority: 'ai_clone_utc',
      timezone: 'UTC',
      observed_at: '2026-08-27T12:00:00Z',
    },
  };
  assert.equal(
    opsProjectionSemanticObservedAt(validProjection),
    '2026-08-27T12:00:00.000Z',
  );
  assert.equal(
    opsProjectionSemanticObservedAt({
      ...validProjection,
      cycle_date: '2026-08-26',
    }),
    null,
  );
  assert.equal(
    opsProjectionSemanticObservedAt({
      ...validProjection,
      clock: { ...validProjection.clock, observed_at: '2026-08-27T12:00:01Z' },
    }),
    null,
  );
  assert.equal(
    opsProjectionSemanticObservedAt({
      ...validProjection,
      schema_version: 'ops_standup_summary_conclusion/v2',
    }),
    null,
  );
  assert.equal(
    automationCycleSemanticObservedAt({
      ...valid,
      clock: { authority: 'browser_local', timezone: 'UTC', observed_at: valid.observed_at },
    }),
    null,
  );
  const latestCycle = opsSource.match(/function latestWorkspaceCycleEvaluations[\s\S]*?\n}/);
  assert.ok(latestCycle, 'expected automation evaluation fallback');
  assert.match(latestCycle[0], /latestSemanticDailyCycle\(automationRuns\)/);
  assert.match(opsSource, /opsProjectionSemanticObservedAt\(projection\)/);
  assert.doesNotMatch(opsSource, /typeof projection\.observed_at === 'string' \? projection\.observed_at : null/);
  assert.doesNotMatch(latestCycle[0], /evaluatedAt[^\n]*(?:run_at|finished_at)/);
  assert.match(opsSource, /execution and persistence time were not substituted/);
});

test('meeting ordering and freshness use semantic ai_clone_utc observation, never persistence time', () => {
  const helpers = opsSource.match(/function standupTimeRecord[\s\S]*?(?=\nfunction isMeetingStandupRecord)/);
  assert.ok(helpers, 'expected the bounded standup semantic-time helpers');
  const compiled = ts.transpileModule(
    `type StandupEntry = { payload?: Record<string, unknown>; created_at?: string };\n${helpers[0]}\nmodule.exports = { standupSemanticObservation, standupSemanticObservedAtText, standupObservedAt, standupPersistedAt, compareStandupSemanticObservationDesc };`,
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
  ).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
  const {
    standupSemanticObservation,
    standupSemanticObservedAtText,
    standupObservedAt,
    standupPersistedAt,
    compareStandupSemanticObservationDesc,
  } = moduleRef.exports;

  const delayedOldCycle = {
    payload: {
      recursion: {
        observed_at: '2026-08-25T12:00:00Z',
        clock: { authority: 'ai_clone_utc', observed_at: '2026-08-25T12:00:00Z' },
      },
    },
    created_at: '2026-08-27T12:00:00Z',
  };
  const newerCycle = {
    payload: {
      observed_at: '2026-08-26T12:00:00Z',
      clock: { authority: 'ai_clone_utc', observed_at: '2026-08-26T12:00:00Z' },
    },
    created_at: '2026-08-26T12:05:00Z',
  };
  assert.equal(
    [delayedOldCycle, newerCycle].sort(compareStandupSemanticObservationDesc)[0],
    newerCycle,
    'a delayed persistence of an older cycle must not become the latest meeting',
  );
  assert.equal(standupSemanticObservedAtText(delayedOldCycle), '2026-08-25T12:00:00.000Z');
  assert.equal(standupObservedAt(delayedOldCycle).toISOString(), '2026-08-25T12:00:00.000Z');
  assert.equal(standupPersistedAt(delayedOldCycle).toISOString(), '2026-08-27T12:00:00.000Z');

  const preciseCycleIdentity = {
    payload: {
      cycle_id: 'daily_integrated_cycle@20260826T120000482752Z',
      observed_at: '2026-08-26T12:00:00Z',
      clock: { authority: 'ai_clone_utc', observed_at: '2026-08-26T12:00:00Z' },
    },
    created_at: '2026-08-26T12:05:00Z',
  };
  assert.equal(
    standupSemanticObservedAtText(preciseCycleIdentity),
    '2026-08-26T12:00:00.000Z',
    'the microsecond cycle identity agrees with the explicit receipt on the same second',
  );

  const conflictingCycleIdentity = {
    payload: {
      cycle_id: 'daily_integrated_cycle@20260826T120000482752Z',
      observed_at: '2026-01-01T00:00:00Z',
      clock: { authority: 'ai_clone_utc', observed_at: '2026-01-01T00:00:00Z' },
    },
    created_at: '2026-08-26T12:05:00Z',
  };
  assert.equal(standupSemanticObservedAtText(conflictingCycleIdentity), null);
  assert.equal(
    standupSemanticObservation(conflictingCycleIdentity).reason,
    'conflicting semantic observations',
  );

  const missingObservation = { payload: {}, created_at: '2026-08-27T12:00:00Z' };
  assert.equal(standupSemanticObservedAtText(missingObservation), null);
  assert.equal(standupObservedAt(missingObservation).getTime(), 0);
  assert.equal(standupSemanticObservation(missingObservation).reason, 'missing semantic observation');

  const wrongClock = {
    payload: { observed_at: '2026-08-27T12:00:00Z', clock: { authority: 'browser_local' } },
    created_at: '2026-08-27T12:00:00Z',
  };
  assert.equal(standupSemanticObservation(wrongClock).reason, 'invalid clock authority');
  assert.equal(standupObservedAt(wrongClock).getTime(), 0);

  const conflictingClock = {
    payload: {
      observed_at: '2026-08-27T12:00:00Z',
      recursion: { observed_at: '2026-08-27T13:00:00Z' },
    },
    created_at: '2026-08-27T14:00:00Z',
  };
  assert.equal(standupSemanticObservation(conflictingClock).reason, 'conflicting semantic observations');
  assert.equal(standupObservedAt(conflictingClock).getTime(), 0);
});

test('meeting week, latency, and latest-room selection stay on semantic observations', () => {
  assert.doesNotMatch(opsSource, /standupCreatedAt/);
  assert.doesNotMatch(opsSource, /standupSemanticObservedAtText\(entry\) \?\? timezoneAwareStandupTimestamp\(entry\.created_at\)/);
  assert.doesNotMatch(opsSource, /new Date\(selectedEntry\.created_at\)/);
  assert.match(opsSource, /buildStandupEffectivenessSummary\(entries, pmCards, executionQueue, observedAtMs\)/);
  assert.match(opsSource, /ownerCalendarIsoWeekBounds\(new Date\(observedAtMs\)\)/);
  assert.match(opsSource, /observedCalendarDate >= weekBounds\.startKey/);
  assert.match(opsSource, /timestampMs\(gate\.firstExecutionAt\) - standupObservedAt\(gate\.entry\)\.getTime\(\)/);
  assert.match(opsSource, /const sortedEntries = entries[\s\S]*?\.filter\(isMeetingStandupRecord\)[\s\S]*?\.sort\(compareStandupSemanticObservationDesc\)/);
  assert.match(opsSource, /freshness = 'unavailable'/);
  assert.match(opsSource, /persistence time is not substituted/);
  assert.match(opsSource, /clock !== 'semantic_observed_at' && clock !== 'semantic_cycle_observation'/);
  assert.match(opsSource, /semantic observation is unavailable, persistence time is not substituted/);
  assert.match(opsSource, /standupPrepSemanticObservedAtText\(prep\)/);
  assert.doesNotMatch(opsSource, /const prepTime = prep\.generatedAt/);
});

test('meeting calendars project ai_clone_utc into the owner calendar without inventing a clock', () => {
  const helperBlock = opsSource.match(
    /function ownerCalendarDateParts[\s\S]*?(?=\nfunction medianNumber)/,
  );
  assert.ok(helperBlock, 'expected bounded owner-calendar helpers');
  const compiled = ts.transpileModule(
    `const OWNER_CALENDAR_TIME_ZONE = 'America/New_York';
     const ownerCalendarDatePartsFormatter = new Intl.DateTimeFormat('en-US', {
       timeZone: OWNER_CALENDAR_TIME_ZONE,
       year: 'numeric', month: '2-digit', day: '2-digit',
     });
     ${helperBlock[0]}
     module.exports = { ownerCalendarDateKey, ownerCalendarIsoWeekBounds };`,
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
  ).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
  const { ownerCalendarDateKey, ownerCalendarIsoWeekBounds } = moduleRef.exports;

  const sundayEvening = new Date('2026-08-31T00:30:00Z');
  assert.equal(ownerCalendarDateKey(sundayEvening), '2026-08-30');
  assert.deepEqual(ownerCalendarIsoWeekBounds(sundayEvening), {
    startKey: '2026-08-24',
    endKey: '2026-08-30',
  });

  const utcSeptemberOwnerAugust = new Date('2026-09-01T01:00:00Z');
  assert.equal(ownerCalendarDateKey(utcSeptemberOwnerAugust), '2026-08-31');
  assert.match(opsSource, /const key = ownerCalendarDateKey\(date\)/);
  assert.match(opsSource, /const observation = ownerCalendarDateParts\(new Date\(observedAtMs\)\)/);
  assert.doesNotMatch(opsSource, /function startOfAiCloneUtcWeek/);
});

test('standups lead with today and lazy-mount diagnostic and archive detail', () => {
  assert.match(opsSource, /What needs you from the meeting system/);
  assert.match(opsSource, /const \[showMeetingArchive, setShowMeetingArchive\] = useState\(false\)/);
  assert.match(opsSource, /const \[showStoredRecords, setShowStoredRecords\] = useState\(false\)/);
  assert.match(opsSource, /showRoomDiagnostics \? \(/);
  assert.match(opsSource, /showMeetingArchive \? \(/);
  assert.match(opsSource, /entries=\{\[selectedMeetingEntry\]\}/);
  assert.match(opsSource, /Back to compact history/);
});

test('standup diagnostics describe automation inventory truthfully and hide legacy local paths', () => {
  assert.match(opsSource, /label="Automation Definitions"/);
  assert.match(opsSource, /configured jobs, not a health score/);
  assert.doesNotMatch(opsSource, /label="Launchd Loop"/);
  assert.match(opsSource, /function sanitizeLegacyLocalPathsForDisplay/);
  assert.match(opsSource, /Legacy workspace record/);
  assert.match(opsSource, /sanitizedPaths/);
  assert.match(opsSource, /normalizeDisplayText\(\s*sanitizedPaths/);
});

test('strategy-only meetings stay neutral and out of the Today action count', () => {
  const strategyBranch = opsSource.indexOf("if (outputGate.category === 'strategy_only') {");
  const genericOutputBranch = opsSource.indexOf('else if (!outputGate.success) {', strategyBranch);
  assert.ok(strategyBranch >= 0, 'expected a dedicated strategy-only room branch');
  assert.ok(genericOutputBranch > strategyBranch, 'strategy-only classification must precede generic failed-output handling');
  assert.match(opsSource, /status = 'strategy_only'/);
  assert.match(opsSource, /room\.outputCategory !== 'strategy_only'/);
  assert.match(opsSource, /room\.outputCategory === 'strategy_only'/);
});

test('execution gate validation is distinct from exact owner approval', () => {
  const approvalHelper = opsSource.match(
    /function queueEntryRequiresApproval\([^)]*\) \{[\s\S]*?\n\}/,
  );
  assert.ok(approvalHelper, 'expected an exact-approval helper');
  assert.match(
    opsSource,
    /function queueEntryNeedsGateValidation\([\s\S]*execution_gate_authorization_current !== true/,
  );
  assert.match(
    approvalHelper[0],
    /execution_gate_decision === 'REQUIRE_APPROVAL'[\s\S]*execution_gate_approval_state !== 'approved'/,
  );
  assert.match(opsSource, /gateValidationRequired\s*\? 'Validate & queue'/);
  assert.match(opsSource, /Validated the current signed execution gate and queued/);
  assert.doesNotMatch(approvalHelper[0], /execution_gate_authorization_current/);
});
