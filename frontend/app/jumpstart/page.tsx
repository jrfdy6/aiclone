'use client';

import { FormEvent, useState } from 'react';
import Link from 'next/link';

import NavHeader from '@/components/NavHeader';
import { apiFetch } from '@/lib/api-client';

type IngestJob = {
  id: string;
  folder_id: string;
  target_collection: 'knowledge_docs';
  status: string;
  processed: number;
  errors: string[];
};

export default function JumpstartPage() {
  const [folderId, setFolderId] = useState('');
  const [maxFiles, setMaxFiles] = useState(25);
  const [tags, setTags] = useState('');
  const [running, setRunning] = useState<'validate' | 'import' | null>(null);
  const [result, setResult] = useState<IngestJob | null>(null);
  const [state, setState] = useState<{ firestore: string; drive: string; reasons: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runIngest = async (dryRun: boolean) => {
    if (!folderId.trim()) {
      setError('Enter a Google Drive folder ID.');
      return;
    }
    setRunning(dryRun ? 'validate' : 'import');
    setError(null);
    setResult(null);
    try {
      const response = await apiFetch('/api/ingest/drive', {
        method: 'POST',
        body: JSON.stringify({
          folder_id: folderId.trim(),
          target_collection: 'knowledge_docs',
          tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean),
          max_files: maxFiles,
          dry_run: dryRun,
        }),
      });
      const payload = await response.json() as IngestJob;
      setResult(payload);
      setState({
        firestore: response.headers.get('X-AI-Clone-Firestore-State') || 'degraded',
        drive: response.headers.get('X-AI-Clone-Drive-State') || 'degraded',
        reasons: (response.headers.get('X-AI-Clone-Degraded-Reasons') || '').split(',').filter(Boolean),
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Drive knowledge import failed.');
      setState({ firestore: 'degraded', drive: 'degraded', reasons: ['drive_ingest_request_failed'] });
    } finally {
      setRunning(null);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void runIngest(false);
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '880px', margin: '0 auto', padding: '32px 24px' }}>
        <header style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Drive Knowledge Import
          </h1>
          <p style={{ color: '#cbd5e1', lineHeight: 1.6 }}>
            Read an owner-controlled Drive folder through the backend&apos;s read-only connector and refresh compact knowledge summaries in the existing <code>knowledge_docs</code> collection. Original files remain in Drive; this surface does not create arbitrary Firestore collections.
          </p>
        </header>

        <section style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '16px' }}>
              <label htmlFor="drive-folder-id" style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#cbd5e1', marginBottom: '8px' }}>
                Google Drive folder ID
              </label>
              <input
                id="drive-folder-id"
                required
                value={folderId}
                onChange={(event) => setFolderId(event.target.value)}
                placeholder="1AbCdEfGhIjklmn"
                style={{ width: '100%', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '16px', marginBottom: '20px' }}>
              <div>
                <label htmlFor="drive-max-files" style={{ display: 'block', fontSize: '14px', color: '#cbd5e1', marginBottom: '8px' }}>
                  Maximum files
                </label>
                <input
                  id="drive-max-files"
                  type="number"
                  min={1}
                  max={100}
                  value={maxFiles}
                  onChange={(event) => setMaxFiles(Number(event.target.value))}
                  style={{ width: '100%', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
                />
              </div>
              <div>
                <label htmlFor="drive-tags" style={{ display: 'block', fontSize: '14px', color: '#cbd5e1', marginBottom: '8px' }}>
                  Tags (comma separated)
                </label>
                <input
                  id="drive-tags"
                  value={tags}
                  onChange={(event) => setTags(event.target.value)}
                  placeholder="owner-curated, reference"
                  style={{ width: '100%', borderRadius: '8px', border: '1px solid #475569', backgroundColor: '#0f172a', color: 'white', padding: '12px' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="button"
                disabled={running !== null}
                onClick={() => void runIngest(true)}
                style={{ padding: '12px 18px', borderRadius: '8px', border: '1px solid #64748b', backgroundColor: '#334155', color: 'white', cursor: running ? 'not-allowed' : 'pointer' }}
              >
                {running === 'validate' ? 'Validating…' : 'Validate folder'}
              </button>
              <button
                type="submit"
                disabled={running !== null}
                style={{ padding: '12px 18px', borderRadius: '8px', border: 'none', backgroundColor: '#2563eb', color: 'white', fontWeight: 600, cursor: running ? 'not-allowed' : 'pointer' }}
              >
                {running === 'import' ? 'Importing…' : 'Import summaries'}
              </button>
            </div>
          </form>
        </section>

        {error && (
          <aside role="alert" style={{ marginTop: '20px', padding: '16px', borderRadius: '8px', border: '1px solid #ef4444', color: '#fca5a5', backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
            {error}
          </aside>
        )}

        {result && state && (
          <aside role="status" style={{ marginTop: '20px', padding: '16px', borderRadius: '8px', border: `1px solid ${state.firestore === 'ready' || state.firestore === 'not_written' ? '#22c55e' : '#f59e0b'}`, color: '#e2e8f0', backgroundColor: '#1e293b' }}>
            <strong>{result.status}</strong>: {result.processed} file{result.processed === 1 ? '' : 's'} {result.status === 'dry_run' ? 'found' : 'projected'}.
            <span style={{ display: 'block', marginTop: '6px', fontSize: '13px', color: '#94a3b8' }}>
              Drive: {state.drive}; Firestore: {state.firestore}
              {state.reasons.length > 0 ? `; ${state.reasons.join(', ')}` : ''}
            </span>
          </aside>
        )}

        <p style={{ marginTop: '24px' }}>
          <Link href="/knowledge" style={{ color: '#60a5fa' }}>View knowledge →</Link>
        </p>
      </div>
    </main>
  );
}
