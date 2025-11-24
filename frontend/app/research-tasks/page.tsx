'use client';

import { useState, useEffect } from 'react';
import { getApiUrl } from '@/lib/api-client';
import Link from 'next/link';

type ResearchTask = {
  id: string;
  title: string;
  input_source: string;
  source_type: 'keywords' | 'urls' | 'profile';
  research_engine: 'perplexity' | 'firecrawl' | 'google_search';
  status: 'queued' | 'running' | 'done' | 'failed';
  priority: 'high' | 'medium' | 'low';
  created_at: string;
  completed_at?: string;
  outputs_available: boolean;
  error?: string;
};

type ResearchInsight = {
  summary: string;
  pain_points: string[];
  opportunities: string[];
  suggested_outreach: string[];
  content_angles: string[];
};

export default function ResearchTasksPage() {
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<ResearchTask | null>(null);
  const [insights, setInsights] = useState<ResearchInsight | null>(null);
  const [showInsightsModal, setShowInsightsModal] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskInput, setNewTaskInput] = useState('');
  const [newTaskEngine, setNewTaskEngine] = useState<'perplexity' | 'firecrawl' | 'google_search'>('perplexity');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    const apiUrl = getApiUrl();
    if (!apiUrl) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      // For now, use mock data - backend endpoint will be implemented
      const mockTasks: ResearchTask[] = [
        {
          id: '1',
          title: 'AI in K-12 Education Trends',
          input_source: 'AI education, K-12 technology, personalized learning',
          source_type: 'keywords',
          research_engine: 'perplexity',
          status: 'done',
          priority: 'high',
          created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          completed_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
          outputs_available: true,
        },
        {
          id: '2',
          title: 'EdTech Competitor Analysis',
          input_source: 'https://example.com/competitor',
          source_type: 'urls',
          research_engine: 'firecrawl',
          status: 'running',
          priority: 'medium',
          created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
          outputs_available: false,
        },
        {
          id: '3',
          title: 'Prospect Research: Sarah Johnson',
          input_source: 'LinkedIn profile analysis',
          source_type: 'profile',
          research_engine: 'google_search',
          status: 'queued',
          priority: 'low',
          created_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
          outputs_available: false,
        },
      ];
      setTasks(mockTasks);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewInsights = async (task: ResearchTask) => {
    setSelectedTask(task);
    // Mock insights - will be replaced with API call
    const mockInsights: ResearchInsight = {
      summary: 'AI adoption in K-12 education is accelerating, with schools increasingly using AI tools for personalized learning, administrative tasks, and student engagement.',
      pain_points: [
        'Teacher workload and burnout',
        'Student engagement challenges',
        'Budget constraints for technology',
        'Privacy and data security concerns',
      ],
      opportunities: [
        'AI-powered tutoring systems',
        'Automated administrative tools',
        'Personalized learning platforms',
        'Student progress tracking',
      ],
      suggested_outreach: [
        'Highlight how AI can reduce teacher workload',
        'Emphasize student engagement improvements',
        'Discuss ROI and cost savings',
        'Address privacy and security features',
      ],
      content_angles: [
        'Case study: How AI improved student outcomes',
        'ROI analysis: Cost savings with AI tools',
        'Privacy-first AI solutions for education',
        'Teacher testimonials on AI adoption',
      ],
    };
    setInsights(mockInsights);
    setShowInsightsModal(true);
  };

  const handleRunTask = async (taskId: string) => {
    // Mock implementation - will be replaced with API call
    setTasks(prev => prev.map(t => 
      t.id === taskId ? { ...t, status: 'running' as const } : t
    ));
    
    // Simulate task completion
    setTimeout(() => {
      setTasks(prev => prev.map(t => 
        t.id === taskId ? { ...t, status: 'done' as const, outputs_available: true } : t
      ));
    }, 2000);
  };

  const handleCreateTask = async () => {
    if (!newTaskTitle.trim() || !newTaskInput.trim()) return;

    const newTask: ResearchTask = {
      id: Date.now().toString(),
      title: newTaskTitle,
      input_source: newTaskInput,
      source_type: newTaskInput.includes('http') ? 'urls' : 'keywords',
      research_engine: newTaskEngine,
      status: 'queued',
      priority: 'medium',
      created_at: new Date().toISOString(),
      outputs_available: false,
    };

    setTasks(prev => [newTask, ...prev]);
    setNewTaskTitle('');
    setNewTaskInput('');
    setShowCreateModal(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'done':
        return 'bg-green-100 text-green-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getEngineIcon = (engine: string) => {
    switch (engine) {
      case 'perplexity':
        return '🤖';
      case 'firecrawl':
        return '🕷️';
      case 'google_search':
        return '🔍';
      default:
        return '⚙️';
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Research Tasks</h1>
            <p className="text-gray-600 mt-1">Automated research workflows using AI engines</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + New Research Task
          </button>
        </div>

        {/* Task Queue Table */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Task Title
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Input Source
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Engine
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Priority
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                      Loading tasks...
                    </td>
                  </tr>
                ) : tasks.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                      No research tasks yet. Create one to get started.
                    </td>
                  </tr>
                ) : (
                  tasks.map((task) => (
                    <tr key={task.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{task.title}</div>
                        <div className="text-xs text-gray-500 capitalize">{task.source_type}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900 max-w-xs truncate">{task.input_source}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-lg">{getEngineIcon(task.research_engine)}</span>
                        <div className="text-xs text-gray-500 capitalize">{task.research_engine.replace('_', ' ')}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(task.status)}`}>
                          {task.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${getPriorityColor(task.priority)}`}>
                          {task.priority}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(task.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                        {task.status === 'queued' && (
                          <button
                            onClick={() => handleRunTask(task.id)}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            Run Now
                          </button>
                        )}
                        {task.outputs_available && (
                          <button
                            onClick={() => handleViewInsights(task)}
                            className="text-green-600 hover:text-green-900"
                          >
                            View Insights
                          </button>
                        )}
                        {task.outputs_available && (
                          <button className="text-purple-600 hover:text-purple-900">
                            Download
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Create Task Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
              <h2 className="text-xl font-bold mb-4">Create Research Task</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Task Title</label>
                  <input
                    type="text"
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., AI in K-12 Education Trends"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Input Source</label>
                  <textarea
                    value={newTaskInput}
                    onChange={(e) => setNewTaskInput(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={3}
                    placeholder="Keywords, URLs, or profile info..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Research Engine</label>
                  <select
                    value={newTaskEngine}
                    onChange={(e) => setNewTaskEngine(e.target.value as any)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="perplexity">Perplexity AI</option>
                    <option value="firecrawl">Firecrawl</option>
                    <option value="google_search">Google Search</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateTask}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Create Task
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Insights Modal */}
        {showInsightsModal && selectedTask && insights && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold">Research Insights: {selectedTask.title}</h2>
                <button
                  onClick={() => setShowInsightsModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-6">
                {/* Summary */}
                <div>
                  <h3 className="text-lg font-semibold mb-2">Summary</h3>
                  <p className="text-gray-700">{insights.summary}</p>
                </div>

                {/* Pain Points */}
                <div>
                  <h3 className="text-lg font-semibold mb-2">Extracted Pain Points</h3>
                  <ul className="list-disc list-inside space-y-1">
                    {insights.pain_points.map((point, idx) => (
                      <li key={idx} className="text-gray-700">{point}</li>
                    ))}
                  </ul>
                </div>

                {/* Opportunities */}
                <div>
                  <h3 className="text-lg font-semibold mb-2">Opportunity Analysis</h3>
                  <ul className="list-disc list-inside space-y-1">
                    {insights.opportunities.map((opp, idx) => (
                      <li key={idx} className="text-gray-700">{opp}</li>
                    ))}
                  </ul>
                </div>

                {/* Suggested Outreach */}
                <div>
                  <h3 className="text-lg font-semibold mb-2">Suggested Outreach</h3>
                  <ul className="list-disc list-inside space-y-1">
                    {insights.suggested_outreach.map((outreach, idx) => (
                      <li key={idx} className="text-gray-700">{outreach}</li>
                    ))}
                  </ul>
                </div>

                {/* Content Angles */}
                <div>
                  <h3 className="text-lg font-semibold mb-2">Content Angles</h3>
                  <ul className="list-disc list-inside space-y-1">
                    {insights.content_angles.map((angle, idx) => (
                      <li key={idx} className="text-gray-700">{angle}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6 pt-6 border-t">
                <button
                  onClick={() => setShowInsightsModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Close
                </button>
                <button className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                  Download Report
                </button>
                <Link
                  href="/outreach"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Use for Outreach
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

