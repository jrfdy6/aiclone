import { redirect } from 'next/navigation';

/** Retired dashboard page. Ops is the canonical health and readiness surface. */
export default function DashboardCompatibilityPage() {
  redirect('/ops');
}
