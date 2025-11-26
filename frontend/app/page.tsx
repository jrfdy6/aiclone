'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { getApiUrl } from '@/lib/api-client';
import NavHeader from '@/components/NavHeader';

const API_URL = getApiUrl();

type ProspectStats = {
  total: number;
  new: number;
  contacted: number;
  follow_up: number;
};

export default function Home() {
  const [stats, setStats] = useState<ProspectStats>({ total: 0, new: 0, contacted: 0, follow_up: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/prospects/?user_id=dev-user&limit=500`);
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.prospects) {
          const prospects = data.prospects;
          setStats({
            total: prospects.length,
            new: prospects.filter((p: any) => p.status === 'new').length,
            contacted: prospects.filter((p: any) => p.status === 'contacted').length,
            follow_up: prospects.filter((p: any) => p.status === 'follow_up_needed').length,
          });
        }
      }
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />

      {/* Hero */}
      <div className="max-w-5xl mx-auto px-6 pt-12 pb-12">
        <h1 className="text-5xl font-bold text-white mb-4">
          AI Clone
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl">
          Find prospects, generate personalized outreach, and manage your pipeline — all in one place.
        </p>
      </div>

      {/* Main Workflow Cards */}
      <div className="max-w-5xl mx-auto px-6 pb-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Step 1: Discover */}
          <Link
            href="/prospect-discovery"
            className="group relative bg-gradient-to-br from-blue-600 to-cyan-600 rounded-2xl p-6 hover:scale-[1.02] transition-all shadow-lg hover:shadow-xl"
          >
            <div className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-white font-bold">
              1
            </div>
            <div className="text-4xl mb-4">🔎</div>
            <h2 className="text-xl font-bold text-white mb-2">Find Prospects</h2>
            <p className="text-blue-100 text-sm">
              Search by specialty & location to discover real people. Free tier available.
            </p>
            <div className="mt-4 text-white/80 text-sm group-hover:text-white transition-colors">
              Start searching →
            </div>
          </Link>

          {/* Step 2: Manage */}
          <Link
            href="/prospects"
            className="group relative bg-gradient-to-br from-purple-600 to-pink-600 rounded-2xl p-6 hover:scale-[1.02] transition-all shadow-lg hover:shadow-xl"
          >
            <div className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-white font-bold">
              2
            </div>
            <div className="text-4xl mb-4">👥</div>
            <h2 className="text-xl font-bold text-white mb-2">View Pipeline</h2>
            <p className="text-purple-100 text-sm">
              Filter, sort, and manage all your prospects in one scrollable table.
            </p>
            {!loading && (
              <div className="mt-4 flex gap-3 text-sm">
                <span className="px-2 py-1 bg-white/20 rounded text-white">{stats.total} total</span>
                {stats.new > 0 && <span className="px-2 py-1 bg-blue-500/30 rounded text-blue-200">{stats.new} new</span>}
              </div>
            )}
          </Link>

          {/* Step 3: Content */}
          <Link
            href="/content-pipeline"
            className="group relative bg-gradient-to-br from-green-600 to-emerald-600 rounded-2xl p-6 hover:scale-[1.02] transition-all shadow-lg hover:shadow-xl"
          >
            <div className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-white font-bold">
              3
            </div>
            <div className="text-4xl mb-4">✉️</div>
            <h2 className="text-xl font-bold text-white mb-2">Content Pipeline</h2>
            <p className="text-green-100 text-sm">
              Generate cold emails, LinkedIn posts, DMs, and Instagram content.
            </p>
            <div className="mt-4 text-white/80 text-sm group-hover:text-white transition-colors">
              Create content →
            </div>
          </Link>
        </div>
      </div>

      {/* Quick Stats */}
      {!loading && stats.total > 0 && (
        <div className="max-w-5xl mx-auto px-6 pb-12">
          <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4">Pipeline Overview</h3>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <div className="text-3xl font-bold text-white">{stats.total}</div>
                <div className="text-sm text-gray-400">Total Prospects</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-blue-400">{stats.new}</div>
                <div className="text-sm text-gray-400">New</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-green-400">{stats.contacted}</div>
                <div className="text-sm text-gray-400">Contacted</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-orange-400">{stats.follow_up}</div>
                <div className="text-sm text-gray-400">Need Follow-up</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Other Tools */}
      <div className="max-w-5xl mx-auto px-6 pb-16">
        <h3 className="text-lg font-semibold text-white mb-4">More Tools</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Link
            href="/topic-intelligence"
            className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 hover:border-slate-600 transition-colors"
          >
            <div className="text-2xl mb-2">🧠</div>
            <div className="text-sm font-medium text-white">Topic Intelligence</div>
            <div className="text-xs text-gray-500">Research pain points</div>
          </Link>
          <Link
            href="/content-marketing"
            className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 hover:border-slate-600 transition-colors"
          >
            <div className="text-2xl mb-2">📝</div>
            <div className="text-sm font-medium text-white">Content Marketing</div>
            <div className="text-xs text-gray-500">Generate content ideas</div>
          </Link>
          <Link
            href="/knowledge"
            className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 hover:border-slate-600 transition-colors"
          >
            <div className="text-2xl mb-2">🔍</div>
            <div className="text-sm font-medium text-white">Knowledge Base</div>
            <div className="text-xs text-gray-500">Search your docs</div>
          </Link>
          <Link
            href="/calendar"
            className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 hover:border-slate-600 transition-colors"
          >
            <div className="text-2xl mb-2">📅</div>
            <div className="text-sm font-medium text-white">Follow-up Calendar</div>
            <div className="text-xs text-gray-500">Track outreach</div>
          </Link>
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-5xl mx-auto px-6 pb-8">
        <div className="flex items-center justify-between text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            <span>Backend Connected</span>
          </div>
          <Link href="/dashboard" className="hover:text-gray-300">
            Full Dashboard →
          </Link>
        </div>
      </div>
    </main>
  );
}
