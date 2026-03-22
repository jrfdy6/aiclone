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

export default function LabPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
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
            <BuildLogCard automations={automations} />
          </div>
        )}
        {activeTab === 'prototypes' && <PrototypeCard running={running} proposed={proposed} />}
        {activeTab === 'buildLogs' && <BuildLogCard automations={automations} expanded />}
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

function PrototypeStat({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ flex: 1, borderRadius: '12px', border: '1px solid #1f2937', backgroundColor: '#071814', padding: '12px' }}>
      <p style={{ color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: '#34d399', fontSize: '22px', fontWeight: 600 }}>{value}</p>
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
