import { redirect } from 'next/navigation';

/** Brain Docs is the authenticated canonical knowledge-review surface. */
export default function KnowledgeBaseCompatibilityPage() {
  redirect('/brain#brain-section-docs');
}
