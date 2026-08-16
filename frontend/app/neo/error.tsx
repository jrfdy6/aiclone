'use client';

import { RouteErrorState } from '@/components/runtime/RouteStateShell';

export default function NeoError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <RouteErrorState
      badge="Neo"
      title="Neo needs a quick reset"
      description="Retry this guest conversation. If the issue continues, ask the owner for a new invite."
      tone="#f59e0b"
      onRetry={reset}
      primaryLabel="Retry Neo"
      secondaryHref={null}
    />
  );
}
