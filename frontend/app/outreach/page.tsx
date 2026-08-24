import { redirect } from 'next/navigation';

/** Retired outreach page. Prospect work remains owner-controlled in Prospects. */
export default function OutreachCompatibilityPage() {
  redirect('/prospects');
}
