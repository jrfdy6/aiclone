'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Template = {
  id: string;
  name: string;
  description: string;
  type: 'email' | 'linkedin' | 'dm' | 'cold_call';
  category: string;
  content: string;
  variables?: string[];
  created_at: string;
  updated_at: string;
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setTemplates([
        {
          id: '1',
          name: 'Cold Email - Value Proposition',
          description: 'Professional cold email template highlighting value proposition',
          type: 'email',
          category: 'Outreach',
          content: 'Hi {{prospect_name}},\n\nI noticed {{company_name}} is working on {{pain_point}}. I\'d love to share how we can help.\n\nBest regards,\n{{sender_name}}',
          variables: ['prospect_name', 'company_name', 'pain_point', 'sender_name'],
          created_at: '2024-01-15T10:00:00Z',
          updated_at: '2024-11-20T14:30:00Z',
        },
        {
          id: '2',
          name: 'LinkedIn Connection Request',
          description: 'Personalized LinkedIn connection request message',
          type: 'linkedin',
          category: 'Social',
          content: 'Hi {{prospect_name}},\n\nI saw your post about {{topic}} and thought you might be interested in connecting. Would love to share ideas!\n\nBest,\n{{sender_name}}',
          variables: ['prospect_name', 'topic', 'sender_name'],
          created_at: '2024-02-01T09:00:00Z',
          updated_at: '2024-11-18T16:00:00Z',
        },
        {
          id: '3',
          name: 'Follow-up Email',
          description: 'Professional follow-up email template',
          type: 'email',
          category: 'Follow-up',
          content: 'Hi {{prospect_name}},\n\nJust following up on my previous message about {{topic}}. Would you be open to a quick conversation?\n\nBest,\n{{sender_name}}',
          variables: ['prospect_name', 'topic', 'sender_name'],
          created_at: '2024-03-10T10:00:00Z',
          updated_at: '2024-11-15T10:00:00Z',
        },
      ]);
    } catch (err) {
      console.error('Failed to load templates:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredTemplates = templates.filter((template) => {
    const matchesFilter = filter === 'all' || template.type === filter;
    const matchesSearch =
      !searchQuery ||
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'email': return '📧';
      case 'linkedin': return '💼';
      case 'dm': return '💬';
      case 'cold_call': return '📞';
      default: return '📄';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'email': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'linkedin': return 'bg-cyan-100 text-cyan-800 border-cyan-200';
      case 'dm': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'cold_call': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading templates...</p>
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
              Templates
            </h1>
            <p style={{ color: '#9ca3af' }}>Manage your outreach and communication templates</p>
          </div>
          <button
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Create Template
          </button>
        </div>

        {/* Filters and Search */}
        <div style={{ marginBottom: '24px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search templates..."
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
            {['all', 'email', 'linkedin', 'dm', 'cold_call'].map((f) => (
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
        </div>

        {/* Template List */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '24px' }}>
          {filteredTemplates.length === 0 ? (
            <div
              style={{
                gridColumn: '1 / -1',
                textAlign: 'center',
                padding: '48px',
                color: '#9ca3af',
              }}
            >
              <p>No templates found. Create your first template to get started.</p>
            </div>
          ) : (
            filteredTemplates.map((template) => (
              <div
                key={template.id}
                style={{
                  backgroundColor: '#1e293b',
                  borderRadius: '12px',
                  border: '1px solid #475569',
                  padding: '24px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'start', gap: '12px', marginBottom: '12px' }}>
                  <div style={{ fontSize: '24px' }}>{getTypeIcon(template.type)}</div>
                  <div style={{ flex: 1 }}>
                    <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '4px' }}>
                      {template.name}
                    </h2>
                    <p style={{ fontSize: '13px', color: '#9ca3af' }}>
                      {template.category}
                    </p>
                  </div>
                </div>

                <p style={{ fontSize: '14px', color: '#e2e8f0', marginBottom: '16px' }}>
                  {template.description}
                </p>

                {template.variables && template.variables.length > 0 && (
                  <div style={{ marginBottom: '16px' }}>
                    <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '8px' }}>
                      Variables:
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {template.variables.map((variable, idx) => (
                        <span
                          key={idx}
                          style={{
                            padding: '4px 8px',
                            backgroundColor: '#475569',
                            color: '#cbd5e1',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontFamily: 'monospace',
                          }}
                        >
                          {`{{${variable}}}`}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div
                  className={`p-3 rounded-lg border ${getTypeColor(template.type)}`}
                  style={{ marginBottom: '16px' }}
                >
                  <pre
                    style={{
                      fontSize: '12px',
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'monospace',
                      margin: 0,
                      maxHeight: '100px',
                      overflow: 'auto',
                    }}
                  >
                    {template.content.substring(0, 150)}
                    {template.content.length > 150 ? '...' : ''}
                  </pre>
                </div>

                <div style={{ display: 'flex', gap: '8px', paddingTop: '16px', borderTop: '1px solid #475569' }}>
                  <button
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                  >
                    Edit
                  </button>
                  <button
                    className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors text-sm"
                  >
                    Use Template
                  </button>
                  <button
                    className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors text-sm"
                  >
                    Preview
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
