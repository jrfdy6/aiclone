'use client';

import Link from 'next/link';
import { useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const features = [
  {
    id: 'chat',
    title: 'Chat with Your Knowledge Base',
    description: 'Ask questions and get answers from your ingested documents using semantic search.',
    icon: '💬',
    href: '#chat',
    color: 'bg-blue-50 border-blue-200 hover:bg-blue-100',
    iconBg: 'bg-blue-100',
  },
  {
    id: 'knowledge',
    title: 'Knowledge Search',
    description: 'Search across all your documents, presentations, and files with AI-powered semantic search.',
    icon: '🔍',
    href: '/knowledge',
    color: 'bg-purple-50 border-purple-200 hover:bg-purple-100',
    iconBg: 'bg-purple-100',
  },
  {
    id: 'prospecting',
    title: 'AI-Assisted Prospecting',
    description: 'Analyze prospects, generate outreach prompts, and create personalized messaging for your pipeline.',
    icon: '🎯',
    href: '/prospecting',
    color: 'bg-green-50 border-green-200 hover:bg-green-100',
    iconBg: 'bg-green-100',
  },
  {
    id: 'outreach',
    title: 'Outreach Automation',
    description: 'Generate personalized outreach messages, connection requests, and follow-up sequences.',
    icon: '📧',
    href: '/outreach',
    color: 'bg-orange-50 border-orange-200 hover:bg-orange-100',
    iconBg: 'bg-orange-100',
  },
  {
    id: 'prospects',
    title: 'Prospect Management',
    description: 'View, manage, and track your prospects with intelligent scoring and filtering.',
    icon: '👥',
    href: '/prospects',
    color: 'bg-teal-50 border-teal-200 hover:bg-teal-100',
    iconBg: 'bg-teal-100',
  },
  {
    id: 'calendar',
    title: 'Follow-Up Calendar',
    description: 'Schedule, track, and manage your outreach follow-ups with drag-and-drop calendar.',
    icon: '📅',
    href: '/calendar',
    color: 'bg-pink-50 border-pink-200 hover:bg-pink-100',
    iconBg: 'bg-pink-100',
  },
  {
    id: 'dashboard',
    title: 'Dashboard',
    description: 'Unified workspace with quick search, insights, top prospects, and system status.',
    icon: '📊',
    href: '/dashboard',
    color: 'bg-indigo-50 border-indigo-200 hover:bg-indigo-100',
    iconBg: 'bg-indigo-100',
  },
  {
    id: 'content',
    title: 'Content Marketing Tools',
    description: 'Research topics, analyze competitors, generate content ideas, and optimize for SEO.',
    icon: '📝',
    href: '/content-marketing',
    color: 'bg-pink-50 border-pink-200 hover:bg-pink-100',
    iconBg: 'bg-pink-100',
  },
  {
    id: 'jumpstart',
    title: 'AI Advantage Jumpstart',
    description: 'Access the AI Advantage Jumpstart Playbook with prompts and strategies for leveraging AI.',
    icon: '🚀',
    href: '/jumpstart',
    color: 'bg-indigo-50 border-indigo-200 hover:bg-indigo-100',
    iconBg: 'bg-indigo-100',
  },
];

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

type RetrievalResult = {
  source_id: string;
  chunk_index: number | null;
  chunk: string;
  similarity_score: number;
  metadata: Record<string, unknown>;
};

type RetrievalResponse = {
  success: boolean;
  query: string;
  results: RetrievalResult[];
};

const createId = () =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [results, setResults] = useState<RetrievalResult[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState('dev-user');
  const [showChat, setShowChat] = useState(false);

  const hasResults = results.length > 0;

  const handleSend = async (message: string) => {
    if (isSending) {
      return;
    }

    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }

    if (!API_URL) {
      setError('NEXT_PUBLIC_API_URL is not configured.');
      return;
    }

    setError(null);
    const userMessage: ChatMessage = {
      id: createId(),
      role: 'user',
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsSending(true);

    try {
      const response = await fetch(`${API_URL}/api/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          query: trimmed,
        }),
      });

      if (!response.ok) {
        throw new Error(`Chat request failed with status ${response.status}`);
      }

      const data: RetrievalResponse = await response.json();
      setResults(Array.isArray(data.results) ? data.results : []);

      const assistantMessage: ChatMessage = {
        id: createId(),
        role: 'assistant',
        content: `Found ${data.results.length} relevant result(s) for "${trimmed}".`,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error sending message.');
    } finally {
      setIsSending(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Hero Section */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              AI Clone
            </h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Your comprehensive AI-powered platform for knowledge management, prospecting automation, 
              content marketing, and intelligent workflows.
            </p>
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Available Features</h2>
          <p className="text-gray-600">Explore all the powerful tools at your fingertips</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
          {features.map((feature) => (
            <Link
              key={feature.id}
              href={feature.href}
              className={`block rounded-lg border-2 p-6 transition-all duration-200 ${feature.color}`}
            >
              <div className="flex items-start space-x-4">
                <div className={`${feature.iconBg} rounded-lg p-3 text-2xl flex-shrink-0`}>
                  {feature.icon}
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {feature.description}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Chat Interface Section */}
        <div id="chat" className="bg-white rounded-lg border-2 border-gray-200 shadow-sm overflow-hidden">
          <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">💬 Chat with Your Knowledge Base</h2>
                <p className="text-blue-100 text-sm mt-1">Ask questions and get answers from your documents</p>
              </div>
              <button
                onClick={() => setShowChat(!showChat)}
                className="text-white hover:text-blue-100 transition-colors"
              >
                {showChat ? '−' : '+'}
              </button>
            </div>
          </div>

          {showChat && (
            <div className="p-6 space-y-4">
              <div className="flex items-center space-x-2">
                <label className="block text-sm font-medium text-gray-700">User ID</label>
                <input
                  value={userId}
                  onChange={(event) => setUserId(event.target.value)}
                  className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="dev-user"
                />
              </div>

              {error && (
                <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              {messages.length > 0 && (
                <div className="space-y-3 max-h-96 overflow-y-auto border rounded-lg p-4 bg-gray-50">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`p-3 rounded-lg ${
                        msg.role === 'user'
                          ? 'bg-blue-100 ml-auto max-w-[80%]'
                          : 'bg-gray-200 mr-auto max-w-[80%]'
                      }`}
                    >
                      <p className="text-sm text-gray-800">{msg.content}</p>
                    </div>
                  ))}
                </div>
              )}

              {hasResults && (
                <div className="space-y-3 border-t pt-4">
                  <h3 className="font-semibold text-gray-900">Retrieved Context</h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {results.map((result) => (
                      <div
                        key={`${result.source_id}-${result.chunk_index}`}
                        className="rounded border border-gray-200 p-3 bg-gray-50 text-sm"
                      >
                        <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                          <span className="font-medium">
                            {String(result.metadata?.file_name ?? result.source_id)}
                          </span>
                          <span>Score: {result.similarity_score.toFixed(3)}</span>
                        </div>
                        <p className="text-gray-700 whitespace-pre-line">{result.chunk}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex space-x-2">
                <input
                  type="text"
                  placeholder="Type your question..."
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !isSending && e.currentTarget.value.trim()) {
                      handleSend(e.currentTarget.value);
                      e.currentTarget.value = '';
                    }
                  }}
                  className="flex-1 rounded border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isSending}
                />
                <button
                  onClick={(e) => {
                    const input = e.currentTarget.previousElementSibling as HTMLInputElement;
                    if (input?.value.trim() && !isSending) {
                      handleSend(input.value);
                      input.value = '';
                    }
                  }}
                  disabled={isSending}
                  className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSending ? 'Sending...' : 'Send'}
                </button>
              </div>

              {messages.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">
                  Start by typing a question about your knowledge base...
                </p>
              )}
            </div>
          )}
        </div>

        {/* System Status */}
        <div className="mt-12 bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-3">System Status</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              <span className="text-gray-600">Backend API: Connected</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              <span className="text-gray-600">Firestore: Available</span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
              <span className="text-gray-600">Ready to use</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
