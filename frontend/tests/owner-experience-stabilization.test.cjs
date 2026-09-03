const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.join(__dirname, '..');
const brainSource = fs.readFileSync(path.join(frontendRoot, 'app', 'brain', 'BrainClient.tsx'), 'utf8');
const opsSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const opsSummarySource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'OpsStandupSummary.tsx'), 'utf8');
const brainPrivacySource = fs.readFileSync(path.join(frontendRoot, 'app', 'brain', 'brainPrivacy.ts'), 'utf8');
const runtimeChromeSource = fs.readFileSync(path.join(frontendRoot, 'components', 'runtime', 'RuntimeChrome.tsx'), 'utf8');
const globalStylesSource = fs.readFileSync(path.join(frontendRoot, 'app', 'globals.css'), 'utf8');
const workspaceSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'WorkspaceClient.tsx'), 'utf8');
const requestWorkSource = fs.readFileSync(path.join(frontendRoot, 'app', 'ops', 'RequestWorkForm.tsx'), 'utf8');

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

test('Brain source errors state scope, healthy remainder, and next action', () => {
  assert.match(brainSource, /YouTube source inventory is unavailable/);
  assert.match(brainSource, /Affected: live YouTube discovery only/);
  assert.match(brainSource, /Still available: existing Brain sources, saved transcripts, Persona review, and manual intake/);
  assert.match(brainSource, /Affected: this source&apos;s live lookup and full-coverage claim only/);
  assert.match(brainSource, /do not treat the visible counts as complete/);
  assert.doesNotMatch(brainSource, />\{youtubeWatchlistError\}<\/p>/);
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

test('Control-surface tabs wrap on phones instead of hiding behind horizontal scrolling', () => {
  const tabs = runtimeChromeSource.match(/function RuntimeTabs\([\s\S]*?\n}\n\nfunction ModuleDock/);
  assert.ok(tabs, 'expected RuntimeTabs');
  assert.match(tabs[0], /flexWrap: 'wrap'/);
  assert.doesNotMatch(tabs[0], /overflowX: 'auto'/);
  assert.match(runtimeChromeSource, /className="runtime-module-dock"/);
  assert.match(globalStylesSource, /@media \(max-width: 640px\)/);
  assert.match(globalStylesSource, /\.runtime-module-dock \{[\s\S]*?position: static !important/);
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
  assert.match(opsSummarySource, /ownerText\(decision\.title\)/);
  assert.match(opsSummarySource, /ownerText\(decision\.resolvedChoice\)/);
  assert.match(opsSummarySource, /uniqueOwnerItems/);
  assert.match(opsSummarySource, /explicitDreamInput/);
  assert.match(opsSummarySource, /Still available: loaded workspace goals/);
  assert.match(opsSummarySource, /do not treat this cycle as a portfolio all-clear/);
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
