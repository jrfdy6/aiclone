import { NextRequest, NextResponse } from 'next/server';

import { isSupportedControlProxyRequest } from '@/lib/control-proxy';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const HOP_BY_HOP = new Set([
  'connection',
  'content-length',
  'content-encoding',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);
const MAX_BACKEND_REDIRECTS = 3;

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const backend = (process.env.BACKEND_API_URL || 'https://aiclone-production-32dc.up.railway.app').replace(/\/$/, '');
  const token = process.env.CONTROL_PLANE_SERVICE_TOKEN;
  if (!token) {
    return NextResponse.json({ status: 'error', message: 'Control plane is not configured.' }, { status: 503 });
  }
  const { path: pathSegments } = await context.params;
  const path = pathSegments.join('/');
  if (!isSupportedControlProxyRequest(path, request.method)) {
    return NextResponse.json({ status: 'error', message: 'Unsupported proxy path.' }, { status: 400 });
  }
  const target = new URL(`${backend}/${path}`);
  request.nextUrl.searchParams.forEach((value, key) => target.searchParams.append(key, value));

  const headers = new Headers(request.headers);
  HOP_BY_HOP.forEach((name) => headers.delete(name));
  headers.delete('cookie');
  headers.set('Authorization', `Bearer ${token}`);
  headers.set('Accept', headers.get('Accept') || 'application/json');

  let method = request.method;
  let body: ArrayBuffer | undefined = !['GET', 'HEAD'].includes(method) ? await request.arrayBuffer() : undefined;
  let currentTarget = target;
  let upstream: Response | undefined;

  for (let attempt = 0; attempt <= MAX_BACKEND_REDIRECTS; attempt += 1) {
    upstream = await fetch(currentTarget, {
      method,
      headers,
      body,
      cache: 'no-store',
      redirect: 'manual',
    });
    if (!REDIRECT_STATUSES.has(upstream.status)) {
      break;
    }
    const location = upstream.headers.get('location');
    if (!location || attempt === MAX_BACKEND_REDIRECTS) {
      return NextResponse.json({ status: 'error', message: 'Backend redirect could not be resolved.' }, { status: 502 });
    }
    const nextTarget = new URL(location, currentTarget);
    const sameBackendHost = nextTarget.hostname === target.hostname && nextTarget.port === target.port;
    const railwayProxyUpgrade = sameBackendHost && nextTarget.protocol === 'http:' && target.protocol === 'https:';
    if (!sameBackendHost || (nextTarget.protocol !== target.protocol && !railwayProxyUpgrade)) {
      return NextResponse.json({ status: 'error', message: 'Backend redirect was rejected.' }, { status: 502 });
    }
    if (railwayProxyUpgrade) {
      nextTarget.protocol = 'https:';
    }
    if (upstream.status === 303 || ((upstream.status === 301 || upstream.status === 302) && method === 'POST')) {
      method = 'GET';
      body = undefined;
      headers.delete('content-type');
    }
    currentTarget = nextTarget;
  }

  if (!upstream) {
    return NextResponse.json({ status: 'error', message: 'Backend request failed.' }, { status: 502 });
  }
  const responseHeaders = new Headers(upstream.headers);
  HOP_BY_HOP.forEach((name) => responseHeaders.delete(name));
  responseHeaders.set('Cache-Control', 'no-store, max-age=0');
  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
