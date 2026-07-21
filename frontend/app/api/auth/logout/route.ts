import { NextResponse } from 'next/server';
import { SESSION_COOKIE } from '@/lib/control-session';

export async function POST() {
  const response = NextResponse.json({ status: 'ok' });
  response.cookies.set({ name: SESSION_COOKIE, value: '', path: '/', maxAge: 0 });
  return response;
}
