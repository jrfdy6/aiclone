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
    const candidates = [
      path.join(process.cwd(), 'knowledge/aiclone'),
      path.join(workspaceRoot, 'knowledge/aiclone'),
    ];
    const baseDir = candidates.find((candidate) => fs.existsSync(candidate));
    if (!baseDir) return workspaceSnapshot.docs as DocEntry[];
    return fs
      .readdirSync(baseDir)
      .filter((file) => file.endsWith('.md') && file !== 'README.md')
      .slice(0, 8)
      .map((file) => {
        const fullPath = path.join(baseDir, file);
        const raw = fs.readFileSync(fullPath, 'utf-8');
        const snippet = raw.split('\n').find((line) => line.trim().length > 0) ?? '';
        return {
          name: file.replace('.md', ''),
          path: path.relative(process.cwd(), fullPath),
          snippet,
        } satisfies DocEntry;
      });
  } catch (err) {
    console.warn('Failed to load docs', err);
  }
  return workspaceSnapshot.docs as DocEntry[];
}
