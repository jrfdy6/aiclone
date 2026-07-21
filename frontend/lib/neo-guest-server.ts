import { NextRequest, NextResponse } from 'next/server';

export const NEO_SESSION_COOKIE = 'neo_guest_session';
const NEO_BACKEND_TIMEOUT_MS = 15_000;

function backendUrl(path: string) {
  const base = (process.env.BACKEND_API_URL || 'https://aiclone-production-32dc.up.railway.app').replace(/\/$/, '');
  return `${base}${path}`;
}

export async function neoBackendFetch(request: NextRequest, path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  const token = request.cookies.get(NEO_SESSION_COOKIE)?.value;
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const controller = new AbortController();
  const forwardAbort = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) forwardAbort();
  else options.signal?.addEventListener('abort', forwardAbort, { once: true });
  const timeoutId = setTimeout(() => controller.abort(), NEO_BACKEND_TIMEOUT_MS);
  try {
    return await fetch(backendUrl(path), {
      ...options,
      headers,
      cache: 'no-store',
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener('abort', forwardAbort);
  }
}

export async function passThrough(upstream: Response) {
  const headers = new Headers({ 'Cache-Control': 'no-store, max-age=0' });
  const contentType = upstream.headers.get('content-type');
  if (contentType) headers.set('Content-Type', contentType);
  return new NextResponse(upstream.body, { status: upstream.status, headers });
}
