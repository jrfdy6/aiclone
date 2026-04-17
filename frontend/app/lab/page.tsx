'use client';

import { useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { getApiUrl } from '@/lib/api-client';
import { formatUiTimestamp } from '@/lib/ui-dates';

const API_URL = getApiUrl();

type Automation = {
  id: string;
  name: string;
  status: string;
  channel: string;
  last_run_at?: string;
  next_run_at?: string;
};

type Tab = 'foundry' | 'prototypes' | 'buildLogs';

type LabExperiment = {
  id: string;
  title: string;
  belongs_to_workspace: string;
  surface: string;
  status: string;
  hypothesis: string;
  coverage?: {
    lanes?: { id: string; label: string }[];
    response_modes?: string[];
    source_probes?: number;
  };
  goal: { metric: string; target_lte: number; unit: string };
  stage_catalog: {
    id: string;
    label: string;
    section?: string;
    description: string;
    possible_failures: string[];
  }[];
  loop: { id: string; label: string; status: string }[];
  current: {
    summary: string;
    probe_count: number;
    structural_fallback_rate: number | null;
    legacy_fallback_rate: number | null;
    provider_fallback_rate: number | null;
    weak_output_rate?: number | null;
    missing_stage_rate?: number | null;
    metric_cards?: {
      id: string;
      label: string;
      value: number | null;
      tone: string;
    }[];
    stage_breakdown: Record<string, number>;
    stage_health: {
      id: string;
      label: string;
      section?: string;
      description: string;
      possible_failures: string[];
      counts: Record<string, number>;
      top_failure_reasons: string[];
    }[];
    top_failure_modes: string[];
  };
  sample_runs: {
    topic: string;
    audience: string;
    generation_strategy: string;
    llm_request_count?: number | null;
    platform?: string;
    source_type?: string;
    structural_fallbacks: string[];
    top_warnings: string[];
    stage_results: {
      id: string;
      label: string;
      section?: string;
      status: string;
      reason: string;
      detail: string;
      score?: number | null;
      evidence?: string[];
      missing_fields?: string[];
    }[];
    top_option_preview: string;
    golden_benchmark?: {
      id: string;
      label: string;
      topic: string;
      audience: string;
      description?: string;
      status: string;
      score: number;
      minimum_score: number;
      required_checks_total: number;
      required_checks_passed_count: number;
      required_checks_passed: boolean;
      anchor_hits?: number;
      anchor_group_total?: number;
      top_warnings: string[];
      summary: string;
      checks: {
        id: string;
        label: string;
        status: string;
        detail: string;
        weight: number;
        required: boolean;
      }[];
    };
    signal_snapshot?: {
      source_channel?: string;
      source_class?: string;
      unit_kind?: string;
      response_modes?: string[];
      topic_tags?: string[];
      core_claim?: string;
      supporting_claims?: string[];
      why_it_matters?: string;
      role_alignment?: string;
      expected_handoff_lane?: string;
      actual_handoff_lane?: string;
      primary_route?: string;
      lane_hint?: string;
      handoff_reason?: string;
      target_file?: string;
      secondary_consumers?: string[];
    };
    matrix_rows?: {
      lane_id: string;
      label: string;
      comment_status: string;
      comment_reason: string;
      comment_detail: string;
      comment_preview: string;
      repost_status: string;
      repost_reason: string;
      repost_detail: string;
      repost_preview: string;
      top_warnings: string[];
      evaluation_overall?: number | null;
      benchmark_score?: number | null;
      role_safety?: string;
      belief_used?: string;
      belief_summary?: string;
      experience_anchor?: string;
      experience_summary?: string;
      stance?: string;
      agreement_level?: string;
      source_takeaway?: string;
      source_takeaway_origin?: string;
      source_takeaway_strategy?: string;
      techniques?: string[];
      technique_reason?: string;
      response_type?: string;
      article_understanding?: Record<string, unknown>;
      persona_retrieval?: Record<string, unknown>;
      johnnie_perspective?: Record<string, unknown>;
      reaction_brief?: Record<string, unknown>;
      response_type_packet?: Record<string, unknown>;
      composition_traces?: Record<string, unknown>;
      stage_evaluation?: Record<string, unknown>;
      evaluation?: Record<string, number | string | boolean | null | undefined>;
      expression_assessment?: Record<string, unknown>;
      context_snapshot?: Record<string, unknown>;
    }[];
  }[];
  live_samples?: {
    topic: string;
    segment_text?: string;
    audience: string;
    generation_strategy: string;
    llm_request_count?: number | null;
    platform?: string;
    source_type?: string;
    structural_fallbacks: string[];
    top_warnings: string[];
    stage_results: {
      id: string;
      label: string;
      section?: string;
      status: string;
      reason: string;
      detail: string;
      score?: number | null;
      evidence?: string[];
      missing_fields?: string[];
    }[];
    top_option_preview: string;
    signal_snapshot?: {
      source_channel?: string;
      source_class?: string;
      unit_kind?: string;
      response_modes?: string[];
      topic_tags?: string[];
      core_claim?: string;
      supporting_claims?: string[];
      why_it_matters?: string;
      role_alignment?: string;
      expected_handoff_lane?: string;
      actual_handoff_lane?: string;
      primary_route?: string;
      lane_hint?: string;
      handoff_reason?: string;
      target_file?: string;
      secondary_consumers?: string[];
      source_path?: string;
      source_url?: string;
    };
  }[];
  live_audit?: {
    source: string;
    generated_at?: string | null;
    asset_count: number;
    candidate_count: number;
    segments_total: number;
    quality_metrics: {
      summary_coverage_rate: number;
      structured_summary_rate: number;
      lesson_coverage_rate: number;
      anecdote_coverage_rate: number;
      quote_coverage_rate: number;
      noisy_summary_rate: number;
      package_readiness_rate: number;
    };
    deep_harvest_metrics: {
      total_fragments: number;
      average_fragments_per_asset: number;
      persona_candidate_rate: number;
      canon_candidate_rate: number;
      post_candidate_rate: number;
      route_to_pm_rate: number;
      voice_guidance_only_rate?: number;
      persona_recommendation_rate?: number;
      canon_suggestion_rate?: number;
      source_only_recommendation_rate?: number;
    };
    origin_breakdown?: Record<
      string,
      {
        asset_count: number;
        quality_metrics: {
          summary_coverage_rate: number;
          structured_summary_rate: number;
          lesson_coverage_rate: number;
          anecdote_coverage_rate: number;
          quote_coverage_rate: number;
          noisy_summary_rate: number;
          package_readiness_rate: number;
        };
        issue_counts?: Record<string, number>;
        deep_harvest_fragments?: number;
      }
    >;
    slice_counts: {
      handoff_lane_counts: Record<string, number>;
      primary_route_counts: Record<string, number>;
      channel_counts: Record<string, number>;
      target_file_counts: Record<string, number>;
      origin_counts?: Record<string, number>;
      summary_origin_counts: Record<string, number>;
      transcript_note_kind_counts?: Record<string, number>;
      persona_use_mode_counts?: Record<string, number>;
      issue_counts: Record<string, number>;
      fragment_type_counts: Record<string, number>;
      fragment_lane_counts: Record<string, number>;
      fragment_recommendation_counts?: Record<string, number>;
      fragment_source_section_counts: Record<string, number>;
    };
    top_issues: { id: string; label: string; count: number }[];
    candidate_samples: {
      topic: string;
      audience: string;
      generation_strategy: string;
      llm_request_count?: number | null;
      platform?: string;
      source_type?: string;
      structural_fallbacks: string[];
      top_warnings: string[];
      stage_results: {
        id: string;
        label: string;
        section?: string;
        status: string;
        reason: string;
        detail: string;
        score?: number | null;
        evidence?: string[];
        missing_fields?: string[];
      }[];
      segment_text?: string;
      top_option_preview: string;
      signal_snapshot?: {
        source_channel?: string;
        source_class?: string;
        unit_kind?: string;
        response_modes?: string[];
        topic_tags?: string[];
        source_origin?: string;
        core_claim?: string;
        supporting_claims?: string[];
        why_it_matters?: string;
        role_alignment?: string;
        actual_handoff_lane?: string;
        primary_route?: string;
        lane_hint?: string;
        handoff_reason?: string;
        target_file?: string;
        secondary_consumers?: string[];
        source_path?: string;
        source_url?: string;
      };
    }[];
    asset_samples: {
      title: string;
      source_channel?: string;
      source_type?: string;
      source_path?: string;
      source_url?: string;
      origin?: string;
      origin_detail?: string;
      summary?: string;
      summary_origin?: string;
      transcript_note_kind?: string;
      persona_use_mode?: string;
      voice_signal_priority?: string;
      structured_summary?: string;
      lessons_learned?: string[];
      key_anecdotes?: string[];
      reusable_quotes?: string[];
      open_questions?: string[];
      quality_flags?: string[];
      word_count?: number | null;
      clean_word_count?: number | null;
      sentence_count?: number | null;
      deep_harvest_counts?: {
        total?: number;
        by_type?: Record<string, number>;
        by_handoff_lane?: Record<string, number>;
        by_recommendation?: Record<string, number>;
        by_source_section?: Record<string, number>;
        canon_candidate_count?: number;
        persona_candidate_count?: number;
        post_candidate_count?: number;
        voice_guidance_only_count?: number;
        persona_recommendation_count?: number;
        canon_suggestion_count?: number;
      };
      top_fragments?: {
        text?: string;
        primary_type?: string;
        labels?: string[];
        source_section?: string;
        score?: number;
        likely_handoff_lane?: string;
        promotion_recommendation?: string;
        promotion_reason?: string;
      }[];
    }[];
    fragment_samples: {
      text: string;
      primary_type: string;
      labels: string[];
      score: number;
      word_count: number;
      likely_handoff_lane: string;
      promotion_recommendation?: string;
      promotion_reason?: string;
      source_section: string;
      asset_title: string;
      asset_source_path?: string;
      asset_source_channel?: string;
      asset_origin?: string;
      asset_transcript_note_kind?: string;
      asset_persona_use_mode?: string;
      asset_voice_signal_priority?: string;
    }[];
  };
  pipeline_audit?: {
    generated_at?: string | null;
    request?: {
      topic?: string;
      context?: string;
      content_type?: string;
      category?: string;
      tone?: string;
      audience?: string;
    };
    issue_count: number;
    high_issue_count: number;
    snapshot_drift_count: number;
    source_mode_collapse_count: number;
    retrieval_reach_count: number;
    issue_counts: Record<string, number>;
    issues: {
      severity: string;
      phase: string;
      summary: string;
      details?: Record<string, unknown>;
    }[];
    phase_health: {
      id: string;
      label: string;
      description: string;
      status: string;
      issue_count: number;
      issue_counts: Record<string, number>;
      top_issue_summaries: string[];
      detail_lines: string[];
    }[];
    source_modes: {
      id: string;
      label: string;
      grounding_mode?: string | null;
      grounding_reason?: string | null;
      retrieval_support_count: number;
      canonical_bundle_count: number;
      reservoir_candidate_count: number;
      content_reservoir_chunk_count: number;
      example_count: number;
      primary_claims: string[];
    }[];
    snapshot_cards: {
      id: string;
      label: string;
      value: number;
      tone: string;
    }[];
  };
  golden_evaluation?: {
    generated_at?: string;
    total: number;
    publishable_count: number;
    close_count: number;
    fail_count: number;
    missing_count?: number;
    publishable_rate: number;
    close_rate: number;
    fail_rate: number;
    average_score: number;
    floor_score: number;
    hard_fail_count: number;
    summary: string;
    metric_cards: {
      id: string;
      label: string;
      value: number | null;
      tone: string;
    }[];
    rows: {
      id: string;
      label: string;
      topic: string;
      audience: string;
      description?: string;
      status: string;
      score: number;
      minimum_score: number;
      required_checks_total: number;
      required_checks_passed_count: number;
      required_checks_passed: boolean;
      anchor_hits?: number;
      anchor_group_total?: number;
      top_warnings: string[];
      summary: string;
      checks: {
        id: string;
        label: string;
        status: string;
        detail: string;
        weight: number;
        required: boolean;
      }[];
    }[];
  };
  history: {
    run_id: string;
    started_at: string;
    structural_fallback_rate: number;
    legacy_fallback_rate: number;
    provider_fallback_rate: number;
    weak_output_rate?: number;
  }[];
  next_action: string;
  ship_target: string;
  last_run_at?: string;
};

export default function LabPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [experiments, setExperiments] = useState<LabExperiment[]>([]);
  const [activeExperimentId, setActiveExperimentId] = useState<string | null>(null);
  const [runningExperimentId, setRunningExperimentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('buildLogs');

  useEffect(() => {
    let cancelled = false;
    async function loadAutomations() {
      try {
        const res = await fetch(`${API_URL}/api/automations/`);
        const data = await res.json();
        if (!cancelled) {
          setAutomations(Array.isArray(data?.data) ? data.data : []);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load automations', err);
          setError('Unable to load automations right now.');
        }
      }
    }
    loadAutomations();
    const interval = setInterval(loadAutomations, 60_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadExperiments() {
      try {
        const res = await fetch(`${API_URL}/api/lab/experiments`);
        const data = await res.json();
        if (!cancelled) {
          const nextExperiments = Array.isArray(data?.experiments) ? data.experiments : [];
          setExperiments(nextExperiments);
          setActiveExperimentId((current) => current ?? nextExperiments[0]?.id ?? null);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load lab experiments', err);
          setError('Unable to load Lab experiments right now.');
        }
      }
    }
    loadExperiments();
    return () => {
      cancelled = true;
    };
  }, []);

  async function runExperiment(experimentId: string) {
    setRunningExperimentId(experimentId);
    try {
      const res = await fetch(`${API_URL}/api/lab/experiments/${experimentId}/run`, { method: 'POST' });
      const data = await res.json();
      setExperiments((current) => {
        const remaining = current.filter((item) => item.id !== experimentId);
        return [data, ...remaining].sort((a, b) => a.title.localeCompare(b.title));
      });
      setActiveExperimentId(experimentId);
    } catch (err) {
      console.error('Failed to run lab experiment', err);
      setError('Unable to run the Lab experiment right now.');
    } finally {
      setRunningExperimentId(null);
    }
  }

  const running = automations.filter((job) => job.status?.toLowerCase() === 'active').length;
  const proposed = automations.length - running;
  const tabs = useMemo(
    () => [
      { key: 'foundry', label: 'Foundry', active: activeTab === 'foundry', onSelect: () => setActiveTab('foundry') },
      { key: 'prototypes', label: 'Prototypes', active: activeTab === 'prototypes', onSelect: () => setActiveTab('prototypes') },
      { key: 'buildLogs', label: 'Build Logs', active: activeTab === 'buildLogs', onSelect: () => setActiveTab('buildLogs') },
    ],
    [activeTab],
  );
  const selectedExperiment =
    experiments.find((item) => item.id === activeExperimentId) ??
    experiments[0] ??
    null;

  return (
    <RuntimePage module="lab" tabs={tabs}>
      <div style={{ maxWidth: '1200px' }}>
        <section
          style={{
            borderRadius: '20px',
            padding: '24px',
            background: 'linear-gradient(135deg, rgba(5,35,21,0.92), rgba(3,12,8,0.95))',
            border: '1px solid rgba(74,222,128,0.25)',
            boxShadow: '0 25px 70px rgba(0,0,0,0.55)',
            marginBottom: '24px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
            <div>
              <p style={{ color: '#34d399', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Lab</p>
              <h1 style={{ color: 'white', fontSize: '32px', margin: '4px 0' }}>Prototypes + Build Logs</h1>
              <p style={{ color: '#94a3b8', fontSize: '14px' }}>Staging-only experiments, nightly self-improvement, and append-only build history.</p>
            </div>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <HeroStat label="Running" value={running.toString()} tone="#34d399" />
              <HeroStat label="Proposed" value={proposed.toString()} tone="#fbbf24" />
            </div>
          </div>
        </section>

        {error && <p style={{ color: '#f87171' }}>{error}</p>}

        {activeTab === 'foundry' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
            <PrototypeCard running={running} proposed={proposed} />
            <ExperimentCard
              experiments={experiments}
              experiment={selectedExperiment}
              activeExperimentId={activeExperimentId}
              onSelectExperiment={setActiveExperimentId}
              runningExperimentId={runningExperimentId}
              onRunExperiment={runExperiment}
            />
          </div>
        )}
        {activeTab === 'prototypes' && <PrototypeCard running={running} proposed={proposed} />}
        {activeTab === 'buildLogs' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(320px, 0.8fr)', gap: '16px' }}>
            <ExperimentCard
              experiments={experiments}
              experiment={selectedExperiment}
              activeExperimentId={activeExperimentId}
              onSelectExperiment={setActiveExperimentId}
              runningExperimentId={runningExperimentId}
              onRunExperiment={runExperiment}
              expanded
            />
            <BuildLogCard automations={automations} expanded />
          </div>
        )}
      </div>
    </RuntimePage>
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

function PrototypeCard({ running, proposed }: { running: number; proposed: number }) {
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#04110a', padding: '20px' }}>
      <p style={{ color: '#34d399', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Prototypes</p>
      <h2 style={{ color: 'white', fontSize: '20px', marginBottom: '12px' }}>GOAT-OS initiatives</h2>
      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
        <PrototypeStat label="Running" value={running} />
        <PrototypeStat label="Proposed" value={proposed} />
      </div>
      <p style={{ color: '#94a3b8', fontSize: '13px' }}>Lab owns staging-only builds. Each run logs to Build Logs before touching prod.</p>
    </section>
  );
}

function ExperimentCard({
  experiments,
  experiment,
  activeExperimentId,
  onSelectExperiment,
  runningExperimentId,
  onRunExperiment,
  expanded = false,
}: {
  experiments: LabExperiment[];
  experiment: LabExperiment | null;
  activeExperimentId: string | null;
  onSelectExperiment: (experimentId: string) => void;
  runningExperimentId: string | null;
  onRunExperiment: (experimentId: string) => void;
  expanded?: boolean;
}) {
  const stageBreakdown = experiment?.current?.stage_breakdown ?? {};
  const stageHealth = experiment?.current?.stage_health ?? [];
  const metricCards =
    experiment?.current?.metric_cards?.length
      ? experiment.current.metric_cards
      : [
          { id: 'structural_fallback_rate', label: 'Structural Fallback', value: experiment?.current?.structural_fallback_rate ?? null, tone: '#34d399' },
          { id: 'legacy_fallback_rate', label: 'Legacy Fallback', value: experiment?.current?.legacy_fallback_rate ?? null, tone: '#f59e0b' },
          { id: 'provider_fallback_rate', label: 'Provider Failover', value: experiment?.current?.provider_fallback_rate ?? null, tone: '#38bdf8' },
          { id: 'weak_output_rate', label: 'Weak Output', value: experiment?.current?.weak_output_rate ?? null, tone: '#a78bfa' },
        ];

  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#101421', padding: '20px', minHeight: expanded ? '420px' : '220px' }}>
      {experiments.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
          {experiments.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelectExperiment(item.id)}
              style={{
                borderRadius: '999px',
                border: `1px solid ${item.id === activeExperimentId ? '#60a5fa55' : '#334155'}`,
                backgroundColor: item.id === activeExperimentId ? 'rgba(59,130,246,0.14)' : '#020617',
                color: 'white',
                fontSize: '12px',
                fontWeight: 700,
                padding: '8px 12px',
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {item.title}
            </button>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', marginBottom: '12px', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#60a5fa', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Experiment Loop</p>
          <h2 style={{ color: 'white', fontSize: '20px', marginBottom: '6px' }}>{experiment?.title ?? 'Content Fallback Observatory'}</h2>
          <p style={{ color: '#94a3b8', fontSize: '13px', maxWidth: '720px' }}>
            {experiment?.hypothesis ??
              'Use Lab to observe fallbacks, tune the weak stage, verify the result, then ship the fix back to the owning workspace.'}
          </p>
        </div>
        <button
          onClick={() => experiment && onRunExperiment(experiment.id)}
          disabled={!experiment || runningExperimentId === experiment?.id}
          style={{
            borderRadius: '12px',
            border: '1px solid rgba(96,165,250,0.45)',
            backgroundColor: 'rgba(59,130,246,0.14)',
            color: 'white',
            fontSize: '13px',
            fontWeight: 600,
            padding: '10px 14px',
            cursor: !experiment || runningExperimentId === experiment?.id ? 'not-allowed' : 'pointer',
            opacity: !experiment || runningExperimentId === experiment?.id ? 0.65 : 1,
          }}
        >
          {runningExperimentId === experiment?.id ? 'Running experiment…' : 'Run experiment'}
        </button>
      </div>

      {experiment && (
        <>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
            <InlineTone label={`Owns ${experiment.ship_target}`} tone="#f59e0b" />
            <InlineTone label={`Status ${humanizeKey(experiment.status)}`} tone="#22c55e" />
            <InlineTone label={`Target ≤ ${experiment.goal.target_lte}${experiment.goal.unit === 'percent' ? '%' : ''}`} tone="#38bdf8" />
            {experiment.last_run_at && <InlineTone label={`Last run ${formatTimestamp(new Date(experiment.last_run_at))}`} tone="#64748b" />}
          </div>

          {experiment.coverage && (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
              {experiment.coverage.lanes?.map((lane) => (
                <InlineTone key={`${experiment.id}:${lane.id}`} label={lane.label} tone="#64748b" />
              ))}
              {experiment.coverage.response_modes?.map((mode) => (
                <InlineTone key={`${experiment.id}:${mode}`} label={humanizeKey(mode)} tone="#a78bfa" />
              ))}
              {typeof experiment.coverage.source_probes === 'number' && (
                <InlineTone label={`${experiment.coverage.source_probes} source probes`} tone="#14b8a6" />
              )}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '16px' }}>
            {metricCards.map((metric) => (
              <PrototypeStat key={`${experiment.id}:${metric.id}`} label={metric.label} value={formatMetric(metric.id, metric.value)} tone={metric.tone} />
            ))}
          </div>

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
            {experiment.loop.map((step) => (
              <InlineTone key={step.id} label={`${step.label}: ${humanizeKey(step.status)}`} tone={phaseTone(step.status)} />
            ))}
          </div>

          <p style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '14px' }}>{experiment.current.summary}</p>

          <div style={{ display: 'grid', gridTemplateColumns: expanded ? 'minmax(0, 1fr)' : 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
            <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
              <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '10px' }}>Fallback Breakdown</p>
              {Object.keys(stageBreakdown).length === 0 && <p style={{ color: '#64748b', fontSize: '13px' }}>Run the experiment to collect stage-level fallback counts.</p>}
              {Object.entries(stageBreakdown).map(([key, value]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', color: '#e2e8f0', fontSize: '13px', marginBottom: '6px' }}>
                  <span>{humanizeKey(key)}</span>
                  <strong>{value}</strong>
                </div>
              ))}
              {experiment.current.top_failure_modes?.length > 0 && (
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '10px' }}>
                  Focus next on: {experiment.current.top_failure_modes.map(humanizeKey).join(', ')}
                </p>
              )}
            </div>

            <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
              <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '10px' }}>System Loop</p>
              <div style={{ display: 'grid', gap: '8px', color: '#cbd5e1', fontSize: '13px' }}>
                <p>1. Run the experiment in Lab.</p>
                <p>2. Tune the stage with the highest fallback count.</p>
                <p>3. Rerun until structural fallback is below target.</p>
                <p>4. Ship the fix back to {experiment.ship_target}.</p>
                <p>5. Write the postmortem and add the lesson to docs.</p>
              </div>
              <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '10px' }}>{experiment.next_action}</p>
            </div>
          </div>

          <div style={{ marginTop: '16px', display: 'grid', gap: '10px' }}>
            <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Content Development Stages</p>
            <div style={{ display: 'grid', gridTemplateColumns: expanded ? 'repeat(auto-fit, minmax(280px, 1fr))' : 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              {stageHealth.map((stage) => {
                const dominantStatus =
                  stage.counts.fail > 0 ? 'fail' : stage.counts.warn > 0 ? 'warn' : stage.counts.missing > 0 ? 'missing' : 'pass';
                return (
                  <div key={stage.id} style={{ borderRadius: '12px', border: `1px solid ${statusTone(dominantStatus)}55`, padding: '14px', backgroundColor: '#020617' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', marginBottom: '8px' }}>
                      <div>
                        <p style={{ color: 'white', fontWeight: 600 }}>{stage.label}</p>
                        {stage.section && <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{humanizeKey(stage.section)}</p>}
                      </div>
                      <InlineTone label={`${statusGlyph(dominantStatus)} ${humanizeKey(dominantStatus)}`} tone={statusTone(dominantStatus)} />
                    </div>
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '10px' }}>{stage.description}</p>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                      <InlineTone label={`Pass ${stage.counts.pass ?? 0}`} tone="#22c55e" />
                      <InlineTone label={`Warn ${stage.counts.warn ?? 0}`} tone="#f59e0b" />
                      <InlineTone label={`Fail ${stage.counts.fail ?? 0}`} tone="#ef4444" />
                      <InlineTone label={`Missing ${stage.counts.missing ?? 0}`} tone="#94a3b8" />
                    </div>
                    {stage.top_failure_reasons?.length > 0 && (
                      <p style={{ color: '#cbd5e1', fontSize: '12px', marginBottom: '10px' }}>
                        Current failures: {stage.top_failure_reasons.map(humanizeKey).join(', ')}
                      </p>
                    )}
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {stage.possible_failures.map((failure) => (
                        <InlineTone key={`${stage.id}:${failure}`} label={humanizeKey(failure)} tone="#64748b" />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {experiment.pipeline_audit && <ContentPipelineAuditSection audit={experiment.pipeline_audit} expanded={expanded} />}
          {experiment.golden_evaluation && <GoldenContentEvalSection evaluation={experiment.golden_evaluation} expanded={expanded} />}

          {experiment.sample_runs?.length > 0 && (
            <div style={{ marginTop: '16px', display: 'grid', gap: '10px' }}>
              <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Latest Probe Runs</p>
              {experiment.sample_runs.slice(0, expanded ? 5 : 3).map((item) => {
                const stageGroups = groupStageResults(item.stage_results || []);
                return (
                <div key={`${item.topic}:${item.audience}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#020617' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '6px' }}>
                    <p style={{ color: 'white', fontWeight: 600 }}>{item.topic}</p>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      <InlineTone label={humanizeKey(item.audience)} tone="#64748b" />
                      <InlineTone label={humanizeKey(item.generation_strategy)} tone="#38bdf8" />
                      {item.platform && <InlineTone label={humanizeKey(item.platform)} tone="#14b8a6" />}
                      {typeof item.llm_request_count === 'number' && (
                        <InlineTone label={`LLM calls ${item.llm_request_count}`} tone="#a78bfa" />
                      )}
                    </div>
                  </div>
                  {item.golden_benchmark && (
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                      <InlineTone
                        label={`Golden ${humanizeKey(item.golden_benchmark.status)}`}
                        tone={goldenTone(item.golden_benchmark.status)}
                      />
                      <InlineTone
                        label={`Score ${item.golden_benchmark.score}/${item.golden_benchmark.minimum_score}`}
                        tone="#38bdf8"
                      />
                      <InlineTone
                        label={`Required ${item.golden_benchmark.required_checks_passed_count}/${item.golden_benchmark.required_checks_total}`}
                        tone={item.golden_benchmark.required_checks_passed ? '#22c55e' : '#ef4444'}
                      />
                    </div>
                  )}
                  <p style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '8px' }}>{item.top_option_preview || 'No option preview returned.'}</p>
                  {item.signal_snapshot && (
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                      {item.signal_snapshot.source_channel && <InlineTone label={`Source ${humanizeKey(item.signal_snapshot.source_channel)}`} tone="#64748b" />}
                      {item.signal_snapshot.source_class && <InlineTone label={`Class ${humanizeKey(item.signal_snapshot.source_class)}`} tone="#475569" />}
                      {item.signal_snapshot.unit_kind && <InlineTone label={`Unit ${humanizeKey(item.signal_snapshot.unit_kind)}`} tone="#475569" />}
                      {item.signal_snapshot.expected_handoff_lane && (
                        <InlineTone label={`Expect ${humanizeKey(item.signal_snapshot.expected_handoff_lane)}`} tone="#f59e0b" />
                      )}
                      {item.signal_snapshot.actual_handoff_lane && (
                        <InlineTone
                          label={`Actual ${humanizeKey(item.signal_snapshot.actual_handoff_lane)}`}
                          tone={
                            item.signal_snapshot.expected_handoff_lane === item.signal_snapshot.actual_handoff_lane
                              ? '#22c55e'
                              : '#ef4444'
                          }
                        />
                      )}
                      {item.signal_snapshot.primary_route && (
                        <InlineTone label={`Route ${humanizeKey(item.signal_snapshot.primary_route)}`} tone="#38bdf8" />
                      )}
                      {item.signal_snapshot.lane_hint && (
                        <InlineTone label={`Hint ${humanizeKey(item.signal_snapshot.lane_hint)}`} tone="#a78bfa" />
                      )}
                      {(item.signal_snapshot.response_modes || []).map((mode) => (
                        <InlineTone key={`${item.topic}:${mode}`} label={humanizeKey(mode)} tone="#334155" />
                      ))}
                      {(item.signal_snapshot.secondary_consumers || []).map((consumer) => (
                        <InlineTone key={`${item.topic}:consumer:${consumer}`} label={`Feeds ${humanizeKey(consumer)}`} tone="#14b8a6" />
                      ))}
                    </div>
                  )}
                  {item.signal_snapshot?.handoff_reason && (
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>
                      {item.signal_snapshot.handoff_reason}
                    </p>
                  )}
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {(item.structural_fallbacks?.length > 0 ? item.structural_fallbacks : ['no_structural_fallbacks']).map((value) => (
                      <InlineTone key={`${item.topic}:${value}`} label={humanizeKey(value)} tone={value === 'no_structural_fallbacks' ? '#22c55e' : '#f97316'} />
                    ))}
                    {(item.top_warnings || []).slice(0, 3).map((warning) => (
                      <InlineTone key={`${item.topic}:${warning}`} label={warning} tone="#fbbf24" />
                    ))}
                  </div>
                  <div style={{ marginTop: '10px', display: 'grid', gap: '6px' }}>
                    {stageGroups.length > 0 && (
                      <>
                        <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Stage Trace</p>
                        {stageGroups.map((group) => (
                          <div key={`${item.topic}:${group.section}`} style={{ display: 'grid', gap: '6px' }}>
                            <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{humanizeKey(group.section)}</p>
                            {group.items.map((stage) => (
                              <div
                                key={`${item.topic}:${stage.id}`}
                                style={{
                                  display: 'grid',
                                  gridTemplateColumns: expanded ? '180px 110px minmax(0, 1fr)' : '150px 92px minmax(0, 1fr)',
                                  gap: '10px',
                                  alignItems: 'start',
                                  borderRadius: '10px',
                                  border: '1px solid #1f2937',
                                  backgroundColor: '#0b1120',
                                  padding: '10px',
                                }}
                              >
                                <div>
                                  <p style={{ color: 'white', fontSize: '12px', fontWeight: 600 }}>{stage.label}</p>
                                  {typeof stage.score === 'number' && <p style={{ color: '#64748b', fontSize: '11px' }}>Score {stage.score}</p>}
                                </div>
                                <InlineTone label={`${statusGlyph(stage.status)} ${humanizeKey(stage.status)}`} tone={statusTone(stage.status)} />
                                <div>
                                  <p style={{ color: '#cbd5e1', fontSize: '12px', marginBottom: '4px' }}>{humanizeKey(stage.reason)}</p>
                                  <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: expanded && ((stage.evidence?.length ?? 0) > 0 || (stage.missing_fields?.length ?? 0) > 0) ? '6px' : 0 }}>{stage.detail}</p>
                                  {expanded && (stage.evidence?.length ?? 0) > 0 && (
                                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: (stage.missing_fields?.length ?? 0) > 0 ? '6px' : 0 }}>
                                      {stage.evidence?.map((evidence) => (
                                        <InlineTone key={`${item.topic}:${stage.id}:${evidence}`} label={evidence} tone="#475569" />
                                      ))}
                                    </div>
                                  )}
                                  {expanded && (stage.missing_fields?.length ?? 0) > 0 && (
                                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                      {stage.missing_fields?.map((field) => (
                                        <InlineTone key={`${item.topic}:${stage.id}:missing:${field}`} label={`Missing ${humanizeKey(field)}`} tone="#94a3b8" />
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                  {item.matrix_rows && item.matrix_rows.length > 0 && (
                    <div style={{ marginTop: '12px', display: 'grid', gap: '8px' }}>
                      <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Lane Matrix</p>
                      {item.matrix_rows.map((row) => {
                        const articleUnderstanding = objectValue(row.article_understanding);
                        const reactionBrief = objectValue(row.reaction_brief);
                        const perspective = objectValue(row.johnnie_perspective);
                        const responseTypePacket = objectValue(row.response_type_packet);
                        const stageEvaluation = objectValue(row.stage_evaluation);
                        const personaRetrieval = objectValue(row.persona_retrieval);
                        const compositionTraces = objectValue(row.composition_traces);
                        const commentTrace = objectValue(compositionTraces.comment);
                        const repostTrace = objectValue(compositionTraces.repost);
                        const articleStance =
                          stringValue(articleUnderstanding.article_stance) || stringValue(row.context_snapshot?.article_stance);
                        const articleView =
                          stringValue(reactionBrief.article_view) || stringValue(row.context_snapshot?.article_view);
                        const johnnieView =
                          stringValue(reactionBrief.johnnie_view) || stringValue(row.context_snapshot?.johnnie_view);
                        const tension =
                          stringValue(reactionBrief.tension) || stringValue(row.context_snapshot?.tension);
                        const contentAngle =
                          stringValue(reactionBrief.content_angle) || stringValue(row.context_snapshot?.content_angle);
                        const selectedResponseType =
                          row.response_type || stringValue(responseTypePacket.response_type);
                        const personalReaction = stringValue(perspective.personal_reaction);
                        const livedAddition = stringValue(perspective.lived_addition);
                        const agreeWith = stringValue(perspective.agree_with);
                        const pushback = stringValue(perspective.pushback);
                        const articleThesis = stringValue(articleUnderstanding.thesis);
                        const worldContext = stringValue(articleUnderstanding.world_context);
                        const worldStakes = stringValue(articleUnderstanding.world_stakes);
                        const worldPosition = stringValue(articleUnderstanding.article_world_position);
                        const retrievalClaims = arrayCount(personaRetrieval.relevant_claims);
                        const retrievalStories = arrayCount(personaRetrieval.relevant_stories);
                        const retrievalInitiatives = arrayCount(personaRetrieval.relevant_initiatives);
                        const retrievalDeltas = arrayCount(personaRetrieval.relevant_deltas);
                        const shippingDecision = stringValue(stageEvaluation.shipping_decision);
                        const shipReadiness = numberValue(stageEvaluation.ship_readiness_score);
                        const retrievalCandidates = arrayCount(personaRetrieval.top_candidates);
                        const stageWarnings = stringArray(stageEvaluation.warnings);
                        const criticalMissing = stringArray(stageEvaluation.critical_missing_fields);
                        const stageMissing = stringArray(stageEvaluation.missing_fields);
                        const responseTypeReason = stringValue(responseTypePacket.type_selection_reason);
                        const humorSafety = objectValue(responseTypePacket.humor_safety);
                        const humorAllowed = booleanValue(humorSafety.humor_allowed);
                        const humorBoundary = stringValue(humorSafety.humor_boundary);
                        const commentTemplate = stringValue(commentTrace.template_family);
                        const repostTemplate = stringValue(repostTrace.template_family);
                        const commentParts = stringArray(commentTrace.selected_parts);
                        const repostParts = stringArray(repostTrace.selected_parts);
                        const articleScore = numberValue(stageEvaluation.article_understanding_score);
                        const retrievalScore = numberValue(stageEvaluation.persona_retrieval_score);
                        const perspectiveScore = numberValue(stageEvaluation.johnnie_perspective_score);
                        const briefScore = numberValue(stageEvaluation.reaction_brief_score);
                        const compositionScore = numberValue(stageEvaluation.template_composition_score);
                        const responseTypeScore = numberValue(stageEvaluation.response_type_score);
                        const humorScore = numberValue(stageEvaluation.humor_safety_score);

                        return (
                          <div
                            key={`${item.topic}:${row.lane_id}`}
                            style={{
                              display: 'grid',
                              gridTemplateColumns: expanded ? '120px 92px 92px minmax(0, 1fr)' : '120px 84px 84px minmax(0, 1fr)',
                              gap: '10px',
                              alignItems: 'start',
                              borderRadius: '10px',
                              border: '1px solid #1f2937',
                              backgroundColor: '#0b1120',
                              padding: '10px',
                            }}
                          >
                            <p style={{ color: 'white', fontSize: '12px', fontWeight: 600 }}>{row.label}</p>
                            <InlineTone label={`Comment ${statusGlyph(row.comment_status)}`} tone={statusTone(row.comment_status)} />
                            <InlineTone label={`Repost ${statusGlyph(row.repost_status)}`} tone={statusTone(row.repost_status)} />
                            <div style={{ display: 'grid', gap: '6px' }}>
                              <p style={{ color: '#cbd5e1', fontSize: '12px' }}>
                                Comment: {humanizeKey(row.comment_reason)}. Repost: {humanizeKey(row.repost_reason)}.
                              </p>
                              {expanded && (
                                <>
                                  <p style={{ color: '#94a3b8', fontSize: '12px' }}>{row.comment_preview || 'No comment preview returned.'}</p>
                                  <p style={{ color: '#94a3b8', fontSize: '12px' }}>{row.repost_preview || 'No repost preview returned.'}</p>
                                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                    {row.stance && <InlineTone label={`Stance ${humanizeKey(row.stance)}`} tone="#38bdf8" />}
                                    {row.agreement_level && <InlineTone label={`Agreement ${humanizeKey(row.agreement_level)}`} tone="#64748b" />}
                                    {selectedResponseType && <InlineTone label={`Type ${humanizeKey(selectedResponseType)}`} tone="#a78bfa" />}
                                    {articleStance && <InlineTone label={`Article stance ${humanizeKey(articleStance)}`} tone="#14b8a6" />}
                                    {row.role_safety && <InlineTone label={`Safety ${humanizeKey(row.role_safety)}`} tone={row.role_safety === 'safe' ? '#22c55e' : '#ef4444'} />}
                                    {shippingDecision && <InlineTone label={`Ship ${humanizeKey(shippingDecision)}`} tone={shippingDecision === 'ship' ? '#22c55e' : shippingDecision === 'needs_review' ? '#f59e0b' : '#94a3b8'} />}
                                    {typeof shipReadiness === 'number' && <InlineTone label={`Readiness ${shipReadiness}`} tone="#38bdf8" />}
                                  </div>
                                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                    {typeof articleScore === 'number' && <InlineTone label={`Article ${articleScore}`} tone={scoreTone(articleScore)} />}
                                    {typeof retrievalScore === 'number' && <InlineTone label={`Retrieval ${retrievalScore}`} tone={scoreTone(retrievalScore)} />}
                                    {typeof perspectiveScore === 'number' && <InlineTone label={`Perspective ${perspectiveScore}`} tone={scoreTone(perspectiveScore)} />}
                                    {typeof briefScore === 'number' && <InlineTone label={`Brief ${briefScore}`} tone={scoreTone(briefScore)} />}
                                    {typeof compositionScore === 'number' && <InlineTone label={`Template ${compositionScore}`} tone={scoreTone(compositionScore)} />}
                                    {typeof responseTypeScore === 'number' && <InlineTone label={`Type score ${responseTypeScore}`} tone={scoreTone(responseTypeScore)} />}
                                    {typeof humorScore === 'number' && <InlineTone label={`Humor ${humorScore}`} tone={scoreTone(humorScore)} />}
                                  </div>
                                  {(row.belief_used || row.experience_anchor || articleView || johnnieView || tension || contentAngle || personalReaction) && (
                                    <div style={{ display: 'grid', gap: '4px' }}>
                                      {articleThesis && <p style={{ color: '#cbd5e1', fontSize: '12px' }}>Thesis: {articleThesis}</p>}
                                      {worldContext && <p style={{ color: '#94a3b8', fontSize: '12px' }}>World context: {worldContext}</p>}
                                      {worldStakes && <p style={{ color: '#94a3b8', fontSize: '12px' }}>World stakes: {worldStakes}</p>}
                                      {worldPosition && <p style={{ color: '#64748b', fontSize: '12px' }}>World position: {worldPosition}</p>}
                                      {row.belief_used && <p style={{ color: '#cbd5e1', fontSize: '12px' }}>Belief: {row.belief_used}</p>}
                                      {row.experience_anchor && <p style={{ color: '#94a3b8', fontSize: '12px' }}>Experience: {row.experience_anchor}{row.experience_summary ? ` — ${row.experience_summary}` : ''}</p>}
                                      {articleView && <p style={{ color: '#94a3b8', fontSize: '12px' }}>Article view: {articleView}</p>}
                                      {johnnieView && <p style={{ color: '#94a3b8', fontSize: '12px' }}>Johnnie view: {johnnieView}</p>}
                                      {tension && <p style={{ color: '#94a3b8', fontSize: '12px' }}>Tension: {tension}</p>}
                                      {contentAngle && <p style={{ color: '#94a3b8', fontSize: '12px' }}>Content angle: {humanizeKey(contentAngle)}</p>}
                                      {agreeWith && <p style={{ color: '#cbd5e1', fontSize: '12px' }}>Agree with: {agreeWith}</p>}
                                      {pushback && <p style={{ color: '#cbd5e1', fontSize: '12px' }}>Pushback: {pushback}</p>}
                                      {personalReaction && <p style={{ color: '#cbd5e1', fontSize: '12px' }}>Reaction: {personalReaction}</p>}
                                      {livedAddition && <p style={{ color: '#94a3b8', fontSize: '12px' }}>Lived addition: {livedAddition}</p>}
                                      {row.source_takeaway && <p style={{ color: '#94a3b8', fontSize: '12px' }}>Source takeaway: {row.source_takeaway}</p>}
                                      {row.source_takeaway_strategy && <p style={{ color: '#64748b', fontSize: '12px' }}>Takeaway strategy: {humanizeKey(row.source_takeaway_strategy)}</p>}
                                      {responseTypeReason && <p style={{ color: '#64748b', fontSize: '12px' }}>Type rationale: {responseTypeReason}</p>}
                                      {row.technique_reason && <p style={{ color: '#64748b', fontSize: '12px' }}>Technique reason: {row.technique_reason}</p>}
                                      {retrievalCandidates > 0 && <p style={{ color: '#64748b', fontSize: '12px' }}>Persona candidates: {retrievalCandidates}</p>}
                                      {(retrievalClaims > 0 || retrievalStories > 0 || retrievalInitiatives > 0 || retrievalDeltas > 0) && (
                                        <p style={{ color: '#64748b', fontSize: '12px' }}>
                                          Retrieval mix: claims {retrievalClaims}, stories {retrievalStories}, initiatives {retrievalInitiatives}, deltas {retrievalDeltas}
                                        </p>
                                      )}
                                      {(commentTemplate || repostTemplate) && (
                                        <p style={{ color: '#64748b', fontSize: '12px' }}>
                                          Templates: comment {commentTemplate || 'missing'}{commentParts.length ? ` (${commentParts.join(', ')})` : ''}; repost {repostTemplate || 'missing'}{repostParts.length ? ` (${repostParts.join(', ')})` : ''}
                                        </p>
                                      )}
                                      {typeof humorAllowed === 'boolean' && (
                                        <p style={{ color: '#64748b', fontSize: '12px' }}>
                                          Humor gate: {humorAllowed ? 'allowed' : 'blocked'}{humorBoundary ? ` — ${humorBoundary}` : ''}
                                        </p>
                                      )}
                                    </div>
                                  )}
                                </>
                              )}
                              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                {(row.techniques || []).map((technique) => (
                                  <InlineTone key={`${item.topic}:${row.lane_id}:technique:${technique}`} label={humanizeKey(technique)} tone="#475569" />
                                ))}
                                {row.top_warnings.map((warning) => (
                                  <InlineTone key={`${item.topic}:${row.lane_id}:${warning}`} label={warning} tone="#fbbf24" />
                                ))}
                                {typeof row.evaluation_overall === 'number' && (
                                  <InlineTone label={`Overall ${row.evaluation_overall}`} tone="#38bdf8" />
                                )}
                                {typeof row.benchmark_score === 'number' && (
                                  <InlineTone label={`Benchmark ${row.benchmark_score}`} tone="#34d399" />
                                )}
                              </div>
                              {expanded && stageWarnings.length > 0 && (
                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                  {stageWarnings.map((warning) => (
                                    <InlineTone key={`${item.topic}:${row.lane_id}:stage-warning:${warning}`} label={humanizeKey(warning)} tone="#fbbf24" />
                                  ))}
                                </div>
                              )}
                              {expanded && criticalMissing.length > 0 && (
                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                  {criticalMissing.map((field) => (
                                    <InlineTone key={`${item.topic}:${row.lane_id}:critical-missing:${field}`} label={`Critical ${humanizeKey(field)}`} tone="#ef4444" />
                                  ))}
                                </div>
                              )}
                              {expanded && criticalMissing.length === 0 && stageMissing.length > 0 && (
                                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                  {stageMissing.map((field) => (
                                    <InlineTone key={`${item.topic}:${row.lane_id}:missing:${field}`} label={`Missing ${humanizeKey(field)}`} tone="#94a3b8" />
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )})}
            </div>
          )}

          {experiment.live_audit && <LiveSourceAuditSection audit={experiment.live_audit} expanded={expanded} />}

          {!experiment.live_audit && experiment.live_samples && experiment.live_samples.length > 0 && (
            <div style={{ marginTop: '16px', display: 'grid', gap: '10px' }}>
              <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Recent Live Source Samples</p>
              {experiment.live_samples.slice(0, expanded ? 5 : 3).map((item) => (
                <div key={`live:${item.topic}:${item.top_option_preview}`} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#020617' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '6px' }}>
                    <p style={{ color: 'white', fontWeight: 600 }}>{item.topic}</p>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      <InlineTone label="Live sample" tone="#14b8a6" />
                      {item.platform && <InlineTone label={humanizeKey(item.platform)} tone="#64748b" />}
                      {item.signal_snapshot?.actual_handoff_lane && (
                        <InlineTone label={`Actual ${humanizeKey(item.signal_snapshot.actual_handoff_lane)}`} tone="#22c55e" />
                      )}
                      {item.signal_snapshot?.primary_route && (
                        <InlineTone label={`Route ${humanizeKey(item.signal_snapshot.primary_route)}`} tone="#38bdf8" />
                      )}
                    </div>
                  </div>
                  <p style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '8px' }}>{item.top_option_preview || 'No source sample returned.'}</p>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                    {item.signal_snapshot?.source_channel && <InlineTone label={`Source ${humanizeKey(item.signal_snapshot.source_channel)}`} tone="#475569" />}
                    {item.signal_snapshot?.lane_hint && <InlineTone label={`Hint ${humanizeKey(item.signal_snapshot.lane_hint)}`} tone="#a78bfa" />}
                    {item.signal_snapshot?.target_file && <InlineTone label={`Target ${item.signal_snapshot.target_file}`} tone="#334155" />}
                    {(item.signal_snapshot?.secondary_consumers || []).map((consumer) => (
                      <InlineTone key={`live:${item.topic}:${consumer}`} label={`Feeds ${humanizeKey(consumer)}`} tone="#f59e0b" />
                    ))}
                  </div>
                  {item.signal_snapshot?.handoff_reason && (
                    <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>{item.signal_snapshot.handoff_reason}</p>
                  )}
                  {item.signal_snapshot?.source_path && (
                    <p style={{ color: '#64748b', fontSize: '11px' }}>{item.signal_snapshot.source_path}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function PrototypeStat({
  label,
  value,
  tone = '#34d399',
  compact = false,
}: {
  label: string;
  value: number | string;
  tone?: string;
  compact?: boolean;
}) {
  return (
    <div style={{ flex: 1, borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#071814', padding: compact ? '10px' : '12px' }}>
      <p style={{ color: '#94a3b8', fontSize: compact ? '10px' : '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: tone, fontSize: compact ? '18px' : '22px', fontWeight: 600 }}>{value}</p>
    </div>
  );
}

function ContentPipelineAuditSection({
  audit,
  expanded = false,
}: {
  audit: NonNullable<LabExperiment['pipeline_audit']>;
  expanded?: boolean;
}) {
  return (
    <div style={{ marginTop: '16px', display: 'grid', gap: '12px' }}>
      <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
          <div>
            <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Upstream Pipeline Audit</p>
            <p style={{ color: 'white', fontSize: '16px', fontWeight: 600, marginTop: '4px' }}>Start-of-pipeline visibility for the content observatory</p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <InlineTone label={`Issues ${audit.issue_count}`} tone="#ef4444" />
            <InlineTone label={`High ${audit.high_issue_count}`} tone="#f97316" />
            <InlineTone label={`Snapshot Drift ${audit.snapshot_drift_count}`} tone="#f59e0b" />
            <InlineTone label={`Mode Collapse ${audit.source_mode_collapse_count}`} tone="#fbbf24" />
            <InlineTone label={`Retrieval Reach ${audit.retrieval_reach_count}/2`} tone="#14b8a6" />
            {audit.generated_at && <InlineTone label={`Generated ${formatTimestamp(new Date(audit.generated_at))}`} tone="#64748b" />}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
          {audit.request?.topic && <InlineTone label={`Topic ${audit.request.topic}`} tone="#38bdf8" />}
          {audit.request?.audience && <InlineTone label={`Audience ${humanizeKey(audit.request.audience)}`} tone="#a78bfa" />}
          {audit.request?.tone && <InlineTone label={`Tone ${humanizeKey(audit.request.tone)}`} tone="#14b8a6" />}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
          {audit.snapshot_cards.map((card) => (
            <PrototypeStat key={card.id} label={card.label} value={card.value} tone={card.tone} />
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: expanded ? 'repeat(auto-fit, minmax(260px, 1fr))' : 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        {audit.phase_health.map((phase) => (
          <div key={phase.id} style={{ borderRadius: '12px', border: `1px solid ${statusTone(phase.status)}55`, padding: '14px', backgroundColor: '#020617' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', marginBottom: '8px' }}>
              <div>
                <p style={{ color: 'white', fontWeight: 600 }}>{phase.label}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>{phase.description}</p>
              </div>
              <InlineTone label={`${statusGlyph(phase.status)} ${humanizeKey(phase.status)}`} tone={statusTone(phase.status)} />
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
              <InlineTone label={`Issues ${phase.issue_count}`} tone="#64748b" />
              {Object.entries(phase.issue_counts || {}).map(([severity, count]) => (
                <InlineTone key={`${phase.id}:${severity}`} label={`${humanizeKey(severity)} ${count}`} tone={severity === 'high' ? '#ef4444' : '#f59e0b'} />
              ))}
            </div>
            <div style={{ display: 'grid', gap: '4px' }}>
              {phase.detail_lines.slice(0, expanded ? 4 : 2).map((line) => (
                <p key={`${phase.id}:${line}`} style={{ color: '#cbd5e1', fontSize: '12px' }}>{line}</p>
              ))}
              {phase.top_issue_summaries.slice(0, expanded ? 3 : 1).map((summary) => (
                <p key={`${phase.id}:issue:${summary}`} style={{ color: '#fbbf24', fontSize: '12px' }}>{summary}</p>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: expanded ? 'repeat(auto-fit, minmax(280px, 1fr))' : 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        {audit.source_modes.map((mode) => (
          <div key={mode.id} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '8px' }}>
              <p style={{ color: 'white', fontWeight: 600 }}>{mode.label}</p>
              {mode.grounding_mode && <InlineTone label={humanizeKey(mode.grounding_mode)} tone="#38bdf8" />}
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
              <InlineTone label={`Retrieval ${mode.retrieval_support_count}`} tone="#14b8a6" />
              <InlineTone label={`Canon ${mode.canonical_bundle_count}`} tone="#64748b" />
              <InlineTone label={`Reservoir ${mode.reservoir_candidate_count}`} tone="#a78bfa" />
              <InlineTone label={`Curated Reservoir ${mode.content_reservoir_chunk_count}`} tone="#f59e0b" />
              <InlineTone label={`Examples ${mode.example_count}`} tone="#334155" />
            </div>
            {mode.grounding_reason && <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '8px' }}>{mode.grounding_reason}</p>}
            <div style={{ display: 'grid', gap: '6px' }}>
              {mode.primary_claims.length === 0 && <p style={{ color: '#64748b', fontSize: '12px' }}>No primary claims returned.</p>}
              {mode.primary_claims.map((claim) => (
                <p key={`${mode.id}:${claim}`} style={{ color: '#cbd5e1', fontSize: '12px' }}>{claim}</p>
              ))}
            </div>
          </div>
        ))}
      </div>

      {audit.issues.length > 0 && (
        <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
            <p style={{ color: 'white', fontWeight: 600 }}>Top Pipeline Issues</p>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {Object.entries(audit.issue_counts || {}).map(([phase, count]) => (
                <InlineTone key={`issue-count:${phase}`} label={`${humanizeKey(phase)} ${count}`} tone="#64748b" />
              ))}
            </div>
          </div>
          <div style={{ display: 'grid', gap: '8px' }}>
            {audit.issues.slice(0, expanded ? 8 : 4).map((issue, index) => (
              <div key={`${issue.phase}:${issue.summary}:${index}`} style={{ borderRadius: '10px', border: '1px solid #1e293b', padding: '10px', backgroundColor: '#0b1120' }}>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                  <InlineTone label={humanizeKey(issue.phase)} tone="#38bdf8" />
                  <InlineTone label={humanizeKey(issue.severity)} tone={issue.severity === 'high' ? '#ef4444' : '#f59e0b'} />
                </div>
                <p style={{ color: '#cbd5e1', fontSize: '12px', marginBottom: expanded && issue.details ? '6px' : 0 }}>{issue.summary}</p>
                {expanded && issue.details && Object.keys(issue.details).length > 0 && (
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {Object.entries(issue.details).slice(0, 6).map(([key, value]) => (
                      <InlineTone key={`${issue.phase}:${key}`} label={`${humanizeKey(key)} ${Array.isArray(value) ? value.length : String(value)}`} tone="#475569" />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GoldenContentEvalSection({
  evaluation,
  expanded = false,
}: {
  evaluation: NonNullable<LabExperiment['golden_evaluation']>;
  expanded?: boolean;
}) {
  return (
    <div style={{ marginTop: '16px', display: 'grid', gap: '12px' }}>
      <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
          <div>
            <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Golden Content Eval</p>
            <p style={{ color: 'white', fontSize: '16px', fontWeight: 600, marginTop: '4px' }}>Fixed benchmark contracts for publishable content</p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <InlineTone label={`Benchmarks ${evaluation.total}`} tone="#64748b" />
            <InlineTone label={`Publishable ${evaluation.publishable_count}`} tone="#22c55e" />
            <InlineTone label={`Close ${evaluation.close_count}`} tone="#f59e0b" />
            <InlineTone label={`Fail ${evaluation.fail_count}`} tone="#ef4444" />
            {evaluation.generated_at && <InlineTone label={`Generated ${formatTimestamp(new Date(evaluation.generated_at))}`} tone="#64748b" />}
          </div>
        </div>
        <p style={{ color: '#cbd5e1', fontSize: '13px', marginBottom: '12px' }}>{evaluation.summary}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
          {evaluation.metric_cards.map((card) => (
            <PrototypeStat key={card.id} label={card.label} value={formatMetric(card.id, card.value)} tone={card.tone} />
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: expanded ? 'repeat(auto-fit, minmax(280px, 1fr))' : 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
        {evaluation.rows.slice(0, expanded ? evaluation.rows.length : 3).map((row) => (
          <div key={row.id} style={{ borderRadius: '12px', border: `1px solid ${goldenTone(row.status)}55`, padding: '14px', backgroundColor: '#020617' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '8px' }}>
              <div>
                <p style={{ color: 'white', fontWeight: 600 }}>{row.label}</p>
                <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '4px' }}>{row.description || row.topic}</p>
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <InlineTone label={humanizeKey(row.audience)} tone="#64748b" />
                <InlineTone label={humanizeKey(row.status)} tone={goldenTone(row.status)} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
              <InlineTone label={`Score ${row.score}/${row.minimum_score}`} tone="#38bdf8" />
              <InlineTone
                label={`Required ${row.required_checks_passed_count}/${row.required_checks_total}`}
                tone={row.required_checks_passed ? '#22c55e' : '#ef4444'}
              />
              {typeof row.anchor_group_total === 'number' && row.anchor_group_total > 0 && (
                <InlineTone label={`Anchors ${row.anchor_hits ?? 0}/${row.anchor_group_total}`} tone="#a78bfa" />
              )}
            </div>
            <p style={{ color: '#cbd5e1', fontSize: '12px', marginBottom: '8px' }}>{row.summary}</p>
            <div style={{ display: 'grid', gap: '6px' }}>
              {row.checks.slice(0, expanded ? row.checks.length : 4).map((check) => (
                <div key={`${row.id}:${check.id}`} style={{ borderRadius: '10px', border: '1px solid #1e293b', padding: '8px', backgroundColor: '#0b1120' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap', marginBottom: '4px' }}>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      <InlineTone label={check.label} tone="#38bdf8" />
                      {check.required && <InlineTone label="Required" tone="#f59e0b" />}
                    </div>
                    <InlineTone label={humanizeKey(check.status)} tone={statusTone(check.status)} />
                  </div>
                  <p style={{ color: '#94a3b8', fontSize: '12px' }}>{check.detail}</p>
                </div>
              ))}
            </div>
            {row.top_warnings?.length > 0 && (
              <p style={{ color: '#fbbf24', fontSize: '12px', marginTop: '8px' }}>
                Warnings: {row.top_warnings.map(humanizeKey).join(', ')}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function LiveSourceAuditSection({
  audit,
  expanded = false,
}: {
  audit: NonNullable<LabExperiment['live_audit']>;
  expanded?: boolean;
}) {
  const [originFilter, setOriginFilter] = useState('all');
  const [laneFilter, setLaneFilter] = useState('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [routeFilter, setRouteFilter] = useState('all');
  const [targetFilter, setTargetFilter] = useState('all');
  const [issueFilter, setIssueFilter] = useState('all');
  const [summaryOriginFilter, setSummaryOriginFilter] = useState('all');
  const [transcriptNoteKindFilter, setTranscriptNoteKindFilter] = useState('all');
  const [personaUseModeFilter, setPersonaUseModeFilter] = useState('all');
  const [fragmentTypeFilter, setFragmentTypeFilter] = useState('all');
  const [fragmentLaneFilter, setFragmentLaneFilter] = useState('all');
  const [fragmentRecommendationFilter, setFragmentRecommendationFilter] = useState('all');
  const [fragmentSectionFilter, setFragmentSectionFilter] = useState('all');

  useEffect(() => {
    setOriginFilter('all');
    setLaneFilter('all');
    setChannelFilter('all');
    setRouteFilter('all');
    setTargetFilter('all');
    setIssueFilter('all');
    setSummaryOriginFilter('all');
    setTranscriptNoteKindFilter('all');
    setPersonaUseModeFilter('all');
    setFragmentTypeFilter('all');
    setFragmentLaneFilter('all');
    setFragmentRecommendationFilter('all');
    setFragmentSectionFilter('all');
  }, [audit.generated_at, audit.source]);

  const candidateSamples = audit.candidate_samples ?? [];
  const assetSamples = audit.asset_samples ?? [];
  const fragmentSamples = audit.fragment_samples ?? [];

  const filteredCandidateSamples = useMemo(() => {
    return candidateSamples.filter((item) => {
      const snapshot = item.signal_snapshot ?? {};
      if (originFilter !== 'all' && snapshot.source_origin !== originFilter) return false;
      if (laneFilter !== 'all' && snapshot.actual_handoff_lane !== laneFilter) return false;
      if (channelFilter !== 'all' && snapshot.source_channel !== channelFilter) return false;
      if (routeFilter !== 'all' && snapshot.primary_route !== routeFilter) return false;
      if (targetFilter !== 'all' && snapshot.target_file !== targetFilter) return false;
      return true;
    });
  }, [candidateSamples, originFilter, laneFilter, channelFilter, routeFilter, targetFilter]);

  const filteredAssetSamples = useMemo(() => {
    return assetSamples.filter((asset) => {
      if (originFilter !== 'all' && asset.origin !== originFilter) return false;
      if (channelFilter !== 'all' && asset.source_channel !== channelFilter) return false;
      if (summaryOriginFilter !== 'all' && asset.summary_origin !== summaryOriginFilter) return false;
      if (transcriptNoteKindFilter !== 'all' && asset.transcript_note_kind !== transcriptNoteKindFilter) return false;
      if (personaUseModeFilter !== 'all' && asset.persona_use_mode !== personaUseModeFilter) return false;
      if (issueFilter !== 'all' && !(asset.quality_flags || []).includes(issueFilter)) return false;
      return true;
    });
  }, [assetSamples, originFilter, channelFilter, summaryOriginFilter, transcriptNoteKindFilter, personaUseModeFilter, issueFilter]);

  const filteredFragmentSamples = useMemo(() => {
    return fragmentSamples.filter((fragment) => {
      if (originFilter !== 'all' && fragment.asset_origin !== originFilter) return false;
      if (channelFilter !== 'all' && fragment.asset_source_channel !== channelFilter) return false;
      if (transcriptNoteKindFilter !== 'all' && fragment.asset_transcript_note_kind !== transcriptNoteKindFilter) return false;
      if (personaUseModeFilter !== 'all' && fragment.asset_persona_use_mode !== personaUseModeFilter) return false;
      if (fragmentTypeFilter !== 'all' && fragment.primary_type !== fragmentTypeFilter) return false;
      if (fragmentLaneFilter !== 'all' && fragment.likely_handoff_lane !== fragmentLaneFilter) return false;
      if (fragmentRecommendationFilter !== 'all' && fragment.promotion_recommendation !== fragmentRecommendationFilter) return false;
      if (fragmentSectionFilter !== 'all' && fragment.source_section !== fragmentSectionFilter) return false;
      if (issueFilter !== 'all' && !fragment.labels.includes(issueFilter)) return false;
      return true;
    });
  }, [
    fragmentSamples,
    originFilter,
    channelFilter,
    transcriptNoteKindFilter,
    personaUseModeFilter,
    fragmentTypeFilter,
    fragmentLaneFilter,
    fragmentRecommendationFilter,
    fragmentSectionFilter,
    issueFilter,
  ]);

  const originOptions = useMemo(
    () => Object.entries(audit.slice_counts.origin_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.origin_counts],
  );
  const handoffOptions = useMemo(
    () => Object.entries(audit.slice_counts.handoff_lane_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.handoff_lane_counts],
  );
  const channelOptions = useMemo(
    () => Object.entries(audit.slice_counts.channel_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.channel_counts],
  );
  const routeOptions = useMemo(
    () => Object.entries(audit.slice_counts.primary_route_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.primary_route_counts],
  );
  const targetOptions = useMemo(
    () =>
      Object.entries(audit.slice_counts.target_file_counts || {}).map(([value, count]) => ({
        value,
        label: value,
        count,
      })),
    [audit.slice_counts.target_file_counts],
  );
  const issueOptions = useMemo(
    () => Object.entries(audit.slice_counts.issue_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.issue_counts],
  );
  const summaryOriginOptions = useMemo(
    () => Object.entries(audit.slice_counts.summary_origin_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.summary_origin_counts],
  );
  const transcriptNoteKindOptions = useMemo(
    () => Object.entries(audit.slice_counts.transcript_note_kind_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.transcript_note_kind_counts],
  );
  const personaUseModeOptions = useMemo(
    () => Object.entries(audit.slice_counts.persona_use_mode_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.persona_use_mode_counts],
  );
  const fragmentTypeOptions = useMemo(
    () => Object.entries(audit.slice_counts.fragment_type_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.fragment_type_counts],
  );
  const fragmentLaneOptions = useMemo(
    () => Object.entries(audit.slice_counts.fragment_lane_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.fragment_lane_counts],
  );
  const fragmentRecommendationOptions = useMemo(
    () => Object.entries(audit.slice_counts.fragment_recommendation_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.fragment_recommendation_counts],
  );
  const fragmentSectionOptions = useMemo(
    () => Object.entries(audit.slice_counts.fragment_source_section_counts || {}).map(([value, count]) => ({ value, label: humanizeKey(value), count })),
    [audit.slice_counts.fragment_source_section_counts],
  );

  return (
    <div style={{ marginTop: '16px', display: 'grid', gap: '12px' }}>
      <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
          <div>
            <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Live Source Audit</p>
            <p style={{ color: 'white', fontSize: '16px', fontWeight: 600, marginTop: '4px' }}>Real corpus slices, filters, and extraction quality</p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <InlineTone label={`Source ${humanizeKey(audit.source)}`} tone="#14b8a6" />
            <InlineTone label={`Assets ${audit.asset_count}`} tone="#38bdf8" />
            <InlineTone label={`Candidates ${audit.candidate_count}`} tone="#a78bfa" />
            <InlineTone label={`Segments ${audit.segments_total}`} tone="#64748b" />
            {audit.generated_at && <InlineTone label={`Generated ${formatTimestamp(new Date(audit.generated_at))}`} tone="#64748b" />}
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
          <PrototypeStat label="Summary" value={`${audit.quality_metrics.summary_coverage_rate}%`} tone="#22c55e" />
          <PrototypeStat label="Structured" value={`${audit.quality_metrics.structured_summary_rate}%`} tone="#34d399" />
          <PrototypeStat label="Lessons" value={`${audit.quality_metrics.lesson_coverage_rate}%`} tone="#38bdf8" />
          <PrototypeStat label="Anecdotes" value={`${audit.quality_metrics.anecdote_coverage_rate}%`} tone="#a78bfa" />
          <PrototypeStat label="Quotes" value={`${audit.quality_metrics.quote_coverage_rate}%`} tone="#f59e0b" />
          <PrototypeStat label="Ready" value={`${audit.quality_metrics.package_readiness_rate}%`} tone="#14b8a6" />
          <PrototypeStat label="Noisy Summary" value={`${audit.quality_metrics.noisy_summary_rate}%`} tone="#ef4444" />
        </div>
      </div>

      <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
          <div>
            <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Deep Harvest</p>
            <p style={{ color: 'white', fontSize: '16px', fontWeight: 600, marginTop: '4px' }}>Many fragments per asset, typed before Persona or canon promotion</p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <InlineTone label={`Fragments ${audit.deep_harvest_metrics.total_fragments}`} tone="#f59e0b" />
            <InlineTone label={`Avg ${audit.deep_harvest_metrics.average_fragments_per_asset}/asset`} tone="#64748b" />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
          <PrototypeStat label="Persona Ready" value={`${audit.deep_harvest_metrics.persona_candidate_rate}%`} tone="#22c55e" />
          <PrototypeStat label="Canon Signal" value={`${audit.deep_harvest_metrics.canon_candidate_rate}%`} tone="#a78bfa" />
          <PrototypeStat label="Post Ready" value={`${audit.deep_harvest_metrics.post_candidate_rate}%`} tone="#38bdf8" />
          <PrototypeStat label="PM Ready" value={`${audit.deep_harvest_metrics.route_to_pm_rate}%`} tone="#ef4444" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginTop: '12px' }}>
          <PrototypeStat label="Voice Guide" value={`${audit.deep_harvest_metrics.voice_guidance_only_rate ?? 0}%`} tone="#f59e0b" />
          <PrototypeStat label="Persona Promote" value={`${audit.deep_harvest_metrics.persona_recommendation_rate ?? 0}%`} tone="#22c55e" />
          <PrototypeStat label="Canon Suggest" value={`${audit.deep_harvest_metrics.canon_suggestion_rate ?? 0}%`} tone="#a78bfa" />
          <PrototypeStat label="Stay Source" value={`${audit.deep_harvest_metrics.source_only_recommendation_rate ?? 0}%`} tone="#64748b" />
        </div>
      </div>

      {audit.origin_breakdown && Object.keys(audit.origin_breakdown).length > 0 && (
        <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '10px' }}>
            <div>
              <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Origin Breakdown</p>
              <p style={{ color: 'white', fontSize: '16px', fontWeight: 600, marginTop: '4px' }}>Separate quality slices for each corpus cohort</p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: expanded ? 'minmax(0, 1fr)' : 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
            {Object.entries(audit.origin_breakdown).map(([origin, breakdown]) => (
              <div key={origin} style={{ borderRadius: '10px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#0b1120' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                  <p style={{ color: 'white', fontSize: '13px', fontWeight: 600 }}>{humanizeKey(origin)}</p>
                  <InlineTone label={`${breakdown.asset_count} assets`} tone="#38bdf8" />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '8px' }}>
                  <PrototypeStat label="Summary" value={`${breakdown.quality_metrics.summary_coverage_rate}%`} tone="#22c55e" compact />
                  <PrototypeStat label="Lessons" value={`${breakdown.quality_metrics.lesson_coverage_rate}%`} tone="#38bdf8" compact />
                  <PrototypeStat label="Anecdotes" value={`${breakdown.quality_metrics.anecdote_coverage_rate}%`} tone="#a78bfa" compact />
                  <PrototypeStat label="Quotes" value={`${breakdown.quality_metrics.quote_coverage_rate}%`} tone="#f59e0b" compact />
                  <PrototypeStat label="Ready" value={`${breakdown.quality_metrics.package_readiness_rate}%`} tone="#14b8a6" compact />
                  <PrototypeStat label="Noisy" value={`${breakdown.quality_metrics.noisy_summary_rate}%`} tone="#ef4444" compact />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: '10px' }}>
        <FilterChipGroup label="Origins" options={originOptions} activeValue={originFilter} onChange={setOriginFilter} tone="#f97316" />
        <FilterChipGroup label="Handoff Lanes" options={handoffOptions} activeValue={laneFilter} onChange={setLaneFilter} tone="#22c55e" />
        <FilterChipGroup label="Channels" options={channelOptions} activeValue={channelFilter} onChange={setChannelFilter} tone="#38bdf8" />
        <FilterChipGroup label="Primary Routes" options={routeOptions} activeValue={routeFilter} onChange={setRouteFilter} tone="#a78bfa" />
        <FilterChipGroup label="Target Files" options={targetOptions} activeValue={targetFilter} onChange={setTargetFilter} tone="#64748b" />
        <FilterChipGroup label="Summary Origins" options={summaryOriginOptions} activeValue={summaryOriginFilter} onChange={setSummaryOriginFilter} tone="#14b8a6" />
        <FilterChipGroup label="Transcript Note Kinds" options={transcriptNoteKindOptions} activeValue={transcriptNoteKindFilter} onChange={setTranscriptNoteKindFilter} tone="#f97316" />
        <FilterChipGroup label="Persona Use" options={personaUseModeOptions} activeValue={personaUseModeFilter} onChange={setPersonaUseModeFilter} tone="#22c55e" />
        <FilterChipGroup label="Quality Issues" options={issueOptions} activeValue={issueFilter} onChange={setIssueFilter} tone="#ef4444" />
        <FilterChipGroup label="Fragment Types" options={fragmentTypeOptions} activeValue={fragmentTypeFilter} onChange={setFragmentTypeFilter} tone="#f59e0b" />
        <FilterChipGroup label="Fragment Lanes" options={fragmentLaneOptions} activeValue={fragmentLaneFilter} onChange={setFragmentLaneFilter} tone="#22c55e" />
        <FilterChipGroup
          label="Promotion Recommendations"
          options={fragmentRecommendationOptions}
          activeValue={fragmentRecommendationFilter}
          onChange={setFragmentRecommendationFilter}
          tone="#a78bfa"
        />
        <FilterChipGroup label="Fragment Sections" options={fragmentSectionOptions} activeValue={fragmentSectionFilter} onChange={setFragmentSectionFilter} tone="#64748b" />
      </div>

      {audit.top_issues?.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {audit.top_issues.map((issue) => (
            <InlineTone key={issue.id} label={`${humanizeKey(issue.label)} ${issue.count}`} tone="#f59e0b" />
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: expanded ? 'minmax(0, 1fr)' : 'repeat(auto-fit, minmax(340px, 1fr))', gap: '12px' }}>
        <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
            <p style={{ color: 'white', fontWeight: 600 }}>Deep Harvest Fragments</p>
            <InlineTone label={`${filteredFragmentSamples.length} of ${fragmentSamples.length}`} tone="#f59e0b" />
          </div>
          <div style={{ display: 'grid', gap: '10px', maxHeight: expanded ? 'unset' : '560px', overflowY: 'auto' }}>
            {filteredFragmentSamples.length === 0 && <p style={{ color: '#64748b', fontSize: '13px' }}>No harvested fragments match the current filters.</p>}
            {filteredFragmentSamples.slice(0, expanded ? 18 : 8).map((fragment, index) => (
              <div key={`fragment:${fragment.asset_title}:${index}:${fragment.text}`} style={{ borderRadius: '10px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#0b1120' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
                  <p style={{ color: 'white', fontSize: '13px', fontWeight: 600 }}>{fragment.asset_title}</p>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <InlineTone label={humanizeKey(fragment.primary_type)} tone="#f59e0b" />
                    <InlineTone label={humanizeKey(fragment.likely_handoff_lane)} tone="#22c55e" />
                    {fragment.promotion_recommendation && fragment.promotion_recommendation !== 'unknown' && (
                      <InlineTone label={humanizeKey(fragment.promotion_recommendation)} tone={recommendationTone(fragment.promotion_recommendation)} />
                    )}
                  </div>
                </div>
                <p style={{ color: '#cbd5e1', fontSize: '12px', marginBottom: '8px' }}>{fragment.text}</p>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                  {fragment.asset_source_channel && <InlineTone label={humanizeKey(fragment.asset_source_channel)} tone="#64748b" />}
                  {fragment.asset_transcript_note_kind && <InlineTone label={humanizeKey(fragment.asset_transcript_note_kind)} tone="#fb7185" />}
                  {fragment.asset_persona_use_mode && <InlineTone label={humanizeKey(fragment.asset_persona_use_mode)} tone="#14b8a6" />}
                  {fragment.asset_voice_signal_priority && <InlineTone label={`Voice ${humanizeKey(fragment.asset_voice_signal_priority)}`} tone="#a78bfa" />}
                  {fragment.source_section && <InlineTone label={humanizeKey(fragment.source_section)} tone="#334155" />}
                  <InlineTone label={`Score ${fragment.score}`} tone="#a78bfa" />
                  <InlineTone label={`${fragment.word_count} words`} tone="#475569" />
                  {fragment.labels.filter((label) => label !== fragment.primary_type).slice(0, 4).map((label) => (
                    <InlineTone key={`${fragment.asset_title}:${fragment.text}:${label}`} label={humanizeKey(label)} tone="#14b8a6" />
                  ))}
                </div>
                {fragment.promotion_reason && <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '6px' }}>{fragment.promotion_reason}</p>}
                {fragment.asset_source_path && <p style={{ color: '#64748b', fontSize: '11px' }}>{fragment.asset_source_path}</p>}
              </div>
            ))}
          </div>
        </div>

        <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
            <p style={{ color: 'white', fontWeight: 600 }}>Filtered Candidate Slices</p>
            <InlineTone label={`${filteredCandidateSamples.length} of ${candidateSamples.length}`} tone="#38bdf8" />
          </div>
          <div style={{ display: 'grid', gap: '10px', maxHeight: expanded ? 'unset' : '560px', overflowY: 'auto' }}>
            {filteredCandidateSamples.length === 0 && <p style={{ color: '#64748b', fontSize: '13px' }}>No live candidate slices match the current filters.</p>}
            {filteredCandidateSamples.slice(0, expanded ? 12 : 6).map((item) => {
              const snapshot = item.signal_snapshot ?? {};
              return (
                <div key={`candidate:${item.topic}:${item.top_option_preview}`} style={{ borderRadius: '10px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#0b1120' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
                    <p style={{ color: 'white', fontSize: '13px', fontWeight: 600 }}>{item.topic}</p>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {snapshot.actual_handoff_lane && <InlineTone label={humanizeKey(snapshot.actual_handoff_lane)} tone="#22c55e" />}
                      {snapshot.primary_route && <InlineTone label={humanizeKey(snapshot.primary_route)} tone="#38bdf8" />}
                    </div>
                  </div>
                  <p style={{ color: '#cbd5e1', fontSize: '12px', marginBottom: '8px' }}>{item.top_option_preview}</p>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                    {snapshot.source_origin && <InlineTone label={humanizeKey(snapshot.source_origin)} tone="#f97316" />}
                    {snapshot.source_channel && <InlineTone label={`Source ${humanizeKey(snapshot.source_channel)}`} tone="#64748b" />}
                    {snapshot.lane_hint && <InlineTone label={`Hint ${humanizeKey(snapshot.lane_hint)}`} tone="#a78bfa" />}
                    {snapshot.target_file && <InlineTone label={snapshot.target_file} tone="#334155" />}
                    {(snapshot.secondary_consumers || []).map((consumer) => (
                      <InlineTone key={`${item.topic}:${consumer}`} label={`Feeds ${humanizeKey(consumer)}`} tone="#14b8a6" />
                    ))}
                  </div>
                  {snapshot.handoff_reason && <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '6px' }}>{snapshot.handoff_reason}</p>}
                  {snapshot.source_path && <p style={{ color: '#64748b', fontSize: '11px' }}>{snapshot.source_path}</p>}
                </div>
              );
            })}
          </div>
        </div>

        <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '14px', backgroundColor: '#020617' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
            <p style={{ color: 'white', fontWeight: 600 }}>Asset Extraction Quality</p>
            <InlineTone label={`${filteredAssetSamples.length} of ${assetSamples.length}`} tone="#14b8a6" />
          </div>
          <div style={{ display: 'grid', gap: '10px', maxHeight: expanded ? 'unset' : '560px', overflowY: 'auto' }}>
            {filteredAssetSamples.length === 0 && <p style={{ color: '#64748b', fontSize: '13px' }}>No ingested assets match the current quality filters.</p>}
            {filteredAssetSamples.slice(0, expanded ? 12 : 6).map((asset) => (
              <div key={`asset:${asset.title}:${asset.source_path}`} style={{ borderRadius: '10px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#0b1120' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
                  <p style={{ color: 'white', fontSize: '13px', fontWeight: 600 }}>{asset.title}</p>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {asset.origin && <InlineTone label={humanizeKey(asset.origin)} tone="#f97316" />}
                    {asset.transcript_note_kind && asset.transcript_note_kind !== 'unknown' && <InlineTone label={humanizeKey(asset.transcript_note_kind)} tone="#fb7185" />}
                    {asset.persona_use_mode && asset.persona_use_mode !== 'unknown' && <InlineTone label={humanizeKey(asset.persona_use_mode)} tone="#22c55e" />}
                    {asset.voice_signal_priority && asset.voice_signal_priority !== 'unknown' && <InlineTone label={`Voice ${humanizeKey(asset.voice_signal_priority)}`} tone="#a78bfa" />}
                    {asset.source_channel && <InlineTone label={humanizeKey(asset.source_channel)} tone="#64748b" />}
                    {asset.summary_origin && <InlineTone label={`Summary ${humanizeKey(asset.summary_origin)}`} tone="#38bdf8" />}
                  </div>
                </div>
                {asset.summary && <p style={{ color: '#cbd5e1', fontSize: '12px', marginBottom: '6px' }}>Summary: {asset.summary}</p>}
                {asset.structured_summary && asset.structured_summary !== asset.summary && (
                  <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '6px' }}>Structured: {asset.structured_summary}</p>
                )}
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                  {(asset.quality_flags || []).map((flag) => (
                    <InlineTone key={`${asset.title}:${flag}`} label={humanizeKey(flag)} tone={flag === 'summary_needs_cleanup' ? '#ef4444' : '#f59e0b'} />
                  ))}
                  {typeof asset.word_count === 'number' && <InlineTone label={`Raw ${asset.word_count}w`} tone="#334155" />}
                  {typeof asset.clean_word_count === 'number' && <InlineTone label={`Clean ${asset.clean_word_count}w`} tone="#475569" />}
                  {typeof asset.sentence_count === 'number' && <InlineTone label={`Sentences ${asset.sentence_count}`} tone="#475569" />}
                  {typeof asset.deep_harvest_counts?.total === 'number' && <InlineTone label={`Harvest ${asset.deep_harvest_counts.total}`} tone="#14b8a6" />}
                  {typeof asset.deep_harvest_counts?.canon_candidate_count === 'number' && asset.deep_harvest_counts.canon_candidate_count > 0 && (
                    <InlineTone label={`Canon ${asset.deep_harvest_counts.canon_candidate_count}`} tone="#a78bfa" />
                  )}
                  {typeof asset.deep_harvest_counts?.voice_guidance_only_count === 'number' && asset.deep_harvest_counts.voice_guidance_only_count > 0 && (
                    <InlineTone label={`Voice ${asset.deep_harvest_counts.voice_guidance_only_count}`} tone="#f59e0b" />
                  )}
                  {typeof asset.deep_harvest_counts?.persona_recommendation_count === 'number' && asset.deep_harvest_counts.persona_recommendation_count > 0 && (
                    <InlineTone label={`Persona ${asset.deep_harvest_counts.persona_recommendation_count}`} tone="#22c55e" />
                  )}
                  {typeof asset.deep_harvest_counts?.canon_suggestion_count === 'number' && asset.deep_harvest_counts.canon_suggestion_count > 0 && (
                    <InlineTone label={`Suggest ${asset.deep_harvest_counts.canon_suggestion_count}`} tone="#a78bfa" />
                  )}
                </div>
                {(asset.lessons_learned?.length || asset.key_anecdotes?.length || asset.reusable_quotes?.length) ? (
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {asset.lessons_learned && asset.lessons_learned.length > 0 && (
                      <p style={{ color: '#94a3b8', fontSize: '12px' }}>Lessons: {asset.lessons_learned.slice(0, 2).join(' | ')}</p>
                    )}
                    {asset.key_anecdotes && asset.key_anecdotes.length > 0 && (
                      <p style={{ color: '#94a3b8', fontSize: '12px' }}>Anecdotes: {asset.key_anecdotes.slice(0, 2).join(' | ')}</p>
                    )}
                    {asset.reusable_quotes && asset.reusable_quotes.length > 0 && (
                      <p style={{ color: '#94a3b8', fontSize: '12px' }}>Quotes: {asset.reusable_quotes.slice(0, 2).join(' | ')}</p>
                    )}
                    {asset.open_questions && asset.open_questions.length > 0 && (
                      <p style={{ color: '#64748b', fontSize: '12px' }}>Open questions: {asset.open_questions.slice(0, 2).join(' | ')}</p>
                    )}
                  </div>
                ) : (
                  <p style={{ color: '#64748b', fontSize: '12px' }}>No structured lessons, anecdotes, or quotes extracted yet.</p>
                )}
                {asset.top_fragments && asset.top_fragments.length > 0 && (
                  <div style={{ display: 'grid', gap: '6px', marginTop: '8px' }}>
                    {asset.top_fragments.slice(0, 3).map((fragment, index) => (
                      <div key={`${asset.title}:top-fragment:${index}:${fragment.text}`} style={{ borderRadius: '8px', border: '1px solid #1e293b', padding: '8px', backgroundColor: '#0f172a' }}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '4px' }}>
                          {fragment.primary_type && <InlineTone label={humanizeKey(fragment.primary_type)} tone="#f59e0b" />}
                          {fragment.likely_handoff_lane && <InlineTone label={humanizeKey(fragment.likely_handoff_lane)} tone="#22c55e" />}
                          {fragment.promotion_recommendation && <InlineTone label={humanizeKey(fragment.promotion_recommendation)} tone={recommendationTone(fragment.promotion_recommendation)} />}
                          {typeof fragment.score === 'number' && <InlineTone label={`Score ${fragment.score}`} tone="#475569" />}
                        </div>
                        {fragment.text && <p style={{ color: '#cbd5e1', fontSize: '12px' }}>{fragment.text}</p>}
                        {fragment.promotion_reason && <p style={{ color: '#94a3b8', fontSize: '11px', marginTop: '4px' }}>{fragment.promotion_reason}</p>}
                      </div>
                    ))}
                  </div>
                )}
                {asset.source_path && <p style={{ color: '#64748b', fontSize: '11px', marginTop: '6px' }}>{asset.source_path}</p>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterChipGroup({
  label,
  options,
  activeValue,
  onChange,
  tone,
}: {
  label: string;
  options: { value: string; label: string; count: number }[];
  activeValue: string;
  onChange: (value: string) => void;
  tone: string;
}) {
  if (!options.length) {
    return null;
  }
  return (
    <div style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#020617' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: '8px' }}>{label}</p>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button
          onClick={() => onChange('all')}
          style={{
            borderRadius: '999px',
            border: `1px solid ${activeValue === 'all' ? `${tone}66` : '#334155'}`,
            backgroundColor: activeValue === 'all' ? `${tone}22` : '#020617',
            color: 'white',
            padding: '6px 10px',
            fontSize: '12px',
            cursor: 'pointer',
          }}
        >
          All
        </button>
        {options.map((option) => (
          <button
            key={`${label}:${option.value}`}
            onClick={() => onChange(option.value)}
            style={{
              borderRadius: '999px',
              border: `1px solid ${activeValue === option.value ? `${tone}66` : '#334155'}`,
              backgroundColor: activeValue === option.value ? `${tone}22` : '#020617',
              color: 'white',
              padding: '6px 10px',
              fontSize: '12px',
              cursor: 'pointer',
            }}
          >
            {option.label} {option.count}
          </button>
        ))}
      </div>
    </div>
  );
}

function BuildLogCard({ automations, expanded = false }: { automations: Automation[]; expanded?: boolean }) {
  return (
    <section style={{ borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#040d16', padding: '20px', minHeight: expanded ? '420px' : '220px' }}>
      <p style={{ color: '#fbbf24', letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase' }}>Build Logs</p>
      <h2 style={{ color: 'white', fontSize: '20px', marginBottom: '12px' }}>Latest isolated runs</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: expanded ? 'unset' : '200px', overflowY: 'auto' }}>
        {automations.length === 0 && <p style={{ color: '#475569' }}>No runs recorded yet.</p>}
        {automations.map((job) => (
          <div key={job.id} style={{ borderRadius: '12px', border: '1px solid #1f2937', padding: '12px', backgroundColor: '#020617' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <p style={{ color: 'white', fontWeight: 600 }}>{job.name}</p>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>{job.channel}</span>
            </div>
            <p style={{ color: '#94a3b8', fontSize: '13px' }}>Last run: {job.last_run_at ? formatTimestamp(new Date(job.last_run_at)) : '—'}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatTimestamp(value: Date) {
  return formatUiTimestamp(value);
}

function formatMetric(metricId: string, value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—';
  }
  if (metricId.includes('rate')) {
    return `${value}%`;
  }
  return `${value}`;
}

function humanizeKey(value: string) {
  return value.replace(/[_-]+/g, ' ');
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value : '';
}

function numberValue(value: unknown) {
  return typeof value === 'number' ? value : undefined;
}

function arrayCount(value: unknown) {
  return Array.isArray(value) ? value.length : 0;
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)).filter((item) => item.trim().length > 0) : [];
}

function objectValue(value: unknown) {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function booleanValue(value: unknown) {
  return typeof value === 'boolean' ? value : undefined;
}

function scoreTone(score: number) {
  if (score >= 8.5) return '#22c55e';
  if (score >= 7) return '#f59e0b';
  return '#ef4444';
}

function recommendationTone(recommendation: string) {
  if (recommendation === 'canon_suggestion') return '#a78bfa';
  if (recommendation === 'persona_candidate') return '#22c55e';
  if (recommendation === 'voice_guidance_only') return '#f59e0b';
  return '#64748b';
}

function groupStageResults(
  stages: {
    id: string;
    label: string;
    section?: string;
    status: string;
    reason: string;
    detail: string;
    score?: number | null;
    evidence?: string[];
    missing_fields?: string[];
  }[],
) {
  const order = ['source', 'article', 'classification', 'johnnie', 'synthesis', 'decision', 'draft', 'evaluation'];
  const groups = new Map<string, typeof stages>();
  for (const stage of stages) {
    const section = stage.section || 'evaluation';
    const current = groups.get(section) || [];
    current.push(stage);
    groups.set(section, current);
  }
  return Array.from(groups.entries())
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([section, items]) => ({ section, items }));
}

function phaseTone(status: string) {
  if (status === 'done' || status === 'ready') return '#22c55e';
  if (status === 'active') return '#38bdf8';
  return '#64748b';
}

function statusTone(status: string) {
  if (status === 'pass') return '#22c55e';
  if (status === 'warn') return '#f59e0b';
  if (status === 'fail') return '#ef4444';
  if (status === 'missing') return '#94a3b8';
  return '#64748b';
}

function goldenTone(status: string) {
  if (status === 'publishable') return '#22c55e';
  if (status === 'close') return '#f59e0b';
  if (status === 'fail') return '#ef4444';
  if (status === 'missing') return '#94a3b8';
  return '#64748b';
}

function statusGlyph(status: string) {
  if (status === 'pass') return 'PASS';
  if (status === 'warn') return 'WARN';
  if (status === 'fail') return 'FAIL';
  if (status === 'missing') return 'MISS';
  return 'INFO';
}

function InlineTone({ label, tone }: { label: string; tone: string }) {
  return (
    <span
      style={{
        borderRadius: '999px',
        border: `1px solid ${tone}55`,
        backgroundColor: `${tone}14`,
        color: tone,
        fontSize: '11px',
        fontWeight: 700,
        letterSpacing: '0.04em',
        padding: '5px 9px',
        textTransform: 'uppercase',
      }}
    >
      {label}
    </span>
  );
}
