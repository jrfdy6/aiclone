'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { controlApiGet } from '@/lib/control-api';
import { safeExternalHttpsUrl } from '@/lib/display-privacy';
import { opsCanonicalDecisionDisplay } from '@/lib/ops-canonical-decision';
import {
  ownerItemText,
  ownerSafeOpsText,
  projectPortfolioOwnerTruth,
  projectWorkspaceOwnerTruth,
  type OpsOwnerItem,
  type OpsOwnerProjection,
  type OpsSharedReconciliation,
  type OpsWorkspaceGoalProjection,
  type WorkspaceOwnerTruth,
  type WorkspaceOwnerTruthState,
} from '@/lib/ops-owner-truth';

const panel: React.CSSProperties = {
  background: 'rgba(15,23,42,.72)',
  border: '1px solid #334155',
  borderRadius: '16px',
  padding: 'clamp(14px, 3vw, 20px)',
  display: 'grid',
  gap: '16px',
  minWidth: 0,
};
const quietText: React.CSSProperties = { color: '#94a3b8', fontSize: '12px', margin: 0, lineHeight: 1.5 };

type ScopeTruth = Pick<WorkspaceOwnerTruth, 'state' | 'currentState' | 'affected' | 'remainsHealthy'>;

function utcLabel(value?: string | null) {
  if (!value) return 'not recorded';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return 'not recorded';
  return `${date.toLocaleString('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} UTC`;
}

function stateLabel(state: WorkspaceOwnerTruthState): string {
  if (state === 'no_change') return 'Healthy — no eligible change';
  if (state === 'unavailable') return 'Unavailable';
  return `${state.slice(0, 1).toUpperCase()}${state.slice(1)}`;
}

function stateTone(state: WorkspaceOwnerTruthState): string {
  if (state === 'healthy') return '#86efac';
  if (state === 'no_change') return '#a5f3fc';
  if (state === 'empty') return '#fcd34d';
  if (state === 'degraded') return '#fdba74';
  return '#fda4af';
}

function factSummary(facts: string[], empty: string): string {
  if (!facts.length) return empty;
  if (facts.length === 1) return facts[0];
  return `${facts[0]} ${facts.length - 1} additional bounded ${facts.length === 2 ? 'item is' : 'items are'} available in supporting details.`;
}

function resultSummary(truth: WorkspaceOwnerTruth): string {
  const parts: string[] = [];
  if (truth.completed.length) parts.push(`Completed: ${truth.completed[0]}`);
  if (truth.failed.length) parts.push(`Failed: ${truth.failed[0]}`);
  if (truth.carried.length) parts.push(`Carried forward: ${truth.carried[0]}`);
  return parts.length
    ? parts.join(' ')
    : 'No completed, failed, or carried-forward work was claimed by this conclusion.';
}

function OwnerTruthRows({ rows }: { rows: Array<{ label: string; value: string; tone?: string }> }) {
  return <div data-ops-owner-summary="primary" style={{ borderTop: '1px solid #334155', borderBottom: '1px solid #334155' }}>
    {rows.map((row, index) => <div key={row.label} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(180px, 100%), 1fr))', gap: '8px 16px', padding: '11px 0', borderTop: index === 0 ? 'none' : '1px solid rgba(51,65,85,.65)' }}>
      <p style={{ color: row.tone ?? '#cbd5e1', margin: 0, fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em' }}>{row.label}</p>
      <p style={{ color: '#dbe7ff', margin: 0, fontSize: '13px', lineHeight: 1.55, overflowWrap: 'anywhere' }}>{row.value}</p>
    </div>)}
  </div>;
}

function ScopeNotice({ truth }: { truth: ScopeTruth }) {
  if (truth.state === 'healthy' || truth.state === 'no_change') {
    return <p role="status" style={{ margin: 0, color: stateTone(truth.state), lineHeight: 1.55 }}>{truth.currentState}</p>;
  }
  return <div role="alert" style={{ borderLeft: `3px solid ${stateTone(truth.state)}`, background: 'rgba(120,53,15,.16)', padding: '11px 13px', color: '#fde68a', display: 'grid', gap: '5px' }}>
    <strong>{truth.currentState}</strong>
    {truth.affected ? <p style={{ margin: 0, lineHeight: 1.5 }}><strong>Affected:</strong> {truth.affected}</p> : null}
    <p style={{ margin: 0, lineHeight: 1.5 }}><strong>What remains healthy:</strong> {truth.remainsHealthy}</p>
  </div>;
}

function FactSection({ title, facts }: { title: string; facts: string[] }) {
  if (!facts.length) return null;
  return <section style={{ borderTop: '1px solid #1e293b', paddingTop: '10px' }}>
    <h4 style={{ color: '#cbd5e1', fontSize: '12px', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '.05em' }}>{title}</h4>
    <ul style={{ color: '#94a3b8', margin: 0, paddingLeft: '18px', display: 'grid', gap: '5px', fontSize: '12px', lineHeight: 1.5 }}>
      {facts.map((fact) => <li key={`${title}-${fact}`}>{fact}</li>)}
    </ul>
  </section>;
}

function WorkspaceSupportingDetails({ truth }: { truth: WorkspaceOwnerTruth }) {
  const hasDetails = Boolean(
    truth.progressSignals.length
    || truth.phaseGate
    || truth.reevaluateWhen
    || truth.decisions.length
    || truth.actions.length > 1
    || truth.completed.length > 1
    || truth.failed.length > 1
    || truth.carried.length > 1
    || truth.changes.length > 1
    || truth.ownerDecisions.length > 1
    || truth.blockers.length > 1
    || truth.noChange.length > 1
    || truth.recommendations.length > 1
    || truth.nextDream.length > 1
    || truth.recommendationResolutions.length
    || truth.referenceCount,
  );
  if (!hasDetails) return null;
  return <details data-workspace-cycle-evidence="secondary" style={{ borderTop: '1px solid #334155', paddingTop: '11px' }}>
    <summary style={{ color: '#7dd3fc', cursor: 'pointer', fontWeight: 700 }}>Supporting goal and cycle evidence</summary>
    <p style={{ ...quietText, marginTop: '8px' }}>These bounded facts support the owner summary above. They do not create a second workspace record or change canonical state.</p>
    <div style={{ display: 'grid', gap: '10px', marginTop: '12px' }}>
      <FactSection title="What counts as progress" facts={truth.progressSignals} />
      <FactSection title="Current phase gate" facts={truth.phaseGate ? [truth.phaseGate] : []} />
      <FactSection title="Reevaluate when" facts={truth.reevaluateWhen ? [truth.reevaluateWhen] : []} />
      <FactSection title="System decisions" facts={truth.decisions} />
      <FactSection title="Additional changes" facts={truth.changes.slice(1)} />
      <FactSection title="Additional actions" facts={truth.actions.slice(1)} />
      <FactSection title="Additional completed work" facts={truth.completed.slice(1)} />
      <FactSection title="Additional failures" facts={truth.failed.slice(1)} />
      <FactSection title="Additional carry-forward" facts={truth.carried.slice(1)} />
      <FactSection title="Additional owner decisions" facts={truth.ownerDecisions.slice(1)} />
      <FactSection title="Additional blockers" facts={truth.blockers.slice(1)} />
      <FactSection title="Additional no-change findings" facts={truth.noChange.slice(1)} />
      <FactSection title="Additional recommendations" facts={truth.recommendations.slice(1)} />
      <FactSection title="Additional next-Dream inputs" facts={truth.nextDream.slice(1)} />
      <FactSection title="Recommendation resolutions" facts={truth.recommendationResolutions} />
      {truth.referenceCount ? <p style={quietText}>{truth.referenceCount} bounded reference record{truth.referenceCount === 1 ? '' : 's'} support this conclusion. Internal references remain hidden from owner guidance.</p> : null}
    </div>
  </details>;
}

function CanonicalDecisionList({ items }: { items: OpsOwnerItem[] }) {
  if (!items.length) return null;
  return <section style={{ borderTop: '1px solid #1e293b', paddingTop: '10px' }}>
    <h4 style={{ color: '#c4b5fd', fontSize: '12px', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '.05em' }}>Canonical decisions</h4>
    <ul style={{ color: '#cbd5e1', margin: 0, paddingLeft: '18px', display: 'grid', gap: '7px', fontSize: '12px' }}>{items.map((item, index) => {
      const decision = opsCanonicalDecisionDisplay(item);
      return <li key={`canonical-decision-${index}`}>
        <strong>{ownerSafeOpsText(decision.title) || 'Recorded decision'}</strong>
        {decision.status ? <span style={{ color: '#94a3b8' }}> · {ownerSafeOpsText(decision.status, 80).replaceAll('_', ' ')}</span> : null}
        {decision.resolvedChoice ? <div style={{ color: '#e2e8f0', marginTop: '2px' }}>Resolved choice: {ownerSafeOpsText(decision.resolvedChoice)}</div> : null}
      </li>;
    })}</ul>
  </section>;
}

function EvidenceLinks({ items }: { items: OpsOwnerItem[] }) {
  const links = items.flatMap((item, index) => {
    const href = safeExternalHttpsUrl(item.url ?? item.href ?? item.source_url);
    if (!href) return [];
    return [{ href, label: ownerItemText(item, 'The portfolio') || `Supporting evidence ${index + 1}` }];
  }).slice(0, 8);
  if (!links.length) return null;
  return <section style={{ borderTop: '1px solid #1e293b', paddingTop: '10px' }}>
    <h4 style={{ color: '#67e8f9', fontSize: '12px', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '.05em' }}>Supporting evidence</h4>
    <ul style={{ margin: 0, paddingLeft: '18px', display: 'grid', gap: '5px', fontSize: '12px' }}>{links.map((link) => <li key={link.href}><a href={link.href} target="_blank" rel="noreferrer" style={{ color: '#7dd3fc' }}>{link.label}</a></li>)}</ul>
  </section>;
}

export function SharedOpsReconciliationSummary({ summary }: { summary?: OpsSharedReconciliation | null }) {
  if (!summary) return null;
  const name = ownerSafeOpsText(summary.display_name, 120) || 'Shared Ops';
  const action = (summary.actions_taken ?? []).map((item) => ownerItemText(item, name)).find(Boolean);
  const recommendation = (summary.recommendations ?? []).map((item) => ownerItemText(item, name)).find(Boolean);
  const nextDream = (summary.next_cycle_inputs ?? []).map((item) => ownerItemText(item, name)).find((text) => /^The next Dream\b/i.test(text));
  return <section data-shared-ops-role={summary.role} aria-labelledby="shared-ops-reconciliation-title" style={{ borderTop: '1px solid #334155', paddingTop: '12px' }}>
    <h3 id="shared-ops-reconciliation-title" style={{ color: '#f8fafc', fontSize: '15px', margin: 0 }}>Shared Ops reconciliation</h3>
    <p style={{ ...quietText, marginTop: '4px' }}>Read-only portfolio reconciliation. Shared Ops routes cross-workspace truth; it does not execute project work or become a seventh project workspace.</p>
    <div style={{ display: 'grid', gap: '6px', marginTop: '9px', color: '#cbd5e1', fontSize: '13px', lineHeight: 1.5 }}>
      <p style={{ margin: 0 }}>{ownerSafeOpsText(summary.summary) || `${(summary.evaluated ?? []).length} project conclusions were evaluated.`}</p>
      {action ? <p style={{ margin: 0 }}><strong>AI Clone did:</strong> {action}</p> : null}
      {recommendation ? <p style={{ margin: 0 }}><strong>Recommendation:</strong> {recommendation}</p> : null}
      {nextDream ? <p style={{ margin: 0 }}><strong>Next Dream:</strong> {nextDream}</p> : null}
    </div>
  </section>;
}

function ScopedWorkspaceSummary({ data, workspaceKey, goalProjection }: { data: OpsOwnerProjection; workspaceKey: string; goalProjection?: OpsWorkspaceGoalProjection | null }) {
  const truth = projectWorkspaceOwnerTruth(data, workspaceKey, goalProjection);
  const rows = [
    { label: 'Workspace goal', value: truth.goal ?? 'The canonical goal is unavailable because its bounded owner projection is not synchronized. Current cycle status remains usable.', tone: truth.goal ? '#e2e8f0' : '#fcd34d' },
    { label: 'What changed', value: factSummary(truth.changes, 'No new canonical change was claimed.'), tone: '#cbd5e1' },
    { label: 'AI Clone did this', value: factSummary(truth.actions, 'No completed system action was claimed.'), tone: '#a5f3fc' },
    { label: 'Completed, failed, carried forward', value: resultSummary(truth), tone: truth.failed.length ? '#fda4af' : '#cbd5e1' },
    { label: 'Needs your decision', value: factSummary(truth.ownerDecisions, 'No owner decision is requested by this workspace conclusion.'), tone: truth.ownerDecisions.length ? '#fde68a' : '#94a3b8' },
    { label: 'AI Clone recommends', value: factSummary(truth.recommendations, 'No new recommendation is recorded for this cycle.'), tone: '#c4b5fd' },
    { label: 'Next Dream consumes', value: factSummary(truth.nextDream, 'No next-Dream input is claimed.'), tone: '#67e8f9' },
  ];
  return <>
    <ScopeNotice truth={truth} />
    <OwnerTruthRows rows={rows} />
    <WorkspaceSupportingDetails truth={truth} />
    <Link href={`/ops?workspace=${encodeURIComponent(truth.workspaceKey)}#workspace`} style={{ color: '#7dd3fc', fontSize: '13px', width: 'fit-content' }}>Open {truth.displayName} in Ops</Link>
  </>;
}

function PortfolioSummary({ data, goalProjection }: { data: OpsOwnerProjection; goalProjection?: OpsWorkspaceGoalProjection | null }) {
  const truth = projectPortfolioOwnerTruth(data, [], goalProjection);
  const rows = [
    { label: 'What changed', value: truth.whatChanged, tone: '#cbd5e1' },
    { label: 'AI Clone did this', value: factSummary(truth.actions, 'No completed portfolio action is recorded for this cycle.'), tone: '#a5f3fc' },
    { label: 'Needs your decision', value: factSummary(truth.ownerDecisions, 'No canonical owner decision is open in this conclusion.'), tone: truth.ownerDecisions.length ? '#fde68a' : '#94a3b8' },
    { label: 'Needs your attention', value: factSummary(truth.attention, 'No separate owner-attention item is recorded.'), tone: truth.attention.length ? '#fcd34d' : '#94a3b8' },
    { label: 'AI Clone recommends', value: factSummary(truth.recommendations, 'No new portfolio recommendation is recorded.'), tone: '#c4b5fd' },
    { label: 'Next Dream consumes', value: truth.nextDream, tone: '#67e8f9' },
  ];
  const scopeTruth: ScopeTruth = {
    state: truth.state,
    currentState: truth.currentState,
    affected: truth.affected,
    remainsHealthy: truth.remainsHealthy,
  };
  return <>
    <ScopeNotice truth={scopeTruth} />
    <OwnerTruthRows rows={rows} />
    <section aria-labelledby="workspace-cycle-status-title" style={{ display: 'grid', gap: '8px' }}>
      <div>
        <h3 id="workspace-cycle-status-title" style={{ color: '#f8fafc', fontSize: '16px', margin: 0 }}>Project workspace conclusions</h3>
        <p style={{ ...quietText, marginTop: '4px' }}>One bounded status per project. Open a workspace for its complete owner-facing conclusion.</p>
      </div>
      <div style={{ borderTop: '1px solid #334155' }}>
        {truth.workspaces.map((workspace) => <div key={workspace.workspaceKey} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(150px, 100%), 1fr))', gap: '8px 14px', alignItems: 'start', padding: '10px 0', borderBottom: '1px solid #1e293b' }}>
          <div><strong style={{ color: '#f8fafc', fontSize: '13px' }}>{workspace.displayName}</strong><div style={{ color: stateTone(workspace.state), fontSize: '11px', marginTop: '2px' }}>{stateLabel(workspace.state)}</div></div>
          <p style={{ color: '#cbd5e1', margin: 0, fontSize: '12px', lineHeight: 1.5 }}>{workspace.state === 'blocked' || workspace.state === 'unavailable' ? workspace.currentState : workspace.goal ?? workspace.currentState}</p>
          <Link href={`/ops?workspace=${encodeURIComponent(workspace.workspaceKey)}#workspace`} style={{ color: '#7dd3fc', fontSize: '12px', whiteSpace: 'nowrap' }}>Open</Link>
        </div>)}
      </div>
    </section>
    <SharedOpsReconciliationSummary summary={data.shared_ops_reconciliation} />
    <details data-ops-cycle-audit="secondary" style={{ borderTop: '1px solid #334155', paddingTop: '11px' }}>
      <summary style={{ color: '#7dd3fc', cursor: 'pointer', fontWeight: 700 }}>Supporting cycle evidence</summary>
      <p style={{ ...quietText, marginTop: '8px' }}>Canonical decisions and safe external evidence remain available here. Workspace recursion is presented once per selected workspace instead of repeated in a portfolio dump.</p>
      <div style={{ display: 'grid', gap: '10px', marginTop: '12px' }}>
        <CanonicalDecisionList items={data.canonical_decisions ?? []} />
        <EvidenceLinks items={data.supporting_evidence_links ?? []} />
        <p style={quietText}>{Object.keys(data.ai_clone_process_updates ?? {}).length} bounded process receipt group{Object.keys(data.ai_clone_process_updates ?? {}).length === 1 ? '' : 's'} accompanied this conclusion. Endpoint and subsystem diagnostics remain in Ops System.</p>
      </div>
    </details>
  </>;
}

export default function OpsStandupSummary({
  workspaceKey,
  projection,
  goalProjection,
}: {
  workspaceKey?: string;
  projection?: OpsOwnerProjection | null;
  goalProjection?: OpsWorkspaceGoalProjection | null;
}) {
  const controlled = projection !== undefined;
  const goalsControlled = goalProjection !== undefined;
  const [loadedData, setLoadedData] = useState<OpsOwnerProjection | null>(null);
  const [loadedGoals, setLoadedGoals] = useState<OpsWorkspaceGoalProjection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [goalError, setGoalError] = useState<string | null>(null);
  const data = controlled ? projection ?? null : loadedData;
  const goals = goalsControlled ? goalProjection ?? null : loadedGoals;
  const load = useCallback(async () => {
    await Promise.all([
      controlled
        ? Promise.resolve()
        : controlApiGet<OpsOwnerProjection>('/api/workspace/ops-standup', { cache: 'no-store' })
          .then((value) => { setLoadedData(value); setError(null); })
          .catch(() => setError('The Ops conclusion could not be loaded. Affected: current cycle status only. Still available: the rest of this workspace. Next: retry this bounded read; no readiness claim is being made.')),
      goalsControlled
        ? Promise.resolve()
        : controlApiGet<OpsWorkspaceGoalProjection>('/api/workspace/ops-workspace-goals', { cache: 'no-store' })
          .then((value) => { setLoadedGoals(value); setGoalError(null); })
          .catch(() => setGoalError('Workspace goals could not be loaded. Affected: canonical goal text and criteria only. Still available: current cycle status and prior records. Next: retry this bounded read.')),
    ]);
  }, [controlled, goalsControlled]);
  useEffect(() => { void load(); }, [load]);
  const title = workspaceKey ? `${projectWorkspaceOwnerTruth(data, workspaceKey, goals).displayName} cycle conclusion` : 'Ops Standup Summary and Conclusion';
  const cycleContext = useMemo(() => data?.cycle_date
    ? `Cycle ${data.cycle_date} · conclusion attempt ${data.ops_conclusion_attempt_number ?? 'unverified'} · observed ${utcLabel(data.observed_at)} on AI Clone UTC`
    : 'Waiting for the first synchronized portfolio cycle.', [data?.cycle_date, data?.observed_at, data?.ops_conclusion_attempt_number]);

  return <section id="ops-standup-summary" aria-labelledby="ops-summary-title" style={panel}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
      <div style={{ minWidth: 0 }}>
        <p style={{ color: '#38bdf8', margin: '0 0 4px', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '.08em' }}>{workspaceKey ? 'Selected workspace truth' : 'Daily owner artifact'}</p>
        <h2 id="ops-summary-title" style={{ color: 'white', margin: 0, fontSize: 'clamp(20px, 4vw, 24px)' }}>{title}</h2>
        <p style={{ color: '#94a3b8', margin: '5px 0 0', fontSize: '13px', lineHeight: 1.5 }}>{workspaceKey ? 'Understand what this workspace concluded, what needs you, and what the next Dream cycle may consume.' : 'Understand the portfolio conclusion, then open one workspace only when its detail matters.'}</p>
        <p style={{ color: '#64748b', margin: '4px 0 0', fontSize: '12px' }}>{cycleContext}</p>
      </div>
      {!controlled ? <button type="button" onClick={() => void load()} style={{ alignSelf: 'start', color: '#bae6fd', background: '#0c4a6e', border: '1px solid #0369a1', borderRadius: '8px', padding: '8px 12px' }}>Refresh</button> : null}
    </div>
    {error ? <p role="alert" style={{ color: '#fca5a5', margin: 0, lineHeight: 1.5 }}>{error}</p> : null}
    {goalError ? <p role="alert" style={{ color: '#fcd34d', margin: 0, lineHeight: 1.5 }}>{goalError}</p> : null}
    {!data && !error ? <p role={controlled ? 'alert' : 'status'} style={{ color: controlled ? '#fca5a5' : '#94a3b8', margin: 0 }}>{controlled ? 'The current Ops projection is unavailable. Other loaded Ops capabilities remain usable; no cycle-success claim is being made.' : 'Loading the latest bounded conclusion…'}</p> : null}
    {data ? workspaceKey ? <ScopedWorkspaceSummary data={data} workspaceKey={workspaceKey} goalProjection={goals} /> : <PortfolioSummary data={data} goalProjection={goals} /> : null}
  </section>;
}
