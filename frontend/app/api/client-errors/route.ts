import { NextRequest, NextResponse } from 'next/server';
import { getRuntimeReleaseInfo } from '@/lib/runtime-release';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const KINDS = new Set(['window_error', 'unhandled_rejection', 'route_error']);
const REASON_CODES = new Set(['window_error', 'unhandled_rejection', 'route_render_error']);
const SAFE_TOKEN_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const STATIC_ROUTES = new Set(['/', '/brain', '/inbox', '/login', '/neo', '/ops', '/prospect-discovery', '/prospects', '/workspace', '/workspace/posting']);
const DYNAMIC_ROUTE_TEMPLATES = new Set(['/inbox/:id', '/outreach/:id', '/prospects/:id']);

function safeToken(value: unknown, fallback: string, maxLength = 80) {
  if (typeof value !== 'string') return fallback;
  const normalized = value.trim();
  return normalized.length <= maxLength && SAFE_TOKEN_PATTERN.test(normalized) ? normalized : fallback;
}

function safeNullableToken(value: unknown, maxLength = 80) {
  const normalized = safeToken(value, '', maxLength);
  return normalized || null;
}

function safeRoute(value: unknown) {
  if (typeof value !== 'string') return '/:route';
  const normalized = value.trim();
  return STATIC_ROUTES.has(normalized) || DYNAMIC_ROUTE_TEMPLATES.has(normalized) ? normalized : '/:route';
}

function safePosition(value: unknown) {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= 10_000_000
    ? value
    : null;
}

function sanitizePayload(payload: Record<string, unknown>) {
  const kind = typeof payload.kind === 'string' && KINDS.has(payload.kind) ? payload.kind : 'unknown';
  const requestedReasonCode = safeToken(payload.reasonCode, kind, 80).toLowerCase();
  return {
    kind,
    reasonCode: REASON_CODES.has(requestedReasonCode) ? requestedReasonCode : kind,
    digest: safeNullableToken(payload.digest, 128),
    route: safeRoute(payload.route),
    release: safeNullableToken(payload.release),
    environment: safeNullableToken(payload.environment),
    service: safeNullableToken(payload.service),
    line: safePosition(payload.line),
    column: safePosition(payload.column),
    capturedAt: new Date().toISOString(),
  };
}

async function readBoundedJson(request: NextRequest, maxBytes = 8_192) {
  if (!request.body) return { payload: null, tooLarge: false };
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let totalBytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalBytes += value.byteLength;
      if (totalBytes > maxBytes) {
        await reader.cancel();
        return { payload: null, tooLarge: true };
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return { payload: JSON.parse(new TextDecoder().decode(body)) as unknown, tooLarge: false };
  } catch {
    return { payload: null, tooLarge: false };
  }
}

export async function POST(request: NextRequest) {
  const contentLength = Number(request.headers.get('content-length') ?? '0');
  if (Number.isFinite(contentLength) && contentLength > 8_192) {
    return NextResponse.json({ ok: false, error: 'payload_too_large' }, { status: 413 });
  }

  const bounded = await readBoundedJson(request);
  if (bounded.tooLarge) {
    return NextResponse.json({ ok: false, error: 'payload_too_large' }, { status: 413 });
  }
  const payload = bounded.payload as Record<string, unknown> | null;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return NextResponse.json({ ok: false, error: 'invalid_payload' }, { status: 400 });
  }

  const runtimeInfo = getRuntimeReleaseInfo();
  console.error('[client-error]', JSON.stringify({
    receivedAt: new Date().toISOString(),
    serverService: runtimeInfo.service,
    serverRelease: runtimeInfo.release,
    serverEnvironment: runtimeInfo.environment,
    report: sanitizePayload(payload),
  }));

  return NextResponse.json({ ok: true });
}
