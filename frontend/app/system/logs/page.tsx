'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type LogEntry = {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  source?: string;
  metadata?: Record<string, any>;
};

export default function SystemLogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    loadLogs();
    
    if (autoRefresh) {
      const interval = setInterval(loadLogs, 5000); // Refresh every 5 seconds
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const loadLogs = async () => {
    try {
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setLogs([
        {
          id: '1',
          timestamp: new Date().toISOString(),
          level: 'info',
          message: 'System initialized successfully',
          source: 'backend',
        },
        {
          id: '2',
          timestamp: new Date(Date.now() - 60000).toISOString(),
          level: 'info',
          message: 'Firebase/Firestore client initialized successfully',
          source: 'backend',
        },
        {
          id: '3',
          timestamp: new Date(Date.now() - 120000).toISOString(),
          level: 'warning',
          message: 'Rate limit approaching for Google Custom Search API',
          source: 'search_client',
        },
      ]);
    } catch (err) {
      console.error('Failed to load logs:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = filter === 'all'
    ? logs
    : logs.filter(log => log.level === filter);

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'text-red-400 bg-red-900/20 border-red-500/50';
      case 'warning':
        return 'text-yellow-400 bg-yellow-900/20 border-yellow-500/50';
      case 'info':
        return 'text-blue-400 bg-blue-900/20 border-blue-500/50';
      case 'debug':
        return 'text-gray-400 bg-gray-900/20 border-gray-500/50';
      default:
        return 'text-gray-400 bg-gray-900/20 border-gray-500/50';
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading system logs...</p>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        {/* Header */}
        <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
              System Logs
            </h1>
            <p style={{ color: '#9ca3af' }}>Monitor system activity and errors</p>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#9ca3af', fontSize: '14px' }}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                style={{ width: '16px', height: '16px' }}
              />
              Auto-refresh
            </label>
            <button
              onClick={loadLogs}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Filters */}
        <div style={{ marginBottom: '24px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {['all', 'info', 'warning', 'error', 'debug'].map((f) => (
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

        {/* Logs List */}
        <div
          style={{
            backgroundColor: '#1e293b',
            borderRadius: '12px',
            border: '1px solid #475569',
            padding: '24px',
            maxHeight: '70vh',
            overflowY: 'auto',
          }}
        >
          {filteredLogs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
              <p>No logs found for this filter.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {filteredLogs.map((log) => (
                <div
                  key={log.id}
                  className={`p-4 rounded-lg border ${getLevelColor(log.level)}`}
                  style={{
                    fontFamily: 'monospace',
                    fontSize: '13px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', gap: '16px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                          }}
                        >
                          {log.level}
                        </span>
                        <span style={{ color: '#9ca3af', fontSize: '12px' }}>
                          {new Date(log.timestamp).toLocaleString()}
                        </span>
                        {log.source && (
                          <span style={{ color: '#64748b', fontSize: '12px' }}>
                            [{log.source}]
                          </span>
                        )}
                      </div>
                      <p style={{ color: '#e2e8f0', margin: 0 }}>
                        {log.message}
                      </p>
                      {log.metadata && Object.keys(log.metadata).length > 0 && (
                        <details style={{ marginTop: '8px' }}>
                          <summary style={{ color: '#9ca3af', cursor: 'pointer', fontSize: '12px' }}>
                            View metadata
                          </summary>
                          <pre
                            style={{
                              marginTop: '8px',
                              padding: '8px',
                              backgroundColor: '#0f172a',
                              borderRadius: '4px',
                              fontSize: '11px',
                              color: '#cbd5e1',
                              overflow: 'auto',
                            }}
                          >
                            {JSON.stringify(log.metadata, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
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
