const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const opsSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'ops', 'OpsClient.tsx'), 'utf8');
const clientLocationSource = fs.readFileSync(path.join(__dirname, '..', 'lib', 'use-client-location.ts'), 'utf8');

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
  assert.match(opsSource, /<PortfolioPulseSection snapshot=\{portfolioPulse\}/);
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
  assert.match(opsSource, /label="Fresh rooms"/);
  assert.match(opsSource, /label="Fresh Transcripts"/);
  assert.match(opsSource, /label="Outcome Clear"/);
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
