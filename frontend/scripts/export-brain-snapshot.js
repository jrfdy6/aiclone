const fs = require('fs');
const path = require('path');

const FRONTMATTER_MARK = '---\n';
const TODO_MARKERS = ['_TODO:', 'TODO:'];

const frontendRoot = path.resolve(__dirname, '..');
const workspaceRoot = path.resolve(frontendRoot, '..');
const docsRoot = path.join(workspaceRoot, 'knowledge', 'aiclone');
const bundleRoot = path.join(workspaceRoot, 'knowledge', 'persona', 'feeze');
const brainOutputPath = path.join(frontendRoot, 'app', 'brain', 'workspaceSnapshot.ts');
const linkedinWorkspaceRoot = path.join(workspaceRoot, 'workspaces', 'linkedin-content-os');
const linkedinPlanPath = path.join(linkedinWorkspaceRoot, 'plans', 'weekly_plan.json');
const linkedinReactionQueuePath = path.join(linkedinWorkspaceRoot, 'plans', 'reaction_queue.json');
const linkedinSocialFeedPath = path.join(linkedinWorkspaceRoot, 'plans', 'social_feed.json');
const editorialMixPath = path.join(linkedinWorkspaceRoot, 'docs', 'editorial_mix.md');
const contentOutputPath = path.join(frontendRoot, 'legacy', 'content-pipeline', 'workspaceSnapshot.ts');

function stripFrontmatter(text) {
  if (!text.startsWith(FRONTMATTER_MARK)) return text.trim();
  const parts = text.split('\n---\n', 2);
  if (parts.length === 2) return parts[1].trim();
  return text.trim();
}

function hasFrontmatter(text) {
  return text.startsWith(FRONTMATTER_MARK);
}

function loadDocs() {
  if (!fs.existsSync(docsRoot)) return [];
  return fs
    .readdirSync(docsRoot)
    .filter((file) => file.endsWith('.md') && file !== 'README.md')
    .sort()
    .slice(0, 8)
    .map((file) => {
      const fullPath = path.join(docsRoot, file);
      const raw = fs.readFileSync(fullPath, 'utf-8');
      const snippet = raw.split('\n').find((line) => line.trim().length > 0) ?? '';
      return {
        name: file.replace('.md', ''),
        path: path.relative(frontendRoot, fullPath),
        snippet,
      };
    });
}

function loadPersonaWorkspace() {
  if (!fs.existsSync(bundleRoot)) {
    return { packs: [], pendingMarkdown: '', health: null };
  }

  const manifest = JSON.parse(fs.readFileSync(path.join(bundleRoot, 'manifest.json'), 'utf-8'));
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

  const pendingPath = path.join(bundleRoot, 'inbox', 'pending_deltas.md');
  const pendingMarkdown = fs.existsSync(pendingPath) ? fs.readFileSync(pendingPath, 'utf-8') : '';

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
  const brainSourcesReady = fs.existsSync(bundleRoot) || fs.existsSync(docsRoot);
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
