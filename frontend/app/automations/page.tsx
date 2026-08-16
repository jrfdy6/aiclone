'use client';

import { useEffect, useMemo, useState } from 'react';
import NavHeader from '@/components/NavHeader';
import { getApiUrl } from '@/lib/api-client';

type AutomationInstruction = {
  title: string;
  detail: string;
};

type Automation = {
  id: string;
  name: string;
  description: string;
  type: 'scheduled' | 'triggered' | 'manual' | string;
  status: 'active' | 'paused' | 'error' | string;
  schedule: string;
  cron: string;
  channel: string;
  isolation: boolean;
  last_run_at?: string;
  next_run_at?: string;
  last_status?: string;
  instructions: AutomationInstruction[];
  metrics?: Record<string, string>;
  notes?: string;
};

const filters = [
  { id: 'all', label: 'All' },
  { id: 'scheduled', label: 'Scheduled' },
  { id: 'triggered', label: 'Triggered' },
  { id: 'manual', label: 'Manual' },
  { id: 'active', label: 'Active' },
  { id: 'paused', label: 'Paused' },
];

export default function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAutomations() {
      setError(null);
      const apiUrl = getApiUrl();
      if (!apiUrl) {
        setError('NEXT_PUBLIC_API_URL is not configured.');
        setLoading(false);
        return;
      }
      try {
        const response = await fetch(`${apiUrl}/api/automations`);
        const payload = await response.json();
        if (!cancelled) {
          setAutomations(Array.isArray(payload?.data) ? payload.data : []);
        }
      } catch (err) {
        console.error('Failed to load automations', err);
        if (!cancelled) {
          setError('Unable to load automations from the API.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
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

  const filteredAutomations = useMemo(() => {
    if (filter === 'all') return automations;
    return automations.filter((automation) => automation.type === filter || automation.status === filter);
  }, [automations, filter]);

  const summary = useMemo(() => {
    const active = automations.filter((automation) => automation.status === 'active').length;
    return {
      total: automations.length,
      active,
      paused: automations.length - active,
    };
  }, [automations]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return '#22c55e';
      case 'paused':
        return '#f97316';
      case 'error':
        return '#ef4444';
      default:
        return '#94a3b8';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'scheduled':
        return '#38bdf8';
      case 'triggered':
        return '#facc15';
      case 'manual':
        return '#a855f7';
      default:
        return '#94a3b8';
    }
  };

  const formatTimestamp = (value?: string) => {
    if (!value) return '—';
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return `${dt.toLocaleDateString()} ${dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        <header style={{ marginBottom: '24px' }}>
          <p style={{ color: '#38bdf8', letterSpacing: '0.2em', fontSize: '12px', textTransform: 'uppercase' }}>Brain</p>
          <h1 style={{ fontSize: '32px', fontWeight: 700, color: 'white', marginBottom: '8px' }}>Automations</h1>
          <p style={{ color: '#94a3b8' }}>
            All cron jobs must mirror to Ops → Mission Control and Brain → Automations. This view reads the live automation
            manifest from the backend so we can verify schedules, isolation, and last run status.
          </p>
        </header>

        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <SummaryCard label="Total Automations" value={summary.total} tone="#38bdf8" />
          <SummaryCard label="Active" value={summary.active} tone="#22c55e" />
          <SummaryCard label="Paused/Error" value={summary.paused} tone="#f97316" />
        </section>

        <div style={{ marginBottom: '24px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {filters.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-4 py-2 rounded-lg transition-colors ${
                filter === f.id ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
              style={{ textTransform: 'capitalize' }}
            >
              {f.label}
            </button>
          ))}
        </div>

        <section style={{ backgroundColor: '#0f172a', border: '1px solid #1f2937', borderRadius: '16px', padding: '24px' }}>
          {loading && <p style={{ color: '#94a3b8' }}>Loading automations…</p>}
          {!loading && error && <p style={{ color: '#f87171' }}>{error}</p>}
          {!loading && !error && filteredAutomations.length === 0 && (
            <p style={{ color: '#94a3b8' }}>No automations match the current filter.</p>
          )}

          {!loading && !error && filteredAutomations.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {filteredAutomations.map((automation) => (
                <article
                  key={automation.id}
                  style={{
                    border: '1px solid #1f2937',
                    borderRadius: '16px',
                    padding: '20px',
                    background: 'linear-gradient(135deg, rgba(8,47,73,0.8), rgba(15,23,42,0.8))',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', marginBottom: '12px' }}>
                    <div>
                      <p style={{ color: '#38bdf8', fontSize: '12px', letterSpacing: '0.2em', textTransform: 'uppercase' }}>{automation.channel}</p>
                      <h2 style={{ fontSize: '22px', fontWeight: 600, color: 'white', margin: '4px 0' }}>{automation.name}</h2>
                      <p style={{ color: '#94a3b8', fontSize: '14px' }}>{automation.description}</p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '4px 12px',
                          borderRadius: '999px',
                          fontSize: '12px',
                          backgroundColor: '#020617',
                          color: getTypeColor(automation.type),
                          border: `1px solid ${getTypeColor(automation.type)}`,
                          marginBottom: '8px',
                        }}
                      >
                        {automation.type}
                      </span>
                      <div>
                        <span
                          style={{
                            padding: '4px 12px',
                            borderRadius: '999px',
                            fontSize: '12px',
                            backgroundColor: getStatusColor(automation.status) + '22',
                            color: getStatusColor(automation.status),
                            border: `1px solid ${getStatusColor(automation.status)}`,
                            textTransform: 'capitalize',
                          }}
                        >
                          {automation.status}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '16px' }}>
                    <DetailChip label="Schedule" value={`${automation.schedule} (${automation.cron})`} />
                    <DetailChip label="Last Run" value={formatTimestamp(automation.last_run_at)} />
                    <DetailChip label="Next Run" value={formatTimestamp(automation.next_run_at)} />
                    <DetailChip label="Isolation" value={automation.isolation ? 'Isolated session' : 'Shared runtime'} />
                    {automation.last_status && <DetailChip label="Last Status" value={automation.last_status} />}
                  </div>

                  {automation.metrics && Object.keys(automation.metrics).length > 0 && (
                    <div style={{ marginBottom: '16px' }}>
                      <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '8px' }}>Signals</p>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {Object.entries(automation.metrics).map(([key, value]) => (
                          <span
                            key={key}
                            style={{
                              borderRadius: '999px',
                              border: '1px solid #1f2937',
                              padding: '6px 12px',
                              color: '#e2e8f0',
                              fontSize: '13px',
                              backgroundColor: '#020617',
                            }}
                          >
                            <strong style={{ color: '#38bdf8', textTransform: 'capitalize', marginRight: '6px' }}>{key}:</strong>
                            {value}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div style={{ marginBottom: '12px' }}>
                    <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '6px' }}>Instructions</p>
                    <ol style={{ color: '#e2e8f0', fontSize: '14px', marginLeft: '16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {automation.instructions.map((instruction) => (
                        <li key={instruction.title}>
                          <strong style={{ color: '#38bdf8', marginRight: '6px' }}>{instruction.title}.</strong>
                          {instruction.detail}
                        </li>
                      ))}
                    </ol>
                  </div>

                  {automation.notes && (
                    <p style={{ color: '#fbbf24', fontSize: '13px' }}>Note: {automation.notes}</p>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div
      style={{
        border: '1px solid #1f2937',
        borderRadius: '16px',
        padding: '16px',
        backgroundColor: '#020617',
      }}
    >
      <p style={{ color: '#94a3b8', fontSize: '13px' }}>{label}</p>
      <p style={{ color: tone, fontSize: '28px', fontWeight: 600 }}>{value}</p>
    </div>
  );
}

function DetailChip({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        borderRadius: '12px',
        border: '1px solid #1f2937',
        padding: '12px',
        backgroundColor: '#020617',
      }}
    >
      <p style={{ color: '#64748b', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</p>
      <p style={{ color: '#e2e8f0', fontSize: '14px', marginTop: '4px' }}>{value}</p>
    </div>
  );
}
