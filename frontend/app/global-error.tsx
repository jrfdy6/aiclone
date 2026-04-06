'use client';

import { useEffect } from 'react';
import { RouteErrorState } from '@/components/runtime/RouteStateShell';
import { reportRouteError } from '@/lib/client-error-reporting';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportRouteError({
      error,
      route: 'global',
      detail: { surface: 'root-layout' },
    });
  }, [error]);

  return (
    <html lang="en">
      <body style={{ margin: 0 }}>
        <RouteErrorState
          badge="Application"
          title="The app hit a top-level failure"
          description="A render fault escaped the route-level boundaries. Retry the application shell, or fall back to the main Ops surface."
          tone="#f87171"
          onRetry={reset}
          secondaryHref="/ops"
          secondaryLabel="Open Ops"
        />
      </body>
    </html>
  );
}
