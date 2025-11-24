'use client';

import { useState, useEffect } from 'react';
import { getApiUrl } from '@/lib/api-client';
import Link from 'next/link';

type ActivityEvent = {
  id: string;
  type: 'prospect' | 'outreach' | 'research' | 'insight' | 'content' | 'error' | 'automation';
  title: string;
  description: string;
  timestamp: string;
  status?: 'success' | 'failed' | 'pending';
  metadata?: Record<string, any>;
  link?: string;
};

export default function ActivityPage() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFilter, setSelectedFilter] = useState<string>('all');
  const [selectedEvent, setSelectedEvent] = useState<ActivityEvent | null>(null);

  useEffect(() => {
    loadActivity();
    // Poll for new activity every 10 seconds
    const interval = setInterval(loadActivity, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadActivity = async () => {
    const apiUrl = getApiUrl();
    if (!apiUrl) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      // Mock data - will be replaced with API call
      const mockEvents: ActivityEvent[] = [
        {
          id: '1',
          type: 'prospect',
          title: 'Prospect Analysis Complete',
          description: 'Sarah Johnson (TechEd Solutions) analyzed successfully',
          timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
          status: 'success',
          metadata: { prospect_id: '1', fit_score: 0.92 },
          link: '/prospects?id=1',
        },
        {
          id: '2',
          type: 'research',
          title: 'Research Report Generated',
          description: 'AI in K-12 Education Trends research completed',
          timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
          status: 'success',
          metadata: { task_id: '1', insights_count: 12 },
          link: '/research-tasks',
        },
        {
          id: '3',
          type: 'outreach',
          title: 'Follow-up Sent Automatically',
          description: 'DM sent to Emily Rodriguez via automation',
          timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
          status: 'success',
          metadata: { prospect_id: '3', message_type: 'dm' },
          link: '/outreach/3',
        },
        {
          id: '4',
          type: 'prospect',
          title: 'High-Fit Prospect Detected',
          description: 'Michael Chen (InnovateEd) - 87% fit score',
          timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
          status: 'success',
          metadata: { prospect_id: '2', fit_score: 0.87 },
          link: '/prospects?id=2',
        },
        {
          id: '5',
          type: 'content',
          title: 'Content Generated',
          description: 'LinkedIn post created: "5 Ways AI is Transforming Education"',
          timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          status: 'success',
          metadata: { content_type: 'linkedin_post', draft_id: '1' },
          link: '/content-marketing',
        },
        {
          id: '6',
          type: 'automation',
          title: 'Automation Executed',
          description: 'Weekly research task completed automatically',
          timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
          status: 'success',
          metadata: { automation_id: '1', trigger: 'scheduled' },
          link: '/automations',
        },
        {
          id: '7',
          type: 'error',
          title: 'API Error Occurred',
          description: 'Failed to fetch prospect data for prospect ID 5',
          timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
          status: 'failed',
          metadata: { error_code: 'API_ERROR', prospect_id: '5' },
          link: '/system/logs',
        },
      ];
      setEvents(mockEvents.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()));
    } catch (error) {
      console.error('Failed to load activity:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredEvents = selectedFilter === 'all' 
    ? events 
    : events.filter(e => e.type === selectedFilter);

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'prospect':
        return '👤';
      case 'outreach':
        return '📧';
      case 'research':
        return '🔍';
      case 'insight':
        return '💡';
      case 'content':
        return '📝';
      case 'error':
        return '❌';
      case 'automation':
        return '🤖';
      default:
        return '⚡';
    }
  };

  const getEventColor = (type: string) => {
    switch (type) {
      case 'prospect':
        return 'bg-blue-100 text-blue-800';
      case 'outreach':
        return 'bg-green-100 text-green-800';
      case 'research':
        return 'bg-purple-100 text-purple-800';
      case 'insight':
        return 'bg-yellow-100 text-yellow-800';
      case 'content':
        return 'bg-pink-100 text-pink-800';
      case 'error':
        return 'bg-red-100 text-red-800';
      case 'automation':
        return 'bg-indigo-100 text-indigo-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const filters = [
    { id: 'all', label: 'All Activity', icon: '⚡' },
    { id: 'prospect', label: 'Prospects', icon: '👤' },
    { id: 'outreach', label: 'Outreach', icon: '📧' },
    { id: 'research', label: 'Research', icon: '🔍' },
    { id: 'insight', label: 'Insights', icon: '💡' },
    { id: 'content', label: 'Content', icon: '📝' },
    { id: 'automation', label: 'Automations', icon: '🤖' },
    { id: 'error', label: 'Errors', icon: '❌' },
  ];

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Activity Timeline</h1>
          <p className="text-gray-600 mt-1">Real-time feed of all system activity</p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex flex-wrap gap-2">
            {filters.map((filter) => (
              <button
                key={filter.id}
                onClick={() => setSelectedFilter(filter.id)}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  selectedFilter === filter.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <span className="mr-2">{filter.icon}</span>
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        {/* Timeline */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          {loading ? (
            <div className="text-center py-12 text-gray-500">Loading activity...</div>
          ) : filteredEvents.length === 0 ? (
            <div className="text-center py-12 text-gray-500">No activity found</div>
          ) : (
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gray-200"></div>

              {/* Events */}
              <div className="space-y-6">
                {filteredEvents.map((event, index) => (
                  <div
                    key={event.id}
                    className="relative flex items-start space-x-4 cursor-pointer hover:bg-gray-50 p-3 rounded-lg transition-colors"
                    onClick={() => setSelectedEvent(event)}
                  >
                    {/* Icon */}
                    <div className={`relative z-10 flex-shrink-0 w-16 h-16 rounded-full ${getEventColor(event.type)} flex items-center justify-center text-2xl`}>
                      {getEventIcon(event.type)}
                      {event.status === 'failed' && (
                        <div className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full"></div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold text-gray-900">{event.title}</h3>
                        <span className="text-sm text-gray-500">{formatTimestamp(event.timestamp)}</span>
                      </div>
                      <p className="text-gray-600 mt-1">{event.description}</p>
                      {event.link && (
                        <Link
                          href={event.link}
                          className="text-sm text-blue-600 hover:underline mt-2 inline-block"
                          onClick={(e) => e.stopPropagation()}
                        >
                          View details →
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Event Detail Modal */}
        {selectedEvent && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => setSelectedEvent(null)}
          >
            <div
              className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <span className="text-4xl">{getEventIcon(selectedEvent.type)}</span>
                  <div>
                    <h2 className="text-2xl font-bold">{selectedEvent.title}</h2>
                    <p className="text-sm text-gray-500">{formatTimestamp(selectedEvent.timestamp)}</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">Description</h3>
                  <p className="text-gray-700">{selectedEvent.description}</p>
                </div>

                {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-2">Metadata</h3>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                        {JSON.stringify(selectedEvent.metadata, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {selectedEvent.status && (
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-1">Status</h3>
                    <span
                      className={`px-3 py-1 rounded-full text-sm font-medium ${
                        selectedEvent.status === 'success'
                          ? 'bg-green-100 text-green-800'
                          : selectedEvent.status === 'failed'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}
                    >
                      {selectedEvent.status}
                    </span>
                  </div>
                )}
              </div>

              {selectedEvent.link && (
                <div className="mt-6 pt-6 border-t">
                  <Link
                    href={selectedEvent.link}
                    className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    View Full Details →
                  </Link>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

