'use client';

import { useState, useEffect } from 'react';

type LogEntry = {
  id: string;
  level: 'error' | 'warning' | 'info' | 'success';
  message: string;
  timestamp: string;
  category: string;
  details?: string;
  link?: string;
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);

  useEffect(() => {
    loadLogs();
    const interval = setInterval(loadLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadLogs = async () => {
    // Mock data
    const mockLogs: LogEntry[] = [
      {
        id: '1',
        level: 'error',
        message: 'Failed to fetch prospect data for prospect ID 5',
        timestamp: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
        category: 'API',
        details: 'HTTP 404: Prospect not found',
        link: '/prospects?id=5',
      },
      {
        id: '2',
        level: 'warning',
        message: 'Research task took longer than expected',
        timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        category: 'Research',
        details: 'Task ID: 123, Duration: 45s',
      },
      {
        id: '3',
        level: 'info',
        message: 'Automation executed successfully',
        timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
        category: 'Automation',
      },
      {
        id: '4',
        level: 'success',
        message: 'Content generated successfully',
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        category: 'Content',
      },
    ];
    setLogs(mockLogs);
  };

  const filteredLogs = filter === 'all' 
    ? logs 
    : logs.filter(log => log.level === filter);

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'info':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'success':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">System Logs & Debug</h1>
          <p className="text-gray-600 mt-1">Monitor system activity, errors, and performance</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex gap-2">
            {['all', 'error', 'warning', 'info', 'success'].map(level => (
              <button
                key={level}
                onClick={() => setFilter(level)}
                className={`px-4 py-2 rounded-lg capitalize ${
                  filter === level
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {level}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Level</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Message</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredLogs.map(log => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium border ${getLevelColor(log.level)}`}>
                        {log.level}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{log.message}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{log.category}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        View Details
                      </button>
                      {log.level === 'error' && (
                        <button className="ml-3 text-green-600 hover:text-green-900">
                          Re-run
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {selectedLog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">Log Details</h2>
                <button onClick={() => setSelectedLog(null)}>✕</button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="font-semibold">Message</label>
                  <p className="text-gray-700">{selectedLog.message}</p>
                </div>
                {selectedLog.details && (
                  <div>
                    <label className="font-semibold">Details</label>
                    <pre className="bg-gray-50 rounded p-3 text-sm">{selectedLog.details}</pre>
                  </div>
                )}
                {selectedLog.link && (
                  <a href={selectedLog.link} className="text-blue-600 hover:underline">
                    View Related Item →
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

