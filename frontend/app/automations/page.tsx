'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Automation = {
  id: string;
  name: string;
  description: string;
  type: 'scheduled' | 'triggered' | 'manual';
  status: 'active' | 'paused' | 'error';
  lastRun?: string;
  nextRun?: string;
};

export default function AutomationsPage() {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    loadAutomations();
  }, []);

  const loadAutomations = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setAutomations([
        {
          id: '1',
          name: 'Daily Prospect Discovery',
          description: 'Automatically discover new prospects in target industries every day',
          type: 'scheduled',
          status: 'active',
          lastRun: '2 hours ago',
          nextRun: 'In 22 hours',
        },
        {
          id: '2',
          name: 'Follow-up Reminders',
          description: 'Send reminders for pending follow-ups with prospects',
          type: 'triggered',
          status: 'active',
          lastRun: '30 minutes ago',
        },
        {
          id: '3',
          name: 'Weekly Report Generation',
          description: 'Generate and email weekly activity reports',
          type: 'scheduled',
          status: 'paused',
          lastRun: '5 days ago',
          nextRun: 'Paused',
        },
        {
          id: '4',
          name: 'Content Publishing',
          description: 'Automatically publish scheduled content to LinkedIn',
          type: 'triggered',
          status: 'active',
          lastRun: '1 hour ago',
        },
      ]);
    } catch (err) {
      console.error('Failed to load automations:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredAutomations = filter === 'all'
    ? automations
    : automations.filter(a => a.type === filter || a.status === filter);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800 border-green-200';
      case 'paused': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'error': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'scheduled': return '⏰';
      case 'triggered': return '⚡';
      case 'manual': return '👆';
      default: return '🤖';
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading automations...</p>
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
            Automations
          </h1>
          <p style={{ color: '#9ca3af' }}>Manage your automated workflows and scheduled tasks</p>
        </div>

        {/* Filters */}
        <div style={{ marginBottom: '24px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {['all', 'scheduled', 'triggered', 'active', 'paused'].map((f) => (
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

        {/* Automation List */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
          {filteredAutomations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
              <p>No automations found for this filter.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {filteredAutomations.map((automation) => (
                <div
                  key={automation.id}
                  className={`p-4 rounded-lg border ${getStatusColor(automation.status)}`}
                  style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', gap: '16px' }}
                >
                  <div style={{ display: 'flex', alignItems: 'start', gap: '16px', flex: 1 }}>
                    <div style={{ fontSize: '24px' }}>{getTypeIcon(automation.type)}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <h3 style={{ fontWeight: 600, fontSize: '16px' }}>{automation.name}</h3>
                        <span
                          className={`text-xs px-2 py-1 rounded ${getStatusColor(automation.status)}`}
                        >
                          {automation.status}
                        </span>
                      </div>
                      <p style={{ fontSize: '14px', opacity: 0.8, marginBottom: '8px' }}>
                        {automation.description}
                      </p>
                      <div style={{ display: 'flex', gap: '16px', fontSize: '12px', opacity: 0.6 }}>
                        {automation.lastRun && (
                          <span>Last run: {automation.lastRun}</span>
                        )}
                        {automation.nextRun && (
                          <span>Next run: {automation.nextRun}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      className="px-3 py-1 text-sm bg-gray-700 text-white rounded hover:bg-gray-600 transition-colors"
                    >
                      {automation.status === 'active' ? 'Pause' : 'Resume'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Create New Automation Button */}
        <div style={{ marginTop: '24px', textAlign: 'center' }}>
          <button
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Create New Automation
          </button>
        </div>
      </div>
    </main>
  );
}
