const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const sourcePath = path.join(__dirname, '..', 'lib', 'integrated-content-owner-actions.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleValue = { exports: {} };
new Function('module', 'exports', 'URL', compiled)(moduleValue, moduleValue.exports, URL);
const {
  buildLearningActionPayload,
  buildManualEditPayload,
  buildPersonaReversalPayload,
  resolveOwnerPostThesis,
} = moduleValue.exports;

const SHA = 'a'.repeat(64);
const NOW = Date.parse('2026-08-20T16:00:00.000Z');

function opportunity(overrides = {}) {
  return {
    opportunity_id: 'opportunity-1',
    thesis: 'Use the synthesized thesis.',
    status: 'qualified',
    truth_state: 'pass',
    safety_state: 'owner_review_required',
    attribution_state: 'required',
    synthesis: { evidence_ids: ['evidence-1'], interpretation_ids: ['interpretation-1'] },
    lineage: { source_ids: ['source-1'], post_id: null },
    ...overrides,
  };
}

test('owner-post requests reuse an eligible synthesized thesis and never replace a blocked synthesis manually', () => {
  assert.deepEqual(
    resolveOwnerPostThesis('source-1', [opportunity()], 'Ignore this manual replacement'),
    {
      mode: 'synthesized',
      thesis: 'Use the synthesized thesis.',
      opportunityId: 'opportunity-1',
      blocker: null,
    },
  );
  const blocked = resolveOwnerPostThesis(
    'source-1',
    [opportunity({ truth_state: 'blocked' })],
    'Do not bypass the truth gate',
  );
  assert.equal(blocked.mode, 'blocked');
  assert.equal(blocked.thesis, null);
  assert.match(blocked.blocker, /truth blocked/);
  assert.deepEqual(resolveOwnerPostThesis('source-1', [], '  Manual   thesis  '), {
    mode: 'manual',
    thesis: 'Manual thesis',
    opportunityId: null,
    blocker: null,
  });
});

test('manual-edit payload binds exact parent bytes and one approved edit classification', () => {
  assert.deepEqual(buildManualEditPayload({
    postId: 'post-1',
    parentRevisionId: 'revision-1',
    parentBody: 'Original copy',
    body: '  Edited copy  ',
    editClassification: 'voice',
  }), {
    post_id: 'post-1',
    parent_revision_id: 'revision-1',
    body: 'Edited copy',
    edit_classification: 'voice',
  });
  assert.throws(() => buildManualEditPayload({
    postId: 'post-1',
    parentRevisionId: 'revision-1',
    parentBody: 'Same copy',
    body: ' Same copy ',
    editClassification: 'voice',
  }), /must change/);
  assert.throws(() => buildManualEditPayload({
    postId: 'post-1',
    parentRevisionId: 'revision-1',
    parentBody: 'Original',
    body: 'Edited',
    editClassification: '',
  }), /Choose why/);
});

test('learning-action payloads are event-specific and exact-revision-bound', () => {
  assert.deepEqual(buildLearningActionPayload({
    postId: 'post-1', revisionId: 'revision-2', eventKind: 'variant_selected',
    revisionSha256: SHA, ownerConfirmed: true, nowMs: NOW,
  }), {
    post_id: 'post-1', revision_id: 'revision-2', event_kind: 'variant_selected',
    revision_sha256: SHA, owner_confirmed: true,
  });
  assert.deepEqual(buildLearningActionPayload({
    postId: 'post-1', revisionId: 'revision-2', eventKind: 'owner_approved',
    revisionSha256: SHA, ownerConfirmed: true, eventAt: '2026-08-20T15:00:00Z', nowMs: NOW,
    integrityConfirmation: { truth: true, safety: true, privacy: true, attribution: true },
  }), {
    post_id: 'post-1', revision_id: 'revision-2', event_kind: 'owner_approved',
    revision_sha256: SHA, owner_confirmed: true,
    event_at: '2026-08-20T15:00:00.000Z',
    integrity_confirmation: { truth: true, safety: true, privacy: true, attribution: true },
  });
  assert.deepEqual(buildLearningActionPayload({
    postId: 'post-1', revisionId: 'revision-2', eventKind: 'publication_confirmed',
    revisionSha256: SHA, ownerConfirmed: true, eventAt: '2026-08-20T15:30:00Z', nowMs: NOW,
    platform: 'linkedin', publicUrl: 'https://www.linkedin.com/posts/example-123',
  }), {
    post_id: 'post-1', revision_id: 'revision-2', event_kind: 'publication_confirmed',
    revision_sha256: SHA, owner_confirmed: true,
    event_at: '2026-08-20T15:30:00.000Z', platform: 'linkedin',
    public_url: 'https://www.linkedin.com/posts/example-123',
  });
});

test('learning-action payloads fail closed on missing confirmation, integrity, time, hash, or native URL', () => {
  const base = {
    postId: 'post-1', revisionId: 'revision-2', eventKind: 'owner_approved',
    revisionSha256: SHA, ownerConfirmed: true, eventAt: '2026-08-20T15:00:00Z', nowMs: NOW,
    integrityConfirmation: { truth: true, safety: true, privacy: true, attribution: true },
  };
  assert.throws(() => buildLearningActionPayload({ ...base, ownerConfirmed: false }), /explicit owner/);
  assert.throws(() => buildLearningActionPayload({ ...base, revisionSha256: 'not-a-sha' }), /SHA-256/);
  assert.throws(() => buildLearningActionPayload({
    ...base,
    integrityConfirmation: { truth: true, safety: false, privacy: true, attribution: true },
  }), /all four|truth, safety/);
  assert.throws(() => buildLearningActionPayload({ ...base, eventAt: '2026-08-20T17:00:00Z' }), /future/);
  assert.throws(() => buildLearningActionPayload({
    ...base,
    eventKind: 'publication_confirmed',
    platform: 'instagram',
    publicUrl: 'https://www.linkedin.com/posts/wrong-platform',
  }), /Instagram item/);
  assert.throws(() => buildLearningActionPayload({
    ...base,
    eventKind: 'publication_confirmed',
    platform: 'linkedin',
    publicUrl: ['https://', 'owner', ':', 'secret', '@', 'www.linkedin.com/posts/credential-bearing'].join(''),
  }), /LinkedIn item/);
});

test('persona reversal binds the exact versioned promotion and explicit owner reason', () => {
  assert.deepEqual(buildPersonaReversalPayload({
    promotionId: 'promotion-1',
    personaCandidateId: 'candidate-1',
    canonVersion: 'automatic-v1:candidate-1',
    reason: '  This pattern reflected a one-off campaign.  ',
    ownerConfirmed: true,
  }), {
    promotion_id: 'promotion-1',
    persona_candidate_id: 'candidate-1',
    canon_version: 'automatic-v1:candidate-1',
    reason: 'This pattern reflected a one-off campaign.',
    owner_confirmed: true,
  });
  assert.throws(() => buildPersonaReversalPayload({
    promotionId: 'promotion-1', personaCandidateId: 'candidate-1',
    canonVersion: 'v1', reason: '', ownerConfirmed: true,
  }), /Explain why/);
  assert.throws(() => buildPersonaReversalPayload({
    promotionId: 'promotion-1', personaCandidateId: 'candidate-1',
    canonVersion: 'v1', reason: 'Reason', ownerConfirmed: false,
  }), /explicit owner/);
});
