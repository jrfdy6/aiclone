import { NextRequest, NextResponse } from 'next/server';
import { getRuntimeReleaseInfo } from '@/lib/runtime-release';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type ClientErrorPayload = {
  kind?: string;
  message?: string;
  stack?: string | null;
  digest?: string | null;
  route?: string | null;
  href?: string | null;
  userAgent?: string | null;
  release?: string | null;
  environment?: string | null;
  detail?: Record<string, unknown> | null;
  capturedAt?: string | null;
};

function trimText(value: unknown, maxLength: number) {
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  return normalized.slice(0, maxLength);
}

function sanitizePayload(payload: ClientErrorPayload) {
  return {
    kind: trimText(payload.kind, 64) ?? 'unknown',
    message: trimText(payload.message, 2000) ?? 'Unknown client error',
    stack: trimText(payload.stack ?? null, 6000),
    digest: trimText(payload.digest ?? null, 256),
    route: trimText(payload.route ?? null, 1024),
    href: trimText(payload.href ?? null, 2048),
    userAgent: trimText(payload.userAgent ?? null, 1024),
    release: trimText(payload.release ?? null, 256),
    environment: trimText(payload.environment ?? null, 128),
    capturedAt: trimText(payload.capturedAt ?? null, 128),
    detail: payload.detail && typeof payload.detail === 'object' ? payload.detail : null,
  };
}

export async function POST(request: NextRequest) {
  const payload = (await request.json().catch(() => null)) as ClientErrorPayload | null;
  if (!payload || typeof payload !== 'object') {
    return NextResponse.json({ ok: false, error: 'invalid_payload' }, { status: 400 });
  }

  const runtime = getRuntimeReleaseInfo();
  const report = sanitizePayload(payload);
  const serverContext = {
    receivedAt: new Date().toISOString(),
    service: runtime.service,
    serverRelease: runtime.release,
    serverEnvironment: runtime.environment,
    requestId: request.headers.get('x-railway-request-id'),
    forwardedFor: request.headers.get('x-forwarded-for'),
  };

  console.error('[client-error]', JSON.stringify({ ...serverContext, report }));

  return NextResponse.json({ ok: true });
}
