import { redirect } from 'next/navigation';

/** Production does not expose an interactive upstream-API debug console. */
export default function ApiTestCompatibilityPage() {
  redirect('/ops');
}
