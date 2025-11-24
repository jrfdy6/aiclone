'use client';

import { useMemo, useState } from 'react';
import ChatInput from '../components/ChatInput';
import ChatMessages from '../components/ChatMessages';

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

const API_URL = process.env.NEXT_PUBLIC_API_URL;

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

  const hasResults = useMemo(() => results.length > 0, [results.length]);

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
        content: `Returned ${data.results.length} chunk(s) for "${trimmed}".`,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error sending message.');
    } finally {
      setIsSending(false);
    }
  };

  return (
    <main className="space-y-6 p-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">AI Clone</h1>
        <p className="text-sm text-gray-600">Conversational interface wired into your Firestore-backed memory.</p>
      </header>

      <div className="space-y-4 rounded border p-4">
        <label className="block text-sm font-medium">User ID</label>
        <input
          value={userId}
          onChange={(event) => setUserId(event.target.value)}
          className="w-full rounded border px-3 py-2"
          placeholder="dev-user"
        />
      </div>

      <div className="space-y-4">
        {error && (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <ChatMessages messages={messages} />
        <ChatInput onSend={handleSend} />
      </div>

      {hasResults && (
        <section className="space-y-3 rounded border p-4">
          <h2 className="text-lg font-semibold">Retrieved Context</h2>
          <ul className="space-y-2 text-sm text-gray-700">
            {results.map((result) => (
              <li key={`${result.source_id}-${result.chunk_index}`} className="rounded border p-3">
                <div className="flex items-center justify-between text-xs uppercase tracking-wide text-gray-500">
                  <span>{String(result.metadata?.file_name ?? result.source_id)}</span>
                  <span>score: {result.similarity_score.toFixed(3)}</span>
                </div>
                <p className="mt-2 whitespace-pre-line">{result.chunk}</p>
                {result.metadata && (
                  <pre className="mt-2 overflow-x-auto rounded bg-gray-50 p-2 text-[11px] text-gray-600">
            {JSON.stringify(result.metadata, null, 2)}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
