import fs from 'fs';
import path from 'path';
import type { DocEntry } from './BrainClient';
import { workspaceSnapshot } from './workspaceSnapshot';

type DocRecord = DocEntry & {
  fullPath: string | null;
};

const RUNTIME_MEMORY_PATHS: Record<string, string> = {
  'memory/persistent_state.md': 'memory/runtime/persistent_state.md',
  'memory/LEARNINGS.md': 'memory/runtime/LEARNINGS.md',
  'memory/codex_session_handoff.jsonl': 'memory/runtime/codex_session_handoff.jsonl',
};

const ROOTS = [
  { relDir: 'knowledge/aiclone', group: 'Knowledge Docs' },
  { relDir: 'knowledge/source-intelligence', group: 'Source Intelligence' },
  { relDir: 'docs', group: 'System Docs' },
  { relDir: 'SOPs', group: 'Operating Docs' },
  { relDir: 'knowledge/persona/feeze', group: 'Persona Bundle' },
  { relDir: 'workspaces/shared-ops/docs', group: 'Workspace Reference' },
  { relDir: 'workspaces/linkedin-content-os/docs', group: 'Workspace Reference' },
  { relDir: 'workspaces/fusion-os/docs', group: 'Workspace Reference' },
  { relDir: 'workspaces/easyoutfitapp/docs', group: 'Workspace Reference' },
  { relDir: 'workspaces/ai-swag-store/docs', group: 'Workspace Reference' },
  { relDir: 'workspaces/agc/docs', group: 'Workspace Reference' },
];

const EXPLICIT_FILES = [
  { relPath: 'memory/persistent_state.md', group: 'Canonical Memory' },
  { relPath: 'memory/LEARNINGS.md', group: 'Canonical Memory' },
  { relPath: 'memory/daily-briefs.md', group: 'Canonical Memory' },
  { relPath: 'memory/cron-prune.md', group: 'Canonical Memory' },
  { relPath: 'memory/dream_cycle_log.md', group: 'Canonical Memory' },
  { relPath: 'memory/codex_session_handoff.jsonl', group: 'Canonical Memory', name: 'codex_session_handoff' },
  { relPath: 'memory/reports/brain_canonical_memory_sync_latest.md', group: 'Canonical Memory', name: 'brain_canonical_memory_sync_latest' },
  { relPath: 'docs/brain_truth_lanes_and_promotion_flow.md', group: 'System Docs' },
];

function candidateWorkspaceRoots() {
  const cwd = process.cwd();
  const candidates = [
    process.env.OPENCLAW_WORKSPACE_ROOT,
    cwd,
    path.join(cwd, '..'),
    path.join(cwd, '..', '..'),
    '/app',
    '/app/frontend',
  ].filter((candidate): candidate is string => Boolean(candidate && candidate.trim().length > 0));

  return Array.from(new Set(candidates.map((candidate) => path.resolve(candidate)))).filter((candidate) => {
    return (
      fs.existsSync(path.join(candidate, 'docs')) ||
      fs.existsSync(path.join(candidate, 'knowledge')) ||
      fs.existsSync(path.join(candidate, 'memory')) ||
      fs.existsSync(path.join(candidate, 'workspaces'))
    );
  });
}

function primaryWorkspaceRoot() {
  return candidateWorkspaceRoots()[0] ?? process.cwd();
}

function firstMeaningfulLine(raw: string) {
  return raw.split('\n').find((line) => line.trim().length > 0) ?? '';
}

function readSnippet(fullPath: string) {
  const fd = fs.openSync(fullPath, 'r');
  try {
    const buffer = Buffer.alloc(8192);
    const bytesRead = fs.readSync(fd, buffer, 0, buffer.length, 0);
    return firstMeaningfulLine(buffer.subarray(0, bytesRead).toString('utf-8'));
  } finally {
    fs.closeSync(fd);
  }
}

function walkMarkdownFiles(dir: string) {
  const files: string[] = [];
  if (!fs.existsSync(dir)) {
    return files;
  }

  const stack = [dir];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) continue;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      if (entry.name.startsWith('.')) continue;
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (entry.isFile() && entry.name.endsWith('.md')) {
        files.push(fullPath);
      }
    }
  }

  return files.sort((left, right) => left.localeCompare(right));
}

function latestSnapshotId(root: string) {
  const pointerPath = path.join(root, 'docs/runtime_snapshots/core_memory/LATEST.json');
  if (!fs.existsSync(pointerPath)) {
    return null;
  }
  try {
    const payload = JSON.parse(fs.readFileSync(pointerPath, 'utf-8')) as { snapshot_id?: unknown };
    return typeof payload.snapshot_id === 'string' && payload.snapshot_id.trim().length > 0 ? payload.snapshot_id.trim() : null;
  } catch {
    return null;
  }
}

export function resolveMemoryReadTarget(root: string, relPath: string) {
  const runtimeRelPath = RUNTIME_MEMORY_PATHS[relPath] ?? relPath;
  const expectedMode = runtimeRelPath !== relPath ? 'runtime' : 'live';
  const livePath = path.join(root, relPath);
  const runtimePath = path.join(root, runtimeRelPath);
  const snapshotId = latestSnapshotId(root);
  const snapshotPath = snapshotId ? path.join(root, 'docs/runtime_snapshots/core_memory', snapshotId, relPath) : null;

  if (fs.existsSync(runtimePath)) {
    return {
      fullPath: runtimePath,
      readMode: expectedMode as 'runtime' | 'live',
      resolvedPath: path.relative(root, runtimePath),
    };
  }
  if (expectedMode === 'runtime' && fs.existsSync(livePath)) {
    return {
      fullPath: livePath,
      readMode: 'live' as const,
      resolvedPath: relPath,
    };
  }
  if (snapshotPath && fs.existsSync(snapshotPath)) {
    return {
      fullPath: snapshotPath,
      readMode: 'snapshot' as const,
      resolvedPath: path.relative(root, snapshotPath),
    };
  }
  return {
    fullPath: runtimePath,
    readMode: 'missing' as const,
    resolvedPath: path.relative(root, runtimePath),
  };
}

function collectDocRecords(): DocRecord[] {
  const roots = candidateWorkspaceRoots();
  const primaryRoot = roots[0] ?? process.cwd();
  const seen = new Set<string>();
  const docs: DocRecord[] = [];

  const pushDoc = (
    fullPath: string,
    group: string,
    nameOverride?: string,
    options: { displayPath?: string; displayRoot?: string; readMode?: DocEntry['readMode']; resolvedPath?: string } = {},
  ) => {
    const relPath = (options.displayPath ?? path.relative(options.displayRoot ?? primaryRoot, fullPath)).replace(/\\/g, '/');
    if (seen.has(relPath)) return;
    if (!fs.existsSync(fullPath)) return;
    seen.add(relPath);
    const stat = fs.statSync(fullPath);
    docs.push({
      name: nameOverride ?? path.basename(fullPath).replace(path.extname(fullPath), ''),
      path: relPath,
      snippet: readSnippet(fullPath),
      group,
      updatedAt: stat.mtime.toISOString(),
      readMode: options.readMode,
      resolvedPath: options.resolvedPath,
      fullPath,
    });
  };

  for (const entry of ROOTS) {
    for (const baseRoot of roots) {
      const dir = path.join(baseRoot, entry.relDir);
      if (!fs.existsSync(dir)) continue;
      for (const fullPath of walkMarkdownFiles(dir)) {
        pushDoc(fullPath, entry.group, undefined, { displayRoot: baseRoot });
      }
    }
  }

  for (const entry of EXPLICIT_FILES) {
    if (entry.relPath.startsWith('memory/')) {
      for (const root of roots) {
        const resolved = resolveMemoryReadTarget(root, entry.relPath);
        pushDoc(resolved.fullPath, entry.group, entry.name, {
          displayPath: entry.relPath,
          readMode: resolved.readMode,
          resolvedPath: resolved.resolvedPath,
        });
      }
    } else {
      for (const baseRoot of roots) {
        const fullPath = path.join(baseRoot, entry.relPath);
        if (!fs.existsSync(fullPath)) continue;
        pushDoc(fullPath, entry.group, entry.name, { displayRoot: baseRoot });
      }
    }
  }

  for (const root of roots) {
    const memoryDir = path.join(root, 'memory');
    if (!fs.existsSync(memoryDir)) continue;
    const latestDailyLog = fs
      .readdirSync(memoryDir)
      .filter((file) => /^\d{4}-\d{2}-\d{2}\.md$/.test(file))
      .sort()
      .pop();
    if (latestDailyLog) {
      const relPath = `memory/${latestDailyLog}`;
      const resolved = resolveMemoryReadTarget(root, relPath);
      pushDoc(resolved.fullPath, 'Canonical Memory', latestDailyLog.replace('.md', ''), {
        displayPath: relPath,
        readMode: resolved.readMode,
        resolvedPath: resolved.resolvedPath,
      });
    }
  }

  return docs.sort((left, right) => left.path.localeCompare(right.path));
}

function fallbackDocs(): DocRecord[] {
  return (workspaceSnapshot.docs as DocEntry[]).map((doc) => ({
    ...doc,
    content: undefined,
    fullPath: null,
  }));
}

export function loadBrainDocIndex(): DocEntry[] {
  try {
    const docs = collectDocRecords();
    if (docs.length > 0) {
      return docs.map(({ fullPath: _fullPath, content: _content, ...doc }) => doc);
    }
  } catch (err) {
    console.warn('Failed to load docs', err);
  }
  return fallbackDocs().map(({ fullPath: _fullPath, content: _content, ...doc }) => doc);
}

export function readBrainDocContent(docPath: string): DocEntry | null {
  const normalizedPath = decodeURIComponent(docPath).replace(/^(\.\.\/)+/, '').trim();
  if (!normalizedPath) {
    return null;
  }

  const record = collectDocRecords().find((doc) => doc.path === normalizedPath);
  if (!record?.fullPath) {
    const fallback = (workspaceSnapshot.docs as DocEntry[]).find((doc) => doc.path === normalizedPath);
    return fallback ?? null;
  }

  const content = fs.readFileSync(record.fullPath, 'utf-8');
  return {
    name: record.name,
    path: record.path,
    snippet: record.snippet || firstMeaningfulLine(content),
    content,
    group: record.group,
    updatedAt: record.updatedAt,
    readMode: record.readMode,
    resolvedPath: record.resolvedPath,
  };
}
