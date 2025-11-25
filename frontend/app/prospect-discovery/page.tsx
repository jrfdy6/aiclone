'use client';

import { useState } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api-client';

interface Prospect {
  name: string;
  title?: string;
  organization?: string;
  specialty: string[];
  location?: string;
  source_url: string;
  source: string;
  contact: {
    email?: string;
    phone?: string;
    website?: string;
  };
  fit_score: number;
}

interface DiscoveryResult {
  success: boolean;
  discovery_id: string;
  source: string;
  total_found: number;
  prospects: Prospect[];
  search_query_used: string;
  error?: string;
}

export default function ProspectDiscoveryPage() {
  const [activeTab, setActiveTab] = useState<'ai' | 'urls'>('ai');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [error, setError] = useState('');

  // AI Search form
  const [specialty, setSpecialty] = useState('educational consultant');
  const [location, setLocation] = useState('Washington DC');
  const [additionalContext, setAdditionalContext] = useState('');
  const [maxResults, setMaxResults] = useState(10);

  // URL Scraping form
  const [urls, setUrls] = useState('');

  const runAISearch = async () => {
    if (!specialty || !location) {
      setError('Please enter specialty and location');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await apiFetch('/api/prospect-discovery/ai-search', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'dev-user',
          specialty,
          location,
          additional_context: additionalContext || undefined,
          max_results: maxResults,
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        setResult(data);
      } else {
        setError(data.error || 'Search failed');
      }
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const scrapeUrls = async () => {
    const urlList = urls.split('\n').map(u => u.trim()).filter(Boolean);
    
    if (urlList.length === 0) {
      setError('Please enter at least one URL');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await apiFetch('/api/prospect-discovery/scrape-urls', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'dev-user',
          urls: urlList,
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        setResult(data);
      } else {
        setError(data.error || 'Scraping failed');
      }
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Header */}
        <header className="space-y-3">
          <Link href="/" className="text-blue-400 hover:text-blue-300 text-sm">
            ← Back to Home
          </Link>
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
              Prospect Discovery
            </h1>
            <p className="mt-2 text-lg text-gray-400">
              Find real people and organizations using AI-powered search
            </p>
          </div>
        </header>

        {error && (
          <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-red-400">
            {error}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('ai')}
            className={`px-6 py-3 rounded-lg font-medium transition-all ${
              activeTab === 'ai'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-gray-400 hover:text-white'
            }`}
          >
            🤖 AI Search
          </button>
          <button
            onClick={() => setActiveTab('urls')}
            className={`px-6 py-3 rounded-lg font-medium transition-all ${
              activeTab === 'urls'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-gray-400 hover:text-white'
            }`}
          >
            🔗 Scrape URLs
          </button>
        </div>

        {/* AI Search Form */}
        {activeTab === 'ai' && (
          <section className="rounded-xl border border-blue-500/30 bg-slate-800/50 backdrop-blur p-6">
            <h2 className="text-xl font-semibold text-white mb-4">AI-Powered Prospect Search</h2>
            <p className="text-gray-400 text-sm mb-6">
              Uses Perplexity AI to find real professionals with their contact information
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Specialty *</label>
                <input
                  type="text"
                  value={specialty}
                  onChange={(e) => setSpecialty(e.target.value)}
                  placeholder="e.g., educational consultant, therapist"
                  className="w-full px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Location *</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g., Washington DC, California"
                  className="w-full px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-300 mb-1">Additional Context</label>
                <input
                  type="text"
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  placeholder="e.g., private school placement, neurodivergent students"
                  className="w-full px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Max Results</label>
                <select
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="w-full px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white focus:border-blue-500 focus:outline-none"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={15}>15</option>
                  <option value={20}>20</option>
                </select>
              </div>
            </div>

            <button
              onClick={runAISearch}
              disabled={loading}
              className="mt-6 w-full py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-medium hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Searching with AI...
                </span>
              ) : (
                '🔍 Find Prospects'
              )}
            </button>
          </section>
        )}

        {/* URL Scraping Form */}
        {activeTab === 'urls' && (
          <section className="rounded-xl border border-blue-500/30 bg-slate-800/50 backdrop-blur p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Scrape Specific URLs</h2>
            <p className="text-gray-400 text-sm mb-6">
              Paste profile URLs (e.g., from Psychology Today) to extract contact information
            </p>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">URLs (one per line)</label>
              <textarea
                value={urls}
                onChange={(e) => setUrls(e.target.value)}
                placeholder="https://www.psychologytoday.com/us/therapists/jane-doe-12345
https://www.psychologytoday.com/us/therapists/john-smith-67890"
                rows={6}
                className="w-full px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none font-mono text-sm"
              />
            </div>

            <button
              onClick={scrapeUrls}
              disabled={loading}
              className="mt-6 w-full py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-medium hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Scraping URLs...
                </span>
              ) : (
                '🔗 Scrape URLs'
              )}
            </button>
          </section>
        )}

        {/* Results */}
        {result && (
          <section className="space-y-6">
            {/* Summary */}
            <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-green-400">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="font-medium">Found {result.total_found} Prospects</span>
                </div>
                <span className="text-sm text-gray-400">ID: {result.discovery_id}</span>
              </div>
              <p className="text-gray-400 text-sm mt-2">Source: {result.source}</p>
            </div>

            {/* Prospects Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.prospects.map((prospect, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-slate-600 bg-slate-800/50 p-6 hover:border-blue-500/50 transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="text-lg font-semibold text-white">{prospect.name}</h3>
                      {prospect.title && (
                        <p className="text-sm text-blue-400">{prospect.title}</p>
                      )}
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      prospect.fit_score >= 80 ? 'bg-green-500/20 text-green-400' :
                      prospect.fit_score >= 60 ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {prospect.fit_score}% fit
                    </span>
                  </div>

                  {prospect.organization && (
                    <p className="text-sm text-gray-400 mb-2">🏢 {prospect.organization}</p>
                  )}

                  {prospect.location && (
                    <p className="text-sm text-gray-400 mb-2">📍 {prospect.location}</p>
                  )}

                  {prospect.specialty.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {prospect.specialty.map((spec, j) => (
                        <span key={j} className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-xs">
                          {spec}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="border-t border-slate-700 pt-3 mt-3 space-y-1">
                    {prospect.contact.email && (
                      <p className="text-sm">
                        <span className="text-gray-500">Email:</span>{' '}
                        <a href={`mailto:${prospect.contact.email}`} className="text-blue-400 hover:underline">
                          {prospect.contact.email}
                        </a>
                      </p>
                    )}
                    {prospect.contact.phone && (
                      <p className="text-sm">
                        <span className="text-gray-500">Phone:</span>{' '}
                        <span className="text-gray-300">{prospect.contact.phone}</span>
                      </p>
                    )}
                    {prospect.contact.website && (
                      <p className="text-sm">
                        <span className="text-gray-500">Website:</span>{' '}
                        <a href={prospect.contact.website} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                          {prospect.contact.website.replace(/^https?:\/\//, '').slice(0, 40)}...
                        </a>
                      </p>
                    )}
                    {prospect.source_url && (
                      <p className="text-sm">
                        <a href={prospect.source_url} target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-gray-300">
                          View source →
                        </a>
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {result.prospects.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                No prospects found. Try adjusting your search criteria.
              </div>
            )}
          </section>
        )}

        {/* Quick Tips */}
        <section className="rounded-xl border border-slate-600 bg-slate-800/50 p-6">
          <h2 className="text-lg font-semibold text-white mb-4">💡 Tips for Better Results</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-400">
            <div>
              <h3 className="text-blue-400 font-medium mb-1">AI Search</h3>
              <ul className="space-y-1">
                <li>• Be specific with specialty (e.g., "educational consultant" not just "consultant")</li>
                <li>• Add context like "private school" or "neurodivergent"</li>
                <li>• Try different locations for more results</li>
              </ul>
            </div>
            <div>
              <h3 className="text-blue-400 font-medium mb-1">URL Scraping</h3>
              <ul className="space-y-1">
                <li>• Works best with individual profile pages</li>
                <li>• Psychology Today profiles extract well</li>
                <li>• Paste up to 20 URLs at once</li>
              </ul>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

