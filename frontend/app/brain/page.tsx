import fs from 'fs';
import path from 'path';
import { getApiUrl } from '@/lib/api-client';
import BrainClient, {
  BrainControlPlanePayload,
  DailyBriefEntry,
  DocEntry,
  PersonaDeltaEntry,
} from './BrainClient';
import { loadPersonaWorkspace } from './personaBundle';
import { workspaceSnapshot } from './workspaceSnapshot';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

type BrainInitialState = {
  briefs: DailyBriefEntry[];
  personaDeltas: PersonaDeltaEntry[];
  controlPlane: BrainControlPlanePayload | null;
};

export default async function BrainPage() {
  const docs = loadDocs();
  const personaWorkspace = loadPersonaWorkspace();
  const initialState = await loadBrainInitialState();
  return <BrainClient docs={docs} personaWorkspace={personaWorkspace} initialState={initialState} />;
}

async function loadBrainInitialState(): Promise<BrainInitialState> {
  const apiUrl = getApiUrl();
  const requestTs = Date.now();
  const [briefsRes, personaRes, controlPlaneRes] = await Promise.allSettled([
    fetch(`${apiUrl}/api/briefs/?limit=50&brain_bootstrap_ts=${requestTs}`, { cache: 'no-store' }).then((res) => res.json()),
    fetch(`${apiUrl}/api/persona/deltas?limit=100&view=brain_queue&brain_bootstrap_ts=${requestTs}`, { cache: 'no-store' }).then((res) => res.json()),
    fetch(`${apiUrl}/api/brain/control-plane?brain_bootstrap_ts=${requestTs}`, { cache: 'no-store' }).then((res) => res.json()),
  ]);

  return {
    briefs: briefsRes.status === 'fulfilled' && Array.isArray(briefsRes.value) ? briefsRes.value : [],
    personaDeltas: personaRes.status === 'fulfilled' && Array.isArray(personaRes.value) ? personaRes.value : [],
    controlPlane: controlPlaneRes.status === 'fulfilled' ? (controlPlaneRes.value ?? null) : null,
  };
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
