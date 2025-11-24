'use client';

import { useState } from 'react';
import Link from 'next/link';

type VaultItem = {
  id: string;
  title: string;
  summary: string;
  topic: string;
  source: string;
  date: string;
  tags: string[];
  highlights: string[];
  linked_outreach?: string;
  linked_content?: string;
};

export default function VaultPage() {
  const [items, setItems] = useState<VaultItem[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<string>('all');
  const [selectedItem, setSelectedItem] = useState<VaultItem | null>(null);

  // Mock data
  const vaultItems: VaultItem[] = [
    {
      id: '1',
      title: 'AI Adoption in K-12 Education',
      summary: 'Educational institutions are increasingly adopting AI tools for personalized learning and administrative efficiency.',
      topic: 'Education Technology',
      source: 'Perplexity Research',
      date: '2024-11-20',
      tags: ['ai', 'education', 'k12', 'trends'],
      highlights: ['25% growth in AI adoption', 'Focus on personalized learning', 'Privacy concerns remain'],
      linked_outreach: '/outreach',
      linked_content: '/content-marketing',
    },
    {
      id: '2',
      title: 'EdTech Market Analysis Q4 2024',
      summary: 'Market analysis shows significant growth in AI-powered education solutions with increased investment.',
      topic: 'Market Trends',
      source: 'Firecrawl Article',
      date: '2024-11-18',
      tags: ['market', 'analysis', 'edtech'],
      highlights: ['$2.5B market size', '30% YoY growth', 'Key players identified'],
    },
  ];

  const topics = ['all', 'Education Technology', 'Market Trends', 'Competitor Analysis', 'Industry Insights'];

  const filteredItems = selectedTopic === 'all' 
    ? vaultItems 
    : vaultItems.filter(item => item.topic === selectedTopic);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI Knowledge Vault</h1>
          <p className="text-gray-600 mt-1">Your research insights organized and linked to actionable items</p>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex gap-2 flex-wrap">
            {topics.map(topic => (
              <button
                key={topic}
                onClick={() => setSelectedTopic(topic)}
                className={`px-4 py-2 rounded-lg ${
                  selectedTopic === topic
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {topic === 'all' ? 'All Topics' : topic}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredItems.map(item => (
            <div
              key={item.id}
              className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => setSelectedItem(item)}
            >
              <div className="mb-2">
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">{item.topic}</span>
              </div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">{item.title}</h3>
              <p className="text-sm text-gray-600 mb-4 line-clamp-3">{item.summary}</p>
              <div className="flex flex-wrap gap-1 mb-4">
                {item.tags.map(tag => (
                  <span key={tag} className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                    {tag}
                  </span>
                ))}
              </div>
              <div className="text-xs text-gray-500 mb-4">
                Source: {item.source} • {item.date}
              </div>
              <div className="flex gap-2">
                {item.linked_outreach && (
                  <Link
                    href={item.linked_outreach}
                    className="text-xs text-blue-600 hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Suggested Outreach →
                  </Link>
                )}
                {item.linked_content && (
                  <Link
                    href={item.linked_content}
                    className="text-xs text-green-600 hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Content Ideas →
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>

        {selectedItem && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => setSelectedItem(null)}
          >
            <div
              className="bg-white rounded-lg shadow-xl p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold">{selectedItem.title}</h2>
                <button onClick={() => setSelectedItem(null)}>✕</button>
              </div>
              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Summary</h3>
                  <p className="text-gray-700">{selectedItem.summary}</p>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Key Highlights</h3>
                  <ul className="list-disc list-inside space-y-1">
                    {selectedItem.highlights.map((highlight, idx) => (
                      <li key={idx} className="text-gray-700">{highlight}</li>
                    ))}
                  </ul>
                </div>
                <div className="flex gap-3 pt-4 border-t">
                  {selectedItem.linked_outreach && (
                    <Link
                      href={selectedItem.linked_outreach}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                    >
                      Use for Outreach
                    </Link>
                  )}
                  {selectedItem.linked_content && (
                    <Link
                      href={selectedItem.linked_content}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                    >
                      Create Content
                    </Link>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

