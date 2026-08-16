import { timingSafeEqual } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';
import { createSessionValue, SESSION_COOKIE, SESSION_SECONDS } from '@/lib/control-session';

export const runtime = 'nodejs';

function safeEqual(left: string, right: string) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

export async function POST(request: NextRequest) {
  const configuredPassword = process.env.CONTROL_PLANE_PASSWORD;
  const sessionSecret = process.env.CONTROL_PLANE_SESSION_SECRET;
  if (!configuredPassword || !sessionSecret) {
    return NextResponse.json({ status: 'error', message: 'Login is not configured.' }, { status: 503 });
  }
  const body = (await request.json().catch(() => ({}))) as { password?: unknown };
  const suppliedPassword = typeof body.password === 'string' ? body.password : '';
  if (!safeEqual(suppliedPassword, configuredPassword)) {
    await new Promise((resolve) => setTimeout(resolve, 750));
    return NextResponse.json({ status: 'error', message: 'Invalid password.' }, { status: 401 });
  }

  const response = NextResponse.json({ status: 'ok' });
  response.cookies.set({
    name: SESSION_COOKIE,
    value: await createSessionValue(sessionSecret),
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    path: '/',
    maxAge: SESSION_SECONDS,
  });
  return response;
}
