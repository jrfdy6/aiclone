import fs from 'fs';
import path from 'path';
import { workspaceSnapshot } from './workspaceSnapshot';

const FRONTMATTER_MARK = '---\n';
const TODO_MARKERS = ['_TODO:', 'TODO:'];

type ManifestPack = {
  title?: string;
  description?: string;
  files?: string[];
};

type Manifest = {
  bundle_version?: string;
  persona_id?: string;
  identity_files?: string[];
  prompt_files?: string[];
  history_files?: string[];
  inbox_files?: string[];
  content_packs?: Record<string, ManifestPack>;
};

export type PersonaBundleHealth = {
  bundlePath: string;
  bundleVersion?: string;
  personaId?: string;
  missingFiles: string[];
  missingFrontmatter: string[];
  todoFiles: { path: string; markers: string[] }[];
  status: 'ok' | 'error';
};

export type PersonaPack = {
  key: string;
  title: string;
  description: string;
  sections: { path: string; content: string }[];
};

export type PersonaWorkspace = {
  packs: PersonaPack[];
  pendingMarkdown: string;
  health: PersonaBundleHealth | null;
};

function stripFrontmatter(text: string) {
  if (!text.startsWith(FRONTMATTER_MARK)) return text.trim();
  const parts = text.split('\n---\n', 2);
  if (parts.length === 2) return parts[1].trim();
  return text.trim();
}

function hasFrontmatter(text: string) {
  return text.startsWith(FRONTMATTER_MARK);
}

function findBundleRoot() {
  const workspaceRoot = path.join(process.cwd(), '..');
  const candidates = [
    path.join(process.cwd(), 'knowledge/persona/feeze'),
    path.join(workspaceRoot, 'knowledge/persona/feeze'),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

function readManifest(bundleRoot: string): Manifest {
  return JSON.parse(fs.readFileSync(path.join(bundleRoot, 'manifest.json'), 'utf-8')) as Manifest;
}

export function loadPersonaWorkspace(): PersonaWorkspace {
  try {
    const bundleRoot = findBundleRoot();
    if (!bundleRoot) {
      return workspaceSnapshot.personaWorkspace as PersonaWorkspace;
    }

    const manifest = readManifest(bundleRoot);
    const packs = Object.entries(manifest.content_packs ?? {}).map(([key, config]) => ({
      key,
      title: config.title ?? key,
      description: config.description ?? '',
      sections: (config.files ?? []).map((relPath) => {
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
    const missingFiles: string[] = [];
    const missingFrontmatter: string[] = [];
    const todoFiles: { path: string; markers: string[] }[] = [];

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

    const pendingPath = path.join(bundleRoot, 'inbox/pending_deltas.md');
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
  } catch (error) {
    console.warn('Failed to load persona workspace', error);
    return workspaceSnapshot.personaWorkspace as PersonaWorkspace;
  }
}
