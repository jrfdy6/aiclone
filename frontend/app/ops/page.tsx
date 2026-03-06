'use client';

import { useEffect, useMemo, useState } from 'react';
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
  const [loading, setLoading] = useState(true);
  const [activePanel, setActivePanel] = useState<Panel>('mission');
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setError(null);
      try {
        const [metricsResp, logsResp, healthResp, automationsResp] = await Promise.all([
          fetch(`${API_URL}/api/analytics/compliance`).then((res) => res.json()),
          fetch(`${API_URL}/api/system/logs?limit=50`).then((res) => res.json()),
          fetch(`${API_URL}/health`).then((res) => res.json()),
          fetch(`${API_URL}/api/automations/`).then((res) => res.json()),
        ]);
        if (!cancelled) {
          setMetrics(metricsResp ?? null);
          setLogs(Array.isArray(logsResp?.logs) ? logsResp.logs : Array.isArray(logsResp) ? logsResp : []);
          setHealth(healthResp ?? null);
          setAutomations(Array.isArray(automationsResp?.data) ? automationsResp.data : []);
          setCheckedAt(new Date());
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load ops data', err);
          setError('Unable to reach the API right now.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadData();
    const interval = setInterval(loadData, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

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
    <main style={{ minHeight: '100vh', backgroundColor: '#020617' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        <header style={{ marginBottom: '16px' }}>
          <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '12px', textTransform: 'uppercase' }}>Ops</p>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
            <div>
              <h1 style={{ fontSize: '32px', fontWeight: 700, color: 'white', marginBottom: '4px' }}>Mission Control</h1>
              <p style={{ color: '#94a3b8' }}>Live telemetry for services, sessions, and cron jobs. No mock data—everything here is reading straight from prod.</p>
            </div>
            <div style={{ textAlign: 'right', color: '#64748b', fontSize: '13px' }}>
              <p>Last check: {checkedAt ? checkedAt.toLocaleTimeString() : '—'}</p>
              <p>API: {error ? 'unreachable' : 'live'}</p>
            </div>
          </div>
        </header>

        <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
          <TabButton active={activePanel === 'mission'} onClick={() => setActivePanel('mission')} label="Mission Control" description="System overview & cron suite" />
          <TabButton active={activePanel === 'org'} onClick={() => setActivePanel('org')} label="Org Chart" description="Feeze → Neo → module agents" />
        </div>

        {activePanel === 'mission' ? (
          <MissionControlView
            loading={loading}
            error={error}
            metrics={metrics}
            models={modelRows}
            sessions={sessionRows}
            cronJobs={cronRows}
          />
        ) : (
          <OrgChartSection layers={orgLayers} />
        )}
      </div>
    </main>
  );
}

function MissionControlView({
  loading,
  error,
  metrics,
  models,
  sessions,
  cronJobs,
}: {
  loading: boolean;
  error: string | null;
  metrics: ComplianceMetrics | null;
  models: { name: string; status: string; version: string; datastore: string }[];
  sessions: { component: string; lastMessage: string; lastTimestamp?: Date }[];
  cronJobs: Automation[];
}) {
  if (loading) {
    return <p style={{ color: '#94a3b8' }}>Refreshing telemetry…</p>;
  }

  if (error) {
    return <p style={{ color: '#f87171' }}>{error}</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <StatGrid metrics={metrics} sessions={sessions.length} cronCount={cronJobs.length} />
      <StatusTable
        title="Models"
        subtitle="Backend surfaces + data stores"
        headers={['Name', 'Status', 'Version', 'Datastore']}
        rows={models.map((model) => [model.name, statusBadge(model.status), model.version, model.datastore])}
      />
      <StatusTable
        title="Active Streams"
        subtitle="Latest events per component"
        headers={['Component', 'Last Event', 'Last Seen']}
        rows={sessions.map((session) => [session.component, session.lastMessage || '—', session.lastTimestamp ? formatTimestamp(session.lastTimestamp) : '—'])}
      />
      <CronTable cronJobs={cronJobs} />
    </div>
  );
}

function StatGrid({ metrics, sessions, cronCount }: { metrics: ComplianceMetrics | null; sessions: number; cronCount: number }) {
  const cards = [
    { label: 'Approvals (24h)', value: metrics?.approvals_last_24h ?? 0, tone: '#38bdf8', detail: 'audit events passed' },
    { label: 'Prospects with email', value: metrics?.prospects_with_email ?? 0, tone: '#fbbf24', detail: 'ready for outreach' },
    { label: 'Live streams', value: sessions, tone: '#34d399', detail: 'components emitting logs' },
    { label: 'Cron jobs', value: cronCount, tone: '#f472b6', detail: 'isolated sessions' },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
      {cards.map((card) => (
        <div key={card.label} style={{ borderRadius: '16px', border: '1px solid #1f2937', padding: '16px', backgroundColor: '#0f172a' }}>
          <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{card.label}</p>
          <p style={{ color: card.tone, fontSize: '28px', fontWeight: 600 }}>{card.value}</p>
          <p style={{ color: '#64748b', fontSize: '12px' }}>{card.detail}</p>
        </div>
      ))}
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
        background: active ? 'linear-gradient(120deg, rgba(251,191,36,0.15), rgba(15,23,42,0.95))' : '#0f172a',
        color: 'white',
        cursor: 'pointer',
      }}
    >
      <p style={{ fontSize: '16px', fontWeight: 600 }}>{label}</p>
      <p style={{ fontSize: '13px', color: '#94a3b8' }}>{description}</p>
    </button>
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
