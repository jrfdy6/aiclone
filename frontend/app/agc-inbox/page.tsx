import { redirect } from 'next/navigation';

export default function AgcInboxPage() {
  redirect('/inbox?workspace=agc');
}
