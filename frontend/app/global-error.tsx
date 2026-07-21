'use client';

import { useEffect, useState } from 'react';
import { RouteErrorState } from '@/components/runtime/RouteStateShell';
import { reportRouteError } from '@/lib/client-error-reporting';

type ErrorSurface = 'unknown' | 'neo' | 'private';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [surface, setSurface] = useState<ErrorSurface>('unknown');

  useEffect(() => {
    const pathname = window.location.pathname;
    const isNeoGuest = pathname === '/neo' || pathname.startsWith('/neo/');
    setSurface(isNeoGuest ? 'neo' : 'private');
    reportRouteError({
      error,
      route: isNeoGuest ? '/neo' : 'global',
      detail: { surface: isNeoGuest ? 'neo-guest' : 'root-layout' },
    });
  }, [error]);

  const exposeOpsRecovery = surface === 'private';
  const description = surface === 'neo'
    ? 'Retry the Neo guest experience. If the issue continues, ask Johnnie for a new invite.'
    : exposeOpsRecovery
      ? 'A render fault escaped the route-level boundaries. Retry the application shell, or fall back to the main Ops surface.'
      : 'A render fault escaped the route-level boundaries. Retry the application shell.';

  return (
    <html lang="en">
      <body style={{ margin: 0 }}>
        <RouteErrorState
          badge="Application"
          title="The app hit a top-level failure"
          description={description}
          tone="#f87171"
          onRetry={reset}
          secondaryHref={exposeOpsRecovery ? '/ops' : null}
          secondaryLabel="Open Ops"
        />
      </body>
    </html>
  );
}
