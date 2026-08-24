'use client';

export type ClientErrorKind = 'window_error' | 'unhandled_rejection' | 'route_error';

export type ClientErrorReport = {
  kind: ClientErrorKind;
  reasonCode: string;
  digest?: string | null;
  route?: string | null;
  release?: string | null;
  environment?: string | null;
  service?: string | null;
  line?: number | null;
  column?: number | null;
  capturedAt: string;
};

type ClientErrorReportInput = Omit<ClientErrorReport, 'capturedAt' | 'service'> & {
  service?: string | null;
};

const SAFE_TOKEN_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const recentReportKeys = new Map<string, number>();
const MAX_RECENT_REPORTS = 50;
const RECENT_REPORT_TTL_MS = 60_000;
const KNOWN_STATIC_ROUTES = new Set([
  '/',
  '/brain',
  '/inbox',
  '/login',
  '/neo',
  '/ops',
  '/prospect-discovery',
  '/prospects',
  '/workspace',
  '/workspace/posting',
]);

function safeToken(value: unknown, fallback: string, maxLength = 80) {
  if (typeof value !== 'string') return fallback;
  const normalized = value.trim();
  return normalized.length <= maxLength && SAFE_TOKEN_PATTERN.test(normalized) ? normalized : fallback;
}

function safePosition(value: unknown) {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= 10_000_000
    ? value
    : null;
}

function safeDigest(value: unknown) {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized.length <= 128 && SAFE_TOKEN_PATTERN.test(normalized) ? normalized : null;
}

/** Remove query strings and concrete identifiers before a route enters logs. */
export function normalizeClientRouteTemplate(value: unknown) {
  if (typeof value !== 'string') return '/:route';
  const pathname = value.trim().split(/[?#]/, 1)[0] || '/';
  if (KNOWN_STATIC_ROUTES.has(pathname)) return pathname;
  for (const base of ['/inbox', '/outreach', '/prospects']) {
    if (pathname.startsWith(`${base}/`)) return `${base}/:id`;
  }
  return '/:route';
}

function readRuntimeValue(name: 'release' | 'environment' | 'service') {
  if (typeof document === 'undefined') return null;
  const key = `app${name.charAt(0).toUpperCase()}${name.slice(1)}` as const;
  const value = document.body?.dataset?.[key] ?? null;
  return value ? safeToken(value, 'unknown', 80) : null;
}

function trimRecentReports(now: number) {
  recentReportKeys.forEach((timestamp, key) => {
    if (now - timestamp > RECENT_REPORT_TTL_MS || recentReportKeys.size > MAX_RECENT_REPORTS) {
      recentReportKeys.delete(key);
    }
  });
}

function createReportKey(report: ClientErrorReport) {
  return [report.kind, report.reasonCode, report.route ?? '', report.digest ?? ''].join('::');
}

function errorReasonCode(error: unknown, fallback: string) {
  // Error names can be assigned by application or third-party code. They are
  // deliberately ignored so no attacker-controlled text becomes telemetry.
  void error;
  return fallback;
}

export function reportClientError(report: ClientErrorReportInput) {
  if (typeof window === 'undefined') return;

  const payload: ClientErrorReport = {
    kind: report.kind,
    reasonCode: safeToken(report.reasonCode, report.kind, 80).toLowerCase(),
    digest: safeDigest(report.digest),
    route: normalizeClientRouteTemplate(report.route),
    release: report.release ? safeToken(report.release, 'unknown', 80) : readRuntimeValue('release'),
    environment: report.environment ? safeToken(report.environment, 'unknown', 80) : readRuntimeValue('environment'),
    service: report.service ? safeToken(report.service, 'unknown', 80) : readRuntimeValue('service'),
    line: safePosition(report.line),
    column: safePosition(report.column),
    capturedAt: new Date().toISOString(),
  };

  const now = Date.now();
  trimRecentReports(now);
  const reportKey = createReportKey(payload);
  if (recentReportKeys.has(reportKey)) return;
  recentReportKeys.set(reportKey, now);

  const body = JSON.stringify(payload);
  const endpoint = '/api/client-errors';

  try {
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' });
      if (navigator.sendBeacon(endpoint, blob)) return;
    }
  } catch {
    // Fall through to the same-origin fetch without exposing the original error.
  }

  void fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    keepalive: true,
  }).catch(() => undefined);
}

export function reportRouteError({
  error,
  route,
  release,
  environment,
}: {
  error: Error & { digest?: string };
  route: string;
  release?: string | null;
  environment?: string | null;
}) {
  reportClientError({
    kind: 'route_error',
    reasonCode: 'route_render_error',
    digest: safeDigest(error.digest),
    route,
    release: release ?? null,
    environment: environment ?? null,
  });
}

export function normalizeRejectionReason(reason: unknown) {
  return { reasonCode: errorReasonCode(reason, 'unhandled_rejection') };
}

export function normalizeWindowError(error: unknown, _fallbackMessage: string) {
  return { reasonCode: errorReasonCode(error, 'window_error') };
}
