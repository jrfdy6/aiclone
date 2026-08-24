import { redirect } from 'next/navigation';

/** Retired direct-backend query route; it must not bypass the control proxy. */
export default function KnowledgeQueryCompatibilityPage() {
  redirect('/brain#brain-section-docs');
}
