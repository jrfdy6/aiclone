'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  CanonicalDecision,
  CanonicalDecisionJobReceipt,
  CanonicalDecisionJobStatus,
  canonicalDecisionActionEndpoint,
  canonicalDecisionActionRequest,
  reconcileCanonicalDecisionViews,
  ReconciledCanonicalDecision,
  waitForCanonicalDecisionJob,
} from '@/lib/canonical-decisions';
import { controlApiGet, controlApiPost, ownerSafeErrorMessage } from '@/lib/control-api';

type ContentDecisionProjection = {
  schema_version?: string;
  generated_at?: string;
  state?: 'ready' | 'empty' | 'degraded' | 'error';
  reason_codes?: string[];
  activity_summary?: { decisions?: { recent?: CanonicalDecision[] } };
  controller_capabilities?: Record<string, boolean>;
  controller_gaps?: Array<{ capability?: string; reason_code?: string; safe_behavior?: string }>;
};

type OpsDecisionProjection = {
  schema_version?: string;
  generated_at?: string;
  state?: 'ready' | 'empty' | 'degraded' | 'error';
  reason_codes?: string[];
  canonical_decisions?: CanonicalDecision[];
};

type DecisionMutationGate = {
  readReady: boolean;
  controllerReady: boolean;
  message: string;
};

type DecisionReadResult = {
  viewsCurrent: boolean;
  controllerReady: boolean;
};

const checkingGate: DecisionMutationGate = {
  readReady: false,
  controllerReady: false,
  message: 'Checking Content, Ops, and signed decision controls…',
};

const unavailableReadResult: DecisionReadResult = {
  viewsCurrent: false,
  controllerReady: false,
};

function projectionReadIsCurrent(
  projection: { schema_version?: string; generated_at?: string; state?: string },
  schemaVersion: string,
) {
  return projection.schema_version === schemaVersion
    && (projection.state === 'ready' || projection.state === 'empty')
    && Number.isFinite(Date.parse(projection.generated_at ?? ''));
}

function controllerUnavailableMessage(projection: ContentDecisionProjection) {
  const safeBehavior = projection.controller_gaps?.find(
    (gap) => gap.capability === 'decision_resolution',
  )?.safe_behavior;
  const normalized = typeof safeBehavior === 'string'
    ? safeBehavior.replace(/\s+/g, ' ').trim()
    : '';
  const fallback = 'Signed decision controls are temporarily unavailable. No decision will change.';
  return normalized && normalized.length <= 180
    ? ownerSafeErrorMessage(normalized, fallback)
    : fallback;
}

function newRequestId() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID();
  return `owner-decision-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function readable(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const terminal = new Set(['resolved', 'canceled', 'superseded']);

export default function OwnerDecisionSurface() {
  const [decisions, setDecisions] = useState<ReconciledCanonicalDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [mutationGate, setMutationGate] = useState<DecisionMutationGate>(checkingGate);
  const [title, setTitle] = useState('');
  const [interactionMode, setInteractionMode] = useState<'simple' | 'complex'>('simple');
  const [createRequestId, setCreateRequestId] = useState(newRequestId);
  const [resolutionById, setResolutionById] = useState<Record<string, string>>({});
  const [statusById, setStatusById] = useState<Record<string, string>>({});
  const [createStatus, setCreateStatus] = useState<string | null>(null);
  const [createPendingJob, setCreatePendingJob] = useState<string | null>(null);
  const [pendingJobByDecisionId, setPendingJobByDecisionId] = useState<Record<string, string>>({});
  const mutationGateRef = useRef<DecisionMutationGate>(checkingGate);
  const currentDecisionsRef = useRef(new Map<string, ReconciledCanonicalDecision>());
  const createPendingRef = useRef(false);
  const pendingDecisionIdsRef = useRef(new Set<string>());
  const readRequestRef = useRef(0);

  const updateMutationGate = useCallback((next: DecisionMutationGate) => {
    mutationGateRef.current = next;
    setMutationGate(next);
  }, []);

  const load = useCallback(async () => {
    const readRequest = readRequestRef.current + 1;
    readRequestRef.current = readRequest;
    setLoading(true);
    updateMutationGate(checkingGate);
    try {
      const [content, ops] = await Promise.all([
        controlApiGet<ContentDecisionProjection>('/api/workspace/integrated-content', { cache: 'no-store' }),
        controlApiGet<OpsDecisionProjection>('/api/workspace/ops-standup', { cache: 'no-store' }),
      ]);
      if (readRequest !== readRequestRef.current) return unavailableReadResult;
      const contentDecisions = Array.isArray(content.activity_summary?.decisions?.recent)
        ? content.activity_summary.decisions.recent
        : [];
      const opsDecisions = Array.isArray(ops.canonical_decisions) ? ops.canonical_decisions : [];
      const reconciled = reconcileCanonicalDecisionViews(contentDecisions, opsDecisions);
      currentDecisionsRef.current = new Map(reconciled.map((decision) => [decision.decision_id, decision]));
      setDecisions(reconciled);

      const viewsCurrent = projectionReadIsCurrent(content, 'integrated_content_portfolio/v1')
        && projectionReadIsCurrent(ops, 'ops_standup_summary_conclusion/v1');
      if (!viewsCurrent) {
        updateMutationGate({
          readReady: false,
          controllerReady: false,
          message: 'Content and Ops are not both current. Decision controls remain paused.',
        });
        return unavailableReadResult;
      }

      const controllerReady = content.controller_capabilities?.decision_resolution === true;
      updateMutationGate({
        readReady: true,
        controllerReady,
        message: controllerReady ? '' : controllerUnavailableMessage(content),
      });
      return { viewsCurrent: true, controllerReady };
    } catch {
      if (readRequest !== readRequestRef.current) return unavailableReadResult;
      updateMutationGate({
        readReady: false,
        controllerReady: false,
        message: 'Content and Ops could not both be verified. Decision controls remain paused.',
      });
      return unavailableReadResult;
    } finally {
      if (readRequest === readRequestRef.current) setLoading(false);
    }
  }, [updateMutationGate]);

  useEffect(() => { void load(); }, [load]);

  const waitForJob = useCallback(async (receipt: CanonicalDecisionJobReceipt) => {
    return waitForCanonicalDecisionJob({
      receipt,
      readStatus: (jobId) => controlApiGet<CanonicalDecisionJobStatus>(
        `/api/workspace/decisions/jobs/${encodeURIComponent(jobId)}`,
        { cache: 'no-store' },
      ),
    });
  }, []);

  const createDecision = useCallback(async () => {
    const gate = mutationGateRef.current;
    if (!gate.readReady || !gate.controllerReady) {
      setCreateStatus(gate.message);
      return;
    }
    if (createPendingRef.current) {
      setCreateStatus('This exact decision request is already in progress.');
      return;
    }
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setCreateStatus('Add the owner call before creating the decision.');
      return;
    }
    createPendingRef.current = true;
    setCreatePendingJob('requesting');
    setCreateStatus('Requesting one signed canonical decision job…');
    try {
      const receipt = await controlApiPost<CanonicalDecisionJobReceipt>('/api/workspace/decisions', {
        decision_type: 'owner_call',
        title: cleanTitle,
        interaction_mode: interactionMode,
        route: 'uncertain',
        surface: 'workspace',
        idempotency_key: createRequestId,
      });
      setCreatePendingJob(receipt.job_id || 'requesting');
      setCreateStatus('Waiting for this exact signed decision job…');
      await waitForJob(receipt);
      setTitle('');
      setCreateRequestId(newRequestId());
      const refreshed = await load();
      setCreateStatus(refreshed.viewsCurrent
        ? 'Decision created. Content and Ops were refreshed.'
        : 'The decision job completed, but both owner views are not current yet. Refresh before another change.');
    } catch (caught) {
      // Keep createRequestId stable so an owner retry cannot create duplicate work.
      const message = ownerSafeErrorMessage(caught, 'The canonical decision was not created.');
      await load();
      setCreateStatus(message);
    } finally {
      createPendingRef.current = false;
      setCreatePendingJob(null);
    }
  }, [createRequestId, interactionMode, load, title, waitForJob]);

  const applyAction = useCallback(async (
    decision: ReconciledCanonicalDecision,
    action: 'begin_session' | 'resolve' | 'block' | 'reopen' | 'cancel',
  ) => {
    const gate = mutationGateRef.current;
    if (!gate.readReady || !gate.controllerReady) {
      setStatusById((current) => ({ ...current, [decision.decision_id]: gate.message }));
      return;
    }
    const currentDecision = currentDecisionsRef.current.get(decision.decision_id);
    if (
      !currentDecision
      || currentDecision.projection_conflict
      || decision.projection_conflict
      || currentDecision.state_version !== decision.state_version
      || currentDecision.status !== decision.status
    ) {
      setStatusById((current) => ({ ...current, [decision.decision_id]: 'This decision view is stale. Refresh Content and Ops before changing it.' }));
      return;
    }
    if (pendingDecisionIdsRef.current.has(decision.decision_id)) {
      setStatusById((current) => ({ ...current, [decision.decision_id]: 'This exact decision action is already in progress.' }));
      return;
    }
    let request: ReturnType<typeof canonicalDecisionActionRequest>;
    try {
      request = canonicalDecisionActionRequest(
        currentDecision,
        action,
        resolutionById[decision.decision_id] ?? '',
      );
    } catch (caught) {
      setStatusById((current) => ({
        ...current,
        [decision.decision_id]: ownerSafeErrorMessage(caught, 'Review this decision before changing it.'),
      }));
      return;
    }

    pendingDecisionIdsRef.current.add(decision.decision_id);
    setPendingJobByDecisionId((current) => ({ ...current, [decision.decision_id]: 'requesting' }));
    setStatusById((current) => ({ ...current, [decision.decision_id]: `Requesting ${readable(action)} at version ${currentDecision.state_version}…` }));
    try {
      const receipt = await controlApiPost<CanonicalDecisionJobReceipt>(
        canonicalDecisionActionEndpoint(decision.decision_id),
        request,
      );
      setPendingJobByDecisionId((current) => ({ ...current, [decision.decision_id]: receipt.job_id || 'requesting' }));
      setStatusById((current) => ({ ...current, [decision.decision_id]: 'Waiting for this exact signed decision job…' }));
      await waitForJob(receipt);
      const refreshed = await load();
      const refreshedDecision = currentDecisionsRef.current.get(decision.decision_id);
      const viewsAgree = refreshed.viewsCurrent
        && refreshedDecision !== undefined
        && !refreshedDecision.projection_conflict
        && refreshedDecision.state_version > currentDecision.state_version;
      setStatusById((current) => ({
        ...current,
        [decision.decision_id]: viewsAgree
          ? 'Decision updated. Content and Ops now agree.'
          : 'The decision job completed, but both owner views are not current yet. Refresh before another change.',
      }));
    } catch (caught) {
      const message = ownerSafeErrorMessage(caught, 'The decision action failed.');
      await load();
      setStatusById((current) => ({
        ...current,
        [decision.decision_id]: message,
      }));
    } finally {
      pendingDecisionIdsRef.current.delete(decision.decision_id);
      setPendingJobByDecisionId((current) => {
        const next = { ...current };
        delete next[decision.decision_id];
        return next;
      });
    }
  }, [load, resolutionById, waitForJob]);

  const controlsReady = mutationGate.readReady && mutationGate.controllerReady && !loading;

  return <section id="owner-decision-surface" aria-labelledby="owner-decision-title" style={panelStyle}>
    <div style={headerStyle}>
      <div>
        <p style={eyebrowStyle}>One record · many views</p>
        <h2 id="owner-decision-title" style={titleStyle}>Owner Decisions</h2>
        <p style={helperStyle}>Simple calls resolve inline. Complex calls use one shared session. Every write is version-checked on the Mac before canonical SQL changes.</p>
      </div>
      <button type="button" onClick={() => void load()} disabled={loading} style={buttonStyle}>{loading ? 'Refreshing…' : 'Refresh'}</button>
    </div>

    {!controlsReady ? <p role={loading ? 'status' : 'alert'} style={loading ? helperStyle : alertStyle}>{mutationGate.message}</p> : null}
    <div style={createStyle}>
      <label style={fieldStyle}>New owner call
        <input value={title} disabled={createPendingJob !== null} onChange={(event) => setTitle(event.target.value)} placeholder="What needs one canonical decision?" style={inputStyle} />
      </label>
      <label style={fieldStyle}>Decision path
        <select value={interactionMode} disabled={createPendingJob !== null} onChange={(event) => setInteractionMode(event.target.value as 'simple' | 'complex')} style={inputStyle}>
          <option value="simple">Simple · resolve inline</option>
          <option value="complex">Complex · shared session</option>
        </select>
      </label>
      <button type="button" aria-busy={createPendingJob !== null} disabled={!controlsReady || createPendingJob !== null} onClick={() => void createDecision()} style={buttonStyle}>{createPendingJob ? 'Creating one decision…' : 'Create canonical decision'}</button>
      {createStatus ? <p role="status" style={helperStyle}>{createStatus}</p> : null}
    </div>

    {!loading && mutationGate.readReady && !decisions.length ? <p role="status" style={helperStyle}>No canonical decisions are currently projected.</p> : null}
    <div style={{ display: 'grid', gap: '10px' }}>
      {decisions.map((decision) => {
        const isTerminal = terminal.has(decision.status);
        const mayResolve = decision.interaction_mode === 'simple' || decision.status === 'in_session';
        const decisionPendingJob = pendingJobByDecisionId[decision.decision_id];
        const decisionControlsDisabled = !controlsReady || decision.projection_conflict || Boolean(decisionPendingJob);
        return <article key={decision.decision_id} style={cardStyle}>
          <div style={headerStyle}>
            <div>
              <strong style={{ color: 'white' }}>{decision.title}</strong>
              <p style={helperStyle}>{readable(decision.decision_type)} · {readable(decision.status)} · version {decision.state_version}</p>
            </div>
            <span style={pillStyle}>{readable(decision.interaction_mode)}</span>
          </div>
          <div style={pillRowStyle}>
            <span style={pillStyle}>Route {readable(decision.route)}</span>
            {decision.visible_in.map((surface) => <span key={surface} style={pillStyle}>Visible in {readable(surface)}</span>)}
            {decision.session_ref ? <span style={pillStyle}>Shared session active</span> : null}
          </div>
          {decision.projection_conflict ? <p role="alert" style={warningStyle}>Content and Ops do not agree on this record yet. Actions are disabled until a refresh shows the same status and version in both views.</p> : null}
          {Object.keys(decision.resolution ?? {}).length ? <p style={helperStyle}>Resolution: {String(decision.resolution.choice ?? JSON.stringify(decision.resolution))}</p> : null}
          {!isTerminal ? <>
            {mayResolve ? <label style={fieldStyle}>Canonical resolution
              <textarea value={resolutionById[decision.decision_id] ?? ''} disabled={decisionControlsDisabled} onChange={(event) => setResolutionById((current) => ({ ...current, [decision.decision_id]: event.target.value }))} placeholder="Record the exact owner call" style={{ ...inputStyle, minHeight: '72px' }} />
            </label> : null}
            <div style={pillRowStyle}>
              {decision.interaction_mode === 'complex' && decision.status !== 'in_session' ? <button type="button" aria-busy={Boolean(decisionPendingJob)} disabled={decisionControlsDisabled} onClick={() => void applyAction(decision, 'begin_session')} style={buttonStyle}>Open shared decision session</button> : null}
              {mayResolve ? <button type="button" aria-busy={Boolean(decisionPendingJob)} disabled={decisionControlsDisabled} onClick={() => void applyAction(decision, 'resolve')} style={buttonStyle}>Resolve canonical decision</button> : null}
              {decision.status === 'blocked' ? <button type="button" aria-busy={Boolean(decisionPendingJob)} disabled={decisionControlsDisabled} onClick={() => void applyAction(decision, 'reopen')} style={secondaryButtonStyle}>Reopen in Ops</button> : <button type="button" aria-busy={Boolean(decisionPendingJob)} disabled={decisionControlsDisabled} onClick={() => void applyAction(decision, 'block')} style={secondaryButtonStyle}>Mark blocked</button>}
              <button type="button" aria-busy={Boolean(decisionPendingJob)} disabled={decisionControlsDisabled} onClick={() => void applyAction(decision, 'cancel')} style={secondaryButtonStyle}>Cancel</button>
            </div>
          </> : null}
          {statusById[decision.decision_id] ? <p role="status" style={helperStyle}>{statusById[decision.decision_id]}</p> : null}
          <small style={identityStyle}>Canonical ID {decision.decision_id} · no publishing, messaging, or external communication occurs here.</small>
        </article>;
      })}
    </div>
  </section>;
}

const panelStyle: React.CSSProperties = { padding: '20px', borderRadius: '14px', border: '1px solid rgba(196,181,253,.28)', background: 'rgba(15,23,42,.82)', display: 'grid', gap: '16px' };
const headerStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' };
const eyebrowStyle: React.CSSProperties = { margin: 0, color: '#c4b5fd', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.1em' };
const titleStyle: React.CSSProperties = { color: 'white', margin: '4px 0', fontSize: '24px' };
const helperStyle: React.CSSProperties = { color: '#94a3b8', margin: '4px 0 0', fontSize: '12px', lineHeight: 1.5 };
const alertStyle: React.CSSProperties = { color: '#fecaca', border: '1px solid #991b1b', borderRadius: '8px', padding: '10px', margin: 0 };
const warningStyle: React.CSSProperties = { color: '#fde68a', border: '1px solid #92400e', borderRadius: '8px', padding: '9px', margin: 0, fontSize: '12px' };
const createStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))', gap: '10px', alignItems: 'end' };
const fieldStyle: React.CSSProperties = { color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px' };
const inputStyle: React.CSSProperties = { width: '100%', boxSizing: 'border-box', borderRadius: '7px', border: '1px solid #475569', background: '#0f172a', color: '#e2e8f0', padding: '8px', font: 'inherit' };
const buttonStyle: React.CSSProperties = { border: '1px solid rgba(167,139,250,.55)', borderRadius: '8px', background: 'rgba(109,40,217,.26)', color: '#ddd6fe', padding: '8px 12px', minHeight: '42px', cursor: 'pointer', touchAction: 'manipulation' };
const secondaryButtonStyle: React.CSSProperties = { ...buttonStyle, borderColor: '#475569', background: 'rgba(30,41,59,.7)', color: '#cbd5e1' };
const cardStyle: React.CSSProperties = { padding: '13px', borderRadius: '10px', border: '1px solid rgba(148,163,184,.2)', background: 'rgba(2,6,23,.56)', display: 'grid', gap: '10px' };
const pillRowStyle: React.CSSProperties = { display: 'flex', gap: '7px', flexWrap: 'wrap', alignItems: 'center' };
const pillStyle: React.CSSProperties = { padding: '4px 7px', border: '1px solid rgba(148,163,184,.24)', borderRadius: '999px', color: '#cbd5e1', fontSize: '11px' };
const identityStyle: React.CSSProperties = { color: '#64748b', overflowWrap: 'anywhere' };
