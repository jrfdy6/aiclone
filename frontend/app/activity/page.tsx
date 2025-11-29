'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type ActivityItem = {
  id: string;
  type: 'prospect' | 'outreach' | 'research' | 'content' | 'system';
  title: string;
  description: string;
  timestamp: string;
  status?: 'success' | 'error' | 'pending';
};

export default function ActivityPage() {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    loadActivities();
  }, []);

  const loadActivities = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setActivities([
        {
          id: '1',
          type: 'prospect',
          title: 'New prospect discovered',
          description: 'Sarah Johnson from TechEd Solutions was added to your prospect list',
          timestamp: '2 minutes ago',
          status: 'success',
        },
        {
          id: '2',
          type: 'outreach',
          title: 'Email sent',
          description: 'Outreach email sent to Emily Rodriguez at Future Schools Inc',
          timestamp: '15 minutes ago',
          status: 'success',
        },
        {
          id: '3',
          type: 'research',
          title: 'Research task completed',
          description: 'Completed research on AI adoption in K-12 education',
          timestamp: '1 hour ago',
          status: 'success',
        },
        {
          id: '4',
          type: 'content',
          title: 'Content generated',
          description: 'LinkedIn post generated: "5 Ways AI is Transforming Education"',
          timestamp: '2 hours ago',
          status: 'success',
        },
        {
          id: '5',
          type: 'system',
          title: 'System update',
          description: 'Prospect discovery service updated with new search algorithms',
          timestamp: '3 hours ago',
          status: 'success',
        },
      ]);
    } catch (err) {
      console.error('Failed to load activities:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredActivities = filter === 'all' 
    ? activities 
    : activities.filter(a => a.type === filter);

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'prospect': return '🎯';
      case 'outreach': return '📧';
      case 'research': return '🔍';
      case 'content': return '✍️';
      case 'system': return '⚙️';
      default: return '📋';
    }
  };

  const getActivityColor = (type: string) => {
    switch (type) {
      case 'prospect': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'outreach': return 'bg-green-100 text-green-800 border-green-200';
      case 'research': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'content': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'system': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading activity...</p>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Activity Log
          </h1>
          <p style={{ color: '#9ca3af' }}>Track all system activities and events</p>
        </div>

        {/* Filters */}
        <div style={{ marginBottom: '24px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {['all', 'prospect', 'outreach', 'research', 'content', 'system'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg transition-colors ${
                filter === f
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
              style={{ textTransform: 'capitalize' }}
            >
              {f === 'all' ? 'All' : f}
            </button>
          ))}
        </div>

        {/* Activity List */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
          {filteredActivities.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
              <p>No activities found for this filter.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {filteredActivities.map((activity) => (
                <div
                  key={activity.id}
                  className={`p-4 rounded-lg border ${getActivityColor(activity.type)}`}
                  style={{ display: 'flex', alignItems: 'start', gap: '16px' }}
                >
                  <div style={{ fontSize: '24px' }}>{getActivityIcon(activity.type)}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <h3 style={{ fontWeight: 600, fontSize: '16px' }}>{activity.title}</h3>
                      {activity.status && (
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            activity.status === 'success'
                              ? 'bg-green-100 text-green-800'
                              : activity.status === 'error'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                        >
                          {activity.status}
                        </span>
                      )}
                    </div>
                    <p style={{ fontSize: '14px', opacity: 0.8, marginBottom: '4px' }}>
                      {activity.description}
                    </p>
                    <p style={{ fontSize: '12px', opacity: 0.6 }}>{activity.timestamp}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
