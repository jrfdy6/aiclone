import fs from 'fs';
import path from 'path';
import OpsClient, {
  ChronicleEntry,
  DocReference,
  ExecutiveArtifact,
  ExecutiveFeed,
  PMRecommendationItem,
  PMRecommendationPacket,
  StandupPrepPacket,
  WorkspaceFile,
} from './OpsClient';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const OPENCLAW_WORKSPACE_ROOT = path.join(process.cwd(), '.openclaw/workspace');
const OPENCLAW_MEMORY_ROOT = path.join(OPENCLAW_WORKSPACE_ROOT, 'memory');

export default function OpsPage() {
  return (
    <OpsClient
      workspaceFiles={loadWorkspaceFiles()}
      docEntries={loadDocEntries()}
      executiveFeed={loadExecutiveFeed()}
    />
  );
}

function loadWorkspaceFiles(): WorkspaceFile[] {
  const roots = [
    { root: path.join(process.cwd(), 'knowledge/persona/feeze'), label: 'persona-bundle' },
    { root: path.join(process.cwd(), 'workspaces/linkedin-content-os'), label: 'linkedin-content-os' },
    { root: path.join(OPENCLAW_WORKSPACE_ROOT, 'workspaces'), label: 'openclaw-workspaces' },
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

function loadExecutiveFeed(): ExecutiveFeed {
  const chronicleEntries = loadChronicleEntries();
  const standupPreps = loadStandupPreps();
  const pmRecommendations = loadPmRecommendations();
  const artifacts = loadExecutiveArtifacts({ chronicleEntries, standupPreps, pmRecommendations });

  return {
    artifacts,
    chronicleEntries,
    standupPreps,
    pmRecommendations,
  };
}

function loadChronicleEntries(): ChronicleEntry[] {
  const handoffPath = path.join(OPENCLAW_MEMORY_ROOT, 'codex_session_handoff.jsonl');
  if (!fs.existsSync(handoffPath)) {
    return [];
  }

  return readJsonLines(handoffPath)
    .map((entry, index) => {
      const id = pickString(entry, ['entry_id', 'handoff_id']) ?? `chronicle-${index}`;
      const createdAt = pickString(entry, ['created_at']) ?? undefined;
      const workspaceKey = pickString(entry, ['workspace_key']) ?? 'shared_ops';
      return {
        id,
        createdAt,
        workspaceKey,
        scope: pickString(entry, ['scope']) ?? undefined,
        summary: pickString(entry, ['summary']) ?? 'Codex Chronicle entry',
        signalTypes: toStringArray(entry.signal_types),
        decisions: toStringArray(entry.decisions),
        blockers: toStringArray(entry.blockers),
        followUps: toStringArray(entry.follow_ups),
        tags: toStringArray(entry.tags),
      } satisfies ChronicleEntry;
    })
    .sort((left, right) => compareIsoDates(left.createdAt, right.createdAt))
    .slice(-8);
}

function loadStandupPreps(): StandupPrepPacket[] {
  const prepRoot = path.join(OPENCLAW_MEMORY_ROOT, 'standup-prep');
  if (!fs.existsSync(prepRoot)) {
    return [];
  }

  const latestByKey = new Map<string, StandupPrepPacket>();

  walk(prepRoot)
    .filter((filePath) => filePath.endsWith('.json'))
    .forEach((filePath) => {
      const payload = readJsonFile(filePath);
      if (!payload) {
        return;
      }
      const standupPayload = isRecord(payload.standup_payload) ? payload.standup_payload : {};
      const blockers = toStringArray(payload.blockers);
      const commitments = toStringArray(payload.commitments);
      const needs = toStringArray(payload.needs);

      const packet = {
        id: pickString(payload, ['prep_id']) ?? path.basename(filePath, '.json'),
        standupKind: pickString(payload, ['standup_kind']) ?? 'executive_ops',
        workspaceKey: pickString(payload, ['workspace_key']) ?? 'shared_ops',
        ownerAgent: pickString(payload, ['owner_agent']) ?? 'jean-claude',
        generatedAt: pickString(payload, ['generated_at']) ?? undefined,
        summary: pickString(payload, ['summary']) ?? 'Standup prep packet',
        agenda: toStringArray(payload.agenda),
        blockers: blockers.length ? blockers : toStringArray(standupPayload.blockers),
        commitments: commitments.length ? commitments : toStringArray(standupPayload.commitments),
        needs: needs.length ? needs : toStringArray(standupPayload.needs),
        artifactDeltas: toStringArray(payload.artifact_deltas),
        pmSnapshot: isRecord(payload.pm_snapshot) ? payload.pm_snapshot : {},
        pmUpdateTitles: toObjectArray(payload.pm_updates).map((item) => pickString(item, ['title']) ?? 'Untitled PM update'),
        memoryPromotions: toObjectArray(payload.memory_promotions).map(
          (item) => pickString(item, ['content']) ?? 'Untitled memory promotion',
        ),
        sourcePaths: collectSourcePaths(payload),
        path: toRelativePath(filePath),
      } satisfies StandupPrepPacket;

      const key = `${packet.standupKind}:${packet.workspaceKey}`;
      const existing = latestByKey.get(key);
      if (!existing || compareIsoDates(existing.generatedAt, packet.generatedAt) < 0) {
        latestByKey.set(key, packet);
      }
    });

  return Array.from(latestByKey.values()).sort((left, right) => compareIsoDates(right.generatedAt, left.generatedAt));
}

function loadPmRecommendations(): PMRecommendationPacket[] {
  const recommendationsRoot = path.join(OPENCLAW_MEMORY_ROOT, 'pm-recommendations');
  if (!fs.existsSync(recommendationsRoot)) {
    return [];
  }

  const packets: PMRecommendationPacket[] = [];
  for (const filePath of walk(recommendationsRoot).filter((candidate) => candidate.endsWith('.json'))) {
    const payload = readJsonFile(filePath);
    if (!payload) {
      continue;
    }

    const items = toObjectArray(payload.pm_updates).map((item) => ({
      workspaceKey: pickString(item, ['workspace_key']) ?? 'shared_ops',
      scope: pickString(item, ['scope']) ?? 'shared_ops',
      ownerAgent: pickString(item, ['owner_agent']) ?? 'jean-claude',
      title: pickString(item, ['title']) ?? 'Untitled recommendation',
      status: pickString(item, ['status']) ?? 'todo',
      reason: pickString(item, ['reason']) ?? 'Standup-generated recommendation',
    }) satisfies PMRecommendationItem);

    packets.push({
      id: pickString(payload, ['recommendation_id']) ?? path.basename(filePath, '.json'),
      workspaceKey: pickString(payload, ['workspace_key']) ?? 'shared_ops',
      createdAt: pickString(payload, ['created_at']) ?? undefined,
      path: toRelativePath(filePath),
      items,
    });
  }

  return packets
    .sort((left, right) => compareIsoDates(right.createdAt, left.createdAt))
    .slice(0, 8);
}

function loadExecutiveArtifacts({
  chronicleEntries,
  standupPreps,
  pmRecommendations,
}: {
  chronicleEntries: ChronicleEntry[];
  standupPreps: StandupPrepPacket[];
  pmRecommendations: PMRecommendationPacket[];
}): ExecutiveArtifact[] {
  const artifacts: ExecutiveArtifact[] = [];
  const latestChronicle = chronicleEntries[chronicleEntries.length - 1] ?? null;
  const latestStandup = standupPreps[0] ?? null;
  const latestPmPacket = pmRecommendations[0] ?? null;

  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'codex-chronicle',
      label: 'Codex Chronicle',
      category: 'codex',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'codex_session_handoff.jsonl'),
      summary: latestChronicle?.summary ?? 'Chronicle is ready to capture high-signal Codex work.',
      detail: `${chronicleEntries.length} Chronicle chunk${chronicleEntries.length === 1 ? '' : 's'} available for standups.`,
    }),
  );
  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'pruning-cycles',
      label: 'Pruning Cycles',
      category: 'memory',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'cron-prune.md'),
      summary: summarize(snippetFromTail(path.join(OPENCLAW_MEMORY_ROOT, 'cron-prune.md')), 160),
      detail: `${countOccurrences(path.join(OPENCLAW_MEMORY_ROOT, todayLogFileName()), '## Context Flush')} context flush checkpoints logged today.`,
    }),
  );
  maybePushArtifact(
    artifacts,
    buildHeartbeatArtifact(path.join(OPENCLAW_MEMORY_ROOT, 'heartbeat-state.json')),
  );
  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'daily-brief',
      label: 'Morning Daily Brief',
      category: 'openclaw',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'daily-briefs.md'),
      summary: summarize(snippetFromHead(path.join(OPENCLAW_MEMORY_ROOT, 'daily-briefs.md')), 160),
      detail: 'OpenClaw summary lane for daily status, alerts, and follow-up framing.',
    }),
  );
  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'dream-cycle',
      label: 'Dream Cycle',
      category: 'openclaw',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'dream_cycle_log.md'),
      summary: summarize(snippetFromHead(path.join(OPENCLAW_MEMORY_ROOT, 'dream_cycle_log.md')), 160),
      detail: 'Dream cycle outcomes should shape next-step thinking before standups.',
    }),
  );
  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'persistent-state',
      label: 'Persistent State',
      category: 'memory',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'persistent_state.md'),
      summary: summarize(snippetFromHead(path.join(OPENCLAW_MEMORY_ROOT, 'persistent_state.md')), 160),
      detail: 'Durable operating memory shared across pruning, briefs, and longer-horizon jobs.',
    }),
  );
  maybePushArtifact(
    artifacts,
    latestStandup
      ? {
          id: 'latest-standup-prep',
          label: 'Latest Standup Prep',
          category: 'local',
          path: latestStandup.path,
          updatedAt: latestStandup.generatedAt,
          summary: latestStandup.summary,
          detail: `${latestStandup.pmUpdateTitles.length} PM changes and ${latestStandup.memoryPromotions.length} memory promotions queued.`,
        }
      : null,
  );
  maybePushArtifact(
    artifacts,
    latestPmPacket
      ? {
          id: 'pm-recommendations',
          label: 'PM Recommendations',
          category: 'local',
          path: latestPmPacket.path,
          updatedAt: latestPmPacket.createdAt,
          summary: latestPmPacket.items[0]?.title ?? 'Standup-generated recommendations are ready.',
          detail: `${latestPmPacket.items.length} queued recommendation${latestPmPacket.items.length === 1 ? '' : 's'} waiting for promotion.`,
        }
      : null,
  );
  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'meeting-watchdog',
      label: 'Meeting Watchdog',
      category: 'local',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'reports', 'meeting_watchdog_latest.md'),
      summary: summarize(snippetFromHead(path.join(OPENCLAW_MEMORY_ROOT, 'reports', 'meeting_watchdog_latest.md')), 160),
      detail: 'Freshness and transcript-quality checks across the required meeting lanes.',
    }),
  );
  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'post-sync-dispatch',
      label: 'Post-Sync Dispatch',
      category: 'local',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'reports', 'post_sync_dispatch_latest.md'),
      summary: summarize(snippetFromHead(path.join(OPENCLAW_MEMORY_ROOT, 'reports', 'post_sync_dispatch_latest.md')), 160),
      detail: 'Standup commitments promoted into PM artifacts and dispatch metadata.',
    }),
  );
  maybePushArtifact(
    artifacts,
    buildFileArtifact({
      id: 'accountability-sweep',
      label: 'Accountability Sweep',
      category: 'local',
      filePath: path.join(OPENCLAW_MEMORY_ROOT, 'reports', 'accountability_sweep_latest.md'),
      summary: summarize(snippetFromHead(path.join(OPENCLAW_MEMORY_ROOT, 'reports', 'accountability_sweep_latest.md')), 160),
      detail: 'Checks whether meeting-created work is still moving through the queue.',
    }),
  );
  maybePushArtifact(
    artifacts,
    buildLatestRunnerMemoArtifact(path.join(OPENCLAW_MEMORY_ROOT, 'runner-memos/jean-claude')),
  );
  buildWorkspaceLaneArtifacts(path.join(OPENCLAW_WORKSPACE_ROOT, 'workspaces')).forEach((artifact) => maybePushArtifact(artifacts, artifact));

  return artifacts;
}

function firstMeaningfulLine(raw: string): string {
  return (
    raw
      .split('\n')
      .map((line) => line.trim())
      .find((line) => line.length > 0 && !line.startsWith('#')) ?? ''
  );
}

function summarize(value: string, maxLength = 120): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return 'No summary available.';
  }
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength - 1).trimEnd()}…` : normalized;
}

function todayLogFileName() {
  return `${new Date().toISOString().slice(0, 10)}.md`;
}

function buildHeartbeatArtifact(filePath: string): ExecutiveArtifact | null {
  const payload = readJsonFile(filePath);
  if (!payload || !fs.existsSync(filePath)) {
    return null;
  }
  const stat = fs.statSync(filePath);
  const checkKeys = Object.keys((payload.lastChecks as Record<string, unknown> | undefined) ?? {});
  return {
    id: 'heartbeat-state',
    label: 'Heartbeat State',
    category: 'openclaw',
    path: toRelativePath(filePath),
    updatedAt: stat.mtime.toISOString(),
    summary: `Heartbeat status is ${pickString(payload, ['lastHeartbeatStatus']) ?? 'unknown'} with note ${pickString(payload, ['lastHeartbeatNote']) ?? 'n/a'}.`,
    detail: `${checkKeys.length} heartbeat checks are currently being tracked.`,
  };
}

function buildLatestRunnerMemoArtifact(dirPath: string): ExecutiveArtifact | null {
  if (!fs.existsSync(dirPath)) {
    return null;
  }
  const latest = walk(dirPath)
    .filter((filePath) => filePath.endsWith('.md'))
    .map((filePath) => ({ filePath, stat: fs.statSync(filePath) }))
    .sort((left, right) => right.stat.mtimeMs - left.stat.mtimeMs)[0];

  if (!latest) {
    return null;
  }

  const raw = fs.readFileSync(latest.filePath, 'utf-8');
  return {
    id: 'jean-claude-memo',
    label: 'Jean-Claude Review',
    category: 'local',
    path: toRelativePath(latest.filePath),
    updatedAt: latest.stat.mtime.toISOString(),
    summary: summarize(firstMeaningfulLine(raw), 160),
    detail: 'Latest executive memo from the Jean-Claude runner.',
  };
}

function buildWorkspaceLaneArtifacts(workspacesRoot: string): ExecutiveArtifact[] {
  if (!fs.existsSync(workspacesRoot)) {
    return [];
  }

  const artifacts: ExecutiveArtifact[] = [];
  const workspaceDirs = fs
    .readdirSync(workspacesRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(workspacesRoot, entry.name));

  workspaceDirs.forEach((workspaceDir) => {
    const workspaceKey = path.basename(workspaceDir);
    const latestDispatch = latestWorkspaceArtifact(workspaceDir, 'dispatch', '.json');
    const latestBriefing = latestWorkspaceArtifact(workspaceDir, 'briefings', '.md');

    maybePushArtifact(
      artifacts,
      latestDispatch
        ? {
            id: `${workspaceKey}-dispatch`,
            label: `${humanizeWorkspaceKey(workspaceKey)} SOP`,
            category: 'local',
            path: toRelativePath(latestDispatch.filePath),
            updatedAt: latestDispatch.updatedAt,
            summary: summarize(firstMeaningfulLine(latestDispatch.raw), 160),
            detail: `Latest workspace SOP from ${workspaceKey} ready for executive discussion.`,
          }
        : null,
    );
    maybePushArtifact(
      artifacts,
      latestBriefing
        ? {
            id: `${workspaceKey}-briefing`,
            label: `${humanizeWorkspaceKey(workspaceKey)} Briefing`,
            category: 'local',
            path: toRelativePath(latestBriefing.filePath),
            updatedAt: latestBriefing.updatedAt,
            summary: summarize(firstMeaningfulLine(latestBriefing.raw), 160),
            detail: `Latest workspace status briefing from ${workspaceKey}.`,
          }
        : null,
    );
  });

  return artifacts
    .sort((left, right) => compareIsoDates(right.updatedAt, left.updatedAt))
    .slice(0, 8);
}

function latestWorkspaceArtifact(workspaceDir: string, subdir: string, extension: string) {
  const dirPath = path.join(workspaceDir, subdir);
  if (!fs.existsSync(dirPath)) {
    return null;
  }
  const latest = walk(dirPath)
    .filter((filePath) => filePath.endsWith(extension))
    .map((filePath) => ({ filePath, stat: fs.statSync(filePath) }))
    .sort((left, right) => right.stat.mtimeMs - left.stat.mtimeMs)[0];

  if (!latest) {
    return null;
  }

  return {
    filePath: latest.filePath,
    updatedAt: latest.stat.mtime.toISOString(),
    raw: fs.readFileSync(latest.filePath, 'utf-8'),
  };
}

function humanizeWorkspaceKey(workspaceKey: string) {
  return workspaceKey
    .split('-')
    .map((segment) => (segment ? `${segment[0].toUpperCase()}${segment.slice(1)}` : segment))
    .join(' ');
}

function buildFileArtifact({
  id,
  label,
  category,
  filePath,
  summary,
  detail,
}: {
  id: string;
  label: string;
  category: ExecutiveArtifact['category'];
  filePath: string;
  summary: string;
  detail: string;
}): ExecutiveArtifact | null {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  const stat = fs.statSync(filePath);
  return {
    id,
    label,
    category,
    path: toRelativePath(filePath),
    updatedAt: stat.mtime.toISOString(),
    summary,
    detail,
  };
}

function maybePushArtifact(list: ExecutiveArtifact[], artifact: ExecutiveArtifact | null) {
  if (artifact) {
    list.push(artifact);
  }
}

function collectSourcePaths(payload: Record<string, unknown>) {
  const direct = toStringArray(payload.source_paths);
  const nested = toObjectArray(payload.chronicle_entries).flatMap((entry) => toStringArray(entry.artifacts));
  return Array.from(new Set([...direct, ...nested]));
}

function countOccurrences(filePath: string, needle: string) {
  if (!fs.existsSync(filePath)) {
    return 0;
  }
  return fs.readFileSync(filePath, 'utf-8').split(needle).length - 1;
}

function snippetFromHead(filePath: string) {
  if (!fs.existsSync(filePath)) {
    return '';
  }
  const raw = fs.readFileSync(filePath, 'utf-8');
  return firstMeaningfulLine(raw);
}

function snippetFromTail(filePath: string) {
  if (!fs.existsSync(filePath)) {
    return '';
  }
  const lines = fs
    .readFileSync(filePath, 'utf-8')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.slice(-4).join(' ');
}

function compareIsoDates(left?: string, right?: string) {
  const leftTime = left ? Date.parse(left) : 0;
  const rightTime = right ? Date.parse(right) : 0;
  return leftTime - rightTime;
}

function pickString(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function toStringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

function toObjectArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object') : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function readJsonFile(filePath: string): Record<string, unknown> | null {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function readJsonLines(filePath: string): Record<string, unknown>[] {
  if (!fs.existsSync(filePath)) {
    return [];
  }

  return fs
    .readFileSync(filePath, 'utf-8')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as Record<string, unknown>;
      } catch {
        return null;
      }
    })
    .filter((entry): entry is Record<string, unknown> => entry !== null);
}

function toRelativePath(filePath: string) {
  return path.relative(process.cwd(), filePath).replace(/\\/g, '/');
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
