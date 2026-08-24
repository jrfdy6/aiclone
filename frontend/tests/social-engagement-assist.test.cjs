const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const frontendRoot = path.resolve(__dirname, '..');
const helperSource = fs.readFileSync(path.join(frontendRoot, 'lib/social-assist-actions.ts'), 'utf8');
const compiled = ts.transpileModule(helperSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const loadedModule = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loadedModule, loadedModule.exports, require);
const {
  copyDraftAndOpenNativeSurface,
  openNativeSocialSurface,
  validateNativeSocialSurface,
} = loadedModule.exports;

const componentSource = fs.readFileSync(path.join(frontendRoot, 'app/workspace/SocialEngagementAssist.tsx'), 'utf8');
const workspaceSource = fs.readFileSync(path.join(frontendRoot, 'app/workspace/WorkspaceClient.tsx'), 'utf8');
const opsSource = fs.readFileSync(path.join(frontendRoot, 'app/ops/OpsClient.tsx'), 'utf8');

test('copy + open executes exact owner-controlled LinkedIn interaction without a platform mutation', async () => {
  const calls = [];
  const result = await copyDraftAndOpenNativeSurface({
    platform: 'linkedin',
    nativeUrl: 'https://www.linkedin.com/posts/example_activity-1',
    draftText: 'Exact prepared owner-review draft.',
    dependencies: {
      writeClipboard: async (text) => calls.push(['clipboard', text]),
      openWindow: (url, target, features) => calls.push(['open', url, target, features]),
    },
  });

  assert.deepEqual(calls, [
    ['clipboard', 'Exact prepared owner-review draft.'],
    ['open', 'https://www.linkedin.com/posts/example_activity-1', '_blank', 'noopener,noreferrer'],
  ]);
  assert.deepEqual(result, {
    copied: true,
    openRequested: true,
    nativeUrl: 'https://www.linkedin.com/posts/example_activity-1',
    externalMutationPerformed: false,
  });
});

test('Instagram native open uses the exact validated source and no clipboard side effect', () => {
  const calls = [];
  const opened = openNativeSocialSurface(
    'instagram',
    'https://www.instagram.com/p/ABC123/',
    (url, target, features) => calls.push([url, target, features]),
  );

  assert.equal(opened, 'https://www.instagram.com/p/ABC123/');
  assert.deepEqual(calls, [['https://www.instagram.com/p/ABC123/', '_blank', 'noopener,noreferrer']]);
});

test('cross-platform, credential-bearing, insecure, and non-native URLs fail before browser actions', async () => {
  const rejected = [
    ['linkedin', 'https://www.instagram.com/p/ABC123/'],
    ['instagram', 'https://www.linkedin.com/posts/example'],
    ['linkedin', 'http://www.linkedin.com/posts/example'],
    ['instagram', ['https://', 'user', ':', 'password', '@', 'www.instagram.com/p/ABC123/'].join('')],
    ['linkedin', 'https://linkedin.example.com/posts/example'],
  ];

  for (const [platform, url] of rejected) {
    assert.throws(() => validateNativeSocialSurface(platform, url), /must belong/);
  }

  const calls = [];
  await assert.rejects(
    copyDraftAndOpenNativeSurface({
      platform: 'linkedin',
      nativeUrl: 'https://example.com/unsafe',
      draftText: 'Draft',
      dependencies: {
        writeClipboard: (text) => calls.push(['clipboard', text]),
        openWindow: (url) => calls.push(['open', url]),
      },
    }),
    /must belong/,
  );
  assert.deepEqual(calls, []);
});

test('empty drafts fail closed before clipboard or native navigation', async () => {
  const calls = [];
  await assert.rejects(
    copyDraftAndOpenNativeSurface({
      platform: 'instagram',
      nativeUrl: 'https://www.instagram.com/p/ABC123/',
      draftText: '   ',
      dependencies: {
        writeClipboard: (text) => calls.push(['clipboard', text]),
        openWindow: (url) => calls.push(['open', url]),
      },
    }),
    /draft is empty/i,
  );
  assert.deepEqual(calls, []);
});

test('shared Workspace/Ops surface wires only assisted capture and preparation actions', () => {
  assert.match(workspaceSource, /<SocialEngagementAssist\s*\/>/);
  assert.match(opsSource, /<LinkedinWorkspaceSurface/);
  assert.match(componentSource, /social-assist\/opportunities/);
  assert.match(componentSource, /prepare_copy/);
  assert.match(componentSource, /open_native_surface/);
  assert.match(componentSource, /never scrapes, publishes, comments, messages, reposts, likes, or follows/);
  assert.doesNotMatch(componentSource, /action:\s*['"](?:publish|comment|message|repost|like|follow)['"]/);
});

test('assisted capture fields cannot force the workspace wider than a narrow phone', () => {
  assert.match(componentSource, /const inputStyle = \{\s*width: '100%',\s*minWidth: 0,\s*boxSizing: 'border-box'/);
  assert.match(componentSource, /gridTemplateColumns: 'repeat\(auto-fit, minmax\(min\(100%, 180px\), 1fr\)\)'/);
  assert.match(componentSource, /gridTemplateColumns: 'repeat\(auto-fit, minmax\(min\(100%, 290px\), 1fr\)\)'/);
  assert.match(componentSource, /gridColumn: '1 \/ -1'/);
  assert.match(componentSource, /key=\{opportunity\.opportunity_id\}[^\n]+minWidth: 0[^\n]+width: '100%'[^\n]+overflowWrap: 'anywhere'/);
  assert.match(componentSource, /whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'/);
});

test('remote assisted capture polls the exact signed job before clearing owner input', () => {
  assert.match(componentSource, /social-assist\/jobs\/\$\{encodeURIComponent\(cardId\)\}/);
  assert.match(componentSource, /next\.status === 'completed'/);
  assert.match(componentSource, /await loadOpportunities\(\)/);
  const queuedBranch = componentSource.indexOf("if (isQueueReceipt(created))");
  const queuedReturn = componentSource.indexOf('return;', queuedBranch);
  const firstClear = componentSource.indexOf("setSourceUrl('');", queuedBranch);
  assert.ok(queuedBranch > -1 && queuedReturn > queuedBranch && firstClear > queuedReturn);
});

test('copy and open wait for a safe control-plane receipt before native browser actions', () => {
  const copyHandler = componentSource.slice(
    componentSource.indexOf('async function prepareCopyAndOpen'),
    componentSource.indexOf('async function openOnly'),
  );
  assert.ok(copyHandler.indexOf('await controlApiPost') < copyHandler.indexOf('await copyDraftAndOpenNativeSurface'));
  const openHandler = componentSource.slice(
    componentSource.indexOf('async function openOnly'),
    componentSource.indexOf('return (', componentSource.indexOf('async function openOnly')),
  );
  assert.ok(openHandler.indexOf('await controlApiPost') < openHandler.indexOf('openNativeSocialSurface'));
  assert.match(componentSource, /external_mutation_performed/);
});
