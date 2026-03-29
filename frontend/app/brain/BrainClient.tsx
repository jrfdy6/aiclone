'use client';

import type { CSSProperties } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { getApiUrl } from '@/lib/api-client';

export type DocEntry = {
  name: string;
  path: string;
  snippet: string;
  content?: string;
  group?: string;
  updatedAt?: string;
};

export type PersonaBundleHealth = {
  bundlePath: string;
  bundleVersion?: string;
  personaId?: string;
  missingFiles: string[];
  missingFrontmatter: string[];
  todoFiles: { path: string; markers: string[] }[];
  status: 'ok' | 'error';
};

export type PersonaPack = {
  key: string;
  title: string;
  description: string;
  sections: { path: string; content: string }[];
};

export type PersonaWorkspace = {
  packs: PersonaPack[];
  pendingMarkdown: string;
  health: PersonaBundleHealth | null;
};

export type DailyBriefEntry = {
  id: string;
  brief_date: string;
  title: string;
  summary?: string | null;
  content_markdown: string;
  source: string;
  source_ref?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type BriefSourceIntelligenceCandidate = {
  title?: string | null;
  priority_lane?: string | null;
  source_kind?: string | null;
  route_reason?: string | null;
  target_file?: string | null;
};

type BriefSourceIntelligenceReviewItem = {
  trait?: string | null;
  belief_relation?: string | null;
  review_source?: string | null;
  target_file?: string | null;
};

type BriefSourceIntelligence = {
  generated_at?: string | null;
  base_generated_at?: string | null;
  source_counts?: Record<string, number>;
  source_asset_counts?: Record<string, number>;
  route_counts?: Record<string, number>;
  primary_route_counts?: Record<string, number>;
  belief_relation_counts?: Record<string, number>;
  media_post_seed_count?: number;
  belief_evidence_candidate_count?: number;
  top_media_post_seeds?: BriefSourceIntelligenceCandidate[];
  top_belief_evidence?: BriefSourceIntelligenceCandidate[];
  top_review_items?: BriefSourceIntelligenceReviewItem[];
};

export type Automation = {
  id: string;
  name: string;
  schedule: string;
  status: string;
  channel: string;
  last_run_at?: string;
  next_run_at?: string;
};

export type CaptureTelemetry = {
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
  recent_captures: CaptureSummary[];
};

type CaptureSummary = {
  id: string;
  source?: string;
  topics?: string[];
  importance?: number;
  markdown_path?: string | null;
  created_at?: string | null;
  chunk_count: number;
};

export type OpenBrainHealth = {
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

export type PersonaDeltaEntry = {
  id: string;
  capture_id?: string | null;
  persona_target: string;
  trait: string;
  notes?: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  committed_at?: string | null;
};

type WorkspaceSnapshotDocEntry = {
  name: string;
  path: string;
  snippet: string;
  content?: string;
  updatedAt?: string;
};

type WorkspaceFile = {
  group?: string;
  name: string;
  path: string;
  snippet: string;
  content?: string;
  updatedAt?: string;
};

type SourceAssetInventory = {
  items?: {
    asset_id?: string;
    title?: string;
    source_channel?: string;
    source_type?: string;
    source_path?: string;
    captured_at?: string;
  }[];
  counts?: {
    total?: number;
    long_form_media?: number;
    pending_segmentation?: number;
    feed_ready?: number;
    by_channel?: Record<string, number>;
  };
};

type LongFormRoutes = {
  assets_considered?: number;
  segments_total?: number;
  route_counts?: Record<string, number>;
  primary_route_counts?: Record<string, number>;
};

type PersonaReviewSummary = {
  counts?: {
    total?: number;
    brain_pending_review?: number;
    workspace_saved?: number;
    approved_unpromoted?: number;
    pending_promotion?: number;
    committed?: number;
  };
  belief_relation_counts?: Record<string, number>;
};

export type BrainWorkspaceSnapshot = {
  doc_entries?: WorkspaceSnapshotDocEntry[];
  workspace_files?: WorkspaceFile[];
  source_assets?: SourceAssetInventory | null;
  long_form_routes?: LongFormRoutes | null;
  persona_review_summary?: PersonaReviewSummary | null;
};

export type BrainControlPlanePayload = {
  generated_at?: string;
  automations?: Automation[];
  telemetry?: CaptureTelemetry | null;
  telemetry_health?: OpenBrainHealth | null;
  workspace_snapshot?: BrainWorkspaceSnapshot | null;
  summary?: {
    automation_count?: number;
    active_automation_count?: number;
    capture_count?: number;
    doc_count?: number;
    workspace_file_count?: number;
    pending_review_count?: number;
    workspace_saved_count?: number;
    source_asset_count?: number;
  };
};

type BrainLongFormIngestForm = {
  url: string;
  title: string;
  summary: string;
  notes: string;
  transcriptText: string;
};

type PromotionItemKind = 'talking_point' | 'framework' | 'anecdote' | 'phrase_candidate' | 'stat';
type PromotionItemProofStrength = 'none' | 'weak' | 'strong';
type PromotionItemGateDecision = 'pending' | 'allow' | 'hold' | 'block';

type PromotionItem = {
  id: string;
  kind: PromotionItemKind;
  label: string;
  content: string;
  evidence: string | null;
  targetFile: string | null;
  artifactSummary: string | null;
  artifactKind: string | null;
  artifactRef: string | null;
  deltaSummary: string | null;
  reviewInterpretation: string | null;
  capabilitySignal: string | null;
  positioningSignal: string | null;
  leverageSignal: string | null;
  proofSignal: string | null;
  proofStrength: PromotionItemProofStrength;
  gateDecision: PromotionItemGateDecision;
  gateReason: string | null;
};

type PromotionGateSummary = {
  decision: PromotionItemGateDecision;
  reason: string | null;
  proofStrength: PromotionItemProofStrength;
  alternativeTarget: string | null;
  selectedCount: number;
};

type CaptureResponsePayload = {
  capture_id: string;
  chunk_ids: string[];
  chunk_count: number;
  expires_at?: string | null;
};

type BrainPromotionResponse = {
  message?: string;
  delta: PersonaDeltaEntry;
  overlay_counts?: {
    items?: number;
    deltas?: number;
    target_files?: number;
  };
  committed_target_files?: string[];
};

type Tab = 'dashboard' | 'briefs' | 'persona' | 'automations' | 'docs';

const API_URL = getApiUrl();
const brainInputStyle: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  borderRadius: '10px',
  border: '1px solid #1f2937',
  backgroundColor: '#020617',
  color: 'white',
  padding: '10px 12px',
  fontSize: '13px',
};
const brainTextareaStyle: CSSProperties = {
  ...brainInputStyle,
  resize: 'vertical',
  minHeight: '96px',
  lineHeight: 1.5,
};

type BrainClientInitialState = {
  briefs?: DailyBriefEntry[];
  personaDeltas?: PersonaDeltaEntry[];
  controlPlane?: BrainControlPlanePayload | null;
};

export default function BrainClient({
  docs,
  personaWorkspace,
  initialState,
}: {
  docs: DocEntry[];
  personaWorkspace: PersonaWorkspace;
  initialState?: BrainClientInitialState;
}) {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [briefs, setBriefs] = useState<DailyBriefEntry[]>(initialState?.briefs ?? []);
  const [selectedBrief, setSelectedBrief] = useState<DailyBriefEntry | null>(initialState?.briefs?.[0] ?? null);
  const [briefsError, setBriefsError] = useState<string | null>(null);
  const [personaDeltas, setPersonaDeltas] = useState<PersonaDeltaEntry[]>(initialState?.personaDeltas ?? []);
  const [personaDeltasError, setPersonaDeltasError] = useState<string | null>(null);
  const [controlPlane, setControlPlane] = useState<BrainControlPlanePayload | null>(initialState?.controlPlane ?? null);
  const [automations, setAutomations] = useState<Automation[]>(initialState?.controlPlane?.automations ?? []);
  const [automationsError, setAutomationsError] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<CaptureTelemetry | null>(initialState?.controlPlane?.telemetry ?? null);
  const [telemetryHealth, setTelemetryHealth] = useState<OpenBrainHealth | null>(initialState?.controlPlane?.telemetry_health ?? null);
  const [telemetryError, setTelemetryError] = useState<string | null>(null);
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState<BrainWorkspaceSnapshot | null>(initialState?.controlPlane?.workspace_snapshot ?? null);
  const [workspaceSnapshotError, setWorkspaceSnapshotError] = useState<string | null>(null);
  const [longFormIngest, setLongFormIngest] = useState<BrainLongFormIngestForm>({
    url: '',
    title: '',
    summary: '',
    notes: '',
    transcriptText: '',
  });
  const [longFormIngestStatus, setLongFormIngestStatus] = useState<string | null>(null);
  const [longFormIngestError, setLongFormIngestError] = useState<string | null>(null);
  const [longFormSubmitting, setLongFormSubmitting] = useState(false);
  const [viewportWidth, setViewportWidth] = useState(1600);
  const mergedDocs = useMemo(() => mergeBrainDocs(docs, workspaceSnapshot), [docs, workspaceSnapshot]);
  const tabs = useMemo(
    () => [
      { key: 'dashboard', label: 'Dashboard', active: activeTab === 'dashboard', onSelect: () => setActiveTab('dashboard') },
      { key: 'briefs', label: 'Daily Briefs', active: activeTab === 'briefs', onSelect: () => setActiveTab('briefs') },
      { key: 'persona', label: 'Persona', active: activeTab === 'persona', onSelect: () => setActiveTab('persona') },
      { key: 'automations', label: 'Automations', active: activeTab === 'automations', onSelect: () => setActiveTab('automations') },
      { key: 'docs', label: 'Docs', active: activeTab === 'docs', onSelect: () => setActiveTab('docs') },
    ],
    [activeTab],
  );

  async function fetchFreshJson<T>(path: string): Promise<T> {
    const separator = path.includes('?') ? '&' : '?';
    const response = await fetch(`${API_URL}${path}${separator}brain_ts=${Date.now()}`, {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-store' },
    });
    return response.json() as Promise<T>;
  }

  async function loadData(cancelled = false) {
      const [briefsRes, personaRes, controlPlaneRes] = await Promise.allSettled([
        fetchFreshJson<DailyBriefEntry[]>('/api/briefs/?limit=50'),
        fetchFreshJson<PersonaDeltaEntry[]>('/api/persona/deltas?limit=100&view=brain_queue'),
        fetchFreshJson<BrainControlPlanePayload>('/api/brain/control-plane'),
      ]);

      if (cancelled) {
        return;
      }

      if (briefsRes.status === 'fulfilled' && Array.isArray(briefsRes.value)) {
        setBriefs(briefsRes.value);
        setSelectedBrief((current) => current ?? briefsRes.value[0] ?? null);
        setBriefsError(null);
      } else {
        console.error('Failed to load daily briefs', briefsRes.status === 'rejected' ? briefsRes.reason : briefsRes.value);
        setBriefsError('Unable to load daily briefs right now.');
      }

      if (personaRes.status === 'fulfilled' && Array.isArray(personaRes.value)) {
        setPersonaDeltas(personaRes.value);
        setPersonaDeltasError(null);
      } else {
        console.error('Failed to load persona deltas', personaRes.status === 'rejected' ? personaRes.reason : personaRes.value);
        setPersonaDeltasError('Unable to load persona deltas right now.');
      }

      if (controlPlaneRes.status === 'fulfilled') {
        const payload = controlPlaneRes.value ?? null;
        setControlPlane(payload);
        setAutomations(Array.isArray(payload?.automations) ? payload.automations : []);
        setTelemetry(payload?.telemetry ?? null);
        setTelemetryHealth(payload?.telemetry_health ?? null);
        setWorkspaceSnapshot(payload?.workspace_snapshot ?? null);
        setAutomationsError(null);
        setWorkspaceSnapshotError(null);
        setTelemetryError(null);
      } else {
        console.error('Failed to load Brain control plane', controlPlaneRes.reason);
        setAutomationsError('Unable to load automations right now.');
        setWorkspaceSnapshotError('Unable to load shared source intelligence right now.');
        setTelemetryError('Unable to load full Open Brain telemetry.');
      }
  }

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const syncWidth = () => setViewportWidth(window.innerWidth);
    syncWidth();
    window.addEventListener('resize', syncWidth);
    return () => window.removeEventListener('resize', syncWidth);
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadData();
    const interval = setInterval(loadData, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function submitLongFormIngest() {
    setLongFormIngestStatus(null);
    setLongFormIngestError(null);
    setLongFormSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/api/brain/ingest-long-form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: longFormIngest.url || null,
          title: longFormIngest.title || null,
          summary: longFormIngest.summary || null,
          notes: longFormIngest.notes || null,
          transcript_text: longFormIngest.transcriptText || null,
          run_refresh: true,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || 'Unable to register long-form source.');
      }
      setLongFormIngestStatus(`Registered ${payload.title || 'long-form source'} in Brain.`);
      setLongFormIngest({ url: '', title: '', summary: '', notes: '', transcriptText: '' });
      await loadData();
    } catch (error) {
      setLongFormIngestError(error instanceof Error ? error.message : 'Unable to register long-form source.');
    } finally {
      setLongFormSubmitting(false);
    }
  }

  return (
    <RuntimePage module="brain" tabs={tabs} maxWidth="1560px">
      {activeTab === 'dashboard' && (
        <DashboardPanel
          briefCount={briefs.length}
          docCount={mergedDocs.length}
          automationCount={automations.length}
          telemetry={telemetry}
          telemetryHealth={telemetryHealth}
          telemetryError={telemetryError}
          workspaceSnapshot={workspaceSnapshot}
          workspaceSnapshotError={workspaceSnapshotError}
          longFormIngest={longFormIngest}
          setLongFormIngest={setLongFormIngest}
          longFormIngestStatus={longFormIngestStatus}
          longFormIngestError={longFormIngestError}
          longFormSubmitting={longFormSubmitting}
          onSubmitLongFormIngest={submitLongFormIngest}
        />
      )}
      {activeTab === 'briefs' && (
        <DailyBriefsPanel briefs={briefs} selected={selectedBrief} onSelect={setSelectedBrief} error={briefsError} />
      )}
      {activeTab === 'persona' && (
        <PersonaPanel
          packs={personaWorkspace.packs}
          deltas={personaDeltas}
          error={personaDeltasError}
          viewportWidth={viewportWidth}
          refreshBrainData={() => loadData()}
          mergeUpdatedDelta={(updatedDelta) =>
            setPersonaDeltas((current) => current.map((delta) => (delta.id === updatedDelta.id ? updatedDelta : delta)))
          }
        />
      )}
      {activeTab === 'automations' && (
        <AutomationsPanel automations={automations} error={automationsError} controlPlane={controlPlane} />
      )}
      {activeTab === 'docs' && <DocsPanel docs={mergedDocs} />}
    </RuntimePage>
  );
}

function DashboardPanel({
  briefCount,
  docCount,
  automationCount,
  telemetry,
  telemetryHealth,
  telemetryError,
  workspaceSnapshot,
  workspaceSnapshotError,
  longFormIngest,
  setLongFormIngest,
  longFormIngestStatus,
  longFormIngestError,
  longFormSubmitting,
  onSubmitLongFormIngest,
}: {
  briefCount: number;
  docCount: number;
  automationCount: number;
  telemetry: CaptureTelemetry | null;
  telemetryHealth: OpenBrainHealth | null;
  telemetryError: string | null;
  workspaceSnapshot: BrainWorkspaceSnapshot | null;
  workspaceSnapshotError: string | null;
  longFormIngest: BrainLongFormIngestForm;
  setLongFormIngest: (value: BrainLongFormIngestForm) => void;
  longFormIngestStatus: string | null;
  longFormIngestError: string | null;
  longFormSubmitting: boolean;
  onSubmitLongFormIngest: () => Promise<void>;
}) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <HeroBlock briefCount={briefCount} docCount={docCount} automationCount={automationCount} />
      <BrainControlPlanePanel
        briefCount={briefCount}
        docCount={docCount}
        automationCount={automationCount}
        telemetry={telemetry}
        workspaceSnapshot={workspaceSnapshot}
        workspaceSnapshotError={workspaceSnapshotError}
      />
      <BrainLongFormIngestPanel
        value={longFormIngest}
        onChange={setLongFormIngest}
        status={longFormIngestStatus}
        error={longFormIngestError}
        submitting={longFormSubmitting}
        onSubmit={onSubmitLongFormIngest}
        workspaceSnapshot={workspaceSnapshot}
      />
      <CaptureTelemetryPanel metrics={telemetry} health={telemetryHealth} error={telemetryError} />
    </section>
  );
}

function HeroBlock({ briefCount, docCount, automationCount }: { briefCount: number; docCount: number; automationCount: number }) {
  return (
    <section
      style={{
        borderRadius: '20px',
        padding: '24px',
        background: 'linear-gradient(135deg, rgba(12,25,55,0.95), rgba(4,8,20,0.95))',
        border: '1px solid rgba(148,163,184,0.15)',
        boxShadow: '0 25px 70px rgba(3,5,15,0.55)',
        marginBottom: '24px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Brain Dashboard</p>
          <h1 style={{ color: 'white', fontSize: '32px', margin: '4px 0' }}>Knowledge + automations</h1>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Daily briefs, Open Brain telemetry, and docs in the same shell used across the reference control UI.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <HeroStat label="Briefs" value={briefCount.toString()} tone="#38bdf8" />
          <HeroStat label="Automations" value={automationCount.toString()} tone="#fbbf24" />
          <HeroStat label="Docs" value={docCount.toString()} tone="#34d399" />
        </div>
      </div>
    </section>
  );
}

function HeroStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div style={{ minWidth: '120px', borderRadius: '14px', border: '1px solid #1f2937', padding: '12px 16px', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: tone, fontSize: '22px', fontWeight: 600 }}>{value}</p>
    </div>
  );
}

function BrainControlPlanePanel({
  briefCount,
  docCount,
  automationCount,
  telemetry,
  workspaceSnapshot,
  workspaceSnapshotError,
}: {
  briefCount: number;
  docCount: number;
  automationCount: number;
  telemetry: CaptureTelemetry | null;
  workspaceSnapshot: BrainWorkspaceSnapshot | null;
  workspaceSnapshotError: string | null;
}) {
  const sourceCounts = workspaceSnapshot?.source_assets?.counts;
  const routeCounts = workspaceSnapshot?.long_form_routes?.primary_route_counts ?? workspaceSnapshot?.long_form_routes?.route_counts ?? {};
  const personaCounts = workspaceSnapshot?.persona_review_summary?.counts;
  const relationCounts = workspaceSnapshot?.persona_review_summary?.belief_relation_counts ?? {};

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Brain Control Plane</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>
            Global briefs, docs, persona state, automations, and shared source intelligence should be understandable here without bouncing back to Workspace.
          </p>
        </div>
        {workspaceSnapshotError && <p style={{ color: '#f87171', fontSize: '12px' }}>{workspaceSnapshotError}</p>}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '14px' }}>
        <TelemetryStat label="Briefs" value={briefCount} tone="#38bdf8" detail="Saved daily briefs" />
        <TelemetryStat label="Automations" value={automationCount} tone="#fbbf24" detail="Configured jobs" />
        <TelemetryStat label="Docs" value={docCount} tone="#34d399" detail="Docs visible in Brain" />
        <TelemetryStat label="Captures" value={telemetry?.captures.total ?? 0} tone="#818cf8" detail="Open Brain all time" />
        <TelemetryStat label="Pending Review" value={personaCounts?.brain_pending_review ?? 0} tone="#f97316" detail="Brain queue" />
        <TelemetryStat label="Workspace Saved" value={personaCounts?.workspace_saved ?? 0} tone="#22c55e" detail="Already approved" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        <BriefOverlayBlock
          title="Shared Source System"
          items={[
            `Source assets: ${numberMeta(sourceCounts?.total)}`,
            `Long-form media: ${numberMeta(sourceCounts?.long_form_media)}`,
            `Pending segmentation: ${numberMeta(sourceCounts?.pending_segmentation)}`,
            `Feed-ready: ${numberMeta(sourceCounts?.feed_ready)}`,
          ]}
          emptyLabel="No shared source data yet."
        />
        <BriefOverlayBlock
          title="Primary Routes"
          items={Object.entries(routeCounts).map(([key, value]) => `${humanizeSnakeCase(key)}: ${value}`)}
          emptyLabel="No route data yet."
        />
        <BriefOverlayBlock
          title="Belief Relations"
          items={Object.entries(relationCounts).map(([key, value]) => `${humanizeBeliefRelation(key)}: ${value}`)}
          emptyLabel="No relation data yet."
        />
      </div>
    </section>
  );
}

function BrainLongFormIngestPanel({
  value,
  onChange,
  status,
  error,
  submitting,
  onSubmit,
  workspaceSnapshot,
}: {
  value: BrainLongFormIngestForm;
  onChange: (value: BrainLongFormIngestForm) => void;
  status: string | null;
  error: string | null;
  submitting: boolean;
  onSubmit: () => Promise<void>;
  workspaceSnapshot: BrainWorkspaceSnapshot | null;
}) {
  const recentAssets = (workspaceSnapshot?.source_assets?.items ?? []).slice(0, 4);

  function updateField<K extends keyof BrainLongFormIngestForm>(key: K, next: BrainLongFormIngestForm[K]) {
    onChange({ ...value, [key]: next });
  }

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '14px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Brain Long-Form Intake</p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, maxWidth: '760px' }}>
            Register YouTube videos, podcasts, and other long-form sources here so Brain becomes the global entry point. These land in the shared source system first, then feed briefs, planning, and persona review.
          </p>
        </div>
        <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right' }}>
          <div>Assets visible: {numberMeta(workspaceSnapshot?.source_assets?.counts?.total)}</div>
          <div>Pending segmentation: {numberMeta(workspaceSnapshot?.source_assets?.counts?.pending_segmentation)}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 1fr)', gap: '16px' }}>
        <div style={{ display: 'grid', gap: '10px' }}>
          <label style={{ display: 'grid', gap: '6px' }}>
            <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Source URL</span>
            <input
              value={value.url}
              onChange={(event) => updateField('url', event.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              style={brainInputStyle}
            />
          </label>
          <label style={{ display: 'grid', gap: '6px' }}>
            <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Title</span>
            <input
              value={value.title}
              onChange={(event) => updateField('title', event.target.value)}
              placeholder="Optional title override"
              style={brainInputStyle}
            />
          </label>
          <label style={{ display: 'grid', gap: '6px' }}>
            <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Summary</span>
            <textarea
              value={value.summary}
              onChange={(event) => updateField('summary', event.target.value)}
              placeholder="One or two lines about why this source matters"
              rows={3}
              style={brainTextareaStyle}
            />
          </label>
          <label style={{ display: 'grid', gap: '6px' }}>
            <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Notes</span>
            <textarea
              value={value.notes}
              onChange={(event) => updateField('notes', event.target.value)}
              placeholder="Optional notes, implications, or what to look for"
              rows={4}
              style={brainTextareaStyle}
            />
          </label>
          <label style={{ display: 'grid', gap: '6px' }}>
            <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Transcript Text</span>
            <textarea
              value={value.transcriptText}
              onChange={(event) => updateField('transcriptText', event.target.value)}
              placeholder="Optional full or partial transcript if you already have it"
              rows={8}
              style={brainTextareaStyle}
            />
          </label>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => void onSubmit()}
              disabled={submitting}
              style={{
                border: '1px solid rgba(56,189,248,0.45)',
                borderRadius: '10px',
                padding: '10px 14px',
                background: submitting ? '#0f172a' : 'rgba(8,47,73,0.8)',
                color: 'white',
                cursor: submitting ? 'progress' : 'pointer',
                fontWeight: 600,
              }}
            >
              {submitting ? 'Registering…' : 'Register Long-Form Source'}
            </button>
            {status && <span style={{ color: '#22c55e', fontSize: '12px' }}>{status}</span>}
            {error && <span style={{ color: '#f87171', fontSize: '12px' }}>{error}</span>}
          </div>
        </div>

        <div style={{ display: 'grid', gap: '12px' }}>
          <BriefOverlayBlock
            title="What This Does"
            items={[
              'Writes a normalized long-form source into knowledge/ingestions/**.',
              'Refreshes the shared snapshot used by Brain, briefs, planner, and /ops.',
              'Keeps the source upstream until segmentation produces claim-sized units.',
            ]}
            emptyLabel=""
          />
          <BriefOverlayBlock
            title="Recent Source Assets"
            items={recentAssets.map((item) => `${item.title || 'Untitled'} · ${humanizeSnakeCase(item.source_channel || 'manual')}`)}
            emptyLabel="No long-form assets are visible yet."
          />
        </div>
      </div>
    </section>
  );
}

function DailyBriefsPanel({
  briefs,
  selected,
  onSelect,
  error,
}: {
  briefs: DailyBriefEntry[];
  selected: DailyBriefEntry | null;
  onSelect: (entry: DailyBriefEntry) => void;
  error: string | null;
}) {
  const selectedSourceIntelligence = selected ? briefSourceIntelligence(selected) : null;
  return (
    <section style={{ display: 'flex', gap: '18px', borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', minHeight: '520px' }}>
      <div style={{ width: '280px', borderRight: '1px solid #0f172a', paddingRight: '14px', maxHeight: '480px', overflowY: 'auto' }}>
        {error && <p style={{ color: '#f87171' }}>{error}</p>}
        {!error && briefs.length === 0 && <p style={{ color: '#475569' }}>No daily briefs saved yet.</p>}
        {briefs.map((entry) => (
          <button
            key={entry.id}
            onClick={() => onSelect(entry)}
            style={{
              width: '100%',
              textAlign: 'left',
              marginBottom: '8px',
              padding: '10px',
              borderRadius: '12px',
              border: entry === selected ? '1px solid #38bdf8' : '1px solid transparent',
              backgroundColor: entry === selected ? '#0f172a' : 'transparent',
              color: 'white',
              cursor: 'pointer',
            }}
          >
            <p style={{ fontSize: '12px', color: '#94a3b8' }}>{entry.brief_date}</p>
            <p style={{ fontSize: '14px', fontWeight: 600 }}>{entry.title}</p>
          </button>
        ))}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {selected ? (
          <div style={{ display: 'grid', gap: '14px' }}>
            <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '4px' }}>{selected.brief_date}</p>
            <div>
              <h2 style={{ color: 'white', fontSize: '26px', marginBottom: '8px' }}>{selected.title}</h2>
              {selected.summary && <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '12px' }}>{selected.summary}</p>}
            </div>
            {selectedSourceIntelligence && <BriefSourceIntelligencePanel overlay={selectedSourceIntelligence} />}
            <div
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '16px',
                color: '#cbd5f5',
                fontSize: '14px',
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
              }}
            >
              <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 10px' }}>Saved Brief</p>
              {selected.content_markdown}
            </div>
          </div>
        ) : (
          <p style={{ color: '#475569' }}>Select a brief to read the saved markdown.</p>
        )}
      </div>
    </section>
  );
}

function BriefSourceIntelligencePanel({ overlay }: { overlay: BriefSourceIntelligence }) {
  const sourceCounts = overlay.source_counts ?? {};
  const assetCounts = overlay.source_asset_counts ?? {};
  const routeCounts = overlay.route_counts ?? {};
  const relationCounts = overlay.belief_relation_counts ?? {};
  const mediaSeeds = overlay.top_media_post_seeds ?? [];
  const beliefEvidence = overlay.top_belief_evidence ?? [];
  const reviewItems = overlay.top_review_items ?? [];

  return (
    <section
      style={{
        borderRadius: '14px',
        border: '1px solid #1f2937',
        backgroundColor: '#020617',
        padding: '16px',
        marginBottom: '12px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', marginBottom: '10px', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Live Source Intelligence</p>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, maxWidth: '760px' }}>
            This is the current shared planning overlay from the source system, not a second brief-only inference path.
          </p>
        </div>
        <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right' }}>
          <div>{overlay.generated_at ? formatTimestamp(new Date(overlay.generated_at)) : 'No live timestamp'}</div>
          {overlay.base_generated_at && <div>Base plan {overlay.base_generated_at}</div>}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
        <InlineBadge label={`media ${numberMeta(sourceCounts.media)}`} tone="#38bdf8" />
        <InlineBadge label={`belief ${numberMeta(sourceCounts.belief_evidence)}`} tone="#22c55e" />
        <InlineBadge label={`assets ${numberMeta(assetCounts.total)}`} tone="#818cf8" />
        <InlineBadge label={`segments ${numberMeta(routeCounts.post_seed)}/${numberMeta(routeCounts.belief_evidence)}`} tone="#f59e0b" />
        <InlineBadge label={`relations ${Object.keys(relationCounts).length}`} tone="#64748b" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '12px' }}>
        <PriorityFocusCard
          title="What deserves a post"
          description={mediaSeeds[0] ? compactBriefCandidate(mediaSeeds[0]) : 'No strong media-derived post seed has surfaced yet.'}
          tone="#38bdf8"
        />
        <PriorityFocusCard
          title="What shapes worldview"
          description={beliefEvidence[0] ? compactBriefCandidate(beliefEvidence[0]) : 'No strong belief-evidence candidate is visible right now.'}
          tone="#22c55e"
        />
        <PriorityFocusCard
          title="What needs judgment"
          description={reviewItems[0] ? compactReviewItem(reviewItems[0]) : 'No worldview review item is at the top of the queue right now.'}
          tone="#818cf8"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        <BriefOverlayBlock
          title="Route Mix"
          items={Object.entries(routeCounts).map(([key, value]) => `${humanizeSnakeCase(key)}: ${value}`)}
          emptyLabel="No route counts yet."
        />
        <BriefOverlayBlock
          title="Belief Relations"
          items={Object.entries(relationCounts).map(([key, value]) => `${humanizeBeliefRelation(key)}: ${value}`)}
          emptyLabel="No relation counts yet."
        />
        <BriefOverlayBlock
          title="Top Media Seeds"
          items={mediaSeeds.map((item) => compactBriefCandidate(item))}
          emptyLabel="No live media seeds yet."
        />
        <BriefOverlayBlock
          title="Top Belief Evidence"
          items={beliefEvidence.map((item) => compactBriefCandidate(item))}
          emptyLabel="No live belief evidence yet."
        />
      </div>

      {reviewItems.length > 0 && (
        <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #1f2937' }}>
          <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Recent worldview review items</p>
          <div style={{ display: 'grid', gap: '8px' }}>
            {reviewItems.map((item, index) => (
              <div key={`${item.trait ?? 'review'}-${index}`} style={{ borderRadius: '10px', border: '1px solid #1f2937', padding: '10px', backgroundColor: '#030712' }}>
                <p style={{ color: '#e2e8f0', fontSize: '13px', lineHeight: 1.5, marginBottom: '6px' }}>{item.trait ?? 'Untitled review item'}</p>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <InlineBadge label={humanizeBeliefRelation(item.belief_relation ?? null)} tone="#22c55e" />
                  <InlineBadge label={humanizeReviewSource(item.review_source ?? null)} tone="#64748b" />
                  {item.target_file && <InlineBadge label={item.target_file} tone="#818cf8" />}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function BriefOverlayBlock({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel: string }) {
  return (
    <div style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#030712', padding: '12px' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{title}</p>
      {items.length === 0 ? (
        <p style={{ color: '#475569', fontSize: '12px' }}>{emptyLabel}</p>
      ) : (
        <div style={{ display: 'grid', gap: '6px' }}>
          {items.map((item, index) => (
            <p key={`${title}-${index}`} style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.45 }}>
              {item}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function PriorityFocusCard({ title, description, tone }: { title: string; description: string; tone: string }) {
  return (
    <div style={{ borderRadius: '12px', border: `1px solid ${tone}33`, backgroundColor: `${tone}10`, padding: '12px' }}>
      <p style={{ color: tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{title}</p>
      <p style={{ color: '#dbe7ff', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>{description}</p>
    </div>
  );
}

function StepCallout({ step, title, description }: { step: string; title: string; description: string }) {
  return (
    <div style={{ borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '12px' }}>
      <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>
        Step {step}
      </p>
      <p style={{ color: 'white', fontSize: '14px', fontWeight: 600, margin: '0 0 6px' }}>{title}</p>
      <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>{description}</p>
    </div>
  );
}

function PersonaPanel({
  packs,
  deltas,
  error,
  viewportWidth,
  refreshBrainData,
  mergeUpdatedDelta,
}: {
  packs: PersonaPack[];
  deltas: PersonaDeltaEntry[];
  error: string | null;
  viewportWidth: number;
  refreshBrainData: () => Promise<void>;
  mergeUpdatedDelta: (updatedDelta: PersonaDeltaEntry) => void;
}) {
  const [completedDeltaIds, setCompletedDeltaIds] = useState<string[]>([]);
  const [showMutedActive, setShowMutedActive] = useState(false);
  const [lifecycleView, setLifecycleView] = useState<'pending_promotion' | 'workspace_saved' | 'committed' | 'resolved'>('pending_promotion');
  const visibleDeltas = useMemo(() => deltas.filter((delta) => !completedDeltaIds.includes(delta.id)), [completedDeltaIds, deltas]);
  const activeReviewDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'brain_pending_review'), [visibleDeltas]);
  const workspaceSavedDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'workspace_saved'), [visibleDeltas]);
  const pendingPromotionDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'pending_promotion'), [visibleDeltas]);
  const committedDeltas = useMemo(() => visibleDeltas.filter((delta) => personaDeltaStage(delta) === 'committed'), [visibleDeltas]);
  const resolvedHistoryDeltas = useMemo(
    () =>
      visibleDeltas.filter((delta) => {
        const stage = personaDeltaStage(delta);
        return stage === 'resolved' || stage === 'approved_unpromoted' || stage === 'reviewed';
      }),
    [visibleDeltas],
  );
  const scoredActiveReviewDeltas = useMemo(
    () =>
      activeReviewDeltas
        .map((delta) => {
          const promotionCandidateCount = promotionSignalCount(delta.metadata);
          const muted = shouldMuteActivePersonaDelta(delta, promotionCandidateCount);
          return {
            delta,
            muted,
            promotionCandidateCount,
            promotionReady: isPromotionReady(delta.status, delta.metadata),
            score: personaDeltaPriorityScore(delta, promotionCandidateCount, muted),
          };
        })
        .sort((left, right) => {
          if (right.score !== left.score) return right.score - left.score;
          return new Date(right.delta.created_at).getTime() - new Date(left.delta.created_at).getTime();
        }),
    [activeReviewDeltas],
  );
  const primaryActiveReviewDeltas = useMemo(() => scoredActiveReviewDeltas.filter((item) => !item.muted), [scoredActiveReviewDeltas]);
  const mutedActiveReviewDeltas = useMemo(() => scoredActiveReviewDeltas.filter((item) => item.muted), [scoredActiveReviewDeltas]);
  const visibleActiveReviewDeltas = useMemo(() => {
    if (primaryActiveReviewDeltas.length === 0) {
      return mutedActiveReviewDeltas;
    }
    return showMutedActive ? [...primaryActiveReviewDeltas, ...mutedActiveReviewDeltas] : primaryActiveReviewDeltas;
  }, [mutedActiveReviewDeltas, primaryActiveReviewDeltas, showMutedActive]);
  const reviewQueue = useMemo(() => visibleActiveReviewDeltas.map((item) => item.delta), [visibleActiveReviewDeltas]);
  const [selectedDeltaId, setSelectedDeltaId] = useState<string>(reviewQueue[0]?.id ?? '');
  const [reflectionText, setReflectionText] = useState('');
  const [reflectionState, setReflectionState] = useState<{ tone: 'idle' | 'success' | 'error'; message: string }>({
    tone: 'idle',
    message: '',
  });
  const [isSavingReflection, setIsSavingReflection] = useState(false);
  const [promotionState, setPromotionState] = useState<{ tone: 'idle' | 'success' | 'error'; message: string }>({
    tone: 'idle',
    message: '',
  });
  const [promotingDeltaId, setPromotingDeltaId] = useState<string | null>(null);
  const [recentlyQueuedDeltaId, setRecentlyQueuedDeltaId] = useState<string | null>(null);
  const selectedDelta = useMemo(
    () => reviewQueue.find((delta) => delta.id === selectedDeltaId) ?? reviewQueue[0] ?? null,
    [reviewQueue, selectedDeltaId],
  );
  const selectedScoredDelta = useMemo(
    () => scoredActiveReviewDeltas.find((item) => item.delta.id === selectedDelta?.id) ?? null,
    [scoredActiveReviewDeltas, selectedDelta],
  );
  const targetFile = selectedDelta ? metadataText(selectedDelta.metadata, 'target_file') : null;
  const linkedPack = useMemo(() => findPackBySection(packs, targetFile) ?? packs[0] ?? null, [packs, targetFile]);
  const targetSection = useMemo(() => findPackSection(packs, targetFile), [packs, targetFile]);
  const activeContext = targetSection?.content ?? linkedPack?.sections[0]?.content ?? null;
  const activeContextPath = targetSection?.path ?? linkedPack?.sections[0]?.path ?? null;
  const selectableItems = useMemo(() => buildPromotionItems(selectedDelta, targetFile), [selectedDelta, targetFile]);
  const reviewHeadline = selectedDelta ? buildReviewHeadline(selectedDelta, targetFile) : 'No persona review items queued.';
  const reviewReason = selectedDelta ? buildReviewReason(selectedDelta, targetFile, activeContextPath) : 'There is no pending persona item to review right now.';
  const reviewAsk = selectedDelta ? buildReviewAsk(selectedDelta, targetFile) : 'You can still save a general thought to memory if you want to capture something new.';
  const evidenceLabel =
    metadataText(selectedDelta?.metadata, 'evidence_source') ?? (selectedDelta?.capture_id ? `capture ${selectedDelta.capture_id}` : 'Not linked yet');
  const statusLabel = selectedDelta?.status ?? 'pending';
  const savedResponseKind = metadataText(selectedDelta?.metadata, 'owner_response_kind');
  const savedResponseExcerpt = metadataText(selectedDelta?.metadata, 'owner_response_excerpt');
  const [selectedPromotionItemIds, setSelectedPromotionItemIds] = useState<string[]>([]);
  const [selectedResponseKind, setSelectedResponseKind] = useState<'agree' | 'disagree' | 'nuance' | 'story' | 'language'>('nuance');
  const selectedPromotionItems = useMemo(
    () => selectableItems.filter((item) => selectedPromotionItemIds.includes(item.id)),
    [selectableItems, selectedPromotionItemIds],
  );
  const selectedPromotionGate = useMemo(
    () => summarizePromotionItems(selectedPromotionItems, targetFile),
    [selectedPromotionItems, targetFile],
  );
  const pendingCount = primaryActiveReviewDeltas.length;
  const totalPendingCount = scoredActiveReviewDeltas.length;
  const mutedCount = mutedActiveReviewDeltas.length;
  const promotionReadyCount = scoredActiveReviewDeltas.filter((item) => item.promotionReady).length;
  const lifecycleGroups = useMemo(
    () => [
      {
        key: 'workspace_saved',
        title: 'Workspace Saved',
        description: 'Approved from Workspace and already saved. No second approval needed here.',
        count: workspaceSavedDeltas.length,
        items: workspaceSavedDeltas,
        tone: '#22c55e',
      },
      {
        key: 'pending_promotion',
        title: 'Queued For Promotion',
        description: 'Reviewed in Brain and holding selected canonical items for later promotion.',
        count: pendingPromotionDeltas.length,
        items: pendingPromotionDeltas,
        tone: '#38bdf8',
      },
      {
        key: 'committed',
        title: 'Committed',
        description: 'Already written into canonical persona files.',
        count: committedDeltas.length,
        items: committedDeltas,
        tone: '#818cf8',
      },
      {
        key: 'resolved',
        title: 'Resolved / Replaced',
        description: 'Historical items that were handled, superseded, or intentionally cleared.',
        count: resolvedHistoryDeltas.length,
        items: resolvedHistoryDeltas,
        tone: '#64748b',
      },
    ],
    [committedDeltas, pendingPromotionDeltas, resolvedHistoryDeltas, workspaceSavedDeltas],
  );
  const activeLifecycleGroup = useMemo(
    () => lifecycleGroups.find((group) => group.key === lifecycleView) ?? lifecycleGroups[0],
    [lifecycleGroups, lifecycleView],
  );
  const stackPersonaShell = viewportWidth < 1220;
  const stackPersonaDetail = viewportWidth < 1480;
  const usePinnedPersonaViewport = viewportWidth >= 1220;
  const personaViewportHeight = usePinnedPersonaViewport ? 'calc(100vh - 185px)' : 'auto';

  useEffect(() => {
    if (!selectedDelta && reviewQueue[0]) {
      setSelectedDeltaId(reviewQueue[0].id);
      return;
    }
    if (reviewQueue.length === 0 && selectedDeltaId) {
      setSelectedDeltaId('');
    }
  }, [reviewQueue, selectedDelta, selectedDeltaId]);

  useEffect(() => {
    const existingItems = readPromotionItemsFromMetadata(selectedDelta?.metadata);
    const existingIds = existingItems.map((item) => item.id);
    const availableIds = new Set(selectableItems.map((item) => item.id));
    setSelectedPromotionItemIds(existingIds.filter((itemId) => availableIds.has(itemId)));
  }, [selectableItems, selectedDelta?.id, selectedDelta?.metadata]);

  useEffect(() => {
    const existing = metadataText(selectedDelta?.metadata, 'owner_response_kind');
    if (existing === 'agree' || existing === 'disagree' || existing === 'nuance' || existing === 'story' || existing === 'language') {
      setSelectedResponseKind(existing);
      return;
    }
    setSelectedResponseKind('nuance');
  }, [selectedDelta?.id, selectedDelta?.metadata]);

  useEffect(() => {
    setReflectionText(metadataText(selectedDelta?.metadata, 'owner_response_excerpt') ?? '');
    setReflectionState({ tone: 'idle', message: '' });
  }, [selectedDelta?.id, selectedDelta?.metadata]);

  async function commitPromotion(delta: PersonaDeltaEntry) {
    const gateSummary = summarizePromotionItems(readPromotionItemsFromMetadata(delta.metadata), metadataText(delta.metadata, 'target_file'));
    if (gateSummary.decision !== 'allow') {
      setPromotionState({
        tone: 'error',
        message:
          gateSummary.decision === 'block'
            ? gateSummary.reason || 'This queued item is blocked from canon until it has a real artifact/output anchor.'
            : gateSummary.reason || 'This queued item is held until the proof is stronger.',
      });
      return;
    }
    setPromotionState({ tone: 'idle', message: '' });
    setPromotingDeltaId(delta.id);
    try {
      const response = await fetch(`${API_URL}/api/brain/persona-promote/${delta.id}`, {
        method: 'POST',
        headers: { 'Cache-Control': 'no-store' },
        cache: 'no-store',
      });
      const payload = (await response.json()) as BrainPromotionResponse | { detail?: string };
      if (!response.ok) {
        throw new Error((payload as { detail?: string }).detail || `Promotion failed with ${response.status}`);
      }
      mergeUpdatedDelta((payload as BrainPromotionResponse).delta);
      await refreshBrainData();
      setPromotionState({
        tone: 'success',
        message: `${(payload as BrainPromotionResponse).message || 'Promotion committed.'} Target files: ${(((payload as BrainPromotionResponse).committed_target_files || []) as string[]).join(', ') || 'n/a'}.`,
      });
      if (selectedDeltaId === delta.id) {
        setSelectedDeltaId(reviewQueue[0]?.id ?? '');
      }
    } catch (error) {
      setPromotionState({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Unable to commit this promotion right now.',
      });
    } finally {
      setPromotingDeltaId(null);
    }
  }

  function queueTemplate(kind: 'agree' | 'disagree' | 'nuance' | 'story' | 'language') {
    if (!selectedDelta) {
      return;
    }
    setSelectedResponseKind(kind);
    const prefix =
      kind === 'agree'
        ? `What I agree with about "${selectedDelta.trait}":\n- `
        : kind === 'disagree'
        ? `What I disagree with about "${selectedDelta.trait}":\n- `
        : kind === 'nuance'
        ? `Nuance I want preserved for "${selectedDelta.trait}":\n- `
        : kind === 'story'
        ? `Personal story or example that should shape "${selectedDelta.trait}":\n- `
        : `Language and wording I prefer for "${selectedDelta.trait}":\n- `;
    setReflectionText((current) => (current.trim().length > 0 ? current : prefix));
    setReflectionState({ tone: 'idle', message: '' });
  }

  async function saveReflection(mode: 'reviewed' | 'approved' = 'reviewed') {
    const trimmedReflection = reflectionText.trim();
    const keepSelectableSourceOpen = mode === 'reviewed' && selectableItems.length > 0;
    if (mode === 'approved' && selectedPromotionItems.length === 0) {
      setReflectionState({ tone: 'error', message: 'Select at least one extracted item before queuing promotion.' });
      return;
    }
    if (!trimmedReflection && mode === 'reviewed') {
      setReflectionState({ tone: 'error', message: 'Add a thought before saving it to memory.' });
      return;
    }
    if (!trimmedReflection && mode === 'approved') {
      setReflectionState({ tone: 'error', message: 'Add a short note so the selected items have your reasoning attached.' });
      return;
    }

    setIsSavingReflection(true);
    setReflectionState({ tone: 'idle', message: '' });
    try {
      const payload = {
        text: buildReflectionCaptureText({
          delta: selectedDelta,
          reflectionText: trimmedReflection,
          targetFile,
          sectionContent: targetSection?.content ?? null,
          selectedItems: selectedPromotionItems,
        }),
        source: 'persona_reflection',
        topics: buildReflectionTopics(selectedDelta, targetFile),
        importance: 3,
        metadata: {
          capture_kind: 'persona_reflection',
          origin: 'brain.persona.ui',
          owner_response_kind: selectedResponseKind,
          linked_delta_id: selectedDelta?.id ?? null,
          linked_capture_id: selectedDelta?.capture_id ?? null,
          persona_target: selectedDelta?.persona_target ?? null,
          target_file: targetFile,
          trait: selectedDelta?.trait ?? null,
          reference_pack: linkedPack?.key ?? null,
          input_mode: 'text',
          selected_promotion_items: selectedPromotionItems,
        },
      };

      const response = await fetch(`${API_URL}/api/capture/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Capture save failed with ${response.status}`);
      }
      const result = (await response.json()) as CaptureResponsePayload;
      if (selectedDelta) {
        const reviewPayload = {
          mode,
          response_kind: selectedResponseKind,
          resolution_capture_id: result.capture_id,
          reflection_excerpt: trimmedReflection.slice(0, 4000),
          selected_promotion_items: selectedPromotionItems,
        };
        const reviewResponse = await fetch(`${API_URL}/api/brain/persona-review/${selectedDelta.id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(reviewPayload),
        });
        if (!reviewResponse.ok) {
          const detail = await reviewResponse.text();
          throw new Error(detail || `Persona review update failed with ${reviewResponse.status}`);
        }
        const updatedDelta = (await reviewResponse.json()) as PersonaDeltaEntry;
        mergeUpdatedDelta(updatedDelta);
        if (mode === 'approved') {
          setRecentlyQueuedDeltaId(updatedDelta.id);
          setLifecycleView('pending_promotion');
          setPromotionState({
            tone: 'success',
            message:
              selectedPromotionGate.decision === 'allow'
                ? `Queued for promotion: ${selectedPromotionItems.length} selected item${selectedPromotionItems.length === 1 ? '' : 's'} from "${truncateText(updatedDelta.trait, 72)}". Ready for canon commit.`
                : `Queued for promotion: ${selectedPromotionItems.length} selected item${selectedPromotionItems.length === 1 ? '' : 's'} from "${truncateText(updatedDelta.trait, 72)}". ${selectedPromotionGate.reason || 'This still needs stronger artifact-backed proof before it can be committed.'}`,
          });
        } else {
          setPromotionState({ tone: 'idle', message: '' });
          setRecentlyQueuedDeltaId(null);
        }
      }
      const nextQueue = selectedDelta ? reviewQueue.filter((delta) => delta.id !== selectedDelta.id) : reviewQueue;
      await refreshBrainData();
      if (selectedDelta && !keepSelectableSourceOpen) {
        setCompletedDeltaIds((current) => (current.includes(selectedDelta.id) ? current : [...current, selectedDelta.id]));
      }
      setSelectedDeltaId(keepSelectableSourceOpen ? selectedDelta?.id ?? '' : nextQueue[0]?.id ?? '');
      setReflectionText('');
      setReflectionState({
        tone: 'success',
        message: keepSelectableSourceOpen
          ? `Saved to Open Brain as capture ${result.capture_id}. This source stays open so you can select canonical items when ready.`
          : nextQueue[0]
          ? mode === 'approved'
            ? `Saved to Open Brain as capture ${result.capture_id} and queued ${selectedPromotionItems.length} selected item${selectedPromotionItems.length === 1 ? '' : 's'} for promotion. Moving to the next review item.`
            : `Saved to Open Brain as capture ${result.capture_id}. Moving to the next review item.`
          : mode === 'approved'
          ? `Saved to Open Brain as capture ${result.capture_id} and queued ${selectedPromotionItems.length} selected item${selectedPromotionItems.length === 1 ? '' : 's'} for promotion. You are done for now.`
          : `Saved to Open Brain as capture ${result.capture_id}. You are done for now.`,
      });
    } catch (saveError) {
      setReflectionState({
        tone: 'error',
        message: saveError instanceof Error ? saveError.message : 'Unable to save reflection right now.',
      });
    } finally {
      setIsSavingReflection(false);
    }
  }

  return (
    <section
      style={{
        display: 'grid',
        gap: '16px',
        height: personaViewportHeight,
        minHeight: 0,
        gridTemplateRows: usePinnedPersonaViewport ? 'minmax(0, 1.2fr) minmax(0, 0.92fr)' : 'none',
      }}
    >
      <section
        style={{
          borderRadius: '18px',
          border: '1px solid #1f2937',
          backgroundColor: '#050b19',
          padding: '18px',
          display: 'grid',
          gap: '12px',
          alignItems: 'start',
          minHeight: 0,
          overflow: 'hidden',
          gridTemplateRows: usePinnedPersonaViewport ? 'auto auto auto minmax(0, 1fr) auto' : 'none',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ maxWidth: '760px' }}>
            <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Active Review</p>
            <h2 style={{ color: 'white', fontSize: '28px', margin: '4px 0 8px' }}>{reviewHeadline}</h2>
            <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6 }}>
              {selectedDelta
                ? `${pendingCount} primary review item${pendingCount === 1 ? '' : 's'} remaining${mutedCount > 0 ? `, plus ${mutedCount} muted long-form item${mutedCount === 1 ? '' : 's'}` : ''}.`
                : 'No pending reviews right now.'}
            </p>
          </div>
          <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right', maxWidth: '360px' }}>
            Workspace approvals already count as saved. Brain is the place to review unresolved items, add nuance, and queue canonical promotion without auto-rewriting the bundle.
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: stackPersonaShell ? 'minmax(0, 1fr)' : 'repeat(3, minmax(0, 1fr))', gap: '8px' }}>
          <StepCallout step="1" title="Choose item" description="Pick one review item from the left rail." />
          <StepCallout step="2" title="Review candidate" description="Read the proposed source material and decide what you actually think." />
          <StepCallout step="3" title="Save your take" description="Record agreement, disagreement, nuance, story, or wording. Queue promotion only if fragments deserve canon." />
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <ReviewMetaChip label="Active" value={String(totalPendingCount)} tone="#38bdf8" />
          <ReviewMetaChip label="Promotion Ready" value={String(promotionReadyCount)} tone="#f59e0b" />
          <ReviewMetaChip label="Queued" value={String(pendingPromotionDeltas.length)} tone="#f59e0b" />
          <ReviewMetaChip label="History" value={String(resolvedHistoryDeltas.length + workspaceSavedDeltas.length + committedDeltas.length)} tone="#64748b" />
        </div>

        {selectedDelta ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: stackPersonaShell ? 'minmax(0, 1fr)' : '340px minmax(0, 1fr)',
              gap: '14px',
              alignItems: 'start',
              minHeight: 0,
              overflow: 'hidden',
            }}
          >
            <aside
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '14px',
                display: 'grid',
                gap: '12px',
                alignSelf: 'stretch',
                minHeight: 0,
                overflow: 'hidden',
                gridTemplateRows: 'auto auto minmax(0, 1fr)',
              }}
            >
              <div>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>Review now</p>
                <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                  Focus on the strongest unresolved items first. Muted long-form fragments stay out of the way unless you choose to inspect them.
                </p>
              </div>
              {primaryActiveReviewDeltas.length > 0 && mutedActiveReviewDeltas.length > 0 && (
                <div
                  style={{
                    display: 'grid',
                    gap: '8px',
                    padding: '10px 12px',
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#010617',
                  }}
                >
                  <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                    {mutedCount} lower-confidence long-form item{mutedCount === 1 ? '' : 's'} muted by default.
                  </p>
                  <button
                    onClick={() => setShowMutedActive((current) => !current)}
                    style={{
                      borderRadius: '999px',
                      border: '1px solid #334155',
                      backgroundColor: showMutedActive ? '#0f172a' : '#020617',
                      color: '#cbd5f5',
                      padding: '8px 12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      justifySelf: 'start',
                    }}
                  >
                    {showMutedActive ? `Hide muted (${mutedCount})` : `Show muted (${mutedCount})`}
                  </button>
                </div>
              )}
              <div style={{ minHeight: 0, overflowY: 'auto', display: 'grid', gap: '10px', paddingRight: '2px' }}>
                {visibleActiveReviewDeltas.map(({ delta, muted, promotionReady }) => {
                  const isActive = delta.id === (selectedDelta?.id ?? '');
                  return (
                    <button
                      key={delta.id}
                      onClick={() => setSelectedDeltaId(delta.id)}
                      style={{
                        textAlign: 'left',
                        borderRadius: '14px',
                        border: `1px solid ${isActive ? '#38bdf8' : '#1f2937'}`,
                        backgroundColor: isActive ? '#082f49' : '#020617',
                        padding: '12px',
                        cursor: 'pointer',
                      }}
                    >
                      <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600, marginBottom: '6px', lineHeight: 1.45 }}>{truncateText(delta.trait, 110)}</p>
                      <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>{metadataText(delta.metadata, 'target_file') ?? 'Target file not assigned'}</p>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                        {isActive && <InlineBadge label="selected" tone="#38bdf8" />}
                        <InlineBadge label={humanizeBeliefRelation(metadataText(delta.metadata, 'belief_relation'))} tone="#22c55e" />
                        {promotionReady && <InlineBadge label="promotion-ready" tone="#f59e0b" />}
                        {muted && <InlineBadge label="muted" tone="#64748b" />}
                      </div>
                      <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {formatTimestamp(new Date(delta.created_at))}
                      </p>
                    </button>
                  );
                })}
              </div>
            </aside>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: stackPersonaDetail ? 'minmax(0, 1fr)' : 'minmax(0, 1.08fr) minmax(420px, 0.92fr)',
                gap: '14px',
                alignItems: 'start',
                minHeight: 0,
                overflow: 'hidden',
              }}
            >
            <section
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '16px',
                display: 'grid',
                gap: '12px',
                alignSelf: 'stretch',
                minWidth: 0,
                minHeight: 0,
                overflow: 'hidden',
                gridTemplateRows: 'auto auto auto minmax(0, 1fr)',
              }}
            >
              <div>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>What you are reviewing</p>
                <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.65, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{reviewReason}</p>
              </div>

              <div style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.6, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                <span>{targetFile ?? 'Target file not assigned'}</span>
                <span style={{ margin: '0 8px' }}>·</span>
                <span>{evidenceLabel}</span>
                <span style={{ margin: '0 8px' }}>·</span>
                <span>{statusLabel}</span>
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <InlineBadge
                  label={selectedScoredDelta?.promotionReady ? 'Promotion-ready path open' : 'Needs review before promotion'}
                  tone={selectedScoredDelta?.promotionReady ? '#f59e0b' : '#38bdf8'}
                />
                <InlineBadge label={humanizeBeliefRelation(metadataText(selectedDelta.metadata, 'belief_relation'))} tone="#22c55e" />
                <InlineBadge
                  label={`${selectableItems.length} canonical candidate${selectableItems.length === 1 ? '' : 's'}`}
                  tone={selectableItems.length > 0 ? '#818cf8' : '#64748b'}
                />
                {selectedScoredDelta?.muted && <InlineBadge label="Muted long-form item" tone="#64748b" />}
                {selectedScoredDelta && <InlineBadge label={`Priority ${selectedScoredDelta.score}`} tone="#22c55e" />}
              </div>

              <div style={{ minHeight: 0, overflowY: 'auto', paddingRight: '4px' }}>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Proposed source material</p>
                <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.7, whiteSpace: 'pre-wrap', marginBottom: '16px' }}>
                  {selectedDelta.notes || 'No candidate notes were attached to this review item.'}
                </p>
                {selectableItems.length > 0 && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'baseline', marginBottom: '10px', flexWrap: 'wrap' }}>
                      <p style={{ color: '#818cf8', fontSize: '13px', fontWeight: 700, margin: 0 }}>
                        Canonical fragments
                      </p>
                      <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>
                        {selectedPromotionItems.length} selected
                      </p>
                    </div>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: viewportWidth >= 1180 ? 'repeat(2, minmax(0, 1fr))' : 'minmax(0, 1fr)',
                        gap: '10px',
                      }}
                    >
                      {selectableItems.map((item) => {
                        const checked = selectedPromotionItemIds.includes(item.id);
                        return (
                          <label
                            key={item.id}
                            style={{
                              width: '100%',
                              display: 'block',
                              borderRadius: '12px',
                              border: `1px solid ${checked ? '#38bdf8' : '#1f2937'}`,
                              backgroundColor: checked ? '#082f49' : '#020617',
                              padding: '10px 12px',
                              cursor: 'pointer',
                              boxSizing: 'border-box',
                            }}
                          >
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  setSelectedPromotionItemIds((current) =>
                                    current.includes(item.id) ? current.filter((entry) => entry !== item.id) : [...current, item.id],
                                  );
                                  if (reflectionState.tone !== 'idle') {
                                    setReflectionState({ tone: 'idle', message: '' });
                                  }
                                }}
                                style={{
                                  width: '16px',
                                  height: '16px',
                                  marginTop: '2px',
                                  accentColor: '#38bdf8',
                                  cursor: 'pointer',
                                }}
                              />
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', marginBottom: '6px', flexWrap: 'wrap' }}>
                                  <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600, overflowWrap: 'anywhere', wordBreak: 'break-word', margin: 0 }}>
                                    {item.label}
                                  </p>
                                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                    <InlineBadge label={humanizePromotionKind(item.kind)} tone="#64748b" />
                                    <InlineBadge label={humanizeGateDecision(resolvePromotionGate(item, targetFile).decision)} tone={gateDecisionTone(resolvePromotionGate(item, targetFile).decision)} />
                                    <InlineBadge label={`proof ${item.proofStrength}`} tone={proofStrengthTone(item.proofStrength)} />
                                  </div>
                                </div>
                                <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.5, overflowWrap: 'anywhere', wordBreak: 'break-word', margin: 0 }}>{item.content}</p>
                                {item.artifactSummary && (
                                  <p style={{ color: '#94a3b8', fontSize: '12px', margin: '6px 0 0', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                                    Artifact: {item.artifactSummary}
                                  </p>
                                )}
                                {item.evidence && <p style={{ color: '#64748b', fontSize: '12px', margin: '6px 0 0', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>Evidence: {item.evidence}</p>}
                                {resolvePromotionGate(item, targetFile).reason && (
                                  <p style={{ color: gateDecisionTone(resolvePromotionGate(item, targetFile).decision), fontSize: '12px', margin: '6px 0 0', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                                    {resolvePromotionGate(item, targetFile).reason}
                                  </p>
                                )}
                              </div>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}
                <details>
                  <summary style={{ color: '#818cf8', cursor: 'pointer', fontSize: '13px', fontWeight: 600, marginBottom: '12px' }}>
                    Current canonical context
                  </summary>
                  <div style={{ marginTop: '12px' }}>
                    {activeContext ? (
                      <>
                        <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{activeContextPath ?? 'Canonical bundle excerpt'}</p>
                        <pre style={{ margin: 0, color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, whiteSpace: 'pre-wrap', fontFamily: 'inherit', overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                          {truncateText(activeContext, 2200)}
                        </pre>
                      </>
                    ) : (
                      <p style={{ color: '#475569', fontSize: '13px', lineHeight: 1.55 }}>
                        There is no canonical excerpt attached yet. Use your response to say where this belongs and how it should be phrased.
                      </p>
                    )}
                  </div>
                </details>
              </div>
            </section>

            <section
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '16px',
                display: 'grid',
                gap: '12px',
                alignSelf: 'stretch',
                minWidth: 0,
                minHeight: 0,
                overflow: 'hidden',
                gridTemplateRows: 'auto auto auto auto minmax(160px, 1fr) auto',
              }}
            >
              <div
                style={{
                  borderRadius: '12px',
                  border: '1px solid #1f2937',
                  backgroundColor: '#010617',
                  padding: '12px',
                }}
              >
                <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Next step</p>
                <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.6, margin: 0 }}>
                  Decide what you think about this item, then save that judgment. Only use promotion when a fragment should become part of your canon.
                </p>
              </div>
              <div style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.6, overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
                {selectableItems.length > 0 ? 'You can also mark canonical fragments from the center panel if any deserve to be promoted later.' : 'This item is review-only for now. Focus on your actual take, not promotion.'}
              </div>

              {selectedPromotionItems.length > 0 && (
                <div
                  style={{
                    borderRadius: '12px',
                    border: `1px solid ${gateDecisionTone(selectedPromotionGate.decision)}55`,
                    backgroundColor: `${gateDecisionTone(selectedPromotionGate.decision)}12`,
                    padding: '12px',
                    color: '#cbd5f5',
                  }}
                >
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '8px' }}>
                    <InlineBadge label={humanizeGateDecision(selectedPromotionGate.decision)} tone={gateDecisionTone(selectedPromotionGate.decision)} />
                    <InlineBadge label={`${selectedPromotionGate.selectedCount} selected`} tone="#818cf8" />
                    <InlineBadge label={`proof ${selectedPromotionGate.proofStrength}`} tone={proofStrengthTone(selectedPromotionGate.proofStrength)} />
                  </div>
                  <p style={{ color: '#dbe7ff', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                    {selectedPromotionGate.reason || 'These selected fragments are ready for canon review.'}
                  </p>
                  {selectedPromotionGate.alternativeTarget && (
                    <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: '8px 0 0' }}>
                      Better fit if you want to preserve the idea now: {selectedPromotionGate.alternativeTarget}
                    </p>
                  )}
                </div>
              )}

              {savedResponseExcerpt && (
                <div
                  style={{
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#0b1220',
                    padding: '12px',
                    color: '#cbd5f5',
                  }}
                >
                  <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>
                    Your current take
                  </p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                    {savedResponseKind && <InlineBadge label={humanizeSavedResponseKind(savedResponseKind)} tone="#818cf8" />}
                    {metadataText(selectedDelta.metadata, 'resolution_capture_id') && (
                      <InlineBadge label={`capture ${metadataText(selectedDelta.metadata, 'resolution_capture_id')}`} tone="#64748b" />
                    )}
                  </div>
                  <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.6, whiteSpace: 'pre-wrap', margin: 0 }}>
                    {truncateText(savedResponseExcerpt, 900)}
                  </p>
                </div>
              )}

              <div style={{ display: 'grid', gap: '8px' }}>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>How are you responding?</p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <QuickFillButton label="Agree" onClick={() => queueTemplate('agree')} />
                  <QuickFillButton label="Disagree" onClick={() => queueTemplate('disagree')} />
                  <QuickFillButton label="Nuance" onClick={() => queueTemplate('nuance')} />
                  <QuickFillButton label="Personal Story" onClick={() => queueTemplate('story')} />
                  <QuickFillButton label="Wording" onClick={() => queueTemplate('language')} />
                </div>
              </div>

              <textarea
                value={reflectionText}
                onChange={(event) => {
                  setReflectionText(event.target.value);
                  if (reflectionState.tone !== 'idle') {
                    setReflectionState({ tone: 'idle', message: '' });
                  }
                }}
                placeholder={`Example: Yes, this is true. I am building an AI project that supports these initiatives, but I want it framed as a system that strengthens AI Clone, BrandEasy, Outfit A Congo, Collective Fusion, market development, and public leadership rather than a flat list.`}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  minHeight: usePinnedPersonaViewport ? '0' : '220px',
                  height: usePinnedPersonaViewport ? '100%' : undefined,
                  resize: usePinnedPersonaViewport ? 'none' : 'vertical',
                  borderRadius: '14px',
                  border: '1px solid #1f2937',
                  backgroundColor: '#010617',
                  color: '#e2e8f0',
                  padding: '14px',
                  fontSize: '14px',
                  lineHeight: 1.6,
                  outline: 'none',
                  overflowY: 'auto',
                }}
              />

              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <InlineBadge label={`Response: ${humanizeResponseKind(selectedResponseKind)}`} tone="#38bdf8" />
                  <InlineBadge label={humanizeBeliefRelation(metadataText(selectedDelta.metadata, 'belief_relation'))} tone="#22c55e" />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
                  {error && <p style={{ color: '#f87171', fontSize: '12px' }}>{error}</p>}
                  {reflectionState.message && (
                    <p style={{ color: reflectionState.tone === 'success' ? '#22c55e' : '#f87171', fontSize: '12px', maxWidth: '420px', textAlign: 'right' }}>{reflectionState.message}</p>
                  )}
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    <button
                      onClick={() => saveReflection('reviewed')}
                      disabled={isSavingReflection}
                      style={{
                        border: '1px solid #38bdf8',
                        backgroundColor: isSavingReflection ? '#0c4a6e' : '#0f172a',
                        color: 'white',
                        borderRadius: '12px',
                        padding: '10px 14px',
                        cursor: isSavingReflection ? 'wait' : 'pointer',
                        fontWeight: 600,
                      }}
                    >
                      {isSavingReflection ? 'Saving…' : 'Save thought'}
                    </button>
                    <button
                      onClick={() => saveReflection('approved')}
                      disabled={isSavingReflection}
                      style={{
                        border: '1px solid #334155',
                        backgroundColor: '#020617',
                        color: '#cbd5f5',
                        borderRadius: '12px',
                        padding: '10px 14px',
                        cursor: isSavingReflection ? 'wait' : 'pointer',
                        fontWeight: 500,
                      }}
                    >
                      Queue for promotion
                    </button>
                  </div>
                </div>
              </div>
            </section>
            </div>
          </div>
        ) : (
          <div
            style={{
              flex: 1,
              minHeight: 0,
              borderRadius: '14px',
              border: '1px solid #1f2937',
              backgroundColor: '#020617',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              padding: '24px',
            }}
          >
            <div style={{ maxWidth: '560px' }}>
              <p style={{ color: '#22c55e', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.18em', marginBottom: '10px' }}>Done</p>
              <h3 style={{ color: 'white', fontSize: '28px', margin: '0 0 10px' }}>You are done for now.</h3>
              <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.65 }}>
                There are no pending persona review items left in this session. New reflections can come back through future persona deltas.
              </p>
              {reflectionState.message && (
                <p style={{ color: reflectionState.tone === 'success' ? '#22c55e' : '#f87171', fontSize: '12px', marginTop: '12px' }}>{reflectionState.message}</p>
              )}
            </div>
          </div>
        )}
        {promotionState.message && promotionState.tone === 'success' && (
          <div
            style={{
              position: usePinnedPersonaViewport ? 'sticky' : 'static',
              top: usePinnedPersonaViewport ? '88px' : undefined,
              zIndex: 2,
              borderRadius: '12px',
              border: '1px solid #14532d',
              backgroundColor: '#052e16',
              padding: '12px 14px',
            }}
          >
            <p style={{ color: '#86efac', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '6px' }}>
              Promotion Queue Updated
            </p>
            <p style={{ color: '#dcfce7', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
              {promotionState.message} It now lives in the <strong>Queued</strong> lane below.
            </p>
          </div>
        )}
      </section>

      <section
        style={{
          borderRadius: '18px',
          border: '1px solid #1f2937',
          backgroundColor: '#050b19',
          padding: '18px',
          display: 'grid',
          gap: '14px',
          minHeight: 0,
          overflow: 'hidden',
          gridTemplateRows: usePinnedPersonaViewport ? 'auto auto minmax(0, 1fr)' : 'none',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <p style={{ color: '#818cf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Persona Lifecycle</p>
            <h3 style={{ color: 'white', fontSize: '22px', margin: '4px 0 8px' }}>Saved, queued, and historical items</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6 }}>
              Active review stays above. Everything below is already saved, queued, committed, or resolved so you can audit state without confusing it with the work that still needs judgment.
            </p>
          </div>
          <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right', maxWidth: '360px' }}>
            Brain should answer one question clearly: what still needs your attention right now versus what the system has already handled.
          </div>
        </div>
        {promotionState.message && promotionState.tone !== 'success' && (
          <p style={{ color: '#f87171', fontSize: '12px' }}>{promotionState.message}</p>
        )}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {lifecycleGroups.map((group) => {
            const active = lifecycleView === group.key;
            return (
              <button
                key={group.key}
                onClick={() => setLifecycleView(group.key as 'pending_promotion' | 'workspace_saved' | 'committed' | 'resolved')}
                style={{
                  borderRadius: '999px',
                  border: `1px solid ${active ? `${group.tone}88` : '#1f2937'}`,
                  backgroundColor: active ? `${group.tone}18` : '#020617',
                  color: active ? '#f8fafc' : '#94a3b8',
                  padding: '8px 12px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {compactLifecycleLabel(group.key)} · {group.count}
              </button>
            );
          })}
        </div>
        {activeLifecycleGroup && (
          <div
            style={{
              borderRadius: '14px',
              border: '1px solid #1f2937',
              backgroundColor: '#020617',
              padding: '14px',
              display: 'grid',
              gap: '10px',
              minHeight: 0,
              overflow: 'hidden',
              gridTemplateRows: 'auto minmax(0, 1fr)',
            }}
          >
            <div>
              <p style={{ color: activeLifecycleGroup.tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{activeLifecycleGroup.title}</p>
              <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.55 }}>{activeLifecycleGroup.description}</p>
            </div>
            <div style={{ display: 'grid', gap: '8px', minHeight: 0, overflowY: 'auto', paddingRight: '2px' }}>
              {activeLifecycleGroup.items.length === 0 ? (
                <p style={{ color: '#475569', fontSize: '12px' }}>Nothing in this state right now.</p>
              ) : (
                activeLifecycleGroup.items.slice(0, 12).map((item) => (
                  (() => {
                    const queuedItems = readPromotionItemsFromMetadata(item.metadata);
                    const gateSummary = summarizePromotionItems(queuedItems, metadataText(item.metadata, 'target_file'));
                    const commitDisabled = activeLifecycleGroup.key === 'pending_promotion' && gateSummary.decision !== 'allow';
                    return (
                  <div
                    key={item.id}
                    style={{
                      borderRadius: '12px',
                      border: `1px solid ${recentlyQueuedDeltaId === item.id ? '#38bdf8' : '#1f2937'}`,
                      padding: '10px',
                      backgroundColor: recentlyQueuedDeltaId === item.id ? '#082f49' : '#0b1220',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '6px' }}>
                      <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>{truncateText(item.trait, 140)}</p>
                      <span style={{ color: '#94a3b8', fontSize: '11px' }}>{formatTimestamp(new Date(item.created_at))}</span>
                    </div>
                    {recentlyQueuedDeltaId === item.id && (
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                        <InlineBadge label="just queued" tone="#38bdf8" />
                        <InlineBadge label={`${metadataArray(item.metadata, 'selected_promotion_items').length} selected`} tone="#f59e0b" />
                        <InlineBadge label={humanizeGateDecision(gateSummary.decision)} tone={gateDecisionTone(gateSummary.decision)} />
                      </div>
                    )}
                    {metadataText(item.metadata, 'owner_response_excerpt') && (
                      <div style={{ marginBottom: '8px' }}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                          {metadataText(item.metadata, 'owner_response_kind') && (
                            <InlineBadge label={humanizeSavedResponseKind(metadataText(item.metadata, 'owner_response_kind') ?? '')} tone="#818cf8" />
                          )}
                          {metadataText(item.metadata, 'belief_relation') && (
                            <InlineBadge label={humanizeBeliefRelation(metadataText(item.metadata, 'belief_relation'))} tone="#22c55e" />
                          )}
                        </div>
                        <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.55, margin: 0 }}>
                          {truncateText(metadataText(item.metadata, 'owner_response_excerpt') ?? '', 180)}
                        </p>
                      </div>
                    )}
                    {activeLifecycleGroup.key === 'pending_promotion' && (
                      <div
                        style={{
                          marginBottom: '8px',
                          padding: '8px 10px',
                          borderRadius: '10px',
                          border: `1px solid ${gateDecisionTone(gateSummary.decision)}44`,
                          backgroundColor: `${gateDecisionTone(gateSummary.decision)}12`,
                        }}
                      >
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                          <InlineBadge label={humanizeGateDecision(gateSummary.decision)} tone={gateDecisionTone(gateSummary.decision)} />
                          <InlineBadge label={`proof ${gateSummary.proofStrength}`} tone={proofStrengthTone(gateSummary.proofStrength)} />
                        </div>
                        <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, margin: 0 }}>
                          {gateSummary.reason || 'This queued item is ready to commit to canon.'}
                        </p>
                        {gateSummary.alternativeTarget && (
                          <p style={{ color: '#94a3b8', fontSize: '11px', lineHeight: 1.5, margin: '6px 0 0' }}>
                            Better fit right now: {gateSummary.alternativeTarget}
                          </p>
                        )}
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                      <span style={{ color: '#64748b', fontSize: '11px' }}>{humanizeReviewSource(metadataText(item.metadata, 'review_source'))}</span>
                      {activeLifecycleGroup.key === 'pending_promotion' && (
                        <button
                          onClick={() => void commitPromotion(item)}
                          disabled={promotingDeltaId === item.id || commitDisabled}
                          style={{
                            borderRadius: '10px',
                            border: `1px solid ${commitDisabled ? '#475569' : '#818cf8'}`,
                            backgroundColor: commitDisabled ? '#0f172a' : promotingDeltaId === item.id ? '#312e81' : '#1e1b4b',
                            color: commitDisabled ? '#64748b' : 'white',
                            padding: '8px 10px',
                            cursor: commitDisabled ? 'not-allowed' : promotingDeltaId === item.id ? 'wait' : 'pointer',
                            fontSize: '12px',
                            fontWeight: 600,
                          }}
                        >
                          {commitDisabled ? (gateSummary.decision === 'block' ? 'Blocked' : 'Held') : promotingDeltaId === item.id ? 'Committing…' : 'Commit to canon'}
                        </button>
                      )}
                    </div>
                  </div>
                    );
                  })()
                ))
              )}
            </div>
          </div>
        )}
      </section>
    </section>
  );
}

function QuickFillButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        borderRadius: '999px',
        border: '1px solid #1f2937',
        backgroundColor: '#020617',
        color: '#cbd5f5',
        padding: '6px 10px',
        fontSize: '12px',
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );
}

function ReviewMetaChip({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div style={{ borderRadius: '999px', border: `1px solid ${tone}44`, backgroundColor: `${tone}18`, padding: '6px 10px' }}>
      <span style={{ color: '#94a3b8', fontSize: '11px', marginRight: '6px', textTransform: 'uppercase' }}>{label}</span>
      <span style={{ color: tone, fontSize: '12px', fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function InlineBadge({ label, tone }: { label: string; tone: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        maxWidth: '100%',
        borderRadius: '999px',
        border: `1px solid ${tone}44`,
        backgroundColor: `${tone}18`,
        color: tone,
        padding: '4px 8px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        whiteSpace: 'normal',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
      }}
    >
      {label}
    </span>
  );
}

function CaptureTelemetryPanel({
  metrics,
  health,
  error,
}: {
  metrics: CaptureTelemetry | null;
  health: OpenBrainHealth | null;
  error: string | null;
}) {
  if (error) {
    return <p style={{ color: '#f87171' }}>{error}</p>;
  }

  const storageLabel = health?.storage_backend === 'pgvector' ? 'Native vector mode' : health?.storage_backend === 'jsonb' ? 'JSON fallback' : 'Unknown';
  const serviceLabel = health?.search_ready ? 'Search ready' : health?.database_connected ? 'Memory store online' : 'Memory store offline';
  const subtitle =
    health?.storage_backend === 'pgvector'
      ? 'Capture + refresh stats from the native Postgres vector lane.'
      : 'Capture + refresh stats from the Postgres memory lane. JSON fallback is active until native vector support is available.';

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Open Brain Telemetry</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>{subtitle}</p>
        </div>
        <p style={{ color: health?.database_connected ? '#22c55e' : '#f87171', fontSize: '12px' }}>
          {serviceLabel}
        </p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <TelemetryMeta label="Storage" value={storageLabel} detail={health?.embedding_type ?? 'n/a'} />
        <TelemetryMeta label="Native Vector Ext" value={health?.vector_extension ? 'Enabled' : 'Unavailable'} detail="Current Postgres capability" />
        <TelemetryMeta
          label="Embedding Dimension"
          value={health?.configured_dimension ? `${health.configured_dimension}/${health.embedder_dimension}` : `${health?.embedder_dimension ?? 0}`}
          detail={health?.dimension_match ? 'DB and embedder aligned' : 'Running fallback storage mode'}
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <TelemetryStat label="Captures" value={metrics?.captures.total ?? 0} tone="#38bdf8" detail="All time" />
        <TelemetryStat label="Last 24h" value={metrics?.captures.last_24h ?? 0} tone="#34d399" detail="Fresh ingest" />
        <TelemetryStat label="Chunks" value={metrics?.vectors.total ?? 0} tone="#f97316" detail="Indexed memory rows" />
        <TelemetryStat label="Expiring" value={metrics?.vectors.with_expiry ?? 0} tone="#fbbf24" detail="Short-term" />
        <TelemetryStat label="Overdue" value={metrics?.vectors.overdue ?? 0} tone="#f87171" detail="Needs cleanup" />
        <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
          <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Last refresh run</p>
          <p style={{ color: '#cbd5f5', fontSize: '18px', fontWeight: 600 }}>{metrics?.vectors.last_refresh_at ? formatTimestamp(new Date(metrics.vectors.last_refresh_at)) : '—'}</p>
          <p style={{ color: '#475569', fontSize: '12px' }}>memory_vectors.last_refreshed_at</p>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Source', 'Topics', 'Chunks', 'Created'].map((header) => (
                <th key={header} style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!metrics || metrics.recent_captures.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ padding: '12px 0', color: '#475569' }}>No captures recorded yet.</td>
              </tr>
            ) : (
              metrics.recent_captures.map((capture) => (
                <tr key={capture.id}>
                  <td style={{ padding: '10px 0', color: '#e2e8f0', fontWeight: 600 }}>{capture.source ?? '—'}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{(capture.topics ?? []).join(', ') || '—'}</td>
                  <td style={{ padding: '10px 0', color: '#e2e8f0' }}>{capture.chunk_count}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{capture.created_at ? formatTimestamp(new Date(capture.created_at)) : '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TelemetryMeta({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: '#e2e8f0', fontSize: '18px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
  );
}

function TelemetryStat({ label, value, detail, tone }: { label: string; value: number; detail: string; tone: string }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: tone, fontSize: '22px', fontWeight: 600 }}>{value}</p>
      <p style={{ color: '#475569', fontSize: '12px' }}>{detail}</p>
    </div>
  );
}

function AutomationsPanel({
  automations,
  error,
  controlPlane,
}: {
  automations: Automation[];
  error: string | null;
  controlPlane: BrainControlPlanePayload | null;
}) {
  if (error) {
    return <p style={{ color: '#f87171' }}>{error}</p>;
  }
  const hasRows = automations.length > 0;
  const summary = controlPlane?.summary ?? null;
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', display: 'grid', gap: '14px' }}>
      <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Automations</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>Use this tab as the operational surface: which jobs exist, when they ran, and whether the system is healthy enough to trust them.</p>
        </div>
        {summary && (
          <p style={{ color: '#94a3b8', fontSize: '12px' }}>
            {summary.active_automation_count ?? automations.length} active · {summary.capture_count ?? 0} captures · {summary.doc_count ?? 0} docs
          </p>
        )}
      </div>
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <TelemetryMeta label="Active Jobs" value={String(summary.active_automation_count ?? automations.length)} detail="Currently visible automation contracts" />
          <TelemetryMeta label="Captures" value={String(summary.capture_count ?? 0)} detail="Open Brain capture total" />
          <TelemetryMeta label="Pending Review" value={String(summary.pending_review_count ?? 0)} detail="Brain persona queue" />
          <TelemetryMeta label="Source Assets" value={String(summary.source_asset_count ?? 0)} detail="Shared long-form source inventory" />
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Name</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Schedule</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Status</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Channel</th>
              <th style={{ textAlign: 'left', color: '#94a3b8', fontSize: '12px', fontWeight: 500, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>Last Run</th>
            </tr>
          </thead>
          <tbody>
            {!hasRows && (
              <tr>
                <td colSpan={5} style={{ padding: '12px 0', color: '#475569' }}>No automations found.</td>
              </tr>
            )}
            {hasRows &&
              automations.map((job) => (
                <tr key={job.id}>
                  <td style={{ padding: '10px 0', color: 'white', fontWeight: 600 }}>{job.name}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.schedule}</td>
                  <td style={{ padding: '10px 0' }}>{statusBadge(job.status)}</td>
                  <td style={{ padding: '10px 0', color: '#cbd5f5' }}>{job.channel}</td>
                  <td style={{ padding: '10px 0', color: '#94a3b8' }}>{job.last_run_at ? formatTimestamp(new Date(job.last_run_at)) : '—'}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DocsPanel({ docs }: { docs: DocEntry[] }) {
  const [docQuery, setDocQuery] = useState('');
  const [selectedGroup, setSelectedGroup] = useState('all');
  const [recentDocPaths, setRecentDocPaths] = useState<string[]>([]);
  const filteredDocs = useMemo(() => {
    const query = docQuery.trim().toLowerCase();
    return docs.filter((doc) => {
      const group = doc.group ?? inferDocGroup(doc.path);
      const matchesGroup = selectedGroup === 'all' || group === selectedGroup;
      const haystack = `${doc.name}\n${doc.path}\n${doc.snippet}\n${doc.content ?? ''}`.toLowerCase();
      const matchesQuery = query.length === 0 || haystack.includes(query);
      return matchesGroup && matchesQuery;
    });
  }, [docQuery, docs, selectedGroup]);
  const groupedDocs = useMemo(() => {
    const groups = new Map<string, DocEntry[]>();
    for (const doc of filteredDocs) {
      const key = doc.group ?? inferDocGroup(doc.path);
      const current = groups.get(key) ?? [];
      current.push(doc);
      groups.set(key, current);
    }
    return Array.from(groups.entries()).map(([group, items]) => ({
      group,
      items: items.sort((left, right) => left.name.localeCompare(right.name)),
    }));
  }, [filteredDocs]);
  const allGroups = useMemo(() => Array.from(new Set(docs.map((doc) => doc.group ?? inferDocGroup(doc.path)))).sort(), [docs]);
  const [selectedDocPath, setSelectedDocPath] = useState<string>(docs[0]?.path ?? '');
  const selectedDoc = useMemo(
    () => groupedDocs.flatMap((entry) => entry.items).find((doc) => doc.path === selectedDocPath) ?? groupedDocs[0]?.items[0] ?? null,
    [groupedDocs, selectedDocPath],
  );
  const recentDocs = useMemo(
    () => recentDocPaths.map((path) => docs.find((doc) => doc.path === path)).filter((doc): doc is DocEntry => Boolean(doc)),
    [docs, recentDocPaths],
  );

  useEffect(() => {
    if (selectedDoc) {
      return;
    }
    if (groupedDocs[0]?.items[0]) {
      setSelectedDocPath(groupedDocs[0].items[0].path);
    }
  }, [groupedDocs, selectedDoc]);

  return (
    <section style={{ display: 'flex', gap: '18px', borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', minHeight: '560px' }}>
      <div style={{ width: '320px', borderRight: '1px solid #0f172a', paddingRight: '12px', maxHeight: '520px', overflowY: 'auto' }}>
        <div style={{ marginBottom: '12px' }}>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Knowledge Docs</p>
          <p style={{ color: '#64748b', fontSize: '13px' }}>
            Brain is the canonical reading surface for operating docs, knowledge docs, persona files, and reference material.
          </p>
        </div>
        <div style={{ display: 'grid', gap: '10px', marginBottom: '14px' }}>
          <input
            value={docQuery}
            onChange={(event) => setDocQuery(event.target.value)}
            placeholder="Search docs, paths, or content"
            style={brainInputStyle}
          />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setSelectedGroup('all')}
              style={docsFilterButtonStyle(selectedGroup === 'all')}
            >
              All
            </button>
            {allGroups.map((group) => (
              <button
                key={group}
                onClick={() => setSelectedGroup(group)}
                style={docsFilterButtonStyle(selectedGroup === group)}
              >
                {group}
              </button>
            ))}
          </div>
        </div>
        {recentDocs.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Recently viewed</p>
            <div style={{ display: 'grid', gap: '8px' }}>
              {recentDocs.slice(0, 3).map((doc) => (
                <button
                  key={`recent-${doc.path}`}
                  onClick={() => setSelectedDocPath(doc.path)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '10px',
                    borderRadius: '12px',
                    border: '1px solid #1f2937',
                    backgroundColor: '#020617',
                    color: 'white',
                    cursor: 'pointer',
                  }}
                >
                  <p style={{ fontSize: '13px', fontWeight: 600 }}>{doc.name}</p>
                  <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.45 }}>{truncateText(doc.snippet, 90)}</p>
                </button>
              ))}
            </div>
          </div>
        )}
        {groupedDocs.length === 0 && <p style={{ color: '#475569' }}>No documentation found.</p>}
        {groupedDocs.map((group) => (
          <div key={group.group} style={{ marginBottom: '16px' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>{group.group}</p>
            <div style={{ display: 'grid', gap: '8px' }}>
              {group.items.map((doc) => {
                const isSelected = doc.path === (selectedDoc?.path ?? '');
                return (
                  <button
                    key={doc.path}
                    onClick={() => {
                      setSelectedDocPath(doc.path);
                      setRecentDocPaths((current) => [doc.path, ...current.filter((entry) => entry !== doc.path)].slice(0, 5));
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '10px',
                      borderRadius: '12px',
                      border: isSelected ? '1px solid #38bdf8' : '1px solid transparent',
                      backgroundColor: isSelected ? '#0f172a' : 'transparent',
                      color: 'white',
                      cursor: 'pointer',
                    }}
                  >
                    <p style={{ fontSize: '13px', fontWeight: 600 }}>{doc.name}</p>
                    <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.45 }}>{doc.snippet}</p>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {selectedDoc ? (
          <div>
            <div style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '4px' }}>{selectedDoc.group ?? inferDocGroup(selectedDoc.path)}</p>
                <h2 style={{ color: 'white', fontSize: '24px', marginBottom: '6px' }}>{selectedDoc.name}</h2>
                <p style={{ color: '#64748b', fontSize: '12px' }}>{selectedDoc.path}</p>
              </div>
              {selectedDoc.updatedAt && <p style={{ color: '#64748b', fontSize: '12px' }}>Updated {formatTimestamp(new Date(selectedDoc.updatedAt))}</p>}
            </div>
            <div
              style={{
                borderRadius: '14px',
                border: '1px solid #1f2937',
                backgroundColor: '#020617',
                padding: '16px',
                color: '#cbd5f5',
                fontSize: '14px',
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                maxHeight: '500px',
                overflowY: 'auto',
              }}
            >
              {selectedDoc.content?.trim() || selectedDoc.snippet}
            </div>
          </div>
        ) : (
          <p style={{ color: '#475569' }}>Select a document to read it here.</p>
        )}
      </div>
    </section>
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

function docsFilterButtonStyle(active: boolean): CSSProperties {
  return {
    borderRadius: '999px',
    border: active ? '1px solid #38bdf8' : '1px solid #1f2937',
    backgroundColor: active ? '#082f49' : '#020617',
    color: active ? '#f8fafc' : '#94a3b8',
    padding: '7px 11px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
  };
}

function compactLifecycleLabel(key: string) {
  if (key === 'workspace_saved') return 'Saved';
  if (key === 'pending_promotion') return 'Queued';
  if (key === 'committed') return 'Committed';
  return 'History';
}

function metadataText(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}

function metadataObject<T extends object>(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as T) : null;
}

function metadataArray(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return Array.isArray(value) ? value : [];
}

function metadataBoolean(metadata: Record<string, unknown> | undefined, key: string) {
  return metadata?.[key] === true;
}

function stablePromotionItemId(kind: PromotionItemKind, title: string, content: string) {
  const source = `${kind}:${title}:${content}`;
  let hash = 0;
  for (let index = 0; index < source.length; index += 1) {
    hash = (hash * 31 + source.charCodeAt(index)) >>> 0;
  }
  return `${kind}:${hash.toString(16)}`;
}

function buildPromotionItems(delta: PersonaDeltaEntry | null, targetFile: string | null): PromotionItem[] {
  if (!delta) {
    return [];
  }
  const items: PromotionItem[] = [];
  const deltaSummary = delta.trait?.trim() || null;
  const reviewInterpretation = metadataText(delta.metadata, 'owner_response_excerpt') ?? delta.notes?.trim() ?? null;
  const pushItem = (kind: PromotionItemKind, label: string, content: string, evidence?: string | null) => {
    const normalizedContent = content.trim();
    if (!normalizedContent) return;
    const normalizedEvidence = evidence?.trim() || null;
    const proofStrength: PromotionItemProofStrength = kind === 'stat' ? 'strong' : normalizedEvidence ? 'weak' : 'none';
    const artifactSummary = kind === 'stat' ? normalizedContent : null;
    const artifactKind = kind === 'stat' ? 'metric_or_proof_point' : null;
    const proofSignal = kind === 'stat' ? normalizedContent : normalizedEvidence;
    items.push({
      id: stablePromotionItemId(kind, label, normalizedContent),
      kind,
      label,
      content: normalizedContent,
      evidence: normalizedEvidence,
      targetFile,
      artifactSummary,
      artifactKind,
      artifactRef: null,
      deltaSummary,
      reviewInterpretation,
      capabilitySignal: null,
      positioningSignal: null,
      leverageSignal: null,
      proofSignal,
      proofStrength,
      gateDecision: 'pending',
      gateReason: null,
    });
  };

  for (const entry of metadataArray(delta.metadata, 'talking_points')) {
    if (typeof entry === 'string') {
      pushItem('talking_point', 'Talking point', entry);
    }
  }
  for (const entry of metadataArray(delta.metadata, 'frameworks')) {
    if (entry && typeof entry === 'object') {
      const framework = entry as Record<string, unknown>;
      pushItem(
        'framework',
        String(framework.title || 'Framework'),
        String(framework.takeaway || framework.evidence || '').trim(),
        typeof framework.evidence === 'string' ? framework.evidence : null,
      );
    }
  }
  for (const entry of metadataArray(delta.metadata, 'anecdotes')) {
    if (entry && typeof entry === 'object') {
      const anecdote = entry as Record<string, unknown>;
      pushItem(
        'anecdote',
        String(anecdote.title || 'Anecdote'),
        String(anecdote.summary || anecdote.evidence || '').trim(),
        typeof anecdote.evidence === 'string' ? anecdote.evidence : null,
      );
    }
  }
  for (const entry of metadataArray(delta.metadata, 'phrase_candidates')) {
    if (typeof entry === 'string') {
      pushItem('phrase_candidate', 'Reusable phrase', entry);
    }
  }
  for (const entry of metadataArray(delta.metadata, 'stats')) {
    if (typeof entry === 'string') {
      pushItem('stat', 'Proof point', entry);
    }
  }
  return items;
}

function readPromotionItemsFromMetadata(metadata: Record<string, unknown> | undefined): PromotionItem[] {
  const items = metadataArray(metadata, 'selected_promotion_items');
  const parsed = items
    .map((entry) => {
      if (!entry || typeof entry !== 'object') return null;
      const record = entry as Record<string, unknown>;
      const kind = record.kind;
      const id = record.id;
      const label = record.label;
      const content = record.content;
      if (typeof kind !== 'string' || typeof id !== 'string' || typeof label !== 'string' || typeof content !== 'string') {
        return null;
      }
      return {
        id,
        kind: kind as PromotionItemKind,
        label,
        content,
        evidence: typeof record.evidence === 'string' ? record.evidence : null,
        targetFile: typeof record.targetFile === 'string' ? record.targetFile : null,
        artifactSummary: typeof record.artifactSummary === 'string' ? record.artifactSummary : null,
        artifactKind: typeof record.artifactKind === 'string' ? record.artifactKind : null,
        artifactRef: typeof record.artifactRef === 'string' ? record.artifactRef : null,
        deltaSummary: typeof record.deltaSummary === 'string' ? record.deltaSummary : null,
        reviewInterpretation: typeof record.reviewInterpretation === 'string' ? record.reviewInterpretation : null,
        capabilitySignal: typeof record.capabilitySignal === 'string' ? record.capabilitySignal : null,
        positioningSignal: typeof record.positioningSignal === 'string' ? record.positioningSignal : null,
        leverageSignal: typeof record.leverageSignal === 'string' ? record.leverageSignal : null,
        proofSignal: typeof record.proofSignal === 'string' ? record.proofSignal : null,
        proofStrength: record.proofStrength === 'weak' || record.proofStrength === 'strong' ? record.proofStrength : 'none',
        gateDecision:
          record.gateDecision === 'allow' || record.gateDecision === 'hold' || record.gateDecision === 'block'
            ? record.gateDecision
            : 'pending',
        gateReason: typeof record.gateReason === 'string' ? record.gateReason : null,
      } satisfies PromotionItem;
    })
    .filter((item): item is PromotionItem => item !== null);
  return parsed;
}

function humanizePromotionKind(kind: PromotionItemKind) {
  switch (kind) {
    case 'talking_point':
      return 'Talking point';
    case 'framework':
      return 'Framework';
    case 'anecdote':
      return 'Anecdote';
    case 'phrase_candidate':
      return 'Reusable phrase';
    case 'stat':
      return 'Proof point';
    default:
      return kind;
  }
}

function humanizeGateDecision(decision: PromotionItemGateDecision) {
  if (decision === 'allow') return 'Allowed';
  if (decision === 'hold') return 'Held';
  if (decision === 'block') return 'Blocked';
  return 'Pending';
}

function gateDecisionTone(decision: PromotionItemGateDecision) {
  if (decision === 'allow') return '#22c55e';
  if (decision === 'hold') return '#f59e0b';
  if (decision === 'block') return '#f87171';
  return '#64748b';
}

function proofStrengthTone(strength: PromotionItemProofStrength) {
  if (strength === 'strong') return '#22c55e';
  if (strength === 'weak') return '#f59e0b';
  return '#64748b';
}

function inferPromotionGate(item: PromotionItem, targetFile: string | null): { decision: PromotionItemGateDecision; reason: string | null } {
  const effectiveTarget = item.targetFile ?? targetFile;
  const explicitDecision = item.gateDecision;
  if (effectiveTarget?.includes('history/initiatives')) {
    const hasArtifactAnchor = Boolean(item.artifactSummary || item.artifactRef || item.artifactKind);
    if (explicitDecision === 'allow' && hasArtifactAnchor && item.proofStrength === 'strong') {
      return { decision: 'allow', reason: item.gateReason || 'Artifact-backed proof is present.' };
    }
    if (explicitDecision === 'hold' && hasArtifactAnchor) {
      return { decision: 'hold', reason: item.gateReason || 'Artifact anchor exists, but the proof is not strong enough yet.' };
    }
    if (explicitDecision === 'block' && !hasArtifactAnchor) {
      return { decision: 'block', reason: item.gateReason || 'Initiatives canon requires a visible artifact, output, or metric.' };
    }
    if (hasArtifactAnchor && item.proofStrength === 'strong') {
      return { decision: 'allow', reason: item.gateReason || 'Artifact-backed proof is present.' };
    }
    if (hasArtifactAnchor) {
      return { decision: 'hold', reason: item.gateReason || 'Artifact anchor exists, but the proof is still weak.' };
    }
    return { decision: 'block', reason: item.gateReason || 'Initiatives canon requires a visible artifact, output, or metric.' };
  }
  return {
    decision: explicitDecision === 'hold' || explicitDecision === 'block' || explicitDecision === 'allow' ? explicitDecision : 'allow',
    reason: item.gateReason,
  };
}

function suggestAlternativeTarget(item: PromotionItem, targetFile: string | null) {
  const effectiveTarget = item.targetFile ?? targetFile;
  if (!effectiveTarget?.includes('history/initiatives')) {
    return null;
  }
  if (item.kind === 'anecdote') return 'history/story_bank.md';
  if (item.kind === 'phrase_candidate') return 'identity/VOICE_PATTERNS.md';
  return 'identity/claims.md';
}

function summarizePromotionItems(items: PromotionItem[], targetFile: string | null): PromotionGateSummary {
  if (items.length === 0) {
    return {
      decision: 'pending',
      reason: 'Select at least one fragment to see whether canon commit is allowed.',
      proofStrength: 'none',
      alternativeTarget: null,
      selectedCount: 0,
    };
  }
  const assessed = items.map((item) => ({ item, gate: inferPromotionGate(item, targetFile) }));
  const strongestProof = assessed.reduce<PromotionItemProofStrength>((current, entry) => {
    if (entry.item.proofStrength === 'strong') return 'strong';
    if (entry.item.proofStrength === 'weak' && current === 'none') return 'weak';
    return current;
  }, 'none');
  const block = assessed.find((entry) => entry.gate.decision === 'block');
  if (block) {
    return {
      decision: 'block',
      reason: block.gate.reason,
      proofStrength: strongestProof,
      alternativeTarget: suggestAlternativeTarget(block.item, targetFile),
      selectedCount: items.length,
    };
  }
  const hold = assessed.find((entry) => entry.gate.decision === 'hold');
  if (hold) {
    return {
      decision: 'hold',
      reason: hold.gate.reason,
      proofStrength: strongestProof,
      alternativeTarget: suggestAlternativeTarget(hold.item, targetFile),
      selectedCount: items.length,
    };
  }
  return {
    decision: 'allow',
    reason: assessed.find((entry) => entry.gate.reason)?.gate.reason || 'These selected fragments are ready for canon commit.',
    proofStrength: strongestProof,
    alternativeTarget: null,
    selectedCount: items.length,
  };
}

function resolvePromotionGate(item: PromotionItem, targetFile: string | null) {
  return inferPromotionGate(item, targetFile);
}

function hasSelectablePromotionMetadata(metadata: Record<string, unknown> | undefined) {
  return (
    metadataArray(metadata, 'talking_points').length > 0 ||
    metadataArray(metadata, 'frameworks').length > 0 ||
    metadataArray(metadata, 'anecdotes').length > 0 ||
    metadataArray(metadata, 'phrase_candidates').length > 0 ||
    metadataArray(metadata, 'stats').length > 0
  );
}

function promotionSignalCount(metadata: Record<string, unknown> | undefined) {
  const explicit = metadata?.queue_promotion_signal_count;
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    return explicit;
  }
  return (
    metadataArray(metadata, 'talking_points').length +
    metadataArray(metadata, 'frameworks').length +
    metadataArray(metadata, 'anecdotes').length +
    metadataArray(metadata, 'phrase_candidates').length +
    metadataArray(metadata, 'stats').length
  );
}

function isPromotionReady(status: string, metadata: Record<string, unknown> | undefined) {
  if (typeof metadata?.queue_promotion_ready === 'boolean') {
    return metadata.queue_promotion_ready;
  }
  const normalized = (status || 'draft').toLowerCase();
  return (normalized === 'in_review' || normalized === 'reviewed') && hasSelectablePromotionMetadata(metadata);
}

function targetPriority(targetFile: string | null) {
  if (!targetFile) return 1;
  if (targetFile.includes('identity/claims')) return 5;
  if (targetFile.includes('identity/VOICE_PATTERNS')) return 5;
  if (targetFile.includes('identity/philosophy')) return 4;
  if (targetFile.includes('identity/decision_principles')) return 4;
  if (targetFile.includes('prompts/content_pillars')) return 4;
  if (targetFile.includes('history/story_bank')) return 3;
  if (targetFile.includes('history/wins')) return 3;
  if (targetFile.includes('history/initiatives')) return 2;
  if (targetFile.includes('history/resume')) return 1;
  return 1;
}

function recencyPriority(createdAt: string) {
  const ageMs = Date.now() - new Date(createdAt).getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  if (ageMs <= dayMs) return 4;
  if (ageMs <= 3 * dayMs) return 3;
  if (ageMs <= 7 * dayMs) return 2;
  if (ageMs <= 30 * dayMs) return 1;
  return 0;
}

function reviewStatePriority(status: string, metadata: Record<string, unknown> | undefined) {
  const normalized = (status || 'draft').toLowerCase();
  if (isPromotionReady(normalized, metadata)) return 6;
  if (normalized === 'in_review') return 5;
  if (normalized === 'reviewed') return 4;
  if (normalized === 'pending') return 3;
  if (normalized === 'draft') return 2;
  return 0;
}

function reviewSourcePriority(reviewSource: string | null) {
  if (reviewSource === 'brain.persona.ui') return 3;
  if (reviewSource === 'linkedin_workspace.feed_quote') return 2;
  if (reviewSource === 'long_form_media.segment') return 1;
  return 0;
}

function looksWeakLongFormText(text: string) {
  const normalized = text.toLowerCase();
  return [
    '# clean transcript',
    '**open questions:**',
    'machine learning is a subset of ai',
    'that element in green',
    "my team and i thought",
    "i'm super proud",
    'alive in spirit',
    'not very well done',
    'why does it have to be that way',
  ].some((pattern) => normalized.includes(pattern));
}

function shouldMuteActivePersonaDelta(delta: PersonaDeltaEntry, promotionCandidateCount: number) {
  if (typeof delta.metadata?.queue_muted === 'boolean') {
    return delta.metadata.queue_muted;
  }
  const reviewSource = metadataText(delta.metadata, 'review_source');
  if (reviewSource !== 'long_form_media.segment') {
    return false;
  }
  if (metadataText(delta.metadata, 'sync_state') === 'stale_segment') {
    return true;
  }
  if (looksWeakLongFormText(delta.trait) || looksWeakLongFormText(delta.notes || '')) {
    return true;
  }
  if (promotionCandidateCount === 0) {
    return true;
  }
  const hasStrongSignal =
    metadataArray(delta.metadata, 'frameworks').length > 0 ||
    metadataArray(delta.metadata, 'anecdotes').length > 0 ||
    metadataArray(delta.metadata, 'phrase_candidates').length > 0;
  return !hasStrongSignal && promotionCandidateCount < 3;
}

function personaDeltaPriorityScore(delta: PersonaDeltaEntry, promotionCandidateCount: number, muted: boolean) {
  const explicit = delta.metadata?.queue_priority_score;
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    return explicit;
  }
  const targetFile = metadataText(delta.metadata, 'target_file');
  const reviewSource = metadataText(delta.metadata, 'review_source');
  let score = 0;
  score += targetPriority(targetFile) * 4;
  score += promotionCandidateCount * 2;
  score += recencyPriority(delta.created_at);
  score += reviewStatePriority(delta.status, delta.metadata);
  score += reviewSourcePriority(reviewSource);
  if (metadataBoolean(delta.metadata, 'pending_promotion')) {
    score += 4;
  }
  if (muted) {
    score -= 8;
  }
  return score;
}

function isWorkspaceApproved(status: string, metadata: Record<string, unknown> | undefined) {
  const normalized = (status || 'draft').toLowerCase();
  const reviewSource = metadataText(metadata, 'review_source');
  const approvalState = metadataText(metadata, 'approval_state');
  return normalized === 'approved' && (reviewSource === 'linkedin_workspace.feed_quote' || approvalState === 'approved_from_workspace');
}

function isBrainPendingReview(status: string, metadata: Record<string, unknown> | undefined) {
  const normalized = (status || 'draft').toLowerCase();
  if (normalized === 'draft' || normalized === 'pending' || normalized === 'in_review') {
    return true;
  }
  return normalized === 'reviewed' && hasSelectablePromotionMetadata(metadata) && !metadataBoolean(metadata, 'pending_promotion');
}

function personaDeltaStage(delta: PersonaDeltaEntry) {
  const queuedStage = metadataText(delta.metadata, 'queue_stage');
  if (queuedStage) return queuedStage;
  const status = (delta.status || 'draft').toLowerCase();
  if (status === 'committed') return 'committed';
  if (metadataBoolean(delta.metadata, 'pending_promotion')) return 'pending_promotion';
  if (isWorkspaceApproved(status, delta.metadata)) return 'workspace_saved';
  if (isBrainPendingReview(status, delta.metadata)) return 'brain_pending_review';
  if (status === 'approved') return 'approved_unpromoted';
  return status || 'draft';
}

function findPackBySection(packs: PersonaPack[], relPath: string | null) {
  if (!relPath) return null;
  return packs.find((pack) => pack.sections.some((section) => section.path === relPath)) ?? null;
}

function findPackSection(packs: PersonaPack[], relPath: string | null) {
  if (!relPath) return null;
  for (const pack of packs) {
    const section = pack.sections.find((item) => item.path === relPath);
    if (section) {
      return section;
    }
  }
  return null;
}

function briefSourceIntelligence(entry: DailyBriefEntry | null) {
  return entry ? metadataObject<BriefSourceIntelligence>(entry.metadata, 'source_intelligence') : null;
}

function numberMeta(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '0';
}

function humanizeSnakeCase(value: string | null | undefined) {
  if (!value) return 'Unknown';
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function compactBriefCandidate(item: BriefSourceIntelligenceCandidate) {
  const title = item.title?.trim() || 'Untitled candidate';
  const parts = [item.priority_lane?.trim(), item.target_file?.trim(), item.route_reason?.trim()].filter(Boolean);
  return parts.length > 0 ? `${title} · ${parts.join(' · ')}` : title;
}

function compactReviewItem(item: BriefSourceIntelligenceReviewItem) {
  const trait = item.trait?.trim() || 'Untitled review item';
  const parts = [item.belief_relation ? humanizeBeliefRelation(item.belief_relation) : null, humanizeReviewSource(item.review_source ?? null)].filter(Boolean);
  return parts.length > 0 ? `${trait} · ${parts.join(' · ')}` : trait;
}

function truncateText(text: string, limit: number) {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).trimEnd()}\n…`;
}

function buildReviewHeadline(delta: PersonaDeltaEntry, targetFile: string | null) {
  if (!targetFile) {
    return delta.trait;
  }
  return `${delta.trait} → ${humanizeTargetPath(targetFile)}`;
}

function buildReviewReason(delta: PersonaDeltaEntry, targetFile: string | null, contextPath: string | null) {
  const explicitReason = metadataText(delta.metadata, 'why_showing');
  if (explicitReason) {
    return explicitReason;
  }
  const targetLabel = targetFile ? humanizeTargetPath(targetFile) : 'the persona bundle';
  const contextLabel = contextPath ? ` The closest live context is pulled from ${contextPath}.` : '';
  return `This is still pending, so I need your judgment before it becomes part of ${targetLabel}.${contextLabel} I am showing it now because it looks durable enough to affect how your initiatives, voice, or narrative get represented.`;
}

function buildReviewAsk(delta: PersonaDeltaEntry, targetFile: string | null) {
  const explicitPrompt = metadataText(delta.metadata, 'review_prompt');
  if (explicitPrompt) {
    return explicitPrompt;
  }
  const targetLabel = targetFile ? humanizeTargetPath(targetFile) : 'the persona bundle';
  return `Tell me if this belongs in ${targetLabel}, what is accurate about it, what nuance is missing, and how you would phrase it in your own voice.`;
}

function humanizeTargetPath(path: string) {
  return path
    .replace(/^identity\//, 'identity / ')
    .replace(/^history\//, 'history / ')
    .replace(/^prompts\//, 'prompts / ')
    .replace(/\.md$/i, '')
    .replace(/[_-]+/g, ' ');
}

function buildReflectionTopics(delta: PersonaDeltaEntry | null, targetFile: string | null) {
  const topics = ['persona', 'reflection'];
  if (delta?.persona_target) topics.push(delta.persona_target);
  if (targetFile) topics.push(targetFile);
  return Array.from(new Set(topics));
}

function buildReflectionCaptureText({
  delta,
  reflectionText,
  targetFile,
  sectionContent,
  selectedItems,
}: {
  delta: PersonaDeltaEntry | null;
  reflectionText: string;
  targetFile: string | null;
  sectionContent: string | null;
  selectedItems: PromotionItem[];
}) {
  const lines = [
    '# Persona Reflection',
    '',
    `Trait: ${delta?.trait ?? 'General reflection'}`,
    `Persona target: ${delta?.persona_target ?? 'general'}`,
    `Target file: ${targetFile ?? 'not assigned'}`,
    delta?.capture_id ? `Linked capture: ${delta.capture_id}` : 'Linked capture: none',
    '',
    '## Candidate Notes',
    delta?.notes?.trim() || 'No candidate notes provided.',
    '',
  ];

  if (selectedItems.length > 0) {
    lines.push('## Selected For Promotion');
    for (const item of selectedItems) {
      lines.push(`- [${humanizePromotionKind(item.kind)}] ${item.label}: ${item.content}`);
      if (item.evidence) {
        lines.push(`  Evidence: ${item.evidence}`);
      }
    }
    lines.push('');
  }

  if (sectionContent) {
    lines.push('## Current Canonical Context', truncateText(sectionContent, 1200), '');
  }

  lines.push('## My Reaction', reflectionText.trim());
  return lines.join('\n');
}

function formatTimestamp(value: Date) {
  return value.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
}

function humanizeReviewSource(source: string | null) {
  if (!source) return 'No source';
  if (source === 'long_form_media.segment') return 'Long-form segment';
  if (source === 'linkedin_workspace.feed_quote') return 'Workspace approval';
  if (source === 'brain.persona.ui') return 'Brain review';
  return source.replace(/[_./-]+/g, ' ');
}

function humanizeBeliefRelation(value: string | null) {
  if (!value) return 'Unknown relation';
  if (value === 'agreement') return 'Agreement';
  if (value === 'qualified_agreement') return 'Qualified agreement';
  if (value === 'disagreement') return 'Disagreement';
  if (value === 'translation') return 'Translation';
  if (value === 'experience_match') return 'Experience match';
  if (value === 'system_translation') return 'System translation';
  return value.replace(/[_-]+/g, ' ');
}

function humanizeResponseKind(value: 'agree' | 'disagree' | 'nuance' | 'story' | 'language') {
  if (value === 'agree') return 'Agreement';
  if (value === 'disagree') return 'Disagreement';
  if (value === 'nuance') return 'Nuance';
  if (value === 'story') return 'Personal story';
  return 'Wording';
}

function humanizeSavedResponseKind(value: string) {
  if (value === 'agree' || value === 'disagree' || value === 'nuance' || value === 'story' || value === 'language') {
    return humanizeResponseKind(value);
  }
  return value.replace(/[_-]+/g, ' ');
}

function inferDocGroup(path: string) {
  if (path.startsWith('SOPs/')) return 'Operating Docs';
  if (path.startsWith('docs/')) return 'System Docs';
  if (path.startsWith('knowledge/persona/')) return 'Persona Bundle';
  if (path.startsWith('knowledge/aiclone/')) return 'Knowledge Docs';
  if (path.startsWith('workspaces/')) return 'Workspace Reference';
  return 'Reference Docs';
}

function mergeBrainDocs(docs: DocEntry[], workspaceSnapshot: BrainWorkspaceSnapshot | null) {
  const registry = new Map<string, DocEntry>();
  for (const doc of docs) {
    registry.set(doc.path, {
      ...doc,
      group: doc.group ?? inferDocGroup(doc.path),
    });
  }
  for (const doc of workspaceSnapshot?.doc_entries ?? []) {
    registry.set(doc.path, {
      name: doc.name,
      path: doc.path,
      snippet: doc.snippet,
      content: doc.content,
      updatedAt: doc.updatedAt,
      group: inferDocGroup(doc.path),
    });
  }
  for (const file of workspaceSnapshot?.workspace_files ?? []) {
    const group = file.group ?? '';
    const shouldInclude =
      group.startsWith('persona-bundle/') ||
      group.startsWith('linkedin-content-os/docs') ||
      group.startsWith('linkedin-content-os/analytics');
    if (!shouldInclude || registry.has(file.path)) {
      continue;
    }
    registry.set(file.path, {
      name: file.name,
      path: file.path,
      snippet: file.snippet,
      content: file.content,
      updatedAt: file.updatedAt,
      group: group.startsWith('persona-bundle/') ? 'Persona Bundle' : 'Workspace Reference',
    });
  }
  return Array.from(registry.values()).sort((left, right) => left.path.localeCompare(right.path));
}
