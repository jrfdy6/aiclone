'use client';

export type ClientErrorKind = 'window_error' | 'unhandled_rejection' | 'route_error';

export type ClientErrorReport = {
  kind: ClientErrorKind;
  message: string;
  stack?: string | null;
  digest?: string | null;
  route?: string | null;
  href?: string | null;
  userAgent?: string | null;
  release?: string | null;
  environment?: string | null;
  detail?: Record<string, unknown> | null;
  capturedAt: string;
};

const recentReportKeys = new Map<string, number>();
const MAX_RECENT_REPORTS = 50;
const RECENT_REPORT_TTL_MS = 60_000;

function readRuntimeValue(name: 'release' | 'environment' | 'service') {
  if (typeof document === 'undefined') {
    return null;
  }
  const key = `app${name.charAt(0).toUpperCase()}${name.slice(1)}` as const;
  return document.body?.dataset?.[key] ?? null;
}

function trimRecentReports(now: number) {
  for (const [key, timestamp] of recentReportKeys.entries()) {
    if (now - timestamp > RECENT_REPORT_TTL_MS || recentReportKeys.size > MAX_RECENT_REPORTS) {
      recentReportKeys.delete(key);
    }
  }
}

function createReportKey(report: ClientErrorReport) {
  return [
    report.kind,
    report.route ?? '',
    report.message,
    report.digest ?? '',
    report.stack?.slice(0, 180) ?? '',
  ].join('::');
}

function normalizeUnknownError(error: unknown) {
  if (error instanceof Error) {
    return {
      message: error.message,
      stack: error.stack ?? null,
    };
  }
  if (typeof error === 'string') {
    return {
      message: error,
      stack: null,
    };
  }
  try {
    return {
      message: JSON.stringify(error),
      stack: null,
    };
  } catch {
    return {
      message: 'Unknown client error',
      stack: null,
    };
  }
}

export function reportClientError(report: Omit<ClientErrorReport, 'capturedAt'>) {
  if (typeof window === 'undefined') {
    return;
  }

  const service = readRuntimeValue('service');
  const payload: ClientErrorReport = {
    ...report,
    release: report.release ?? readRuntimeValue('release'),
    environment: report.environment ?? readRuntimeValue('environment'),
    detail: {
      ...(service ? { service } : {}),
      ...(report.detail ?? {}),
    },
    capturedAt: new Date().toISOString(),
  };

  const now = Date.now();
  trimRecentReports(now);
  const reportKey = createReportKey(payload);
  if (recentReportKeys.has(reportKey)) {
    return;
  }
  recentReportKeys.set(reportKey, now);

  const body = JSON.stringify(payload);
  const endpoint = '/api/client-errors';

  try {
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([body], { type: 'application/json' });
      if (navigator.sendBeacon(endpoint, blob)) {
        return;
      }
    }
  } catch {
    // Fall through to fetch.
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
  detail,
}: {
  error: Error & { digest?: string };
  route: string;
  release?: string | null;
  environment?: string | null;
  detail?: Record<string, unknown>;
}) {
  reportClientError({
    kind: 'route_error',
    message: error.message || 'Route render error',
    stack: error.stack ?? null,
    digest: error.digest ?? null,
    route,
    href: typeof window !== 'undefined' ? window.location.href : route,
    userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
    release: release ?? null,
    environment: environment ?? null,
    detail: detail ?? null,
  });
}

export function normalizeRejectionReason(reason: unknown) {
  return normalizeUnknownError(reason);
}

export function normalizeWindowError(error: unknown, fallbackMessage: string) {
  const normalized = normalizeUnknownError(error);
  return {
    message: normalized.message || fallbackMessage,
    stack: normalized.stack,
  };
}
