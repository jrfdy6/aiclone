const fs = require('fs');
const path = require('path');

const FRONTMATTER_MARK = '---\n';
const TODO_MARKERS = ['_TODO:', 'TODO:'];

const frontendRoot = path.resolve(__dirname, '..');
const workspaceRoot = path.resolve(frontendRoot, '..');
const bundleRoot = path.join(workspaceRoot, 'knowledge', 'persona', 'feeze');
const brainOutputPath = path.join(frontendRoot, 'app', 'brain', 'workspaceSnapshot.ts');
const linkedinWorkspaceRoot = path.join(workspaceRoot, 'workspaces', 'linkedin-content-os');
const linkedinPlanPath = path.join(linkedinWorkspaceRoot, 'plans', 'weekly_plan.json');
const linkedinReactionQueuePath = path.join(linkedinWorkspaceRoot, 'plans', 'reaction_queue.json');
const linkedinSocialFeedPath = path.join(linkedinWorkspaceRoot, 'plans', 'social_feed.json');
const editorialMixPath = path.join(linkedinWorkspaceRoot, 'docs', 'editorial_mix.md');
const contentOutputPath = path.join(frontendRoot, 'legacy', 'content-pipeline', 'workspaceSnapshot.ts');

const docRoots = [
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

const explicitDocs = [
  { relPath: 'memory/persistent_state.md', group: 'Canonical Memory' },
  { relPath: 'memory/LEARNINGS.md', group: 'Canonical Memory' },
  { relPath: 'memory/daily-briefs.md', group: 'Canonical Memory' },
  { relPath: 'memory/cron-prune.md', group: 'Canonical Memory' },
  { relPath: 'memory/dream_cycle_log.md', group: 'Canonical Memory' },
  { relPath: 'memory/codex_session_handoff.jsonl', group: 'Canonical Memory', name: 'codex_session_handoff' },
  { relPath: 'memory/reports/brain_canonical_memory_sync_latest.md', group: 'Canonical Memory', name: 'brain_canonical_memory_sync_latest' },
];

function stripFrontmatter(text) {
  if (!text.startsWith(FRONTMATTER_MARK)) return text.trim();
  const parts = text.split('\n---\n', 2);
  if (parts.length === 2) return parts[1].trim();
  return text.trim();
}

function hasFrontmatter(text) {
  return text.startsWith(FRONTMATTER_MARK);
}

function walkMarkdownFiles(dir) {
  const files = [];
  if (!fs.existsSync(dir)) return files;
  const stack = [dir];
  while (stack.length > 0) {
    const current = stack.pop();
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

function firstMeaningfulLine(raw) {
  return raw.split('\n').find((line) => line.trim().length > 0) ?? '';
}

function toDoc(fullPath, group, name) {
  const raw = fs.readFileSync(fullPath, 'utf-8');
  const relPath = path.relative(workspaceRoot, fullPath).replace(/\\/g, '/');
  const stat = fs.statSync(fullPath);
  return {
    name: name ?? path.basename(fullPath, path.extname(fullPath)),
    path: relPath,
    snippet: firstMeaningfulLine(raw),
    content: raw,
    group,
    updatedAt: stat.mtime.toISOString(),
  };
}

function loadDocs() {
  const docs = [];
  const seen = new Set();

  const pushDoc = (doc) => {
    if (seen.has(doc.path)) return;
    seen.add(doc.path);
    docs.push(doc);
  };

  for (const source of docRoots) {
    const dir = path.join(workspaceRoot, source.relDir);
    for (const fullPath of walkMarkdownFiles(dir)) {
      pushDoc(toDoc(fullPath, source.group));
    }
  }

  for (const source of explicitDocs) {
    const fullPath = path.join(workspaceRoot, source.relPath);
    if (fs.existsSync(fullPath)) {
      pushDoc(toDoc(fullPath, source.group, source.name));
    }
  }

  const memoryDir = path.join(workspaceRoot, 'memory');
  if (fs.existsSync(memoryDir)) {
    const latestDailyLog = fs
      .readdirSync(memoryDir)
      .filter((file) => /^\d{4}-\d{2}-\d{2}\.md$/.test(file))
      .sort()
      .pop();
    if (latestDailyLog) {
      pushDoc(toDoc(path.join(memoryDir, latestDailyLog), 'Canonical Memory', latestDailyLog.replace('.md', '')));
    }
  }

  return docs.sort((left, right) => left.path.localeCompare(right.path));
}

function loadPersonaWorkspace() {
  if (!fs.existsSync(bundleRoot)) {
    return { packs: [], pendingMarkdown: '', health: null };
  }

  const manifestPath = path.join(bundleRoot, 'manifest.json');
  const pendingPath = path.join(bundleRoot, 'inbox', 'pending_deltas.md');
  const pendingMarkdown = fs.existsSync(pendingPath) ? fs.readFileSync(pendingPath, 'utf-8') : '';

  if (!fs.existsSync(manifestPath)) {
    return {
      packs: [],
      pendingMarkdown,
      health: {
        bundlePath: bundleRoot,
        missingFiles: ['manifest.json'],
        missingFrontmatter: [],
        todoFiles: [],
        status: 'error',
      },
    };
  }

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  } catch (error) {
    return {
      packs: [],
      pendingMarkdown,
      health: {
        bundlePath: bundleRoot,
        missingFiles: [],
        missingFrontmatter: ['manifest.json'],
        todoFiles: [{ path: 'manifest.json', markers: [`Invalid JSON: ${error.message}`] }],
        status: 'error',
      },
    };
  }

  const packs = Object.entries(manifest.content_packs ?? {}).map(([key, config]) => ({
    key,
    title: config.title ?? key,
    description: config.description ?? '',
    sections: (config.files ?? [])
      .filter((relPath) => fs.existsSync(path.join(bundleRoot, relPath)))
      .map((relPath) => {
        const fullPath = path.join(bundleRoot, relPath);
        const text = fs.readFileSync(fullPath, 'utf-8');
        return { path: relPath, content: stripFrontmatter(text) };
      }),
  }));

  const allFiles = [
    ...(manifest.identity_files ?? []),
    ...(manifest.prompt_files ?? []),
    ...(manifest.history_files ?? []),
    ...(manifest.inbox_files ?? []),
  ];
  const missingFiles = [];
  const missingFrontmatter = [];
  const todoFiles = [];

  allFiles.forEach((relPath) => {
    const fullPath = path.join(bundleRoot, relPath);
    if (!fs.existsSync(fullPath)) {
      missingFiles.push(relPath);
      return;
    }
    const text = fs.readFileSync(fullPath, 'utf-8');
    if (!hasFrontmatter(text)) {
      missingFrontmatter.push(relPath);
    }
    const markers = TODO_MARKERS.filter((marker) => text.includes(marker));
    if (markers.length > 0) {
      todoFiles.push({ path: relPath, markers });
    }
  });

  return {
    packs,
    pendingMarkdown,
    health: {
      bundlePath: bundleRoot,
      bundleVersion: manifest.bundle_version,
      personaId: manifest.persona_id,
      missingFiles,
      missingFrontmatter,
      todoFiles,
      status: missingFiles.length === 0 && missingFrontmatter.length === 0 ? 'ok' : 'error',
    },
  };
}

function loadEditorialMix() {
  if (!fs.existsSync(editorialMixPath)) return [];
  return fs
    .readFileSync(editorialMixPath, 'utf-8')
    .split('\n')
    .filter((line) => line.startsWith('- '))
    .map((line) => line.slice(2).trim())
    .slice(0, 8);
}

function loadWeeklyPlan() {
  if (!fs.existsSync(linkedinPlanPath)) return null;
  return JSON.parse(fs.readFileSync(linkedinPlanPath, 'utf-8'));
}

function loadReactionQueue() {
  if (!fs.existsSync(linkedinReactionQueuePath)) return null;
  return JSON.parse(fs.readFileSync(linkedinReactionQueuePath, 'utf-8'));
}

function loadSocialFeed() {
  if (!fs.existsSync(linkedinSocialFeedPath)) return null;
  return JSON.parse(fs.readFileSync(linkedinSocialFeedPath, 'utf-8'));
}

function writeModule(outputPath, source) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, source, 'utf-8');
  console.log(`wrote snapshot to ${outputPath}`);
}

function main() {
  const brainSourcesReady = fs.existsSync(bundleRoot) || docRoots.some((source) => fs.existsSync(path.join(workspaceRoot, source.relDir)));
  if (!brainSourcesReady && fs.existsSync(brainOutputPath)) {
    console.log(`brain snapshot source not found; keeping existing snapshot at ${brainOutputPath}`);
  } else {
    const payload = {
      generatedAt: new Date().toISOString(),
      docs: loadDocs(),
      personaWorkspace: loadPersonaWorkspace(),
    };

    const moduleSource = [
      'import type { DocEntry, PersonaWorkspace } from "./BrainClient";',
      '',
      'export const workspaceSnapshot: { docs: DocEntry[]; personaWorkspace: PersonaWorkspace } = ',
      `${JSON.stringify({ docs: payload.docs, personaWorkspace: payload.personaWorkspace }, null, 2)} as const;`,
      '',
    ].join('\n');
    writeModule(brainOutputPath, moduleSource);
  }

  const contentSourcesReady =
    fs.existsSync(linkedinPlanPath) ||
    fs.existsSync(linkedinReactionQueuePath) ||
    fs.existsSync(linkedinSocialFeedPath) ||
    fs.existsSync(editorialMixPath);
  if (!contentSourcesReady && fs.existsSync(contentOutputPath)) {
    console.log(`content snapshot source not found; keeping existing snapshot at ${contentOutputPath}`);
  } else {
    const contentPayload = {
      generatedAt: new Date().toISOString(),
      weeklyPlan: loadWeeklyPlan(),
      reactionQueue: loadReactionQueue(),
      socialFeed: loadSocialFeed(),
      editorialMix: loadEditorialMix(),
    };
    const contentModule = [
      'export const contentPipelineSnapshot = ',
      `${JSON.stringify(contentPayload, null, 2)} as const;`,
      '',
    ].join('\n');
    writeModule(contentOutputPath, contentModule);
  }
}

main();
