'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { apiGet, apiPost } from '@/lib/api-client';
import type {
  EmailDraftEngine,
  EmailThreadDraftLifecycleAction,
  EmailDraftMode,
  EmailDraftType,
  EmailThread,
  EmailThreadDraftLifecycleResponse,
  EmailThreadDraftResponse,
  EmailThreadEscalateResponse,
  EmailThreadSaveDraftResponse,
} from '@/lib/email-types';
import { formatUiTimestamp } from '@/lib/ui-dates';

const EMAIL_THREAD_LOAD_TIMEOUT_MS = 45_000;
const EMAIL_THREAD_ROUTE_TIMEOUT_MS = 30_000;
const EMAIL_THREAD_DRAFT_TIMEOUT_MS = 45_000;
const EMAIL_THREAD_SAVE_DRAFT_TIMEOUT_MS = 45_000;
const EMAIL_THREAD_DRAFT_LIFECYCLE_TIMEOUT_MS = 30_000;
const EMAIL_THREAD_ESCALATE_TIMEOUT_MS = 30_000;
const EMAIL_THREAD_CODEX_POLL_MS = 4_000;

const WORKSPACE_OPTIONS = [
  'agc',
  'fusion-os',
  'feezie-os',
  'easyoutfitapp',
  'ai-swag-store',
  'shared_ops',
];

const AGC_LANE_OPTIONS = [
  'consulting_opportunity',
  'product_sourcing',
  'supplier_partner',
  'registrations_compliance',
  'finance_admin',
  'noise_archive',
];

export default function InboxThreadPage() {
  const params = useParams<{ threadId: string }>();
  const threadId = String(params?.threadId ?? '');
  const [thread, setThread] = useState<EmailThread | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [workspaceKey, setWorkspaceKey] = useState('shared_ops');
  const [lane, setLane] = useState('manual_review');
  const [draftType, setDraftType] = useState<EmailDraftType>('qualify');
  const [draftMode, setDraftMode] = useState<EmailDraftMode>('email_reply');
  const [draftEngine, setDraftEngine] = useState<EmailDraftEngine>('template');
  const [operatorNotes, setOperatorNotes] = useState('');

  const tabs = useMemo(
    () => [
      {
        key: 'portfolio-inbox',
        label: 'Portfolio Inbox',
        active: true,
        onSelect: () => undefined,
      },
    ],
    [],
  );

  async function loadThread() {
    try {
      setLoading(true);
      setError(null);
      const result = await apiGet<EmailThread>(`/api/email/threads/${threadId}`, {
        timeoutMs: EMAIL_THREAD_LOAD_TIMEOUT_MS,
      });
      setThread(result);
      setWorkspaceKey(result.workspace_key);
      setLane(result.lane);
      setDraftType((result.draft_type as EmailDraftType | null) ?? defaultDraftType(result));
      setDraftMode(result.draft_mode ?? 'email_reply');
      setDraftEngine(result.draft_engine ?? defaultDraftEngine(result));
      setOperatorNotes(existingOperatorNotes(result));
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : 'Unable to load email thread right now.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!threadId) {
      return;
    }
    void loadThread();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  useEffect(() => {
    if (!thread?.draft_job_id) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadThread();
    }, EMAIL_THREAD_CODEX_POLL_MS);
    return () => {
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread?.draft_job_id]);

  useEffect(() => {
    if (workspaceKey === 'agc') {
      if (!AGC_LANE_OPTIONS.includes(lane)) {
        setLane('consulting_opportunity');
      }
      return;
    }
    const nonAgcOptions = ['primary', 'manual_review', 'ops_admin'];
    if (!nonAgcOptions.includes(lane)) {
      setLane(workspaceKey === 'shared_ops' ? 'manual_review' : 'primary');
    }
  }, [lane, workspaceKey]);

  async function saveRoute() {
    try {
      setStatus('Saving routing decision...');
      const result = await apiPost<EmailThread>(`/api/email/threads/${threadId}/route`, {
        workspace_key: workspaceKey,
        lane,
      }, {
        timeoutMs: EMAIL_THREAD_ROUTE_TIMEOUT_MS,
      });
      setThread(result);
      setStatus('Routing saved.');
    } catch (issue) {
      setStatus(issue instanceof Error ? issue.message : 'Unable to save routing right now.');
    }
  }

  async function restoreAutoRoute() {
    try {
      setStatus('Restoring auto routing...');
      const result = await apiPost<EmailThread>(`/api/email/threads/${threadId}/route/reset`, {}, {
        timeoutMs: EMAIL_THREAD_ROUTE_TIMEOUT_MS,
      });
      setThread(result);
      setWorkspaceKey(result.workspace_key);
      setLane(result.lane);
      setStatus('Auto routing restored.');
    } catch (issue) {
      setStatus(issue instanceof Error ? issue.message : 'Unable to restore auto routing right now.');
    }
  }

  async function generateDraft() {
    try {
      setStatus('Generating draft...');
      const result = await apiPost<EmailThreadDraftResponse>(`/api/email/threads/${threadId}/draft`, {
        draft_type: draftType,
        draft_mode: draftMode,
        draft_engine: draftEngine,
        source_mode: draftEngine === 'content_generation' || draftEngine === 'codex_job' ? 'email_thread_grounded' : undefined,
        operator_notes: operatorNotes.trim() || undefined,
      }, {
        timeoutMs: EMAIL_THREAD_DRAFT_TIMEOUT_MS,
      });
      setThread(result.thread);
      setDraftMode(result.thread.draft_mode ?? draftMode);
      setDraftEngine(result.thread.draft_engine ?? draftEngine);
      setStatus(draftStatusMessage(result.thread, result.draft_type));
    } catch (issue) {
      setStatus(issue instanceof Error ? issue.message : 'Unable to generate draft right now.');
    }
  }

  const generationAvailability = thread ? contentGenerationAvailability(thread) : null;
  const draftAudit = thread ? readDraftAudit(thread) : null;
  const localDraftStatePresent = thread ? hasLocalDraftState(thread) : false;
  const providerDraftStatePresent = thread ? hasProviderDraftState(thread) : false;

  async function escalateThread() {
    try {
      setStatus('Escalating thread...');
      const result = await apiPost<EmailThreadEscalateResponse>(`/api/email/threads/${threadId}/escalate`, {
        reason: 'Manual escalation from inbox detail page.',
        create_pm_card: true,
      }, {
        timeoutMs: EMAIL_THREAD_ESCALATE_TIMEOUT_MS,
      });
      setThread(result.thread);
      setStatus(result.pm_card_id ? `Escalated and linked to PM card ${result.pm_card_id}.` : result.message);
    } catch (issue) {
      setStatus(issue instanceof Error ? issue.message : 'Unable to escalate thread right now.');
    }
  }

  async function saveDraftToProvider() {
    try {
      setStatus(providerDraftActionLabel(thread) === 'Update Gmail draft' ? 'Updating Gmail draft...' : 'Saving Gmail draft...');
      const result = await apiPost<EmailThreadSaveDraftResponse>(`/api/email/threads/${threadId}/draft/save`, {
        overwrite_existing: true,
      }, {
        timeoutMs: EMAIL_THREAD_SAVE_DRAFT_TIMEOUT_MS,
      });
      setThread(result.thread);
      setStatus(result.message);
    } catch (issue) {
      setStatus(issue instanceof Error ? issue.message : 'Unable to save the Gmail draft right now.');
    }
  }

  async function runDraftLifecycle(action: EmailThreadDraftLifecycleAction) {
    try {
      setStatus(draftLifecycleStatusMessage(action, thread));
      const result = await apiPost<EmailThreadDraftLifecycleResponse>(`/api/email/threads/${threadId}/draft/lifecycle`, {
        action,
      }, {
        timeoutMs: EMAIL_THREAD_DRAFT_LIFECYCLE_TIMEOUT_MS,
      });
      setThread(result.thread);
      setDraftType((result.thread.draft_type as EmailDraftType | null) ?? defaultDraftType(result.thread));
      setDraftMode(result.thread.draft_mode ?? 'email_reply');
      setDraftEngine(result.thread.draft_engine ?? defaultDraftEngine(result.thread));
      setOperatorNotes(existingOperatorNotes(result.thread));
      setStatus(result.message);
    } catch (issue) {
      setStatus(issue instanceof Error ? issue.message : 'Unable to update draft lifecycle right now.');
    }
  }

  return (
    <RuntimePage module="ops" tabs={tabs} maxWidth="1280px">
      <section style={{ display: 'grid', gap: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div>
            <p style={{ color: '#60a5fa', fontSize: '11px', letterSpacing: '0.16em', textTransform: 'uppercase', margin: 0 }}>Thread Detail</p>
            <h1 style={{ color: 'white', fontSize: '28px', margin: '6px 0 0' }}>{thread?.subject || 'Inbox thread'}</h1>
          </div>
          <Link
            href="/inbox"
            style={{
              borderRadius: '999px',
              border: '1px solid rgba(148,163,184,0.22)',
              backgroundColor: '#08101f',
              color: '#e2e8f0',
              textDecoration: 'none',
              padding: '10px 14px',
              fontSize: '13px',
              fontWeight: 700,
            }}
          >
            Back to Inbox
          </Link>
        </div>

        {error ? <Notice tone="#fca5a5" message={error} /> : null}
        {status ? <Notice tone="#cbd5e1" message={status} /> : null}
        {loading ? (
          <Panel>
            <p style={{ color: '#94a3b8', margin: 0 }}>Loading thread…</p>
          </Panel>
        ) : thread ? (
          <>
            <Panel>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '10px' }}>
                <div>
                  <p style={{ color: 'white', fontSize: '18px', fontWeight: 700, margin: 0 }}>{thread.from_name || thread.organization || thread.from_address}</p>
                  <p style={{ color: '#94a3b8', fontSize: '13px', margin: '6px 0 0' }}>
                    {thread.from_address} · {formatUiTimestamp(thread.last_message_at)}
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {pill(`workspace:${thread.workspace_key}`, '#38bdf8')}
                  {pill(`lane:${thread.lane}`, thread.workspace_key === 'agc' ? '#a78bfa' : '#94a3b8')}
                  {thread.needs_human ? pill('needs human', '#fbbf24') : null}
                  {thread.high_value ? pill('high value', '#34d399') : null}
                  {thread.high_risk ? pill('high risk', '#f87171') : null}
                </div>
              </div>
              {thread.provider_labels.length ? (
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
                  {thread.provider_labels.map((label) => pill(`gmail:${label}`, '#22c55e'))}
                </div>
              ) : null}
              <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.6, margin: 0 }}>{thread.excerpt || thread.summary}</p>
            </Panel>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(320px, 0.8fr)', gap: '16px' }}>
              <Panel>
                <p style={sectionEyebrowStyle}>Thread History</p>
                <div style={{ display: 'grid', gap: '12px' }}>
                  {thread.messages.map((message) => (
                    <article key={message.id} style={{ borderRadius: '14px', border: '1px solid rgba(148,163,184,0.14)', backgroundColor: '#08101f', padding: '12px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '8px' }}>
                        <p style={{ color: 'white', fontWeight: 700, margin: 0 }}>{message.from_name || message.from_address}</p>
                        <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{formatUiTimestamp(message.received_at)}</p>
                      </div>
                      <p style={{ color: '#cbd5e1', fontSize: '13px', lineHeight: 1.6, margin: 0 }}>{message.body_text}</p>
                    </article>
                  ))}
                </div>
              </Panel>

              <div style={{ display: 'grid', gap: '16px' }}>
                <Panel>
                  <p style={sectionEyebrowStyle}>Routing Panel</p>
                  <div style={{ display: 'grid', gap: '10px' }}>
                    {thread.last_route_source === 'manual' ? (
                      <div style={{ borderRadius: '12px', border: '1px solid rgba(251,191,36,0.22)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '12px' }}>
                        <p style={{ color: '#fde68a', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                          This thread is currently on a manual override. Restoring auto routing will clear the manual workspace/lane decision and re-run the live classifier.
                        </p>
                      </div>
                    ) : null}
                    <label style={fieldLabelStyle}>
                      Workspace
                      <select value={workspaceKey} onChange={(event) => setWorkspaceKey(event.target.value)} style={selectStyle}>
                        {WORKSPACE_OPTIONS.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label style={fieldLabelStyle}>
                      Lane
                      <select value={lane} onChange={(event) => setLane(event.target.value)} style={selectStyle}>
                        {(workspaceKey === 'agc' ? AGC_LANE_OPTIONS : ['primary', 'manual_review', 'ops_admin']).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button type="button" onClick={() => void saveRoute()} style={primaryButtonStyle}>
                      Save routing
                    </button>
                    {thread.last_route_source === 'manual' ? (
                      <button type="button" onClick={() => void restoreAutoRoute()} style={secondaryButtonStyle}>
                        Restore auto routing
                      </button>
                    ) : null}
                  </div>
                </Panel>

                <Panel>
                  <p style={sectionEyebrowStyle}>Draft Panel</p>
                  <div style={{ display: 'grid', gap: '10px' }}>
                    <label style={fieldLabelStyle}>
                      Draft type
                      <select value={draftType} onChange={(event) => setDraftType(event.target.value as EmailDraftType)} style={selectStyle}>
                        <option value="acknowledge">acknowledge</option>
                        <option value="qualify">qualify</option>
                        <option value="schedule">schedule</option>
                        <option value="decline_or_redirect">decline_or_redirect</option>
                      </select>
                    </label>
                    <label style={fieldLabelStyle}>
                      Draft engine
                      <select value={draftEngine} onChange={(event) => setDraftEngine(event.target.value as EmailDraftEngine)} style={selectStyle}>
                        <option value="codex_job">codex_job</option>
                        <option value="content_generation">content_generation</option>
                        <option value="template">template</option>
                      </select>
                    </label>
                    <label style={fieldLabelStyle}>
                      Draft mode
                      <select value={draftMode} onChange={(event) => setDraftMode(event.target.value as EmailDraftMode)} style={selectStyle}>
                        <option value="email_reply">email_reply</option>
                        <option value="email_follow_up">email_follow_up</option>
                        <option value="outbound_email">outbound_email</option>
                      </select>
                    </label>
                    <label style={fieldLabelStyle}>
                      Operator notes
                      <textarea
                        value={operatorNotes}
                        onChange={(event) => setOperatorNotes(event.target.value)}
                        rows={4}
                        placeholder="Optional grounding notes for the draft engine."
                        style={textareaStyle}
                      />
                    </label>
                    {(draftEngine === 'content_generation' || draftEngine === 'codex_job') && generationAvailability ? (
                      <p
                        style={{
                          color: generationAvailability.eligible ? '#86efac' : '#fde68a',
                          fontSize: '12px',
                          lineHeight: 1.5,
                          margin: 0,
                        }}
                      >
                        {generationAvailability.eligible
                          ? draftEngine === 'codex_job'
                            ? 'Grounded Codex drafting is eligible on this thread.'
                            : 'Grounded AI drafting is eligible on this thread.'
                          : `${draftEngine === 'codex_job' ? 'Codex drafting' : 'Grounded AI'} will fall back to the template path: ${describeGenerationReason(generationAvailability.reason)}`}
                      </p>
                    ) : null}
                    <button type="button" onClick={() => void generateDraft()} style={primaryButtonStyle}>
                      Generate draft
                    </button>
                    {thread.draft_job_id && !thread.draft_body ? (
                      <div style={{ borderRadius: '12px', border: '1px solid rgba(167,139,250,0.22)', backgroundColor: 'rgba(167,139,250,0.08)', padding: '12px' }}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                          {pill(`engine:${thread.draft_engine ?? 'codex_job'}`, '#a78bfa')}
                          {pill('path:codex_job_pending', '#c4b5fd')}
                          {pill(`job:${thread.draft_job_id.slice(0, 8)}`, '#94a3b8')}
                        </div>
                        <p style={{ color: '#e9d5ff', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                          Codex draft job is queued and this page will refresh automatically until the draft is ready.
                        </p>
                      </div>
                    ) : null}
                    {thread.draft_body ? (
                      <div style={{ borderRadius: '12px', border: '1px solid rgba(96,165,250,0.18)', backgroundColor: 'rgba(96,165,250,0.06)', padding: '12px' }}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                          {thread.draft_engine ? pill(`engine:${thread.draft_engine}`, thread.draft_engine === 'codex_job' ? '#a78bfa' : thread.draft_engine === 'content_generation' ? '#60a5fa' : '#cbd5e1') : null}
                          {draftAudit?.selectedPath ? pill(`path:${draftAudit.selectedPath}`, draftAudit.selectedPath === 'codex_job' ? '#a78bfa' : draftAudit.selectedPath === 'content_generation' ? '#22c55e' : '#fbbf24') : null}
                          {thread.draft_source_mode ? pill(`source:${thread.draft_source_mode}`, '#93c5fd') : null}
                          {thread.draft_generated_at ? pill(`generated:${formatUiTimestamp(thread.draft_generated_at)}`, '#94a3b8') : null}
                        </div>
                        <p style={{ color: '#93c5fd', fontSize: '12px', margin: '0 0 8px' }}>{thread.draft_subject}</p>
                        <pre
                          style={{
                            margin: 0,
                            whiteSpace: 'pre-wrap',
                            fontFamily: 'inherit',
                            color: '#e2e8f0',
                            fontSize: '13px',
                            lineHeight: 1.6,
                          }}
                        >
                          {thread.draft_body}
                        </pre>
                        <div style={{ display: 'grid', gap: '6px', marginTop: '10px' }}>
                          {thread.draft_confidence != null ? (
                            <p style={{ color: '#cbd5e1', fontSize: '12px', margin: 0 }}>
                              Draft confidence: {(thread.draft_confidence * 100).toFixed(0)}%
                            </p>
                          ) : null}
                          {draftAudit?.generationReason ? (
                            <p style={{ color: '#cbd5e1', fontSize: '12px', margin: 0 }}>
                              Bridge note: {describeGenerationReason(draftAudit.generationReason)}
                            </p>
                          ) : null}
                          {thread.provider === 'gmail' ? (
                            <p style={{ color: '#cbd5e1', fontSize: '12px', margin: 0 }}>
                              Gmail draft state: {providerDraftStateLabel(thread)}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                    {!thread.draft_body && draftAudit?.selectedPath === 'codex_job_failed' ? (
                      <div style={{ borderRadius: '12px', border: '1px solid rgba(248,113,113,0.22)', backgroundColor: 'rgba(248,113,113,0.08)', padding: '12px' }}>
                        <p style={{ color: '#fecaca', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                          Codex draft failed: {describeGenerationReason(draftAudit.generationReason)}{draftAudit.generationError ? ` (${draftAudit.generationError})` : ''}.
                        </p>
                      </div>
                    ) : null}
                    {!thread.draft_body && providerDraftStatePresent ? (
                      <div style={{ borderRadius: '12px', border: '1px solid rgba(96,165,250,0.18)', backgroundColor: 'rgba(96,165,250,0.06)', padding: '12px' }}>
                        <p style={{ color: '#cbd5e1', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                          Gmail draft state: {providerDraftStateLabel(thread)}
                        </p>
                      </div>
                    ) : null}
                    {thread.provider === 'gmail' && thread.draft_body ? (
                      <button type="button" onClick={() => void saveDraftToProvider()} style={secondaryButtonStyle}>
                        {providerDraftActionLabel(thread)}
                      </button>
                    ) : null}
                    {localDraftStatePresent || providerDraftStatePresent ? (
                      <div style={{ display: 'grid', gap: '8px' }}>
                        <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                          These actions only change app-side draft state and Gmail draft linkage metadata. They do not send email or delete the Gmail draft itself.
                        </p>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                          {localDraftStatePresent ? (
                            <button type="button" onClick={() => void runDraftLifecycle('clear_local_draft')} style={secondaryButtonStyle}>
                              {clearLocalDraftActionLabel(thread)}
                            </button>
                          ) : null}
                          {providerDraftStatePresent ? (
                            <button type="button" onClick={() => void runDraftLifecycle('unlink_provider_draft')} style={secondaryButtonStyle}>
                              Unlink Gmail draft
                            </button>
                          ) : null}
                          {localDraftStatePresent && providerDraftStatePresent ? (
                            <button type="button" onClick={() => void runDraftLifecycle('clear_all_draft_state')} style={dangerButtonStyle}>
                              Clear local + Gmail link
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </Panel>

                <Panel>
                  <p style={sectionEyebrowStyle}>Escalation</p>
                  <div style={{ display: 'grid', gap: '10px' }}>
                    <p style={{ color: '#cbd5e1', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                      Escalate when the thread needs a human decision, pricing judgment, compliance answer, or executive response path.
                    </p>
                    <button type="button" onClick={() => void escalateThread()} style={dangerButtonStyle}>
                      Escalate to human review
                    </button>
                    {thread.pm_card_id ? <p style={{ color: '#86efac', fontSize: '12px', margin: 0 }}>Linked PM card: {thread.pm_card_id}</p> : null}
                  </div>
                </Panel>

                <Panel>
                  <p style={sectionEyebrowStyle}>Routing Reasons</p>
                  <div style={{ display: 'grid', gap: '8px' }}>
                    {thread.routing_reasons.map((reason) => (
                      <div key={reason} style={{ borderRadius: '12px', backgroundColor: '#08101f', padding: '10px', color: '#cbd5e1', fontSize: '12px' }}>
                        {reason}
                      </div>
                    ))}
                  </div>
                </Panel>
              </div>
            </div>
          </>
        ) : (
          <Panel>
            <p style={{ color: '#94a3b8', margin: 0 }}>Thread not found.</p>
          </Panel>
        )}
      </section>
    </RuntimePage>
  );
}

function defaultDraftType(thread: EmailThread): EmailDraftType {
  if (thread.workspace_key === 'agc') {
    return thread.lane === 'registrations_compliance' ? 'acknowledge' : 'qualify';
  }
  if (thread.workspace_key === 'fusion-os') {
    return 'schedule';
  }
  return 'acknowledge';
}

function defaultDraftEngine(thread: EmailThread): EmailDraftEngine {
  return contentGenerationAvailability(thread).eligible ? 'codex_job' : 'template';
}

function existingOperatorNotes(thread: EmailThread): string {
  const packet = readAuditPacket(thread);
  const value = packet?.operator_notes;
  return typeof value === 'string' ? value : '';
}

function draftStatusMessage(thread: EmailThread, draftType: EmailDraftType) {
  const audit = readDraftAudit(thread);
  if (audit.selectedPath === 'codex_job_pending') {
    return 'Codex draft job queued.';
  }
  if (audit.selectedPath === 'codex_job') {
    return `Codex draft generated: ${draftType}.`;
  }
  if (audit.selectedPath === 'codex_job_failed') {
    return `Codex draft failed: ${describeGenerationReason(audit.generationReason)}.`;
  }
  if (audit.selectedPath === 'content_generation') {
    return `Grounded AI draft generated: ${draftType}.`;
  }
  if (audit.selectedPath === 'template_fallback') {
    return `Template draft stored after AI fallback: ${describeGenerationReason(audit.generationReason)}.`;
  }
  return `Template draft generated: ${draftType}.`;
}

function contentGenerationAvailability(thread: EmailThread) {
  if (!['feezie-os', 'fusion-os'].includes(thread.workspace_key)) {
    return { eligible: false, reason: 'workspace_not_enabled' };
  }
  if (thread.lane !== 'primary') {
    return { eligible: false, reason: 'lane_not_enabled' };
  }
  if (thread.needs_human) {
    return { eligible: false, reason: 'thread_requires_human_review' };
  }
  if (thread.high_value) {
    return { eligible: false, reason: 'thread_marked_high_value' };
  }
  if (thread.high_risk) {
    return { eligible: false, reason: 'thread_marked_high_risk' };
  }
  return { eligible: true, reason: 'eligible' };
}

function readDraftAudit(thread: EmailThread) {
  const audit = thread.draft_audit;
  const selectedPath = typeof audit?.selected_path === 'string' ? audit.selected_path : null;
  const generationReason = typeof audit?.generation_reason === 'string' ? audit.generation_reason : null;
  const diagnostics = audit?.generation_diagnostics;
  const diagnosticsRecord = diagnostics && typeof diagnostics === 'object' ? diagnostics as Record<string, unknown> : null;
  const generationError = typeof diagnosticsRecord?.error === 'string' ? diagnosticsRecord.error : null;
  return {
    selectedPath,
    generationReason,
    generationError,
  };
}

function readAuditPacket(thread: EmailThread) {
  const audit = thread.draft_audit;
  if (!audit || typeof audit !== 'object') {
    return null;
  }
  const packet = audit.packet;
  return packet && typeof packet === 'object' ? packet as Record<string, unknown> : null;
}

function describeGenerationReason(reason: string | null) {
  switch (reason) {
    case 'eligible':
      return 'the thread met the grounded AI eligibility rules';
    case 'draft_engine_not_requested':
      return 'template drafting was requested';
    case 'workspace_not_enabled':
      return 'this workspace is not yet enabled for grounded AI drafting';
    case 'lane_not_enabled':
      return 'this lane is not yet enabled for grounded AI drafting';
    case 'thread_requires_human_review':
      return 'the thread is already marked for human review';
    case 'thread_marked_high_value':
      return 'the thread is marked high value';
    case 'thread_marked_high_risk':
      return 'the thread is marked high risk';
    case 'content_generation_returned_no_usable_body':
      return 'the generator did not return a usable email body';
    case 'codex_job_failed':
      return 'the Codex runner failed before producing a draft';
    case 'codex_job_canceled':
      return 'the Codex runner job was canceled';
    default:
      if (reason?.startsWith('codex_job_queue_error:')) {
        return `queueing the Codex runner raised ${reason.replace('codex_job_queue_error:', '')}`;
      }
      return reason?.startsWith('content_generation_error:')
        ? `the generator raised ${reason.replace('content_generation_error:', '')}`
        : reason || 'no bridge note recorded';
  }
}

function providerDraftStateLabel(thread: EmailThread) {
  if (thread.provider_draft_status === 'saved') {
    const timestamp = thread.provider_draft_saved_at ? ` on ${formatUiTimestamp(thread.provider_draft_saved_at)}` : '';
    return `saved to Gmail${timestamp}`;
  }
  if (thread.provider_draft_status === 'error') {
    return thread.provider_draft_error || 'save failed';
  }
  return 'not yet saved to Gmail';
}

function providerDraftActionLabel(thread: EmailThread | null) {
  if (!thread) {
    return 'Save to Gmail Drafts';
  }
  return thread.provider_draft_id ? 'Update Gmail draft' : 'Save to Gmail Drafts';
}

function hasLocalDraftState(thread: EmailThread) {
  const audit = readDraftAudit(thread);
  return Boolean(
    thread.draft_body ||
    thread.draft_job_id ||
    thread.draft_subject ||
    thread.draft_type ||
    thread.draft_generated_at ||
    audit.selectedPath,
  );
}

function hasProviderDraftState(thread: EmailThread) {
  return Boolean(
    thread.provider_draft_id ||
    thread.provider_draft_status ||
    thread.provider_draft_saved_at ||
    thread.provider_draft_error,
  );
}

function clearLocalDraftActionLabel(thread: EmailThread | null) {
  if (thread?.draft_job_id && !thread.draft_body) {
    return 'Cancel queued draft';
  }
  return 'Clear local draft';
}

function draftLifecycleStatusMessage(action: EmailThreadDraftLifecycleAction, thread: EmailThread | null) {
  switch (action) {
    case 'clear_local_draft':
      return thread?.draft_job_id && !thread.draft_body ? 'Canceling queued draft...' : 'Clearing local draft...';
    case 'unlink_provider_draft':
      return 'Clearing Gmail draft link...';
    case 'clear_all_draft_state':
      return 'Clearing local draft and Gmail draft link...';
    default:
      return 'Updating draft lifecycle...';
  }
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <section style={{ borderRadius: '18px', border: '1px solid rgba(148,163,184,0.16)', backgroundColor: '#071121', padding: '14px' }}>
      {children}
    </section>
  );
}

function Notice({ tone, message }: { tone: string; message: string }) {
  return (
    <div style={{ borderRadius: '14px', border: `1px solid ${tone}33`, backgroundColor: `${tone}10`, padding: '12px 14px', color: tone, fontSize: '13px' }}>
      {message}
    </div>
  );
}

function pill(label: string, tone: string) {
  return (
    <span
      style={{
        borderRadius: '999px',
        border: `1px solid ${tone}44`,
        backgroundColor: `${tone}18`,
        color: tone,
        fontSize: '11px',
        fontWeight: 700,
        padding: '5px 8px',
      }}
    >
      {label}
    </span>
  );
}

const sectionEyebrowStyle = {
  color: '#93c5fd',
  fontSize: '11px',
  letterSpacing: '0.16em',
  textTransform: 'uppercase' as const,
  margin: '0 0 12px',
};

const fieldLabelStyle = {
  display: 'grid',
  gap: '6px',
  color: '#cbd5e1',
  fontSize: '13px',
};

const selectStyle = {
  borderRadius: '10px',
  border: '1px solid rgba(148,163,184,0.22)',
  backgroundColor: '#08101f',
  color: 'white',
  padding: '10px 12px',
};

const textareaStyle = {
  borderRadius: '10px',
  border: '1px solid rgba(148,163,184,0.22)',
  backgroundColor: '#08101f',
  color: 'white',
  padding: '10px 12px',
  resize: 'vertical' as const,
  font: 'inherit',
};

const primaryButtonStyle = {
  borderRadius: '999px',
  border: '1px solid rgba(96,165,250,0.28)',
  backgroundColor: 'rgba(96,165,250,0.12)',
  color: '#dbeafe',
  padding: '10px 14px',
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
};

const secondaryButtonStyle = {
  borderRadius: '999px',
  border: '1px solid rgba(34,197,94,0.28)',
  backgroundColor: 'rgba(34,197,94,0.12)',
  color: '#dcfce7',
  padding: '10px 14px',
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
};

const dangerButtonStyle = {
  borderRadius: '999px',
  border: '1px solid rgba(248,113,113,0.3)',
  backgroundColor: 'rgba(248,113,113,0.12)',
  color: '#fecaca',
  padding: '10px 14px',
  fontSize: '13px',
  fontWeight: 700,
  cursor: 'pointer',
};
