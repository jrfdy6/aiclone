import fs from 'fs';
import path from 'path';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const WORKSPACE_ROOT = path.join(process.cwd(), 'workspaces/linkedin-content-os');

export default function LinkedInPage() {
  const backlogRaw = readWorkspaceFile('backlog.md');
  const weeklyPlanRaw = readWorkspaceFile('plans/weekly_plan.md');
  const reactionQueueRaw = readWorkspaceFile('plans/reaction_queue.md');
  const workflowDoc = readWorkspaceFile('docs/linkedin_curation_workflow.md');

  const planGeneratedAt = parseGeneratedAt(weeklyPlanRaw);
  const queueGeneratedAt = parseGeneratedAt(reactionQueueRaw);

  const workflowSteps = parseSubsections(extractSection(workflowDoc, 'Core Workflow'));
  const saveRules = collectSaveRules(workflowDoc);
  const sourcePriority = parseNumberedList(extractSection(workflowDoc, 'Source Priority'));
  const plannerRule = extractSection(workflowDoc, 'Planner Rule');

  const priorityLanes = parseBullets(extractSection(weeklyPlanRaw, "This Week's Priority Lanes"));
  const positioningModel = parseBullets(extractSection(weeklyPlanRaw, 'Positioning Model'));
  const operatingNotes = parseBullets(extractSection(weeklyPlanRaw, 'Operating Notes'));
  const researchFeed = parseBullets(extractSection(weeklyPlanRaw, 'Research Feed'));
  const holdNotes = parseBullets(extractSection(weeklyPlanRaw, 'Hold / Careful Framing'));

  const marketSignals = parseSubsections(extractSection(weeklyPlanRaw, 'Market Signals'));
  const recommendedPosts = parseSubsections(extractSection(weeklyPlanRaw, 'Recommended Posts'));

  const immediateOpportunities = parseReactionEntries(extractSection(reactionQueueRaw, 'Immediate Comment Opportunities'));
  const postSeeds = parseReactionEntries(extractSection(reactionQueueRaw, 'Standalone Post Seeds'));

  const backlogActive = parseSubsections(extractSection(backlogRaw, 'Active'));
  const backlogParked = parseSubsections(extractSection(backlogRaw, 'Parked'));

  const docFiles = listWorkspaceFiles('docs').filter((name) => name.endsWith('.md') && name !== 'README.md');
  const draftFiles = listWorkspaceFiles('drafts').filter((name) => name.endsWith('.md') && name !== 'README.md');
  const draftCount = draftFiles.length;

  const signalCount = marketSignals.length;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <NavHeader />
      <div className="mx-auto max-w-6xl space-y-10 px-4 py-10">
        <section className="space-y-6 rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/80 to-slate-950/80 p-8 shadow-lg shadow-black/30">
          <div>
            <p className="text-xs uppercase tracking-[0.45em] text-fuchsia-300">LinkedIn OS</p>
            <h1 className="mt-2 text-3xl font-semibold text-white">Workspace mission control</h1>
            <p className="mt-2 text-sm text-slate-300">
              LinkedIn-specific intelligence now lives under <code>workspaces/linkedin-content-os</code>. Running
              <code>python3 scripts/personal-brand/refresh_linkedin_strategy.py</code> rebuilds the weekly plan, reaction queue, and the
              workspace snapshot that powers this UI so non-technical operators can see every signal, idea, and draft in one place.
            </p>
          </div>
          <div className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Plan refreshed" value={planGeneratedAt || '—'} />
            <Stat label="Reaction queue" value={queueGeneratedAt || '—'} />
            <Stat label="Active backlog" value={`${backlogActive.length} tasks`} />
            <Stat label="Draft queue" value={`${draftCount} drafts`} />
            <Stat label="Signals captured" value={`${signalCount}`} />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Link
              href="/ops"
              className="rounded-full border border-fuchsia-500 px-4 py-1.5 text-fuchsia-200 transition hover:bg-fuchsia-500/20"
            >
              Open Ops mission control
            </Link>
            <span className="text-slate-400">
              Workspace snapshot: <code>workspaceSnapshot.ts</code>
            </span>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            {positioningModel.slice(0, 3).map((item) => (
              <span key={item} className="rounded-full border border-slate-700 px-3 py-1">
                {item}
              </span>
            ))}
          </div>
        </section>

        <section className="grid gap-8 lg:grid-cols-[2fr,1fr]">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Signal pipeline</h2>
              <span className="text-xs uppercase tracking-[0.3em] text-slate-500">From capture to publish</span>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {workflowSteps.map((step) => {
                const commands = extractCommands(step.body);
                return (
                  <div key={step.title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                    <p className="text-xs uppercase tracking-[0.4em] text-fuchsia-300">{step.title}</p>
                    <div className="mt-2 space-y-2 text-sm text-slate-300">
                      {step.body
                        .split('\n')
                        .map((line) => line.trim())
                        .filter((line) => line.length > 0)
                        .map((line, index) => (
                          <p key={`${step.title}-${index}`}>{line}</p>
                        ))}
                    </div>
                    {commands.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {commands.map((command) => (
                          <code
                            key={`${step.title}-${command}`}
                            className="rounded-full border border-slate-700 bg-slate-950/80 px-3 py-1 text-xs text-slate-200"
                          >
                            {command}
                          </code>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <h3 className="text-sm font-semibold uppercase tracking-[0.4em] text-slate-400">Save rules</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Keep</p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-300">
                    {saveRules.keep.map((rule) => (
                      <li key={`keep-${rule}`}>• {rule}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Do not keep</p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-300">
                    {saveRules.drop.map((rule) => (
                      <li key={`drop-${rule}`}>• {rule}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="mt-4">
                <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Source priority</p>
                <ol className="mt-2 space-y-1 text-xs text-slate-300">
                  {sourcePriority.map((item) => (
                    <li key={`source-${item}`}>{item}</li>
                  ))}
                </ol>
              </div>
              <p className="mt-4 text-xs uppercase tracking-[0.4em] text-slate-500">Planner rule</p>
              <p className="mt-2 text-sm text-slate-200">{plannerRule}</p>
            </div>
          </div>
        </section>

        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">Weekly LinkedIn plan</h2>
              <p className="text-xs text-slate-500">Generated {planGeneratedAt}</p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-400">
              <span className="rounded-full border border-slate-700 px-3 py-1">Plan lanes / priority signal feed</span>
              <span className="rounded-full border border-slate-700 px-3 py-1">Backed by <code>plans/weekly_plan.md</code></span>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Priority lanes</p>
              <div className="flex flex-wrap gap-2">
                {priorityLanes.map((lane) => (
                  <span key={`lane-${lane}`} className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200">
                    {lane}
                  </span>
                ))}
              </div>
            </div>
            <div className="space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Operating notes</p>
              <ul className="space-y-1 text-sm text-slate-200">
                {operatingNotes.map((note, index) => (
                  <li key={`note-${index}`}>• {note}</li>
                ))}
                {holdNotes.length > 0 && <li className="text-amber-300">Hold items: {holdNotes.join('; ')}</li>}
              </ul>
            </div>
            <div className="space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Research feed</p>
              <ul className="space-y-1 text-sm text-slate-300">
                {researchFeed.map((line, index) => (
                  <li key={`feed-${index}`}>
                    <code className="text-xs text-slate-400">{line}</code>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {recommendedPosts.map((post) => (
              <div key={post.title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                <h3 className="text-base font-semibold text-white">{post.title}</h3>
                <p className="text-xs text-slate-400">{stripBackticks(post.fields['Category'] || post.fields['Source'])}</p>
                {post.fields['Priority lane'] && (
                  <p className="text-xs text-slate-400">Priority lane: {stripBackticks(post.fields['Priority lane'])}</p>
                )}
                {post.fields.Hook && (
                  <p className="mt-2 text-sm text-slate-200">Hook: {post.fields.Hook}</p>
                )}
                {post.fields['Why now'] && (
                  <p className="mt-1 text-sm text-slate-300">Why now: {post.fields['Why now']}</p>
                )}
                {post.fields['Source file'] && (
                  <p className="mt-3 text-xs text-slate-500">Source file: <code>{post.fields['Source file']}</code></p>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">Reaction queue</h2>
              <p className="text-xs text-slate-500">Immediate comments, post seeds, and engagement moves (generated {queueGeneratedAt})</p>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {immediateOpportunities.map((entry) => (
              <div key={entry.title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                <p className="text-xs uppercase tracking-[0.35em] text-fuchsia-300">Comment move</p>
                <h3 className="mt-2 text-lg font-semibold text-white">{entry.title}</h3>
                <p className="text-xs text-slate-400">Lane: {entry.fields.Lane}</p>
                <p className="mt-2 text-sm text-slate-200">Hook: {entry.fields['Hook to react to']}</p>
                {entry.fields['Comment angle'] && <p className="mt-1 text-sm text-slate-300">Angle: {entry.fields['Comment angle']}</p>}
                {entry.suggestedComment && (
                  <p className="mt-3 rounded-2xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm text-slate-100">
                    {entry.suggestedComment}
                  </p>
                )}
                {entry.fields['Why this matters'] && (
                  <p className="mt-3 text-xs text-slate-400">Why: {entry.fields['Why this matters']}</p>
                )}
                <p className="mt-2 text-[0.65rem] uppercase tracking-[0.4em] text-slate-500">Source file</p>
                <p className="text-xs text-slate-400"><code>{entry.fields['Source file']}</code></p>
              </div>
            ))}
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Standalone post seeds</h3>
              <span className="text-xs text-slate-500">Turn signals into full drafts</span>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {postSeeds.map((seed) => (
                <div key={seed.title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-200">
                  <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Seed</p>
                  <p className="mt-1 font-semibold text-white">{seed.title}</p>
                  {seed.fields['Post angle'] && <p className="mt-2 text-xs text-slate-300">{seed.fields['Post angle']}</p>}
                  {seed.fields['Risk'] && <p className="mt-1 text-xs text-amber-400">Risk: {seed.fields['Risk']}</p>}
                  {seed.fields['Source file'] && (
                    <p className="mt-2 text-[0.65rem] text-slate-500"><code>{seed.fields['Source file']}</code></p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Workspace assets</h2>
            <span className="text-xs text-slate-500">Backlog, drafts, research, and docs</span>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-baseline justify-between">
                <h3 className="text-base font-semibold">Active backlog</h3>
                <span className="text-xs text-slate-400">{backlogActive.length} tasks</span>
              </div>
              <div className="space-y-3 text-sm text-slate-200">
                {backlogActive.map((task) => (
                  <div key={task.title} className="space-y-1 rounded-xl border border-slate-800/60 bg-slate-950/50 p-3">
                    <p className="font-semibold text-slate-100">{task.title}</p>
                    <p className="text-xs text-slate-400">{summarize(task.body)}</p>
                  </div>
                ))}
              </div>
              {backlogParked.length > 0 && (
                <p className="text-[0.65rem] text-slate-400">
                  Parked: {backlogParked.map((task) => task.title).join(', ')}
                </p>
              )}
              <p className="text-[0.65rem] text-slate-400">See <code>backlog.md</code> for the full roadmap.</p>
            </div>
            <div className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <h3 className="text-base font-semibold">Draft queue</h3>
              <ul className="space-y-2 text-sm text-slate-200">
                {draftFiles.slice(0, 6).map((draft) => (
                  <li key={draft}>• {draft.replace('.md', '')}</li>
                ))}
                {draftFiles.length > 6 && <li className="text-xs text-slate-400">…and {draftFiles.length - 6} more drafts.</li>}
              </ul>
              <p className="text-[0.65rem] text-slate-400">Queue definitions live in <code>drafts/queue_01.md</code>.</p>
            </div>
            <div className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <h3 className="text-base font-semibold">Docs & signals</h3>
              <div className="space-y-2 text-sm text-slate-200">
                {docFiles.map((doc) => (
                  <p key={doc} className="text-xs text-slate-400">• {doc}</p>
                ))}
              </div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Market signals (weekly plan)</p>
              <ul className="space-y-2 text-sm text-slate-200">
                {marketSignals.map((signal) => (
                  <li key={signal.title}>
                    <p className="font-semibold text-slate-100">{signal.title}</p>
                    <p className="text-xs text-slate-400">Priority lane: {stripBackticks(signal.fields['Priority lane'] || '')}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 px-4 py-3 text-center">
      <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function readWorkspaceFile(relativePath: string) {
  const fullPath = path.join(WORKSPACE_ROOT, relativePath);
  if (!fs.existsSync(fullPath)) {
    return '';
  }
  return fs.readFileSync(fullPath, 'utf8');
}

function listWorkspaceFiles(relativeDir: string) {
  const dir = path.join(WORKSPACE_ROOT, relativeDir);
  if (!fs.existsSync(dir)) {
    return [];
  }
  return fs.readdirSync(dir);
}

function extractSection(raw: string, heading: string) {
  const marker = `## ${heading}`;
  const start = raw.indexOf(marker);
  if (start === -1) {
    return '';
  }
  let section = raw.slice(start + marker.length);
  if (section.startsWith('\n')) {
    section = section.slice(1);
  }
  const nextHeading = section.indexOf('\n## ');
  if (nextHeading !== -1) {
    section = section.slice(0, nextHeading);
  }
  return section.trim();
}

function parseBullets(section: string) {
  return section
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => line.slice(2).trim())
    .filter((item) => item.length > 0);
}

function parseNumberedList(section: string) {
  return section
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => /^\d+\.\s+/.test(line))
    .map((line) => line.replace(/^\d+\.\s+/, ''));
}

type Subsection = {
  title: string;
  body: string;
  fields: Record<string, string>;
};

function parseSubsections(section: string): Subsection[] {
  if (!section) {
    return [];
  }
  const pattern = /###\s+([^\n]+)\n([\s\S]*?)(?=(?:\n###\s)|$)/g;
  const matches = Array.from(section.matchAll(pattern));
  return matches.map((match) => ({
    title: match[1].trim(),
    body: match[2].trim(),
    fields: parseKeyValueBullets(match[2]),
  }));
}

function parseKeyValueBullets(body: string) {
  const lines = body.split('\n');
  const map: Record<string, string> = {};
  for (const raw of lines) {
    const line = raw.trim();
    if (!line.startsWith('- ')) {
      continue;
    }
    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) {
      continue;
    }
    const key = line.slice(2, colonIndex).trim();
    const value = line.slice(colonIndex + 1).trim();
    map[key] = value;
  }
  return map;
}

function parseGeneratedAt(raw: string) {
  const match = raw.match(/Generated:\s*(.+)/);
  return match ? match[1].trim() : '';
}

function collectSaveRules(raw: string) {
  const section = extractSection(raw, 'Save Rules');
  const keepMatch = section.match(/Keep a signal if:\s*([\s\S]*?)Do not keep a signal if:/);
  const keep = keepMatch ? parseBullets(keepMatch[1]) : parseBullets(section);
  const dropMatch = section.match(/Do not keep a signal if:\s*([\s\S]*)/);
  const drop = dropMatch ? parseBullets(dropMatch[1]) : [];
  return { keep, drop };
}

type ReactionEntry = {
  title: string;
  fields: Record<string, string>;
  suggestedComment?: string;
};

function parseReactionEntries(section: string): ReactionEntry[] {
  if (!section) {
    return [];
  }
  const pattern = /###\s+([^\n]+)\n([\s\S]*?)(?=(?:\n###\s)|$)/g;
  const matches = Array.from(section.matchAll(pattern));
  return matches.map((match) => {
    const body = match[2].trim();
    const suggestion = extractSuggestedComment(body);
    const sanitizedBody = suggestion
      ? body.replace(/- Suggested comment:\n\n[\s\S]*?(?=(?:\n- [A-Z])|$)/, '')
      : body;
    return {
      title: match[1].trim(),
      fields: parseKeyValueBullets(sanitizedBody),
      suggestedComment: suggestion,
    };
  });
}

function extractSuggestedComment(body: string) {
  const match = body.match(/- Suggested comment:\n\n([\s\S]*?)(?=(?:\n- [A-Z])|$)/);
  if (!match) {
    return undefined;
  }
  return match[1]
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join(' ');
}

function extractCommands(body: string) {
  const matches = Array.from(body.matchAll(/`?python3[^`\n]*`?/g));
  const unique = Array.from(new Set(matches.map((match) => match[0].replace(/`/g, '').trim())));
  return unique.filter((command) => command.length > 0);
}

function stripBackticks(value: string) {
  return value.replace(/`/g, '');
}

function summarize(text: string, maxLength = 120) {
  const trimmed = text.replace(/\s+/g, ' ').trim();
  if (trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, maxLength).trim()}…`;
}
