'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api-client';
import NavHeader from '@/components/NavHeader';

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
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'free' | 'ai' | 'urls'>('free');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [error, setError] = useState('');
  const [savedMessage, setSavedMessage] = useState('');
  const [selectedProspects, setSelectedProspects] = useState<Set<number>>(new Set());

  // AI Search form
  const [specialty, setSpecialty] = useState('educational consultant');
  const [location, setLocation] = useState('Washington DC');
  const [additionalContext, setAdditionalContext] = useState('');
  const [maxResults, setMaxResults] = useState(10);

  // URL Scraping form
  const [urls, setUrls] = useState('');

  const runFreeSearch = async (saveToProspects = false) => {
    if (!specialty || !location) {
      setError('Please enter specialty and location');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);
    setSavedMessage('');

    try {
      const response = await apiFetch('/api/prospect-discovery/search-free', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'dev-user',
          specialty,
          location,
          additional_context: additionalContext || undefined,
          max_results: maxResults,
          save_to_prospects: saveToProspects,
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        setResult(data);
        if (saveToProspects && data.total_found > 0) {
          setSavedMessage(`✓ ${data.total_found} prospects saved to your pipeline`);
        }
      } else {
        setError(data.error || 'Search failed');
      }
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const runAISearch = async (saveToProspects = false) => {
    if (!specialty || !location) {
      setError('Please enter specialty and location');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);
    setSavedMessage('');

    try {
      const response = await apiFetch('/api/prospect-discovery/ai-search', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'dev-user',
          specialty,
          location,
          additional_context: additionalContext || undefined,
          max_results: maxResults,
          save_to_prospects: saveToProspects,
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        setResult(data);
        if (saveToProspects && data.total_found > 0) {
          setSavedMessage(`✓ ${data.total_found} prospects saved to your pipeline`);
        }
      } else {
        setError(data.error || 'Search failed');
      }
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const scrapeUrls = async (saveToProspects = false) => {
    const urlList = urls.split('\n').map(u => u.trim()).filter(Boolean);
    
    if (urlList.length === 0) {
      setError('Please enter at least one URL');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);
    setSavedMessage('');

    try {
      const response = await apiFetch('/api/prospect-discovery/scrape-urls', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'dev-user',
          urls: urlList,
          save_to_prospects: saveToProspects,
        }),
      });

      const data = await response.json();
      
      if (data.success) {
        setResult(data);
        if (saveToProspects && data.total_found > 0) {
          setSavedMessage(`✓ ${data.total_found} prospects saved to your pipeline`);
        }
      } else {
        setError(data.error || 'Scraping failed');
      }
    } catch (err: any) {
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const saveSelectedProspects = async () => {
    if (!result || selectedProspects.size === 0) return;
    
    setSaving(true);
    try {
      const prospectsToSave = result.prospects.filter((_, i) => selectedProspects.has(i));
      
      const response = await apiFetch('/api/prospects/', {
        method: 'POST',
        body: JSON.stringify({
          user_id: 'dev-user',
          prospects: prospectsToSave.map(p => ({
            name: p.name,
            company: p.organization,
            job_title: p.title,
            email: p.contact.email,
            fit_score: p.fit_score / 100,
            status: 'new',
            tags: p.specialty,
            source_url: p.source_url,
          })),
        }),
      });

      if (response.ok) {
        setSavedMessage(`✓ ${selectedProspects.size} prospects saved to your pipeline`);
        setSelectedProspects(new Set());
      }
    } catch (err: any) {
      setError('Failed to save prospects');
    } finally {
      setSaving(false);
    }
  };

  const toggleProspect = (index: number) => {
    const newSet = new Set(selectedProspects);
    if (newSet.has(index)) {
      newSet.delete(index);
    } else {
      newSet.add(index);
    }
    setSelectedProspects(newSet);
  };

  const selectAll = () => {
    if (result) {
      if (selectedProspects.size === result.prospects.length) {
        setSelectedProspects(new Set());
      } else {
        setSelectedProspects(new Set(result.prospects.map((_, i) => i)));
      }
    }
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        {/* Header */}
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
              Prospect Discovery
            </h1>
            <p style={{ color: '#9ca3af' }}>
              Find and save prospects to your pipeline
            </p>
          </div>
          <Link
            href="/prospects"
            style={{
              padding: '10px 20px',
              backgroundColor: '#2563eb',
              color: 'white',
              borderRadius: '8px',
              textDecoration: 'none',
              fontWeight: 500,
            }}
          >
            View Pipeline →
          </Link>
        </header>

        {error && (
          <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-red-400">
            {error}
          </div>
        )}

        {savedMessage && (
          <div className="rounded-lg border border-green-500/50 bg-green-500/10 p-4 text-green-400 flex items-center justify-between">
            <span>{savedMessage}</span>
            <Link href="/prospects" className="text-green-300 hover:text-green-200 underline">
              View in Pipeline →
            </Link>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('free')}
            className={`px-6 py-3 rounded-lg font-medium transition-all ${
              activeTab === 'free'
                ? 'bg-green-600 text-white'
                : 'bg-slate-800 text-gray-400 hover:text-white'
            }`}
          >
            🆓 Free Search
          </button>
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

        {/* Search Forms */}
        {(activeTab === 'free' || activeTab === 'ai') && (
          <section className={`rounded-xl border ${activeTab === 'free' ? 'border-green-500/30' : 'border-blue-500/30'} bg-slate-800/50 backdrop-blur p-6`}>
            <div className="flex items-center gap-2 mb-4">
              <h2 className="text-xl font-semibold text-white">
                {activeTab === 'free' ? 'Free Prospect Search' : 'AI-Powered Search'}
              </h2>
              <span className={`px-2 py-1 rounded text-xs ${activeTab === 'free' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                {activeTab === 'free' ? '100/day FREE' : '~$0.005/query'}
              </span>
            </div>

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

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => activeTab === 'free' ? runFreeSearch(false) : runAISearch(false)}
                disabled={loading}
                className="flex-1 py-3 rounded-lg bg-slate-700 text-white font-medium hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? 'Searching...' : '🔍 Preview Results'}
              </button>
              <button
                onClick={() => activeTab === 'free' ? runFreeSearch(true) : runAISearch(true)}
                disabled={loading}
                className={`flex-1 py-3 rounded-lg text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-all ${
                  activeTab === 'free' 
                    ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500'
                    : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500'
                }`}
              >
                {loading ? 'Searching...' : '🔍 Find & Save to Pipeline'}
              </button>
            </div>
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
                placeholder="https://www.psychologytoday.com/us/therapists/jane-doe-12345"
                rows={6}
                className="w-full px-4 py-2 rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none font-mono text-sm"
              />
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => scrapeUrls(false)}
                disabled={loading}
                className="flex-1 py-3 rounded-lg bg-slate-700 text-white font-medium hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? 'Scraping...' : '🔗 Preview Results'}
              </button>
              <button
                onClick={() => scrapeUrls(true)}
                disabled={loading}
                className="flex-1 py-3 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-medium hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? 'Scraping...' : '🔗 Scrape & Save to Pipeline'}
              </button>
            </div>
          </section>
        )}

        {/* Results */}
        {result && (
          <section className="space-y-4">
            {/* Summary */}
            <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-green-400">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="font-medium">Found {result.total_found} Prospects</span>
              </div>
              {result.prospects.length > 0 && !savedMessage && (
                <div className="flex items-center gap-3">
                  <button
                    onClick={selectAll}
                    className="text-sm text-gray-400 hover:text-white"
                  >
                    {selectedProspects.size === result.prospects.length ? 'Deselect All' : 'Select All'}
                  </button>
                  {selectedProspects.size > 0 && (
                    <button
                      onClick={saveSelectedProspects}
                      disabled={saving}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm disabled:opacity-50"
                    >
                      {saving ? 'Saving...' : `Save ${selectedProspects.size} Selected`}
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Results Table */}
            <div className="rounded-xl border-2 border-slate-500 bg-slate-900 overflow-hidden shadow-xl">
              <table className="w-full border-collapse">
                <thead className="bg-slate-700">
                  <tr className="border-b-2 border-slate-500">
                    <th className="px-4 py-4 text-left w-12 border-r border-slate-600">
                      <input
                        type="checkbox"
                        checked={selectedProspects.size === result.prospects.length && result.prospects.length > 0}
                        onChange={selectAll}
                        className="rounded w-4 h-4"
                      />
                    </th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wide border-r border-slate-600">Name</th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wide border-r border-slate-600">Organization</th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wide border-r border-slate-600">Specialty</th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wide border-r border-slate-600 w-20">Fit</th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wide">Contact</th>
                  </tr>
                </thead>
                <tbody>
                  {result.prospects.map((prospect, i) => (
                    <tr 
                      key={i} 
                      className={`border-b border-slate-600 hover:bg-slate-800 transition-colors ${i % 2 === 0 ? 'bg-slate-900' : 'bg-slate-850'}`}
                    >
                      <td className="px-4 py-4 border-r border-slate-700">
                        <input
                          type="checkbox"
                          checked={selectedProspects.has(i)}
                          onChange={() => toggleProspect(i)}
                          className="rounded w-4 h-4"
                        />
                      </td>
                      <td className="px-4 py-4 border-r border-slate-700">
                        <div className="font-semibold text-white text-base">{prospect.name || 'Unknown'}</div>
                        {prospect.title && <div className="text-sm text-gray-400 mt-1">{prospect.title}</div>}
                      </td>
                      <td className="px-4 py-4 border-r border-slate-700 text-gray-200">{prospect.organization || '—'}</td>
                      <td className="px-4 py-4 border-r border-slate-700">
                        <div className="flex flex-wrap gap-1">
                          {prospect.specialty.slice(0, 2).map((s, j) => (
                            <span key={j} className="px-2 py-1 rounded bg-blue-600 text-white text-xs font-medium">
                              {s}
                            </span>
                          ))}
                          {prospect.specialty.length > 2 && (
                            <span className="text-xs text-gray-400">+{prospect.specialty.length - 2}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-4 border-r border-slate-700">
                        <span className={`px-3 py-1.5 rounded-full text-sm font-bold ${
                          prospect.fit_score >= 80 ? 'bg-green-600 text-white' :
                          prospect.fit_score >= 60 ? 'bg-yellow-500 text-black' :
                          'bg-gray-600 text-white'
                        }`}>
                          {prospect.fit_score}%
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex gap-3">
                          {prospect.contact.email && (
                            <a href={`mailto:${prospect.contact.email}`} className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-500 transition-colors">
                              Email
                            </a>
                          )}
                          {prospect.source_url && (
                            <a href={prospect.source_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1 bg-slate-600 text-white rounded text-sm hover:bg-slate-500 transition-colors">
                              Source
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
