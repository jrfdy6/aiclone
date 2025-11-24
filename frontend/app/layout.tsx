import './globals.css';
import type { Metadata } from 'next';
import React from 'react';
import Notifications from '../components/Notifications';
import { CommandPaletteProvider } from '../components/CommandPaletteProvider';

export const metadata: Metadata = {
  title: 'AI Clone',
  description: 'AI Clone frontend scaffold',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <CommandPaletteProvider>
          <div className="fixed top-4 right-4 z-50">
            <Notifications />
          </div>
          {children}
        </CommandPaletteProvider>
      </body>
    </html>
  );
}
