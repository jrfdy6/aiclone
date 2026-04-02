'use client';

import { useEffect, useMemo, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { getApiUrl } from '@/lib/api-client';

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
    slice_counts: {
      handoff_lane_counts: Record<string, number>;
      primary_route_counts: Record<string, number>;
      channel_counts: Record<string, number>;
      target_file_counts: Record<string, number>;
      summary_origin_counts: Record<string, number>;
      issue_counts: Record<string, number>;
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
      summary?: string;
      summary_origin?: string;
      structured_summary?: string;
      lessons_learned?: string[];
      key_anecdotes?: string[];
      reusable_quotes?: string[];
      open_questions?: string[];
      quality_flags?: string[];
      word_count?: number | null;
      clean_word_count?: number | null;
      sentence_count?: number | null;
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
  const [activeTab, setActiveTab] = useState<Tab>('foundry');

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

function PrototypeStat({ label, value, tone = '#34d399' }: { label: string; value: number | string; tone?: string }) {
  return (
    <div style={{ flex: 1, borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#071814', padding: '12px' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: tone, fontSize: '22px', fontWeight: 600 }}>{value}</p>
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
  const [laneFilter, setLaneFilter] = useState('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [routeFilter, setRouteFilter] = useState('all');
  const [targetFilter, setTargetFilter] = useState('all');
  const [issueFilter, setIssueFilter] = useState('all');
  const [summaryOriginFilter, setSummaryOriginFilter] = useState('all');

  useEffect(() => {
    setLaneFilter('all');
    setChannelFilter('all');
    setRouteFilter('all');
    setTargetFilter('all');
    setIssueFilter('all');
    setSummaryOriginFilter('all');
  }, [audit.generated_at, audit.source]);

  const candidateSamples = audit.candidate_samples ?? [];
  const assetSamples = audit.asset_samples ?? [];

  const filteredCandidateSamples = useMemo(() => {
    return candidateSamples.filter((item) => {
      const snapshot = item.signal_snapshot ?? {};
      if (laneFilter !== 'all' && snapshot.actual_handoff_lane !== laneFilter) return false;
      if (channelFilter !== 'all' && snapshot.source_channel !== channelFilter) return false;
      if (routeFilter !== 'all' && snapshot.primary_route !== routeFilter) return false;
      if (targetFilter !== 'all' && snapshot.target_file !== targetFilter) return false;
      return true;
    });
  }, [candidateSamples, laneFilter, channelFilter, routeFilter, targetFilter]);

  const filteredAssetSamples = useMemo(() => {
    return assetSamples.filter((asset) => {
      if (channelFilter !== 'all' && asset.source_channel !== channelFilter) return false;
      if (summaryOriginFilter !== 'all' && asset.summary_origin !== summaryOriginFilter) return false;
      if (issueFilter !== 'all' && !(asset.quality_flags || []).includes(issueFilter)) return false;
      return true;
    });
  }, [assetSamples, channelFilter, summaryOriginFilter, issueFilter]);

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

      <div style={{ display: 'grid', gap: '10px' }}>
        <FilterChipGroup label="Handoff Lanes" options={handoffOptions} activeValue={laneFilter} onChange={setLaneFilter} tone="#22c55e" />
        <FilterChipGroup label="Channels" options={channelOptions} activeValue={channelFilter} onChange={setChannelFilter} tone="#38bdf8" />
        <FilterChipGroup label="Primary Routes" options={routeOptions} activeValue={routeFilter} onChange={setRouteFilter} tone="#a78bfa" />
        <FilterChipGroup label="Target Files" options={targetOptions} activeValue={targetFilter} onChange={setTargetFilter} tone="#64748b" />
        <FilterChipGroup label="Summary Origins" options={summaryOriginOptions} activeValue={summaryOriginFilter} onChange={setSummaryOriginFilter} tone="#14b8a6" />
        <FilterChipGroup label="Quality Issues" options={issueOptions} activeValue={issueFilter} onChange={setIssueFilter} tone="#ef4444" />
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
  return value.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
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
