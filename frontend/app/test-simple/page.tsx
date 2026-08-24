import { redirect } from 'next/navigation';

/** Production health is verified by the bounded /health route and Ops. */
export default function TestSimpleCompatibilityPage() {
  redirect('/ops');
}
