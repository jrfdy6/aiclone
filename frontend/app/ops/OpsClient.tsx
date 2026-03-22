'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { getApiUrl } from '@/lib/api-client';

const API_URL = getApiUrl();

function pickWorkspacePath(files: WorkspaceFile[], workspaceKey?: string): string | null {
  if (!workspaceKey) {
    return null;
  }
  const match =
    files.find((file) => file.path.includes(`/workspaces/${workspaceKey}/`)) ??
    files.find((file) => file.group.startsWith(workspaceKey));
  return match?.path ?? null;
}

export type WorkspaceFile = {
  group: string;
  name: string;
  path: string;
  snippet: string;
  content: string;
  updatedAt: string;
};

export type DocReference = {
  name: string;
  path: string;
  snippet: string;
  content: string;
  updatedAt: string;
};

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

type PMCard = {
  id: string;
  title: string;
  owner?: string | null;
  status: string;
  source?: string | null;
  link_type?: string | null;
  link_id?: string | null;
  due_at?: string | null;
  payload?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
};

type StandupEntry = {
  id: string;
  owner: string;
  status?: string | null;
  blockers: string[];
  commitments: string[];
  needs: string[];
  source?: string | null;
  conversation_path?: string | null;
  created_at?: string;
};

type Panel = 'mission' | 'team' | 'pm' | 'standups' | 'workspace' | 'docs';

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

type OpenBrainHealth = {
  database_connected: boolean;
  vector_extension: boolean;
  embedding_type?: string | null;
  configured_dimension?: number | null;
  storage_backend?: string | null;
  embedder_dimension: number;
  dimension_match: boolean;
  capture_count: number;
  vector_count: number;
  non_expired_vector_count: number;
  search_ready: boolean;
};

type TelemetryErrors = {
  metrics: string | null;
  logs: string | null;
  health: string | null;
  automations: string | null;
  brain: string | null;
  brainHealth: string | null;
  pmCards: string | null;
  standups: string | null;
};

type LogsResponse = { logs?: SystemLog[] } | SystemLog[];
type AutomationsResponse = { data?: Automation[] } | { automations?: Automation[] } | Automation[] | null | undefined;

const TELEMETRY_LABELS: Record<keyof TelemetryErrors, string> = {
  metrics: 'Compliance metrics',
  logs: 'System logs',
  health: 'Service health',
  automations: 'Automations suite',
  brain: 'Open Brain telemetry',
  brainHealth: 'Open Brain health',
  pmCards: 'PM board',
  standups: 'Standups',
};

const orgLayers: OrgNode[][] = [
  [
    {
      id: 'feeze',
      name: 'Feeze',
      role: 'Principal Operator',
      description: 'Approves production deploys, data use, and spend.',
      status: 'active',
      highlight: 'core',
      responsibilities: ['Final approvals', 'Risk posture', 'Product direction'],
    },
  ],
  [
    {
      id: 'neo',
      name: 'Neo',
      role: 'Core Agent',
      description: 'Routes work across Ops, Brain, and Lab while enforcing guardrails.',
      status: 'active',
      highlight: 'ops',
      responsibilities: ['Mission Control', 'Process orchestration', 'Deployment coordination'],
    },
  ],
  [
    {
      id: 'brain-agent',
      name: 'Brain Agent',
      role: 'Knowledge lane',
      description: 'Daily briefs, docs, persona deltas, and memory health.',
      status: 'planned',
      highlight: 'brain',
      responsibilities: ['Daily brief cron', 'Docs mirror', 'Memory review'],
    },
    {
      id: 'lab-agent',
      name: 'Lab Agent',
      role: 'Staging lane',
      description: 'Owns prototypes, build logs, and self-improvement runs.',
      status: 'planned',
      highlight: 'lab',
      responsibilities: ['Nightly self-improvement', 'Build logs', 'Staging QA'],
    },
  ],
];

export default function OpsClient({
  workspaceFiles,
  docEntries,
  initialPanel = 'mission',
  initialWorkspaceKey,
}: {
  workspaceFiles: WorkspaceFile[];
  docEntries: DocReference[];
  initialPanel?: Panel;
  initialWorkspaceKey?: string;
}) {
  const [metrics, setMetrics] = useState<ComplianceMetrics | null>(null);
  const [logs, setLogs] = useState<SystemLog[]>([]);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [pmCards, setPmCards] = useState<PMCard[]>([]);
  const [standups, setStandups] = useState<StandupEntry[]>([]);
  const [brainMetrics, setBrainMetrics] = useState<OpenBrainTelemetry | null>(null);
  const [brainHealth, setBrainHealth] = useState<OpenBrainHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [activePanel, setActivePanel] = useState<Panel>(initialPanel);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [selectedWorkspacePath, setSelectedWorkspacePath] = useState(() => pickWorkspacePath(workspaceFiles, initialWorkspaceKey) ?? workspaceFiles[0]?.path ?? '');
  const [selectedDocPath, setSelectedDocPath] = useState(docEntries[0]?.path ?? '');
  const [sectionErrors, setSectionErrors] = useState<TelemetryErrors>({
    metrics: null,
    logs: null,
    health: null,
    automations: null,
    brain: null,
    brainHealth: null,
    pmCards: null,
    standups: null,
  });

  const updateSectionError = useCallback((key: keyof TelemetryErrors, message: string | null) => {
    setSectionErrors((prev) => ({ ...prev, [key]: message }));
  }, []);

  useEffect(() => {
    if (!workspaceFiles.some((file) => file.path === selectedWorkspacePath)) {
      setSelectedWorkspacePath(pickWorkspacePath(workspaceFiles, initialWorkspaceKey) ?? workspaceFiles[0]?.path ?? '');
    }
  }, [initialWorkspaceKey, selectedWorkspacePath, workspaceFiles]);

  useEffect(() => {
    if (!docEntries.some((entry) => entry.path === selectedDocPath)) {
      setSelectedDocPath(docEntries[0]?.path ?? '');
    }
  }, [docEntries, selectedDocPath]);

  const loadTelemetry = useCallback(async () => {
    setIsRefreshing(true);
    setGlobalError(null);

    const requests = await Promise.allSettled([
      fetchJson<ComplianceMetrics>(`${API_URL}/api/analytics/compliance`),
      fetchJson<LogsResponse>(`${API_URL}/api/system/logs/?limit=40`),
      fetchJson<HealthPayload>(`${API_URL}/health`),
      fetchJson<AutomationsResponse>(`${API_URL}/api/automations/`),
      fetchJson<OpenBrainTelemetry>(`${API_URL}/api/analytics/open-brain`),
      fetchJson<OpenBrainHealth>(`${API_URL}/api/open-brain/health`),
      fetchJson<PMCard[]>(`${API_URL}/api/pm/cards?limit=50`),
      fetchJson<StandupEntry[]>(`${API_URL}/api/standups/?limit=20`),
    ]);

    const [metricsResp, logsResp, healthResp, automationsResp, brainResp, brainHealthResp, pmResp, standupsResp] = requests;

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

    if (brainHealthResp.status === 'fulfilled') {
      setBrainHealth(brainHealthResp.value ?? null);
      updateSectionError('brainHealth', null);
    } else {
      updateSectionError('brainHealth', toErrorMessage(brainHealthResp.reason));
    }

    if (pmResp.status === 'fulfilled') {
      setPmCards(Array.isArray(pmResp.value) ? pmResp.value : []);
      updateSectionError('pmCards', null);
    } else {
      updateSectionError('pmCards', toErrorMessage(pmResp.reason));
    }

    if (standupsResp.status === 'fulfilled') {
      setStandups(Array.isArray(standupsResp.value) ? standupsResp.value : []);
      updateSectionError('standups', null);
    } else {
      updateSectionError('standups', toErrorMessage(standupsResp.reason));
    }

    const failures = requests.filter((result) => result.status === 'rejected');
    if (failures.length === requests.length) {
      setGlobalError('Unable to reach the production control APIs right now. Check backend health and Railway logs before trusting the UI.');
    }

    setCheckedAt(new Date());
    setLoading(false);
    setIsRefreshing(false);
  }, [updateSectionError]);

  useEffect(() => {
    loadTelemetry();
    const interval = setInterval(loadTelemetry, 60_000);
    return () => clearInterval(interval);
  }, [loadTelemetry]);

  const sectionErrorSummary = useMemo(() => {
    const messages = Object.entries(sectionErrors)
      .filter(([, value]) => Boolean(value))
      .map(([key, value]) => `${TELEMETRY_LABELS[key as keyof TelemetryErrors]}: ${value}`);
    return messages.length ? messages.join(' | ') : null;
  }, [sectionErrors]);

  const modelRows = useMemo(() => {
    if (!health) return [];
    return [
      {
        name: health.service ?? 'aiclone-backend',
        status: health.status ?? 'unknown',
        version: health.version ?? 'n/a',
        datastore: health.firestore ?? 'n/a',
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

  const selectedWorkspace = useMemo(
    () => workspaceFiles.find((file) => file.path === selectedWorkspacePath) ?? workspaceFiles[0] ?? null,
    [selectedWorkspacePath, workspaceFiles],
  );
  const selectedDoc = useMemo(
    () => docEntries.find((entry) => entry.path === selectedDocPath) ?? docEntries[0] ?? null,
    [docEntries, selectedDocPath],
  );

  const tabs = [
    { key: 'mission', label: 'Mission Control', active: activePanel === 'mission', onSelect: () => setActivePanel('mission') },
    { key: 'team', label: 'Team', active: activePanel === 'team', onSelect: () => setActivePanel('team') },
    { key: 'pm', label: 'PM Board', active: activePanel === 'pm', onSelect: () => setActivePanel('pm') },
    { key: 'standups', label: 'Standups', active: activePanel === 'standups', onSelect: () => setActivePanel('standups') },
    { key: 'workspace', label: 'Workspace', active: activePanel === 'workspace', onSelect: () => setActivePanel('workspace') },
    { key: 'docs', label: 'Docs', active: activePanel === 'docs', onSelect: () => setActivePanel('docs') },
  ];

  return (
    <RuntimePage module="ops" tabs={tabs}>
      <header style={{ marginBottom: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <div>
            <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Ops</p>
            <h1 style={{ fontSize: '40px', fontWeight: 700, color: 'white', margin: '4px 0' }}>Mission Control</h1>
            <p style={{ color: '#8ea0bd', maxWidth: '760px' }}>Runtime health, live telemetry, team surfaces, and the control-center shell from the March 20 reference screenshots.</p>
          </div>
          <div style={{ textAlign: 'right', color: '#94a3b8', fontSize: '13px', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
            <p>Last check: {checkedAt ? checkedAt.toLocaleTimeString() : loading ? 'Checking...' : '-'}</p>
            <p>Refresh cadence: 60s poll + manual trigger</p>
            <button
              onClick={loadTelemetry}
              disabled={isRefreshing}
              style={{
                padding: '9px 18px',
                borderRadius: '999px',
                border: '1px solid rgba(251,191,36,0.35)',
                backgroundColor: isRefreshing ? '#101827' : '#fbbf24',
                color: isRefreshing ? '#94a3b8' : '#0f172a',
                fontWeight: 700,
                cursor: isRefreshing ? 'not-allowed' : 'pointer',
              }}
            >
              {isRefreshing ? 'Refreshing...' : 'Manual refresh'}
            </button>
          </div>
        </div>
      </header>

      {globalError && <SectionAlert message={globalError} />}
      {!globalError && sectionErrorSummary && <SectionAlert message={sectionErrorSummary} />}

      {activePanel === 'mission' && (
        <MissionControlView
          loading={loading}
          metrics={metrics}
          metricsError={sectionErrors.metrics}
          models={modelRows}
          modelsError={sectionErrors.health}
          sessions={sessionRows}
          sessionsError={sectionErrors.logs}
          cronJobs={automations}
          cronError={sectionErrors.automations}
          brainMetrics={brainMetrics}
          brainError={sectionErrors.brain}
          brainHealth={brainHealth}
          brainHealthError={sectionErrors.brainHealth}
        />
      )}
      {activePanel === 'team' && <OrgChartSection layers={orgLayers} />}
      {activePanel === 'pm' && <PMBoardPanel cards={pmCards} error={sectionErrors.pmCards} />}
      {activePanel === 'standups' && <StandupsPanel entries={standups} error={sectionErrors.standups} />}
      {activePanel === 'workspace' && (
        <WorkspacePanel
          files={workspaceFiles}
          selected={selectedWorkspace}
          onSelect={setSelectedWorkspacePath}
        />
      )}
      {activePanel === 'docs' && <DocsPanel docs={docEntries} selected={selectedDoc} onSelect={setSelectedDocPath} />}
    </RuntimePage>
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
  brainHealth,
  brainHealthError,
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
  brainHealth: OpenBrainHealth | null;
  brainHealthError: string | null;
}) {
  if (loading) {
    return <p style={{ color: '#94a3b8' }}>Refreshing telemetry...</p>;
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
      <OpenBrainPanel metrics={brainMetrics} health={brainHealth} />
      {brainError && <SectionAlert message={`${TELEMETRY_LABELS.brain}: ${brainError}`} />}
      {brainHealthError && <SectionAlert message={`${TELEMETRY_LABELS.brainHealth}: ${brainHealthError}`} />}
      <StatusTable
        title="Active Streams"
        subtitle="Latest events per component"
        headers={['Component', 'Last Event', 'Last Seen']}
        rows={sessions.map((session) => [session.component, session.lastMessage || '-', session.lastTimestamp ? formatTimestamp(session.lastTimestamp) : '-'])}
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
    { label: 'Prospects Ready', value: metrics?.prospects_with_email ?? 0, detail: 'Email staged', tone: '#38bdf8' },
    { label: 'Log Streams', value: sessions, detail: 'Active emitters', tone: '#4ade80' },
    { label: 'Cron Runs', value: cronCount, detail: 'Isolated jobs', tone: '#f472b6' },
  ];
  return (
    <section
      style={{
        borderRadius: '22px',
        padding: '24px',
        background: 'linear-gradient(135deg, rgba(17,24,39,0.94), rgba(8,12,24,0.98))',
        border: '1px solid rgba(251,191,36,0.18)',
        boxShadow: '0 26px 72px rgba(0,0,0,0.35)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Ops Dashboard</p>
          <h2 style={{ color: 'white', fontSize: '32px', margin: '4px 0' }}>Mission Control</h2>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Realtime guardrails, sessions, and automations for the production agent.</p>
        </div>
        <div style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'right' }}>
          <p>Reference shell aligned to March 20 capture</p>
          <p>Bottom dock routes across Ops, Brain, and Lab</p>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
        {cards.map((card) => (
          <div key={card.label} style={{ padding: '16px', borderRadius: '18px', backgroundColor: '#060b18', border: '1px solid rgba(30,41,59,0.9)' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{card.label}</p>
            <p style={{ color: card.tone, fontSize: '30px', fontWeight: 700 }}>{card.value}</p>
            <p style={{ color: '#475569', fontSize: '12px' }}>{card.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function OpenBrainPanel({ metrics, health }: { metrics: OpenBrainTelemetry | null; health: OpenBrainHealth | null }) {
  const storageLabel = health?.storage_backend === 'pgvector' ? 'Native vector mode' : health?.storage_backend === 'jsonb' ? 'JSON fallback' : 'Unknown';
  const serviceLabel = health?.search_ready ? 'Search ready' : health?.database_connected ? 'Memory store online' : 'Memory store offline';
  const subtitle =
    health?.storage_backend === 'pgvector'
      ? 'Capture + refresh telemetry from the native Postgres vector lane.'
      : 'Capture + refresh telemetry from the Postgres memory lane. JSON fallback is active until native vector support is available.';

  return (
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Open Brain</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>{subtitle}</p>
        </div>
        <p style={{ color: health?.database_connected ? '#22c55e' : '#f87171', fontSize: '12px' }}>{serviceLabel}</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <MiniMeta label="Storage" value={storageLabel} detail={health?.embedding_type ?? 'n/a'} />
        <MiniMeta label="Native Vector Ext" value={health?.vector_extension ? 'Enabled' : 'Unavailable'} detail="Current Postgres capability" />
        <MiniMeta
          label="Embedding Dimension"
          value={health?.configured_dimension ? `${health.configured_dimension}/${health.embedder_dimension}` : `${health?.embedder_dimension ?? 0}`}
          detail={health?.dimension_match ? 'DB and embedder aligned' : 'Running fallback storage mode'}
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <MiniStat label="Captures" value={metrics?.captures.total ?? 0} tone="#38bdf8" detail="All time" />
        <MiniStat label="New (24h)" value={metrics?.captures.last_24h ?? 0} tone="#4ade80" detail="Working memory" />
        <MiniStat label="Chunks" value={metrics?.vectors.total ?? 0} tone="#f97316" detail="Indexed memory rows" />
        <MiniStat label="Expiring" value={metrics?.vectors.with_expiry ?? 0} tone="#fbbf24" detail="Short-term" />
        <MiniStat label="Overdue" value={metrics?.vectors.overdue ?? 0} tone="#f87171" detail="Needs cleanup" />
        <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
          <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Last refresh</p>
          <p style={{ color: '#cbd5f5', fontSize: '18px', fontWeight: 600 }}>
            {metrics?.vectors.last_refresh_at ? formatTimestamp(new Date(metrics.vectors.last_refresh_at)) : '-'}
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
                  <td style={{ padding: '10px 0', color: '#e2e8f0', fontWeight: 600 }}>{item.source ?? '-'}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{(item.topics ?? []).join(', ') || '-'}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{item.importance ?? '-'}</td>
                  <td style={{ padding: '10px 0', color: '#e2e8f0' }}>{item.chunk_count}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{item.created_at ? formatTimestamp(new Date(item.created_at)) : '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PMBoardPanel({ cards, error }: { cards: PMCard[]; error: string | null }) {
  const buckets = useMemo(() => groupPmCards(cards), [cards]);
  const columns: { key: keyof typeof buckets; label: string }[] = [
    { key: 'todo', label: 'To Do' },
    { key: 'in_progress', label: 'In Progress' },
    { key: 'review', label: 'Review' },
    { key: 'done', label: 'Done' },
  ];

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>PM Board</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>Task flow</h2>
        <p style={{ color: '#94a3b8' }}>Live cards from the production PM API, grouped by status.</p>
      </div>
      {error && <SectionAlert message={`${TELEMETRY_LABELS.pmCards}: ${error}`} />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
        {columns.map((column) => (
          <div key={column.key} style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '16px', minHeight: '260px' }}>
            <div style={{ marginBottom: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <p style={{ color: 'white', fontWeight: 700 }}>{column.label}</p>
              <span style={{ color: '#64748b', fontSize: '12px' }}>{buckets[column.key].length}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {buckets[column.key].length === 0 && <p style={{ color: '#475569', fontSize: '13px' }}>Nothing in this lane yet.</p>}
              {buckets[column.key].map((card) => (
                <article key={card.id} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '14px' }}>
                  <p style={{ color: 'white', fontWeight: 600, marginBottom: '8px' }}>{card.title}</p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                    <span>{card.owner ?? 'Unassigned'}</span>
                    <span>{card.source ?? 'manual'}</span>
                  </div>
                  <div style={{ color: '#64748b', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span>Updated: {card.updated_at ? formatTimestamp(new Date(card.updated_at)) : '-'}</span>
                    <span>Due: {card.due_at ? formatTimestamp(new Date(card.due_at)) : '-'}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StandupsPanel({ entries, error }: { entries: StandupEntry[]; error: string | null }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Standups</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>Async status reports</h2>
        <p style={{ color: '#94a3b8' }}>Formatted reports from the standup API, including blockers, commitments, and cross-team needs.</p>
      </div>
      {error && <SectionAlert message={`${TELEMETRY_LABELS.standups}: ${error}`} />}
      <div style={{ display: 'grid', gap: '14px' }}>
        {entries.length === 0 && <EmptyPanel message="No standup entries recorded yet." />}
        {entries.map((entry) => (
          <article key={entry.id} style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '20px', color: 'white', margin: 0 }}>{entry.owner}</h3>
                <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '4px' }}>{entry.created_at ? formatTimestamp(new Date(entry.created_at)) : '-'}</p>
              </div>
              {statusBadge(entry.status ?? 'pending')}
            </div>
            <PanelList title="Status" items={entry.status ? [entry.status] : []} emptyLabel="No status summary yet." />
            <PanelList title="Blockers" items={entry.blockers} emptyLabel="No blockers captured." />
            <PanelList title="Commitments" items={entry.commitments} emptyLabel="No commitments captured." />
            <PanelList title="Needs" items={entry.needs} emptyLabel="No cross-team needs captured." />
          </article>
        ))}
      </div>
    </section>
  );
}

function WorkspacePanel({ files, selected, onSelect }: { files: WorkspaceFile[]; selected: WorkspaceFile | null; onSelect: (path: string) => void }) {
  const groups = useMemo(() => {
    const map = new Map<string, WorkspaceFile[]>();
    files.forEach((file) => {
      const bucket = map.get(file.group) ?? [];
      bucket.push(file);
      map.set(file.group, bucket);
    });
    return Array.from(map.entries());
  }, [files]);

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workspace</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>Workspace files</h2>
        <p style={{ color: '#94a3b8' }}>Real repo files loaded from the canonical persona bundle and child workspaces, including `workspaces/linkedin-content-os`.</p>
      </div>
      <SplitPane
        sidebar={
          files.length === 0 ? (
            <EmptyPanel message="No persona bundle files found." compact />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {groups.map(([group, items]) => (
                <div key={group}>
                  <p style={{ color: '#64748b', fontSize: '11px', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: '8px' }}>{group}</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {items.map((file) => (
                      <button
                        key={file.path}
                        onClick={() => onSelect(file.path)}
                        style={{
                          textAlign: 'left',
                          padding: '12px',
                          borderRadius: '12px',
                          border: file.path === selected?.path ? '1px solid #fbbf24' : '1px solid #1f2937',
                          background: file.path === selected?.path ? 'rgba(251,191,36,0.12)' : '#050b19',
                          color: 'white',
                          cursor: 'pointer',
                        }}
                      >
                        <p style={{ fontWeight: 600 }}>{file.name}</p>
                        <p style={{ color: '#64748b', fontSize: '12px', marginTop: '4px' }}>{file.snippet || file.path}</p>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        }
        content={selected ? <MarkdownSurface title={selected.name} path={selected.path} updatedAt={selected.updatedAt} content={selected.content} /> : <EmptyPanel message="Select a workspace file to inspect." />}
      />
    </section>
  );
}

function DocsPanel({ docs, selected, onSelect }: { docs: DocReference[]; selected: DocReference | null; onSelect: (path: string) => void }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Docs</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>Specs + runbooks</h2>
        <p style={{ color: '#94a3b8' }}>The docs pane is wired to real local markdown instead of placeholder copy.</p>
      </div>
      <SplitPane
        sidebar={
          docs.length === 0 ? (
            <EmptyPanel message="No docs available." compact />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {docs.map((doc) => (
                <button
                  key={doc.path}
                  onClick={() => onSelect(doc.path)}
                  style={{
                    textAlign: 'left',
                    padding: '12px',
                    borderRadius: '12px',
                    border: doc.path === selected?.path ? '1px solid #fbbf24' : '1px solid #1f2937',
                    background: doc.path === selected?.path ? 'rgba(251,191,36,0.12)' : '#050b19',
                    color: 'white',
                    cursor: 'pointer',
                  }}
                >
                  <p style={{ fontWeight: 600 }}>{doc.name}</p>
                  <p style={{ color: '#64748b', fontSize: '12px', marginTop: '4px' }}>{doc.snippet || doc.path}</p>
                </button>
              ))}
            </div>
          )
        }
        content={selected ? <MarkdownSurface title={selected.name} path={selected.path} updatedAt={selected.updatedAt} content={selected.content} /> : <EmptyPanel message="Select a document to inspect." />}
      />
    </section>
  );
}

function SplitPane({ sidebar, content }: { sidebar: JSX.Element; content: JSX.Element }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr)', gap: '16px', alignItems: 'start' }}>
      <div style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '16px', minHeight: '520px' }}>{sidebar}</div>
      <div style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px', minHeight: '520px' }}>{content}</div>
    </div>
  );
}

function MarkdownSurface({ title, path, updatedAt, content }: { title: string; path: string; updatedAt: string; content: string }) {
  return (
    <div>
      <div style={{ marginBottom: '16px' }}>
        <p style={{ color: '#64748b', fontSize: '12px' }}>{path}</p>
        <h3 style={{ fontSize: '28px', color: 'white', margin: '6px 0' }}>{title}</h3>
        <p style={{ color: '#94a3b8', fontSize: '13px' }}>Updated {formatTimestamp(new Date(updatedAt))}</p>
      </div>
      <pre
        style={{
          margin: 0,
          whiteSpace: 'pre-wrap',
          color: '#dbe4f4',
          fontSize: '13px',
          lineHeight: 1.65,
          fontFamily: 'ui-monospace, SFMono-Regular, SFMono, Menlo, Consolas, monospace',
        }}
      >
        {content}
      </pre>
    </div>
  );
}

function EmptyPanel({ message, compact = false }: { message: string; compact?: boolean }) {
  return (
    <div style={{ borderRadius: compact ? '0' : '16px', border: compact ? 'none' : '1px dashed #1f2937', padding: compact ? 0 : '18px', color: '#64748b', fontSize: '14px' }}>
      {message}
    </div>
  );
}

function PanelList({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel: string }) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '6px' }}>{title}</p>
      {items.length === 0 ? (
        <p style={{ color: '#475569', fontSize: '13px' }}>{emptyLabel}</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: '18px', color: '#dbe4f4', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {items.map((item) => (
            <li key={`${title}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MiniMeta({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
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
    <div
      style={{
        marginBottom: '16px',
        padding: '12px 16px',
        borderRadius: '12px',
        border: '1px solid rgba(248,113,113,0.3)',
        backgroundColor: 'rgba(69,10,10,0.6)',
        color: '#fecaca',
        fontSize: '14px',
      }}
    >
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
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
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
    <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#94a3b8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Cron Jobs</p>
        <p style={{ color: '#64748b', fontSize: '13px' }}>Isolated sessions mirrored into Brain to Automations</p>
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
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.last_run_at ? formatTimestamp(new Date(job.last_run_at)) : '-'}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.next_run_at ? formatTimestamp(new Date(job.next_run_at)) : '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const highlightColors: Record<OrgNode['highlight'], string> = {
  core: '#f97316',
  ops: '#fbbf24',
  brain: '#38bdf8',
  lab: '#4ade80',
};

const statusLabels: Record<OrgNode['status'], string> = {
  active: 'Live',
  planned: 'Planned',
};

function OrgChartSection({ layers }: { layers: OrgNode[][] }) {
  return (
    <section style={{ border: '1px solid #1f2937', borderRadius: '18px', padding: '24px', backgroundColor: '#0b1324' }}>
      <div style={{ marginBottom: '16px' }}>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '12px', textTransform: 'uppercase' }}>Org Design</p>
        <h2 style={{ fontSize: '28px', fontWeight: 600, color: 'white', margin: '4px 0' }}>Team</h2>
        <p style={{ color: '#94a3b8' }}>Feeze to Neo to module-specific agents. Future slots remain visible without pretending they are live.</p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {layers.map((layer, idx) => (
          <div key={`layer-${idx}`} style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
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
        flex: '1 1 240px',
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

function groupPmCards(cards: PMCard[]) {
  return cards.reduce(
    (acc, card) => {
      const normalized = normalizeStatus(card.status);
      acc[normalized].push(card);
      return acc;
    },
    { todo: [] as PMCard[], in_progress: [] as PMCard[], review: [] as PMCard[], done: [] as PMCard[] },
  );
}

function normalizeStatus(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === 'in_progress' || normalized === 'in-progress') return 'in_progress';
  if (normalized === 'review') return 'review';
  if (normalized === 'done') return 'done';
  return 'todo';
}

function statusBadge(status?: string) {
  const normalized = status?.toLowerCase();
  const color =
    normalized === 'healthy' || normalized === 'active' || normalized === 'done'
      ? '#22c55e'
      : normalized === 'warning' || normalized === 'review'
        ? '#fbbf24'
        : normalized === 'error'
          ? '#f87171'
          : normalized === 'in_progress' || normalized === 'in-progress'
            ? '#38bdf8'
            : '#94a3b8';
  return (
    <span style={{ padding: '4px 12px', borderRadius: '999px', backgroundColor: `${color}33`, color, fontSize: '12px', textTransform: 'capitalize' }}>
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
    if (Array.isArray(maybeData)) return maybeData;
    const maybeAutomations = (payload as { automations?: Automation[] }).automations;
    if (Array.isArray(maybeAutomations)) return maybeAutomations;
  }
  return [];
}

function toErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  return 'Unknown error';
}
