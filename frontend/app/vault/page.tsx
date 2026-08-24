import { redirect } from 'next/navigation';

/** Retired vault page. Canonical reviewed documents are exposed through Brain. */
export default function VaultCompatibilityPage() {
  redirect('/brain#brain-section-docs');
}
