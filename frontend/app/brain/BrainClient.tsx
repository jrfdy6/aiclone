'use client';

import { useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { getApiUrl } from '@/lib/api-client';

export type DocEntry = {
  name: string;
  path: string;
  snippet: string;
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

type Automation = {
  id: string;
  name: string;
  schedule: string;
  status: string;
  channel: string;
  last_run_at?: string;
  next_run_at?: string;
};

type CaptureTelemetry = {
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

type PersonaDeltaEntry = {
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

type PromotionItemKind = 'talking_point' | 'framework' | 'anecdote' | 'phrase_candidate' | 'stat';

type PromotionItem = {
  id: string;
  kind: PromotionItemKind;
  label: string;
  content: string;
  evidence: string | null;
  targetFile: string | null;
};

type CaptureResponsePayload = {
  capture_id: string;
  chunk_ids: string[];
  chunk_count: number;
  expires_at?: string | null;
};

type Tab = 'dashboard' | 'briefs' | 'persona' | 'automations' | 'docs';

const API_URL = getApiUrl();

export default function BrainClient({ docs, personaWorkspace }: { docs: DocEntry[]; personaWorkspace: PersonaWorkspace }) {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [briefs, setBriefs] = useState<DailyBriefEntry[]>([]);
  const [selectedBrief, setSelectedBrief] = useState<DailyBriefEntry | null>(null);
  const [briefsError, setBriefsError] = useState<string | null>(null);
  const [personaDeltas, setPersonaDeltas] = useState<PersonaDeltaEntry[]>([]);
  const [personaDeltasError, setPersonaDeltasError] = useState<string | null>(null);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [automationsError, setAutomationsError] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<CaptureTelemetry | null>(null);
  const [telemetryHealth, setTelemetryHealth] = useState<OpenBrainHealth | null>(null);
  const [telemetryError, setTelemetryError] = useState<string | null>(null);
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

  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      const [briefsRes, personaRes, automationsRes, telemetryRes, healthRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/briefs/?limit=50`).then((res) => res.json()),
        fetch(`${API_URL}/api/persona/deltas?limit=100&view=brain_queue`).then((res) => res.json()),
        fetch(`${API_URL}/api/automations/`).then((res) => res.json()),
        fetch(`${API_URL}/api/analytics/open-brain`).then((res) => res.json()),
        fetch(`${API_URL}/api/open-brain/health`).then((res) => res.json()),
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

      if (automationsRes.status === 'fulfilled') {
        setAutomations(Array.isArray(automationsRes.value?.data) ? automationsRes.value.data : []);
        setAutomationsError(null);
      } else {
        console.error('Failed to load automations', automationsRes.reason);
        setAutomationsError('Unable to load automations right now.');
      }

      if (telemetryRes.status === 'fulfilled') {
        setTelemetry(telemetryRes.value ?? null);
      } else {
        console.error('Failed to load Open Brain telemetry', telemetryRes.reason);
      }

      if (healthRes.status === 'fulfilled') {
        setTelemetryHealth(healthRes.value ?? null);
      } else {
        console.error('Failed to load Open Brain health', healthRes.reason);
      }

      if (telemetryRes.status === 'fulfilled' && healthRes.status === 'fulfilled') {
        setTelemetryError(null);
      } else {
        setTelemetryError('Unable to load full Open Brain telemetry.');
      }
    }
    loadData();
    const interval = setInterval(loadData, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <RuntimePage module="brain" tabs={tabs}>
      {activeTab === 'dashboard' && (
        <DashboardPanel
          briefCount={briefs.length}
          docCount={docs.length}
          automationCount={automations.length}
          telemetry={telemetry}
          telemetryHealth={telemetryHealth}
          telemetryError={telemetryError}
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
        />
      )}
      {activeTab === 'automations' && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <CaptureTelemetryPanel metrics={telemetry} health={telemetryHealth} error={telemetryError} />
          <AutomationsPanel automations={automations} error={automationsError} />
        </section>
      )}
      {activeTab === 'docs' && <DocsPanel docs={docs} />}
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
}: {
  briefCount: number;
  docCount: number;
  automationCount: number;
  telemetry: CaptureTelemetry | null;
  telemetryHealth: OpenBrainHealth | null;
  telemetryError: string | null;
}) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <HeroBlock briefCount={briefCount} docCount={docCount} automationCount={automationCount} />
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
  return (
    <section style={{ display: 'flex', gap: '16px', borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', minHeight: '460px' }}>
      <div style={{ width: '260px', borderRight: '1px solid #0f172a', paddingRight: '12px', maxHeight: '420px', overflowY: 'auto' }}>
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
      <div style={{ flex: 1 }}>
        {selected ? (
          <div>
            <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '4px' }}>{selected.brief_date}</p>
            <h2 style={{ color: 'white', fontSize: '24px', marginBottom: '8px' }}>{selected.title}</h2>
            {selected.summary && <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '12px' }}>{selected.summary}</p>}
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

function PersonaPanel({
  packs,
  deltas,
  error,
}: {
  packs: PersonaPack[];
  deltas: PersonaDeltaEntry[];
  error: string | null;
}) {
  const [completedDeltaIds, setCompletedDeltaIds] = useState<string[]>([]);
  const [showMutedActive, setShowMutedActive] = useState(false);
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
  const [selectedPromotionItemIds, setSelectedPromotionItemIds] = useState<string[]>([]);
  const selectedPromotionItems = useMemo(
    () => selectableItems.filter((item) => selectedPromotionItemIds.includes(item.id)),
    [selectableItems, selectedPromotionItemIds],
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
        items: workspaceSavedDeltas.slice(0, 5),
        tone: '#22c55e',
      },
      {
        key: 'pending_promotion',
        title: 'Queued For Promotion',
        description: 'Reviewed in Brain and holding selected canonical items for later promotion.',
        count: pendingPromotionDeltas.length,
        items: pendingPromotionDeltas.slice(0, 5),
        tone: '#38bdf8',
      },
      {
        key: 'committed',
        title: 'Committed',
        description: 'Already written into canonical persona files.',
        count: committedDeltas.length,
        items: committedDeltas.slice(0, 5),
        tone: '#818cf8',
      },
      {
        key: 'resolved',
        title: 'Resolved / Replaced',
        description: 'Historical items that were handled, superseded, or intentionally cleared.',
        count: resolvedHistoryDeltas.length,
        items: resolvedHistoryDeltas.slice(0, 5),
        tone: '#64748b',
      },
    ],
    [committedDeltas, pendingPromotionDeltas, resolvedHistoryDeltas, workspaceSavedDeltas],
  );

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

  function queueTemplate(kind: 'agree' | 'nuance' | 'story' | 'language') {
    if (!selectedDelta) {
      return;
    }
    const prefix =
      kind === 'agree'
        ? `What I agree with about "${selectedDelta.trait}":\n- `
        : kind === 'nuance'
        ? `Nuance I want preserved for "${selectedDelta.trait}":\n- `
        : kind === 'story'
        ? `Story or example that should shape "${selectedDelta.trait}":\n- `
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
          status: mode === 'approved' ? 'approved' : keepSelectableSourceOpen ? 'in_review' : 'reviewed',
          metadata: {
            review_state: mode === 'approved' ? 'approved' : keepSelectableSourceOpen ? 'in_review' : 'reviewed',
            review_source: 'brain.persona.ui',
            last_reviewed_at: new Date().toISOString(),
            resolution_capture_id: result.capture_id,
            pending_promotion: mode === 'approved' && selectedPromotionItems.length > 0,
            owner_response_excerpt: trimmedReflection.slice(0, 4000),
            selected_promotion_items: selectedPromotionItems,
            selected_promotion_item_ids: selectedPromotionItems.map((item) => item.id),
            selected_promotion_count: selectedPromotionItems.length,
          },
        };
        const reviewResponse = await fetch(`${API_URL}/api/persona/deltas/${selectedDelta.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(reviewPayload),
        });
        if (!reviewResponse.ok) {
          const detail = await reviewResponse.text();
          throw new Error(detail || `Persona review update failed with ${reviewResponse.status}`);
        }
      }
      const nextQueue = selectedDelta ? reviewQueue.filter((delta) => delta.id !== selectedDelta.id) : reviewQueue;
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
    <section style={{ display: 'flex', flexDirection: 'column', gap: '12px', height: 'calc(100vh - 250px)', minHeight: 'calc(100vh - 250px)', overflow: 'hidden' }}>
      <section
        style={{
          flex: 1,
          minHeight: 0,
          borderRadius: '18px',
          border: '1px solid #1f2937',
          backgroundColor: '#050b19',
          padding: '18px',
          display: 'grid',
          gridTemplateRows: 'auto minmax(0, 1fr)',
          gap: '14px',
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

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <ReviewMetaChip label="Active" value={String(totalPendingCount)} tone="#38bdf8" />
          <ReviewMetaChip label="Primary" value={String(pendingCount)} tone="#0ea5e9" />
          <ReviewMetaChip label="Muted" value={String(mutedCount)} tone="#64748b" />
          <ReviewMetaChip label="Promotion Ready" value={String(promotionReadyCount)} tone="#f59e0b" />
          <ReviewMetaChip label="Workspace Saved" value={String(workspaceSavedDeltas.length)} tone="#22c55e" />
          <ReviewMetaChip label="Queued" value={String(pendingPromotionDeltas.length)} tone="#f59e0b" />
          <ReviewMetaChip label="Committed" value={String(committedDeltas.length)} tone="#818cf8" />
          <ReviewMetaChip label="History" value={String(resolvedHistoryDeltas.length)} tone="#64748b" />
        </div>

        {primaryActiveReviewDeltas.length > 0 && mutedActiveReviewDeltas.length > 0 && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: '12px',
              alignItems: 'center',
              flexWrap: 'wrap',
              padding: '12px 14px',
              borderRadius: '14px',
              border: '1px solid #1f2937',
              backgroundColor: '#020617',
            }}
          >
            <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
              Lower-confidence long-form items are muted by default so the active queue stays focused on the strongest review work first.
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
              }}
            >
              {showMutedActive ? `Hide muted (${mutedCount})` : `Show muted (${mutedCount})`}
            </button>
          </div>
        )}

        {reviewQueue.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
            {visibleActiveReviewDeltas.map(({ delta, muted, promotionReady, promotionCandidateCount, score }) => {
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
                  <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600, marginBottom: '6px', lineHeight: 1.45 }}>{truncateText(delta.trait, 120)}</p>
                  <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>{metadataText(delta.metadata, 'target_file') ?? 'Target file not assigned'}</p>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                    <InlineBadge label={humanizeReviewSource(metadataText(delta.metadata, 'review_source'))} tone="#64748b" />
                    <InlineBadge label={`score ${score}`} tone={muted ? '#64748b' : '#38bdf8'} />
                    <InlineBadge label={`${promotionCandidateCount} promo`} tone={promotionCandidateCount > 0 ? '#818cf8' : '#64748b'} />
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
        )}

        {selectedDelta ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.08fr) minmax(320px, 0.92fr)', gap: '14px', minHeight: 0 }}>
            <section style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px', display: 'grid', gridTemplateRows: 'auto auto minmax(0, 1fr)', gap: '12px', minHeight: 0 }}>
              <div>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Why I am showing this</p>
                <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.65 }}>{reviewReason}</p>
              </div>

              <div style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.6 }}>
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
                <InlineBadge
                  label={`${selectableItems.length} canonical candidate${selectableItems.length === 1 ? '' : 's'}`}
                  tone={selectableItems.length > 0 ? '#818cf8' : '#64748b'}
                />
                {selectedScoredDelta?.muted && <InlineBadge label="Muted long-form item" tone="#64748b" />}
                {selectedScoredDelta && <InlineBadge label={`Priority ${selectedScoredDelta.score}`} tone="#22c55e" />}
              </div>

              <div style={{ minHeight: 0, overflowY: 'auto', paddingRight: '4px' }}>
                <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>What is being proposed</p>
                <p style={{ color: '#e2e8f0', fontSize: '14px', lineHeight: 1.7, whiteSpace: 'pre-wrap', marginBottom: '16px' }}>
                  {selectedDelta.notes || 'No candidate notes were attached to this review item.'}
                </p>
                {selectableItems.length > 0 && (
                  <>
                    <div style={{ height: '1px', backgroundColor: '#1f2937', marginBottom: '16px' }} />
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'baseline', marginBottom: '10px', flexWrap: 'wrap' }}>
                      <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Select what is canonical-worthy</p>
                      <p style={{ color: '#64748b', fontSize: '12px' }}>
                        {selectedPromotionItems.length} selected for promotion
                      </p>
                    </div>
                    <div style={{ display: 'grid', gap: '10px', marginBottom: '16px' }}>
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
                              padding: '12px',
                              cursor: 'pointer',
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
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', marginBottom: '6px' }}>
                                  <div>
                                    <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 600 }}>{item.label}</p>
                                    <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{humanizePromotionKind(item.kind)}</p>
                                  </div>
                                </div>
                                <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55 }}>{item.content}</p>
                                {item.evidence && <p style={{ color: '#64748b', fontSize: '12px', marginTop: '6px' }}>Evidence: {item.evidence}</p>}
                              </div>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </>
                )}
                <div style={{ height: '1px', backgroundColor: '#1f2937', marginBottom: '16px' }} />
                <p style={{ color: '#818cf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>Current canonical context</p>
                {activeContext ? (
                  <>
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>{activeContextPath ?? 'Canonical bundle excerpt'}</p>
                    <pre style={{ margin: 0, color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
                      {truncateText(activeContext, 2200)}
                    </pre>
                  </>
                ) : (
                  <p style={{ color: '#475569', fontSize: '13px', lineHeight: 1.55 }}>
                    There is no canonical excerpt attached yet. Use your response to say where this belongs and how it should be phrased.
                  </p>
                )}
              </div>
            </section>

            <section style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '16px', display: 'grid', gridTemplateRows: 'auto minmax(0, 1fr) auto', gap: '12px', minHeight: 0 }}>
              <div style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.6 }}>
                {selectableItems.length > 0
                  ? `${reviewAsk} Select the canonical-worthy pieces below, then queue them for promotion when your wording is ready.`
                  : `${reviewAsk} This item is not promotion-ready yet, so focus on your agreement, nuance, story context, or wording.`}
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
                  minHeight: 0,
                  resize: 'none',
                  borderRadius: '14px',
                  border: '1px solid #1f2937',
                  backgroundColor: '#010617',
                  color: '#e2e8f0',
                  padding: '14px',
                  fontSize: '14px',
                  lineHeight: 1.6,
                  outline: 'none',
                }}
              />

              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <QuickFillButton label="Agree" onClick={() => queueTemplate('agree')} />
                  <QuickFillButton label="Nuance" onClick={() => queueTemplate('nuance')} />
                  <QuickFillButton label="Story" onClick={() => queueTemplate('story')} />
                  <QuickFillButton label="Wording" onClick={() => queueTemplate('language')} />
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
      </section>

      <section style={{ borderRadius: '18px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '18px', display: 'grid', gap: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <p style={{ color: '#818cf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Persona Lifecycle</p>
            <h3 style={{ color: 'white', fontSize: '22px', margin: '4px 0 8px' }}>Saved and historical items</h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6 }}>
              Active review stays above. Everything below is already saved, queued, committed, or resolved so you can audit state without confusing it with the work that still needs judgment.
            </p>
          </div>
          <div style={{ color: '#64748b', fontSize: '12px', textAlign: 'right', maxWidth: '360px' }}>
            Brain should answer one question clearly: what still needs your attention right now versus what the system has already handled.
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          {lifecycleGroups.map((group) => (
            <div key={group.key} style={{ borderRadius: '14px', border: '1px solid #1f2937', backgroundColor: '#020617', padding: '14px', display: 'grid', gap: '10px' }}>
              <div>
                <p style={{ color: group.tone, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{group.title}</p>
                <p style={{ color: '#e2e8f0', fontSize: '28px', fontWeight: 700, margin: '4px 0 6px' }}>{group.count}</p>
                <p style={{ color: '#64748b', fontSize: '12px', lineHeight: 1.55 }}>{group.description}</p>
              </div>
              <div style={{ display: 'grid', gap: '8px' }}>
                {group.items.length === 0 ? (
                  <p style={{ color: '#475569', fontSize: '12px' }}>Nothing in this state right now.</p>
                ) : (
                  group.items.map((item) => (
                    <div key={item.id} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '10px', backgroundColor: '#0b1220' }}>
                      <p style={{ color: '#cbd5f5', fontSize: '12px', lineHeight: 1.5, marginBottom: '6px' }}>{truncateText(item.trait, 110)}</p>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <span style={{ color: '#64748b', fontSize: '11px' }}>{humanizeReviewSource(metadataText(item.metadata, 'review_source'))}</span>
                        <span style={{ color: '#94a3b8', fontSize: '11px' }}>{formatTimestamp(new Date(item.created_at))}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
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
        borderRadius: '999px',
        border: `1px solid ${tone}44`,
        backgroundColor: `${tone}18`,
        color: tone,
        padding: '4px 8px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
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

function AutomationsPanel({ automations, error }: { automations: Automation[]; error: string | null }) {
  if (error) {
    return <p style={{ color: '#f87171' }}>{error}</p>;
  }
  const hasRows = automations.length > 0;
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Automations</p>
        <p style={{ color: '#64748b', fontSize: '13px' }}>Same manifest that powers Ops → Cron Jobs.</p>
      </div>
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
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px' }}>
      <div style={{ marginBottom: '12px' }}>
        <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Documentation</p>
        <p style={{ color: '#64748b', fontSize: '13px' }}>Primary knowledge files from knowledge/aiclone/.</p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {docs.length === 0 && <p style={{ color: '#475569' }}>No documentation found.</p>}
        {docs.map((doc) => (
          <div key={doc.path} style={{ borderRadius: '14px', border: '1px solid #1f2937', padding: '16px', backgroundColor: '#0f172a' }}>
            <h3 style={{ color: 'white', fontSize: '16px', marginBottom: '8px' }}>{doc.name}</h3>
            <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '12px' }}>{doc.snippet}</p>
            <a href={`/${doc.path}`} style={{ color: '#38bdf8', fontSize: '13px' }}>Open file ↗</a>
          </div>
        ))}
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

function metadataText(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
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
  const pushItem = (kind: PromotionItemKind, label: string, content: string, evidence?: string | null) => {
    const normalizedContent = content.trim();
    if (!normalizedContent) return;
    items.push({
      id: stablePromotionItemId(kind, label, normalizedContent),
      kind,
      label,
      content: normalizedContent,
      evidence: evidence?.trim() || null,
      targetFile,
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
