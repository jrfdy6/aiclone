'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type ResearchTask = {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed';
  assigned_to?: string;
  due_date?: string;
  created_at: string;
};

export default function ResearchTasksPage() {
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      setTasks([
        {
          id: '1',
          title: 'Market Research: EdTech Industry',
          description: 'Research trends and opportunities in the EdTech industry',
          status: 'in_progress',
          due_date: '2024-12-15',
          created_at: '2024-11-01T10:00:00Z',
        },
        {
          id: '2',
          title: 'Competitor Analysis',
          description: 'Analyze competitor products and positioning',
          status: 'pending',
          created_at: '2024-11-05T10:00:00Z',
        },
      ]);
    } catch (err) {
      console.error('Failed to load research tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredTasks = filter === 'all' 
    ? tasks 
    : tasks.filter(t => t.status === filter);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      case 'in_progress': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'pending': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading research tasks...</p>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Research Tasks
          </h1>
          <p style={{ color: '#9ca3af' }}>Manage your research and analysis tasks</p>
        </div>

        <div style={{ marginBottom: '24px', display: 'flex', gap: '8px' }}>
          {['all', 'pending', 'in_progress', 'completed'].map((f) => (
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
              {f === 'all' ? 'All' : f.replace('_', ' ')}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {filteredTasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
              <p>No research tasks found.</p>
            </div>
          ) : (
            filteredTasks.map((task) => (
              <div
                key={task.id}
                className={`p-4 rounded-lg border ${getStatusColor(task.status)}`}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontWeight: 600, fontSize: '16px', marginBottom: '4px' }}>
                      {task.title}
                    </h3>
                    <p style={{ fontSize: '14px', opacity: 0.8, marginBottom: '8px' }}>
                      {task.description}
                    </p>
                    {task.due_date && (
                      <p style={{ fontSize: '12px', opacity: 0.7 }}>
                        Due: {new Date(task.due_date).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <span
                    style={{
                      padding: '4px 12px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      textTransform: 'capitalize',
                    }}
                  >
                    {task.status.replace('_', ' ')}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
