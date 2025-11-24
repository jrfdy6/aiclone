'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function OutreachPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to prospecting page (outreach functionality is there)
    router.replace('/prospecting');
  }, [router]);

  return null;
}

