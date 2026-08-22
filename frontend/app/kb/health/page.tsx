import type { Metadata } from 'next';

import { fetchResearchLibrary } from '@/lib/research-backend';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export const metadata: Metadata = {
  title: 'Knowledge Research Health',
  robots: { index: false, follow: false },
};

export default async function KbHealthPage() {
  const library = await fetchResearchLibrary();
  const ready = library.state === 'ready';

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', maxWidth: '760px', margin: '0 auto', padding: '40px 24px' }}>
      <h1>Knowledge Research Health</h1>
      <p role="status" style={{ color: ready ? '#166534' : '#92400e' }}>
        {ready
          ? 'The authenticated backend verified both topic-intelligence and prospect-discovery reads.'
          : 'Research dependencies are degraded. The interface is not treating unavailable data as an empty library.'}
      </p>
      <dl>
        <dt>Backend data state</dt>
        <dd>{library.state}</dd>
        <dt>Verified topic rows</dt>
        <dd>{library.topics.length}</dd>
        <dt>Verified discovery rows</dt>
        <dd>{library.discoveries.length}</dd>
        <dt>Reason codes</dt>
        <dd>{library.reasonCodes.join(', ') || 'none'}</dd>
      </dl>
    </main>
  );
}
