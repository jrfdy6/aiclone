import { redirect } from 'next/navigation';

/** Compatibility route for the retired prompt-copy prospecting surface. */
export default function ProspectingCompatibilityPage() {
  redirect('/prospects');
}
