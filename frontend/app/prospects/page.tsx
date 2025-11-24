'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { prospectAPI, outreachAPI, type Prospect } from '@/lib/api';
import Link from 'next/link';

export default function ProspectsPage() {
  const [user_id] = useState('demo-user-123'); // TODO: Get from auth/session
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'priority' | 'fit' | 'name'>('priority');
  const [searchQuery, setSearchQuery] = useState('');

  const queryClient = useQueryClient();

  // Fetch prospects (assuming we have a list endpoint)
  const { data: prospectsData, isLoading } = useQuery({
    queryKey: ['prospects', user_id, filterStatus],
    queryFn: () => prospectAPI.list(user_id, filterStatus === 'all' ? undefined : filterStatus),
    enabled: !!user_id,
  });

  const prospects = prospectsData?.prospects || [];

  // Approve/Reject mutation
  const approveMutation = useMutation({
    mutationFn: ({ prospect_ids, status }: { prospect_ids: string[]; status: 'approved' | 'rejected' }) =>
      prospectAPI.approve(user_id, prospect_ids, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
    },
  });

  // Score mutation
  const scoreMutation = useMutation({
    mutationFn: (prospect_ids: string[]) => prospectAPI.score(user_id, prospect_ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
    },
  });

  // Segment mutation
  const segmentMutation = useMutation({
    mutationFn: (prospect_ids?: string[]) => outreachAPI.segment(user_id, prospect_ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
    },
  });

  // Filter and sort prospects
  const filteredProspects = prospects
    .filter((p: Prospect) => {
      if (filterStatus !== 'all' && p.approval_status !== filterStatus) return false;
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          p.name?.toLowerCase().includes(query) ||
          p.company?.toLowerCase().includes(query) ||
          p.job_title?.toLowerCase().includes(query)
        );
      }
      return true;
    })
    .sort((a: Prospect, b: Prospect) => {
      switch (sortBy) {
        case 'priority':
          return (b.priority_score || 0) - (a.priority_score || 0);
        case 'fit':
          return (b.fit_score || 0) - (a.fit_score || 0);
        case 'name':
          return (a.name || '').localeCompare(b.name || '');
        default:
          return 0;
      }
    });

  const handleApprove = (prospect_ids: string[], status: 'approved' | 'rejected') => {
    if (confirm(`Are you sure you want to ${status} ${prospect_ids.length} prospect(s)?`)) {
      approveMutation.mutate({ prospect_ids, status });
    }
  };

  const handleScore = (prospect_ids: string[]) => {
    scoreMutation.mutate(prospect_ids);
  };

  const handleSegment = () => {
    segmentMutation.mutate(undefined);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Prospect Dashboard</h1>
            <p className="mt-1 text-sm text-gray-500">
              Manage and prioritize your prospects
            </p>
          </div>
          <div className="flex space-x-3">
            <button
              onClick={handleSegment}
              disabled={segmentMutation.isPending}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {segmentMutation.isPending ? 'Segmenting...' : 'Segment All Prospects'}
            </button>
            <Link
              href="/prospects/discover"
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
            >
              Discover New Prospects
            </Link>
          </div>
        </div>

        {/* Filters and Search */}
        <div className="mb-6 rounded-lg bg-white p-4 shadow">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-1 items-center gap-4">
              <input
                type="text"
                placeholder="Search prospects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-center gap-4">
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="priority">Sort by Priority</option>
                <option value="fit">Sort by Fit Score</option>
                <option value="name">Sort by Name</option>
              </select>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">Total Prospects</div>
            <div className="text-2xl font-bold text-gray-900">{prospects.length}</div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">Approved</div>
            <div className="text-2xl font-bold text-green-600">
              {prospects.filter((p: Prospect) => p.approval_status === 'approved').length}
            </div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">Pending</div>
            <div className="text-2xl font-bold text-yellow-600">
              {prospects.filter((p: Prospect) => p.approval_status === 'pending').length}
            </div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">High Priority</div>
            <div className="text-2xl font-bold text-blue-600">
              {prospects.filter((p: Prospect) => (p.priority_score || 0) >= 80).length}
            </div>
          </div>
        </div>

        {/* Prospect Table */}
        <div className="rounded-lg bg-white shadow">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading prospects...</div>
          ) : filteredProspects.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No prospects found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      <input type="checkbox" className="rounded border-gray-300" />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Name / Company
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Job Title
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Scores
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Segment
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {filteredProspects.map((prospect: Prospect) => (
                    <tr key={prospect.prospect_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <input type="checkbox" className="rounded border-gray-300" />
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">{prospect.name}</div>
                        <div className="text-sm text-gray-500">{prospect.company}</div>
                        {prospect.linkedin && (
                          <a
                            href={prospect.linkedin}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline"
                          >
                            LinkedIn →
                          </a>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">{prospect.job_title}</td>
                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          <div className="text-xs">
                            <span className="font-medium">Fit:</span>{' '}
                            <span className={prospect.fit_score && prospect.fit_score >= 70 ? 'text-green-600' : 'text-gray-600'}>
                              {prospect.fit_score || 'N/A'}
                            </span>
                          </div>
                          <div className="text-xs">
                            <span className="font-medium">Referral:</span>{' '}
                            <span className={prospect.referral_capacity && prospect.referral_capacity >= 70 ? 'text-green-600' : 'text-gray-600'}>
                              {prospect.referral_capacity || 'N/A'}
                            </span>
                          </div>
                          <div className="text-xs">
                            <span className="font-medium">Signal:</span>{' '}
                            <span className={prospect.signal_strength && prospect.signal_strength >= 70 ? 'text-green-600' : 'text-gray-600'}>
                              {prospect.signal_strength || 'N/A'}
                            </span>
                          </div>
                          {prospect.priority_score && (
                            <div className="text-xs font-bold text-blue-600">
                              Priority: {prospect.priority_score.toFixed(1)}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                            prospect.approval_status === 'approved'
                              ? 'bg-green-100 text-green-800'
                              : prospect.approval_status === 'rejected'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                        >
                          {prospect.approval_status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {prospect.segment ? (
                          <span className="rounded bg-purple-100 px-2 py-1 text-xs text-purple-800">
                            {prospect.segment.replace('_', ' ')}
                          </span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex space-x-2">
                          {prospect.approval_status === 'pending' && (
                            <>
                              <button
                                onClick={() => handleApprove([prospect.prospect_id], 'approved')}
                                className="text-green-600 hover:text-green-900"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleApprove([prospect.prospect_id], 'rejected')}
                                className="text-red-600 hover:text-red-900"
                              >
                                Reject
                              </button>
                            </>
                          )}
                          {!prospect.fit_score && (
                            <button
                              onClick={() => handleScore([prospect.prospect_id])}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              Score
                            </button>
                          )}
                          <Link
                            href={`/outreach/${prospect.prospect_id}`}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            Outreach →
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Bulk Actions */}
        {filteredProspects.length > 0 && (
          <div className="mt-4 flex items-center justify-between rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-600">
              {filteredProspects.length} prospect(s) displayed
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => handleScore(prospects.map((p: Prospect) => p.prospect_id))}
                disabled={scoreMutation.isPending}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {scoreMutation.isPending ? 'Scoring...' : 'Score All'}
              </button>
              <button
                onClick={() => handleApprove(prospects.filter((p: Prospect) => p.approval_status === 'pending').map((p: Prospect) => p.prospect_id), 'approved')}
                disabled={approveMutation.isPending}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                Approve All Pending
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

