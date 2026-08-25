const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const sourcePath = path.join(__dirname, '..', 'app', 'brain', 'brainNavigation.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const displayPrivacySource = fs.readFileSync(path.join(__dirname, '..', 'lib', 'display-privacy.ts'), 'utf8');
const privacySource = fs.readFileSync(path.join(__dirname, '..', 'app', 'brain', 'brainPrivacy.ts'), 'utf8');
const clientSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'brain', 'BrainClient.tsx'), 'utf8');
const pageSource = fs.readFileSync(path.join(__dirname, '..', 'app', 'brain', 'page.tsx'), 'utf8');
const packageJson = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
const repoRoot = path.join(__dirname, '..', '..');
const deployScriptPath = path.join(repoRoot, 'scripts', 'deploy_railway_service.sh');
const deployScript = fs.existsSync(deployScriptPath) ? fs.readFileSync(deployScriptPath, 'utf8') : null;
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loadedModule, loadedModule.exports, require);
const compiledDisplayPrivacy = ts.transpileModule(displayPrivacySource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedDisplayPrivacyModule = { exports: {} };
new Function('module', 'exports', 'require', compiledDisplayPrivacy)(
  loadedDisplayPrivacyModule,
  loadedDisplayPrivacyModule.exports,
  require,
);
const compiledPrivacy = ts.transpileModule(privacySource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loadedPrivacyModule = { exports: {} };
new Function('module', 'exports', 'require', compiledPrivacy)(
  loadedPrivacyModule,
  loadedPrivacyModule.exports,
  (request) => request === '@/lib/display-privacy' ? loadedDisplayPrivacyModule.exports : require(request),
);
const {
  buildBrainSectionHref,
  lifecycleViewForDeltaStage,
  parseBrainLocation,
  personaDeltaElementId,
} = loadedModule.exports;
const { normalizeBrainDisplayText } = loadedPrivacyModule.exports;

test('persona delta query opens the persona surface', () => {
  assert.deepEqual(parseBrainLocation('?delta_id=delta-123', ''), {
    tab: 'persona',
    deltaId: 'delta-123',
  });
});

test('known section hash wins while preserving a requested delta', () => {
  assert.deepEqual(parseBrainLocation('?delta_id=delta-123', '#brain-section-docs'), {
    tab: 'docs',
    deltaId: 'delta-123',
  });
  assert.deepEqual(parseBrainLocation('', '#brain-section-briefs'), {
    tab: 'briefs',
    deltaId: null,
  });
});

test('unknown hashes fall back safely', () => {
  assert.deepEqual(parseBrainLocation('', '#unexpected'), { tab: 'dashboard', deltaId: null });
  assert.deepEqual(parseBrainLocation('?delta_id=%20', '#brain-section-unknown'), {
    tab: 'dashboard',
    deltaId: null,
  });
});

test('section links retain the current query string', () => {
  assert.equal(
    buildBrainSectionHref('persona', '?delta_id=delta-123&from=ops'),
    '/brain?delta_id=delta-123&from=ops#brain-section-persona',
  );
  assert.equal(buildBrainSectionHref('dashboard'), '/brain#brain-section-dashboard');
});

test('persona lifecycle stages map to the correct audit view', () => {
  assert.equal(lifecycleViewForDeltaStage('pending_promotion'), 'pending_promotion');
  assert.equal(lifecycleViewForDeltaStage('workspace_saved'), 'workspace_saved');
  assert.equal(lifecycleViewForDeltaStage('committed'), 'committed');
  assert.equal(lifecycleViewForDeltaStage('approved_unpromoted'), 'resolved');
  assert.equal(lifecycleViewForDeltaStage('brain_pending_review'), null);
});

test('delta element ids encode unsafe identifier characters', () => {
  assert.equal(personaDeltaElementId('delta/123?x'), 'brain-persona-delta-delta%2F123%3Fx');
});

test('loads Brain docs through authenticated backend contracts only', () => {
  assert.match(clientSource, /fetchFreshJson<BrainDocsIndexPayload>\('\/api\/brain\/docs'/);
  assert.match(clientSource, /controlApiGet<DocEntry>\(`\/api\/brain\/docs\/content\?path=/);
  assert.doesNotMatch(clientSource, /\/api\/brain-docs/);
  assert.doesNotMatch(pageSource, /loadBrainDocIndex/);
  assert.doesNotMatch(pageSource, /loadPersonaWorkspace/);
  assert.match(clientSource, /findPersonaDocForTarget\(docs, contextTargetFile\)/);
  assert.match(clientSource, /Loading the matching canon file through authenticated Brain Docs/);
  assert.match(clientSource, /normalizeBrainDisplayText\(\s*selectedDocContent\?\.trim\(\)/);
});

test('does not generate private Brain snapshots during frontend builds', () => {
  assert.equal(packageJson.scripts.prebuild, undefined);
  assert.equal(fs.existsSync(path.join(__dirname, '..', 'app', 'brain', 'workspaceSnapshot.json')), false);
  assert.equal(fs.existsSync(path.join(__dirname, '..', 'app', 'brain', 'workspaceSnapshot.ts')), false);
  if (deployScript) {
    assert.match(deployScript, /--exclude '\*workspaceSnapshot\.\*'/);
    assert.match(deployScript, /private workspace snapshot entered the frontend deployment stage/);
  } else {
    assert.equal(fs.existsSync(path.join(repoRoot, 'release', 'public_source_manifest.json')), true);
    assert.equal(fs.existsSync(path.join(repoRoot, 'docs', 'public_repository_boundary.md')), true);
  }
});

test('pins the self-hosted frontend to the patched Next.js release', () => {
  assert.equal(packageJson.dependencies.next, '15.5.21');
  assert.equal(packageJson.devDependencies['eslint-config-next'], '15.5.21');
});

test('does not compile operator-specific Mac or retired runtime paths into Brain', () => {
  assert.doesNotMatch(clientSource, /\/Users\/neo|\.openclaw/);
});

test('Brain mirrors FEEZIE strategy provenance and recommendation safety metadata', () => {
  for (const field of [
    'strategy_contract_freshness',
    'pillar_coverage',
    'canonical_pillar',
    'employer_safety',
    'proof_posture',
    'audience_consequence',
    'development_status',
  ]) {
    assert.match(clientSource, new RegExp(field));
  }
  assert.match(clientSource, /Strategy \$\{humanizeSnakeCase\(contractState\)\}/);
  assert.match(clientSource, /Contract \$\{contractHash\.slice\(0, 8\)\}/);
  assert.match(clientSource, /pillarWarnings\.map/);
});

test('Persona reuses the existing review surface for longitudinal owner positions', () => {
  assert.match(clientSource, /related_owner_positions/);
  assert.match(clientSource, /Prior owner positions/);
  assert.match(clientSource, /not external claims or automatic canon/);
  assert.match(clientSource, /owner_response_history/);
  assert.match(clientSource, /This response over time/);
  assert.match(clientSource, /does not decide whether they conflict, reinforce one another, or represent a changed view/);
  assert.doesNotMatch(clientSource, /Perspective Inbox/);
});

test('Brain renders private grounding and source registry as aggregate status only', () => {
  assert.match(clientSource, /recent_source_count\?: number/);
  assert.doesNotMatch(clientSource, /sourceIndex\?\.recent_sources/);
  assert.doesNotMatch(clientSource, /recentAssets\.map/);
  assert.match(clientSource, /Exact names, identifiers, excerpts, and paths remain outside this aggregate view/);
  assert.match(clientSource, /Exact titles, identifiers, and paths remain outside this aggregate view/);
});

test('redacts private host paths and credential names from every Brain display string', () => {
  assert.equal(
    normalizeBrainDisplayText('Result in /opt/aiclone/private-runtime/jobs/result.json.'),
    'Result in [local path].',
  );
  assert.equal(
    normalizeBrainDisplayText('Updated /opt/aiclone/project/workspaces/agc/analytics/report.md.'),
    'Updated workspaces/agc/analytics/report.md.',
  );
  assert.equal(
    normalizeBrainDisplayText('Read /app/knowledge/persona/feeze/identity/claims.md.'),
    'Read knowledge/persona/feeze/identity/claims.md.',
  );
  assert.equal(
    normalizeBrainDisplayText('MY_SERVICE_TOKEN=do-not-show was configured.'),
    '[credential] was configured.',
  );
  assert.equal(
    normalizeBrainDisplayText('Use frontend/app/ops/ and frontend/app/brain/ as the product surfaces.'),
    'Use frontend/app/ops/ and frontend/app/brain/ as the product surfaces.',
  );
});

test('redacts every saved Daily Brief field before it reaches the visible surface', () => {
  const panelStart = clientSource.indexOf('function DailyBriefsPanel(');
  const panelEnd = clientSource.indexOf('function BriefLaneLegendPanel(', panelStart);
  assert.ok(panelStart >= 0 && panelEnd > panelStart, 'expected the Daily Briefs panel source');
  const panelSource = clientSource.slice(panelStart, panelEnd);

  for (const field of [
    'entry.title',
    'selected.title',
    'selected.summary',
    'selected.content_markdown',
  ]) {
    assert.match(
      panelSource,
      new RegExp(`normalize(?:Brain)?DisplayText\\(\\s*${field.replace('.', '\\.')}\\s*\\)`),
      `${field} must pass through the display privacy boundary`,
    );
    assert.doesNotMatch(
      panelSource,
      new RegExp(`\\{\\s*${field.replace('.', '\\.')}\\s*\\}`),
      `${field} must not be rendered raw`,
    );
  }
});

test('keeps document selection and load errors scoped to the visible document', () => {
  assert.match(
    clientSource,
    /find\(\(doc\) => doc\.path === selectedDocPath\) \?\? null/,
  );
  assert.match(clientSource, /const nextPath = groupedDocs\[0\]\?\.items\[0\]\?\.path \?\? ''/);
  assert.match(clientSource, /setDocContentError\(null\);\s*if \(!selectedDoc \|\| selectedDoc\.content \|\| docContentByPath\[selectedDoc\.path\]\)/);
});

test('routes every Brain request through the authenticated same-origin control proxy', () => {
  assert.match(clientSource, /controlApiGet/);
  assert.match(clientSource, /controlApiPost/);
  assert.doesNotMatch(clientSource, /from ['"]@\/lib\/api-client['"]/);
  assert.doesNotMatch(clientSource, /getApiUrl/);
  assert.doesNotMatch(clientSource, /API_URL/);
  assert.doesNotMatch(clientSource, /\bfetch\s*\(/);
  assert.doesNotMatch(pageSource, /apiGet|getApiUrl|API_URL|\bfetch\s*\(/);
});

test('mounts only the selected Brain workspace panel', () => {
  for (const tab of ['dashboard', 'briefs', 'persona', 'automations', 'docs']) {
    assert.match(clientSource, new RegExp(`activeTab === '${tab}' && <section id="brain-section-${tab}"[^>]*tabIndex=\\{-1\\}`));
  }
});

test('waits for the browser hash before loading a workspace', () => {
  assert.match(clientSource, /const \[locationReady, setLocationReady\] = useState\(false\)/);
  assert.match(clientSource, /setLocationReady\(true\)/);
  assert.match(clientSource, /if \(!locationReady\) \{\s*return;\s*\}/);
});

test('moves focus and scroll position when the active Brain workspace changes', () => {
  assert.match(clientSource, /activeTab === 'persona' && requestedDeltaId/);
  assert.match(clientSource, /document\.getElementById\(`brain-section-\$\{activeTab\}`\)/);
  assert.match(clientSource, /target\.scrollIntoView\(/);
  assert.match(clientSource, /target\.focus\(\{ preventScroll: true \}\)/);
});

test('keeps completed persona items visible in lifecycle history', () => {
  assert.match(
    clientSource,
    /deltas\.filter\(\(delta\) => !completedDeltaIds\.includes\(delta\.id\) && personaDeltaStage\(delta\) === 'brain_pending_review'\)/,
  );
  assert.match(clientSource, /deltas\.filter\(\(delta\) => personaDeltaStage\(delta\) === 'committed'\)/);
  assert.doesNotMatch(clientSource, /const visibleDeltas =/);
});

test('keeps draft-safe manual persona selection and its deep link in sync', () => {
  assert.match(clientSource, /const selectPersonaDeltaInUrl = useCallback/);
  assert.match(clientSource, /params\.set\('delta_id', deltaId\)/);
  assert.match(clientSource, /params\.delete\('delta_id'\)/);
  assert.match(clientSource, /window\.history\.pushState\(null, '', href\)/);
  assert.match(clientSource, /window\.history\.replaceState\(null, '', href\)/);
  assert.match(clientSource, /onClick=\{\(\) => selectMobilePersonaDelta\(delta\.id\)\}/);
  assert.match(clientSource, /selectActiveDelta\(deltaId, 'replace'\)/);
});

test('falls back to an exact persona lookup for deep-linked queue misses', () => {
  assert.match(clientSource, /`\/api\/persona\/deltas\/\$\{encodeURIComponent\(requestedDeltaId\)\}`/);
  assert.match(clientSource, /setPersonaDeltas\(\(current\) =>/);
  assert.match(clientSource, /requestedDeltaLookupState === 'not_found'/);
});

test('requires explicit sign-off before canonical writes', () => {
  assert.match(clientSource, /window\.confirm\(/);
  assert.match(clientSource, /Commit .*approved canon fragment/);
});

test('does not call an old memory snapshot live', () => {
  assert.match(clientSource, /isRecentTimestamp\(brainMemorySync\?\.generated_at, 6 \* 60 \* 60 \* 1000\)/);
  assert.match(clientSource, /Sync status stale/);
});

test('reports local Brain mutations as queued Mac work', () => {
  assert.match(clientSource, /type BrainLocalActionQueuedResponse =/);
  assert.match(clientSource, /formatBrainLocalQueueStatus\(payload/);
  assert.match(clientSource, /controlApiPost<BrainLocalActionQueuedResponse>\('\/api\/brain\/refresh-persona-review', \{\}\)/);
  assert.match(clientSource, /Refresh Persona Queue on Mac/);
  assert.doesNotMatch(clientSource, /!compactPersonaChrome && \(\s*<div[^>]*>[\s\S]{0,1200}Refresh Persona Queue on Mac/);
  assert.match(clientSource, /It will run on your Mac without a model API call/);
  assert.doesNotMatch(clientSource, /Brain Signal review saved/);
  assert.doesNotMatch(clientSource, /Registered .* in Brain/);
});

test('reports first-run and idempotently reused Persona routes truthfully', () => {
  assert.match(clientSource, /standup_reused\?: boolean/);
  assert.match(clientSource, /pm_card_reused\?: boolean/);
  assert.match(clientSource, /existing standup reused/);
  assert.match(clientSource, /standups ready \(new and existing\)/);
  assert.match(clientSource, /existing PM work reused/);
  assert.match(clientSource, /PM work ready \(new and existing\)/);
});

test('validates local intake and labels persisted watchlist freshness', () => {
  assert.match(clientSource, /const canQueueLongForm = Boolean\(value\.url\.trim\(\) \|\| value\.transcriptText\.trim\(\) \|\| value\.notes\.trim\(\)\)/);
  assert.match(clientSource, /disabled=\{longFormQueueDisabled\}/);
  assert.match(clientSource, /youtubeWatchlist\?\.data_mode === 'persisted'/);
  assert.match(clientSource, /isRecentTimestamp\(youtubeWatchlist\?\.generated_at, 3 \* 60 \* 60 \* 1000\)/);
  assert.match(clientSource, /Transcript runtime was ready at last snapshot/);
  assert.match(clientSource, /Configuration only — local runner has not reported yet/);
  assert.match(clientSource, /only governed public-safe deployed docs/);
});

test('isolates expensive Dashboard truth reads so one dependency cannot erase the whole surface', () => {
  assert.match(clientSource, /fetchFreshJson<BrainControlPlanePayload>\('\/api\/brain\/control-plane'/);
  assert.match(clientSource, /fetchFreshJson<PortfolioWorkspaceSnapshot>\('\/api\/brain\/portfolio-snapshot'/);
  assert.match(clientSource, /fetchFreshJson<OpenBrainHealth>\('\/api\/open-brain\/health'/);
  assert.match(clientSource, /Brain could not verify the current control-plane snapshot/);
  assert.match(clientSource, /Unknown values remain blank instead of being shown as zero/);
  assert.match(clientSource, /Last verified/);
});

test('loads observed automation truth instead of treating configured contracts as health', () => {
  assert.match(clientSource, /fetchFreshJson<AutomationsIndexPayload>\('\/api\/automations\/'/);
  assert.match(clientSource, /Configuration and observed runtime are shown separately/);
  assert.match(clientSource, /job\.last_status \|\| 'unknown'/);
  assert.match(clientSource, /job\.last_delivered === true/);
  assert.match(clientSource, /mismatchReport\?\.action_required_count/);
});

test('keeps unsaved Brief and Persona writing intact across polling refreshes', () => {
  assert.match(clientSource, /setReactionText\(''\);[\s\S]{0,180}\}, \[brief\.id\]\);/);
  assert.doesNotMatch(clientSource, /setReactionText\(''\);[\s\S]{0,120}\[brief\.id, items\]/);
  const personaHydrationStart = clientSource.indexOf('const draft = selectedDelta ? readPersonaReviewDraft(selectedDelta.id) : null');
  const personaHydrationEnd = clientSource.indexOf('if (!selectedDelta || personaDraftReadyDeltaId !== selectedDelta.id', personaHydrationStart);
  assert.ok(personaHydrationStart >= 0 && personaHydrationEnd > personaHydrationStart);
  const personaHydrationSource = clientSource.slice(personaHydrationStart, personaHydrationEnd);
  assert.match(personaHydrationSource, /setReflectionText\(draft\?\.reflectionText \?\? metadataText\(selectedDelta\?\.metadata, 'owner_response_excerpt'\) \?\? ''\)/);
  assert.match(personaHydrationSource, /\}, \[selectedDelta\?\.id\]\)/);
  assert.doesNotMatch(personaHydrationSource, /\[selectedDelta\?\.id, selectedDelta\?\.metadata\]/);
});

test('carries exact Brain origins and owner reactions into FEEZIE drafting', () => {
  assert.match(clientSource, /originType', 'daily_brief_item'/);
  assert.match(clientSource, /params\.set\('briefId', brief\.id\)/);
  assert.match(clientSource, /params\.set\('ownerReaction', latestOwnerReaction\)/);
  assert.match(clientSource, /originType: 'brain_signal'/);
  assert.match(clientSource, /originType: 'persona_delta'/);
  assert.match(clientSource, /Draft in FEEZIE/);
});
