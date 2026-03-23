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
  market_signals: PlanMarketSignal[];
  source_counts: {
    drafts: number;
    media: number;
    research: number;
  };
};

type PlanMarketSignal = {
  source_kind?: string;
  title: string;
  theme?: string;
  priority_lane: string;
  role_alignment: string;
  summary: string;
  source_path: string;
};

type ReactionItem = {
  title: string;
  author: string;
  source_platform?: string;
  source_type?: string;
  source_url?: string;
  source_path: string;
  priority_lane: string;
  role_alignment: string;
  risk_level?: string;
  publish_posture?: string;
  recommended_move?: string;
  hook: string;
  summary: string;
  why_it_matters: string;
  comment_angle?: string;
  suggested_comment: string;
  post_angle: string;
  score: number;
};

type ReactionQueue = {
  generated_at: string;
  workspace?: string;
  comment_opportunities: ReactionItem[];
  post_seeds: ReactionItem[];
  counts: {
    comment_opportunities: number;
    post_seeds: number;
    background_only: number;
  };
};

type SocialFeedItem = {
  id: string;
  platform: string;
  source_lane: string;
  capture_method?: string;
  title: string;
  author: string;
  source_url?: string;
  source_path?: string;
  why_it_matters?: string;
  comment_draft?: string;
  repost_draft?: string;
  lens_variants?: Partial<Record<Exclude<WorkspaceLensId, 'all'>, { label: string; comment: string; short_comment?: string; repost: string; why_this_angle?: string }>>;
  standout_lines?: string[];
  lenses?: string[];
  summary?: string;
  ranking: { total: number };
};

type SocialFeed = {
  generated_at: string;
  workspace: string;
  strategy_mode: string;
  items: SocialFeedItem[];
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

type WorkspaceLensId =
  | 'all'
  | 'admissions'
  | 'entrepreneurship'
  | 'personal-story'
  | 'program-leadership'
  | 'therapist-referral'
  | 'enrollment-management'
  | 'ai-entrepreneurship';

type FeedLensId = Exclude<WorkspaceLensId, 'all'>;

type WorkspaceLens = {
  id: WorkspaceLensId;
  label: string;
  description: string;
};

type SourceRecord = {
  title: string;
  sourcePath: string;
  priorityLane: string;
  roleAlignment: string;
  summary: string;
  author?: string;
  sourcePlatform?: string;
  sourceType?: string;
  sourceUrl?: string;
  hook?: string;
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

const WORKSPACE_LENSES: WorkspaceLens[] = [
  { id: 'all', label: 'All Lanes', description: 'Show every ranked idea and signal in the workspace.' },
  { id: 'admissions', label: 'Admissions', description: 'Lead with admissions, outreach, and family-facing takes.' },
  { id: 'entrepreneurship', label: 'Entrepreneurship', description: 'Bias toward builder, founder-adjacent, and leverage stories.' },
  { id: 'personal-story', label: 'Personal Story', description: 'Highlight lived experience, identity, and story-led framing.' },
  { id: 'program-leadership', label: 'Program Leadership', description: 'Center team leadership, operating systems, and execution.' },
  { id: 'therapist-referral', label: 'Therapist / Referral', description: 'Focus on referral ecosystems, trust, and partner relationships.' },
  { id: 'enrollment-management', label: 'Enrollment Mgmt', description: 'Pull toward enrollment pipeline, conversion, and student journey.' },
  { id: 'ai-entrepreneurship', label: 'AI Entrepreneurship', description: 'Surface AI systems, automation, and intrapreneur/operator takes.' },
];

const POST_MODE_OPTIONS: { id: FeedLensId; label: string }[] = [
  { id: 'entrepreneurship', label: 'Entrepreneurship' },
  { id: 'program-leadership', label: 'Job / Program Leadership' },
  { id: 'enrollment-management', label: 'Enrollment' },
  { id: 'ai-entrepreneurship', label: 'AI + Ops' },
  { id: 'therapist-referral', label: 'Therapy / Referral' },
  { id: 'personal-story', label: 'Personal Story' },
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
  const [activeLens, setActiveLens] = useState<WorkspaceLensId>('all');
  const sourceRecords = useMemo(() => {
    const byPath = new Map<string, SourceRecord>();

    (reactionQueue?.comment_opportunities ?? []).forEach((item) => {
      byPath.set(item.source_path, {
        title: item.title,
        sourcePath: item.source_path,
        priorityLane: item.priority_lane,
        roleAlignment: item.role_alignment,
        summary: item.summary,
        author: item.author,
        sourcePlatform: item.source_platform,
        sourceType: item.source_type,
        sourceUrl: item.source_url,
        hook: item.hook,
      });
    });

    (plan?.market_signals ?? []).forEach((item) => {
      const existing = byPath.get(item.source_path);
      byPath.set(item.source_path, {
        title: item.title,
        sourcePath: item.source_path,
        priorityLane: item.priority_lane,
        roleAlignment: item.role_alignment,
        summary: item.summary,
        author: existing?.author,
        sourcePlatform: existing?.sourcePlatform,
        sourceType: existing?.sourceType,
        sourceUrl: existing?.sourceUrl,
        hook: existing?.hook,
      });
    });

    return Array.from(byPath.values());
  }, [plan?.market_signals, reactionQueue?.comment_opportunities]);
  const lensCounts = useMemo(
    () =>
      WORKSPACE_LENSES.map((lens) => ({
        id: lens.id,
        count:
          (plan?.recommendations ?? []).filter((item) => matchesWorkspaceLens(lens.id, item)).length +
          (reactionQueue?.comment_opportunities ?? []).filter((item) => matchesWorkspaceLens(lens.id, item)).length +
          sourceRecords.filter((item) => matchesWorkspaceLens(lens.id, item)).length,
      })),
    [plan?.recommendations, reactionQueue?.comment_opportunities, sourceRecords],
  );
  const filteredRecommendations = useMemo(
    () => (plan?.recommendations ?? []).filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, plan?.recommendations],
  );
  const filteredSignals = useMemo(
    () => sourceRecords.filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, sourceRecords],
  );
  const filteredCommentOpportunities = useMemo(
    () => (reactionQueue?.comment_opportunities ?? []).filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, reactionQueue?.comment_opportunities],
  );
  const filteredPostSeeds = useMemo(
    () => (reactionQueue?.post_seeds ?? []).filter((item) => matchesWorkspaceLens(activeLens, item)),
    [activeLens, reactionQueue?.post_seeds],
  );
  const activeLensMeta = WORKSPACE_LENSES.find((lens) => lens.id === activeLens) ?? WORKSPACE_LENSES[0];
  const [postMode, setPostMode] = useState<WorkspaceLensId>('ai-entrepreneurship');
  const [selectedRecommendation, setSelectedRecommendation] = useState<PlanCandidate | null>(null);
  const [postDraft, setPostDraft] = useState('');
  const currentSourceRecord = useMemo(
    () => (selectedRecommendation ? sourceRecords.find((record) => record.sourcePath === selectedRecommendation.source_path) : undefined),
    [selectedRecommendation, sourceRecords],
  );
  const socialFeedFile = useMemo(() => findWorkspaceFile(linkedinFiles, 'plans/social_feed.json'), [linkedinFiles]);
  const snapshotSocialFeed = (contentPipelineSnapshot as unknown as { socialFeed?: SocialFeed }).socialFeed ?? null;
  const socialFeed = useMemo<SocialFeed | null>(() => {
    if (socialFeedFile) {
      try {
        return JSON.parse(socialFeedFile.content) as SocialFeed;
      } catch {
        return snapshotSocialFeed;
      }
    }
    return snapshotSocialFeed;
  }, [socialFeedFile, snapshotSocialFeed]);
  const feedItems = socialFeed?.items ?? [];
  const [refreshingFeed, setRefreshingFeed] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [ingestUrl, setIngestUrl] = useState('');
  const [ingestText, setIngestText] = useState('');
  const [ingestTitle, setIngestTitle] = useState('');
  const [ingestPriority, setIngestPriority] = useState('custom');
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);
  const [ingestLoading, setIngestLoading] = useState(false);
  const [quoteStatus, setQuoteStatus] = useState<string | null>(null);
  const [isApprovingQuote, setIsApprovingQuote] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [feedbackState, setFeedbackState] = useState<Record<string, string>>({});
  const [feedbackLoading, setFeedbackLoading] = useState<Record<string, boolean>>({});
  const [feedLensSelections, setFeedLensSelections] = useState<Record<string, FeedLensId>>({});
  const resolveFeedLens = useCallback(
    (item: SocialFeedItem): FeedLensId => {
      const selected = feedLensSelections[item.id];
      if (selected) {
        return selected;
      }
      if (postMode !== 'all') {
        return postMode;
      }
      return 'ai-entrepreneurship';
    },
    [feedLensSelections, postMode],
  );
  const createCommentDraft = useCallback(
    (item: SocialFeedItem, lens: FeedLensId) => {
      const variant = item.lens_variants?.[lens];
      if (variant?.comment) {
        return variant.comment.trim();
      }
      return `${POST_MODE_OPTIONS.find((mode) => mode.id === lens)?.label ?? 'Comment'} angle: ${item.comment_draft ?? item.summary ?? ''}`.trim();
    },
    [],
  );
  const createShortCommentDraft = useCallback(
    (item: SocialFeedItem, lens: FeedLensId) => {
      const variant = item.lens_variants?.[lens];
      if (variant?.short_comment) {
        return variant.short_comment.trim();
      }
      return `${POST_MODE_OPTIONS.find((mode) => mode.id === lens)?.label ?? 'Quick'} take.`.trim();
    },
    [],
  );
  const createRepostDraft = useCallback((item: SocialFeedItem, lens: FeedLensId) => {
    const variant = item.lens_variants?.[lens];
    if (variant?.repost) {
      return variant.repost.trim();
    }
    return `${item.repost_draft ?? item.summary ?? ''}`.trim();
  }, []);
  const copyToClipboard = useCallback(async (text: string, label: string) => {
    if (!text) return;
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      setCopyStatus(`${label} copied!`);
      setTimeout(() => setCopyStatus(null), 1500);
    }
  }, []);
  const refreshSocialFeed = useCallback(async () => {
    setRefreshingFeed(true);
    setRefreshStatus('Refreshing social feed...');
    try {
      const res = await fetch(`${API_URL}/api/workspace/refresh-social-feed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skip_fetch: false, sources: 'safe' }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || 'Unable to queue feed refresh.');
      }
      const data = await res.json();
      setRefreshStatus(`Refresh queued${data.started_at ? ` at ${new Date(data.started_at).toLocaleTimeString()}` : ''}`);
    } catch (error) {
      setRefreshStatus(error instanceof Error ? error.message : 'Refresh failed.');
    } finally {
      setRefreshingFeed(false);
      setTimeout(() => setRefreshStatus(null), 3500);
    }
  }, []);
  const ingestSignal = useCallback(async () => {
    if (!ingestUrl && !ingestText) {
      setIngestStatus('Provide a link or some text.');
      return;
    }
    setIngestLoading(true);
    setIngestStatus('Starting signal ingestion...');
    try {
      const payload = {
        priority_lane: ingestPriority,
        url: ingestUrl || undefined,
        text: ingestText || undefined,
        title: ingestTitle || undefined,
        run_refresh: true,
      };
      const res = await fetch(`${API_URL}/api/workspace/ingest-signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || 'Ingest failed.');
      }
      await res.json();
      setIngestStatus('Signal ingested. Refreshing feed...');
      setIngestUrl('');
      setIngestText('');
      setIngestTitle('');
      refreshSocialFeed();
    } catch (error) {
      setIngestStatus(error instanceof Error ? error.message : 'Ingest failed.');
    } finally {
      setIngestLoading(false);
      setTimeout(() => setIngestStatus(null), 4000);
    }
  }, [ingestPriority, ingestUrl, ingestText, ingestTitle, refreshSocialFeed]);
  const approveFeedLine = useCallback(
    async (item: SocialFeedItem, line: string) => {
      const lens = resolveFeedLens(item);
      setQuoteStatus('Approving quote...');
      setIsApprovingQuote(true);
      try {
        const payload = {
          persona_target: 'feeze.core',
          trait: `LinkedIn quote (${item.author})`,
          notes: `${line.trim()}`,
          metadata: {
            target_file: 'identity/VOICE_PATTERNS.md',
            review_source: 'linkedin_workspace.feed_quote',
            approval_state: 'pending_workspace_approval',
            platform: item.platform,
            author: item.author,
            source_url: item.source_url,
            source_path: item.source_path,
            selected_line: line.trim(),
            workspace: 'linkedin-content-os',
            lens,
          },
        };
        const createRes = await fetch(`${API_URL}/api/persona/deltas`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!createRes.ok) {
          const detail = await createRes.text();
          throw new Error(detail || 'Unable to create persona delta.');
        }
        const delta = await createRes.json();
        const patchRes = await fetch(`${API_URL}/api/persona/deltas/${delta.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            status: 'approved',
            metadata: {
              approval_state: 'approved_from_workspace',
              last_reviewed_at: new Date().toISOString(),
              review_source: 'linkedin_workspace.feed_quote',
            },
          }),
        });
        if (!patchRes.ok) {
          const detail = await patchRes.text();
          throw new Error(detail || 'Unable to finalize persona delta.');
        }
        setQuoteStatus(`Approved quote "${line.slice(0, 40)}..."`);
      } catch (error) {
        setQuoteStatus(error instanceof Error ? error.message : 'Unable to approve quote right now.');
      } finally {
        setIsApprovingQuote(false);
      }
    },
    [resolveFeedLens],
  );
  const recordFeedback = useCallback(
    async (item: SocialFeedItem, decision: 'like' | 'dislike') => {
      const lens = resolveFeedLens(item);
      setFeedbackLoading((current) => ({ ...current, [item.id]: true }));
      const label = decision === 'like' ? 'Liked' : 'Disliked';
      try {
        const payload = {
          feed_item_id: item.id,
          title: item.title,
          platform: item.platform,
          decision,
          lens,
        };
        const res = await fetch(`${API_URL}/api/workspace/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const detail = await res.text();
          throw new Error(detail || 'Unable to save preference.');
        }
        setFeedbackState((current) => ({ ...current, [item.id]: `${label}` }));
      } catch (error) {
        setFeedbackState((current) => ({
          ...current,
          [item.id]: error instanceof Error ? error.message : 'Feedback failed.',
        }));
      } finally {
        setFeedbackLoading((current) => ({ ...current, [item.id]: false }));
      }
    },
    [resolveFeedLens],
  );

  useEffect(() => {
    if (!selectedRecommendation) {
      setPostDraft('');
      return;
    }
    setPostDraft(generatePostDraft(selectedRecommendation, postMode));
  }, [selectedRecommendation, postMode]);

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
        {selectedRecommendation && (
          <section
            style={{
              marginTop: '12px',
              borderRadius: '12px',
              border: '1px solid #334155',
              backgroundColor: '#020617',
              padding: '16px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '12px' }}>
              <div>
                <p style={{ color: '#cbd5f5', fontSize: '12px', textTransform: 'uppercase' }}>Post Composer</p>
                <h4 style={{ color: 'white', margin: '6px 0' }}>{selectedRecommendation.title}</h4>
              </div>
              <span style={{ color: '#64748b', fontSize: '12px' }}>
                mode: {POST_MODE_OPTIONS.find((mode) => mode.id === postMode)?.label ?? 'Default'}
              </span>
            </div>
            <textarea
              value={postDraft}
              onChange={(event) => setPostDraft(event.target.value)}
              rows={5}
              style={{
                width: '100%',
                borderRadius: '12px',
                border: '1px solid #1f2937',
                background: '#030712',
                color: '#e2e8f0',
                padding: '12px',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '10px' }}>
              <button
                onClick={async () => {
                  if (!postDraft) return;
                  if (typeof navigator !== 'undefined' && navigator.clipboard) {
                    await navigator.clipboard.writeText(postDraft);
                  }
                }}
                style={{
                  borderRadius: '12px',
                  border: postDraft ? '1px solid rgba(255,255,255,0.5)' : '1px solid rgba(255,255,255,0.2)',
                  background: postDraft ? 'rgba(255,255,255,0.06)' : 'transparent',
                  color: '#f8fafc',
                  padding: '8px 14px',
                  cursor: postDraft ? 'pointer' : 'not-allowed',
                }}
              >
                Copy post draft
              </button>
              <a
                href={currentSourceRecord?.sourceUrl ?? '#'}
                target="_blank"
                rel="noreferrer"
                style={{
                  borderRadius: '12px',
                  border: '1px solid #38bdf8',
                  background: 'rgba(56,189,248,0.15)',
                  color: '#38bdf8',
                  padding: '8px 14px',
                  textDecoration: 'none',
                  fontSize: '13px',
                }}
              >
                Compose on LinkedIn
              </a>
            </div>
          </section>
        )}
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
          <div>
            <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Social Feed</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>High-performing signals</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px' }}>
              Fresh LinkedIn-first posts from key people and topical sources, mixed with reaction-ready Reddit/RSS placeholders. Comment or repost directly from the cards.
            </p>
          </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
          <button
              onClick={refreshSocialFeed}
              disabled={refreshingFeed}
              style={{
                borderRadius: '10px',
                border: '1px solid #38bdf8',
                padding: '8px 14px',
                background: refreshingFeed ? 'rgba(59,130,246,0.2)' : 'rgba(56,189,248,0.16)',
                color: '#38bdf8',
                cursor: refreshingFeed ? 'not-allowed' : 'pointer',
                fontSize: '13px',
              }}
            >
              {refreshingFeed ? 'Refreshing…' : 'Refresh feed'}
            </button>
            <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>
              Updated {socialFeed?.generated_at ?? 'waiting for feed'} · {feedItems.length} items tracked
            </p>
            {refreshStatus && (
              <p style={{ color: refreshingFeed ? '#38bdf8' : '#34d399', fontSize: '12px', margin: 0 }}>{refreshStatus}</p>
            )}
          </div>
        </div>
        <div style={{ border: '1px solid #334155', borderRadius: '12px', padding: '12px 14px', marginBottom: '16px', backgroundColor: '#030712' }}>
          <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
            Paste a URL or stand-alone copy of a post/text, pick a lane, and generate your persona-friendly comment by clicking ingest.
          </p>
          <input
            placeholder="https://link.to/post"
            value={ingestUrl}
            onChange={(event) => setIngestUrl(event.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', marginBottom: '6px', fontSize: '12px' }}
          />
          <textarea
            placeholder="Or paste text you want to comment on..."
            value={ingestText}
            onChange={(event) => setIngestText(event.target.value)}
            rows={4}
            style={{ width: '100%', padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', fontSize: '12px', resize: 'vertical', marginBottom: '6px' }}
          />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '6px' }}>
            <input
              placeholder="Signal title (optional)"
              value={ingestTitle}
              onChange={(event) => setIngestTitle(event.target.value)}
              style={{ flex: 1, padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', fontSize: '12px' }}
            />
            <select
              value={ingestPriority}
              onChange={(event) => setIngestPriority(event.target.value)}
              style={{ padding: '8px 10px', borderRadius: '8px', border: '1px solid #334155', background: '#020617', color: '#e2e8f0', fontSize: '12px' }}
            >
              {POST_MODE_OPTIONS.map((mode) => (
                <option key={mode.id} value={mode.label}>
                  {mode.label}
                </option>
              ))}
              <option value="custom">Custom</option>
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={ingestLoading ? undefined : ingestSignal}
              disabled={ingestLoading}
              style={{
                borderRadius: '10px',
                border: '1px solid #38bdf8',
                padding: '8px 14px',
                background: ingestLoading ? 'rgba(56,189,248,0.2)' : 'rgba(56,189,248,0.16)',
                color: '#38bdf8',
                cursor: ingestLoading ? 'not-allowed' : 'pointer',
                fontSize: '12px',
              }}
            >
              {ingestLoading ? 'Ingesting…' : 'Ingest signal'}
            </button>
            {ingestStatus && <p style={{ color: '#34d399', fontSize: '12px', margin: 0 }}>{ingestStatus}</p>}
          </div>
        </div>
        {quoteStatus && (
          <div
            style={{
              marginBottom: '12px',
              padding: '10px 14px',
              borderRadius: '10px',
              backgroundColor: isApprovingQuote ? 'rgba(37, 99, 235, 0.2)' : 'rgba(34,197,94,0.2)',
              border: `1px solid ${isApprovingQuote ? 'rgba(37,99,235,0.6)' : 'rgba(34,197,94,0.6)'}`,
              color: '#e0f2fe',
              fontSize: '13px',
            }}
          >
            {quoteStatus}
          </div>
        )}
        {copyStatus && (
          <p style={{ color: '#34d399', fontSize: '12px', marginTop: '-8px', marginBottom: '12px' }}>{copyStatus}</p>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
          {feedItems.slice(0, 5).map((item) => {
            const selectedFeedLens = resolveFeedLens(item);
            const shortCommentDraft = createShortCommentDraft(item, selectedFeedLens);
            const commentDraft = createCommentDraft(item, selectedFeedLens);
            const repostDraft = createRepostDraft(item, selectedFeedLens);
            return (
            <article key={item.id} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                <span style={{ color: '#38bdf8', fontSize: '12px', border: '1px solid rgba(56,189,248,0.4)', borderRadius: '999px', padding: '2px 10px' }}>{item.platform}</span>
                <span style={{ color: '#fcd34d', fontWeight: 600, fontSize: '12px' }}>score {item.ranking.total.toFixed(1)}</span>
              </div>
              <h4 style={{ color: 'white', fontSize: '18px', margin: '0' }}>{item.title}</h4>
              <p style={{ color: '#94a3b8', margin: 0 }}>{item.author}</p>
              {item.source_url && (
                <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px' }}>
                  Open original post
                </a>
              )}
              {item.why_it_matters && <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{item.why_it_matters}</p>}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {POST_MODE_OPTIONS.map((mode) => (
                  <button
                    key={`${item.id}-${mode.id}`}
                    onClick={() => setFeedLensSelections((current) => ({ ...current, [item.id]: mode.id }))}
                    style={{
                      borderRadius: '999px',
                      border: selectedFeedLens === mode.id ? '1px solid #fbbf24' : '1px solid #334155',
                      padding: '6px 12px',
                      background: selectedFeedLens === mode.id ? 'rgba(251,191,36,0.14)' : 'transparent',
                      color: selectedFeedLens === mode.id ? '#fbbf24' : '#cbd5f5',
                      fontSize: '11px',
                      cursor: 'pointer',
                    }}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
              {item.standout_lines?.map((line) => (
                <div key={`${item.id}-${line}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', borderRadius: '12px', border: '1px solid rgba(148,163,184,0.4)', padding: '8px', backgroundColor: '#030712' }}>
                  <span style={{ color: '#e2e8f0', fontSize: '13px', flex: 1 }}>{line}</span>
                  <button
                    onClick={() => approveFeedLine(item, line)}
                    disabled={isApprovingQuote}
                    style={{ borderRadius: '10px', border: '1px solid #fbbf24', padding: '4px 10px', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: isApprovingQuote ? 'not-allowed' : 'pointer' }}
                  >
                    {isApprovingQuote ? 'Approving…' : 'Approve line'}
                  </button>
                </div>
              ))}
              <div>
                <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>Quick reply</p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: '1px solid #334155', margin: 0 }}>{shortCommentDraft}</p>
                  <button
                    onClick={() => copyToClipboard(shortCommentDraft, 'quick reply')}
                    style={{ borderRadius: '10px', border: '1px solid #34d399', background: 'transparent', color: '#34d399', padding: '4px 10px', fontSize: '12px' }}
                  >
                    Copy
                  </button>
                </div>
              </div>
              <div>
                <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>Suggested comment</p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: '1px solid #334155', margin: 0 }}>{commentDraft}</p>
                  <button
                    onClick={() => copyToClipboard(commentDraft, 'comment')}
                    style={{ borderRadius: '10px', border: '1px solid #38bdf8', background: 'transparent', color: '#38bdf8', padding: '4px 10px', fontSize: '12px' }}
                  >
                    Copy
                  </button>
                </div>
              </div>
              <div>
                <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>Suggested repost</p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <p style={{ background: '#030712', padding: '8px 10px', borderRadius: '10px', border: '1px solid #334155', margin: 0 }}>{repostDraft}</p>
                  <button
                    onClick={() => copyToClipboard(repostDraft, 'repost')}
                    style={{ borderRadius: '10px', border: '1px solid #f472b6', background: 'transparent', color: '#f472b6', padding: '4px 10px', fontSize: '12px' }}
                  >
                    Copy
                  </button>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                <button
                  onClick={() => recordFeedback(item, 'like')}
                  disabled={feedbackLoading[item.id]}
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #22c55e',
                    background: feedbackLoading[item.id] ? 'rgba(34,197,94,0.15)' : 'rgba(34,197,94,0.2)',
                    color: '#22c55e',
                    padding: '6px 12px',
                    fontSize: '12px',
                    cursor: feedbackLoading[item.id] ? 'not-allowed' : 'pointer',
                  }}
                >
                  👍 Like
                </button>
                <button
                  onClick={() => recordFeedback(item, 'dislike')}
                  disabled={feedbackLoading[item.id]}
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #f87171',
                    background: feedbackLoading[item.id] ? 'rgba(248,113,113,0.15)' : 'rgba(248,113,113,0.2)',
                    color: '#f87171',
                    padding: '6px 12px',
                    fontSize: '12px',
                    cursor: feedbackLoading[item.id] ? 'not-allowed' : 'pointer',
                  }}
                >
                  👎 Dislike
                </button>
                <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{feedbackState[item.id] ?? 'Select a preference to train the feed.'}</p>
              </div>
            </article>
          );
          })}
          {feedItems.length === 0 && <EmptyPanel message="No social feed items available yet. Run the refresh script to populate the JSON." />}
        </div>
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Perspective Toggle</p>
            <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Shift the strategy lens</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '760px' }}>
              Switch between admissions, entrepreneurship, personal story, leadership, referral, enrollment, and AI lenses to re-rank what is visible. This does not regenerate content yet, but it does surface a different cut of the current workspace.
            </p>
          </div>
          <div style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '12px 14px', minWidth: '220px' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Active Lens</p>
            <p style={{ color: '#f8fafc', fontSize: '20px', fontWeight: 700, margin: '4px 0' }}>{activeLensMeta.label}</p>
            <p style={{ color: '#64748b', fontSize: '13px', lineHeight: 1.45 }}>{activeLensMeta.description}</p>
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          {WORKSPACE_LENSES.map((lens) => {
            const count = lensCounts.find((item) => item.id === lens.id)?.count ?? 0;
            const active = lens.id === activeLens;
            return (
              <button
                key={lens.id}
                onClick={() => setActiveLens(lens.id)}
                style={{
                  borderRadius: '999px',
                  border: active ? '1px solid #fbbf24' : '1px solid #334155',
                  backgroundColor: active ? 'rgba(251,191,36,0.14)' : '#020617',
                  color: active ? '#f8fafc' : '#cbd5f5',
                  padding: '10px 14px',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '13px',
                  fontWeight: 600,
                }}
              >
                <span>{lens.label}</span>
                <span style={{ color: active ? '#fbbf24' : '#64748b', fontSize: '12px' }}>{count}</span>
              </button>
            );
          })}
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
            <p style={{ color: '#64748b', fontSize: '13px' }}>Visible through the <span style={{ color: '#cbd5f5' }}>{activeLensMeta.label}</span> lens.</p>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredRecommendations.length} shown / {plan?.recommendations.length ?? 0} ranked items</span>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            {POST_MODE_OPTIONS.map((mode) => (
              <button
                key={mode.id}
                onClick={() => setPostMode(mode.id)}
                style={{
                  borderRadius: '999px',
                  border: postMode === mode.id ? '1px solid #fbbf24' : '1px solid #1f2937',
                  padding: '6px 14px',
                  background: postMode === mode.id ? 'rgba(251,191,36,0.15)' : 'transparent',
                  color: postMode === mode.id ? '#fbbf24' : '#cbd5f5',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                {mode.label}
              </button>
            ))}
            <span style={{ color: '#64748b', fontSize: '12px' }}>post mode</span>
          </div>
        </div>
        <div style={{ display: 'grid', gap: '12px' }}>
          {filteredRecommendations.slice(0, 4).map((item, index) => {
            const sourceRecord = sourceRecords.find((record) => record.sourcePath === item.source_path);
            const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.source_path);
            return (
            <article key={`${item.source_path}-${index}`} style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#f8fafc', fontSize: '12px' }}>{index + 1}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>{item.role_alignment}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#fbbf24', fontSize: '12px' }}>{item.risk_level}</span>
                <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{labelSourceKind(item.source_kind)}</span>
                {item.priority_lane ? <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{item.priority_lane}</span> : null}
              </div>
              <h4 style={{ fontSize: '18px', color: 'white', margin: '0 0 6px' }}>{item.title}</h4>
              <p style={{ color: '#f5d0fe', fontSize: '14px', marginBottom: '8px' }}>{item.hook}</p>
              <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.55 }}>{item.rationale}</p>
              <div style={{ marginTop: '12px', padding: '12px', borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712' }}>
                <p style={{ color: '#64748b', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '6px' }}>Lens Remix</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5 }}>{buildLensRemix(activeLens, item)}</p>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '12px' }}>
                <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.source_path}</p>
                {sourceRecord?.sourceUrl ? (
                  <a href={sourceRecord.sourceUrl} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                    Open original source
                  </a>
                ) : null}
                {mountedSource ? (
                  <button
                    onClick={() => onSelect(mountedSource.path)}
                    style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                  >
                    Open workspace file
                  </button>
                ) : null}
              </div>
              <button
                onClick={() => setSelectedRecommendation(item)}
                style={{
                  marginTop: '10px',
                  border: '1px solid #38bdf8',
                  borderRadius: '12px',
                  padding: '8px 12px',
                  background: 'rgba(56,189,248,0.08)',
                  color: '#38bdf8',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                Create post from this idea
              </button>
            </article>
          );
          })}
          {filteredRecommendations.length === 0 && <EmptyPanel message={`No recommendations match the ${activeLensMeta.label} lens yet.`} />}
        </div>
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div>
            <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Signal Feed</p>
            <h3 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Source-native market inputs</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '760px' }}>
              These are the actual external signals the workspace is reacting to. This is the evidence lane behind the generated strategy view.
            </p>
          </div>
          <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredSignals.length} shown / {sourceRecords.length} tracked sources</span>
        </div>
        <div style={{ display: 'grid', gap: '12px' }}>
          {filteredSignals.slice(0, 6).map((item) => {
            const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.sourcePath);
            return (
              <article key={item.sourcePath} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                  <div>
                    <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                      {[item.author, item.sourcePlatform, item.sourceType].filter(Boolean).join(' · ') || 'Workspace signal'}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {item.priorityLane ? <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#cbd5f5', fontSize: '12px' }}>{item.priorityLane}</span> : null}
                    <span style={{ borderRadius: '999px', border: '1px solid #374151', padding: '4px 10px', color: '#94a3b8', fontSize: '12px' }}>{item.roleAlignment}</span>
                  </div>
                </div>
                {item.hook ? <p style={{ color: '#f5d0fe', fontSize: '13px', marginTop: '8px' }}>{item.hook}</p> : null}
                <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5, marginTop: '8px' }}>{item.summary}</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.sourcePath}</p>
                  {item.sourceUrl ? (
                    <a href={item.sourceUrl} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original post
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
          {filteredSignals.length === 0 && <EmptyPanel message={`No source-native signals match the ${activeLensMeta.label} lens yet.`} />}
        </div>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Reaction Queue</p>
              <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Immediate comment opportunities</h3>
            </div>
            <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredCommentOpportunities.length} shown / {reactionQueue?.counts.comment_opportunities ?? 0}</span>
          </div>
          <div style={{ display: 'grid', gap: '12px' }}>
            {filteredCommentOpportunities.slice(0, 3).map((item) => {
              const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.source_path);
              return (
              <article key={item.source_path} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>
                  {[item.author, item.source_platform, item.priority_lane, item.role_alignment].filter(Boolean).join(' · ')}
                </p>
                <p style={{ color: '#f5d0fe', fontSize: '13px', marginTop: '8px' }}>{item.hook}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{item.suggested_comment}</p>
                <div style={{ marginTop: '10px', padding: '12px', borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712' }}>
                  <p style={{ color: '#64748b', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '6px' }}>Current Lens Remix</p>
                  <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5 }}>{buildLensRemix(activeLens, item)}</p>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.source_path}</p>
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original post
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
            })}
            {filteredCommentOpportunities.length === 0 && <EmptyPanel message={`No reaction opportunities match the ${activeLensMeta.label} lens yet.`} />}
          </div>
        </section>

        <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#0b1324', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <p style={{ color: '#f0abfc', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Draft Inputs</p>
              <h3 style={{ fontSize: '22px', color: 'white', margin: '4px 0' }}>Post seeds and assets</h3>
            </div>
            <span style={{ color: '#64748b', fontSize: '13px' }}>{filteredPostSeeds.length} shown / {reactionQueue?.counts.post_seeds ?? 0} seeds</span>
          </div>
          <div style={{ display: 'grid', gap: '12px', marginBottom: '14px' }}>
            {filteredPostSeeds.slice(0, 3).map((item) => {
              const mountedSource = findWorkspaceFileBySourcePath(linkedinFiles, item.source_path);
              return (
              <article key={`${item.source_path}-seed`} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px' }}>
                <p style={{ color: '#f8fafc', fontWeight: 700 }}>{item.title}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>{[item.priority_lane, item.role_alignment].filter(Boolean).join(' · ')}</p>
                <p style={{ color: '#cbd5f5', fontSize: '13px', marginTop: '8px', lineHeight: 1.5 }}>{item.post_angle}</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                  <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>{item.source_path}</p>
                  {item.source_url ? (
                    <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px', textDecoration: 'none' }}>
                      Open original post
                    </a>
                  ) : null}
                  {mountedSource ? (
                    <button
                      onClick={() => onSelect(mountedSource.path)}
                      style={{ border: 'none', background: 'transparent', color: '#fbbf24', fontSize: '12px', cursor: 'pointer', padding: 0 }}
                    >
                      Open source file
                    </button>
                  ) : null}
                </div>
              </article>
            );
            })}
            {filteredPostSeeds.length === 0 && <EmptyPanel message={`No post seeds match the ${activeLensMeta.label} lens yet.`} />}
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

function findWorkspaceFileBySourcePath(files: WorkspaceFile[], sourcePath: string) {
  return files.find((file) => file.path.endsWith(sourcePath)) ?? null;
}

function normalizeLensText(value: unknown) {
  return typeof value === 'string'
    ? value
        .toLowerCase()
        .replace(/[`'".,/_-]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
    : '';
}

function collectLensText(item: unknown) {
  if (!item || typeof item !== 'object') {
    return '';
  }
  return Object.values(item as Record<string, unknown>)
    .filter((value) => typeof value === 'string')
    .map((value) => normalizeLensText(value))
    .join(' ');
}

function matchesWorkspaceLens(lens: WorkspaceLensId, item: unknown) {
  if (lens === 'all') {
    return true;
  }

  const text = collectLensText(item);
  if (!text) {
    return false;
  }

  const keywordMap: Record<Exclude<WorkspaceLensId, 'all'>, string[]> = {
    admissions: ['admissions', 'prospective student', 'family', 'outreach', 'school fit', 'higher ed'],
    entrepreneurship: ['entrepreneur', 'founder', 'builder', 'business', 'startup', 'venture', 'operator'],
    'personal-story': ['i ', 'my ', 'lived', 'story', 'journey', 'lesson', 'experience', 'authentic'],
    'program-leadership': ['leadership', 'leader', 'team', 'manager', 'program', 'execution', 'process', 'operator clarity'],
    'therapist-referral': ['therapist', 'referral', 'counselor', 'consultant', 'partner', 'trust', 'family referral'],
    'enrollment-management': ['enrollment', 'pipeline', 'conversion', 'yield', 'concierge', 'follow up', 'follow-up'],
    'ai-entrepreneurship': ['ai', 'agent', 'automation', 'system', 'intrapreneur', 'context', 'workflow', 'model'],
  };

  return keywordMap[lens].some((keyword) => text.includes(keyword));
}

function buildLensRemix(lens: WorkspaceLensId, item: { title?: string; hook?: string; priority_lane?: string; role_alignment?: string }) {
  const title = item.title ?? 'this idea';
  const hook = item.hook ?? 'the current hook';
  switch (lens) {
    case 'admissions':
      return `Reframe ${title} around student/family reality, frontline outreach, and what admissions teams learn before the rest of the institution sees it.`;
    case 'entrepreneurship':
      return `Reframe ${title} as a leverage story: show how the current role sharpens builder instincts, systems thinking, and founder-adjacent execution.`;
    case 'personal-story':
      return `Start from lived experience instead of abstraction. Use ${hook} as the lesson, then connect it to a real moment, change, or identity shift.`;
    case 'program-leadership':
      return `Translate ${title} into a leadership system takeaway. Emphasize clarity, repeatability, coaching, and what a team leader should do next.`;
    case 'therapist-referral':
      return `Angle ${title} toward trust-building with therapists, consultants, and referral partners. Show how better communication reduces friction for families.`;
    case 'enrollment-management':
      return `Turn ${title} into an enrollment-management post by linking it to pipeline quality, follow-up discipline, and a more legible student journey.`;
    case 'ai-entrepreneurship':
      return `Push ${title} further into AI-native intrapreneurship. Keep the operator tone, but make the post about systems, context, and execution leverage.`;
    default:
      return `Keep ${title} in its current lane, then tighten the post around the clearest next-step takeaway for the audience.`;
  }
}

function generatePostDraft(item: PlanCandidate, mode: WorkspaceLensId) {
  const intro = buildLensRemix(mode, item).replace(/\s+$/, '');
  const hook = item.hook ? `Hook: ${item.hook}` : '';
  return `${intro} ${hook}`.trim();
}

function labelSourceKind(kind?: string) {
  if (!kind) {
    return 'workspace';
  }
  return kind.replace(/_/g, ' ');
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
