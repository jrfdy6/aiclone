import type { Metadata } from 'next';
import { possessivePublicName, publicOwnerDisplayName } from '@/lib/public-profile';
import NeoClient from './NeoClient';

export const metadata: Metadata = {
  title: `Meet Neo | ${publicOwnerDisplayName}`,
  description: `Talk with Neo, ${possessivePublicName()} AI assistant, and request a 15-minute coffee chat.`,
};

export default function NeoPage() {
  return <NeoClient />;
}
