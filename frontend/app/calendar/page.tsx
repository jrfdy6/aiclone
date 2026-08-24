import { redirect } from 'next/navigation';

/** Retired calendar UI. Prospect follow-up truth lives on the prospects surface. */
export default function CalendarCompatibilityPage() {
  redirect('/prospects');
}
