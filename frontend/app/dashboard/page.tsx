'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { prospectAPI, outreachAPI, metricsAPI } from '@/lib/api';
import Link from 'next/link';

export default function DashboardPage() {
  const [user_id] = useState('demo-user-123'); // TODO: Get from auth

  // Quick stats queries
  const { data: prospectsData } = useQuery({
    queryKey: ['prospects', user_id],
    queryFn: () => prospectAPI.list(user_id),
    enabled: !!user_id,
  });

  const { data: outreachMetrics } = useQuery({
    queryKey: ['outreach-metrics', user_id],
    queryFn: () => outreachAPI.metrics(user_id, 7),
    enabled: !!user_id,
  });

  const { data: weeklyReport } = useQuery({
    queryKey: ['weekly-report', user_id],
    queryFn: () => metricsAPI.weeklyReport(user_id),
    enabled: !!user_id,
  });

  const prospects = prospectsData?.prospects || [];
  const approvedCount = prospects.filter((p: any) => p.approval_status === 'approved').length;
  const pendingCount = prospects.filter((p: any) => p.approval_status === 'pending').length;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            Overview of your prospects, outreach, and campaigns
          </p>
        </div>

        {/* Quick Stats */}
        <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-4">
          <Link
            href="/prospects"
            className="rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-md"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-gray-500">Total Prospects</div>
                <div className="text-3xl font-bold text-gray-900">{prospects.length}</div>
                <div className="mt-1 text-xs text-gray-400">
                  {approvedCount} approved, {pendingCount} pending
                </div>
              </div>
              <div className="text-4xl">👥</div>
            </div>
          </Link>

          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-gray-500">Outreach Reply Rate</div>
                <div className="text-3xl font-bold text-green-600">
                  {outreachMetrics?.reply_rate?.toFixed(1) || '0.0'}%
                </div>
                <div className="mt-1 text-xs text-gray-400">Last 7 days</div>
              </div>
              <div className="text-4xl">📧</div>
            </div>
          </div>

          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-gray-500">Content Engagement</div>
                <div className="text-3xl font-bold text-blue-600">
                  {weeklyReport?.avg_engagement_rate?.toFixed(1) || '0.0'}%
                </div>
                <div className="mt-1 text-xs text-gray-400">
                  {weeklyReport?.total_posts || 0} posts this week
                </div>
              </div>
              <div className="text-4xl">📊</div>
            </div>
          </div>

          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-gray-500">Meetings Booked</div>
                <div className="text-3xl font-bold text-purple-600">
                  {outreachMetrics?.meetings_booked || weeklyReport?.outreach_summary?.meetings_booked || 0}
                </div>
                <div className="mt-1 text-xs text-gray-400">This week</div>
              </div>
              <div className="text-4xl">📅</div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mb-8">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">Quick Actions</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Link
              href="/prospects/discover"
              className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-6 text-center transition-colors hover:border-blue-500 hover:bg-blue-50"
            >
              <div className="text-3xl mb-2">🔍</div>
              <div className="font-medium text-gray-900">Discover Prospects</div>
              <div className="text-sm text-gray-500">Find new prospects to reach out to</div>
            </Link>

            <Link
              href="/scheduler"
              className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-6 text-center transition-colors hover:border-blue-500 hover:bg-blue-50"
            >
              <div className="text-3xl mb-2">📅</div>
              <div className="font-medium text-gray-900">View Weekly Cadence</div>
              <div className="text-sm text-gray-500">See your outreach schedule</div>
            </Link>

            <Link
              href="/campaigns"
              className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-6 text-center transition-colors hover:border-blue-500 hover:bg-blue-50"
            >
              <div className="text-3xl mb-2">📊</div>
              <div className="font-medium text-gray-900">View Campaign Insights</div>
              <div className="text-sm text-gray-500">Check performance metrics</div>
            </Link>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <h3 className="text-lg font-semibold text-gray-900">Top Prospects</h3>
            </div>
            <div className="divide-y divide-gray-200">
              {prospects
                .filter((p: any) => p.priority_score && p.priority_score >= 80)
                .slice(0, 5)
                .map((prospect: any) => (
                  <Link
                    key={prospect.prospect_id}
                    href={`/outreach/${prospect.prospect_id}`}
                    className="block px-6 py-4 transition-colors hover:bg-gray-50"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{prospect.name}</div>
                        <div className="text-sm text-gray-500">{prospect.company}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium text-blue-600">
                          Priority: {prospect.priority_score?.toFixed(1)}
                        </div>
                        <div className="text-xs text-gray-500">{prospect.segment || '—'}</div>
                      </div>
                    </div>
                  </Link>
                ))}
            </div>
          </div>

          <div className="rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <h3 className="text-lg font-semibold text-gray-900">Recommendations</h3>
            </div>
            <div className="p-6">
              {weeklyReport?.recommendations && weeklyReport.recommendations.length > 0 ? (
                <ul className="space-y-2">
                  {weeklyReport.recommendations.slice(0, 5).map((rec, i) => (
                    <li key={i} className="flex items-start text-sm text-gray-700">
                      <span className="mr-2">•</span>
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-gray-500">
                  Generate weekly report to see recommendations
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

