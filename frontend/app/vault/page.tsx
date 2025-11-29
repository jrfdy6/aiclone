'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type VaultItem = {
  id: string;
  name: string;
  type: 'credential' | 'note' | 'document' | 'link';
  description?: string;
  content?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
};

export default function VaultPage() {
  const [items, setItems] = useState<VaultItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadItems();
  }, []);

  const loadItems = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setItems([
        {
          id: '1',
          name: 'API Keys',
          type: 'credential',
          description: 'Collection of API keys and tokens',
          tags: ['api', 'security'],
          created_at: '2024-01-15T10:00:00Z',
          updated_at: '2024-11-20T14:30:00Z',
        },
        {
          id: '2',
          name: 'Meeting Notes - Q4 Planning',
          type: 'note',
          description: 'Notes from quarterly planning meeting',
          tags: ['meetings', 'planning'],
          created_at: '2024-11-01T09:00:00Z',
          updated_at: '2024-11-05T16:00:00Z',
        },
        {
          id: '3',
          name: 'Important Resources',
          type: 'link',
          description: 'Collection of important documentation links',
          tags: ['resources', 'docs'],
          created_at: '2024-02-01T10:00:00Z',
          updated_at: '2024-11-15T10:00:00Z',
        },
      ]);
    } catch (err) {
      console.error('Failed to load vault items:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredItems = items.filter((item) => {
    const matchesFilter = filter === 'all' || item.type === filter;
    const matchesSearch =
      !searchQuery ||
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'credential': return '🔐';
      case 'note': return '📝';
      case 'document': return '📄';
      case 'link': return '🔗';
      default: return '📦';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'credential': return 'bg-red-100 text-red-800 border-red-200';
      case 'note': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'document': return 'bg-green-100 text-green-800 border-green-200';
      case 'link': return 'bg-purple-100 text-purple-800 border-purple-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading vault...</p>
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
              Vault
            </h1>
            <p style={{ color: '#9ca3af' }}>Secure storage for credentials, notes, and resources</p>
          </div>
          <button
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Add Item
          </button>
        </div>

        {/* Filters and Search */}
        <div style={{ marginBottom: '24px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search vault..."
              style={{
                width: '100%',
                padding: '12px',
                backgroundColor: '#1e293b',
                border: '1px solid #475569',
                borderRadius: '8px',
                color: 'white',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {['all', 'credential', 'note', 'document', 'link'].map((f) => (
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
        </div>

        {/* Items Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '24px' }}>
          {filteredItems.length === 0 ? (
            <div
              style={{
                gridColumn: '1 / -1',
                textAlign: 'center',
                padding: '48px',
                color: '#9ca3af',
              }}
            >
              <p>No vault items found. Add your first item to get started.</p>
            </div>
          ) : (
            filteredItems.map((item) => (
              <div
                key={item.id}
                style={{
                  backgroundColor: '#1e293b',
                  borderRadius: '12px',
                  border: '1px solid #475569',
                  padding: '24px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'start', gap: '12px', marginBottom: '12px' }}>
                  <div style={{ fontSize: '24px' }}>{getTypeIcon(item.type)}</div>
                  <div style={{ flex: 1 }}>
                    <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '4px' }}>
                      {item.name}
                    </h2>
                    <span
                      className={`px-2 py-1 rounded text-xs ${getTypeColor(item.type)}`}
                      style={{ textTransform: 'capitalize' }}
                    >
                      {item.type}
                    </span>
                  </div>
                </div>

                {item.description && (
                  <p style={{ fontSize: '14px', color: '#e2e8f0', marginBottom: '12px' }}>
                    {item.description}
                  </p>
                )}

                {item.tags && item.tags.length > 0 && (
                  <div style={{ marginBottom: '12px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {item.tags.map((tag, idx) => (
                      <span
                        key={idx}
                        style={{
                          padding: '4px 8px',
                          backgroundColor: '#475569',
                          color: '#cbd5e1',
                          borderRadius: '4px',
                          fontSize: '11px',
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                <div style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '16px' }}>
                  Updated: {new Date(item.updated_at).toLocaleDateString()}
                </div>

                <div style={{ display: 'flex', gap: '8px', paddingTop: '16px', borderTop: '1px solid #475569' }}>
                  <button
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                  >
                    View
                  </button>
                  <button
                    className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors text-sm"
                  >
                    Edit
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
