'use client';

import { useId, useMemo, useState, type CSSProperties, type FormEvent } from 'react';

import type { WorkspaceRegistryEntry } from '@/lib/workspace-registry';

export type RequestWorkInput = {
  request_id: string;
  workspace_key: string;
  outcome: string;
  context?: string;
  acceptance_criteria: string[];
  artifacts_expected: string[];
  approved_for_queue: true;
};

export type RequestWorkCard = {
  id: string;
  title: string;
  status: string;
  owner?: string | null;
  source?: string | null;
  payload?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

export type RequestWorkQueueEntry = {
  card_id: string;
  title: string;
  workspace_key: string;
  pm_status: string;
  execution_state: string;
  manager_agent: string;
  target_agent: string;
  workspace_agent?: string | null;
  execution_mode: string;
  requested_by?: string | null;
  assigned_runner?: string | null;
  lane: string;
  reason?: string | null;
  source?: string | null;
  front_door_agent?: string | null;
  trigger_key?: string | null;
  manager_attention_required?: boolean;
  executor_status?: string | null;
  executor_worker_id?: string | null;
  execution_packet_path?: string | null;
  sop_path?: string | null;
  briefing_path?: string | null;
  latest_result_status?: string | null;
  latest_result_summary?: string | null;
  latest_result_artifacts?: string[];
  execution_gate_decision?: 'AUTO_EXECUTE' | 'REQUIRE_APPROVAL';
  execution_gate_reason?: string | null;
  execution_gate_risk_factors?: string[];
  execution_gate_approval_state?: 'not_required' | 'missing' | 'stale' | 'approved';
  execution_gate_authorization_current?: boolean;
  queued_at?: string | null;
  last_transition_at?: string | null;
};

export type RequestWorkRouting = {
  workspace_key: string;
  manager_agent: string;
  target_agent: string;
  workspace_agent?: string | null;
  execution_mode: string;
};

export type RequestWorkResult = {
  card: RequestWorkCard;
  queue_entry: RequestWorkQueueEntry;
  routing: RequestWorkRouting;
  disposition: 'queued' | 'already_active' | 'approval_required';
};

export type RequestWorkFormProps = {
  workspaceRegistry: readonly WorkspaceRegistryEntry[];
  onRequestWork: (request: RequestWorkInput) => Promise<RequestWorkResult>;
  registryLoading?: boolean;
  registryError?: string | null;
  onOpenWorkOrder?: (cardId: string) => void;
};

const MAX_LIST_ITEMS = 6;

function createRequestId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }

  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function parseList(value: string): string[] {
  const seen = new Set<string>();
  const items: string[] = [];

  for (const line of value.split('\n')) {
    const item = line.trim().replace(/^[-*]\s+/, '');
    const key = item.toLowerCase();
    if (!item || seen.has(key)) {
      continue;
    }
    seen.add(key);
    items.push(item);
  }

  return items;
}

function readableError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }
  return 'The signed work order could not be queued. Please try again.';
}

function routingDestination(workspace: WorkspaceRegistryEntry): string {
  return workspace.workspace_agent || workspace.target_agent || workspace.manager_agent;
}

export default function RequestWorkForm({
  workspaceRegistry,
  onRequestWork,
  registryLoading = false,
  registryError = null,
  onOpenWorkOrder,
}: RequestWorkFormProps) {
  const fieldId = useId();
  const workspaces = useMemo(
    () =>
      [...workspaceRegistry]
        .filter((workspace) => workspace.kind === 'executive' || workspace.portfolio_visible)
        .sort((left, right) => left.priority_order - right.priority_order || left.display_name.localeCompare(right.display_name)),
    [workspaceRegistry],
  );
  const [requestId, setRequestId] = useState(createRequestId);
  const [workspaceKey, setWorkspaceKey] = useState('');
  const [outcome, setOutcome] = useState('');
  const [context, setContext] = useState('');
  const [acceptanceText, setAcceptanceText] = useState('');
  const [artifactsText, setArtifactsText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RequestWorkResult | null>(null);

  const selectedWorkspace = useMemo(() => {
    const selected = workspaces.find((workspace) => workspace.key === workspaceKey);
    if (selected) {
      return selected;
    }
    return workspaces.find((workspace) => workspace.key === 'shared_ops') ?? workspaces[0] ?? null;
  }, [workspaceKey, workspaces]);
  const selectedWorkspaceKey = selectedWorkspace?.key ?? '';
  const acceptanceCriteria = useMemo(() => parseList(acceptanceText), [acceptanceText]);
  const artifactsExpected = useMemo(() => parseList(artifactsText), [artifactsText]);
  const tooManyAcceptanceItems = acceptanceCriteria.length > MAX_LIST_ITEMS;
  const tooManyArtifactItems = artifactsExpected.length > MAX_LIST_ITEMS;
  const outcomeReady = outcome.trim().length >= 3;
  const registryReady = workspaces.length > 0 && Boolean(selectedWorkspace);
  const canSubmit =
    !submitting &&
    !registryLoading &&
    !registryError &&
    registryReady &&
    outcomeReady &&
    !tooManyAcceptanceItems &&
    !tooManyArtifactItems;

  function startAnotherRequest() {
    if (result) {
      setResult(null);
    }
    if (error) {
      setError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || !selectedWorkspace) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const queuedResult = await onRequestWork({
        request_id: requestId,
        workspace_key: selectedWorkspace.key,
        outcome: outcome.trim(),
        ...(context.trim() ? { context: context.trim() } : {}),
        acceptance_criteria: acceptanceCriteria,
        artifacts_expected: artifactsExpected,
        approved_for_queue: true,
      });
      setResult(queuedResult);
      setRequestId(createRequestId());
      setOutcome('');
      setContext('');
      setAcceptanceText('');
      setArtifactsText('');
    } catch (requestError) {
      setError(readableError(requestError));
      // Keep requestId unchanged so an uncertain or failed retry is idempotent.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      aria-labelledby={`${fieldId}-heading`}
      style={{
        borderRadius: '22px',
        border: '1px solid rgba(56,189,248,0.3)',
        background: 'linear-gradient(145deg, rgba(8,17,31,0.98), rgba(9,20,37,0.94))',
        boxShadow: '0 18px 45px rgba(2,6,23,0.22), inset 0 1px 0 rgba(148,163,184,0.06)',
        padding: 'clamp(16px, 3vw, 24px)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ maxWidth: '760px' }}>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase', margin: '0 0 7px' }}>
            Private authenticated control
          </p>
          <h2 id={`${fieldId}-heading`} style={{ color: '#f8fafc', fontSize: 'clamp(22px, 4vw, 30px)', lineHeight: 1.15, margin: '0 0 8px' }}>
            What do you want Neo to accomplish?
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6, margin: 0 }}>
            One deliberate click creates a signed work order on Railway and places it on the local launchd queue for the Codex runner.
          </p>
        </div>
        <span
          style={{
            borderRadius: '999px',
            border: '1px solid rgba(34,197,94,0.32)',
            backgroundColor: 'rgba(34,197,94,0.09)',
            color: '#bbf7d0',
            padding: '7px 11px',
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}
        >
          Signed remote queue
        </span>
      </div>

      <div
        aria-label="Trusted execution route"
        style={{
          margin: '18px 0',
          borderRadius: '14px',
          border: '1px solid rgba(56,189,248,0.2)',
          backgroundColor: 'rgba(2,6,23,0.58)',
          padding: '12px 14px',
        }}
      >
        <p style={{ color: '#7dd3fc', fontSize: '10px', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 6px' }}>
          Trusted route · system controlled
        </p>
        <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
          Railway <span aria-hidden="true">→</span> signed PM queue <span aria-hidden="true">→</span> launchd on your Mac <span aria-hidden="true">→</span> Codex runner using your ChatGPT login
        </p>
        <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.5, margin: '5px 0 0' }}>
          This runner path uses no model API token. Project routing is read-only and comes from the canonical registry.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '16px' }}>
        <label htmlFor={`${fieldId}-workspace`} style={labelStyle}>
          Project
          <select
            id={`${fieldId}-workspace`}
            value={selectedWorkspaceKey}
            onChange={(event) => {
              startAnotherRequest();
              setWorkspaceKey(event.target.value);
            }}
            disabled={registryLoading || workspaces.length === 0 || submitting}
            style={{ ...controlStyle, cursor: registryLoading || workspaces.length === 0 ? 'not-allowed' : 'pointer' }}
          >
            {workspaces.length === 0 ? <option value="">No projects available</option> : null}
            {workspaces.map((workspace) => (
              <option key={workspace.key} value={workspace.key}>
                {workspace.kind === 'executive' ? 'Across projects' : workspace.display_name}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor={`${fieldId}-outcome`} style={labelStyle}>
          Outcome
          <textarea
            id={`${fieldId}-outcome`}
            value={outcome}
            onChange={(event) => {
              startAnotherRequest();
              setOutcome(event.target.value);
            }}
            rows={5}
            maxLength={4000}
            placeholder="Describe the finished result you want, not the steps Codex should take."
            disabled={submitting}
            required
            style={{ ...controlStyle, resize: 'vertical', minHeight: '132px', lineHeight: 1.55 }}
          />
          <span style={hintStyle}>Be specific about what “done” should look like. Codex will work inside the selected project boundary.</span>
        </label>

        {selectedWorkspace ? (
          <div
            aria-label="Read-only project routing"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(180px, 100%), 1fr))',
              gap: '8px',
              borderRadius: '14px',
              border: `1px solid ${selectedWorkspace.accent}38`,
              backgroundColor: `${selectedWorkspace.accent}0d`,
              padding: '12px',
            }}
          >
            <div>
              <p style={routeLabelStyle}>Intake</p>
              <p style={routeValueStyle}>Neo</p>
            </div>
            <div>
              <p style={routeLabelStyle}>Manager</p>
              <p style={routeValueStyle}>{selectedWorkspace.manager_agent}</p>
            </div>
            <div>
              <p style={routeLabelStyle}>Project operator</p>
              <p style={routeValueStyle}>{routingDestination(selectedWorkspace)}</p>
            </div>
            <div>
              <p style={routeLabelStyle}>Mode</p>
              <p style={routeValueStyle}>{selectedWorkspace.execution_mode}</p>
            </div>
          </div>
        ) : null}

        <details
          style={{
            borderRadius: '14px',
            border: '1px solid #1f2937',
            backgroundColor: 'rgba(11,19,36,0.72)',
            padding: '12px 14px',
          }}
        >
          <summary style={{ color: '#cbd5e1', cursor: 'pointer', fontSize: '13px', fontWeight: 700 }}>
            Add details, proof of done, or expected files <span style={{ color: '#64748b', fontWeight: 500 }}>(optional)</span>
          </summary>
          <div style={{ display: 'grid', gap: '14px', marginTop: '14px' }}>
            <label htmlFor={`${fieldId}-context`} style={labelStyle}>
              Helpful context
              <textarea
                id={`${fieldId}-context`}
                value={context}
                onChange={(event) => {
                  startAnotherRequest();
                  setContext(event.target.value);
                }}
                rows={3}
                maxLength={6000}
                placeholder="Constraints, background, or decisions Codex should preserve."
                disabled={submitting}
                style={{ ...controlStyle, resize: 'vertical', lineHeight: 1.5 }}
              />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(260px, 100%), 1fr))', gap: '14px' }}>
              <label htmlFor={`${fieldId}-acceptance`} style={labelStyle}>
                Proof of done
                <textarea
                  id={`${fieldId}-acceptance`}
                  value={acceptanceText}
                  onChange={(event) => {
                    startAnotherRequest();
                    setAcceptanceText(event.target.value);
                  }}
                  rows={4}
                  placeholder={'One check per line\nTests pass\nMobile flow is verified'}
                  disabled={submitting}
                  style={{ ...controlStyle, resize: 'vertical', lineHeight: 1.5 }}
                  aria-describedby={`${fieldId}-acceptance-count`}
                />
                <span id={`${fieldId}-acceptance-count`} style={{ ...hintStyle, color: tooManyAcceptanceItems ? '#fca5a5' : hintStyle.color }}>
                  {acceptanceCriteria.length}/{MAX_LIST_ITEMS} checks
                  {tooManyAcceptanceItems ? ' · Remove an item before sending.' : ''}
                </span>
              </label>
              <label htmlFor={`${fieldId}-artifacts`} style={labelStyle}>
                Expected files or evidence
                <textarea
                  id={`${fieldId}-artifacts`}
                  value={artifactsText}
                  onChange={(event) => {
                    startAnotherRequest();
                    setArtifactsText(event.target.value);
                  }}
                  rows={4}
                  placeholder={'One item per line\nImplementation summary\nVerification report'}
                  disabled={submitting}
                  style={{ ...controlStyle, resize: 'vertical', lineHeight: 1.5 }}
                  aria-describedby={`${fieldId}-artifacts-count`}
                />
                <span id={`${fieldId}-artifacts-count`} style={{ ...hintStyle, color: tooManyArtifactItems ? '#fca5a5' : hintStyle.color }}>
                  {artifactsExpected.length}/{MAX_LIST_ITEMS} items
                  {tooManyArtifactItems ? ' · Remove an item before sending.' : ''}
                </span>
              </label>
            </div>
          </div>
        </details>

        <div
          style={{
            borderRadius: '12px',
            border: '1px solid rgba(251,191,36,0.22)',
            backgroundColor: 'rgba(251,191,36,0.06)',
            padding: '10px 12px',
          }}
        >
          <p style={{ color: '#fde68a', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
            Sending approves bounded project work. Publishing, payments, messages, access changes, deletion, and other external-consequence actions still require their own approval.
          </p>
        </div>

        {registryError ? (
          <div role="alert" style={errorStyle}>
            <strong>Project routing is unavailable.</strong> {registryError} Nothing can be sent until the canonical registry is available.
          </div>
        ) : null}
        {error ? (
          <div role="alert" style={errorStyle}>
            <strong>Not confirmed as queued.</strong> {error} Your retry ID was preserved, so pressing Send to Codex again will not create duplicate active work.
          </div>
        ) : null}
        {result ? (
          <div
            role="status"
            aria-live="polite"
            style={{
              borderRadius: '14px',
              border: `1px solid ${result.disposition === 'approval_required' ? 'rgba(251,191,36,0.4)' : 'rgba(34,197,94,0.32)'}`,
              backgroundColor: result.disposition === 'approval_required' ? 'rgba(251,191,36,0.08)' : 'rgba(22,101,52,0.12)',
              padding: '13px 14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
              <div>
                <p style={{ color: result.disposition === 'approval_required' ? '#fbbf24' : '#86efac', fontSize: '11px', fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 5px' }}>
                  {result.disposition === 'approval_required'
                    ? 'Saved · waiting for your explicit approval'
                    : result.disposition === 'already_active'
                      ? 'Already active · no duplicate created'
                      : 'Queued for local Codex'}
                </p>
                <p style={{ color: '#f8fafc', fontSize: '14px', fontWeight: 700, lineHeight: 1.45, margin: '0 0 4px' }}>{result.card.title}</p>
                <p style={{ color: '#bbf7d0', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                  {result.queue_entry.execution_state} · {result.routing.manager_agent} → {result.routing.workspace_agent || result.routing.target_agent}
                </p>
                {result.disposition === 'approval_required' && result.queue_entry.execution_gate_reason ? (
                  <p style={{ color: '#fde68a', fontSize: '12px', lineHeight: 1.5, margin: '6px 0 0' }}>
                    {result.queue_entry.execution_gate_reason}
                  </p>
                ) : null}
              </div>
              {onOpenWorkOrder ? (
                <button type="button" onClick={() => onOpenWorkOrder(result.card.id)} style={secondaryButtonStyle}>
                  Open work order
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <p aria-live="polite" style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
            {registryLoading ? 'Loading trusted project routes…' : 'Safe internal work queues automatically. Consequential work is saved for a separate exact-intent approval.'}
          </p>
          <button
            type="submit"
            disabled={!canSubmit}
            style={{
              borderRadius: '999px',
              border: canSubmit ? '1px solid rgba(56,189,248,0.72)' : '1px solid #334155',
              background: canSubmit ? 'linear-gradient(135deg, #0369a1, #0e7490)' : '#0f172a',
              boxShadow: canSubmit ? '0 10px 25px rgba(14,116,144,0.22)' : 'none',
              color: canSubmit ? '#f0f9ff' : '#64748b',
              minWidth: '168px',
              padding: '11px 18px',
              cursor: submitting ? 'wait' : canSubmit ? 'pointer' : 'not-allowed',
              fontSize: '13px',
              fontWeight: 800,
              letterSpacing: '0.01em',
            }}
          >
            {submitting ? 'Sending securely…' : 'Send to Codex'}
          </button>
        </div>
      </form>
    </section>
  );
}

const labelStyle: CSSProperties = {
  display: 'grid',
  gap: '7px',
  color: '#e2e8f0',
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '0.02em',
};

const controlStyle: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  borderRadius: '12px',
  border: '1px solid #334155',
  backgroundColor: '#020617',
  color: '#f8fafc',
  padding: '11px 12px',
  font: 'inherit',
  fontSize: '14px',
  outlineColor: '#38bdf8',
};

const hintStyle: CSSProperties = {
  color: '#64748b',
  fontSize: '11px',
  fontWeight: 500,
  letterSpacing: 0,
  lineHeight: 1.45,
};

const routeLabelStyle: CSSProperties = {
  color: '#64748b',
  fontSize: '10px',
  fontWeight: 700,
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  margin: '0 0 3px',
};

const routeValueStyle: CSSProperties = {
  color: '#e2e8f0',
  fontSize: '12px',
  fontWeight: 700,
  lineHeight: 1.4,
  margin: 0,
};

const errorStyle: CSSProperties = {
  borderRadius: '12px',
  border: '1px solid rgba(248,113,113,0.32)',
  backgroundColor: 'rgba(127,29,29,0.16)',
  color: '#fecaca',
  padding: '11px 12px',
  fontSize: '12px',
  lineHeight: 1.55,
};

const secondaryButtonStyle: CSSProperties = {
  borderRadius: '999px',
  border: '1px solid rgba(34,197,94,0.38)',
  backgroundColor: 'rgba(2,6,23,0.55)',
  color: '#dcfce7',
  padding: '8px 12px',
  cursor: 'pointer',
  fontSize: '12px',
  fontWeight: 700,
};
