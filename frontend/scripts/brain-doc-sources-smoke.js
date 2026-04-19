#!/usr/bin/env node
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const ts = require('typescript');
const vm = require('vm');

const frontendRoot = path.resolve(__dirname, '..');
const sourcePath = path.join(frontendRoot, 'app/brain/docSources.ts');
const source = fs.readFileSync(sourcePath, 'utf-8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    esModuleInterop: true,
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
}).outputText;

const moduleObject = { exports: {} };
const sandbox = {
  Buffer,
  console,
  exports: moduleObject.exports,
  module: moduleObject,
  process,
  require(specifier) {
    if (specifier === 'fs' || specifier === 'path') {
      return require(specifier);
    }
    if (specifier === './workspaceSnapshot') {
      return {
        workspaceSnapshot: {
          docs: [],
          personaWorkspace: { packs: [], pendingMarkdown: '', health: null },
        },
      };
    }
    if (specifier === './BrainClient') {
      return {};
    }
    throw new Error(`Unexpected require from docSources smoke: ${specifier}`);
  },
};

vm.runInNewContext(compiled, sandbox, { filename: sourcePath });

const { loadBrainDocIndex, readBrainDocContent, resolveMemoryReadTarget } = moduleObject.exports;
assert.equal(typeof loadBrainDocIndex, 'function');
assert.equal(typeof readBrainDocContent, 'function');
assert.equal(typeof resolveMemoryReadTarget, 'function');

const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'brain-doc-sources-'));
const previousCwd = process.cwd();

try {
  fs.mkdirSync(path.join(tempRoot, 'memory/runtime'), { recursive: true });
  fs.mkdirSync(path.join(tempRoot, 'docs/runtime_snapshots/core_memory/2026-04-19/memory'), { recursive: true });
  fs.writeFileSync(path.join(tempRoot, 'memory/persistent_state.md'), '# Live State\n\nlive stale\n');
  fs.writeFileSync(path.join(tempRoot, 'memory/runtime/persistent_state.md'), '# Runtime State\n\nruntime current\n');
  fs.writeFileSync(path.join(tempRoot, 'docs/runtime_snapshots/core_memory/LATEST.json'), JSON.stringify({ snapshot_id: '2026-04-19' }));
  fs.writeFileSync(path.join(tempRoot, 'docs/runtime_snapshots/core_memory/2026-04-19/memory/LEARNINGS.md'), '# Snapshot Learnings\n\nsnapshot current\n');

  process.chdir(tempRoot);

  const persistentResolution = resolveMemoryReadTarget(tempRoot, 'memory/persistent_state.md');
  assert.equal(persistentResolution.readMode, 'runtime');
  assert.equal(persistentResolution.resolvedPath, 'memory/runtime/persistent_state.md');

  const learningsResolution = resolveMemoryReadTarget(tempRoot, 'memory/LEARNINGS.md');
  assert.equal(learningsResolution.readMode, 'snapshot');
  assert.equal(learningsResolution.resolvedPath, 'docs/runtime_snapshots/core_memory/2026-04-19/memory/LEARNINGS.md');

  const docs = loadBrainDocIndex();
  const persistentDoc = docs.find((doc) => doc.path === 'memory/persistent_state.md');
  assert.ok(persistentDoc, 'persistent_state.md should be indexed');
  assert.equal(persistentDoc.readMode, 'runtime');
  assert.equal(persistentDoc.resolvedPath, 'memory/runtime/persistent_state.md');
  assert.match(persistentDoc.snippet, /Runtime State/);

  const content = readBrainDocContent('memory/persistent_state.md');
  assert.ok(content, 'persistent_state.md content should load');
  assert.equal(content.readMode, 'runtime');
  assert.equal(content.resolvedPath, 'memory/runtime/persistent_state.md');
  assert.match(content.content, /runtime current/);
  assert.doesNotMatch(content.content, /live stale/);

  console.log('brain-doc-sources smoke OK');
} finally {
  process.chdir(previousCwd);
  fs.rmSync(tempRoot, { recursive: true, force: true });
}
