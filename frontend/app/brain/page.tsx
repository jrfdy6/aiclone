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
    const cwd = process.cwd();
    const workspaceRoot = fs.existsSync(path.join(cwd, 'memory')) ? cwd : path.join(cwd, '..');
    const searchRoots = Array.from(new Set([cwd, workspaceRoot]));
    const roots = [
      { relDir: 'knowledge/aiclone', group: 'Knowledge Docs' },
      { relDir: 'knowledge/source-intelligence', group: 'Source Intelligence' },
      { relDir: 'docs', group: 'System Docs' },
      { relDir: 'SOPs', group: 'Operating Docs' },
      { relDir: 'knowledge/persona/feeze/identity', group: 'Persona Bundle' },
      { relDir: 'workspaces/linkedin-content-os/docs', group: 'Workspace Reference' },
    ];
    const explicitFiles = [
      { relPath: 'memory/persistent_state.md', group: 'Canonical Memory' },
      { relPath: 'memory/LEARNINGS.md', group: 'Canonical Memory' },
      { relPath: 'memory/daily-briefs.md', group: 'Canonical Memory' },
      { relPath: 'memory/cron-prune.md', group: 'Canonical Memory' },
      { relPath: 'memory/dream_cycle_log.md', group: 'Canonical Memory' },
      { relPath: 'memory/codex_session_handoff.jsonl', group: 'Canonical Memory', name: 'codex_session_handoff' },
      { relPath: 'memory/reports/brain_canonical_memory_sync_latest.md', group: 'Canonical Memory', name: 'brain_canonical_memory_sync_latest' },
      { relPath: 'docs/brain_truth_lanes_and_promotion_flow.md', group: 'System Docs' },
    ];
    const seen = new Set<string>();
    const docs: DocEntry[] = [];
    const pushDoc = (fullPath: string, group: string, nameOverride?: string) => {
      const relPath = path.relative(workspaceRoot, fullPath);
      if (seen.has(relPath)) return;
      seen.add(relPath);
      const raw = fs.readFileSync(fullPath, 'utf-8');
      const snippet = raw.split('\n').find((line) => line.trim().length > 0) ?? '';
      const stat = fs.statSync(fullPath);
      docs.push({
        name: nameOverride ?? path.basename(fullPath).replace(path.extname(fullPath), ''),
        path: relPath,
        snippet,
        content: raw,
        group,
        updatedAt: stat.mtime.toISOString(),
      } satisfies DocEntry);
    };

    for (const root of roots) {
      for (const baseRoot of searchRoots) {
        const dir = path.join(baseRoot, root.relDir);
        if (!fs.existsSync(dir)) continue;
        for (const file of fs.readdirSync(dir)) {
          if (!file.endsWith('.md')) continue;
          pushDoc(path.join(dir, file), root.group);
        }
      }
    }

    for (const entry of explicitFiles) {
      for (const baseRoot of searchRoots) {
        const fullPath = path.join(baseRoot, entry.relPath);
        if (!fs.existsSync(fullPath)) continue;
        pushDoc(fullPath, entry.group, entry.name);
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
        pushDoc(path.join(memoryDir, latestDailyLog), 'Canonical Memory', latestDailyLog.replace('.md', ''));
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
