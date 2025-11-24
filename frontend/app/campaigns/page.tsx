'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { metricsAPI, outreachAPI, type WeeklyReport } from '@/lib/api';
import Link from 'next/link';

export default function CampaignsPage() {
  const [user_id] = useState('demo-user-123'); // TODO: Get from auth
  const [dateRangeDays, setDateRangeDays] = useState(30);

  // Fetch weekly report
  const { data: weeklyReport, isLoading: reportLoading } = useQuery({
    queryKey: ['weekly-report', user_id],
    queryFn: () => metricsAPI.weeklyReport(user_id),
    enabled: !!user_id,
  });

  // Fetch outreach metrics
  const { data: outreachMetrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['outreach-metrics', user_id, dateRangeDays],
    queryFn: () => outreachAPI.metrics(user_id, dateRangeDays),
    enabled: !!user_id,
  });

  if (reportLoading || metricsLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="mx-auto max-w-7xl">
          <div className="rounded-lg bg-white p-8 text-center shadow">
            <div className="text-gray-500">Loading campaign insights...</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Campaign Insights</h1>
            <p className="mt-1 text-sm text-gray-500">
              Content & outreach performance metrics
            </p>
          </div>
          <div className="flex space-x-3">
            <select
              value={dateRangeDays}
              onChange={(e) => setDateRangeDays(Number(e.target.value))}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <button
              onClick={() => window.location.reload()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Weekly Report Section */}
        {weeklyReport && (
          <div className="mb-6 rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <h2 className="text-xl font-semibold text-gray-900">Weekly Performance Report</h2>
              <p className="text-sm text-gray-500">
                {weeklyReport.week_start} - {weeklyReport.week_end}
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <div>
                  <div className="text-sm text-gray-500">Total Posts</div>
                  <div className="text-3xl font-bold text-gray-900">{weeklyReport.total_posts}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-500">Avg Engagement Rate</div>
                  <div className="text-3xl font-bold text-blue-600">
                    {weeklyReport.avg_engagement_rate.toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500">Best Performing Pillar</div>
                  <div className="text-2xl font-semibold text-purple-600">
                    {weeklyReport.best_pillar?.replace('_', ' ') || 'N/A'}
                  </div>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-medium text-gray-700">Top Hashtags</h3>
                  <div className="flex flex-wrap gap-2">
                    {weeklyReport.top_hashtags.map((tag, i) => (
                      <span
                        key={i}
                        className="rounded-full bg-blue-100 px-3 py-1 text-sm text-blue-800"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-medium text-gray-700">Top Audience Segments</h3>
                  <div className="flex flex-wrap gap-2">
                    {weeklyReport.top_audience_segments.map((segment, i) => (
                      <span
                        key={i}
                        className="rounded-full bg-purple-100 px-3 py-1 text-sm text-purple-800"
                      >
                        {segment}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {weeklyReport.outreach_summary && (
                <div className="mt-6 rounded-lg bg-gray-50 p-4">
                  <h3 className="mb-3 text-sm font-medium text-gray-700">Outreach Summary</h3>
                  <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                    <div>
                      <div className="text-xs text-gray-500">Connection Accept Rate</div>
                      <div className="text-lg font-semibold text-gray-900">
                        {weeklyReport.outreach_summary.connection_accept_rate.toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">DM Reply Rate</div>
                      <div className="text-lg font-semibold text-green-600">
                        {weeklyReport.outreach_summary.dm_reply_rate.toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Meetings Booked</div>
                      <div className="text-lg font-semibold text-blue-600">
                        {weeklyReport.outreach_summary.meetings_booked}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Total DMs Sent</div>
                      <div className="text-lg font-semibold text-gray-900">
                        {weeklyReport.outreach_summary.total_dms_sent}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {weeklyReport.recommendations && weeklyReport.recommendations.length > 0 && (
                <div className="mt-6 rounded-lg border-l-4 border-blue-500 bg-blue-50 p-4">
                  <h3 className="mb-2 text-sm font-semibold text-blue-900">Recommendations</h3>
                  <ul className="space-y-1">
                    {weeklyReport.recommendations.map((rec, i) => (
                      <li key={i} className="text-sm text-blue-800">
                        • {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Outreach Metrics Section */}
        {outreachMetrics && (
          <div className="rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <h2 className="text-xl font-semibold text-gray-900">Outreach Performance</h2>
              <p className="text-sm text-gray-500">Last {dateRangeDays} days</p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
                <div>
                  <div className="text-sm text-gray-500">Total Outreach</div>
                  <div className="text-3xl font-bold text-gray-900">{outreachMetrics.total_outreach}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-500">Reply Rate</div>
                  <div className="text-3xl font-bold text-green-600">
                    {outreachMetrics.reply_rate.toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500">Meeting Rate</div>
                  <div className="text-3xl font-bold text-blue-600">
                    {outreachMetrics.meeting_rate.toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500">Connection Requests</div>
                  <div className="text-3xl font-bold text-purple-600">
                    {outreachMetrics.connection_requests_sent || 0}
                  </div>
                </div>
              </div>

              {outreachMetrics.segment_performance && (
                <div className="mt-6">
                  <h3 className="mb-3 text-sm font-medium text-gray-700">Performance by Segment</h3>
                  <div className="space-y-3">
                    {Object.entries(outreachMetrics.segment_performance).map(([segment, perf]: [string, any]) => (
                      <div key={segment} className="rounded-lg bg-gray-50 p-4">
                        <div className="mb-2 flex items-center justify-between">
                          <span className="font-medium text-gray-900">
                            {segment.replace('_', ' ')}
                          </span>
                          <span className="text-sm text-gray-500">
                            {perf.total || 0} outreach attempts
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <div className="text-xs text-gray-500">Reply Rate</div>
                            <div className="text-lg font-semibold text-green-600">
                              {perf.reply_rate?.toFixed(1) || 0}%
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-gray-500">Meeting Rate</div>
                            <div className="text-lg font-semibold text-blue-600">
                              {perf.meeting_rate?.toFixed(1) || 0}%
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

