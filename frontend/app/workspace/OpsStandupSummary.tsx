'use client';

import { useCallback, useEffect, useState } from 'react';
import { controlApiGet } from '@/lib/control-api';
import { safeExternalHttpsUrl } from '@/lib/display-privacy';
import { opsCanonicalDecisionDisplay } from '@/lib/ops-canonical-decision';

type Item = Record<string, unknown>;
type OpsProjection = {
  generated_at: string;
  observed_at?: string | null;
  state: 'ready' | 'empty' | 'degraded' | 'error';
  reason_codes: string[];
  cycle_date?: string | null;
  status?: string;
  workspace_updates: Item[];
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
  recommended_next_actions: string[];
};

const panel: React.CSSProperties = { background: 'rgba(15,23,42,.72)', border: '1px solid #334155', borderRadius: '16px', padding: '20px', display: 'grid', gap: '16px' };

function label(item: Item): string {
  return String(item.summary ?? item.title ?? item.label ?? item.workspace_key ?? 'Recorded item');
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
      <div><p style={{ color: '#38bdf8', margin: '0 0 4px', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '.08em' }}>Daily owner artifact</p><h2 id="ops-summary-title" style={{ color: 'white', margin: 0, fontSize: '24px' }}>Ops Standup Summary and Conclusion</h2><p style={{ color: '#94a3b8', margin: '6px 0 0' }}>{data?.cycle_date ? `Portfolio cycle ${data.cycle_date} · observed ${utcLabel(data.observed_at)} on AI Clone UTC` : 'Waiting for the first synchronized portfolio cycle.'}</p></div>
      <button type="button" onClick={() => void load()} style={{ alignSelf: 'start', color: '#bae6fd', background: '#0c4a6e', border: '1px solid #0369a1', borderRadius: '8px', padding: '8px 12px' }}>Refresh</button>
    </div>
    {error ? <p role="alert" style={{ color: '#fca5a5', margin: 0 }}>{error}</p> : null}
    {!data && !error ? <p role="status" style={{ color: '#94a3b8', margin: 0 }}>Loading the latest Ops conclusion…</p> : null}
    {data?.state === 'empty' ? <p role="status" style={{ color: '#fbbf24', margin: 0 }}>No final Ops conclusion has been generated yet.</p> : null}
    {data && (data.state === 'degraded' || data.state === 'error') ? <div role="alert" style={{ border: '1px solid #b45309', background: 'rgba(120,53,15,.25)', borderRadius: '10px', padding: '12px', color: '#fde68a' }}><strong>Degraded system</strong><ul style={{ marginBottom: 0 }}>{[...data.degraded_system_warnings, ...data.reason_codes].map((warning) => <li key={warning}>{warning.replaceAll('_', ' ')}</li>)}</ul></div> : null}
    {data?.decision_readiness?.state === 'ready' ? <p style={{ color: '#86efac', margin: 0, fontSize: '12px' }}>Canonical owner decisions were checked on {data.decision_readiness.clock_authority === 'ai_clone_utc' ? 'the AI Clone UTC clock' : 'an unverified clock'}. Unrelated health warnings remain visible above without changing that record’s write authority.</p> : null}
    {data ? <>
      <ItemList title="Workspace updates" items={data.workspace_updates} accent="#7dd3fc" />
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
      {data.recommended_next_actions.length ? <div><h3 style={{ color: '#c4b5fd', fontSize: '14px', margin: '0 0 8px' }}>Recommended next actions</h3><ol style={{ color: '#e2e8f0', margin: 0, paddingLeft: '20px' }}>{data.recommended_next_actions.map((item) => <li key={item}>{item}</li>)}</ol></div> : null}
      <details><summary style={{ color: '#94a3b8', cursor: 'pointer' }}>Endpoint and subsystem health</summary><pre style={{ color: '#cbd5e1', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>{JSON.stringify(data.endpoint_and_subsystem_health, null, 2)}</pre></details>
    </> : null}
  </section>;
}
