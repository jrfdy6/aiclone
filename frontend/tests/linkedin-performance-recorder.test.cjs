const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const frontendRoot = path.join(__dirname, '..');
const componentPath = path.join(frontendRoot, 'app', 'workspace', 'LinkedinPerformanceRecorder.tsx');
const source = fs.readFileSync(componentPath, 'utf8');

test('LinkedIn performance recorder is valid TSX and exposes every canonical lifecycle event', () => {
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    reportDiagnostics: true,
  });
  const errors = (compiled.diagnostics || []).filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error);
  assert.deepEqual(errors, []);

  for (const eventType of [
    'owner_reviewed',
    'publication_confirmed',
    'metrics_24h_recorded',
    'metrics_7d_recorded',
    'owner_assessment_recorded',
  ]) {
    assert.match(source, new RegExp(`['\"]${eventType}['\"]`));
  }
});

test('recorder uses the explicit rollback-only Railway-to-local event and status endpoints', () => {
  assert.match(source, /controlApiPost<QueueResponse>\(\s*['"]\/api\/workspace\/linkedin-performance\/events\?legacy_compatibility=true['"]/s);
  assert.match(source, /ROLLBACK-ONLY · SIGNED TRANSPORT/);
  assert.match(source, /Canonical posts record learning in the integrated content portfolio/);
  assert.match(source, /controlApiGet<LinkedinPerformanceJob>\(\s*`\/api\/workspace\/linkedin-performance\/jobs\/\$\{encodeURIComponent\(cardId\)\}`/s);
  assert.match(source, /data-performance-job-status/);
  for (const status of ['queued', 'running', 'completed', 'failed']) {
    assert.match(source, new RegExp(`status === ['\"]${status}['\"]`));
  }
});

test('recorder never accepts or sends raw copy or private notes', () => {
  assert.doesNotMatch(source, /<textarea\b/i);
  const payloadBuilder = source.slice(source.indexOf('function buildPayload()'), source.indexOf('async function submit'));
  assert.ok(payloadBuilder.length > 500, 'expected to isolate the payload builder');
  assert.doesNotMatch(payloadBuilder, /\bcopy_text\s*:/);
  assert.doesNotMatch(payloadBuilder, /\bnotes\s*:/);
  assert.match(source, /Raw post copy and private notes are never accepted or sent/);
  assert.match(source, /content_version_sha256: normalizeDigest\(form\.digest\)/);
});

test('recorder enforces approval completion and observation windows before queueing', () => {
  assert.match(source, /completed approval receipt for this exact content ID and digest is required first/);
  assert.match(source, /eventType === 'publication_confirmed' && !approvalCompleted/);
  assert.match(source, /observedApprovalKey === currentIdentity/);
  assert.match(source, /next\.status === 'completed'/);
  assert.match(source, /setObservedApprovalKey\(submittedContext\.identity\)/);
  assert.match(source, /eventType === 'metrics_24h_recorded' \? 24 : 168/);
  assert.match(source, /windowHours \* 3_600_000/);
  assert.match(source, /browser entry alone cannot establish publication truth/);
  assert.match(source, /This records evidence only for the explicitly enabled legacy compatibility lane\. It cannot draft, schedule, or publish/);
});

test('metrics reference timestamp stays browser-only', () => {
  const metricBranch = source.slice(
    source.indexOf("if (eventType === 'metrics_24h_recorded' || eventType === 'metrics_7d_recorded')", source.indexOf('function buildPayload()')),
    source.indexOf('const outcomeCounts', source.indexOf('function buildPayload()')),
  );
  assert.ok(metricBranch.length > 200, 'expected to isolate the metrics payload branch');
  assert.doesNotMatch(metricBranch, /published_at\s*:/);
  assert.doesNotMatch(metricBranch, /referencePublishedAt\s*:/);
  assert.match(source, /Browser-only time-window check; this value is not sent in the metrics payload/);
});

test('banked-post seeds update safely and trusted classification is canonicalized', () => {
  assert.match(source, /initialClassification\?: LinkedinPerformanceInitialClassification/);
  for (const field of [
    'pillarId',
    'intent',
    'treatment',
    'careerSignal',
    'employerSafety',
    'proofPosture',
    'hookFamily',
    'format',
    'audience',
    'experimentId',
  ]) {
    assert.match(source, new RegExp(`${field}\\?:`));
  }
  assert.match(source, /appliedSeedToken\.current === externalSeedToken \|\| inFlight/);
  assert.match(source, /contentId: seed\.identityProvided \? seed\.contentId \?\? '' : current\.contentId/);
  assert.match(source, /digest: seed\.identityProvided \? seed\.digest \?\? '' : current\.digest/);
  assert.match(source, /careerSignal: PILLAR_CAREER_SIGNAL\[pillarId\]/);
  assert.match(source, /Career signal must match the owner-approved canonical pillar contract/);
});
