import { redirect } from 'next/navigation';

/** Retired task page. Brain Briefs is the canonical source-review surface. */
export default function ResearchTasksCompatibilityPage() {
  redirect('/brain#brain-section-briefs');
}
