import type { Metadata } from 'next';
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
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
