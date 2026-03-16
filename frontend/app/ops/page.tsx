'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import NavHeader from '@/components/NavHeader';
import { getApiUrl } from '@/lib/api-client';

const API_URL = getApiUrl();

type ComplianceMetrics = {
  approvals_last_24h: number;
  prospects_with_email: number;
  total_system_events?: number;
};

type SystemLog = {
  id?: string;
  component?: string;
  level?: string;
  message?: string;
  timestamp?: string;
};

type HealthPayload = {
  status?: string;
  service?: string;
  version?: string;
  firestore?: string;
};

type Automation = {
  id: string;
  name: string;
  schedule: string;
  cron: string;
  status: string;
  channel: string;
  last_run_at?: string;
  next_run_at?: string;
};

type Panel = 'mission' | 'org';

type OrgNode = {
  id: string;
  name: string;
  role: string;
  description: string;
  status: 'active' | 'planned';
  highlight: 'core' | 'ops' | 'brain' | 'lab';
  responsibilities?: string[];
};

type OpenBrainTelemetry = {
  database_connected: boolean;
  captures: {
    total: number;
    last_24h: number;
    last_7d: number;
  };
  vectors: {
    total: number;
    with_expiry: number;
    overdue: number;
    last_refresh_at?: string | null;
  };
  recent_captures: RecentCapture[];
};

type RecentCapture = {
  id: string;
  source?: string;
  topics?: string[];
  importance?: number;
  markdown_path?: string | null;
  created_at?: string | null;
  chunk_count: number;
};

type TelemetryErrors = {
  metrics: string | null;
  logs: string | null;
  health: string | null;
  automations: string | null;
  brain: string | null;
};

type LogsResponse = { logs?: SystemLog[] } | SystemLog[];
type AutomationsResponse = { data?: Automation[] } | { automations?: Automation[] } | Automation[] | null | undefined;

const TELEMETRY_LABELS: Record<keyof TelemetryErrors, string> = {
  metrics: 'Compliance metrics',
  logs: 'System logs',
  health: 'Service health',
  automations: 'Automations suite',
  brain: 'Open Brain telemetry',
};

const orgLayers: OrgNode[][] = [
  [
    {
      id: 'feeze',
      name: 'Feeze',
      role: 'Principal Operator',
      description: 'Approves prod deploys, data use, and spend.',
      status: 'active',
      highlight: 'core',
      responsibilities: ['Final approvals', 'Risk posture + ethics'],
    },
  ],
  [
    {
      id: 'neo',
      name: 'Neo',
      role: 'Core Agent — strategy + systems',
      description: 'Routes work across Ops, Brain, and Lab while enforcing guardrails.',
      status: 'active',
      highlight: 'ops',
      responsibilities: ['Mission Control', 'Process orchestration'],
    },
  ],
  [
    {
      id: 'ops-agent',
      name: 'Ops Agent',
      role: 'Watchdogs + collectors',
      description: 'Discord/Railway monitors and compliance posting.',
      status: 'planned',
      highlight: 'ops',
      responsibilities: ['Compliance dashboard', 'Railway watchdog', 'Gmail/Calendar commands'],
    },
    {
      id: 'brain-agent',
      name: 'Brain Agent',
      role: 'Knowledge + briefs',
      description: 'Daily briefs, System Docs, Automations mirror.',
      status: 'planned',
      highlight: 'brain',
      responsibilities: ['Daily brief cron', 'System Docs tab', 'Automations sync'],
    },
    {
      id: 'lab-agent',
      name: 'Lab Agent',
      role: 'Staging + self-improvement',
      description: 'Runs port 8900 staging builds and nightly self-improvements.',
      status: 'planned',
      highlight: 'lab',
      responsibilities: ['Nightly self-improvement', 'Lab build logs', 'Staging QA'],
    },
  ],
  [
    {
      id: 'collectors',
      name: 'Collectors',
      role: 'Discord cron relays',
      description: 'Hourly compliance posts + 5-min health checks.',
      status: 'planned',
      highlight: 'ops',
      responsibilities: ['Hourly compliance poster', '5-min health DM'],
    },
    {
      id: 'cron-suite',
      name: 'Cron Suite',
      role: 'Isolated automations',
      description: 'Backups, self-improvement, daily brief, docs.',
      status: 'active',
      highlight: 'brain',
      responsibilities: ['Backup @ 02:00', 'Daily brief @ 07:30', 'Docs @ 00:00'],
    },
    {
      id: 'future-agents',
      name: 'Project Agents',
      role: 'Per-initiative clones',
      description: 'Future per-project agents with their own sub-agents.',
      status: 'planned',
      highlight: 'lab',
      responsibilities: ['Prospect ingestion', 'Campaign pilots'],
    },
  ],
];

export default function OpsPage() {
  const [metrics, setMetrics] = useState<ComplianceMetrics | null>(null);
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [brainMetrics, setBrainMetrics] = useState<OpenBrainTelemetry | null>(null);
  const [loading, setLoading] = useState(true);
  const [activePanel, setActivePanel] = useState<Panel>('mission');
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [sectionErrors, setSectionErrors] = useState<TelemetryErrors>({
    metrics: null,
    logs: null,
    health: null,
    automations: null,
    brain: null,
  });

  const updateSectionError = useCallback((key: keyof TelemetryErrors, message: string | null) => {
    setSectionErrors((prev) => ({ ...prev, [key]: message }));
  }, []);


  const loadTelemetry = useCallback(async () => {
    if (!API_URL) {
      setGlobalError('NEXT_PUBLIC_API_URL is not configured');
      setLoading(false);
      return;
    }

    setIsRefreshing(true);
    setGlobalError(null);

    try {
      const [metricsResp, logsResp, healthResp, automationsResp, brainResp] = await Promise.allSettled([
        fetchJson<ComplianceMetrics>(`${API_URL}/api/analytics/compliance`),
        fetchJson<LogsResponse>(`${API_URL}/api/system/logs?limit=50`),
        fetchJson<HealthPayload>(`${API_URL}/health`),
        fetchJson<AutomationsResponse>(`${API_URL}/api/automations/`),
        fetchJson<OpenBrainTelemetry>(`${API_URL}/api/analytics/open-brain`),
      ]);

      if (metricsResp.status === 'fulfilled') {
        setMetrics(metricsResp.value ?? null);
        updateSectionError('metrics', null);
      } else {
        updateSectionError('metrics', toErrorMessage(metricsResp.reason));
      }

      if (logsResp.status === 'fulfilled') {
        setLogs(normalizeLogs(logsResp.value));
        updateSectionError('logs', null);
      } else {
        updateSectionError('logs', toErrorMessage(logsResp.reason));
      }

      if (healthResp.status === 'fulfilled') {
        setHealth(healthResp.value ?? null);
        updateSectionError('health', null);
      } else {
        updateSectionError('health', toErrorMessage(healthResp.reason));
      }

      if (automationsResp.status === 'fulfilled') {
        setAutomations(normalizeAutomations(automationsResp.value));
        updateSectionError('automations', null);
      } else {
        updateSectionError('automations', toErrorMessage(automationsResp.reason));
      }

      if (brainResp.status === 'fulfilled') {
        setBrainMetrics(brainResp.value ?? null);
        updateSectionError('brain', null);
      } else {
        updateSectionError('brain', toErrorMessage(brainResp.reason));
      }

      setCheckedAt(new Date());
    } catch (err) {
      setGlobalError(toErrorMessage(err));
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [updateSectionError]);

  useEffect(() => {
    loadTelemetry();
    const DAY_MS = 86_400_000;
    const interval = setInterval(loadTelemetry, DAY_MS);
    return () => clearInterval(interval);
  }, [loadTelemetry]);

  const sectionErrorSummary = useMemo(() => {
    const failing = Object.entries(sectionErrors).filter(([, value]) => value) as [keyof TelemetryErrors, string | null][];
    if (!failing.length) return null;
    const labels = failing.map(([key]) => TELEMETRY_LABELS[key]);
    return `Partial telemetry outage: ${labels.join(', ')}`;
  }, [sectionErrors]);

  const modelRows = useMemo(() => {
    if (!health) return [];
    return [
      {
        name: health.service ?? 'aiclone-backend',
        status: health.status ?? 'unknown',
        version: health.version ?? '—',
        datastore: health.firestore ?? '—',
      },
    ];
  }, [health]);

  const sessionRows = useMemo(() => {
    const map = new Map<string, { component: string; lastMessage: string; lastTimestamp?: Date }>();
    logs.forEach((log) => {
      if (!log.component) return;
      const ts = log.timestamp ? new Date(log.timestamp) : undefined;
      const existing = map.get(log.component);
      if (!existing || (ts && existing.lastTimestamp && ts > existing.lastTimestamp) || (!existing?.lastTimestamp && ts)) {
        map.set(log.component, {
          component: log.component,
          lastMessage: log.message ?? '',
          lastTimestamp: ts,
        });
      }
    });
    return Array.from(map.values()).sort((a, b) => {
      const aTime = a.lastTimestamp?.getTime() ?? 0;
      const bTime = b.lastTimestamp?.getTime() ?? 0;
      return bTime - aTime;
    });
  }, [logs]);

  const cronRows = useMemo(() => automations, [automations]);

  return (
    <main style={{ minHeight: '100vh', background: 'radial-gradient(circle at top, rgba(36,42,71,0.7), #010617 45%)', position: 'relative', paddingBottom: '120px' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        <header style={{ marginBottom: '16px' }}>
          <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '12px', textTransform: 'uppercase' }}>Ops</p>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
            <div>
              <h1 style={{ fontSize: '36px', fontWeight: 700, color: 'white', marginBottom: '4px' }}>Mission Control</h1>
              <p style={{ color: '#94a3b8' }}>Live telemetry for services, sessions, and cron jobs. No mock data—everything here is reading straight from prod.</p>
            </div>
            <div style={{ textAlign: 'right', color: '#94a3b8', fontSize: '13px', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
              <p>Last check: {checkedAt ? checkedAt.toLocaleTimeString() : loading ? 'Checking…' : '—'}</p>
              <p>Auto refresh: daily · Manual trigger below</p>
              <button
                onClick={loadTelemetry}
                disabled={isRefreshing}
                style={{
                  padding: '8px 18px',
                  borderRadius: '999px',
                  border: '1px solid #1f2937',
                  backgroundColor: isRefreshing ? '#0f172a' : '#fbbf24',
                  color: isRefreshing ? '#94a3b8' : '#0f172a',
                  fontWeight: 600,
                  cursor: isRefreshing ? 'not-allowed' : 'pointer',
                }}
              >
                {isRefreshing ? 'Refreshing…' : 'Manual refresh'}
              </button>
            </div>
          </div>
        </header>

        {globalError && <SectionAlert message={globalError} />}
        {!globalError && sectionErrorSummary && <SectionAlert message={sectionErrorSummary} />}

        <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
          <TabButton active={activePanel === 'mission'} onClick={() => setActivePanel('mission')} label="Mission Control" description="System overview & cron suite" />
          <TabButton active={activePanel === 'org'} onClick={() => setActivePanel('org')} label="Org Chart" description="Feeze → Neo → module agents" />
        </div>

        {activePanel === 'mission' ? (
          <MissionControlView
            loading={loading}
            metrics={metrics}
            metricsError={sectionErrors.metrics}
            models={modelRows}
            modelsError={sectionErrors.health}
            sessions={sessionRows}
            sessionsError={sectionErrors.logs}
            cronJobs={cronRows}
            cronError={sectionErrors.automations}
            brainMetrics={brainMetrics}
            brainError={sectionErrors.brain}
          />
        ) : (
          <OrgChartSection layers={orgLayers} />
        )}
      </div>
      <ModuleDock />
    </main>
  );
}

function MissionControlView({
  loading,
  metrics,
  metricsError,
  models,
  modelsError,
  sessions,
  sessionsError,
  cronJobs,
  cronError,
  brainMetrics,
  brainError,
}: {
  loading: boolean;
  metrics: ComplianceMetrics | null;
  metricsError: string | null;
  models: { name: string; status: string; version: string; datastore: string }[];
  modelsError: string | null;
  sessions: { component: string; lastMessage: string; lastTimestamp?: Date }[];
  sessionsError: string | null;
  cronJobs: Automation[];
  cronError: string | null;
  brainMetrics: OpenBrainTelemetry | null;
  brainError: string | null;
}) {
  if (loading) {
    return <p style={{ color: '#94a3b8' }}>Refreshing telemetry…</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <HeroCard metrics={metrics} sessions={sessions.length} cronCount={cronJobs.length} />
      {metricsError && <SectionAlert message={`${TELEMETRY_LABELS.metrics}: ${metricsError}`} />}
      <StatusTable
        title="Models"
        subtitle="Backend surfaces + data stores"
        headers={['Name', 'Status', 'Version', 'Datastore']}
        rows={models.map((model) => [model.name, statusBadge(model.status), model.version, model.datastore])}
      />
      {modelsError && <SectionAlert message={`${TELEMETRY_LABELS.health}: ${modelsError}`} />}
      <OpenBrainPanel metrics={brainMetrics} />
      {brainError && <SectionAlert message={`${TELEMETRY_LABELS.brain}: ${brainError}`} />}
      <StatusTable
        title="Active Streams"
        subtitle="Latest events per component"
        headers={['Component', 'Last Event', 'Last Seen']}
        rows={sessions.map((session) => [session.component, session.lastMessage || '—', session.lastTimestamp ? formatTimestamp(session.lastTimestamp) : '—'])}
      />
      {sessionsError && <SectionAlert message={`${TELEMETRY_LABELS.logs}: ${sessionsError}`} />}
      <CronTable cronJobs={cronJobs} />
      {cronError && <SectionAlert message={`${TELEMETRY_LABELS.automations}: ${cronError}`} />}
    </div>
  );
}

function HeroCard({ metrics, sessions, cronCount }: { metrics: ComplianceMetrics | null; sessions: number; cronCount: number }) {
  const cards = [
    { label: 'Approvals', value: metrics?.approvals_last_24h ?? 0, detail: 'Last 24h', tone: '#fbbf24' },
    { label: 'Prospects ready', value: metrics?.prospects_with_email ?? 0, detail: 'Email staged', tone: '#38bdf8' },
    { label: 'Log streams', value: sessions, detail: 'Active emitters', tone: '#34d399' },
    { label: 'Cron runs', value: cronCount, detail: 'Isolated jobs', tone: '#f472b6' },
  ];
  return (
    <section
      style={{
        borderRadius: '20px',
        padding: '24px',
        background: 'linear-gradient(135deg, rgba(15,23,42,0.9), rgba(8,12,24,0.95))',
        border: '1px solid rgba(248,250,252,0.05)',
        boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Ops Dashboard</p>
          <h2 style={{ color: 'white', fontSize: '32px', margin: '4px 0' }}>Mission Control</h2>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Realtime guardrails and automations for the production agent.</p>
        </div>
        <div style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'right' }}>
          <p>Isolated sessions only</p>
          <p>Mirrored to Brain → Automations</p>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px' }}>
        {cards.map((card) => (
          <div key={card.label} style={{ padding: '14px', borderRadius: '16px', backgroundColor: '#020617', border: '1px solid #111827' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{card.label}</p>
            <p style={{ color: card.tone, fontSize: '28px', fontWeight: 600 }}>{card.value}</p>
            <p style={{ color: '#475569', fontSize: '12px' }}>{card.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function OpenBrainPanel({ metrics }: { metrics: OpenBrainTelemetry | null }) {
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#0f172a', padding: '20px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Open Brain</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>Capture + refresh telemetry mirrored to Brain.</p>
        </div>
        <p style={{ color: metrics?.database_connected ? '#22c55e' : '#f87171', fontSize: '12px' }}>
          {metrics?.database_connected ? 'Vector store connected' : 'Vector store offline'}
        </p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <MiniStat label="Captures" value={metrics?.captures.total ?? 0} tone="#38bdf8" detail="All time" />
        <MiniStat label="New (24h)" value={metrics?.captures.last_24h ?? 0} tone="#34d399" detail="Working memory" />
        <MiniStat label="Chunks" value={metrics?.vectors.total ?? 0} tone="#f97316" detail="Vector rows" />
        <MiniStat label="Expiring" value={metrics?.vectors.with_expiry ?? 0} tone="#fbbf24" detail="Short-term" />
        <MiniStat label="Overdue" value={metrics?.vectors.overdue ?? 0} tone="#f87171" detail="Needs cleanup" />
        <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
          <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Last refresh</p>
          <p style={{ color: '#cbd5f5', fontSize: '18px', fontWeight: 600 }}>
            {metrics?.vectors.last_refresh_at ? formatTimestamp(new Date(metrics.vectors.last_refresh_at)) : '—'}
          </p>
          <p style={{ color: '#475569', fontSize: '12px' }}>memory_vectors.last_refreshed_at</p>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Source', 'Topics', 'Importance', 'Chunks', 'Created'].map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!metrics || metrics.recent_captures.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '12px 0', color: '#475569' }}>No captures recorded yet.</td>
              </tr>
            ) : (
              metrics.recent_captures.map((item) => (
                <tr key={item.id}>
                  <td style={{ padding: '10px 0', color: '#e2e8f0', fontWeight: 600 }}>{item.source ?? '—'}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{(item.topics ?? []).join(', ') || '—'}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{item.importance ?? '—'}</td>
                  <td style={{ padding: '10px 0', color: '#e2e8f0' }}>{item.chunk_count}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{item.created_at ? formatTimestamp(new Date(item.created_at)) : '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MiniStat({ label, value, detail, tone }: { label: string; value: number; detail: string; tone: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: tone, fontSize: '22px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
  );
}

function SectionAlert({ message }: { message: string }) {
  return (
    <div style={{
      marginTop: '16px',
      padding: '12px 16px',
      borderRadius: '12px',
      border: '1px solid rgba(248,113,113,0.3)',
      backgroundColor: 'rgba(69,10,10,0.6)',
      color: '#fecaca',
      fontSize: '14px',
    }}>
      {message}
    </div>
  );
}

function StatusTable({
  title,
  subtitle,
  headers,
  rows,
}: {
  title: string;
  subtitle: string;
  headers: string[];
  rows: (string | JSX.Element)[][];
}) {
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#0f172a', padding: '20px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#94a3b8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>{title}</p>
        <p style={{ color: '#64748b', fontSize: '13px' }}>{subtitle}</p>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {headers.map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length} style={{ padding: '12px 0', color: '#475569' }}>
                  Nothing to show yet.
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr key={idx}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} style={{ padding: '10px 0', color: '#e2e8f0', fontSize: '14px', borderBottom: '1px solid #0f172a' }}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CronTable({ cronJobs }: { cronJobs: Automation[] }) {
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#0f172a', padding: '20px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#94a3b8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Cron Jobs</p>
        <p style={{ color: '#64748b', fontSize: '13px' }}>Isolated sessions mirrored into Brain → Automations</p>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Name', 'Schedule', 'Status', 'Channel', 'Last Run', 'Next Run'].map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cronJobs.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '12px 0', color: '#475569' }}>No cron jobs configured.</td>
              </tr>
            ) : (
              cronJobs.map((job) => (
                <tr key={job.id}>
                  <td style={{ padding: '10px 0', color: '#e2e8f0', fontWeight: 600 }}>{job.name}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span>{job.schedule}</span>
                      <span style={{ fontSize: '12px', color: '#475569' }}>{job.cron}</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 0' }}>{statusBadge(job.status)}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{job.channel}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.last_run_at ? formatTimestamp(new Date(job.last_run_at)) : '—'}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.next_run_at ? formatTimestamp(new Date(job.next_run_at)) : '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TabButton({ active, onClick, label, description }: { active: boolean; onClick: () => void; label: string; description: string }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        textAlign: 'left',
        borderRadius: '16px',
        padding: '16px',
        border: active ? '1px solid #fbbf24' : '1px solid #1f2937',
        background: active ? 'linear-gradient(120deg, rgba(251,191,36,0.18), rgba(15,23,42,0.95))' : '#050b19',
        color: 'white',
        cursor: 'pointer',
      }}
    >
      <p style={{ fontSize: '16px', fontWeight: 600 }}>{label}</p>
      <p style={{ fontSize: '13px', color: '#94a3b8' }}>{description}</p>
    </button>
  );
}

function ModuleDock() {
  const buttons = [
    { label: 'Ops', tone: '#fbbf24', active: true },
    { label: 'Brain', tone: '#38bdf8', active: false },
    { label: 'Lab', tone: '#34d399', active: false },
  ];

  return (
    <div style={{ position: 'fixed', bottom: '32px', left: 0, right: 0, display: 'flex', justifyContent: 'center', pointerEvents: 'none' }}>
      <div style={{ display: 'flex', gap: '12px', padding: '10px 16px', background: 'rgba(2,6,23,0.85)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: '999px', boxShadow: '0 20px 50px rgba(0,0,0,0.45)', pointerEvents: 'auto' }}>
        {buttons.map((btn) => (
          <span
            key={btn.label}
            style={{
              padding: '10px 18px',
              borderRadius: '999px',
              backgroundColor: btn.active ? `${btn.tone}22` : 'transparent',
              border: btn.active ? `1px solid ${btn.tone}` : '1px solid transparent',
              color: btn.active ? 'white' : '#94a3b8',
              fontWeight: 600,
              fontSize: '13px',
            }}
          >
            {btn.label}
          </span>
        ))}
      </div>
    </div>
  );
}

const highlightColors: Record<OrgNode['highlight'], string> = {
  core: '#f97316',
  ops: '#fbbf24',
  brain: '#38bdf8',
  lab: '#34d399',
};

const statusLabels: Record<OrgNode['status'], string> = {
  active: 'Live',
  planned: 'Planned',
};

function OrgChartSection({ layers }: { layers: OrgNode[][] }) {
  return (
    <section
      style={{
        border: '1px solid #1f2937',
        borderRadius: '16px',
        padding: '24px',
        backgroundColor: '#0f172a',
      }}
    >
      <div style={{ marginBottom: '16px' }}>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '12px', textTransform: 'uppercase' }}>Org Design</p>
        <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'white', margin: '4px 0' }}>Ops → Org Chart</h2>
        <p style={{ color: '#94a3b8' }}>Feeze → Neo → module-specific agents. Future slots are marked “Planned” until we staff them.</p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {layers.map((layer, idx) => (
          <div
            key={`layer-${idx}`}
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '16px',
            }}
          >
            {layer.map((node) => (
              <OrgNodeCard key={node.id} node={node} />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function OrgNodeCard({ node }: { node: OrgNode }) {
  const tone = highlightColors[node.highlight] ?? '#38bdf8';
  return (
    <div
      style={{
        flex: '1 1 220px',
        borderRadius: '16px',
        border: '1px solid #1f2937',
        padding: '16px',
        background: 'linear-gradient(135deg, rgba(15,23,42,0.9), rgba(2,6,23,0.9))',
      }}
    >
      <p style={{ color: tone, letterSpacing: '0.2em', fontSize: '10px', textTransform: 'uppercase' }}>{node.role}</p>
      <h3 style={{ color: 'white', fontSize: '18px', fontWeight: 600, margin: '4px 0 8px' }}>{node.name}</h3>
      <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '8px' }}>{node.description}</p>
      {node.responsibilities && node.responsibilities.length > 0 && (
        <ul style={{ color: '#cbd5f5', fontSize: '13px', marginLeft: '16px', marginBottom: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {node.responsibilities.map((item) => (
            <li key={`${node.id}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          borderRadius: '999px',
          border: '1px solid #1f2937',
          padding: '6px 12px',
          color: node.status === 'active' ? '#22c55e' : '#fbbf24',
          fontSize: '12px',
          backgroundColor: '#0f172a',
        }}
      >
        <span style={{ width: '6px', height: '6px', borderRadius: '999px', backgroundColor: node.status === 'active' ? '#22c55e' : tone }} />
        {statusLabels[node.status]}
      </span>
    </div>
  );
}

function statusBadge(status?: string) {
  const normalized = status?.toLowerCase();
  const color =
    normalized === 'healthy' || normalized === 'active'
      ? '#22c55e'
      : normalized === 'warning'
      ? '#fbbf24'
      : normalized === 'error'
      ? '#f87171'
      : '#94a3b8';
  const background = `${color}33`;
  return (
    <span style={{ padding: '4px 12px', borderRadius: '999px', backgroundColor: background, color, fontSize: '12px', textTransform: 'capitalize' }}>
      {status ?? 'unknown'}
    </span>
  );
}

function formatTimestamp(value: Date) {
  return value.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

function normalizeLogs(payload: LogsResponse | undefined): SystemLog[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.logs)) return payload.logs;
  return [];
}

function normalizeAutomations(payload: AutomationsResponse): Automation[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (typeof payload === 'object' && payload !== null) {
    const maybeData = (payload as { data?: Automation[] }).data;
    if (Array.isArray(maybeData)) {
      return maybeData;
    }
    const maybeAutomations = (payload as { automations?: Automation[] }).automations;
    if (Array.isArray(maybeAutomations)) {
      return maybeAutomations;
    }
  }
  return [];
}

function toErrorMessage(err: unknown): string {
  if (err instanceof Error) {
    return err.message;
  }
  if (typeof err === 'string') {
    return err;
  }
  return 'Unknown error';
}
