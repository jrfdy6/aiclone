import { redirect } from 'next/navigation';

/** Retired template page. The canonical writer lives in Workspace. */
export default function TemplatesCompatibilityPage() {
  redirect('/workspace');
}
