'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { apiGet, apiPost } from '@/lib/api-client';
import type { EmailProviderStatusResponse, EmailSyncResponse, EmailThread, EmailThreadListResponse } from '@/lib/email-types';
import { formatUiNumber, formatUiTimestamp } from '@/lib/ui-dates';

const EMAIL_LIST_TIMEOUT_MS = 45_000;
const EMAIL_STATUS_TIMEOUT_MS = 20_000;
const EMAIL_SYNC_TIMEOUT_MS = 60_000;
const INBOX_CACHE_PREFIX = 'aiclone:inbox:threads:v2';

type WorkspaceFilter = 'all' | 'agc' | 'fusion-os' | 'feezie-os' | 'easyoutfitapp' | 'ai-swag-store' | 'shared_ops' | 'manual_review';

type InboxPayloadState = {
  payload: EmailThreadListResponse;
  workspaceFilter: WorkspaceFilter;
  humanOnly: boolean;
};

type InboxPageProps = {
  searchParams?: {
    workspace?: string | string[];
  };
};

const FILTERS: { key: WorkspaceFilter; label: string }[] = [
  { key: 'all', label: 'All Threads' },
  { key: 'agc', label: 'AGC' },
  { key: 'manual_review', label: 'Manual Review' },
  { key: 'shared_ops', label: 'Shared Ops' },
  { key: 'fusion-os', label: 'Fusion OS' },
  { key: 'feezie-os', label: 'FEEZIE' },
  { key: 'easyoutfitapp', label: 'Easy Outfit' },
  { key: 'ai-swag-store', label: 'Swag Store' },
];

const AGC_LANE_LABELS: Record<string, string> = {
  consulting_opportunity: 'Consulting',
  product_sourcing: 'Product Sourcing',
  supplier_partner: 'Supplier / Partner',
  registrations_compliance: 'Compliance',
  finance_admin: 'Finance / Admin',
  noise_archive: 'Noise',
};

function normalizeWorkspaceFilter(value: string | null): WorkspaceFilter | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return FILTERS.some((item) => item.key === normalized) ? (normalized as WorkspaceFilter) : null;
}

function firstSearchParam(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

export default function InboxPage({ searchParams }: InboxPageProps) {
  const initialWorkspaceFilter = normalizeWorkspaceFilter(firstSearchParam(searchParams?.workspace)) ?? 'all';
  const [payloadState, setPayloadState] = useState<InboxPayloadState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncState, setSyncState] = useState<string | null>(null);
  const [workspaceFilter, setWorkspaceFilter] = useState<WorkspaceFilter>(initialWorkspaceFilter);
  const [humanOnly, setHumanOnly] = useState(false);
  const [providerStatus, setProviderStatus] = useState<EmailProviderStatusResponse | null>(null);
  const activeLoadId = useRef(0);

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

  async function loadThreads(
    nextWorkspaceFilter: WorkspaceFilter = workspaceFilter,
    nextHumanOnly: boolean = humanOnly,
    showLoading = true,
  ) {
    const loadId = activeLoadId.current + 1;
    activeLoadId.current = loadId;
    try {
      if (showLoading) {
        setLoading(true);
      }
      setError(null);
      const params = new URLSearchParams();
      if (nextWorkspaceFilter !== 'all') {
        params.set('workspace_key', nextWorkspaceFilter);
      }
      if (nextHumanOnly) {
        params.set('needs_human', 'true');
      }
      const endpoint = `/api/email/threads${params.toString() ? `?${params.toString()}` : ''}`;
      const result = await apiGet<EmailThreadListResponse>(endpoint, { timeoutMs: EMAIL_LIST_TIMEOUT_MS });
      if (loadId !== activeLoadId.current) {
        return;
      }
      setPayloadState({ payload: result, workspaceFilter: nextWorkspaceFilter, humanOnly: nextHumanOnly });
      writeCachedInboxPayload(nextWorkspaceFilter, nextHumanOnly, result);
    } catch (issue) {
      if (loadId !== activeLoadId.current) {
        return;
      }
      const cachedPayload = readCachedInboxPayload(nextWorkspaceFilter, nextHumanOnly);
      if (cachedPayload) {
        setPayloadState({ payload: cachedPayload, workspaceFilter: nextWorkspaceFilter, humanOnly: nextHumanOnly });
      }
      setError(issue instanceof Error ? issue.message : 'Unable to load inbox state right now.');
    } finally {
      if (loadId === activeLoadId.current) {
        setLoading(false);
      }
    }
  }

  async function loadProviderStatus() {
    try {
      const result = await apiGet<EmailProviderStatusResponse>('/api/email/google/status', {
        timeoutMs: EMAIL_STATUS_TIMEOUT_MS,
      });
      setProviderStatus(result);
    } catch {
      setProviderStatus(null);
    }
  }

  useEffect(() => {
    void loadProviderStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const cachedPayload = readCachedInboxPayload(workspaceFilter, humanOnly);
    if (cachedPayload) {
      setPayloadState({ payload: cachedPayload, workspaceFilter, humanOnly });
      setLoading(false);
    }
    void loadThreads(workspaceFilter, humanOnly, !cachedPayload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceFilter, humanOnly]);

  async function handleSync() {
    try {
      setSyncState('Syncing inbox state...');
      const result = await apiPost<EmailSyncResponse>('/api/email/sync', undefined, {
        timeoutMs: EMAIL_SYNC_TIMEOUT_MS,
      });
      setSyncState(
        result.status === 'gmail_synced'
          ? 'Live Gmail inbox synced.'
          : result.status === 'gmail_auth_required'
            ? 'Gmail OAuth client is configured, but the account is not connected yet. Run the Gmail connection script.'
            : result.seeded_samples
              ? 'Sample inbox seeded. Gmail provider sync is still not connected.'
              : 'Inbox state refreshed.',
      );
      await loadThreads(workspaceFilter, humanOnly);
      await loadProviderStatus();
    } catch (issue) {
      setSyncState(issue instanceof Error ? issue.message : 'Unable to sync inbox state right now.');
    }
  }

  const payload = payloadState?.payload ?? null;
  const payloadMatchesActiveFilter = payloadState
    ? payloadState.workspaceFilter === workspaceFilter && payloadState.humanOnly === humanOnly
    : false;
  const visibleItems = payload?.items.filter((thread) => matchesInboxFilters(thread, workspaceFilter, humanOnly)) ?? [];
  const workspaceCounts = payload?.workspace_counts ?? {};
  const agcLaneCounts = payload?.agc_lane_counts ?? {};
  const metricCounts = payloadMatchesActiveFilter
    ? {
        total: payload?.total ?? 0,
        needsHuman: payload?.needs_human_count ?? 0,
        highValue: payload?.high_value_count ?? 0,
        highRisk: payload?.high_risk_count ?? 0,
      }
    : deriveMetricCounts(visibleItems);
  const title = workspaceFilter === 'agc' ? 'AGC inbox' : 'Portfolio email routing';
  const description =
    workspaceFilter === 'agc'
      ? 'AGC-only inbox view. This page shows threads that Gmail explicitly labeled workspace/agc.'
      : 'This is the Phase 1 inbox surface. It routes one portfolio mailbox into workspace buckets first, then into AGC lanes when the thread belongs in AGC.';

  return (
    <RuntimePage module="ops" tabs={tabs} maxWidth="1480px">
      <section style={{ display: 'grid', gap: '18px' }}>
        <header style={{ display: 'grid', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
            <div>
              <p style={{ color: '#60a5fa', letterSpacing: '0.18em', fontSize: '11px', textTransform: 'uppercase', margin: 0 }}>Shared Inbox</p>
              <h1 style={{ margin: '6px 0 0', color: 'white', fontSize: '28px' }}>{title}</h1>
            </div>
            <button
              type="button"
              onClick={() => void handleSync()}
              style={{
                borderRadius: '999px',
                border: '1px solid rgba(96,165,250,0.35)',
                backgroundColor: 'rgba(96,165,250,0.12)',
                color: '#dbeafe',
                padding: '10px 14px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Seed / Refresh
            </button>
          </div>
          <p style={{ color: '#94a3b8', fontSize: '14px', margin: 0, lineHeight: 1.6 }}>{description}</p>
          {workspaceFilter === 'agc' ? (
            <p style={{ color: '#c4b5fd', fontSize: '13px', margin: 0 }}>
              This route is pinned to the AGC workspace filter. Open <Link href="/inbox" style={{ color: '#93c5fd' }}>the shared inbox</Link> to see every workspace.
            </p>
          ) : null}
          {providerStatus ? (
            providerStatus.connected ? (
              <div style={{ borderRadius: '14px', border: '1px solid rgba(34,197,94,0.25)', backgroundColor: 'rgba(34,197,94,0.08)', padding: '12px 14px' }}>
                <p style={{ color: '#bbf7d0', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>
                  Gmail is connected for <strong>{providerStatus.account_email}</strong>. Sync will pull live inbox threads using query <code>{providerStatus.sync_query}</code>.
                </p>
              </div>
            ) : providerStatus.configured ? (
              <div style={{ borderRadius: '14px', border: '1px solid rgba(251,191,36,0.25)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '12px 14px' }}>
                <p style={{ color: '#fde68a', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>
                  Gmail OAuth client is configured for <strong>{providerStatus.account_email}</strong>, but the inbox is not authorized yet. Run <code>/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python /Users/neo/.openclaw/workspace/scripts/connect_gmail_inbox.py</code> on the host to finish connection.
                </p>
              </div>
            ) : (
              <div style={{ borderRadius: '14px', border: '1px solid rgba(248,113,113,0.25)', backgroundColor: 'rgba(248,113,113,0.08)', padding: '12px 14px' }}>
                <p style={{ color: '#fecaca', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>
                  Gmail OAuth client is not configured yet. Put the desktop OAuth client JSON at <code>{providerStatus.client_file}</code> for local use, or set <code>GOOGLE_GMAIL_OAUTH_CLIENT_JSON</code> in production.
                </p>
              </div>
            )
          ) : null}
          {payload?.data_mode === 'sample_only' ? (
            <div style={{ borderRadius: '14px', border: '1px solid rgba(251,191,36,0.25)', backgroundColor: 'rgba(251,191,36,0.08)', padding: '12px 14px' }}>
              <p style={{ color: '#fde68a', fontSize: '13px', margin: 0, lineHeight: 1.55 }}>
                Sample threads are loaded right now so you can test routing before Gmail OAuth and mailbox sync are connected.
              </p>
            </div>
          ) : null}
          {syncState ? <p style={{ color: '#cbd5e1', fontSize: '13px', margin: 0 }}>{syncState}</p> : null}
          {error ? <p style={{ color: '#fca5a5', fontSize: '13px', margin: 0 }}>{error}</p> : null}
        </header>

        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <MetricCard label="Threads" value={payload ? formatUiNumber(metricCounts.total) : '—'} detail="filtered queue" tone="#60a5fa" />
          <MetricCard label="Needs Human" value={payload ? formatUiNumber(metricCounts.needsHuman) : '—'} detail="manual review queue" tone="#fbbf24" />
          <MetricCard label="High Value" value={payload ? formatUiNumber(metricCounts.highValue) : '—'} detail="buyer or contract pressure" tone="#34d399" />
          <MetricCard label="High Risk" value={payload ? formatUiNumber(metricCounts.highRisk) : '—'} detail="claims / compliance / pricing" tone="#f87171" />
        </section>

        <section style={{ borderRadius: '18px', border: '1px solid rgba(148,163,184,0.16)', backgroundColor: '#071121', padding: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '12px' }}>
            <div>
              <p style={{ color: '#93c5fd', fontSize: '11px', letterSpacing: '0.16em', textTransform: 'uppercase', margin: 0 }}>Workspace Buckets</p>
              <p style={{ color: '#cbd5e1', fontSize: '13px', margin: '4px 0 0' }}>Use these counts to see where the shared inbox is routing traffic.</p>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#cbd5e1', fontSize: '13px' }}>
              <input type="checkbox" checked={humanOnly} onChange={(event) => setHumanOnly(event.target.checked)} />
              Needs human only
            </label>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px' }}>
            {FILTERS.filter((item) => item.key !== 'all').map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setWorkspaceFilter(item.key)}
                style={{
                  borderRadius: '14px',
                  border: workspaceFilter === item.key ? '1px solid rgba(96,165,250,0.55)' : '1px solid rgba(148,163,184,0.14)',
                  backgroundColor: workspaceFilter === item.key ? 'rgba(96,165,250,0.12)' : '#08101f',
                  padding: '12px',
                  textAlign: 'left',
                  cursor: 'pointer',
                }}
              >
                <p style={{ color: 'white', fontSize: '14px', fontWeight: 700, margin: 0 }}>{item.label}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: '6px 0 0' }}>{workspaceCounts[item.key] ?? 0} thread(s)</p>
              </button>
            ))}
            <button
              type="button"
              onClick={() => setWorkspaceFilter('all')}
              style={{
                borderRadius: '14px',
                border: workspaceFilter === 'all' ? '1px solid rgba(96,165,250,0.55)' : '1px solid rgba(148,163,184,0.14)',
                backgroundColor: workspaceFilter === 'all' ? 'rgba(96,165,250,0.12)' : '#08101f',
                padding: '12px',
                textAlign: 'left',
                cursor: 'pointer',
              }}
            >
              <p style={{ color: 'white', fontSize: '14px', fontWeight: 700, margin: 0 }}>All</p>
              <p style={{ color: '#94a3b8', fontSize: '12px', margin: '6px 0 0' }}>{Object.values(workspaceCounts).reduce((sum, count) => sum + count, 0)} total</p>
            </button>
          </div>
        </section>

        <section style={{ borderRadius: '18px', border: '1px solid rgba(167,139,250,0.18)', backgroundColor: '#071121', padding: '14px' }}>
          <div style={{ marginBottom: '12px' }}>
            <p style={{ color: '#c4b5fd', fontSize: '11px', letterSpacing: '0.16em', textTransform: 'uppercase', margin: 0 }}>AGC Lane Board</p>
            <p style={{ color: '#cbd5e1', fontSize: '13px', margin: '4px 0 0' }}>Second-pass routing inside AGC.</p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
            {Object.entries(AGC_LANE_LABELS).map(([key, label]) => (
              <div key={key} style={{ borderRadius: '14px', border: '1px solid rgba(167,139,250,0.14)', backgroundColor: '#08101f', padding: '12px' }}>
                <p style={{ color: 'white', fontSize: '14px', fontWeight: 700, margin: 0 }}>{label}</p>
                <p style={{ color: '#a78bfa', fontSize: '12px', margin: '6px 0 0' }}>{agcLaneCounts[key] ?? 0} thread(s)</p>
              </div>
            ))}
          </div>
        </section>

        <section style={{ display: 'grid', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'baseline' }}>
            <div>
              <p style={{ color: '#38bdf8', fontSize: '11px', letterSpacing: '0.16em', textTransform: 'uppercase', margin: 0 }}>Recent Queue</p>
              <p style={{ color: '#cbd5e1', fontSize: '13px', margin: '4px 0 0' }}>
                {payload?.last_synced_at ? `Updated ${formatUiTimestamp(payload.last_synced_at)}` : 'No sync timestamp yet.'}
              </p>
            </div>
          </div>
          {loading ? (
            <EmptyPanel message="Loading inbox threads…" />
          ) : payload && visibleItems.length > 0 ? (
            visibleItems.map((thread) => (
              <Link
                key={thread.id}
                href={`/inbox/${thread.id}`}
                style={{
                  display: 'block',
                  borderRadius: '16px',
                  border: '1px solid rgba(148,163,184,0.14)',
                  backgroundColor: '#08101f',
                  padding: '14px',
                  textDecoration: 'none',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
                  <div>
                    <p style={{ color: 'white', fontSize: '16px', fontWeight: 700, margin: 0 }}>{thread.subject}</p>
                    <p style={{ color: '#94a3b8', fontSize: '12px', margin: '6px 0 0' }}>
                      {thread.from_name || thread.organization || thread.from_address} · {formatUiTimestamp(thread.last_message_at)}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                    {pill(`workspace:${thread.workspace_key}`, '#38bdf8')}
                    {pill(`lane:${thread.lane}`, thread.workspace_key === 'agc' ? '#a78bfa' : '#94a3b8')}
                    {thread.needs_human ? pill('needs human', '#fbbf24') : null}
                    {thread.high_value ? pill('high value', '#34d399') : null}
                    {thread.high_risk ? pill('high risk', '#f87171') : null}
                  </div>
                </div>
                <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.55, margin: '0 0 10px' }}>{thread.excerpt || thread.summary || 'No excerpt yet.'}</p>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', color: '#94a3b8', fontSize: '12px' }}>
                  <span>Confidence {(thread.confidence_score * 100).toFixed(0)}%</span>
                  <span>{thread.last_route_source === 'manual' ? 'Manually routed' : 'Auto-routed'}</span>
                </div>
              </Link>
            ))
          ) : error && !payload ? (
            <EmptyPanel message="Inbox is unavailable right now, and no cached inbox threads are available." />
          ) : (
            <EmptyPanel message="No inbox threads are currently loaded." />
          )}
        </section>
      </section>
    </RuntimePage>
  );
}

function inboxCacheKey(workspaceFilter: WorkspaceFilter, humanOnly: boolean) {
  return `${INBOX_CACHE_PREFIX}:${workspaceFilter}:${humanOnly ? 'human' : 'all'}`;
}

function readCachedInboxPayload(workspaceFilter: WorkspaceFilter, humanOnly: boolean): EmailThreadListResponse | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(inboxCacheKey(workspaceFilter, humanOnly));
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as EmailThreadListResponse;
  } catch {
    return null;
  }
}

function writeCachedInboxPayload(workspaceFilter: WorkspaceFilter, humanOnly: boolean, payload: EmailThreadListResponse) {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(inboxCacheKey(workspaceFilter, humanOnly), JSON.stringify(payload));
  } catch {
    // Ignore storage failures; live state is still usable.
  }
}

function matchesInboxFilters(thread: EmailThread, workspaceFilter: WorkspaceFilter, humanOnly: boolean) {
  if (humanOnly && !thread.needs_human) {
    return false;
  }
  if (workspaceFilter === 'all') {
    return true;
  }
  if (workspaceFilter === 'manual_review') {
    return thread.workspace_key === 'shared_ops' && thread.lane === 'manual_review';
  }
  return thread.workspace_key === workspaceFilter;
}

function deriveMetricCounts(items: EmailThread[]) {
  return {
    total: items.length,
    needsHuman: items.filter((thread) => thread.needs_human).length,
    highValue: items.filter((thread) => thread.high_value).length,
    highRisk: items.filter((thread) => thread.high_risk).length,
  };
}

function MetricCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) {
  return (
    <div style={{ borderRadius: '16px', border: `1px solid ${tone}33`, backgroundColor: `${tone}12`, padding: '14px' }}>
      <p style={{ color: tone, fontSize: '11px', letterSpacing: '0.16em', textTransform: 'uppercase', margin: 0 }}>{label}</p>
      <p style={{ color: 'white', fontSize: '24px', fontWeight: 700, margin: '8px 0 4px' }}>{value}</p>
      <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{detail}</p>
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div style={{ borderRadius: '16px', border: '1px dashed rgba(148,163,184,0.22)', backgroundColor: '#08101f', padding: '24px' }}>
      <p style={{ color: '#94a3b8', fontSize: '13px', margin: 0 }}>{message}</p>
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
