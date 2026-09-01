'use client';

import { useCallback, useEffect, useState } from 'react';
import { controlApiGet } from '@/lib/control-api';
import { safeExternalHttpsUrl } from '@/lib/display-privacy';
import { opsCanonicalDecisionDisplay } from '@/lib/ops-canonical-decision';

type Item = Record<string, unknown>;
type WorkspaceRecursion = {
  workspace_key: string;
  display_name: string;
  goal: Record<string, unknown>;
  changes_since_prior: Item[];
  system_decisions: Item[];
  actions_taken: Item[];
  completed_work: Item[];
  failed_work: Item[];
  carried_forward: Item[];
  owner_decisions: Item[];
  blocked: Item[];
  no_action: Item[];
  recommendations: Item[];
  reference_only: Item[];
  next_cycle_inputs: Item[];
  recommendation_resolutions: Item[];
};
type SharedOpsReconciliation = {
  display_name: string;
  role: 'portfolio_reconciler';
  summary: string;
  goal: Record<string, unknown>;
  evaluated: Item[];
  system_decisions: Item[];
  actions_taken: Item[];
  owner_calls: Item[];
  blocked: Item[];
  no_action: Item[];
  recommendations: Item[];
  reference_only: Item[];
  next_cycle_inputs: Item[];
};
type OpsProjection = {
  generated_at: string;
  observed_at?: string | null;
  ops_conclusion_attempt_number?: number | null;
  state: 'ready' | 'empty' | 'degraded' | 'error';
  reason_codes: string[];
  cycle_date?: string | null;
  status?: string;
  workspace_updates: Item[];
  workspace_recursion: WorkspaceRecursion[];
  shared_ops_reconciliation?: SharedOpsReconciliation | null;
  ai_clone_process_updates: Record<string, unknown>;
  endpoint_and_subsystem_health: Record<string, unknown>;
  work_underway: Item[];
  completed_work: Item[];
  blockers: Item[];
  urgent_escalations: Item[];
  workspace_decisions: Item[];
  ops_decisions: Item[];
  owner_calls: Item[];
  canonical_decisions: Item[];
  decision_readiness?: {
    state?: 'ready' | 'degraded';
    clock_authority?: string;
    checked_at?: string;
    source_updated_at?: string | null;
    blocking_reason_codes?: string[];
    context_warnings?: string[];
  };
  degraded_system_warnings: string[];
  supporting_evidence_links: Item[];
  recommended_next_actions: Item[];
};

const panel: React.CSSProperties = { background: 'rgba(15,23,42,.72)', border: '1px solid #334155', borderRadius: '16px', padding: '20px', display: 'grid', gap: '16px' };
const recursionPanel: React.CSSProperties = { display: 'grid', gap: '12px' };
const recursionCard: React.CSSProperties = { border: '1px solid #334155', borderRadius: '14px', background: 'rgba(2,6,23,.6)', padding: '14px', display: 'grid', gap: '12px' };
const recursionGrid: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '10px' };
const recursionField: React.CSSProperties = { border: '1px solid rgba(71,85,105,.7)', borderRadius: '10px', padding: '10px', background: 'rgba(15,23,42,.55)', minWidth: 0 };
const quietText: React.CSSProperties = { color: '#64748b', fontSize: '12px', margin: 0, lineHeight: 1.45 };

function label(item: Item): string {
  return String(item.summary ?? item.title ?? item.label ?? item.workspace_key ?? 'Recorded item');
}

function detailValue(item: Item, key: string): string | null {
  const value = item[key];
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'string' || typeof value === 'number') {
    const text = String(value).trim();
    return text || null;
  }
  return null;
}

function itemKey(item: Item, index: number): string {
  for (const key of ['recommendation_id', 'result_id', 'action_id', 'decision_id', 'card_id', 'summary', 'title']) {
    const value = detailValue(item, key);
    if (value) return `${key}-${value}-${index}`;
  }
  return `item-${index}`;
}

function evidenceUrl(item: Item): string | null {
  for (const key of ['url', 'href', 'source_url']) {
    const href = safeExternalHttpsUrl(item[key]);
    if (href) return href;
  }
  return null;
}

function utcLabel(value?: string | null) {
  if (!value) return 'not recorded';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return 'not recorded';
  return `${date.toLocaleString('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} UTC`;
}

function ItemList({ title, items, accent = '#cbd5e1', linkEvidence = false }: { title: string; items: Item[]; accent?: string; linkEvidence?: boolean }) {
  if (!items.length) return null;
  return <div><h3 style={{ color: accent, fontSize: '14px', margin: '0 0 8px' }}>{title}</h3><ul style={{ color: '#cbd5e1', margin: 0, paddingLeft: '20px', display: 'grid', gap: '6px' }}>{items.map((item, index) => {
    const href = linkEvidence ? evidenceUrl(item) : null;
    return <li key={`${title}-${index}`}>{href ? <a href={href} target="_blank" rel="noreferrer" style={{ color: '#7dd3fc' }}>{label(item)}</a> : label(item)}{item.provenance_kind ? <small style={{ color: '#64748b' }}> · {String(item.provenance_kind).replaceAll('_', ' ')}</small> : null}</li>;
  })}</ul></div>;
}

function CanonicalDecisionList({ items }: { items: Item[] }) {
  if (!items.length) return null;
  return <div><h3 style={{ color: '#c4b5fd', fontSize: '14px', margin: '0 0 8px' }}>Canonical decisions</h3><ul style={{ color: '#cbd5e1', margin: 0, paddingLeft: '20px', display: 'grid', gap: '8px' }}>{items.map((item, index) => {
    const decision = opsCanonicalDecisionDisplay(item);
    return <li key={`Canonical decisions-${index}`}>
      <strong>{decision.title}</strong>
      {decision.status || decision.stateVersion ? <div><small style={{ color: '#94a3b8' }}>{decision.status ? decision.status.replaceAll('_', ' ') : 'status unavailable'}{decision.stateVersion ? ` · version ${decision.stateVersion}` : ''}</small></div> : null}
      {decision.resolvedChoice ? <div style={{ color: '#e2e8f0', marginTop: '2px' }}><small style={{ color: '#a78bfa' }}>Resolved choice: </small>{decision.resolvedChoice}</div> : null}
    </li>;
  })}</ul></div>;
}

function ProcessUpdates({ updates }: { updates: Record<string, unknown> }) {
  const rows = Object.entries(updates);
  if (!rows.length) return null;
  return <div><h3 style={{ color: '#a5f3fc', fontSize: '14px', margin: '0 0 8px' }}>AI Clone process updates</h3><dl style={{ display: 'grid', gridTemplateColumns: 'minmax(150px, auto) 1fr', gap: '6px 12px', margin: 0, color: '#cbd5e1', fontSize: '13px' }}>{rows.map(([key, value]) => <div key={key} style={{ display: 'contents' }}><dt style={{ color: '#94a3b8' }}>{key.replaceAll('_', ' ')}</dt><dd style={{ margin: 0, overflowWrap: 'anywhere' }}>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl></div>;
}

function RecursionFactList({
  title,
  items,
  accent,
  detailKeys = [],
}: {
  title: string;
  items: Item[];
  accent: string;
  detailKeys?: string[];
}) {
  return <div style={recursionField}>
    <h4 style={{ color: accent, fontSize: '12px', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '.05em' }}>{title}</h4>
    {items.length ? <ul style={{ color: '#cbd5e1', margin: 0, paddingLeft: '18px', display: 'grid', gap: '6px', fontSize: '13px' }}>{items.map((item, index) => {
      const details = detailKeys
        .map((key) => ({ key, value: detailValue(item, key) }))
        .filter((detail): detail is { key: string; value: string } => detail.value !== null);
      return <li key={itemKey(item, index)}>
        {label(item)}
        {details.length ? <div style={{ color: '#94a3b8', fontSize: '11px', marginTop: '3px', display: 'grid', gap: '2px' }}>{details.map((detail) => <span key={detail.key}><strong>{detail.key.replaceAll('_', ' ')}:</strong> {detail.value.replaceAll('_', ' ')}</span>)}</div> : null}
      </li>;
    })}</ul> : <p style={quietText}>None recorded for this cycle.</p>}
  </div>;
}

function GoalSummary({ goal }: { goal: Record<string, unknown> }) {
  const goalText = detailValue(goal, 'goal') ?? detailValue(goal, 'summary');
  const phaseGate = detailValue(goal, 'phase_gate');
  return <div style={{ ...recursionField, gridColumn: '1 / -1' }}>
    <h4 style={{ color: '#7dd3fc', fontSize: '12px', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '.05em' }}>Goal</h4>
    <p style={{ color: goalText ? '#e2e8f0' : '#64748b', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>{goalText ?? 'No machine-readable goal was projected for this cycle.'}</p>
    {phaseGate ? <p style={{ color: '#94a3b8', fontSize: '11px', margin: '6px 0 0', lineHeight: 1.45 }}><strong>Phase gate:</strong> {phaseGate}</p> : null}
  </div>;
}

function WorkspaceRecursionList({ items }: { items: WorkspaceRecursion[] }) {
  if (!items.length) return null;
  return <section aria-labelledby="workspace-recursion-title" style={recursionPanel}>
    <div>
      <h3 id="workspace-recursion-title" style={{ color: '#f8fafc', fontSize: '17px', margin: 0 }}>Workspace recursion truth</h3>
      <p style={{ color: '#94a3b8', fontSize: '12px', margin: '4px 0 0' }}>What each workspace evaluated, decided, did, completed, carried, or escalated in this canonical Ops cycle.</p>
    </div>
    {items.map((workspace) => <article key={workspace.workspace_key} style={recursionCard} aria-labelledby={`recursion-${workspace.workspace_key}`}>
      <h3 id={`recursion-${workspace.workspace_key}`} style={{ color: 'white', fontSize: '15px', margin: 0 }}>{workspace.display_name || workspace.workspace_key}</h3>
      <div style={recursionGrid}>
        <GoalSummary goal={workspace.goal} />
        <RecursionFactList title="What changed" items={workspace.changes_since_prior} accent="#7dd3fc" />
        <RecursionFactList title="AI Clone decided" items={workspace.system_decisions} accent="#c4b5fd" />
        <RecursionFactList title="AI Clone did" items={workspace.actions_taken} accent="#a5f3fc" />
        <RecursionFactList title="Completed" items={workspace.completed_work} accent="#86efac" />
        <RecursionFactList title="Failed" items={workspace.failed_work} accent="#fca5a5" detailKeys={['status', 'retryable']} />
        <RecursionFactList title="Carried forward" items={workspace.carried_forward} accent="#fcd34d" />
        <RecursionFactList title="Needs owner" items={workspace.owner_decisions} accent="#fde68a" detailKeys={['state', 'trigger']} />
        <RecursionFactList title="Blocked" items={workspace.blocked} accent="#fdba74" detailKeys={['dependency', 'reason']} />
        <RecursionFactList title="No eligible change" items={workspace.no_action} accent="#94a3b8" detailKeys={['trigger']} />
        <RecursionFactList title="AI Clone recommends" items={workspace.recommendations} accent="#c4b5fd" detailKeys={['trigger', 'future_trigger']} />
        <RecursionFactList title="Reference only" items={workspace.reference_only} accent="#94a3b8" detailKeys={['classification', 'ref']} />
        <RecursionFactList title="Next-cycle input" items={workspace.next_cycle_inputs} accent="#67e8f9" />
        <RecursionFactList title="Recommendation resolution" items={workspace.recommendation_resolutions} accent="#d8b4fe" detailKeys={['state', 'explanation', 'future_trigger']} />
      </div>
    </article>)}
  </section>;
}

export function SharedOpsReconciliationSummary({ summary }: { summary?: SharedOpsReconciliation | null }) {
  if (!summary) return null;
  return <section aria-labelledby="shared-ops-reconciliation-title" style={recursionPanel}>
    <div>
      <h3 id="shared-ops-reconciliation-title" style={{ color: '#f8fafc', fontSize: '17px', margin: 0 }}>Shared Ops reconciliation</h3>
      <p style={{ color: '#94a3b8', fontSize: '12px', margin: '4px 0 0' }}>Read-only portfolio reconciliation. Shared Ops evaluates and routes cross-workspace truth; it does not execute project work or become a seventh project workspace.</p>
    </div>
    <article style={recursionCard} data-shared-ops-role={summary.role}>
      <h3 style={{ color: 'white', fontSize: '15px', margin: 0 }}>{summary.display_name}</h3>
      <p style={{ color: '#cbd5e1', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>{summary.summary}</p>
      <div style={recursionGrid}>
        <GoalSummary goal={summary.goal} />
        <RecursionFactList title="Ops evaluated" items={summary.evaluated} accent="#7dd3fc" />
        <RecursionFactList title="AI Clone decided" items={summary.system_decisions} accent="#c4b5fd" />
        <RecursionFactList title="AI Clone did" items={summary.actions_taken} accent="#a5f3fc" detailKeys={['status']} />
        <RecursionFactList title="Needs owner" items={summary.owner_calls} accent="#fde68a" detailKeys={['state', 'trigger']} />
        <RecursionFactList title="Blocked" items={summary.blocked} accent="#fdba74" detailKeys={['workspace_key', 'dependency', 'reason']} />
        <RecursionFactList title="No eligible change" items={summary.no_action} accent="#94a3b8" detailKeys={['trigger']} />
        <RecursionFactList title="AI Clone recommends" items={summary.recommendations} accent="#c4b5fd" detailKeys={['trigger', 'future_trigger']} />
        <RecursionFactList title="Reference only" items={summary.reference_only} accent="#94a3b8" detailKeys={['workspace_key', 'classification', 'ref']} />
        <RecursionFactList title="Next Dream consumes" items={summary.next_cycle_inputs} accent="#67e8f9" detailKeys={['workspace_key', 'trigger']} />
      </div>
    </article>
  </section>;
}

export default function OpsStandupSummary() {
  const [data, setData] = useState<OpsProjection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setData(await controlApiGet<OpsProjection>('/api/workspace/ops-standup', { cache: 'no-store' }));
      setError(null);
    } catch {
      setError('The Ops summary could not be loaded. No readiness claim is being made.');
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <section id="ops-standup-summary" aria-labelledby="ops-summary-title" style={panel}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
      <div><p style={{ color: '#38bdf8', margin: '0 0 4px', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '.08em' }}>Daily owner artifact</p><h2 id="ops-summary-title" style={{ color: 'white', margin: 0, fontSize: '24px' }}>Ops Standup Summary and Conclusion</h2><p style={{ color: '#94a3b8', margin: '6px 0 0' }}>{data?.cycle_date ? `Portfolio cycle ${data.cycle_date} · conclusion attempt ${data.ops_conclusion_attempt_number ?? 'unverified'} · observed ${utcLabel(data.observed_at)} on AI Clone UTC` : 'Waiting for the first synchronized portfolio cycle.'}</p></div>
      <button type="button" onClick={() => void load()} style={{ alignSelf: 'start', color: '#bae6fd', background: '#0c4a6e', border: '1px solid #0369a1', borderRadius: '8px', padding: '8px 12px' }}>Refresh</button>
    </div>
    {error ? <p role="alert" style={{ color: '#fca5a5', margin: 0 }}>{error}</p> : null}
    {!data && !error ? <p role="status" style={{ color: '#94a3b8', margin: 0 }}>Loading the latest Ops conclusion…</p> : null}
    {data?.state === 'empty' ? <p role="status" style={{ color: '#fbbf24', margin: 0 }}>No final Ops conclusion has been generated yet.</p> : null}
    {data && (data.state === 'degraded' || data.state === 'error') ? <div role="alert" style={{ border: '1px solid #b45309', background: 'rgba(120,53,15,.25)', borderRadius: '10px', padding: '12px', color: '#fde68a' }}><strong>Degraded system</strong><ul style={{ marginBottom: 0 }}>{data.reason_codes.map((warning) => <li key={warning}>{warning.replaceAll('_', ' ')}</li>)}</ul></div> : null}
    {data && data.degraded_system_warnings.length > 0 ? <div role="alert" data-ops-subsystem-warnings="visible" style={{ border: '1px solid #b45309', background: 'rgba(120,53,15,.18)', borderRadius: '10px', padding: '12px', color: '#fde68a' }}><strong>Subsystem warnings</strong><ul style={{ marginBottom: 0 }}>{data.degraded_system_warnings.map((warning) => <li key={warning}>{warning.replaceAll('_', ' ')}</li>)}</ul></div> : null}
    {data?.decision_readiness?.state === 'ready' ? <p style={{ color: '#86efac', margin: 0, fontSize: '12px' }}>Canonical owner decisions were checked on {data.decision_readiness.clock_authority === 'ai_clone_utc' ? 'the AI Clone UTC clock' : 'an unverified clock'}. Unrelated health warnings remain visible above without changing that record’s write authority.</p> : null}
    {data ? <>
      <ItemList title="Workspace updates" items={data.workspace_updates} accent="#7dd3fc" />
      <SharedOpsReconciliationSummary summary={data.shared_ops_reconciliation} />
      <WorkspaceRecursionList items={data.workspace_recursion ?? []} />
      <ProcessUpdates updates={data.ai_clone_process_updates} />
      <ItemList title="Urgent escalations" items={data.urgent_escalations} accent="#fca5a5" />
      <ItemList title="Owner calls" items={data.owner_calls} accent="#fcd34d" />
      <ItemList title="Blockers" items={data.blockers} accent="#fdba74" />
      <ItemList title="Work underway" items={data.work_underway} />
      <ItemList title="Completed work" items={data.completed_work} accent="#86efac" />
      <ItemList title="Workspace decisions" items={data.workspace_decisions} />
      <ItemList title="Ops decisions" items={data.ops_decisions} />
      <CanonicalDecisionList items={data.canonical_decisions} />
      <ItemList title="Supporting evidence" items={data.supporting_evidence_links} accent="#67e8f9" linkEvidence />
      <ItemList title="Recommended next actions" items={data.recommended_next_actions ?? []} accent="#c4b5fd" />
      <details><summary style={{ color: '#94a3b8', cursor: 'pointer' }}>Endpoint and subsystem health</summary><pre style={{ color: '#cbd5e1', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(data.endpoint_and_subsystem_health, null, 2)}</pre></details>
    </> : null}
  </section>;
}
