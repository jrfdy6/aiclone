'use client';

import Link from 'next/link';

export function RouteLoadingState({
  badge,
  title,
  description,
  tone,
}: {
  badge: string;
  title: string;
  description: string;
  tone: string;
}) {
  return (
    <main
      style={{
        minHeight: '100vh',
        background: 'radial-gradient(circle at top, rgba(24, 32, 54, 0.92), #040816 48%, #020611 100%)',
        color: 'white',
      }}
    >
      <div style={{ maxWidth: 'min(960px, calc(100vw - 24px))', margin: '0 auto', padding: '48px 24px 120px' }}>
        <section
          style={{
            display: 'grid',
            gap: '14px',
            borderRadius: '20px',
            border: '1px solid rgba(148, 163, 184, 0.16)',
            background: 'rgba(4, 8, 22, 0.78)',
            padding: '28px',
            boxShadow: '0 18px 44px rgba(0, 0, 0, 0.24)',
          }}
        >
          <div
            style={{
              width: '52px',
              height: '52px',
              borderRadius: '16px',
              border: `1px solid ${tone}55`,
              background: `${tone}16`,
              display: 'grid',
              placeItems: 'center',
              color: tone,
              fontSize: '24px',
              fontWeight: 700,
            }}
          >
            •••
          </div>
          <div>
            <p style={{ color: tone, letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase', margin: 0 }}>{badge}</p>
            <h1 style={{ color: 'white', fontSize: '30px', margin: '10px 0 8px' }}>{title}</h1>
            <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.7, margin: 0 }}>{description}</p>
          </div>
        </section>
      </div>
    </main>
  );
}

export function RouteErrorState({
  badge,
  title,
  description,
  tone,
  onRetry,
  primaryLabel = 'Try again',
  secondaryHref = '/ops',
  secondaryLabel = 'Back to Ops',
}: {
  badge: string;
  title: string;
  description: string;
  tone: string;
  onRetry?: () => void;
  primaryLabel?: string;
  secondaryHref?: string;
  secondaryLabel?: string;
}) {
  return (
    <main
      style={{
        minHeight: '100vh',
        background: 'radial-gradient(circle at top, rgba(24, 32, 54, 0.92), #040816 48%, #020611 100%)',
        color: 'white',
      }}
    >
      <div style={{ maxWidth: 'min(960px, calc(100vw - 24px))', margin: '0 auto', padding: '48px 24px 120px' }}>
        <section
          style={{
            display: 'grid',
            gap: '18px',
            borderRadius: '20px',
            border: '1px solid rgba(248, 113, 113, 0.22)',
            background: 'rgba(8, 12, 26, 0.88)',
            padding: '28px',
            boxShadow: '0 18px 44px rgba(0, 0, 0, 0.24)',
          }}
        >
          <div>
            <p style={{ color: tone, letterSpacing: '0.2em', fontSize: '11px', textTransform: 'uppercase', margin: 0 }}>{badge}</p>
            <h1 style={{ color: 'white', fontSize: '30px', margin: '10px 0 8px' }}>{title}</h1>
            <p style={{ color: '#cbd5f5', fontSize: '14px', lineHeight: 1.7, margin: 0 }}>{description}</p>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
            {onRetry ? (
              <button
                onClick={onRetry}
                style={{
                  border: `1px solid ${tone}`,
                  borderRadius: '12px',
                  background: `${tone}18`,
                  color: 'white',
                  padding: '10px 14px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {primaryLabel}
              </button>
            ) : null}
            <Link
              href={secondaryHref}
              style={{
                border: '1px solid rgba(148, 163, 184, 0.22)',
                borderRadius: '12px',
                background: 'rgba(15, 23, 42, 0.74)',
                color: '#e2e8f0',
                padding: '10px 14px',
                fontSize: '14px',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              {secondaryLabel}
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
