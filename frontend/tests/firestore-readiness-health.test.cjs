const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.resolve(__dirname, '..');
const opsSource = fs.readFileSync(path.join(frontendRoot, 'app/ops/OpsClient.tsx'), 'utf8');
const normalizerSource = fs.readFileSync(path.join(frontendRoot, 'lib/firestore-readiness.ts'), 'utf8');

test('Ops reads Firestore readiness only through the authenticated same-origin control proxy', () => {
  assert.match(opsSource, /controlApiGet<unknown>\('\/api\/system\/firestore-readiness'/);
  assert.match(opsSource, /normalizeFirestoreReadinessReceipt\(value\)/);
  assert.doesNotMatch(opsSource, /FIREBASE_SERVICE_ACCOUNT|firebase-admin|google\.cloud/);
  assert.match(opsSource, /<FirestoreReadinessPanel/);
});

test('owner health view exposes every retained role without document data', () => {
  assert.match(opsSource, /Read-only live readiness/);
  assert.match(opsSource, /No document bodies or identifiers are returned to this view/);
  assert.match(opsSource, /receipt\.passedCheckCount/);
  assert.match(opsSource, /check\.scope === 'collection_group'/);
  assert.match(opsSource, /live reads unverified/);
  assert.match(opsSource, /firestoreReadiness\.passedCheckCount/);
  assert.doesNotMatch(opsSource, /check\.(?:document|documentId|payload|body|providerError)/);
});

test('browser normalizer is a closed allowlist for schema, collections, and reason codes', () => {
  assert.match(normalizerSource, /firestore_retained_role_readiness\/v1/);
  assert.match(normalizerSource, /EXPECTED_CHECKS/);
  for (const collection of [
    'activity_logs',
    'knowledge_docs',
    'playbooks',
    'research_insights',
    'research_tasks',
    'system_logs',
    'memory_chunks',
    'ingest_jobs',
    'prospect_discoveries',
    'prospects',
    'topic_intelligence',
  ]) {
    assert.match(normalizerSource, new RegExp(`collection: '${collection}'`));
  }
  assert.match(normalizerSource, /SAFE_REASON_CODES/);
  assert.match(normalizerSource, /firestore_readiness_invalid/);
  assert.doesNotMatch(normalizerSource, /\.\.\.source|\.\.\.raw/);
});
