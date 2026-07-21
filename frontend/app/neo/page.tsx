import type { Metadata } from 'next';
import NeoClient from './NeoClient';

export const metadata: Metadata = {
  title: 'Meet Neo | Johnnie Fields',
  description: "Talk with Neo, Johnnie Fields' AI assistant, and request a 15-minute coffee chat.",
};

export default function NeoPage() {
  return <NeoClient />;
}
