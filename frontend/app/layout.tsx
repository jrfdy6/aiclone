import type { Metadata } from 'next';
import { Suspense } from 'react';
import ClientErrorReporter from '@/components/runtime/ClientErrorReporter';
import { getRuntimeReleaseInfo } from '@/lib/runtime-release';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Clone',
  description: 'Find prospects, generate personalized outreach, and manage your pipeline — all in one place.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const runtime = getRuntimeReleaseInfo();

  return (
    <html lang="en">
      <body>
        <Suspense fallback={null}>
          <ClientErrorReporter release={runtime.release} environment={runtime.environment} service={runtime.service} />
        </Suspense>
        {children}
      </body>
    </html>
  );
}
