import { NextRequest, NextResponse } from 'next/server';
import { NEO_SESSION_COOKIE, neoBackendFetch } from '@/lib/neo-guest-server';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  const body = await request.text();
  const upstream = await neoBackendFetch(request, '/api/neo/guest/access', { method: 'POST', body });
  const payload = await upstream.json().catch(() => ({ detail: 'Unable to validate invite.' }));
  if (!upstream.ok) return NextResponse.json(payload, { status: upstream.status });
  const token = String(payload.session_token || '');
  if (!token) return NextResponse.json({ detail: 'Guest session was not created.' }, { status: 502 });
  const response = NextResponse.json({ status: 'ready', invite_label: payload.invite_label });
  response.cookies.set(NEO_SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/api/neo',
    maxAge: 60 * 60 * 24 * 30,
  });
  response.headers.set('Cache-Control', 'no-store, max-age=0');
  return response;
}
