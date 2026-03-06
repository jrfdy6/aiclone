'use client';

import { useEffect, useState } from 'react';
import { getApiUrl } from '@/lib/api-client';
import NavHeader from '@/components/NavHeader';

export type TranscriptEntry = {
  date: string;
  title: string;
  tags: string[];
  summary: string;
  link: string;
};

export type DocEntry = {
  name: string;
  path: string;
  snippet: string;
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

type Tab = 'briefs' | 'automations' | 'docs';

const API_URL = getApiUrl();

export default function BrainClient({ transcripts, docs }: { transcripts: TranscriptEntry[]; docs: DocEntry[] }) {
  const [activeTab, setActiveTab] = useState<Tab>('briefs');
  const [selectedBrief, setSelectedBrief] = useState<TranscriptEntry | null>(transcripts[0] ?? null);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [automationsError, setAutomationsError] = useState<string | null>(null);

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
          setAutomationsError('Unable to load automations right now.');
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

  return (
    <main style={{ minHeight: '100vh', background: 'radial-gradient(circle at top, rgba(12,20,45,0.85), #010617 50%)', paddingBottom: '120px' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        <HeroBlock />
        <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
          <BrainTabButton active={activeTab === 'briefs'} onClick={() => setActiveTab('briefs')} label="Daily Briefs" description="History + markdown" />
          <BrainTabButton active={activeTab === 'automations'} onClick={() => setActiveTab('automations')} label="Automations" description="Cron manifest" />
          <BrainTabButton active={activeTab === 'docs'} onClick={() => setActiveTab('docs')} label="Documentation" description="Knowledge base" />
        </div>

        {activeTab === 'briefs' && (
          <DailyBriefsPanel transcripts={transcripts} selected={selectedBrief} onSelect={setSelectedBrief} />
        )}
        {activeTab === 'automations' && (
          <AutomationsPanel automations={automations} error={automationsError} />
        )}
        {activeTab === 'docs' && <DocsPanel docs={docs} />}
      </div>
      <ModuleDock active="Brain" />
    </main>
  );
}

function HeroBlock() {
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
          <h1 style={{ color: 'white', fontSize: '32px', margin: '4px 0' }}>Daily Briefs + Automations</h1>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Markdown-driven briefs, mirrored cron manifest, and living documentation for the agent.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <HeroStat label="Briefs" value="Live" tone="#38bdf8" />
          <HeroStat label="Automations" value="4" tone="#fbbf24" />
          <HeroStat label="Docs" value="Knowledge" tone="#34d399" />
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

function BrainTabButton({ active, onClick, label, description }: { active: boolean; onClick: () => void; label: string; description: string }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        textAlign: 'left',
        borderRadius: '16px',
        padding: '16px',
        border: active ? '1px solid #38bdf8' : '1px solid #1f2937',
        background: active ? 'linear-gradient(120deg, rgba(56,189,248,0.18), rgba(15,23,42,0.95))' : '#050b19',
        color: 'white',
        cursor: 'pointer',
      }}
    >
      <p style={{ fontSize: '16px', fontWeight: 600 }}>{label}</p>
      <p style={{ fontSize: '13px', color: '#94a3b8' }}>{description}</p>
    </button>
  );
}

function DailyBriefsPanel({ transcripts, selected, onSelect }: { transcripts: TranscriptEntry[]; selected: TranscriptEntry | null; onSelect: (entry: TranscriptEntry) => void }) {
  return (
    <section style={{ display: 'flex', gap: '16px', borderRadius: '16px', border: '1px solid #1f2937', backgroundColor: '#050b19', padding: '20px', minHeight: '460px' }}>
      <div style={{ width: '260px', borderRight: '1px solid #0f172a', paddingRight: '12px', maxHeight: '420px', overflowY: 'auto' }}>
        {transcripts.length === 0 && <p style={{ color: '#475569' }}>No briefs indexed yet.</p>}
        {transcripts.map((entry) => (
          <button
            key={`${entry.date}-${entry.title}`}
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
            <p style={{ fontSize: '12px', color: '#94a3b8' }}>{entry.date}</p>
            <p style={{ fontSize: '14px', fontWeight: 600 }}>{entry.title}</p>
          </button>
        ))}
      </div>
      <div style={{ flex: 1 }}>
        {selected ? (
          <div>
            <p style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '4px' }}>{selected.date}</p>
            <h2 style={{ color: 'white', fontSize: '24px', marginBottom: '8px' }}>{selected.title}</h2>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '12px' }}>{selected.summary}</p>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
              {selected.tags.map((tag) => (
                <span key={tag} style={{ fontSize: '12px', color: '#38bdf8', border: '1px solid rgba(56,189,248,0.4)', borderRadius: '999px', padding: '4px 10px' }}>
                  {tag}
                </span>
              ))}
            </div>
            <a href={`/knowledge/aiclone/transcripts/${selected.link}`} style={{ color: '#38bdf8', fontSize: '14px' }}>
              Open full note ↗
            </a>
          </div>
        ) : (
          <p style={{ color: '#475569' }}>Select a brief to read the markdown.</p>
        )}
      </div>
    </section>
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

function formatTimestamp(value: Date) {
  return value.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
}

function ModuleDock({ active }: { active: 'Ops' | 'Brain' | 'Lab' }) {
  const buttons: { label: 'Ops' | 'Brain' | 'Lab'; tone: string }[] = [
    { label: 'Ops', tone: '#fbbf24' },
    { label: 'Brain', tone: '#38bdf8' },
    { label: 'Lab', tone: '#34d399' },
  ];
  return (
    <div style={{ position: 'fixed', bottom: '32px', left: 0, right: 0, display: 'flex', justifyContent: 'center', pointerEvents: 'none' }}>
      <div style={{ display: 'flex', gap: '12px', padding: '10px 16px', background: 'rgba(2,6,23,0.9)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: '999px', boxShadow: '0 20px 50px rgba(0,0,0,0.45)', pointerEvents: 'auto' }}>
        {buttons.map((btn) => (
          <span
            key={btn.label}
            style={{
              padding: '10px 18px',
              borderRadius: '999px',
              backgroundColor: btn.label === active ? `${btn.tone}22` : 'transparent',
              border: btn.label === active ? `1px solid ${btn.tone}` : '1px solid transparent',
              color: btn.label === active ? 'white' : '#94a3b8',
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
