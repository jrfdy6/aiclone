'use client';

import Link from 'next/link';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { controlApiGet, controlApiPatch, controlApiPost } from '@/lib/control-api';

type Invite = { id: string; label: string; status: string; expires_at?: string; created_at: string; session_count: number };
type Meeting = { id: string; visitor_name: string; visitor_email: string; visitor_phone: string; purpose: string; preferred_times: string[]; timezone: string; status: string; created_at: string; owner_notes?: string };
type Conversation = { id: string; visitor_name?: string; visitor_email?: string; invite_label: string; message_count: number; last_seen_at: string };
type Inbox = { meeting_requests: Meeting[]; conversations: Conversation[] };

const panel = { border: '1px solid rgba(148,163,184,.16)', background: '#071121', borderRadius: '18px', padding: '18px' } as const;
const input = { background: '#0a1727', color: 'white', border: '1px solid #314158', borderRadius: '10px', padding: '11px 12px' } as const;
const button = { background: '#fbbf24', color: '#241800', border: 0, borderRadius: '10px', padding: '11px 14px', fontWeight: 800, cursor: 'pointer' } as const;

export default function NeoInboxPage() {
  const [inbox, setInbox] = useState<Inbox>({ meeting_requests: [], conversations: [] });
  const [invites, setInvites] = useState<Invite[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const [nextInbox, nextInvites] = await Promise.all([
        controlApiGet<Inbox>('/api/neo/operator/inbox'),
        controlApiGet<{ items: Invite[] }>('/api/neo/operator/invites'),
      ]);
      setInbox(nextInbox); setInvites(nextInvites.items); setError('');
    } catch (issue) { setError(issue instanceof Error ? issue.message : 'Unable to load Neo Inbox.'); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function createInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true); setError(''); const form = new FormData(formElement);
    try {
      await controlApiPost('/api/neo/operator/invites', { label: form.get('label'), passcode: form.get('passcode'), expires_at: null });
      formElement.reset(); await load();
    } catch (issue) { setError(issue instanceof Error ? issue.message : 'Invite could not be created.'); }
    finally { setBusy(false); }
  }
  async function revoke(id: string) { if (!window.confirm('Revoke this invite and all active sessions created by it?')) return; setBusy(true); try { await controlApiPost(`/api/neo/operator/invites/${id}/revoke`, {}); await load(); } finally { setBusy(false); } }
  async function decide(id: string, status: 'approved' | 'declined') { setBusy(true); try { await controlApiPatch(`/api/neo/operator/meeting-requests/${id}`, { status, owner_notes: null }); await load(); } finally { setBusy(false); } }

  const tabs = [{ key: 'neo-inbox', label: 'Neo Guest Inbox', active: true, onSelect: () => undefined }];
  return <RuntimePage module="ops" tabs={tabs} maxWidth="1180px"><div style={{ display: 'grid', gap: '18px' }}>
    <header><p style={{ color: '#fbbf24', letterSpacing: '.18em', fontSize: '11px', textTransform: 'uppercase', margin: 0 }}>Guest conversations</p><h1 style={{ fontSize: '30px', margin: '7px 0', color: 'white' }}>Neo Inbox</h1><p style={{ color: '#94a3b8', margin: 0 }}>Review coffee-chat requests, guest activity, and invite access. Approval does not create a calendar event yet.</p><p><Link href="/inbox" style={{ color: '#93c5fd' }}>Back to portfolio email inbox</Link> · <Link href="/neo" style={{ color: '#93c5fd' }}>Open guest experience</Link></p></header>
    {error && <p style={{ color: '#fca5a5', background: '#3b1118', padding: '12px', borderRadius: '12px' }}>{error}</p>}
    <section style={panel}><h2 style={{ marginTop: 0 }}>Meeting requests</h2>{inbox.meeting_requests.length === 0 ? <p style={{ color: '#94a3b8' }}>No meeting requests yet.</p> : <div style={{ display: 'grid', gap: '12px' }}>{inbox.meeting_requests.map((item) => <article key={item.id} style={{ border: '1px solid #26364a', borderRadius: '14px', padding: '15px' }}><div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}><strong>{item.visitor_name}</strong><span style={{ color: item.status === 'pending' ? '#fde68a' : '#94a3b8' }}>{item.status}</span></div><p style={{ color: '#cbd5e1' }}>{item.purpose}</p><p style={{ color: '#94a3b8', fontSize: '13px' }}>{item.visitor_email} · {item.visitor_phone}<br />{item.preferred_times.join('; ')} ({item.timezone})</p>{item.status === 'pending' && <div style={{ display: 'flex', gap: '8px' }}><button disabled={busy} style={button} onClick={() => void decide(item.id, 'approved')}>Approve</button><button disabled={busy} style={{ ...button, background: '#334155', color: 'white' }} onClick={() => void decide(item.id, 'declined')}>Decline</button></div>}</article>)}</div>}</section>
    <section style={panel}><h2 style={{ marginTop: 0 }}>Invite access</h2><p style={{ color: '#94a3b8' }}>Passcodes are stored only as one-way digests. Use a unique code per visitor; revoke it here at any time.</p><form onSubmit={createInvite} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '10px' }}><input name="label" style={input} placeholder="Test invite or visitor name" required /><input name="passcode" style={input} type="password" minLength={10} placeholder="Unique passcode" required /><button disabled={busy} style={button}>Create invite</button></form><div style={{ marginTop: '14px', display: 'grid', gap: '8px' }}>{invites.map((item) => <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #1d2b3d', paddingTop: '10px' }}><span><strong>{item.label}</strong> <small style={{ color: '#94a3b8' }}>· {item.session_count} session(s) · {item.status}</small></span>{item.status === 'active' && <button disabled={busy} onClick={() => void revoke(item.id)} style={{ background: 'transparent', color: '#fca5a5', border: 0, cursor: 'pointer' }}>Revoke</button>}</div>)}</div></section>
    <section style={panel}><h2 style={{ marginTop: 0 }}>Recent conversations</h2>{inbox.conversations.length === 0 ? <p style={{ color: '#94a3b8' }}>No guest conversations yet.</p> : inbox.conversations.map((item) => <div key={item.id} style={{ borderTop: '1px solid #1d2b3d', padding: '11px 0' }}><strong>{item.visitor_name || 'Unidentified visitor'}</strong><p style={{ color: '#94a3b8', margin: '4px 0', fontSize: '13px' }}>{item.invite_label} · {item.message_count} messages · last active {new Date(item.last_seen_at).toLocaleString()}</p></div>)}</section>
  </div></RuntimePage>;
}
