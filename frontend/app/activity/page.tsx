import { redirect } from 'next/navigation';

/** Retired activity page. Ops is the canonical runtime-status surface. */
export default function ActivityCompatibilityPage() {
  redirect('/ops');
}
