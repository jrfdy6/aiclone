import './globals.css';
import type { Metadata } from 'next';
import React from 'react';
import { Providers } from './providers';
import Navigation from '@/components/Navigation';

export const metadata: Metadata = {
  title: 'AI Clone',
  description: 'AI Clone frontend scaffold',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <Navigation />
          {children}
        </Providers>
      </body>
    </html>
  );
}
