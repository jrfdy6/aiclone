const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const helperPath = path.join(__dirname, '..', 'app', 'brain', 'personaReviewMobile.ts');
const helperSource = fs.readFileSync(helperPath, 'utf8');
const clientSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'brain', 'BrainClient.tsx'), 'utf8');
const nextConfigSource = fs.readFileSync(path.join(__dirname, '..', 'next.config.js'), 'utf8');
const compiled = ts.transpileModule(helperSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loadedModule, loadedModule.exports, require);

const {
  adjacentPersonaReviewDeltaId,
  findPersonaReviewPosition,
  groupPersonaReviewDeltas,
  nextPersonaReviewSourceDeltaId,
  personaResponsePlaceholder,
  resolvePersonaReviewSelection,
  youtubeThumbnailUrl,
  youtubeVideoId,
} = loadedModule.exports;

test('response categories provide unsaved guidance without supplying owner evidence', () => {
  assert.match(personaResponsePlaceholder('agree'), /agree with, and why/i);
  assert.match(personaResponsePlaceholder('disagree'), /disagree with, and why/i);
  assert.match(personaResponsePlaceholder('nuance'), /nuance or qualification/i);
  assert.match(personaResponsePlaceholder('story'), /real personal story/i);
  assert.match(personaResponsePlaceholder('language'), /wording sounds more like you/i);
  const queueTemplateStart = clientSource.indexOf('function queueTemplate');
  const queueTemplateEnd = clientSource.indexOf('function seedSourceDecision', queueTemplateStart);
  const queueTemplateSource = clientSource.slice(queueTemplateStart, queueTemplateEnd);
  assert.match(queueTemplateSource, /setSelectedResponseKind\(kind\)/);
  assert.doesNotMatch(queueTemplateSource, /setReflectionText/);
  assert.equal((clientSource.match(/placeholder=\{personaResponsePlaceholder\(selectedResponseKind\)\}/g) || []).length, 2);
});

test('an empty Persona batch cannot masquerade as an empty ingestion backlog', () => {
  assert.match(clientSource, /No review cards are currently loaded\./);
  assert.match(clientSource, /This is not an empty-source claim\./);
  assert.match(clientSource, /sources awaiting transcripts remain in the ingestion backlog\./);
  assert.match(clientSource, /Refresh Persona Queue on Mac/);
});

function delta(id, metadata = {}, createdAt = '2026-08-24T12:00:00Z') {
  return { id, created_at: createdAt, metadata };
}

test('groups long-form claims by their existing source identity and orders segments', () => {
  const deltas = [
    delta('claim-2', { review_source: 'long_form_media.segment', source_asset_id: 'video-a', segment_index: 2 }),
    delta('single', { review_source: 'brain.persona.ui', source_asset_id: 'video-a' }),
    delta('claim-1', { review_source: 'long_form_media.segment', source_asset_id: 'video-a', segment_index: 1 }),
    delta('article-1', { review_source: 'long_form_media.segment', source_url: 'https://example.com/article', segment_index: 1 }),
  ];

  const groups = groupPersonaReviewDeltas(deltas);

  assert.equal(groups.length, 3);
  assert.deepEqual(groups[0].deltas.map((item) => item.id), ['claim-1', 'claim-2']);
  assert.deepEqual(groups[1].deltas.map((item) => item.id), ['single']);
  assert.deepEqual(groups[2].deltas.map((item) => item.id), ['article-1']);
});

test('advances claim to claim and then source to source', () => {
  const groups = groupPersonaReviewDeltas([
    delta('claim-1', { review_source: 'long_form_media.segment', source_asset_id: 'video-a', segment_index: 1 }),
    delta('claim-2', { review_source: 'long_form_media.segment', source_asset_id: 'video-a', segment_index: 2 }),
    delta('article-1', { review_source: 'long_form_media.segment', source_asset_id: 'article-a', segment_index: 1 }),
  ]);

  assert.equal(adjacentPersonaReviewDeltaId(groups, 'claim-1', 'next'), 'claim-2');
  assert.equal(adjacentPersonaReviewDeltaId(groups, 'claim-2', 'next'), 'article-1');
  assert.equal(adjacentPersonaReviewDeltaId(groups, 'article-1', 'previous'), 'claim-2');
  assert.equal(adjacentPersonaReviewDeltaId(groups, 'article-1', 'next'), null);
  assert.deepEqual(findPersonaReviewPosition(groups, 'claim-2'), {
    sourceIndex: 0,
    claimIndex: 1,
    source: groups[0],
  });
  assert.equal(nextPersonaReviewSourceDeltaId(groups, 'claim-1'), 'article-1');
  assert.equal(nextPersonaReviewSourceDeltaId(groups, 'claim-2'), 'article-1');
  assert.equal(nextPersonaReviewSourceDeltaId(groups, 'article-1'), null);
});

test('pins the intended next claim while a saved claim leaves the active queue', () => {
  const nextSource = delta('article-1', {
    review_source: 'long_form_media.segment',
    source_asset_id: 'article-a',
    segment_index: 1,
  });
  const nextClaim = delta('claim-2', {
    review_source: 'long_form_media.segment',
    source_asset_id: 'video-a',
    segment_index: 2,
  });

  assert.equal(resolvePersonaReviewSelection([nextSource, nextClaim], 'saved-claim', 'claim-2')?.id, 'claim-2');
  assert.equal(resolvePersonaReviewSelection([nextSource, nextClaim], 'saved-claim', null), null);
  assert.equal(resolvePersonaReviewSelection([nextSource, nextClaim], 'missing-claim')?.id, 'article-1');
});

test('derives safe YouTube thumbnail URLs from supported public video URLs', () => {
  assert.equal(youtubeVideoId('https://www.youtube.com/watch?v=abc123'), 'abc123');
  assert.equal(youtubeVideoId('https://youtu.be/short456?t=10'), 'short456');
  assert.equal(youtubeVideoId('https://youtube.com/shorts/clip789'), 'clip789');
  assert.equal(youtubeVideoId('https://example.com/watch?v=nope'), null);
  assert.equal(youtubeThumbnailUrl('https://youtube.com/watch?v=abc123'), 'https://i.ytimg.com/vi/abc123/hqdefault.jpg');
});

test('Persona keeps the approved iPhone review inside the existing surface', () => {
  assert.match(clientSource, /const usePersonaPhoneLayout = viewportWidth <= PERSONA_PHONE_MAX_WIDTH/);
  assert.match(clientSource, /aria-label="Persona mobile review"/);
  assert.match(clientSource, /height: 'min\(660px, calc\(100dvh - 184px\)\)'/);
  assert.match(clientSource, /groupPersonaReviewDeltas\(reviewQueue\)/);
  assert.match(clientSource, /onTouchStart=/);
  assert.match(clientSource, /onTouchEnd=/);
  assert.match(clientSource, /Review details · \{selectedPromotionItems\.length\} selected/);
  assert.match(clientSource, /Save & next \$\{mobileAdvanceLabel\}/);
  assert.match(clientSource, /complete_review: advanceAfterSave/);
  assert.match(clientSource, /resolvePersonaReviewSelection\(reviewQueue, selectedDeltaId, pendingPersonaAdvanceDeltaId\)/);
  assert.match(clientSource, /setPendingPersonaAdvanceDeltaId\(options\.nextDeltaId \?\? null\)/);
  assert.match(clientSource, /nextDraft\?\.reflectionText\.trim\(\) === effectiveReflection\.trim\(\)/);
  assert.match(clientSource, /expected next \$\{advanceNoun\} changed during refresh/);
  assert.match(clientSource, /no different source was selected automatically/);
  assert.match(clientSource, /aiclone\.brain\.persona-review-drafts\.v1/);
  assert.match(clientSource, /excluded from canon, Dream, and learning/);
  assert.match(clientSource, />\s*Skip claim\s*</);
  assert.match(clientSource, />\s*Skip source\s*</);
  assert.match(clientSource, /Skip records no opinion\. The source stays attributed external knowledge\./);
  const skipStart = clientSource.indexOf("async function skipPersonaReview(scope: 'claim' | 'source')");
  const skipEnd = clientSource.indexOf('async function saveMobilePersonaReview()', skipStart);
  assert.ok(skipStart >= 0 && skipEnd > skipStart);
  const skipSource = clientSource.slice(skipStart, skipEnd);
  assert.match(skipSource, /\/api\/brain\/persona-review\/\$\{encodeURIComponent\(selectedDelta\.id\)\}\/skip/);
  assert.match(skipSource, /owner_evidence_created !== false/);
  assert.match(skipSource, /nextPersonaSourceDeltaId/);
  assert.doesNotMatch(skipSource, /\/api\/capture\//);
  assert.match(clientSource, /reviewPurpose === 'source_reaction'/);
  assert.match(clientSource, /persona\/deltas\?limit=100&view=brain_queue/);
  const mobileQueueStart = clientSource.indexOf("mobilePersonaSheet === 'queue' ?");
  const mobileQueueEnd = clientSource.indexOf("                  ) : (", mobileQueueStart);
  assert.ok(mobileQueueStart >= 0 && mobileQueueEnd > mobileQueueStart);
  const mobileQueueSource = clientSource.slice(mobileQueueStart, mobileQueueEnd);
  assert.match(mobileQueueSource, /Refresh Persona Queue on Mac/);
  assert.match(mobileQueueSource, /personaRefreshState\.tone === 'success' \? 'status' : 'alert'/);
  assert.match(clientSource, /const sourceDisplayExcerpt = normalizeBrainDisplayText/);
  assert.match(clientSource, /flexDirection: 'column'/);
  assert.doesNotMatch(clientSource, /minHeight: '100px',[\s\S]{0,220}alignContent: 'center'/);
  assert.doesNotMatch(clientSource, /Perspective Inbox/);
  assert.match(clientSource, /effectivePromotionItems\.map\(promotionItemRequestPayload\)/);
  assert.match(clientSource, /function promotionItemRequestPayload\(item: PromotionItem\)/);
  assert.doesNotMatch(clientSource, /selected_promotion_items: effectivePromotionItems,/);
});

test('YouTube previews use the configured optimized image host', () => {
  assert.match(clientSource, /<Image src=\{sourceThumbnailUrl\}/);
  assert.match(nextConfigSource, /hostname: 'i\.ytimg\.com'/);
  assert.match(nextConfigSource, /pathname: '\/vi\/\*\*'/);
});
