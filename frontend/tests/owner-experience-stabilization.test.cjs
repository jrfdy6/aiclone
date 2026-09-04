const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.join(__dirname, '..');
const brainSource = fs.readFileSync(path.join(frontendRoot, 'app', 'brain', 'BrainClient.tsx'), 'utf8');
const opsSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const opsSummarySource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'OpsStandupSummary.tsx'), 'utf8');
const opsOwnerTruthSource = fs.readFileSync(path.join(frontendRoot, 'lib', 'ops-owner-truth.ts'), 'utf8');
const brainPrivacySource = fs.readFileSync(path.join(frontendRoot, 'app', 'brain', 'brainPrivacy.ts'), 'utf8');
const runtimeChromeSource = fs.readFileSync(path.join(frontendRoot, 'components', 'runtime', 'RuntimeChrome.tsx'), 'utf8');
const globalStylesSource = fs.readFileSync(path.join(frontendRoot, 'app', 'globals.css'), 'utf8');
const workspaceSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'WorkspaceClient.tsx'), 'utf8');
const requestWorkSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'RequestWorkForm.tsx'), 'utf8');
const nextConfigSource = fs.readFileSync(path.join(frontendRoot, 'next.config.js'), 'utf8');

test('Ops scopes partial failures without covering healthy capabilities', () => {
  assert.match(opsSource, /const sectionErrorItems = useMemo/);
  assert.match(opsSource, /<TelemetryDegradedNotice items=\{sectionErrorItems\}/);
  assert.match(opsSource, /Other successfully loaded Ops sections remain usable/);
  assert.match(opsSource, /Affected: \{allUnavailable \? 'all live Ops controls and freshness checks'/);
  assert.match(opsSource, /Still available:/);
  assert.match(opsSource, /Why each capability is unavailable/);
  assert.match(opsSource, /ownerSafeFailureExplanation/);
  assert.doesNotMatch(opsSource, /messages\.join\('\s*\|\s*'\)/);
});

test('Ops polling stays read-only and leaves PM maintenance to its automation runner', () => {
  assert.doesNotMatch(opsSource, /review-hygiene\/auto-resolve/);
  assert.doesNotMatch(opsSource, /review-hygiene\/auto-progress/);
  assert.doesNotMatch(opsSource, /owner-review\/sync/);
  assert.match(opsSource, /review-hygiene\/audit\?limit=8&hours=24/);
  assert.match(opsSource, /const interval = setInterval\(loadTelemetry, 60_000\)/);
});

test('Ops distinguishes first load from unavailability and retains last-known projections on refresh failure', () => {
  assert.match(opsSource, /initialTelemetryPending=\{checkedAt === null\}/);
  assert.match(opsSource, /const cycleTruthPending = initialTelemetryPending && !opsProjection/);
  assert.match(opsSource, /Loading the canonical workspace goal from its bounded owner projection/);
  assert.match(opsSource, /No missing-goal conclusion is being made yet/);
  assert.match(opsSource, /No action, failure, or no-change result is being claimed while it loads/);
  assert.match(opsSource, /opsCycle: 'Workspace cycle conclusion'/);
  assert.match(opsSource, /opsGoals: 'Workspace goals'/);
  assert.match(opsSource, /\(error\) => updateSectionError\('opsCycle', toErrorMessage\(error\)\)/);
  assert.match(opsSource, /\(error\) => updateSectionError\('opsGoals', toErrorMessage\(error\)\)/);
  assert.doesNotMatch(opsSource, /setOpsWorkspaceCycle\(null\)/);
  assert.doesNotMatch(opsSource, /setOpsWorkspaceGoals\(null\)/);
});

test('Ops shows bounded real workspace inputs from the governed cycle', () => {
  assert.match(opsOwnerTruthSource, /OpsWorkspaceContextProjection/);
  assert.match(opsOwnerTruthSource, /ops_workspace_context_projection/);
  assert.match(opsOwnerTruthSource, /export function projectOpsWorkspaceContext/);
  assert.match(opsOwnerTruthSource, /artifact\.consumption_role !== 'reference_only'/);
  assert.match(opsSource, /\/api\/workspace\/ops-workspace-context/);
  assert.match(opsSource, /opsContext: 'Workspace cycle source receipts'/);
  assert.match(opsSource, /opsWorkspaceContextState/);
  assert.match(opsSource, /contextPending=\{opsWorkspaceContextState === 'loading' && !opsWorkspaceContext\}/);
  assert.match(opsSource, /data-workspace-consumed-context=\{selectedWorkspaceId\}/);
  assert.match(opsSource, /What AI Clone actually read/);
  assert.match(opsSource, /data-workspace-consumed-artifact-title/);
  assert.match(opsSource, /Read as reference during/);
  assert.match(opsSource, /this is not a completed-work claim, an owner decision, or new Persona evidence/);
  assert.match(opsSource, /source_state === 'verified_preexisting'/);
  assert.match(opsSource, /Current content is not presented as what AI Clone read/);
  assert.match(opsSource, /setOpsWorkspaceContext\(\(current\) => current && current\.state !== 'unavailable' \? current : value\)/);
  assert.doesNotMatch(opsSource, /setOpsWorkspaceContext\(null\)/);
  assert.doesNotMatch(opsSource, /\{primaryConsumedArtifact\.reference\}/);
  assert.doesNotMatch(opsSource, /\{primaryConsumedArtifact\.source_sha256\}/);
});

test('Ops project cards separate current state from historical Dream receipts', () => {
  const pulse = opsSource.match(/function PortfolioPulseSection\([\s\S]*?\n}\n\nfunction PMBoardPanel/);
  assert.ok(pulse, 'expected PortfolioPulseSection');
  assert.match(pulse[0], /Needs you/);
  assert.match(pulse[0], /Active PM/);
  assert.match(pulse[0], /Standup/);
  assert.match(pulse[0], /Shared operating system/);
  assert.match(pulse[0], /contentVisibility: 'auto'/);
  assert.doesNotMatch(pulse[0], /workspaceCycleEvaluationCopy|Cycle checked|Last canonical workspace observation/);
});

test('Ops workspace goals prefer the canonical bounded goal projection and retain cycle fallback', () => {
  assert.match(opsSource, /projectOpsWorkspaceGoals\(opsWorkspaceCycle, opsWorkspaceGoals\)/);
  assert.match(opsSource, /\/api\/workspace\/ops-workspace-goals/);
  assert.match(opsOwnerTruthSource, /ops_workspace_goal_projection\/v1/);
  assert.match(opsOwnerTruthSource, /raw\.schema_version !== 'workspace_goal_contract\/v1'/);
  assert.match(opsOwnerTruthSource, /projection\?\.schema_version !== 'ops_standup_summary_conclusion\/v3'/);
  assert.match(opsOwnerTruthSource, /Array\.isArray\(projection\.workspace_recursion\)/);
  assert.match(opsSource, /const workspaceGoals = useMemo/);
  assert.match(opsSource, /workspaceGoals\.get\(normalizeWorkspaceBoardKey\(workspace\.workspace_key\)\)/);
  assert.match(opsSource, /projectWorkspaceOwnerTruth\(opsProjection, selectedWorkspaceId, goalProjection\)/);
  assert.doesNotMatch(opsSource, /activeCycleEvaluation\?\.goal/);
  assert.match(opsSource, /activeOwnerTruth\.goal \?\? \(initialTelemetryPending/);
  assert.match(opsSource, /The canonical goal is unavailable because its bounded owner projection is not synchronized\. Current cycle status remains usable\./);
  assert.match(opsSource, /activeOwnerTruth\.progressSignals\.join\(' '\)/);
  assert.match(opsSource, /activeOwnerTruth\.phaseGate/);
  assert.match(opsSource, /activeOwnerTruth\.reevaluateWhen/);
  assert.match(opsSource, /Scope: \{activeWorkspace\.description\}/);
});

test('Brain source errors state scope, healthy remainder, and next action', () => {
  assert.match(brainSource, /YouTube source inventory is unavailable/);
  assert.match(brainSource, /Affected: live YouTube discovery only/);
  assert.match(brainSource, /Still available: existing Brain sources, saved transcripts, Persona review, and manual intake/);
  assert.match(brainSource, /Affected: this source&apos;s live lookup and full-coverage claim only/);
  assert.match(brainSource, /do not treat the visible counts as complete/);
  assert.doesNotMatch(brainSource, />\{youtubeWatchlistError\}<\/p>/);
  assert.doesNotMatch(brainSource, /memory_vectors\.last_refreshed_at/);
  assert.doesNotMatch(opsSource, /memory_vectors\.last_refreshed_at/);
});

test('Brain never turns a missing Persona projection into a false zero', () => {
  assert.match(brainSource, /persona_review_available/);
  assert.match(brainSource, /Persona queue projection unavailable/);
  assert.match(brainSource, /Projection unavailable; open Persona for the live queue/);
  assert.doesNotMatch(brainSource, /Pending Review" value=\{verified \? pendingReviewCount \?\? 0/);
});

test('Persona owner guidance hides internal receipt identifiers', () => {
  assert.match(brainSource, /Saved your response as owner evidence in Open Brain/);
  assert.match(brainSource, /nothing became canonical/);
  assert.match(brainSource, /Owner response receipt/);
  assert.doesNotMatch(brainSource, /Saved to Open Brain as capture/);
  assert.doesNotMatch(brainSource, /InlineBadge label=\{`capture \$\{metadataText\(selectedDelta\.metadata, 'resolution_capture_id'\)\}`\}/);
});

test('Persona save confirmation survives automatic advance and names the downstream boundary', () => {
  assert.match(brainSource, /preserveReflectionMessageForDeltaId/);
  assert.match(brainSource, /It is now available in Persona review history/);
  assert.match(brainSource, /The next Dream cycle will not consume it unless you later use an eligible canon or routing action/);
  assert.doesNotMatch(brainSource, /maxHeight: '360px', overflowY: 'auto'/);
});

test('Persona save retries bind one capture to one expected owner-response revision', () => {
  assert.match(brainSource, /resolved_capture_id: resolvedCaptureId/);
  assert.match(brainSource, /expected_owner_response_revision: currentOwnerResponseRevision/);
  assert.match(brainSource, /nextOwnerResponseRevision: currentOwnerResponseRevision \+ 1/);
  assert.match(brainSource, /crypto\?\.subtle/);
  assert.match(brainSource, /persona-review:r\$\{currentOwnerResponseRevision \+ 1\}/);
});

test('Daily Briefs bound history and translate legacy runtime detail for owner guidance', () => {
  assert.match(brainSource, /Older saved briefs/);
  assert.match(brainSource, /normalizeBrainOwnerGuidanceText\(selected\.content_markdown\)/);
  assert.match(brainSource, /Reading, switching dates, and opening details are passive/);
  assert.match(brainPrivacySource, /Internal automation detail is available in Ops System/);
  assert.match(brainPrivacySource, /INTERNAL_UUID_PATTERN/);
  assert.match(brainSource, /dailyBriefSection\(selected\.content_markdown, 'Action Now'\)/);
  assert.match(brainSource, /Read the full saved brief/);
});

test('Docs require explicit selection and keep the initial index bounded', () => {
  assert.match(brainSource, /useState<string>\(''\)/);
  assert.match(brainSource, /filteredDocs\.slice\(0, 12\)/);
  assert.match(brainSource, /Browse all \$\{filteredDocs\.length\} documents/);
  assert.match(brainSource, /Opening or reading one is passive and does not modify canon or create owner evidence/);
});

test('Control-surface chrome stays readable without covering tablet or phone content', () => {
  const tabs = runtimeChromeSource.match(/function RuntimeTabs\([\s\S]*?\n}\n\nfunction ModuleDock/);
  assert.ok(tabs, 'expected RuntimeTabs');
  assert.match(tabs[0], /flexWrap: 'wrap'/);
  assert.doesNotMatch(tabs[0], /overflowX: 'auto'/);
  assert.match(runtimeChromeSource, /className="runtime-tab"/);
  assert.match(runtimeChromeSource, /className="runtime-module-dock"/);
  assert.match(globalStylesSource, /@media \(max-width: 1280px\), \(max-height: 800px\)/);
  assert.match(globalStylesSource, /@media \(max-width: 1024px\)/);
  assert.match(globalStylesSource, /\.runtime-module-dock \{[\s\S]*?position: static !important/);
  assert.match(globalStylesSource, /\.ops-panel-header-meta \{[\s\S]*?flex-direction: row !important/);
  assert.match(opsSource, /className="ops-panel-header-meta"/);
  assert.match(opsSource, /data-ops-portfolio-project-grid="true"[\s\S]*?minmax\(min\(280px, 100%\), 1fr\)/);
  assert.match(opsSource, /data-ops-system-summary-grid="true"[\s\S]*?minmax\(min\(240px, 100%\), 1fr\)/);
});

test('Persona presents one source title and flattens supporting context', () => {
  const activeSourceContext = brainSource.match(/Why this is in review[\s\S]*?Technical provenance and routing hints/);
  assert.ok(activeSourceContext, 'expected active Persona source context');
  assert.doesNotMatch(activeSourceContext[0], />Review the source</);
  assert.doesNotMatch(activeSourceContext[0], /\{sourceTitle\}/);
  assert.match(brainSource, /borderLeft: '2px solid #0e7490'/);
  assert.match(brainSource, /backgroundColor: 'transparent'/);
  assert.match(brainSource, /stackPersonaDetail = viewportWidth < 900/);
  assert.match(brainSource, /minHeight: stackPersonaDetail \? '160px' : compactPersonaChrome \? '72px' : '220px'/);
  assert.match(brainSource, /display: 'contents'/);
  assert.match(brainSource, /Save records one owner-response receipt/);
});

test('local development hydration gets only the CSP exception Next requires', () => {
  assert.match(nextConfigSource, /process\.env\.NODE_ENV === 'development'/);
  assert.match(nextConfigSource, /developmentScriptSource/);
  assert.match(nextConfigSource, /script-src 'self' 'unsafe-inline'/);
});

test('FEEZIE leads with owner truth and defers its dense inventories', () => {
  assert.match(workspaceSource, /data-feezie-owner-orientation="primary"/);
  assert.match(workspaceSource, /No distribution decision is eligible right now/);
  assert.match(workspaceSource, /Viewing this page does not create feedback, Persona evidence, publication evidence, or any native social action/);
  assert.match(workspaceSource, /A previous-cycle comparison is unavailable in this projection/);
  assert.match(workspaceSource, /Do not force a distribution action/);
  assert.match(workspaceSource, /The next Dream cycle consumes canonical source, decision, feedback, and performance artifacts—not this page view or unsaved text/);
  assert.match(workspaceSource, /data-feezie-assisted-review="secondary"/);
  assert.match(workspaceSource, /data-feezie-content-intelligence="secondary"/);
  assert.match(workspaceSource, /secondary to Today&apos;s Distribution and opens only when you choose it/);
});

test('Brain automation status distinguishes current runtime from latest task history', () => {
  assert.match(brainSource, /data-automation-task-failures=/);
  assert.match(brainSource, /historical run evidence; it does not by itself mean the automation contract is stopped/);
  assert.match(brainSource, />Current runtime<\/th>/);
  assert.match(brainSource, />Latest task result<\/th>/);
  assert.match(brainSource, /data-automation-diagnostics="all-jobs"/);
  assert.match(brainSource, /Inspect all automation contracts and bounded run diagnostics/);
});

test('Ops keeps owner truth primary and defers cycle lineage to a bounded audit', () => {
  assert.match(opsSummarySource, /data-ops-owner-summary="primary"/);
  assert.match(opsSummarySource, /data-ops-cycle-audit="secondary"/);
  assert.match(opsSummarySource, /What remains healthy/);
  assert.match(opsSummarySource, /Next Dream consumes/);
  assert.match(opsSummarySource, /ownerSafeOpsText\(decision\.title\)/);
  assert.match(opsSummarySource, /ownerSafeOpsText\(decision\.resolvedChoice\)/);
  assert.match(opsSummarySource, /projectPortfolioOwnerTruth\(data, \[\], goalProjection\)/);
  assert.match(opsSummarySource, /projectWorkspaceOwnerTruth\(data, workspaceKey, goalProjection\)/);
  assert.match(opsOwnerTruthSource, /The current portfolio conclusion is incomplete/);
  assert.match(opsOwnerTruthSource, /will not consume this failed handoff as a completed update/);
  assert.doesNotMatch(opsSummarySource, /WorkspaceRecursionList|Reference only/);
  assert.doesNotMatch(opsSummarySource, /JSON\.stringify\(data\.endpoint_and_subsystem_health/);
});

test('Ops project workspaces keep supporting systems collapsed and FEEZIE links to its full surface', () => {
  assert.match(opsSource, /data-workspace-supporting-details=\{workspace\.id\}/);
  assert.match(opsSource, /data-workspace-supporting-summary="feezie-os"/);
  assert.match(opsSource, /Open FEEZIE workspace/);
  assert.doesNotMatch(opsSource, /<LinkedinWorkspaceSurface/);
});

test('disabled execution intake explains exactly what enables its primary action', () => {
  assert.match(requestWorkSource, /Enter a specific outcome of at least three characters to enable Send to Codex/);
  assert.match(requestWorkSource, /aria-describedby=\{`\$\{fieldId\}-send-guidance`\}/);
  assert.match(requestWorkSource, /Project routing is unavailable, so this work order cannot be sent yet/);
});
