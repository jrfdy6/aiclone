'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

type Playbook = {
  id: string;
  title: string;
  description: string;
  category: string;
  icon: string;
  favorited: boolean;
  tags: string[];
};

export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedPlaybook, setSelectedPlaybook] = useState<Playbook | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);

  useEffect(() => {
    loadPlaybooks();
  }, []);

  const loadPlaybooks = async () => {
    // Mock data - will be replaced with API call
    const mockPlaybooks: Playbook[] = [
      {
        id: '1',
        title: 'LinkedIn Growth',
        description: 'Complete playbook for growing your LinkedIn presence and engagement',
        category: 'Social Media',
        icon: '💼',
        favorited: true,
        tags: ['linkedin', 'growth', 'engagement'],
      },
      {
        id: '2',
        title: 'B2B Prospecting',
        description: 'End-to-end B2B prospecting strategy with outreach templates',
        category: 'Sales',
        icon: '🎯',
        favorited: false,
        tags: ['b2b', 'prospecting', 'outreach'],
      },
      {
        id: '3',
        title: 'Newsletter Writing',
        description: 'Create engaging newsletters that convert readers into customers',
        category: 'Content',
        icon: '📧',
        favorited: false,
        tags: ['email', 'newsletter', 'content'],
      },
      {
        id: '4',
        title: 'Competitor Analysis',
        description: 'Deep dive into competitor strategies and market positioning',
        category: 'Research',
        icon: '🔍',
        favorited: true,
        tags: ['competitor', 'analysis', 'research'],
      },
      {
        id: '5',
        title: 'SEO Pillar Content',
        description: 'Build comprehensive SEO content that ranks and converts',
        category: 'Content',
        icon: '📝',
        favorited: false,
        tags: ['seo', 'content', 'blogging'],
      },
      {
        id: '6',
        title: 'AI Advantage Jumpstart',
        description: 'Complete guide to leveraging AI for business growth',
        category: 'AI',
        icon: '🚀',
        favorited: true,
        tags: ['ai', 'automation', 'growth'],
      },
    ];
    setPlaybooks(mockPlaybooks);
    setLoading(false);
  };

  const categories = ['all', 'Social Media', 'Sales', 'Content', 'Research', 'AI'];

  const filteredPlaybooks = playbooks.filter(p => {
    const matchesSearch = p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         p.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesCategory = selectedCategory === 'all' || p.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const toggleFavorite = (id: string) => {
    setPlaybooks(prev => prev.map(p => 
      p.id === id ? { ...p, favorited: !p.favorited } : p
    ));
  };

  const handleRunPlaybook = (playbook: Playbook) => {
    setSelectedPlaybook(playbook);
    setShowRunModal(true);
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Playbooks Library</h1>
          <p className="text-gray-600 mt-1">Reusable workflows and strategies for your business</p>
        </div>

        {/* Search and Filters */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search playbooks..."
                className="w-full rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-2">
              {categories.map(category => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    selectedCategory === category
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {category === 'all' ? 'All' : category}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Playbook Grid */}
        {loading ? (
          <div className="text-center py-12 text-gray-500">Loading playbooks...</div>
        ) : filteredPlaybooks.length === 0 ? (
          <div className="text-center py-12 text-gray-500">No playbooks found</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPlaybooks.map(playbook => (
              <div
                key={playbook.id}
                className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow"
              >
                <div className="flex items-start justify-between mb-4">
                  <span className="text-4xl">{playbook.icon}</span>
                  <button
                    onClick={() => toggleFavorite(playbook.id)}
                    className={`text-2xl ${playbook.favorited ? 'text-yellow-500' : 'text-gray-300'} hover:text-yellow-500`}
                  >
                    {playbook.favorited ? '★' : '☆'}
                  </button>
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2">{playbook.title}</h3>
                <p className="text-gray-600 mb-4">{playbook.description}</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">{playbook.category}</span>
                  <button
                    onClick={() => handleRunPlaybook(playbook)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                  >
                    Run →
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Run Playbook Modal */}
        {showRunModal && selectedPlaybook && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
              <h2 className="text-2xl font-bold mb-4">Run Playbook: {selectedPlaybook.title}</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Input</label>
                  <textarea
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={4}
                    placeholder="Enter input for this playbook..."
                  />
                </div>
                <div className="flex justify-end space-x-3">
                  <button
                    onClick={() => setShowRunModal(false)}
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Run Playbook
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

