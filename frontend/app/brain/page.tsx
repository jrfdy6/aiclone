import fs from 'fs';
import path from 'path';
import BrainClient, { DocEntry, TranscriptEntry } from './BrainClient';

export default function BrainPage() {
  const transcripts = loadTranscripts();
  const docs = loadDocs();
  return <BrainClient transcripts={transcripts} docs={docs} />;
}

function loadTranscripts(): TranscriptEntry[] {
  try {
    const indexPath = path.join(process.cwd(), 'knowledge/aiclone/transcripts/INDEX.md');
    if (!fs.existsSync(indexPath)) return [];
    const lines = fs
      .readFileSync(indexPath, 'utf-8')
      .split('\n')
      .filter((line) => line.trim().startsWith('|') && line.includes('|'));
    return lines
      .slice(2)
      .map((line) => {
        const parts = line.split('|').map((p) => p.trim());
        if (parts.length < 6) return null;
        const date = parts[1];
        const title = parts[2];
        const tags = parts[3] ? parts[3].split(',').map((tag) => tag.trim()).filter(Boolean) : [];
        const summary = parts[4];
        const linkMatch = parts[5].match(/\((.*)\)/);
        const link = linkMatch ? linkMatch[1] : '';
        if (!date || !title) return null;
        return { date, title, tags, summary, link } satisfies TranscriptEntry;
      })
      .filter((entry): entry is TranscriptEntry => Boolean(entry));
  } catch (err) {
    console.warn('Failed to load transcript index', err);
    return [];
  }
}

function loadDocs(): DocEntry[] {
  const baseDir = path.join(process.cwd(), 'knowledge/aiclone');
  if (!fs.existsSync(baseDir)) return [];
  return fs
    .readdirSync(baseDir)
    .filter((file) => file.endsWith('.md') && file !== 'README.md')
    .slice(0, 8)
    .map((file) => {
      const fullPath = path.join(baseDir, file);
      const raw = fs.readFileSync(fullPath, 'utf-8');
      const snippet = raw.split('\n').find((line) => line.trim().length > 0) ?? '';
      return {
        name: file.replace('.md', ''),
        path: `knowledge/aiclone/${file}`,
        snippet,
      } satisfies DocEntry;
    });
}
