'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api-client';

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
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header */}
        <header className="space-y-3">
          <Link href="/" className="text-purple-400 hover:text-purple-300 text-sm">
            ← Back to Home
          </Link>
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              Topic Intelligence
            </h1>
            <p className="mt-2 text-lg text-gray-400">
              Research themes to learn language, pain points, and generate content ideas
            </p>
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-red-400">
            {error}
          </div>
        )}

        {/* Theme Selection */}
        <section className="rounded-xl border border-purple-500/30 bg-slate-800/50 backdrop-blur p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Select Intelligence Theme</h2>
          
          {loadingThemes ? (
            <div className="text-gray-400">Loading themes...</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {themes.map((theme) => (
                <button
                  key={theme.id}
                  onClick={() => setSelectedTheme(theme.id)}
                  className={`p-4 rounded-lg border text-left transition-all ${
                    selectedTheme === theme.id
                      ? 'border-purple-500 bg-purple-500/20 text-white'
                      : 'border-slate-600 bg-slate-700/50 text-gray-300 hover:border-purple-500/50'
                  }`}
                >
                  <div className="font-medium">{theme.name}</div>
                  <div className="text-sm text-gray-400 mt-1">{theme.dork_count} search queries</div>
                </button>
              ))}
            </div>
          )}

          {selectedThemeData && (
            <div className="mt-4 p-4 rounded-lg bg-slate-700/50 border border-slate-600">
              <h3 className="text-sm font-medium text-purple-400 mb-2">Sources for {selectedThemeData.name}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {selectedThemeData.sources.map((source, i) => (
                  <div key={i} className="text-sm">
                    <span className="text-white">{source.source}</span>
                    <span className="text-gray-500"> → {source.extracts}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={runIntelligence}
            disabled={loading || !selectedTheme}
            className="mt-6 w-full py-3 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Running Intelligence (30-60s)...
              </span>
            ) : (
              'Run Topic Intelligence'
            )}
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

