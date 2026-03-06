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

type Panel = 'compliance' | 'health' | 'audit';

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
  const [loading, setLoading] = useState(true);
  const [activePanel, setActivePanel] = useState<Panel>('compliance');
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setError(null);
      try {
        const [metricsResp, logsResp, healthResp] = await Promise.all([
          fetch(`${API_URL}/api/analytics/compliance`).then((res) => res.json()),
          fetch(`${API_URL}/api/system/logs?limit=20`).then((res) => res.json()),
          fetch(`${API_URL}/health`).then((res) => res.json()),
        ]);
        if (!cancelled) {
          setMetrics(metricsResp ?? null);
          setLogs(Array.isArray(logsResp?.logs) ? logsResp.logs : Array.isArray(logsResp) ? logsResp : []);
          setHealth(healthResp ?? null);
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

  const panelList = useMemo(
    () => [
      {
        id: 'compliance' as Panel,
        title: 'Compliance Summary',
        subtitle: 'Approvals, prospect coverage, log stream',
        trend: metrics?.approvals_last_24h ?? '—',
      },
      {
        id: 'health' as Panel,
        title: 'Health Watchdog',
        subtitle: 'Railway heartbeat and dependencies',
        trend: health?.status ?? '—',
      },
      {
        id: 'audit' as Panel,
        title: 'Audit Trail',
        subtitle: 'Latest system events + context',
        trend: logs.length,
      },
    ],
    [metrics, health, logs.length]
  );

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        <header style={{ marginBottom: '24px' }}>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '12px', textTransform: 'uppercase' }}>Ops</p>
          <h1 style={{ fontSize: '32px', fontWeight: 700, color: 'white', marginBottom: '8px' }}>Mission Control</h1>
          <p style={{ color: '#94a3b8' }}>Live compliance + health telemetry sourced from the production API (and mirrored into Discord once the cron posts hourly).</p>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px' }}>
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1f2937', borderRadius: '16px', padding: '16px', height: 'fit-content' }}>
            <p style={{ color: '#64748b', fontSize: '12px', textTransform: 'uppercase', marginBottom: '12px' }}>Watchers</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {panelList.map((panel) => (
                <button
                  key={panel.id}
                  onClick={() => setActivePanel(panel.id)}
                  style={{
                    textAlign: 'left',
                    borderRadius: '12px',
                    padding: '12px',
                    border: activePanel === panel.id ? '1px solid #38bdf8' : '1px solid #1f2937',
                    backgroundColor: activePanel === panel.id ? '#0f172a' : '#020617',
                    color: 'white',
                    cursor: 'pointer',
                  }}
                >
                  <p style={{ fontSize: '16px', fontWeight: 600 }}>{panel.title}</p>
                  <p style={{ fontSize: '13px', color: '#94a3b8' }}>{panel.subtitle}</p>
                  <p style={{ fontSize: '12px', color: '#38bdf8', marginTop: '4px' }}>Live • {panel.trend}</p>
                </button>
              ))}
            </div>
          </div>

          <section style={{ backgroundColor: '#0f172a', border: '1px solid #1f2937', borderRadius: '16px', padding: '24px', minHeight: '520px' }}>
            {loading && <p style={{ color: '#94a3b8' }}>Refreshing telemetry…</p>}
            {!loading && error && <p style={{ color: '#f87171' }}>{error}</p>}
            {!loading && !error && activePanel === 'compliance' && metrics && (
              <CompliancePanel metrics={metrics} logs={logs} />
            )}
            {!loading && !error && activePanel === 'health' && (
              <HealthPanel health={health} checkedAt={checkedAt} />
            )}
            {!loading && !error && activePanel === 'audit' && <AuditPanel logs={logs} />}
          </section>
        </div>
        <OrgChartSection layers={orgLayers} />
      </div>
    </main>
  );
}

function CompliancePanel({ metrics, logs }: { metrics: ComplianceMetrics; logs: SystemLog[] }) {
  return (
    <div style={{ color: 'white' }}>
      <h2 style={{ fontSize: '24px', marginBottom: '16px' }}>Compliance Summary</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <MetricCard label="Approvals (24h)" value={metrics.approvals_last_24h ?? 0} tone="#38bdf8" />
        <MetricCard label="Prospects w/ email" value={metrics.prospects_with_email ?? 0} tone="#fbbf24" />
        <MetricCard label="Log snapshots" value={logs.length} tone="#34d399" />
      </div>
      <h3 style={{ fontSize: '16px', color: '#94a3b8', marginBottom: '8px' }}>Latest events</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '320px', overflowY: 'auto' }}>
        {logs.slice(0, 10).map((log, idx) => (
          <div key={`${log.id ?? idx}`} style={{ border: '1px solid #1f2937', borderRadius: '12px', padding: '12px', backgroundColor: '#020617' }}>
            <p style={{ fontSize: '12px', color: '#38bdf8' }}>{log.timestamp}</p>
            <p style={{ fontSize: '14px', fontWeight: 600 }}>{log.component ?? log.level ?? 'system'}</p>
            <p style={{ fontSize: '14px', color: '#cbd5f5' }}>{log.message}</p>
          </div>
        ))}
        {logs.length === 0 && <p style={{ color: '#64748b' }}>No log entries returned.</p>}
      </div>
    </div>
  );
}

function HealthPanel({ health, checkedAt }: { health: HealthPayload | null; checkedAt: Date | null }) {
  return (
    <div style={{ color: 'white' }}>
      <h2 style={{ fontSize: '24px', marginBottom: '16px' }}>Railway Watchdog</h2>
      {health ? (
        <div style={{ border: '1px solid #1f2937', borderRadius: '16px', padding: '24px', backgroundColor: '#020617' }}>
          <p style={{ fontSize: '14px', color: '#94a3b8', marginBottom: '8px' }}>Last check: {checkedAt ? checkedAt.toUTCString() : '—'}</p>
          <p style={{ fontSize: '28px', fontWeight: 700, color: health.status === 'healthy' ? '#34d399' : '#f87171' }}>
            {health.status ?? 'unknown'}
          </p>
          <div style={{ marginTop: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
            <MetricCard label="Service" value={health.service ?? 'n/a'} tone="#3b82f6" />
            <MetricCard label="Version" value={health.version ?? '—'} tone="#a78bfa" />
            <MetricCard label="Firestore" value={health.firestore ?? '—'} tone="#f472b6" />
          </div>
        </div>
      ) : (
        <p style={{ color: '#f97316' }}>No heartbeat response.</p>
      )}
    </div>
  );
}

function AuditPanel({ logs }: { logs: SystemLog[] }) {
  return (
    <div style={{ color: 'white' }}>
      <h2 style={{ fontSize: '24px', marginBottom: '16px' }}>Audit Trail</h2>
      <p style={{ color: '#94a3b8', marginBottom: '16px' }}>
        Append-only snapshot sourced from `/api/system/logs`. Refreshes every 60s.
      </p>
      <div style={{ maxHeight: '420px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {logs.map((log, idx) => (
          <div key={`${log.id ?? idx}`} style={{ borderLeft: "3px solid #38bdf8", padding: '12px', backgroundColor: '#020617', borderRadius: '8px' }}>
            <p style={{ fontSize: '12px', color: '#38bdf8', marginBottom: '4px' }}>{log.timestamp}</p>
            <p style={{ fontSize: '14px', fontWeight: 600 }}>{log.component ?? log.level ?? 'system'}</p>
            <p style={{ fontSize: '14px', color: '#cbd5f5' }}>{log.message}</p>
          </div>
        ))}
        {logs.length === 0 && <p style={{ color: '#64748b' }}>No system logs available.</p>}
      </div>
    </div>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: string | number; tone: string }) {
  return (
    <div style={{ borderRadius: '16px', border: '1px solid #1f2937', padding: '16px', backgroundColor: '#020617' }}>
      <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>{label}</p>
      <p style={{ fontSize: '24px', fontWeight: 700, color: tone }}>{value}</p>
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
        marginTop: '32px',
        border: '1px solid #1f2937',
        borderRadius: '16px',
        padding: '24px',
        backgroundColor: '#020617',
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
