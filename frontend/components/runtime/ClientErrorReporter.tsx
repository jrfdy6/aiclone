'use client';

import { useEffect } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import { normalizeRejectionReason, normalizeWindowError, reportClientError } from '@/lib/client-error-reporting';

export default function ClientErrorReporter({
  release,
  environment,
  service,
}: {
  release: string;
  environment: string;
  service: string;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    const search = searchParams?.toString();
    const route = search ? `${pathname ?? ''}?${search}` : pathname ?? '/';

    const handleWindowError = (event: ErrorEvent) => {
      const normalized = normalizeWindowError(event.error, event.message || 'Window error');
      reportClientError({
        kind: 'window_error',
        message: normalized.message,
        stack: normalized.stack,
        route,
        href: typeof window !== 'undefined' ? window.location.href : route,
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
        href: typeof window !== 'undefined' ? window.location.href : route,
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
  }, [environment, pathname, release, searchParams, service]);

  return null;
}
