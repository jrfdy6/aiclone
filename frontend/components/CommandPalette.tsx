'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getApiUrl } from '@/lib/api-client';

type SearchResult = {
  id: string;
  type: 'prospect' | 'event' | 'insight' | 'playbook' | 'template' | 'page' | 'action';
  title: string;
  subtitle?: string;
  icon: string;
  action?: () => void;
  href?: string;
};

type CommandPaletteProps = {
  isOpen: boolean;
  onClose: () => void;
};

export default function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
      loadQuickActions();
    }
  }, [isOpen]);

  useEffect(() => {
    if (query.trim()) {
      search(query);
    } else {
      loadQuickActions();
    }
  }, [query]);

  const loadQuickActions = async () => {
    const quickActions: SearchResult[] = [
      { id: '1', type: 'action' as const, title: 'Create new prospect', icon: '👤', action: () => router.push('/prospecting') },
      { id: '2', type: 'action' as const, title: 'Generate outreach sequence', icon: '📧', action: () => router.push('/outreach') },
      { id: '3', type: 'action' as const, title: 'Run research task', icon: '🔍', action: () => router.push('/research-tasks') },
      { id: '4', type: 'action' as const, title: 'Open calendar', icon: '📅', href: '/calendar' },
      { id: '5', type: 'action' as const, title: 'Search knowledge base', icon: '📚', href: '/knowledge' },
      { id: '6', type: 'page' as const, title: 'Go to Prospect Management', icon: '👥', href: '/prospects' },
      { id: '7', type: 'page' as const, title: 'Go to Dashboard', icon: '📊', href: '/dashboard' },
      { id: '8', type: 'page' as const, title: 'Go to Content Marketing', icon: '📝', href: '/content-marketing' },
    ];
    setResults(quickActions);
  };

  const search = async (searchQuery: string) => {
    setLoading(true);
    const apiUrl = getApiUrl();
    
    try {
      const allResults: SearchResult[] = [];

      // Search prospects
      try {
        const prospectsRes = await fetch(`${apiUrl}/api/prospects/?user_id=dev-user&limit=10&search=${encodeURIComponent(searchQuery)}`);
        if (prospectsRes.ok) {
          const data = await prospectsRes.json();
          if (data.prospects) {
            data.prospects.forEach((p: any) => {
              allResults.push({
                id: `prospect-${p.id}`,
                type: 'prospect' as const,
                title: p.name || 'Unknown',
                subtitle: `${p.company || ''} - ${p.job_title || ''}`,
                icon: '👤',
                href: `/prospects?id=${p.id}`,
              });
            });
          }
        }
      } catch (e) {
        // Ignore errors
      }

      // Search calendar events
      try {
        const today = new Date();
        const startDate = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
        const endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
        const eventsRes = await fetch(`${apiUrl}/api/calendar/?user_id=dev-user&start_date=${startDate}&end_date=${endDate}&limit=10`);
        if (eventsRes.ok) {
          const data = await eventsRes.json();
          if (data.events) {
            data.events
              .filter((e: any) => 
                e.prospect_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                e.company?.toLowerCase().includes(searchQuery.toLowerCase())
              )
              .forEach((e: any) => {
                allResults.push({
                  id: `event-${e.id}`,
                  type: 'event' as const,
                  title: e.prospect_name || 'Unknown',
                  subtitle: `${e.company || ''} - ${e.scheduled_date || ''}`,
                  icon: '📅',
                  href: `/calendar?event=${e.id}`,
                });
              });
          }
        }
      } catch (e) {
        // Ignore errors
      }

      // Page navigation
      const pages: SearchResult[] = [
        { id: 'page-prospects', type: 'page' as const, title: 'Go to Prospect Management', icon: '👥', href: '/prospects' },
        { id: 'page-calendar', type: 'page' as const, title: 'Go to Calendar', icon: '📅', href: '/calendar' },
        { id: 'page-dashboard', type: 'page' as const, title: 'Go to Dashboard', icon: '📊', href: '/dashboard' },
        { id: 'page-outreach', type: 'page' as const, title: 'Go to Outreach', icon: '📧', href: '/outreach' },
        { id: 'page-research', type: 'page' as const, title: 'Go to Research Tasks', icon: '🔍', href: '/research-tasks' },
        { id: 'page-playbooks', type: 'page' as const, title: 'Go to Playbooks', icon: '📖', href: '/playbooks' },
        { id: 'page-templates', type: 'page' as const, title: 'Go to Templates', icon: '📋', href: '/templates' },
        { id: 'page-vault', type: 'page' as const, title: 'Go to Knowledge Vault', icon: '💎', href: '/vault' },
        { id: 'page-activity', type: 'page' as const, title: 'Go to Activity Timeline', icon: '⚡', href: '/activity' },
        { id: 'page-automations', type: 'page' as const, title: 'Go to Automations', icon: '🤖', href: '/automations' },
        { id: 'page-personas', type: 'page' as const, title: 'Go to Personas', icon: '🎭', href: '/personas' },
        { id: 'page-content', type: 'page' as const, title: 'Go to Content Marketing', icon: '📝', href: '/content-marketing' },
        { id: 'page-knowledge', type: 'page' as const, title: 'Go to Knowledge Search', icon: '📚', href: '/knowledge' },
      ].filter(p => 
        p.title.toLowerCase().includes(searchQuery.toLowerCase())
      );

      allResults.push(...pages);

      // Quick actions that match query
      const actions: SearchResult[] = [
        { id: 'action-create-prospect', type: 'action' as const, title: 'Create new prospect', icon: '👤', action: () => router.push('/prospecting') },
        { id: 'action-generate-outreach', type: 'action' as const, title: 'Generate outreach sequence', icon: '📧', action: () => router.push('/outreach') },
        { id: 'action-research-task', type: 'action' as const, title: 'Run research task', icon: '🔍', action: () => router.push('/research-tasks') },
        { id: 'action-create-automation', type: 'action' as const, title: 'Create new automation', icon: '🤖', action: () => router.push('/automations?new=true') },
        { id: 'action-create-template', type: 'action' as const, title: 'Create new template', icon: '📋', action: () => router.push('/templates?new=true') },
      ].filter(a => 
        a.title.toLowerCase().includes(searchQuery.toLowerCase())
      );

      allResults.push(...actions);

      // Filter and sort by relevance
      const filtered = allResults.slice(0, 10);
      setResults(filtered);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (results[selectedIndex]) {
        handleSelect(results[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  const handleSelect = (result: SearchResult) => {
    if (result.action) {
      result.action();
    } else if (result.href) {
      router.push(result.href);
    }
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/50" onClick={onClose}>
      <div 
        className="bg-white rounded-lg shadow-2xl w-full max-w-2xl max-h-[60vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <span className="text-gray-400">🔍</span>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search prospects, events, pages, or run actions..."
              className="flex-1 outline-none text-lg"
            />
            {loading && <span className="text-gray-400 text-sm">Loading...</span>}
          </div>
        </div>

        {/* Results */}
        <div className="overflow-y-auto flex-1">
          {results.length === 0 && !loading && (
            <div className="p-8 text-center text-gray-500">
              {query.trim() ? 'No results found' : 'Type to search or use arrow keys to navigate'}
            </div>
          )}
          
          {results.map((result, index) => (
            <button
              key={result.id}
              onClick={() => handleSelect(result)}
              className={`w-full px-4 py-3 flex items-center space-x-3 text-left hover:bg-gray-50 transition-colors ${
                index === selectedIndex ? 'bg-blue-50 border-l-4 border-blue-600' : ''
              }`}
            >
              <span className="text-2xl">{result.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-900">{result.title}</div>
                {result.subtitle && (
                  <div className="text-sm text-gray-500 truncate">{result.subtitle}</div>
                )}
                <div className="text-xs text-gray-400 mt-0.5">
                  {result.type === 'prospect' && 'Prospect'}
                  {result.type === 'event' && 'Calendar Event'}
                  {result.type === 'page' && 'Page'}
                  {result.type === 'action' && 'Quick Action'}
                </div>
              </div>
              <span className="text-gray-400 text-xs">Enter ↵</span>
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center space-x-4">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>Esc Close</span>
          </div>
          <div>
            <kbd className="px-2 py-1 bg-white border border-gray-300 rounded">⌘K</kbd> to open
          </div>
        </div>
      </div>
    </div>
  );
}

