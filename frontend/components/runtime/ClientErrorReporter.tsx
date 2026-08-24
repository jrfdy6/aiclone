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
  const { pathname } = useClientLocation();

  useEffect(() => {
    const route = pathname || '/';

    const handleWindowError = (event: ErrorEvent) => {
      const normalized = normalizeWindowError(event.error, 'Window error');
      reportClientError({
        kind: 'window_error',
        reasonCode: normalized.reasonCode,
        route,
        release,
        environment,
        service,
        line: event.lineno || null,
        column: event.colno || null,
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const normalized = normalizeRejectionReason(event.reason);
      reportClientError({
        kind: 'unhandled_rejection',
        reasonCode: normalized.reasonCode,
        route,
        release,
        environment,
        service,
      });
    };

    window.addEventListener('error', handleWindowError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleWindowError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [environment, pathname, release, service]);

  return null;
}
