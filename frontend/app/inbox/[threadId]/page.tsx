'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { apiGet, apiPost } from '@/lib/api-client';
import type { EmailDraftType, EmailThread, EmailThreadDraftResponse, EmailThreadEscalateResponse } from '@/lib/email-types';
import { formatUiTimestamp } from '@/lib/ui-dates';

const EMAIL_THREAD_LOAD_TIMEOUT_MS = 45_000;
const EMAIL_THREAD_ROUTE_TIMEOUT_MS = 30_000;
const EMAIL_THREAD_DRAFT_TIMEOUT_MS = 45_000;
const EMAIL_THREAD_ESCALATE_TIMEOUT_MS = 30_000;

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

  async function generateDraft() {
    try {
      setStatus('Generating draft...');
      const result = await apiPost<EmailThreadDraftResponse>(`/api/email/threads/${threadId}/draft`, {
        draft_type: draftType,
      }, {
        timeoutMs: EMAIL_THREAD_DRAFT_TIMEOUT_MS,
      });
      setThread(result.thread);
      setStatus(`Draft generated: ${result.draft_type}.`);
    } catch (issue) {
      setStatus(issue instanceof Error ? issue.message : 'Unable to generate draft right now.');
    }
  }

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
                    <button type="button" onClick={() => void generateDraft()} style={primaryButtonStyle}>
                      Generate draft
                    </button>
                    {thread.draft_body ? (
                      <div style={{ borderRadius: '12px', border: '1px solid rgba(96,165,250,0.18)', backgroundColor: 'rgba(96,165,250,0.06)', padding: '12px' }}>
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
