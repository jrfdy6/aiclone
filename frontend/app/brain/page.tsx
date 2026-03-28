import fs from 'fs';
import path from 'path';
import BrainClient, { DocEntry } from './BrainClient';
import { loadPersonaWorkspace } from './personaBundle';
import { workspaceSnapshot } from './workspaceSnapshot';

export default function BrainPage() {
  const docs = loadDocs();
  const personaWorkspace = loadPersonaWorkspace();
  return <BrainClient docs={docs} personaWorkspace={personaWorkspace} />;
}

function loadDocs(): DocEntry[] {
  try {
    const workspaceRoot = path.join(process.cwd(), '..');
    const roots = [
      { dir: path.join(process.cwd(), 'knowledge/aiclone'), group: 'Knowledge Docs' },
      { dir: path.join(workspaceRoot, 'knowledge/aiclone'), group: 'Knowledge Docs' },
      { dir: path.join(process.cwd(), 'docs'), group: 'System Docs' },
      { dir: path.join(workspaceRoot, 'docs'), group: 'System Docs' },
      { dir: path.join(process.cwd(), 'SOPs'), group: 'Operating Docs' },
      { dir: path.join(workspaceRoot, 'SOPs'), group: 'Operating Docs' },
      { dir: path.join(process.cwd(), 'knowledge/persona/feeze/identity'), group: 'Persona Bundle' },
      { dir: path.join(workspaceRoot, 'knowledge/persona/feeze/identity'), group: 'Persona Bundle' },
      { dir: path.join(process.cwd(), 'workspaces/linkedin-content-os/docs'), group: 'Workspace Reference' },
      { dir: path.join(workspaceRoot, 'workspaces/linkedin-content-os/docs'), group: 'Workspace Reference' },
    ];
    const seen = new Set<string>();
    const docs: DocEntry[] = [];
    for (const root of roots) {
      if (!fs.existsSync(root.dir)) continue;
      for (const file of fs.readdirSync(root.dir)) {
        if (!file.endsWith('.md')) continue;
        const fullPath = path.join(root.dir, file);
        const relPath = path.relative(process.cwd(), fullPath);
        if (seen.has(relPath)) continue;
        seen.add(relPath);
        const raw = fs.readFileSync(fullPath, 'utf-8');
        const snippet = raw.split('\n').find((line) => line.trim().length > 0) ?? '';
        const stat = fs.statSync(fullPath);
        docs.push({
          name: file.replace('.md', ''),
          path: relPath,
          snippet,
          content: raw,
          group: root.group,
          updatedAt: stat.mtime.toISOString(),
        } satisfies DocEntry);
      }
    }
    if (docs.length > 0) {
      return docs.sort((left, right) => left.path.localeCompare(right.path));
    }
  } catch (err) {
    console.warn('Failed to load docs', err);
  }
  return workspaceSnapshot.docs as DocEntry[];
}
