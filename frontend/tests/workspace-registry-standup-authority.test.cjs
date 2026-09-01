const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const frontendRoot = path.resolve(__dirname, '..');
const source = fs.readFileSync(
  path.join(frontendRoot, 'lib', 'workspace-registry.ts'),
  'utf8',
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', 'require', compiled)(
  loaded,
  loaded.exports,
  require,
);

test('FEEZIE projects relevance-selected lenses while Shared Ops keeps its executive trio', () => {
  const registry = loaded.exports.fallbackWorkspaceRegistry;
  const sharedOps = registry.find((entry) => entry.key === 'shared_ops');
  const feezie = registry.find((entry) => entry.key === 'feezie-os');

  assert.deepEqual(sharedOps.workspace_sync_participants, [
    'Jean-Claude',
    'Neo',
    'Yoda',
  ]);
  assert.equal(sharedOps.standup_relevance_required, undefined);
  assert.deepEqual(feezie.workspace_sync_participants, []);
  assert.equal(feezie.standup_relevance_required, true);
});
