'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { getApiUrl } from '@/lib/api-client';
import { contentPipelineSnapshot } from '../../legacy/content-pipeline/workspaceSnapshot';

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

const PANEL_HASH: Record<Panel, string> = {
  mission: '',
  team: '#team',
  pm: '#pm',
  standups: '#standups',
  workspace: '#workspace',
  docs: '#docs',
};

type OrgNode = {
  id: string;
  name: string;
  role: string;
  description: string;
  status: 'active' | 'planned';
  highlight: 'core' | 'ops' | 'brain' | 'lab';
  responsibilities?: string[];
};

type PlanCandidate = {
  source_kind: string;
  title: string;
  category: string;
  role_alignment: string;
  risk_level: string;
  publish_posture: string;
  hook: string;
  rationale: string;
  source_path: string;
  score: number;
  priority_lane?: string;
};

type WeeklyPlan = {
  generated_at: string;
  workspace: string;
  positioning_model: string[];
  priority_lanes: string[];
  recommendations: PlanCandidate[];
  hold_items: PlanCandidate[];
  market_signals: {
    title: string;
    priority_lane: string;
    role_alignment: string;
    summary: string;
    source_path: string;
  }[];
  source_counts: {
    drafts: number;
    media: number;
    research: number;
  };
};

type ReactionItem = {
  title: string;
  author: string;
  source_path: string;
  priority_lane: string;
  role_alignment: string;
  hook: string;
  summary: string;
  why_it_matters: string;
  suggested_comment: string;
  post_angle: string;
  score: number;
};

type ReactionQueue = {
  generated_at: string;
  comment_opportunities: ReactionItem[];
  post_seeds: ReactionItem[];
  counts: {
    comment_opportunities: number;
    post_seeds: number;
    background_only: number;
  };
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
    if (typeof window === 'undefined') {
      return;
    }

    const syncPanelFromHash = () => {
      const hash = window.location.hash;
      const nextPanel = (Object.entries(PANEL_HASH).find(([, value]) => value === hash)?.[0] ?? initialPanel) as Panel;
      setActivePanel(nextPanel);
    };

    syncPanelFromHash();
    window.addEventListener('hashchange', syncPanelFromHash);
    return () => window.removeEventListener('hashchange', syncPanelFromHash);
  }, [initialPanel]);

  const selectPanel = useCallback((panel: Panel) => {
    setActivePanel(panel);
    if (typeof window === 'undefined') {
      return;
    }
    const nextUrl = `${window.location.pathname}${window.location.search}${PANEL_HASH[panel]}`;
    window.history.replaceState(null, '', nextUrl);
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
    { key: 'mission', label: 'Mission Control', active: activePanel === 'mission', onSelect: () => selectPanel('mission') },
    { key: 'team', label: 'Team', active: activePanel === 'team', onSelect: () => selectPanel('team') },
    { key: 'pm', label: 'PM Board', active: activePanel === 'pm', onSelect: () => selectPanel('pm') },
    { key: 'standups', label: 'Standups', active: activePanel === 'standups', onSelect: () => selectPanel('standups') },
    { key: 'workspace', label: 'Workspace', active: activePanel === 'workspace', onSelect: () => selectPanel('workspace') },
    { key: 'docs', label: 'Docs', active: activePanel === 'docs', onSelect: () => selectPanel('docs') },
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
  const plan = contentPipelineSnapshot.weeklyPlan as unknown as WeeklyPlan | null;
  const reactionQueue = contentPipelineSnapshot.reactionQueue as unknown as ReactionQueue | null;
  const editorialMix = Array.from(contentPipelineSnapshot.editorialMix ?? []);
  const linkedinFiles = useMemo(
    () => files.filter((file) => file.path.includes('/workspaces/linkedin-content-os/') || file.group.startsWith('linkedin-content-os')),
    [files],
  );
  const selectedLinkedin = useMemo(
    () => linkedinFiles.find((file) => file.path === selected?.path) ?? linkedinFiles[0] ?? null,
    [linkedinFiles, selected],
  );
  const groups = useMemo(() => {
    const map = new Map<string, WorkspaceFile[]>();
    linkedinFiles.forEach((file) => {
      const bucket = map.get(file.group) ?? [];
      bucket.push(file);
      map.set(file.group, bucket);
    });
    return Array.from(map.entries());
  }, [linkedinFiles]);
  const workflowDoc = useMemo(() => findWorkspaceFile(linkedinFiles, 'docs/linkedin_curation_workflow.md'), [linkedinFiles]);
  const backlogDoc = useMemo(() => findWorkspaceFile(linkedinFiles, 'backlog.md'), [linkedinFiles]);
  const workflowSteps = useMemo(() => (workflowDoc ? parseSubsections(extractSection(workflowDoc.content, 'Core Workflow')) : []), [workflowDoc]);
  const saveRules = useMemo(() => (workflowDoc ? collectSaveRules(workflowDoc.content) : { keep: [], drop: [] }), [workflowDoc]);
  const backlogActive = useMemo(() => (backlogDoc ? parseSubsections(extractSection(backlogDoc.content, 'Active')) : []), [backlogDoc]);
  const draftFiles = useMemo(
    () => linkedinFiles.filter((file) => file.path.includes('/drafts/') && file.path.endsWith('.md') && !file.path.endsWith('/README.md')),
    [linkedinFiles],
  );
  const docFiles = useMemo(
    () => linkedinFiles.filter((file) => file.path.includes('/docs/') && file.path.endsWith('.md') && !file.path.endsWith('/README.md')),
    [linkedinFiles],
  );

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workspace</p>
        <h2 style={{ fontSize: '30px', margin: '4px 0', color: 'white' }}>LinkedIn Strategy Workspace</h2>
        <p style={{ color: '#94a3b8' }}>The Workspace tab now carries the LinkedIn OS strategy surface directly: positioning, weekly plan, reaction queue, and the raw LinkedIn workspace files underneath.</p>
      </div>
      <section
        style={{
          borderRadius: '22px',
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(35,12,56,0.95), rgba(9,7,22,0.98))',
          border: '1px solid rgba(217,70,239,0.22)',
          boxShadow: '0 26px 72px rgba(0,0,0,0.35)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', marginBottom: '18px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>LinkedIn OS</p>
            <h3 style={{ fontSize: '30px', color: 'white', margin: '4px 0' }}>Strategy mission control</h3>
            <p style={{ color: '#d8b4fe', maxWidth: '760px', fontSize: '14px' }}>
              Persona truth, signal capture, weekly recommendations, and engagement moves for `linkedin-content-os` now live inside Workspaces instead of on a separate page.
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(140px, 1fr))', gap: '12px' }}>
            <MiniMeta label="Plan Refreshed" value={plan?.generated_at ?? '-'} detail="weekly_plan snapshot" />
            <MiniMeta label="Reaction Queue" value={reactionQueue?.generated_at ?? '-'} detail="reaction_queue snapshot" />
            <MiniMeta label="Draft Queue" value={`${draftFiles.length || plan?.source_counts.drafts || 0}`} detail="Ready or in progress" />
            <MiniMeta label="Signals" value={`${plan?.market_signals.length ?? 0}`} detail="Captured market signals" />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          {(plan?.positioning_model ?? []).slice(0, 4).map((item) => (
            <div key={item} style={{ borderRadius: '16px', border: '1px solid rgba(192,132,252,0.25)', backgroundColor: 'rgba(17,24,39,0.68)', padding: '14px' }}>
              <p style={{ color: '#f5d0fe', fontSize: '14px', lineHeight: 1.5 }}>{item}</p>
            </div>
          ))}
          {!(plan?.positioning_model?.length) && <EmptyPanel message="No LinkedIn positioning model available yet." />}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Priority Lanes</p>
          <h3 style={{ fontSize: '22px', color: 'white', margin: '6px 0 12px' }}>What to publish around</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {(plan?.priority_lanes ?? []).map((lane) => (
              <span key={lane} style={{ borderRadius: '999px', border: '1px solid #374151', padding: '8px 12px', color: '#e2e8f0', fontSize: '13px', backgroundColor: '#020617' }}>
                {lane}
              </span>
            ))}
          </div>
          {editorialMix.length > 0 && (
            <>
              <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', margin: '18px 0 8px' }}>Editorial Mix</p>
              <div style={{ display: 'grid', gap: '8px' }}>
                {editorialMix.slice(0, 4).map((item) => (
                  <div key={item} style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '10px 12px', color: '#cbd5f5', fontSize: '13px' }}>
                    {item}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Workflow</p>
          <h3 style={{ fontSize: '22px', color: 'white', margin: '6px 0 12px' }}>Capture to publish</h3>
          {workflowSteps.length > 0 ? (
            <div style={{ display: 'grid', gap: '10px' }}>
              {workflowSteps.map((step) => (
                <div key={step.title} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '12px 14px' }}>
                  <p style={{ color: '#f8fafc', fontWeight: 700, marginBottom: '6px' }}>{step.title}</p>
                  <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.5 }}>{summarize(step.body, 180)}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyPanel message="Workflow doc is not mounted in this frontend context yet, but the strategy snapshot below is live." />
          )}
          {saveRules.keep.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '8px' }}>Signal Rules</p>
              <ul style={{ margin: 0, paddingLeft: '18px', color: '#cbd5f5', display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '13px' }}>
                {saveRules.keep.slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Weekly Recommendations</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Recommended LinkedIn posts</h3>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>{plan?.recommendations.length ?? 0} ranked items</span>
        </div>
        <div style={{ display: 'grid', gap: '12px' }}>
          {(plan?.recommendations ?? []).slice(0, 4).map((item, index) => (
            <article key={`${item.source_path}-${index}`} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#f8fafc', fontSize: '12px' }}>{index + 1}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>{item.role_alignment}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#fbbf24', fontSize: '12px' }}>{item.risk_level}</span>
                {item.priority_lane ? <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{item.priority_lane}</span> : null}
              </div>
              <h4 style={{ fontSize: '18px', color: 'white', margin: '0 0 6px' }}>{item.title}</h4>
              <p style={{ color: '#f5d0fe', fontSize: '14px', marginBottom: '8px' }}>{item.hook}</p>
              <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.55 }}>{item.rationale}</p>
              <p style={{ color: '#64748b', fontSize: '12px', marginTop: '10px' }}>{item.source_path}</p>
            </article>
          ))}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Reaction Queue</p>
              <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Immediate comment opportunities</h3>
            </div>
            <span style={{ color: '#64748b', fontSize: '13px' }}>{reactionQueue?.counts.comment_opportunities ?? 0}</span>
          </div>
          <div style={{ display: 'grid', gap: '12px' }}>
            {(reactionQueue?.comment_opportunities ?? []).slice(0, 3).map((item) => (
              <article key={item.source_path} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>{item.priority_lane} · {item.role_alignment}</p>
                <p style={{ color: '#f5d0fe', fontSize: '13px', marginTop: '8px' }}>{item.hook}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{item.suggested_comment}</p>
              </article>
            ))}
          </div>
        </section>

        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Draft Inputs</p>
              <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Post seeds and assets</h3>
            </div>
            <span style={{ color: '#64748b', fontSize: '13px' }}>{reactionQueue?.counts.post_seeds ?? 0} seeds</span>
          </div>
          <div style={{ display: 'grid', gap: '12px', marginBottom: '14px' }}>
            {(reactionQueue?.post_seeds ?? []).slice(0, 3).map((item) => (
              <article key={`${item.source_path}-seed`} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>{item.priority_lane}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{item.post_angle}</p>
              </article>
            ))}
          </div>
          <div style={{ display: 'grid', gap: '8px' }}>
            <MiniMeta label="Workspace Docs" value={`${docFiles.length}`} detail="LinkedIn OS runbooks and models" />
            <MiniMeta label="Backlog Items" value={`${backlogActive.length}`} detail="Active LinkedIn tasks" />
            <MiniMeta label="Draft Files" value={`${draftFiles.length}`} detail="Posts ready to refine" />
          </div>
        </section>
      </div>

      {backlogActive.length > 0 && (
        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ marginBottom: '14px' }}>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Backlog</p>
            <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Active LinkedIn workspace tasks</h3>
          </div>
          <div style={{ display: 'grid', gap: '12px', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
            {backlogActive.slice(0, 4).map((item) => (
              <div key={item.title} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{summarize(item.body, 160)}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <SplitPane
        sidebar={
          linkedinFiles.length === 0 ? (
            <EmptyPanel message="Raw LinkedIn workspace files are not mounted in this frontend context yet. The strategy snapshot above is still live." compact />
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
                          border: file.path === selectedLinkedin?.path ? '1px solid #fbbf24' : '1px solid #1f2937',
                          background: file.path === selectedLinkedin?.path ? 'rgba(251,191,36,0.12)' : '#050b19',
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
        content={selectedLinkedin ? <MarkdownSurface title={selectedLinkedin.name} path={selectedLinkedin.path} updatedAt={selectedLinkedin.updatedAt} content={selectedLinkedin.content} /> : <EmptyPanel message="Select a LinkedIn workspace file to inspect." />}
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

type MarkdownSubsection = {
  title: string;
  body: string;
  fields: Record<string, string>;
};

function findWorkspaceFile(files: WorkspaceFile[], suffix: string) {
  return files.find((file) => file.path.endsWith(suffix)) ?? null;
}

function extractSection(raw: string, heading: string) {
  const marker = `## ${heading}`;
  const start = raw.indexOf(marker);
  if (start === -1) {
    return '';
  }
  let section = raw.slice(start + marker.length);
  if (section.startsWith('\n')) {
    section = section.slice(1);
  }
  const nextHeading = section.indexOf('\n## ');
  if (nextHeading !== -1) {
    section = section.slice(0, nextHeading);
  }
  return section.trim();
}

function parseSubsections(section: string): MarkdownSubsection[] {
  if (!section) {
    return [];
  }
  const pattern = /###\s+([^\n]+)\n([\s\S]*?)(?=(?:\n###\s)|$)/g;
  const matches = Array.from(section.matchAll(pattern));
  return matches.map((match) => ({
    title: match[1].trim(),
    body: match[2].trim(),
    fields: parseKeyValueBullets(match[2]),
  }));
}

function parseKeyValueBullets(body: string) {
  const lines = body.split('\n');
  const map: Record<string, string> = {};
  for (const raw of lines) {
    const line = raw.trim();
    if (!line.startsWith('- ')) {
      continue;
    }
    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) {
      continue;
    }
    const key = line.slice(2, colonIndex).trim();
    const value = line.slice(colonIndex + 1).trim();
    map[key] = value;
  }
  return map;
}

function parseBullets(section: string) {
  return section
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => line.slice(2).trim())
    .filter((item) => item.length > 0);
}

function collectSaveRules(raw: string) {
  const section = extractSection(raw, 'Save Rules');
  const keepMatch = section.match(/Keep a signal if:\s*([\s\S]*?)Do not keep a signal if:/);
  const keep = keepMatch ? parseBullets(keepMatch[1]) : parseBullets(section);
  const dropMatch = section.match(/Do not keep a signal if:\s*([\s\S]*)/);
  const drop = dropMatch ? parseBullets(dropMatch[1]) : [];
  return { keep, drop };
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

function summarize(text: string, maxLength = 120) {
  const trimmed = text.replace(/\s+/g, ' ').trim();
  if (trimmed.length <= maxLength) {
    return trimmed;
  }
  return `${trimmed.slice(0, maxLength).trim()}...`;
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
