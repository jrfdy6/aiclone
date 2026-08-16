'use client';

import { useEffect } from 'react';
import { normalizeRejectionReason, normalizeWindowError, reportClientError } from '@/lib/client-error-reporting';
import { useClientLocation } from '@/lib/use-client-location';

export default function ClientErrorReporter({
  release,
  environment,
  service,
}: {
  release: string;
  environment: string;
  service: string;
}) {
  const { href, pathname, search } = useClientLocation();

  useEffect(() => {
    const route = search ? `${pathname || '/'}${search}` : pathname || '/';

    const handleWindowError = (event: ErrorEvent) => {
      const normalized = normalizeWindowError(event.error, event.message || 'Window error');
      reportClientError({
        kind: 'window_error',
        message: normalized.message,
        stack: normalized.stack,
        route,
        href: href || route,
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
        release,
        environment,
        detail: {
          service,
          source: event.filename || null,
          line: event.lineno || null,
          column: event.colno || null,
        },
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const normalized = normalizeRejectionReason(event.reason);
      reportClientError({
        kind: 'unhandled_rejection',
        message: normalized.message,
        stack: normalized.stack,
        route,
        href: href || route,
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
        release,
        environment,
        detail: {
          service,
        },
      });
    };

    window.addEventListener('error', handleWindowError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleWindowError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [environment, href, pathname, release, search, service]);

  return null;
}
