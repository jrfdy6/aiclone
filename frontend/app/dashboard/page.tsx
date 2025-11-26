'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type WidgetData = {
  quickSearch: {
    recentQueries: string[];
  };
  recentInsights: Array<{
    id: string;
    title: string;
    summary: string;
    source: string;
    date: string;
  }>;
  topProspects: Array<{
    id: string;
    name: string;
    company: string;
    fit_score: number;
  }>;
  followUpsDueToday: Array<{
    id: string;
    prospect_name: string;
    time: string;
  }>;
  contentIdeas: Array<{
    id: string;
    type: 'tweet' | 'linkedin' | 'email';
    title: string;
  }>;
};

export default function DashboardPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [widgetData, setWidgetData] = useState<WidgetData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setWidgetData({
        quickSearch: {
          recentQueries: ['AI in education', 'Prospect scoring', 'Content marketing trends'],
        },
        recentInsights: [
          {
            id: '1',
            title: 'AI Adoption in K-12 Schools',
            summary: 'Educational institutions are increasingly adopting AI tools for personalized learning...',
            source: 'Perplexity Research',
            date: '2 hours ago',
          },
          {
            id: '2',
            title: 'EdTech Market Trends Q4 2024',
            summary: 'Market analysis shows 25% growth in AI-powered education solutions...',
            source: 'Firecrawl Article',
            date: '1 day ago',
          },
        ],
        topProspects: [
          { id: '1', name: 'Sarah Johnson', company: 'TechEd Solutions', fit_score: 0.92 },
          { id: '3', name: 'Emily Rodriguez', company: 'Future Schools Inc', fit_score: 0.95 },
          { id: '2', name: 'Michael Chen', company: 'InnovateEd', fit_score: 0.87 },
        ],
        followUpsDueToday: [
          { id: '1', prospect_name: 'Emily Rodriguez', time: '10:00 AM' },
          { id: '2', prospect_name: 'David Park', time: '2:00 PM' },
        ],
        contentIdeas: [
          { id: '1', type: 'linkedin', title: '5 Ways AI is Transforming Education' },
          { id: '2', type: 'tweet', title: 'Quick tip: Using AI for prospect research' },
          { id: '3', type: 'email', title: 'Weekly newsletter: EdTech insights' },
        ],
      });
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    if (searchQuery.trim()) {
      window.location.href = `/knowledge?query=${encodeURIComponent(searchQuery)}`;
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading dashboard...</p>
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
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>Dashboard</h1>
          <p style={{ color: '#9ca3af' }}>Your unified AI workspace command center</p>
        </div>

        {/* Quick Search Widget */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>🔍 Quick Search</h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search your knowledge base..."
              style={{ flex: 1, borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
            />
            <button
              onClick={handleSearch}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Search
            </button>
          </div>
          {widgetData?.quickSearch.recentQueries && widgetData.quickSearch.recentQueries.length > 0 && (
            <div className="mt-3">
              <p className="text-sm text-gray-600 mb-2">Recent searches:</p>
              <div className="flex flex-wrap gap-2">
                {widgetData.quickSearch.recentQueries.map((query, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSearchQuery(query)}
                    className="text-xs px-3 py-1 bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Insights */}
          <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">🧠 Recent Insights</h2>
              <Link href="/prospecting" className="text-sm text-blue-600 hover:underline">
                View all →
              </Link>
            </div>
            <div className="space-y-4">
              {widgetData?.recentInsights.map((insight) => (
                <div
                  key={insight.id}
                  className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
                >
                  <h3 className="font-semibold text-gray-900 mb-1">{insight.title}</h3>
                  <p className="text-sm text-gray-600 mb-2 line-clamp-2">{insight.summary}</p>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>{insight.source}</span>
                    <span>{insight.date}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top Prospects Widget */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">🎯 Top Prospects</h2>
              <Link href="/prospects" className="text-sm text-blue-600 hover:underline">
                View all →
              </Link>
            </div>
            <div className="space-y-3">
              {widgetData?.topProspects.map((prospect, idx) => (
                <Link
                  key={prospect.id}
                  href={`/prospects`}
                  className="block p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-gray-900">{prospect.name}</span>
                    <span className="text-xs font-medium text-blue-600">
                      {Math.round(prospect.fit_score * 100)}%
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">{prospect.company}</p>
                  <div className="mt-2 w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${
                        prospect.fit_score > 0.8 ? 'bg-green-500' : prospect.fit_score > 0.6 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${prospect.fit_score * 100}%` }}
                    />
                  </div>
                </Link>
              ))}
            </div>
          </div>

          {/* Follow-ups Due Today */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">📅 Follow-ups Due Today</h2>
              <Link href="/calendar" className="text-sm text-blue-600 hover:underline">
                View calendar →
              </Link>
            </div>
            {widgetData?.followUpsDueToday && widgetData.followUpsDueToday.length > 0 ? (
              <div className="space-y-3">
                {widgetData.followUpsDueToday.map((followUp) => (
                  <div
                    key={followUp.id}
                    className="p-3 border border-yellow-200 bg-yellow-50 rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-gray-900">{followUp.prospect_name}</span>
                      <span className="text-xs text-gray-500">{followUp.time}</span>
                    </div>
                    <Link
                      href={`/outreach/${followUp.id}`}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      Generate message →
                    </Link>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 text-center py-4">No follow-ups scheduled for today</p>
            )}
          </div>

          {/* Content Generator Quick-Launch */}
          <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">✍️ Content Generator Quick-Launch</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Link
                href="/content-marketing"
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-center"
              >
                <div className="text-3xl mb-2">📝</div>
                <div className="font-medium text-gray-900">LinkedIn Post</div>
                <div className="text-xs text-gray-500 mt-1">Generate a post</div>
              </Link>
              <Link
                href="/content-marketing"
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-center"
              >
                <div className="text-3xl mb-2">🐦</div>
                <div className="font-medium text-gray-900">Tweet</div>
                <div className="text-xs text-gray-500 mt-1">Quick tweet</div>
              </Link>
              <Link
                href="/content-marketing"
                className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-center"
              >
                <div className="text-3xl mb-2">📧</div>
                <div className="font-medium text-gray-900">Email</div>
                <div className="text-xs text-gray-500 mt-1">Newsletter</div>
              </Link>
            </div>
            {widgetData?.contentIdeas && widgetData.contentIdeas.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <p className="text-sm font-medium text-gray-700 mb-2">Suggested Ideas:</p>
                <div className="space-y-2">
                  {widgetData.contentIdeas.map((idea) => (
                    <div key={idea.id} className="text-sm text-gray-600">
                      <span className="mr-2">
                        {idea.type === 'linkedin' ? '📝' : idea.type === 'tweet' ? '🐦' : '📧'}
                      </span>
                      {idea.title}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* System Status */}
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">📊 System Status</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Backend API</span>
                <span className="flex items-center space-x-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  <span className="text-sm font-medium text-gray-900">Connected</span>
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Firestore</span>
                <span className="flex items-center space-x-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  <span className="text-sm font-medium text-gray-900">Available</span>
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">AI Services</span>
                <span className="flex items-center space-x-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  <span className="text-sm font-medium text-gray-900">Ready</span>
                </span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-200">
              <Link
                href="/"
                className="text-sm text-blue-600 hover:underline block text-center"
              >
                View all features →
              </Link>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

