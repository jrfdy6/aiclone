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

        {loading && <p style={{ color: '#9ca3af' }}>Loading playbook...</p>}
        {error && <p style={{ color: '#f87171' }}>{error}</p>}

        {!loading && !error && summary && (
          <section style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>Playbook Principles</h2>
            <p style={{ color: '#e2e8f0', marginBottom: '8px' }}>
              <strong>Movement:</strong> {summary.movement}
            </p>
            <p style={{ color: '#e2e8f0', marginBottom: '16px' }}>
              <strong>Audience:</strong> {summary.audience}
            </p>
            <ul style={{ listStyle: 'disc', paddingLeft: '24px', color: '#9ca3af' }}>
              {summary.principles.map((principle) => (
                <li key={principle} style={{ marginBottom: '4px' }}>{principle}</li>
              ))}
            </ul>
          </section>
        )}

        {!loading && !error && (
          <section style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white' }}>Train My AI Assistant Prompt</h2>
              <button
                type="button"
                style={{ padding: '8px 16px', borderRadius: '8px', border: '1px solid #475569', backgroundColor: 'transparent', color: '#9ca3af', cursor: 'pointer' }}
                onClick={() => copyToClipboard(onboardingPrompt)}
              >
                Copy Prompt
              </button>
            </div>
            <pre style={{ overflow: 'auto', borderRadius: '8px', backgroundColor: '#0f172a', padding: '16px', fontSize: '14px', color: '#e2e8f0', whiteSpace: 'pre-wrap' }}>
              {onboardingPrompt}
            </pre>
          </section>
        )}

        {!loading && !error && prompts.length > 0 && (
          <section style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>Starter Prompts</h2>
            <p style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '16px' }}>
              Use these plug-and-play prompts to remove roadblocks, reclaim time, improve customer experience, and future-proof your skills.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              {prompts.map((prompt) => (
                <article key={prompt.id} style={{ backgroundColor: '#0f172a', borderRadius: '8px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h3 style={{ fontWeight: 600, color: 'white' }}>{prompt.title}</h3>
                    <button
                      type="button"
                      style={{ fontSize: '12px', color: '#3b82f6', background: 'none', border: 'none', cursor: 'pointer' }}
                      onClick={() => copyToClipboard(prompt.prompt)}
                    >
                      Copy
                    </button>
                  </div>
                  <p style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px' }}>{prompt.description}</p>
                  <pre style={{ overflow: 'auto', borderRadius: '4px', backgroundColor: '#1e293b', padding: '8px', fontSize: '12px', color: '#e2e8f0', whiteSpace: 'pre-wrap' }}>
                    {prompt.prompt}
                  </pre>
                </article>
              ))}
            </div>
          </section>
        )}

        <section style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>Ingest a Google Drive Folder</h2>
          <p style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '16px' }}>
            Point the system at a Drive folder to extract Docs/Slides/PDFs, chunk them, embed locally, and store them in Firestore.
          </p>
          <form onSubmit={handleIngest}>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>User ID</label>
              <input
                style={{ width: '100%', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>Google Drive Folder ID</label>
              <input
                style={{ width: '100%', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
                value={folderId}
                onChange={(event) => setFolderId(event.target.value)}
                placeholder="e.g. 1AbCdEfGhIjklmn"
              />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginBottom: '8px' }}>Max Files (optional)</label>
              <input
                type="number"
                min={1}
                style={{ width: '128px', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
                value={maxFiles}
                onChange={(event) => setMaxFiles(event.target.value === '' ? '' : Number(event.target.value))}
              />
            </div>
            <button
              type="submit"
              style={{ borderRadius: '8px', backgroundColor: '#2563eb', padding: '12px 24px', fontWeight: 500, color: 'white', border: 'none', cursor: 'pointer' }}
            >
              Ingest Folder
            </button>
          </form>
          {ingestStatus && <p style={{ marginTop: '16px', fontSize: '14px', color: '#9ca3af' }}>{ingestStatus}</p>}
        </section>
      </div>
    </main>
  );
}
