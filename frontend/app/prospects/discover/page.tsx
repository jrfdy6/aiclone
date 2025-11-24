'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { prospectAPI } from '@/lib/api';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function DiscoverProspectsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [user_id] = useState('demo-user-123'); // TODO: Get from auth

  const [industry, setIndustry] = useState('EdTech');
  const [location, setLocation] = useState('');
  const [maxResults, setMaxResults] = useState(10);
  const [isDiscovering, setIsDiscovering] = useState(false);

  const discoverMutation = useMutation({
    mutationFn: (params: { industry?: string; location?: string; max_results: number }) =>
      prospectAPI.discover(user_id, params),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
      alert(`Discovered ${data.discovered_count} prospects! Redirecting to prospects page...`);
      router.push('/prospects');
    },
  });

  const handleDiscover = async () => {
    setIsDiscovering(true);
    try {
      await discoverMutation.mutateAsync({
        industry: industry || undefined,
        location: location || undefined,
        max_results: maxResults,
      });
    } catch (error) {
      alert(`Discovery failed: ${error}`);
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6">
          <Link
            href="/prospects"
            className="mb-4 inline-block text-sm text-gray-500 hover:text-gray-700"
          >
            ← Back to Prospects
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Discover Prospects</h1>
          <p className="mt-1 text-sm text-gray-500">
            Use Google Custom Search + Firecrawl to find new prospects
          </p>
        </div>

        <div className="rounded-lg bg-white p-6 shadow">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Industry</label>
              <input
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="EdTech, SaaS, Healthcare..."
                className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Location (Optional)</label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="San Francisco, New York..."
                className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Max Results</label>
              <input
                type="number"
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value))}
                min={1}
                max={50}
                className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                Note: Free-tier limits apply. Start with 10-20 results.
              </p>
            </div>

            <div className="rounded-lg bg-blue-50 p-4">
              <h3 className="mb-2 text-sm font-semibold text-blue-900">How it works:</h3>
              <ul className="space-y-1 text-sm text-blue-800">
                <li>1. Google Custom Search finds company pages</li>
                <li>2. Firecrawl scrapes team/contact pages</li>
                <li>3. Prospects are extracted and saved as "pending"</li>
                <li>4. Review and approve prospects on the Prospects page</li>
              </ul>
            </div>

            <button
              onClick={handleDiscover}
              disabled={isDiscovering || discoverMutation.isPending}
              className="w-full rounded-lg bg-blue-600 px-4 py-3 text-base font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {isDiscovering || discoverMutation.isPending ? 'Discovering Prospects...' : 'Discover Prospects'}
            </button>

            {discoverMutation.isError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                Error: {discoverMutation.error instanceof Error ? discoverMutation.error.message : 'Unknown error'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

