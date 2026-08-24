import { redirect } from 'next/navigation';

/** Retired playbook page. Ops is the canonical operating surface. */
export default function PlaybooksCompatibilityPage() {
  redirect('/ops');
}
