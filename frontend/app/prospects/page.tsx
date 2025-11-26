'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { getApiUrl, apiFetch } from '@/lib/api-client';
import NavHeader from '@/components/NavHeader';

const API_URL = getApiUrl();

type Prospect = {
  id: string;
  name?: string;
  company?: string;
  job_title?: string;
  email?: string;
  fit_score?: number;
  status?: 'new' | 'analyzed' | 'contacted' | 'follow_up_needed';
  tags?: string[];
  last_action?: string;
  notes?: string;
  summary?: string;
  pain_points?: string[];
  source_url?: string;
  created_at?: string;
};

type ProspectStatus = 'all' | 'new' | 'analyzed' | 'contacted' | 'follow_up_needed';

const STATUS_OPTIONS = [
  { value: 'new', label: 'New', color: 'bg-blue-100 text-blue-800' },
  { value: 'analyzed', label: 'Analyzed', color: 'bg-purple-100 text-purple-800' },
  { value: 'contacted', label: 'Contacted', color: 'bg-green-100 text-green-800' },
  { value: 'follow_up_needed', label: 'Follow-up', color: 'bg-orange-100 text-orange-800' },
];

export default function ProspectsPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProspectStatus>('all');
  const [minFitScore, setMinFitScore] = useState(0);
  const [sortBy, setSortBy] = useState<'fit_score' | 'company' | 'name' | 'created_at'>('fit_score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  
  // Selection
  const [selectedProspects, setSelectedProspects] = useState<Set<string>>(new Set());
  
  // Inline editing
  const [editingStatus, setEditingStatus] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  useEffect(() => {
    loadProspects();
  }, []);

  const loadProspects = async () => {
    if (!API_URL) {
      setError('API URL not configured');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const params = new URLSearchParams({
        user_id: 'dev-user',
        limit: '500',
      });

      const response = await fetch(`${API_URL}/api/prospects/?${params.toString()}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          setProspects([]);
          setError(null);
          return;
        }
        throw new Error(`Failed to load prospects: ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.success && data.prospects) {
        setProspects(data.prospects.map((p: any) => ({
          id: p.id,
          name: p.name,
          company: p.company,
          job_title: p.job_title,
          email: p.email,
          fit_score: p.fit_score,
          status: p.status || 'new',
          tags: p.tags || [],
          last_action: p.last_action,
          summary: p.summary || p.analysis?.summary,
          pain_points: p.pain_points || [],
          source_url: p.source_url,
          created_at: p.created_at,
        })));
        setError(null);
      } else {
        setProspects([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load prospects');
    } finally {
      setLoading(false);
    }
  };

  const updateProspectStatus = async (prospectId: string, newStatus: string) => {
    try {
      const response = await apiFetch(`/api/prospects/${prospectId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      
      if (response.ok) {
        setProspects(prev => prev.map(p => 
          p.id === prospectId ? { ...p, status: newStatus as any } : p
        ));
      }
    } catch (err) {
      console.error('Failed to update status:', err);
    }
    setEditingStatus(null);
  };

  // Filter and sort prospects
  const filteredProspects = useMemo(() => {
    return prospects
      .filter(p => {
        // Search filter
        if (searchQuery) {
          const query = searchQuery.toLowerCase();
          const matchesSearch = 
            p.name?.toLowerCase().includes(query) ||
            p.company?.toLowerCase().includes(query) ||
            p.job_title?.toLowerCase().includes(query) ||
            p.email?.toLowerCase().includes(query) ||
            p.tags?.some(t => t.toLowerCase().includes(query));
          if (!matchesSearch) return false;
        }
        
        // Status filter
        if (statusFilter !== 'all' && p.status !== statusFilter) return false;
        
        // Fit score filter
        if (minFitScore > 0 && (p.fit_score || 0) < minFitScore / 100) return false;
        
        return true;
      })
      .sort((a, b) => {
        let comparison = 0;
        switch (sortBy) {
          case 'fit_score':
            comparison = (a.fit_score || 0) - (b.fit_score || 0);
            break;
          case 'company':
            comparison = (a.company || '').localeCompare(b.company || '');
            break;
          case 'name':
            comparison = (a.name || '').localeCompare(b.name || '');
            break;
          case 'created_at':
            comparison = (a.created_at || '').localeCompare(b.created_at || '');
            break;
        }
        return sortOrder === 'asc' ? comparison : -comparison;
      });
  }, [prospects, searchQuery, statusFilter, minFitScore, sortBy, sortOrder]);

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selectedProspects);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedProspects(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedProspects.size === filteredProspects.length) {
      setSelectedProspects(new Set());
    } else {
      setSelectedProspects(new Set(filteredProspects.map(p => p.id)));
    }
  };

  const getStatusColor = (status?: string) => {
    return STATUS_OPTIONS.find(s => s.value === status)?.color || 'bg-gray-100 text-gray-800';
  };

  const formatFitScore = (score?: number) => {
    if (!score) return 'N/A';
    return `${Math.round(score * 100)}%`;
  };

  const stats = useMemo(() => ({
    total: prospects.length,
    new: prospects.filter(p => p.status === 'new').length,
    contacted: prospects.filter(p => p.status === 'contacted').length,
    followUp: prospects.filter(p => p.status === 'follow_up_needed').length,
    highFit: prospects.filter(p => (p.fit_score || 0) >= 0.8).length,
  }), [prospects]);

  return (
    <main className="min-h-screen bg-gray-900">
      <NavHeader />
      {/* Sticky Header */}
      <div className="sticky top-[58px] z-10 bg-slate-800 border-b border-slate-600 shadow-sm">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white">Prospect Pipeline</h1>
              <p className="text-sm text-gray-400">{filteredProspects.length} of {prospects.length} prospects</p>
            </div>
            <div className="flex items-center gap-3">
              {selectedProspects.size > 0 && (
                <button
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
                  onClick={() => alert(`Generate DMs for ${selectedProspects.size} prospects`)}
                >
                  Generate DMs ({selectedProspects.size})
                </button>
              )}
              <Link
                href="/prospect-discovery"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                + Find Prospects
              </Link>
            </div>
          </div>

          {/* Filters Row */}
          <div className="flex flex-wrap items-center gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[200px] max-w-md">
              <input
                type="text"
                placeholder="Search name, company, tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-4 py-2 border border-slate-600 bg-slate-700 text-white rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ProspectStatus)}
              className="px-3 py-2 border border-slate-600 bg-slate-700 text-white rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Status</option>
              {STATUS_OPTIONS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>

            {/* Fit Score Filter */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-300">Min Fit:</span>
              <input
                type="range"
                min="0"
                max="100"
                value={minFitScore}
                onChange={(e) => setMinFitScore(Number(e.target.value))}
                className="w-24"
              />
              <span className="text-sm text-white w-10">{minFitScore}%</span>
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="px-3 py-2 border border-slate-600 bg-slate-700 text-white rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="fit_score">Sort: Fit Score</option>
              <option value="name">Sort: Name</option>
              <option value="company">Sort: Company</option>
              <option value="created_at">Sort: Date Added</option>
            </select>

            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="px-3 py-2 border border-slate-600 bg-slate-700 text-white rounded-lg text-sm hover:bg-slate-600"
            >
              {sortOrder === 'asc' ? '↑' : '↓'}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-[1600px] mx-auto px-6 py-6">
        {/* Quick Stats */}
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="bg-slate-800 rounded-lg border border-slate-600 p-4">
            <div className="text-2xl font-bold text-white">{stats.total}</div>
            <div className="text-sm text-gray-400">Total</div>
          </div>
          <div className="bg-slate-800 rounded-lg border border-slate-600 p-4">
            <div className="text-2xl font-bold text-blue-400">{stats.new}</div>
            <div className="text-sm text-gray-400">New</div>
          </div>
          <div className="bg-slate-800 rounded-lg border border-slate-600 p-4">
            <div className="text-2xl font-bold text-green-400">{stats.contacted}</div>
            <div className="text-sm text-gray-400">Contacted</div>
          </div>
          <div className="bg-slate-800 rounded-lg border border-slate-600 p-4">
            <div className="text-2xl font-bold text-orange-400">{stats.followUp}</div>
            <div className="text-sm text-gray-400">Follow-up</div>
          </div>
          <div className="bg-slate-800 rounded-lg border border-slate-600 p-4">
            <div className="text-2xl font-bold text-purple-400">{stats.highFit}</div>
            <div className="text-sm text-gray-400">High Fit (80%+)</div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-6">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="text-center py-12">
            <p className="text-gray-600">Loading prospects...</p>
          </div>
        ) : (
          /* Prospects Table */
          <div className="bg-slate-800 rounded-lg border-2 border-slate-600 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-700 border-b-2 border-slate-500">
                  <tr>
                    <th className="px-4 py-4 text-left w-10 border-r border-slate-600">
                      <input
                        type="checkbox"
                        checked={selectedProspects.size === filteredProspects.length && filteredProspects.length > 0}
                        onChange={toggleSelectAll}
                        className="rounded"
                      />
                    </th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wider border-r border-slate-600">
                      Name
                    </th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wider border-r border-slate-600">
                      Company
                    </th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wider w-24 border-r border-slate-600">
                      Fit
                    </th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wider w-32 border-r border-slate-600">
                      Status
                    </th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wider border-r border-slate-600">
                      Tags
                    </th>
                    <th className="px-4 py-4 text-left text-sm font-bold text-white uppercase tracking-wider w-40">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-600">
                  {filteredProspects.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center text-gray-400">
                        {prospects.length === 0 ? (
                          <>
                            No prospects yet.{' '}
                            <Link href="/prospect-discovery" className="text-blue-600 hover:underline">
                              Find some prospects
                            </Link>{' '}
                            to get started.
                          </>
                        ) : (
                          'No prospects match your filters.'
                        )}
                      </td>
                    </tr>
                  ) : (
                    filteredProspects.map((prospect) => (
                      <>
                        <tr
                          key={prospect.id}
                          className={`hover:bg-slate-700 transition-colors ${expandedRow === prospect.id ? 'bg-slate-700' : ''}`}
                        >
                          <td className="px-4 py-4 border-r border-slate-700">
                            <input
                              type="checkbox"
                              checked={selectedProspects.has(prospect.id)}
                              onChange={() => toggleSelect(prospect.id)}
                              className="rounded"
                            />
                          </td>
                          <td className="px-4 py-4 border-r border-slate-700">
                            <button
                              onClick={() => setExpandedRow(expandedRow === prospect.id ? null : prospect.id)}
                              className="text-left w-full"
                            >
                              <div className="font-medium text-white hover:text-blue-400">
                                {prospect.name || 'N/A'}
                              </div>
                              {prospect.job_title && (
                                <div className="text-sm text-gray-400">{prospect.job_title}</div>
                              )}
                            </button>
                          </td>
                          <td className="px-4 py-4 text-sm text-gray-200 border-r border-slate-700">{prospect.company || '—'}</td>
                          <td className="px-4 py-4 border-r border-slate-700">
                            <div className="flex items-center gap-2">
                              <div className="w-12 h-2 bg-slate-600 rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${
                                    (prospect.fit_score || 0) >= 0.8
                                      ? 'bg-green-500'
                                      : (prospect.fit_score || 0) >= 0.6
                                      ? 'bg-yellow-500'
                                      : 'bg-red-500'
                                  }`}
                                  style={{ width: `${(prospect.fit_score || 0) * 100}%` }}
                                />
                              </div>
                              <span className="text-sm font-medium text-white">{formatFitScore(prospect.fit_score)}</span>
                            </div>
                          </td>
                          <td className="px-4 py-4 border-r border-slate-700">
                            {editingStatus === prospect.id ? (
                              <select
                                autoFocus
                                value={prospect.status}
                                onChange={(e) => updateProspectStatus(prospect.id, e.target.value)}
                                onBlur={() => setEditingStatus(null)}
                                className="text-xs rounded border-gray-300 focus:ring-blue-500"
                              >
                                {STATUS_OPTIONS.map(s => (
                                  <option key={s.value} value={s.value}>{s.label}</option>
                                ))}
                              </select>
                            ) : (
                              <button
                                onClick={() => setEditingStatus(prospect.id)}
                                className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(prospect.status)} hover:opacity-80`}
                              >
                                {prospect.status?.replace('_', ' ') || 'new'}
                              </button>
                            )}
                          </td>
                          <td className="px-4 py-4 border-r border-slate-700">
                            <div className="flex flex-wrap gap-1">
                              {prospect.tags?.slice(0, 2).map((tag, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex px-2 py-0.5 text-xs font-medium bg-blue-600 text-white rounded"
                                >
                                  {tag}
                                </span>
                              ))}
                              {prospect.tags && prospect.tags.length > 2 && (
                                <span className="text-xs text-gray-400">+{prospect.tags.length - 2}</span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-4">
                            <div className="flex items-center gap-2">
                              <Link
                                href={`/outreach/${prospect.id}`}
                                className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                              >
                                DM
                              </Link>
                              {prospect.email && (
                                <a
                                  href={`mailto:${prospect.email}`}
                                  className="text-gray-600 hover:text-gray-800 text-sm"
                                >
                                  Email
                                </a>
                              )}
                              {prospect.source_url && (
                                <a
                                  href={prospect.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-gray-400 hover:text-gray-600 text-sm"
                                >
                                  Source
                                </a>
                              )}
                            </div>
                          </td>
                        </tr>
                        {/* Expanded Row */}
                        {expandedRow === prospect.id && (
                          <tr key={`${prospect.id}-expanded`} className="bg-slate-700">
                            <td colSpan={7} className="px-4 py-4">
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <h4 className="font-medium text-white mb-2">Contact Info</h4>
                                  <div className="space-y-1 text-gray-300">
                                    {prospect.email && <div>📧 {prospect.email}</div>}
                                    {prospect.source_url && (
                                      <div>
                                        🔗{' '}
                                        <a href={prospect.source_url} target="_blank" className="text-blue-600 hover:underline">
                                          {prospect.source_url.slice(0, 50)}...
                                        </a>
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <div>
                                  {prospect.summary && (
                                    <>
                                      <h4 className="font-medium text-white mb-2">Summary</h4>
                                      <p className="text-gray-300">{prospect.summary}</p>
                                    </>
                                  )}
                                  {prospect.pain_points && prospect.pain_points.length > 0 && (
                                    <>
                                      <h4 className="font-medium text-white mt-3 mb-2">Pain Points</h4>
                                      <ul className="list-disc list-inside text-gray-300">
                                        {prospect.pain_points.map((pp, i) => (
                                          <li key={i}>{pp}</li>
                                        ))}
                                      </ul>
                                    </>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
