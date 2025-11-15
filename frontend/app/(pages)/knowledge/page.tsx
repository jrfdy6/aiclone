'use client';

import { useState } from 'react';

type SourceItem = {
  id: string;
  score: number;
  data: {
    text: string;
    source?: string;
    chunk_index?: number;
  } & Record<string, unknown>;
};

type QueryResponse = {
  answer: string;
  sources: SourceItem[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function KnowledgePage() {
  const [query, setQuery] = useState('');
  const [userId, setUserId] = useState('default-user');
  const [topK, setTopK] = useState(5);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<QueryResponse | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!API_URL) {
      setError('NEXT_PUBLIC_API_URL is not configured.');
      return;
    }
    if (!query.trim()) {
      setError('Enter a question to search your knowledge base.');
      return;
    }
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/knowledge/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          query,
          top_k: topK,
        }),
      });

      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }

      const data: QueryResponse = await res.json();
      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setResponse(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Knowledge Inspector</h1>
        <p className="text-sm text-gray-600">
          Query your AI clone&apos;s memory with provenance-aware retrieval.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-4 rounded border p-4">
        <div className="space-y-2">
          <label className="block text-sm font-medium">User ID</label>
          <input
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            className="w-full rounded border px-3 py-2"
            placeholder="user-123"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium">Question</label>
          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-24 w-full rounded border px-3 py-2"
            placeholder="What were the key takeaways from my USC grad school slides?"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium">Top K Results</label>
          <input
            type="number"
            min={1}
            max={20}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
            className="w-24 rounded border px-3 py-2"
          />
        </div>

        <button
          type="submit"
          className="rounded bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50"
          disabled={isLoading}
        >
          {isLoading ? 'Searching...' : 'Search Knowledge'}
        </button>
      </form>

      {error && <div className="rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</div>}

      {response && (
        <section className="space-y-3">
          <div className="rounded border p-4">
            <h2 className="text-lg font-semibold">Answer</h2>
            <p className="whitespace-pre-line text-gray-800">{response.answer}</p>
          </div>

          <div className="space-y-2">
            <h3 className="text-md font-semibold">Sources</h3>
            {response.sources.length === 0 ? (
              <p className="text-sm text-gray-500">No sources returned.</p>
            ) : (
              <ul className="space-y-2">
                {response.sources.map((source) => (
                  <li key={source.id} className="rounded border p-3">
                    <div className="flex items-center justify-between text-sm text-gray-500">
                      <span>{source.data.source ?? 'Unknown source'}</span>
                      <span>score: {source.score.toFixed(3)}</span>
                    </div>
                    <p className="mt-2 text-sm text-gray-700">{source.data.text}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}
    </main>
  );
}
