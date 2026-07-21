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
const promotableSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'PromotableInlineText.tsx'), 'utf8');
const fragmentUtilsSource = fs.readFileSync(path.join(frontendRoot, 'app', 'workspace', 'generatedFragmentUtils.ts'), 'utf8');
const controlApiSource = fs.readFileSync(path.join(frontendRoot, 'lib', 'control-api.ts'), 'utf8');

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
  normalizeWorkspaceReturnUrl,
  readWorkspaceComposerQuery,
  toWorkspaceSourceCard,
} = loadedComposer.exports;

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

test('attaches the source card to both local Codex queue requests', () => {
  const queueRequests = postingSource.match(
    /controlApiPost<LocalCodexJobCreateResponse>\('\/api\/content-generation\/codex-jobs'/g,
  ) ?? [];
  const sourceCardPayloads = postingSource.match(/source_card:\s*sourceCard/g) ?? [];

  assert.equal(queueRequests.length, 2);
  assert.equal(sourceCardPayloads.length, 2);
});

test('the full FEEZIE workspace also preserves structured source identity', () => {
  assert.match(workspaceSource, /readWorkspaceComposerQuery\(searchParams\)/);
  assert.match(workspaceSource, /toWorkspaceSourceCard\(composerQuery\)/);
  const sourceCardPayloads = workspaceSource.match(/source_card:\s*activeSourceCard/g) ?? [];
  assert.equal(sourceCardPayloads.length, 2);
  assert.match(workspaceSource, /origin_type:\s*'feezie_feed_item'/);
  assert.match(workspaceSource, /origin_type:\s*'feezie_weekly_recommendation'/);
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

test('the queue tells the owner that Codex Terminal runs on the Mac', () => {
  assert.match(fragmentUtilsSource, /Codex Terminal is generating the options through the signed-in Codex session on this Mac/);
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
