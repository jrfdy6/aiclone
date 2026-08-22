const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const frontendRoot = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(frontendRoot, relativePath), 'utf8');
}

test('prospect pipeline consumes the versioned envelope and exposes degraded state', () => {
  const source = read('app/prospects/page.tsx');

  assert.match(source, /schema_version: 'prospect_pipeline\/v1'/);
  assert.match(source, /apiFetch\(`\/api\/prospects\/\?\$\{params\.toString\(\)\}`\)/);
  assert.match(source, /pipelineState\.state !== 'ready'/);
  assert.match(source, /canonical writes still target/);
  assert.match(source, /apiFetch\(`\/api\/prospects\/\$\{prospectId\}`/);
  assert.doesNotMatch(source, /dev-user|NEXT_PUBLIC_API_URL/);
});

test('prospect discovery distinguishes preview from explicit canonical save', () => {
  const source = read('app/prospect-discovery/page.tsx');

  assert.match(source, /save_to_prospects: saveToProspects/);
  assert.match(source, /apiFetch\('\/api\/prospects\/'/);
  assert.match(source, /source: `discovery:\$\{p\.source\}`/);
  assert.match(source, /saved_count/);
  assert.doesNotMatch(source, /user_id: 'dev-user'/);
});

test('Drive import uses the mounted authenticated route and exact collection allowlist', () => {
  const source = read('app/jumpstart/page.tsx');

  assert.match(source, /apiFetch\('\/api\/ingest\/drive'/);
  assert.match(source, /target_collection: 'knowledge_docs'/);
  assert.match(source, /dry_run: dryRun/);
  assert.match(source, /X-AI-Clone-Firestore-State/);
  assert.doesNotMatch(source, /\/api\/ingest_drive|NEXT_PUBLIC_API_URL|user_id/);
});

test('topic intelligence lets the backend bind the configured owner', () => {
  const source = read('app/topic-intelligence/page.tsx');

  assert.match(source, /apiFetch\('\/api\/topic-intelligence\/run'/);
  assert.doesNotMatch(source, /user_id:\s*'dev-user'/);
});

test('legacy prospecting URL redirects to the canonical owner prospect surface', () => {
  const source = read('app/prospecting/page.tsx');

  assert.match(source, /redirect\('\/prospects'\)/);
  assert.doesNotMatch(source, /NEXT_PUBLIC_API_URL|manual\/prompts|upload-analysis|dev-user/);
});
