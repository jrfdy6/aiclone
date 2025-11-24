'use client';

import { useState, useEffect } from 'react';

type Template = {
  id: string;
  title: string;
  description: string;
  category: string;
  content_preview: string;
  tags: string[];
  favorited: boolean;
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    // Mock data
    const mockTemplates: Template[] = [
      {
        id: '1',
        title: 'LinkedIn Post - Thought Leadership',
        description: 'Engaging thought leadership post template',
        category: 'LinkedIn',
        content_preview: '🚀 Excited to share 5 key insights on...',
        tags: ['linkedin', 'thought-leadership'],
        favorited: true,
      },
      {
        id: '2',
        title: 'Cold Email - Introduction',
        description: 'Professional cold email template for initial outreach',
        category: 'Email',
        content_preview: 'Hi [Name], I noticed that your company...',
        tags: ['email', 'cold-outreach'],
        favorited: false,
      },
      {
        id: '3',
        title: 'Prospecting DM - Value Offer',
        description: 'Direct message template offering value',
        category: 'LinkedIn DM',
        content_preview: 'Hi [Name], I saw your post about...',
        tags: ['dm', 'linkedin', 'prospecting'],
        favorited: true,
      },
      {
        id: '4',
        title: 'Follow-up Sequence - 3 Touch',
        description: 'Three-touch follow-up sequence template',
        category: 'Follow-up',
        content_preview: 'Touch 1: [Introduction] Touch 2: [Value] Touch 3: [CTA]',
        tags: ['follow-up', 'sequence'],
        favorited: false,
      },
      {
        id: '5',
        title: 'Reel Script - Educational',
        description: 'Short-form video script template',
        category: 'Video',
        content_preview: 'Hook: [Attention grabber] Story: [Narrative] CTA: [Action]',
        tags: ['reels', 'video', 'social-media'],
        favorited: false,
      },
    ];
    setTemplates(mockTemplates);
    setLoading(false);
  };

  const categories = ['all', 'LinkedIn', 'Email', 'LinkedIn DM', 'Follow-up', 'Video', 'Twitter'];

  const filteredTemplates = templates.filter(t => 
    selectedCategory === 'all' || t.category === selectedCategory
  );

  const toggleFavorite = (id: string) => {
    setTemplates(prev => prev.map(t => 
      t.id === id ? { ...t, favorited: !t.favorited } : t
    ));
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Templates Gallery</h1>
          <p className="text-gray-600 mt-1">Reusable templates for content and outreach</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex gap-2 flex-wrap">
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  selectedCategory === cat
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {cat === 'all' ? 'All' : cat}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading ? (
            <div className="col-span-full text-center py-12 text-gray-500">Loading templates...</div>
          ) : filteredTemplates.map(template => (
            <div
              key={template.id}
              className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">{template.category}</span>
                <button
                  onClick={() => toggleFavorite(template.id)}
                  className={`text-xl ${template.favorited ? 'text-yellow-500' : 'text-gray-300'}`}
                >
                  {template.favorited ? '★' : '☆'}
                </button>
              </div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">{template.title}</h3>
              <p className="text-sm text-gray-600 mb-4">{template.description}</p>
              <div className="bg-gray-50 rounded p-3 mb-4 text-sm text-gray-700 line-clamp-3">
                {template.content_preview}
              </div>
              <div className="flex items-center justify-between">
                <div className="flex flex-wrap gap-1">
                  {template.tags.map(tag => (
                    <span key={tag} className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => {
                    setSelectedTemplate(template);
                    setShowPreviewModal(true);
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
                >
                  Preview
                </button>
                <button className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
                  Use Template
                </button>
              </div>
            </div>
          ))}
        </div>

        {showPreviewModal && selectedTemplate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold">{selectedTemplate.title}</h2>
                <button onClick={() => setShowPreviewModal(false)}>✕</button>
              </div>
              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Content Preview</h3>
                  <div className="bg-gray-50 rounded p-4 whitespace-pre-wrap">
                    {selectedTemplate.content_preview}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
                    Duplicate & Edit
                  </button>
                  <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Use Template
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

