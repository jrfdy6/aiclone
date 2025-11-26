'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api-client';
import NavHeader from '@/components/NavHeader';

interface Theme {
  id: string;
  name: string;
  dork_count: number;
  sources: { source: string; extracts: string }[];
}

interface ProspectIntelligence {
  target_personas: string[];
  pain_points: string[];
  language_patterns: string[];
  decision_triggers: string[];
  objections: string[];
}

interface OutreachTemplate {
  type: string;
  subject?: string;
  body: string;
  personalization_hooks: string[];
}

interface ContentIdea {
  format: string;
  headline: string;
  outline: string[];
  cta?: string;
}

interface TopicResult {
  theme: string;
  theme_display: string;
  research_id: string;
  sources_scraped: number;
  summary: string;
  prospect_intelligence: ProspectIntelligence;
  outreach_templates: OutreachTemplate[];
  content_ideas: ContentIdea[];
  keywords: string[];
  trending_topics: string[];
  dorks_used: string[];
  dork_performance: { dork_index: number; dork: string; sources_found: number }[];
}

export default function TopicIntelligencePage() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [selectedTheme, setSelectedTheme] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [loadingThemes, setLoadingThemes] = useState(true);
  const [result, setResult] = useState<TopicResult | null>(null);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'intelligence' | 'outreach' | 'content'>('intelligence');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchThemes();
  }, []);

  const fetchThemes = async () => {
    try {
      const response = await apiFetch('/api/topic-intelligence/themes');
      const data = await response.json();
      setThemes(data.themes || []);
    } catch (err) {
      setError('Failed to load themes');
    } finally {
      setLoadingThemes(false);
    }
  };

  const runIntelligence = async () => {
    if (!selectedTheme) {
      setError('Please select a theme');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await apiFetch('/api/topic-intelligence/run', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'dev-user',
          theme: selectedTheme,
          generate_content: true,
          generate_outreach: true,
        }),
      });

      const data = await response.json();
      
      if (data.success && data.result) {
        setResult(data.result);
      } else {
        setError(data.error || 'Failed to run intelligence');
      }
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const selectedThemeData = themes.find(t => t.id === selectedTheme);

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        {/* Header */}
        <header style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Topic Intelligence
          </h1>
          <p style={{ color: '#9ca3af' }}>
            Research themes to learn language, pain points, and generate content ideas
          </p>
        </header>

        {error && (
          <div style={{ borderRadius: '8px', border: '1px solid #ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '16px', color: '#f87171', marginBottom: '24px' }}>
            {error}
          </div>
        )}

        {/* Theme Selection */}
        <section style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>Select Intelligence Theme</h2>
          
          {loadingThemes ? (
            <div style={{ color: '#9ca3af' }}>Loading themes...</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              {themes.map((theme) => (
                <button
                  key={theme.id}
                  onClick={() => setSelectedTheme(theme.id)}
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    border: selectedTheme === theme.id ? '2px solid #a855f7' : '1px solid #475569',
                    backgroundColor: selectedTheme === theme.id ? 'rgba(168, 85, 247, 0.2)' : '#334155',
                    color: 'white',
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 500 }}>{theme.name}</div>
                  <div style={{ fontSize: '14px', color: '#9ca3af', marginTop: '4px' }}>{theme.dork_count} search queries</div>
                </button>
              ))}
            </div>
          )}

          {selectedThemeData && (
            <div style={{ marginTop: '16px', padding: '16px', borderRadius: '8px', backgroundColor: '#334155', border: '1px solid #475569' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#a855f7', marginBottom: '8px' }}>Sources for {selectedThemeData.name}</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                {selectedThemeData.sources.map((source, i) => (
                  <div key={i} style={{ fontSize: '14px' }}>
                    <span style={{ color: 'white' }}>{source.source}</span>
                    <span style={{ color: '#6b7280' }}> → {source.extracts}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={runIntelligence}
            disabled={loading || !selectedTheme}
            style={{
              marginTop: '24px',
              width: '100%',
              padding: '12px',
              borderRadius: '8px',
              background: 'linear-gradient(to right, #9333ea, #ec4899)',
              color: 'white',
              fontWeight: 500,
              border: 'none',
              cursor: loading || !selectedTheme ? 'not-allowed' : 'pointer',
              opacity: loading || !selectedTheme ? 0.5 : 1,
            }}
          >
            {loading ? 'Running Intelligence (30-60s)...' : 'Run Topic Intelligence'}
          </button>
        </section>

        {/* Results */}
        {result && (
          <section className="space-y-6">
            {/* Summary */}
            <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-6">
              <div className="flex items-center gap-2 text-green-400 mb-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="font-medium">Research Complete</span>
              </div>
              <p className="text-gray-300">{result.summary}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {result.dorks_used.map((dork, i) => (
                  <span key={i} className="px-2 py-1 rounded bg-slate-700 text-xs text-gray-400">
                    {dork}
                  </span>
                ))}
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 border-b border-slate-700 pb-2">
              {(['intelligence', 'outreach', 'content'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
                    activeTab === tab
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {tab === 'intelligence' && 'Prospect Intelligence'}
                  {tab === 'outreach' && 'Outreach Templates'}
                  {tab === 'content' && 'Content Ideas'}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            {activeTab === 'intelligence' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Target Personas */}
                <div className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
                  <h3 className="text-lg font-semibold text-purple-400 mb-3">Target Personas</h3>
                  <div className="flex flex-wrap gap-2">
                    {result.prospect_intelligence.target_personas.map((persona, i) => (
                      <span key={i} className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 text-sm">
                        {persona}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Pain Points */}
                <div className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
                  <h3 className="text-lg font-semibold text-red-400 mb-3">Pain Points</h3>
                  <ul className="space-y-2">
                    {result.prospect_intelligence.pain_points.slice(0, 5).map((pain, i) => (
                      <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                        <span className="text-red-400 mt-1">•</span>
                        {pain.slice(0, 150)}...
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Language Patterns */}
                <div className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
                  <h3 className="text-lg font-semibold text-blue-400 mb-3">Language Patterns</h3>
                  <div className="flex flex-wrap gap-2">
                    {result.prospect_intelligence.language_patterns.map((pattern, i) => (
                      <span key={i} className="px-3 py-1 rounded bg-blue-500/20 text-blue-300 text-sm">
                        {pattern}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Decision Triggers */}
                <div className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
                  <h3 className="text-lg font-semibold text-green-400 mb-3">Decision Triggers</h3>
                  <div className="flex flex-wrap gap-2">
                    {result.prospect_intelligence.decision_triggers.map((trigger, i) => (
                      <span key={i} className="px-3 py-1 rounded bg-green-500/20 text-green-300 text-sm">
                        {trigger}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Keywords */}
                <div className="rounded-xl border border-slate-600 bg-slate-800/50 p-6 md:col-span-2">
                  <h3 className="text-lg font-semibold text-yellow-400 mb-3">Keywords</h3>
                  <div className="flex flex-wrap gap-2">
                    {result.keywords.map((keyword, i) => (
                      <span key={i} className="px-2 py-1 rounded bg-yellow-500/20 text-yellow-300 text-xs">
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'outreach' && (
              <div className="space-y-6">
                {result.outreach_templates.map((template, i) => (
                  <div key={i} className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-lg font-semibold text-white capitalize">
                        {template.type.replace('_', ' ')} Template
                      </h3>
                      <button
                        onClick={() => copyToClipboard(template.body)}
                        className="px-3 py-1 rounded bg-purple-600 text-white text-sm hover:bg-purple-500"
                      >
                        {copied ? '✓ Copied' : 'Copy'}
                      </button>
                    </div>
                    {template.subject && (
                      <div className="text-sm text-gray-400 mb-2">
                        <span className="text-purple-400">Subject:</span> {template.subject}
                      </div>
                    )}
                    <pre className="whitespace-pre-wrap text-sm text-gray-300 bg-slate-900 p-4 rounded-lg">
                      {template.body}
                    </pre>
                    <div className="mt-3">
                      <span className="text-xs text-gray-500">Personalization hooks:</span>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {template.personalization_hooks.map((hook, j) => (
                          <span key={j} className="px-2 py-1 rounded bg-slate-700 text-xs text-gray-400">
                            {hook}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === 'content' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {result.content_ideas.map((idea, i) => (
                  <div key={i} className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="px-2 py-1 rounded bg-pink-500/20 text-pink-300 text-xs uppercase">
                        {idea.format}
                      </span>
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-3">{idea.headline}</h3>
                    <ul className="space-y-1 mb-3">
                      {idea.outline.map((point, j) => (
                        <li key={j} className="text-sm text-gray-400 flex items-start gap-2">
                          <span className="text-pink-400">{j + 1}.</span>
                          {point}
                        </li>
                      ))}
                    </ul>
                    {idea.cta && (
                      <div className="text-sm text-purple-400 italic">
                        CTA: {idea.cta}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Dork Performance */}
            <div className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Dork Performance (This Run)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400 border-b border-slate-700">
                      <th className="text-left py-2">Index</th>
                      <th className="text-left py-2">Query</th>
                      <th className="text-right py-2">Sources Found</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.dork_performance.map((perf, i) => (
                      <tr key={i} className="border-b border-slate-700/50">
                        <td className="py-2 text-gray-500">{perf.dork_index}</td>
                        <td className="py-2 text-gray-300">{perf.dork}</td>
                        <td className="py-2 text-right">
                          <span className={`px-2 py-1 rounded ${
                            perf.sources_found >= 10 ? 'bg-green-500/20 text-green-400' :
                            perf.sources_found >= 5 ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-red-500/20 text-red-400'
                          }`}>
                            {perf.sources_found}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

