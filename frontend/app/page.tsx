'use client';

import Link from 'next/link';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import NavHeader from '@/components/NavHeader';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/ops');
  }, [router]);

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div className="flex items-center justify-center px-6 py-20 text-center text-white">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-sky-300">Runtime Control</p>
          <h1 className="mt-2 text-3xl font-semibold">Ops is the homepage.</h1>
          <p className="mt-3 text-sm text-slate-300">
            Brain, Lab, and Workspaces all route through the runtime shell now. If you are not redirected automatically,{' '}
            <Link href="/ops" className="text-fuchsia-300 underline">
              click here
            </Link>.
          </p>
        </div>
      </div>
    </main>
  );
}
