'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type PlaybookSummary = {
  movement: string;
  audience: string;
  principles: string[];
};

type StarterPrompt = {
  id: string;
  title: string;
  description: string;
  prompt: string;
};

type IngestResponse = {
  success: boolean;
  message: string;
  files_ingested?: number;
  chunks_created?: number;
  ingest_job_id?: string;
};

export default function JumpstartPage() {
  const [summary, setSummary] = useState<PlaybookSummary | null>(null);
  const [onboardingPrompt, setOnboardingPrompt] = useState<string>('');
  const [prompts, setPrompts] = useState<StarterPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [userId, setUserId] = useState('dev-user');
  const [folderId, setFolderId] = useState('');
  const [maxFiles, setMaxFiles] = useState<number | ''>('');
  const [ingestStatus, setIngestStatus] = useState<string>('');

  useEffect(() => {
    async function fetchPlaybook() {
      try {
        if (!API_URL) {
          setError('NEXT_PUBLIC_API_URL is not configured.');
          return;
        }
        const [summaryRes, onboardingRes, promptsRes] = await Promise.all([
          fetch(`${API_URL}/api/playbook/summary`),
          fetch(`${API_URL}/api/playbook/onboarding`),
          fetch(`${API_URL}/api/playbook/prompts`),
        ]);

        if (!summaryRes.ok || !onboardingRes.ok || !promptsRes.ok) {
          throw new Error('Could not load playbook data.');
        }

        const summaryData = await summaryRes.json();
        const onboardingData = await onboardingRes.json();
        const promptsData = await promptsRes.json();

        setSummary(summaryData);
        setOnboardingPrompt(onboardingData.prompt);
        setPrompts(promptsData.prompts ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load playbook.');
      } finally {
        setLoading(false);
      }
    }

    fetchPlaybook();
  }, []);

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setIngestStatus('Copied to clipboard!');
      setTimeout(() => setIngestStatus(''), 2000);
    } catch (err) {
      setIngestStatus('Unable to copy.');
      setTimeout(() => setIngestStatus(''), 2000);
    }
  };

  const handleIngest = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!API_URL) {
      setError('NEXT_PUBLIC_API_URL is not configured.');
      return;
    }
    if (!folderId.trim()) {
      setIngestStatus('Enter a Google Drive folder ID.');
      return;
    }

    setIngestStatus('Submitting ingestion request...');
    try {
      const response = await fetch(`${API_URL}/api/ingest_drive`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          folder_id: folderId,
          max_files: maxFiles === '' ? undefined : maxFiles,
        }),
      });

      if (!response.ok) {
        throw new Error(`Ingest request failed with status ${response.status}`);
      }

      const data: IngestResponse = await response.json();
      setIngestStatus(data.message || 'Ingestion completed.');
    } catch (err) {
      setIngestStatus(err instanceof Error ? err.message : 'Unexpected error running ingestion.');
    }
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        <header style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>AI Jumpstart Playbook</h1>
          <p style={{ color: '#9ca3af' }}>
            Ground your AI clone in Tony Robbins & Dean Graziosi's human-first system: choose a tool, train it, start with a high-impact prompt, and iterate for quick wins.
          </p>
        </header>

      {loading && <p>Loading playbook...</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && !error && summary && (
        <section className="space-y-3 rounded border p-4">
          <h2 className="text-2xl font-semibold">Playbook Principles</h2>
          <p>
            <strong>Movement:</strong> {summary.movement}
          </p>
          <p>
            <strong>Audience:</strong> {summary.audience}
          </p>
          <ul className="list-disc space-y-1 pl-6 text-sm text-gray-700">
            {summary.principles.map((principle) => (
              <li key={principle}>{principle}</li>
            ))}
          </ul>
        </section>
      )}

      {!loading && !error && (
        <section className="space-y-3 rounded border p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Train My AI Assistant Prompt</h2>
            <button
              type="button"
              className="rounded border px-3 py-1 text-sm"
              onClick={() => copyToClipboard(onboardingPrompt)}
            >
              Copy Prompt
            </button>
          </div>
          <pre className="overflow-x-auto rounded bg-gray-50 p-3 text-sm text-gray-800">
            {onboardingPrompt}
          </pre>
        </section>
      )}

      {!loading && !error && prompts.length > 0 && (
        <section className="space-y-4 rounded border p-4">
          <h2 className="text-2xl font-semibold">Starter Prompts</h2>
          <p className="text-sm text-gray-600">
            Use these plug-and-play prompts to remove roadblocks, reclaim time, improve customer experience, and future-proof your skills.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            {prompts.map((prompt) => (
              <article key={prompt.id} className="space-y-2 rounded border p-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">{prompt.title}</h3>
                  <button
                    type="button"
                    className="text-xs text-blue-600"
                    onClick={() => copyToClipboard(prompt.prompt)}
                  >
                    Copy
                  </button>
                </div>
                <p className="text-sm text-gray-600">{prompt.description}</p>
                <pre className="overflow-x-auto rounded bg-gray-50 p-2 text-xs text-gray-800">
                  {prompt.prompt}
                </pre>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-4 rounded border p-4">
        <h2 className="text-2xl font-semibold">Ingest a Google Drive Folder</h2>
        <p className="text-sm text-gray-600">
          Point the system at a Drive folder to extract Docs/Slides/PDFs, chunk them, embed locally, and store them in Firestore.
        </p>
        <form onSubmit={handleIngest} className="space-y-4">
          <div>
            <label className="block text-sm font-medium">User ID</label>
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium">Google Drive Folder ID</label>
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={folderId}
              onChange={(event) => setFolderId(event.target.value)}
              placeholder="e.g. 1AbCdEfGhIjklmn"
            />
          </div>
          <div>
            <label className="block text-sm font-medium">Max Files (optional)</label>
            <input
              type="number"
              min={1}
              className="mt-1 w-32 rounded border px-3 py-2"
              value={maxFiles}
              onChange={(event) => setMaxFiles(event.target.value === '' ? '' : Number(event.target.value))}
            />
          </div>
          <button
            type="submit"
            className="rounded bg-blue-600 px-4 py-2 font-medium text-white"
          >
            Ingest Folder
          </button>
        </form>
        {ingestStatus && <p className="text-sm text-gray-700">{ingestStatus}</p>}
      </section>
    </main>
  );
}
