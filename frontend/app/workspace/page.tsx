import fs from 'fs';
import path from 'path';
import OpsClient, { DocReference, WorkspaceFile } from '../ops/OpsClient';

export default function WorkspacePage() {
  return <OpsClient workspaceFiles={loadWorkspaceFiles()} docEntries={loadDocEntries()} initialPanel="workspace" initialWorkspaceKey="linkedin-content-os" />;
}

function loadWorkspaceFiles(): WorkspaceFile[] {
  const roots = [
    { root: path.join(process.cwd(), 'knowledge/persona/feeze'), label: 'persona-bundle' },
    { root: path.join(process.cwd(), 'workspaces/linkedin-content-os'), label: 'linkedin-content-os' },
  ].filter((entry) => fs.existsSync(entry.root));

  return roots
    .flatMap(({ root, label }) =>
      walk(root)
        .filter((file) => file.endsWith('.md') || file.endsWith('.json'))
        .sort()
        .map((filePath) => {
          const relativePath = path.relative(process.cwd(), filePath).replace(/\\/g, '/');
          const relativeToRoot = path.relative(root, filePath).replace(/\\/g, '/');
          const segments = relativeToRoot.split('/');
          const group = segments.length > 1 ? `${label}/${segments[0]}` : label;
          const raw = fs.readFileSync(filePath, 'utf-8');
          const stat = fs.statSync(filePath);
          return {
            group,
            name: path.basename(filePath),
            path: relativePath,
            snippet: firstMeaningfulLine(raw),
            content: raw,
            updatedAt: stat.mtime.toISOString(),
          } satisfies WorkspaceFile;
        }),
    );
}

function loadDocEntries(): DocReference[] {
  const targets = [
    'SOPs/_index.md',
    'SOPs/direct_postgres_bootstrap.md',
    'deliverables/brain-tab-ui-requirements.md',
    'docs/persistent_memory_blueprint.md',
  ];

  return targets
    .map((relativePath) => path.join(process.cwd(), relativePath))
    .filter((fullPath) => fs.existsSync(fullPath))
    .map((fullPath) => {
      const raw = fs.readFileSync(fullPath, 'utf-8');
      const stat = fs.statSync(fullPath);
      return {
        name: path.basename(fullPath),
        path: path.relative(process.cwd(), fullPath).replace(/\\/g, '/'),
        snippet: firstMeaningfulLine(raw),
        content: raw,
        updatedAt: stat.mtime.toISOString(),
      } satisfies DocReference;
    });
}

function firstMeaningfulLine(raw: string): string {
  return (
    raw
      .split('\n')
      .map((line) => line.trim())
      .find((line) => line.length > 0 && !line.startsWith('#')) ?? ''
  );
}

function walk(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const results: string[] = [];

  entries.forEach((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walk(fullPath));
      return;
    }
    results.push(fullPath);
  });

  return results;
}
