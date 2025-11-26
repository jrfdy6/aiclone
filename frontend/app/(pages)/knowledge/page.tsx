'use client';

import { useState } from 'react';
import NavHeader from '@/components/NavHeader';

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
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '800px', margin: '0 auto', padding: '24px' }}>
        <header style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>Knowledge Inspector</h1>
          <p style={{ color: '#9ca3af' }}>
            Query your AI clone&apos;s memory with provenance-aware retrieval.
          </p>
        </header>

        <form onSubmit={handleSubmit} style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px', marginBottom: '24px' }}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>User ID</label>
            <input
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              style={{ width: '100%', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
              placeholder="user-123"
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>Question</label>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              style={{ width: '100%', height: '96px', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
              placeholder="What were the key takeaways from my USC grad school slides?"
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>Top K Results</label>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
              style={{ width: '96px', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
            />
          </div>

          <button
            type="submit"
            style={{ borderRadius: '8px', backgroundColor: '#2563eb', padding: '12px 24px', fontWeight: 500, color: 'white', border: 'none', cursor: 'pointer', opacity: isLoading ? 0.5 : 1 }}
            disabled={isLoading}
          >
            {isLoading ? 'Searching...' : 'Search Knowledge'}
          </button>
        </form>

        {error && <div style={{ borderRadius: '8px', border: '1px solid #ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '12px', color: '#f87171', marginBottom: '24px' }}>{error}</div>}

        {response && (
          <section>
            <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '12px' }}>Answer</h2>
              <p style={{ whiteSpace: 'pre-line', color: '#e2e8f0' }}>{response.answer}</p>
            </div>

            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'white', marginBottom: '12px' }}>Sources</h3>
              {response.sources.length === 0 ? (
                <p style={{ fontSize: '14px', color: '#6b7280' }}>No sources returned.</p>
              ) : (
                <ul style={{ display: 'flex', flexDirection: 'column', gap: '12px', listStyle: 'none', padding: 0, margin: 0 }}>
                  {response.sources.map((source) => (
                    <li key={source.id} style={{ backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #475569', padding: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#6b7280', marginBottom: '8px' }}>
                        <span>{source.data.source ?? 'Unknown source'}</span>
                        <span>score: {source.score.toFixed(3)}</span>
                      </div>
                      <p style={{ fontSize: '14px', color: '#9ca3af', margin: 0 }}>{source.data.text}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
