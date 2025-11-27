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
    if (score === undefined || score === null) return 'N/A';
    // Backend now returns 0-100, not 0-1
    const displayScore = score > 1 ? score : score * 100;
    return `${Math.round(displayScore)}%`;
  };

  const stats = useMemo(() => ({
    total: prospects.length,
    new: prospects.filter(p => p.status === 'new').length,
    contacted: prospects.filter(p => p.status === 'contacted').length,
    followUp: prospects.filter(p => p.status === 'follow_up_needed').length,
    highFit: prospects.filter(p => (p.fit_score || 0) >= 0.8).length,
  }), [prospects]);

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      {/* Sticky Header */}
      <div style={{ position: 'sticky', top: '58px', zIndex: 10, backgroundColor: '#1e293b', borderBottom: '1px solid #475569', padding: '16px 24px' }}>
        <div style={{ maxWidth: '1600px', margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: 'white', marginBottom: '4px' }}>Prospect Pipeline</h1>
              <p style={{ fontSize: '14px', color: '#9ca3af' }}>{filteredProspects.length} of {prospects.length} prospects</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {selectedProspects.size > 0 && (
                <button
                  style={{ padding: '8px 16px', backgroundColor: '#22c55e', color: 'white', borderRadius: '8px', border: 'none', cursor: 'pointer', fontSize: '14px' }}
                  onClick={() => alert(`Generate DMs for ${selectedProspects.size} prospects`)}
                >
                  Generate DMs ({selectedProspects.size})
                </button>
              )}
              <Link
                href="/prospect-discovery"
                style={{ padding: '8px 16px', backgroundColor: '#2563eb', color: 'white', borderRadius: '8px', textDecoration: 'none', fontSize: '14px' }}
              >
                + Find Prospects
              </Link>
            </div>
          </div>

          {/* Filters Row */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '16px' }}>
            {/* Search */}
            <div style={{ flex: 1, minWidth: '200px', maxWidth: '400px' }}>
              <input
                type="text"
                placeholder="Search name, company, tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: '100%', padding: '8px 16px', border: '1px solid #475569', backgroundColor: '#334155', color: 'white', borderRadius: '8px', fontSize: '14px' }}
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ProspectStatus)}
              style={{ padding: '8px 12px', border: '1px solid #475569', backgroundColor: '#334155', color: 'white', borderRadius: '8px', fontSize: '14px' }}
            >
              <option value="all">All Status</option>
              {STATUS_OPTIONS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>

            {/* Fit Score Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '14px', color: '#9ca3af' }}>Min Fit:</span>
              <input
                type="range"
                min="0"
                max="100"
                value={minFitScore}
                onChange={(e) => setMinFitScore(Number(e.target.value))}
                style={{ width: '96px' }}
              />
              <span style={{ fontSize: '14px', color: 'white', width: '40px' }}>{minFitScore}%</span>
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              style={{ padding: '8px 12px', border: '1px solid #475569', backgroundColor: '#334155', color: 'white', borderRadius: '8px', fontSize: '14px' }}
            >
              <option value="fit_score">Sort: Fit Score</option>
              <option value="name">Sort: Name</option>
              <option value="company">Sort: Company</option>
              <option value="created_at">Sort: Date Added</option>
            </select>

            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              style={{ padding: '8px 12px', border: '1px solid #475569', backgroundColor: '#334155', color: 'white', borderRadius: '8px', fontSize: '14px', cursor: 'pointer' }}
            >
              {sortOrder === 'asc' ? '↑' : '↓'}
            </button>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: '1600px', margin: '0 auto', padding: '24px' }}>
        {/* Quick Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px', marginBottom: '24px' }}>
          <div style={{ backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #475569', padding: '16px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>{stats.total}</div>
            <div style={{ fontSize: '14px', color: '#9ca3af' }}>Total</div>
          </div>
          <div style={{ backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #475569', padding: '16px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#60a5fa' }}>{stats.new}</div>
            <div style={{ fontSize: '14px', color: '#9ca3af' }}>New</div>
          </div>
          <div style={{ backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #475569', padding: '16px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#4ade80' }}>{stats.contacted}</div>
            <div style={{ fontSize: '14px', color: '#9ca3af' }}>Contacted</div>
          </div>
          <div style={{ backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #475569', padding: '16px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fb923c' }}>{stats.followUp}</div>
            <div style={{ fontSize: '14px', color: '#9ca3af' }}>Follow-up</div>
          </div>
          <div style={{ backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #475569', padding: '16px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#c084fc' }}>{stats.highFit}</div>
            <div style={{ fontSize: '14px', color: '#9ca3af' }}>High Fit (80%+)</div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', padding: '16px', color: '#f87171', marginBottom: '24px' }}>
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '48px' }}>
            <p style={{ color: '#9ca3af' }}>Loading prospects...</p>
          </div>
        ) : (
          /* Prospects Table */
          <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '2px solid #475569', overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead style={{ backgroundColor: '#334155', borderBottom: '2px solid #475569' }}>
                  <tr>
                    <th style={{ padding: '16px', textAlign: 'left', width: '40px', borderRight: '1px solid #475569' }}>
                      <input
                        type="checkbox"
                        checked={selectedProspects.size === filteredProspects.length && filteredProspects.length > 0}
                        onChange={toggleSelectAll}
                      />
                    </th>
                    <th style={{ padding: '16px', textAlign: 'left', fontSize: '14px', fontWeight: 'bold', color: 'white', textTransform: 'uppercase', borderRight: '1px solid #475569' }}>
                      Name
                    </th>
                    <th style={{ padding: '16px', textAlign: 'left', fontSize: '14px', fontWeight: 'bold', color: 'white', textTransform: 'uppercase', borderRight: '1px solid #475569' }}>
                      Company
                    </th>
                    <th style={{ padding: '16px', textAlign: 'left', fontSize: '14px', fontWeight: 'bold', color: 'white', textTransform: 'uppercase', width: '96px', borderRight: '1px solid #475569' }}>
                      Fit
                    </th>
                    <th style={{ padding: '16px', textAlign: 'left', fontSize: '14px', fontWeight: 'bold', color: 'white', textTransform: 'uppercase', width: '128px', borderRight: '1px solid #475569' }}>
                      Status
                    </th>
                    <th style={{ padding: '16px', textAlign: 'left', fontSize: '14px', fontWeight: 'bold', color: 'white', textTransform: 'uppercase', borderRight: '1px solid #475569' }}>
                      Tags
                    </th>
                    <th style={{ padding: '16px', textAlign: 'left', fontSize: '14px', fontWeight: 'bold', color: 'white', textTransform: 'uppercase', width: '160px' }}>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProspects.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ padding: '48px', textAlign: 'center', color: '#9ca3af' }}>
                        {prospects.length === 0 ? (
                          <>
                            No prospects yet.{' '}
                            <Link href="/prospect-discovery" style={{ color: '#3b82f6' }}>
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
                          style={{ borderBottom: '1px solid #475569', backgroundColor: expandedRow === prospect.id ? '#334155' : 'transparent' }}
                        >
                          <td style={{ padding: '16px', borderRight: '1px solid #374151' }}>
                            <input
                              type="checkbox"
                              checked={selectedProspects.has(prospect.id)}
                              onChange={() => toggleSelect(prospect.id)}
                            />
                          </td>
                          <td style={{ padding: '16px', borderRight: '1px solid #374151' }}>
                            <button
                              onClick={() => setExpandedRow(expandedRow === prospect.id ? null : prospect.id)}
                              style={{ textAlign: 'left', width: '100%', background: 'none', border: 'none', cursor: 'pointer' }}
                            >
                              <div style={{ fontWeight: 500, color: 'white' }}>
                                {prospect.name || 'N/A'}
                              </div>
                              {prospect.job_title && (
                                <div style={{ fontSize: '14px', color: '#9ca3af' }}>{prospect.job_title}</div>
                              )}
                            </button>
                          </td>
                          <td style={{ padding: '16px', fontSize: '14px', color: '#e2e8f0', borderRight: '1px solid #374151' }}>{prospect.company || '—'}</td>
                          <td style={{ padding: '16px', borderRight: '1px solid #374151' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <div style={{ width: '48px', height: '8px', backgroundColor: '#475569', borderRadius: '4px', overflow: 'hidden' }}>
                                <div
                                  style={{ 
                                    height: '100%', 
                                    // Handle both 0-1 and 0-100 scales
                                    width: `${(prospect.fit_score || 0) > 1 ? prospect.fit_score : (prospect.fit_score || 0) * 100}%`,
                                    backgroundColor: ((prospect.fit_score || 0) > 1 ? prospect.fit_score : (prospect.fit_score || 0) * 100) >= 80 ? '#22c55e' : ((prospect.fit_score || 0) > 1 ? prospect.fit_score : (prospect.fit_score || 0) * 100) >= 60 ? '#eab308' : '#ef4444'
                                  }}
                                />
                              </div>
                              <span style={{ fontSize: '14px', fontWeight: 500, color: 'white' }}>{formatFitScore(prospect.fit_score)}</span>
                            </div>
                          </td>
                          <td style={{ padding: '16px', borderRight: '1px solid #374151' }}>
                            {editingStatus === prospect.id ? (
                              <select
                                autoFocus
                                value={prospect.status}
                                onChange={(e) => updateProspectStatus(prospect.id, e.target.value)}
                                onBlur={() => setEditingStatus(null)}
                                style={{ fontSize: '12px', borderRadius: '4px', padding: '4px 8px', backgroundColor: '#334155', color: 'white', border: '1px solid #475569' }}
                              >
                                {STATUS_OPTIONS.map(s => (
                                  <option key={s.value} value={s.value}>{s.label}</option>
                                ))}
                              </select>
                            ) : (
                              <button
                                onClick={() => setEditingStatus(prospect.id)}
                                style={{ 
                                  display: 'inline-flex', 
                                  padding: '4px 8px', 
                                  fontSize: '12px', 
                                  fontWeight: 500, 
                                  borderRadius: '9999px',
                                  border: 'none',
                                  cursor: 'pointer',
                                  backgroundColor: prospect.status === 'new' ? '#1e40af' : prospect.status === 'contacted' ? '#166534' : prospect.status === 'follow_up_needed' ? '#9a3412' : '#6b21a8',
                                  color: 'white'
                                }}
                              >
                                {prospect.status?.replace('_', ' ') || 'new'}
                              </button>
                            )}
                          </td>
                          <td style={{ padding: '16px', borderRight: '1px solid #374151' }}>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                              {prospect.tags?.slice(0, 2).map((tag, idx) => (
                                <span
                                  key={idx}
                                  style={{ display: 'inline-flex', padding: '2px 8px', fontSize: '12px', fontWeight: 500, backgroundColor: '#2563eb', color: 'white', borderRadius: '4px' }}
                                >
                                  {tag}
                                </span>
                              ))}
                              {prospect.tags && prospect.tags.length > 2 && (
                                <span style={{ fontSize: '12px', color: '#9ca3af' }}>+{prospect.tags.length - 2}</span>
                              )}
                            </div>
                          </td>
                          <td style={{ padding: '16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <Link
                                href={`/outreach/${prospect.id}`}
                                style={{ color: '#3b82f6', fontSize: '14px', fontWeight: 500, textDecoration: 'none' }}
                              >
                                DM
                              </Link>
                              {prospect.email && (
                                <a
                                  href={`mailto:${prospect.email}`}
                                  style={{ color: '#9ca3af', fontSize: '14px', textDecoration: 'none' }}
                                >
                                  Email
                                </a>
                              )}
                              {prospect.source_url && (
                                <a
                                  href={prospect.source_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{ color: '#6b7280', fontSize: '14px', textDecoration: 'none' }}
                                >
                                  Source
                                </a>
                              )}
                            </div>
                          </td>
                        </tr>
                        {/* Expanded Row */}
                        {expandedRow === prospect.id && (
                          <tr key={`${prospect.id}-expanded`} style={{ backgroundColor: '#334155' }}>
                            <td colSpan={7} style={{ padding: '16px' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '14px' }}>
                                <div>
                                  <h4 style={{ fontWeight: 500, color: 'white', marginBottom: '8px' }}>Contact Info</h4>
                                  <div style={{ color: '#9ca3af' }}>
                                    {prospect.email && <div>📧 {prospect.email}</div>}
                                    {prospect.source_url && (
                                      <div>
                                        🔗{' '}
                                        <a href={prospect.source_url} target="_blank" style={{ color: '#3b82f6' }}>
                                          {prospect.source_url.slice(0, 50)}...
                                        </a>
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <div>
                                  {prospect.summary && (
                                    <>
                                      <h4 style={{ fontWeight: 500, color: 'white', marginBottom: '8px' }}>Summary</h4>
                                      <p style={{ color: '#9ca3af' }}>{prospect.summary}</p>
                                    </>
                                  )}
                                  {prospect.pain_points && prospect.pain_points.length > 0 && (
                                    <>
                                      <h4 style={{ fontWeight: 500, color: 'white', marginTop: '12px', marginBottom: '8px' }}>Pain Points</h4>
                                      <ul style={{ listStyle: 'disc', paddingLeft: '20px', color: '#9ca3af' }}>
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
