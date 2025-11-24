'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

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
};

type ProspectStatus = 'all' | 'new' | 'analyzed' | 'contacted' | 'follow_up_needed';

export default function ProspectsPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ProspectStatus>('all');
  const [sortBy, setSortBy] = useState<'fit_score' | 'company' | 'last_action'>('fit_score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedProspects, setSelectedProspects] = useState<Set<string>>(new Set());
  const [hoveredProspect, setHoveredProspect] = useState<string | null>(null);

  useEffect(() => {
    loadProspects();
  }, [statusFilter, sortBy, sortOrder]);

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
        sort_by: sortBy === 'fit_score' ? 'fit_score' : sortBy === 'company' ? 'company' : 'updated_at',
        sort_order: sortOrder,
      });
      
      if (statusFilter !== 'all') {
        params.append('status', statusFilter);
      }

      const response = await fetch(`${API_URL}/api/prospects/?${params.toString()}`);
      
      if (!response.ok) {
        // If no prospects found or error, fall back to empty array
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
          status: p.status,
          tags: p.tags || [],
          last_action: p.last_action,
          summary: p.summary || (p.analysis?.summary),
          pain_points: p.pain_points || [],
        })));
        setError(null);
      } else {
        // Fallback to mock data if structure is unexpected
        const mockProspects: Prospect[] = [
        {
          id: '1',
          name: 'Sarah Johnson',
          company: 'TechEd Solutions',
          job_title: 'VP of Education',
          email: 'sarah@teched.com',
          fit_score: 0.92,
          status: 'new',
          tags: ['Founder', 'AI', 'High Priority'],
          last_action: 'Discovered 2 days ago',
          summary: 'Educational technology leader interested in AI tools for K-12',
          pain_points: ['Manual processes', 'Teacher workload'],
        },
        {
          id: '2',
          name: 'Michael Chen',
          company: 'InnovateEd',
          job_title: 'Director of Innovation',
          email: 'mchen@innovateed.com',
          fit_score: 0.87,
          status: 'analyzed',
          tags: ['AI', 'Inbound'],
          last_action: 'Analyzed yesterday',
          summary: 'Actively looking for automation solutions',
        },
        {
          id: '3',
          name: 'Emily Rodriguez',
          company: 'Future Schools Inc',
          job_title: 'CEO',
          email: 'emily@futureschools.com',
          fit_score: 0.95,
          status: 'contacted',
          tags: ['Founder', 'High Priority', 'Early Adopter'],
          last_action: 'DM Sent (2 days ago)',
          summary: 'Stealth founder building AI-powered education platform',
        },
        {
          id: '4',
          name: 'David Park',
          company: 'EduTech Ventures',
          job_title: 'CTO',
          email: 'david@edutech.com',
          fit_score: 0.78,
          status: 'follow_up_needed',
          tags: ['AI'],
          last_action: 'Initial contact (5 days ago)',
          summary: 'Technical leader evaluating AI tools',
        },
      ];

        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 500));
        setProspects(mockProspects);
        setError(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load prospects');
    } finally {
      setLoading(false);
    }
  };

  const filteredProspects = prospects
    .filter(p => statusFilter === 'all' || p.status === statusFilter)
    .sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case 'fit_score':
          comparison = (a.fit_score || 0) - (b.fit_score || 0);
          break;
        case 'company':
          comparison = (a.company || '').localeCompare(b.company || '');
          break;
        case 'last_action':
          comparison = (a.last_action || '').localeCompare(b.last_action || '');
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

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
    switch (status) {
      case 'new':
        return 'bg-blue-100 text-blue-800';
      case 'analyzed':
        return 'bg-purple-100 text-purple-800';
      case 'contacted':
        return 'bg-green-100 text-green-800';
      case 'follow_up_needed':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatFitScore = (score?: number) => {
    if (!score) return 'N/A';
    return `${Math.round(score * 100)}%`;
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Prospects</h1>
            <p className="text-gray-600 mt-1">Manage and track your outreach pipeline</p>
          </div>
          <Link
            href="/prospecting"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Add Prospects
          </Link>
        </div>

        {/* Filters and Actions */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* Status Filter */}
            <div>
              <label className="text-sm font-medium text-gray-700 mr-2">Filter by Status:</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ProspectStatus)}
                className="rounded border border-gray-300 px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Prospects</option>
                <option value="new">New</option>
                <option value="analyzed">Analyzed</option>
                <option value="contacted">Contacted</option>
                <option value="follow_up_needed">Follow-up Needed</option>
              </select>
            </div>

            {/* Sort */}
            <div>
              <label className="text-sm font-medium text-gray-700 mr-2">Sort by:</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="rounded border border-gray-300 px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="fit_score">Fit Score</option>
                <option value="company">Company</option>
                <option value="last_action">Last Action</option>
              </select>
            </div>

            <div>
              <button
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                {sortOrder === 'asc' ? '↑ Ascending' : '↓ Descending'}
              </button>
            </div>

            {/* Bulk Actions */}
            {selectedProspects.size > 0 && (
              <div className="ml-auto">
                <button
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm transition-colors"
                  onClick={() => {
                    // TODO: Implement bulk DM generation
                    alert(`Generate DMs for ${selectedProspects.size} prospects`);
                  }}
                >
                  Generate DMs ({selectedProspects.size})
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
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
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left">
                      <input
                        type="checkbox"
                        checked={selectedProspects.size === filteredProspects.length && filteredProspects.length > 0}
                        onChange={toggleSelectAll}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Company
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Fit Score
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tags
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Last Action
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {filteredProspects.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                        No prospects found. <Link href="/prospecting" className="text-blue-600 hover:underline">Add some prospects</Link> to get started.
                      </td>
                    </tr>
                  ) : (
                    filteredProspects.map((prospect) => (
                      <tr
                        key={prospect.id}
                        className="hover:bg-gray-50 transition-colors"
                        onMouseEnter={() => setHoveredProspect(prospect.id)}
                        onMouseLeave={() => setHoveredProspect(null)}
                      >
                        <td className="px-4 py-4">
                          <input
                            type="checkbox"
                            checked={selectedProspects.has(prospect.id)}
                            onChange={() => toggleSelect(prospect.id)}
                            className="rounded border-gray-300"
                          />
                        </td>
                        <td className="px-4 py-4">
                          <div className="font-medium text-gray-900">{prospect.name || 'N/A'}</div>
                          {prospect.job_title && (
                            <div className="text-sm text-gray-500">{prospect.job_title}</div>
                          )}
                          {hoveredProspect === prospect.id && prospect.summary && (
                            <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-gray-700">
                              <strong>Summary:</strong> {prospect.summary}
                              {prospect.pain_points && prospect.pain_points.length > 0 && (
                                <div className="mt-1">
                                  <strong>Pain Points:</strong> {prospect.pain_points.join(', ')}
                                </div>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-900">{prospect.company || 'N/A'}</td>
                        <td className="px-4 py-4">
                          <div className="flex items-center space-x-2">
                            <span className="text-sm font-medium">{formatFitScore(prospect.fit_score)}</span>
                            {prospect.fit_score && (
                              <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${
                                    (prospect.fit_score || 0) > 0.8
                                      ? 'bg-green-500'
                                      : (prospect.fit_score || 0) > 0.6
                                      ? 'bg-yellow-500'
                                      : 'bg-red-500'
                                  }`}
                                  style={{ width: `${(prospect.fit_score || 0) * 100}%` }}
                                />
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <span
                            className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(
                              prospect.status
                            )}`}
                          >
                            {prospect.status?.replace('_', ' ') || 'Unknown'}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex flex-wrap gap-1">
                            {prospect.tags?.slice(0, 3).map((tag, idx) => (
                              <span
                                key={idx}
                                className="inline-flex px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800 rounded"
                              >
                                {tag}
                              </span>
                            ))}
                            {prospect.tags && prospect.tags.length > 3 && (
                              <span className="text-xs text-gray-500">+{prospect.tags.length - 3}</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-500">{prospect.last_action || 'N/A'}</td>
                        <td className="px-4 py-4">
                          <div className="flex space-x-2">
                            <Link
                              href={`/outreach/${prospect.id}`}
                              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                            >
                              Generate DM
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Stats Summary */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-gray-900">{prospects.length}</div>
            <div className="text-sm text-gray-600">Total Prospects</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-blue-600">
              {prospects.filter(p => p.status === 'new').length}
            </div>
            <div className="text-sm text-gray-600">New</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-green-600">
              {prospects.filter(p => p.status === 'contacted').length}
            </div>
            <div className="text-sm text-gray-600">Contacted</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-2xl font-bold text-orange-600">
              {prospects.filter(p => p.status === 'follow_up_needed').length}
            </div>
            <div className="text-sm text-gray-600">Follow-up Needed</div>
          </div>
        </div>
      </div>
    </main>
  );
}

