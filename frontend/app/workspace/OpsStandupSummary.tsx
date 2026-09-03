'use client';

import { useCallback, useEffect, useState } from 'react';
import { controlApiGet } from '@/lib/control-api';
import { normalizeDisplayText, safeExternalHttpsUrl } from '@/lib/display-privacy';
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
const INTERNAL_UUID_PATTERN = /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi;

function ownerText(value: unknown, limit = 900): string {
  const normalized = normalizeDisplayText(String(value ?? ''))
    .replace(/\[private-workspace-context\]/gi, 'private workspace context')
    .replace(INTERNAL_UUID_PATTERN, 'record')
    .replace(/\bai-swag-store\b/gi, 'AI Swag Store')
    .replace(/\beasyoutfitapp\b/gi, 'Easy Outfit App')
    .replace(/\bfeezie-os\b/gi, 'FEEZIE OS')
    .replace(/\bfusion-os\b/gi, 'Fusion OS')
    .replace(/\bwork-life-tools\b/gi, 'Work Life Tools')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return normalized.slice(0, limit);
}

function ownerStatus(value: unknown): string {
  return ownerText(value, 160).replaceAll('_', ' ');
}

function label(item: Item): string {
  return ownerText(item.summary ?? item.title ?? item.label ?? item.workspace_key ?? 'Recorded item');
}

function ownerPreview(value: unknown, limit = 260): string {
  const text = ownerText(value, Math.max(limit + 1, 80));
  const firstSentence = text.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim();
  const candidate = firstSentence && firstSentence.length >= 28 ? firstSentence : text;
  return candidate.length > limit ? `${candidate.slice(0, Math.max(0, limit - 1)).trimEnd()}…` : candidate;
}

function ownerItemSummary(item: Item, limit = 260): string {
  const rawSummary = String(item.summary ?? '').trim();
  const trigger = item.future_trigger ?? item.trigger;
  if (rawSummary === 'participant_receipt_unavailable') {
    const workspace = ownerStatus(item.workspace_key);
    const next = trigger ? ` Next: ${ownerPreview(trigger, 190)}` : '';
    return `${workspace ? `${workspace.toUpperCase()} is waiting because a required participant receipt is unavailable.` : 'A required participant receipt is unavailable.'}${next}`;
  }
  if (rawSummary === 'No conclusion receipt received.' && item.workspace_key) {
    return `${ownerStatus(item.workspace_key)} did not return a conclusion receipt.`;
  }
  return ownerPreview(label(item), limit);
}

function uniqueOwnerItems(items: Item[]): Item[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = [item.workspace_key, item.summary, item.reason_code].map((value) => String(value ?? '')).join('|');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
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
      <strong>{ownerText(decision.title)}</strong>
      {decision.status || decision.stateVersion ? <div><small style={{ color: '#94a3b8' }}>{decision.status ? ownerStatus(decision.status) : 'status unavailable'}{decision.stateVersion ? ` · version ${ownerText(decision.stateVersion, 80)}` : ''}</small></div> : null}
      {decision.resolvedChoice ? <div style={{ color: '#e2e8f0', marginTop: '2px' }}><small style={{ color: '#a78bfa' }}>Resolved choice: </small>{ownerText(decision.resolvedChoice)}</div> : null}
    </li>;
  })}</ul></div>;
}

function ProcessUpdates({ updates }: { updates: Record<string, unknown> }) {
  const rows = Object.entries(updates);
  if (!rows.length) return null;
  return <div>
    <h3 style={{ color: '#a5f3fc', fontSize: '14px', margin: '0 0 8px' }}>AI Clone process updates</h3>
    <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
      {rows.length} internal process receipt{rows.length === 1 ? '' : 's'} accompanied this cycle. Open System for bounded health and runtime diagnostics; raw payloads do not belong in owner guidance.
    </p>
  </div>;
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
        {details.length ? <div style={{ color: '#94a3b8', fontSize: '11px', marginTop: '3px', display: 'grid', gap: '2px' }}>{details.map((detail) => <span key={detail.key}><strong>{detail.key.replaceAll('_', ' ')}:</strong> {ownerStatus(detail.value)}</span>)}</div> : null}
      </li>;
    })}</ul> : <p style={quietText}>None recorded for this cycle.</p>}
  </div>;
}

function GoalSummary({ goal }: { goal: Record<string, unknown> }) {
  const goalText = detailValue(goal, 'goal') ?? detailValue(goal, 'summary');
  const phaseGate = detailValue(goal, 'phase_gate');
  return <div style={{ ...recursionField, gridColumn: '1 / -1' }}>
    <h4 style={{ color: '#7dd3fc', fontSize: '12px', margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '.05em' }}>Goal</h4>
    <p style={{ color: goalText ? '#e2e8f0' : '#64748b', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>{goalText ? ownerText(goalText) : 'No machine-readable goal was projected for this cycle.'}</p>
    {phaseGate ? <p style={{ color: '#94a3b8', fontSize: '11px', margin: '6px 0 0', lineHeight: 1.45 }}><strong>Phase gate:</strong> {ownerText(phaseGate)}</p> : null}
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
      <h3 id={`recursion-${workspace.workspace_key}`} style={{ color: 'white', fontSize: '15px', margin: 0 }}>{ownerText(workspace.display_name || workspace.workspace_key)}</h3>
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
      <h3 style={{ color: 'white', fontSize: '15px', margin: 0 }}>{ownerText(summary.display_name)}</h3>
      <p style={{ color: '#cbd5e1', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>{ownerText(summary.summary)}</p>
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

  const sharedOps = data?.shared_ops_reconciliation;
  const ownerItems = data
    ? uniqueOwnerItems([
        ...(data.owner_calls ?? []),
        ...(sharedOps?.owner_calls ?? []),
        ...(data.workspace_recursion ?? []).flatMap((workspace) => (workspace.owner_decisions ?? []).map((item) => ({ workspace_key: workspace.workspace_key, ...item }))),
      ])
    : [];
  const blockedItems = data
    ? uniqueOwnerItems([
        ...(data.blockers ?? []),
        ...(sharedOps?.blocked ?? []),
        ...(data.workspace_recursion ?? []).flatMap((workspace) => (workspace.blocked ?? []).map((item) => ({ workspace_key: workspace.workspace_key, ...item }))),
      ])
    : [];
  const actionItems = data
    ? uniqueOwnerItems([
        ...(sharedOps?.actions_taken ?? []),
        ...(data.completed_work ?? []),
        ...(data.workspace_recursion ?? []).flatMap((workspace) => (workspace.actions_taken ?? []).map((item) => ({ workspace_key: workspace.workspace_key, ...item }))),
      ])
    : [];
  const recommendationItems = data
    ? uniqueOwnerItems([
        ...(data.recommended_next_actions ?? []),
        ...(sharedOps?.recommendations ?? []),
        ...(data.workspace_recursion ?? []).flatMap((workspace) => (workspace.recommendations ?? []).map((item) => ({ workspace_key: workspace.workspace_key, ...item }))),
      ])
    : [];
  const nextCycleItems = data
    ? uniqueOwnerItems([
        ...(sharedOps?.next_cycle_inputs ?? []),
        ...(data.workspace_recursion ?? []).flatMap((workspace) => (workspace.next_cycle_inputs ?? []).map((item) => ({ workspace_key: workspace.workspace_key, ...item }))),
      ])
    : [];
  const recordedWorkspaceUpdates = data?.workspace_updates?.filter((item) => item.state !== 'missing') ?? [];
  const missingWorkspaceUpdates = data?.workspace_updates?.filter((item) => item.state === 'missing') ?? [];
  const explicitDreamInput = nextCycleItems.find((item) => /^The next Dream\b/i.test(String(item.summary ?? '')));
  const ownerSummaryRows = data
    ? [
        {
          label: 'Current state',
          value:
            data.state === 'ready'
              ? 'Ready. The latest bounded portfolio conclusion is available.'
              : data.state === 'empty'
                ? 'Empty. No final portfolio conclusion has been recorded yet.'
                : data.state === 'error'
                  ? 'Unavailable. The final portfolio conclusion could not be loaded; no readiness claim is being made.'
                  : 'Degraded. The latest portfolio conclusion is incomplete; affected capabilities and missing workspace conclusions are identified above.',
          tone: data.state === 'ready' ? '#86efac' : data.state === 'empty' ? '#fcd34d' : '#fda4af',
        },
        {
          label: 'What changed',
          value: recordedWorkspaceUpdates.length
            ? `${recordedWorkspaceUpdates.length} workspace update${recordedWorkspaceUpdates.length === 1 ? '' : 's'} returned; ${missingWorkspaceUpdates.length} did not return a conclusion. First recorded change: ${ownerPreview(label(recordedWorkspaceUpdates[0]), 220)}`
            : missingWorkspaceUpdates.length
              ? `${missingWorkspaceUpdates.length} project workspace${missingWorkspaceUpdates.length === 1 ? '' : 's'} did not return a conclusion receipt.`
            : 'No new workspace update is claimed by this cycle.',
          tone: '#cbd5e1',
        },
        {
          label: 'AI Clone did this',
          value: actionItems.length
            ? ownerItemSummary(actionItems[0])
            : 'No completed system action is recorded for this cycle.',
          tone: '#a5f3fc',
        },
        {
          label: 'Needs your decision',
          value: ownerItems.length
            ? `${ownerItems.length} item${ownerItems.length === 1 ? ' needs' : 's need'} owner attention. First: ${ownerItemSummary(ownerItems[0])}`
            : 'No owner decision is recorded for this cycle.',
          tone: ownerItems.length ? '#fde68a' : '#94a3b8',
        },
        {
          label: 'Blocked',
          value: blockedItems.length
            ? `${blockedItems.length} bounded blocker${blockedItems.length === 1 ? ' remains' : 's remain'}. First: ${ownerItemSummary(blockedItems[0])}`
            : 'No blocker is recorded in the current conclusion.',
          tone: blockedItems.length ? '#fdba74' : '#86efac',
        },
        {
          label: 'What remains healthy',
          value: data.decision_readiness?.state === 'ready'
            ? 'Canonical owner-decision checks remain verified; loaded workspace goals and prior cycle evidence remain readable.'
            : 'Loaded workspace goals and prior cycle evidence remain readable. Decision controls stay paused until their own readiness check passes.',
          tone: data.decision_readiness?.state === 'ready' ? '#86efac' : '#cbd5e1',
        },
        {
          label: 'AI Clone recommends',
          value: recommendationItems.length
            ? ownerItemSummary(recommendationItems[0])
            : 'No new recommendation is recorded for this cycle.',
          tone: '#c4b5fd',
        },
        {
          label: 'Next Dream consumes',
          value: explicitDreamInput
            ? ownerItemSummary(explicitDreamInput)
            : nextCycleItems.length
            ? ownerItemSummary(nextCycleItems[0])
            : 'The next natural cycle may use the current canonical conclusion and unresolved PM state; no new input is claimed here.',
          tone: '#67e8f9',
        },
      ]
    : [];

  return <section id="ops-standup-summary" aria-labelledby="ops-summary-title" style={panel}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
      <div><p style={{ color: '#38bdf8', margin: '0 0 4px', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '.08em' }}>Daily owner artifact</p><h2 id="ops-summary-title" style={{ color: 'white', margin: 0, fontSize: '24px' }}>Ops Standup Summary and Conclusion</h2><p style={{ color: '#94a3b8', margin: '6px 0 0' }}>{data?.cycle_date ? `Portfolio cycle ${data.cycle_date} · conclusion attempt ${data.ops_conclusion_attempt_number ?? 'unverified'} · observed ${utcLabel(data.observed_at)} on AI Clone UTC` : 'Waiting for the first synchronized portfolio cycle.'}</p></div>
      <button type="button" onClick={() => void load()} style={{ alignSelf: 'start', color: '#bae6fd', background: '#0c4a6e', border: '1px solid #0369a1', borderRadius: '8px', padding: '8px 12px' }}>Refresh</button>
    </div>
    {error ? <p role="alert" style={{ color: '#fca5a5', margin: 0 }}>{error}</p> : null}
    {!data && !error ? <p role="status" style={{ color: '#94a3b8', margin: 0 }}>Loading the latest Ops conclusion…</p> : null}
    {data?.state === 'empty' ? <p role="status" style={{ color: '#fbbf24', margin: 0 }}>No final Ops conclusion has been generated yet.</p> : null}
    {data && (data.state === 'degraded' || data.state === 'error') ? <div role="alert" style={{ border: '1px solid #b45309', background: 'rgba(120,53,15,.25)', borderRadius: '10px', padding: '12px', color: '#fde68a', display: 'grid', gap: '6px' }}>
      <strong>{data.state === 'error' ? 'Portfolio conclusion unavailable' : 'Portfolio conclusion degraded'}</strong>
      <p style={{ margin: 0, lineHeight: 1.5 }}>Affected: the complete portfolio conclusion and the missing workspace lanes listed below.</p>
      <p style={{ margin: 0, lineHeight: 1.5 }}>Still available: loaded workspace goals, prior cycle evidence, and separately verified owner-decision readiness.</p>
      <p style={{ margin: 0, lineHeight: 1.5 }}>Next: repair the missing conclusion lanes; do not treat this cycle as a portfolio all-clear.</p>
      {data.reason_codes.length ? <details><summary style={{ cursor: 'pointer' }}>Technical reason codes</summary><ul style={{ marginBottom: 0 }}>{data.reason_codes.map((warning) => <li key={warning}>{ownerStatus(warning)}</li>)}</ul></details> : null}
    </div> : null}
    {data && data.degraded_system_warnings.length > 0 ? <div role="alert" data-ops-subsystem-warnings="visible" style={{ border: '1px solid #b45309', background: 'rgba(120,53,15,.18)', borderRadius: '10px', padding: '12px', color: '#fde68a' }}><strong>What is affected</strong><ul style={{ marginBottom: 0 }}>{data.degraded_system_warnings.slice(0, 5).map((warning) => <li key={warning}>{ownerText(warning)}</li>)}</ul>{data.degraded_system_warnings.length > 5 ? <p style={{ margin: '8px 0 0' }}>+{data.degraded_system_warnings.length - 5} more in the cycle audit.</p> : null}</div> : null}
    {data?.decision_readiness?.state === 'ready' ? <p style={{ color: '#86efac', margin: 0, fontSize: '12px' }}>Canonical owner decisions were checked on {data.decision_readiness.clock_authority === 'ai_clone_utc' ? 'the AI Clone UTC clock' : 'an unverified clock'}. Unrelated health warnings remain visible above without changing that record’s write authority.</p> : null}
    {data ? <>
      <div data-ops-owner-summary="primary" style={{ borderTop: '1px solid #334155', borderBottom: '1px solid #334155' }}>
        {ownerSummaryRows.map((row, index) => <div key={row.label} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(220px, 100%), 1fr))', gap: '8px 16px', padding: '10px 0', borderTop: index === 0 ? 'none' : '1px solid rgba(51,65,85,.65)' }}>
          <p style={{ color: row.tone, margin: 0, fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em' }}>{row.label}</p>
          <p style={{ color: '#dbe7ff', margin: 0, fontSize: '13px', lineHeight: 1.5 }}>{row.value}</p>
        </div>)}
      </div>
      <details data-ops-cycle-audit="secondary" style={{ border: '1px solid #334155', borderRadius: '12px', padding: '12px' }}>
        <summary style={{ color: '#7dd3fc', cursor: 'pointer', fontWeight: 700 }}>Open cycle audit, workspace recursion, and supporting evidence</summary>
        <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5 }}>These records explain lineage and subsystem detail. They are secondary to the current state and owner action above.</p>
        <div style={{ display: 'grid', gap: '16px', marginTop: '14px' }}>
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
          <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>Endpoint and subsystem diagnostics are available in System, where their scope and health context can be reviewed together.</p>
        </div>
      </details>
    </> : null}
  </section>;
}
