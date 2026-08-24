import { redirect } from 'next/navigation';

/** Retired detail route. It never sends outreach or represents delivery. */
export default function OutreachDetailCompatibilityPage() {
  redirect('/prospects');
}
