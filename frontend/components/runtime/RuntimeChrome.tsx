'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';
import { useClientLocation } from '@/lib/use-client-location';

export type RuntimeModule = 'ops' | 'brain' | 'lab';

export type RuntimeTab = {
  key: string;
  label: string;
  active: boolean;
  onSelect: () => void;
};

const accents: Record<RuntimeModule, string> = {
  ops: '#fbbf24',
  brain: '#38bdf8',
  lab: '#4ade80',
};

type IconComponent = ({ size }: { size?: number }) => ReactNode;

function iconFrame(size = 18) {
  return {
    fill: 'none',
    height: size,
    stroke: 'currentColor',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    strokeWidth: 1.8,
    viewBox: '0 0 24 24',
    width: size,
  };
}

function SignalIcon({ size = 18 }: { size?: number }) {
  return (
    <svg {...iconFrame(size)}>
      <path d="M12 3v18" />
      <path d="M5 9a7 7 0 0 1 14 0" />
      <path d="M8 12a4 4 0 0 1 8 0" />
      <circle cx="12" cy="18" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

function BrainIcon({ size = 18 }: { size?: number }) {
  return (
    <svg {...iconFrame(size)}>
      <path d="M9 6a3 3 0 0 0-3 3v6a3 3 0 0 0 3 3" />
      <path d="M15 6a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3" />
      <path d="M9 8.5c1.2-1.4 2.4-2.1 3-2.1s1.8.7 3 2.1" />
      <path d="M9 15.5c1.2 1.4 2.4 2.1 3 2.1s1.8-.7 3-2.1" />
      <path d="M12 6v12" />
      <path d="M8.5 12H15.5" />
    </svg>
  );
}

function FlaskIcon({ size = 18 }: { size?: number }) {
  return (
    <svg {...iconFrame(size)}>
      <path d="M10 3h4" />
      <path d="M11 3v5l-4.5 8a2 2 0 0 0 1.8 3h7.4a2 2 0 0 0 1.8-3L13 8V3" />
      <path d="M8.5 14h7" />
    </svg>
  );
}

function WorkspaceIconGlyph({ size = 18 }: { size?: number }) {
  return (
    <svg {...iconFrame(size)}>
      <rect x="3" y="5" width="7" height="6" rx="1.2" />
      <rect x="14" y="5" width="7" height="6" rx="1.2" />
      <rect x="3" y="13" width="18" height="6" rx="1.2" />
    </svg>
  );
}

function InboxIconGlyph({ size = 18 }: { size?: number }) {
  return (
    <svg {...iconFrame(size)}>
      <path d="M4 6h16l-1.2 11a2 2 0 0 1-2 1.8H7.2a2 2 0 0 1-2-1.8z" />
      <path d="M4 12h4l2 3h4l2-3h4" />
    </svg>
  );
}

function BookIcon({ size = 18 }: { size?: number }) {
  return (
    <svg {...iconFrame(size)}>
      <path d="M6 5.5A2.5 2.5 0 0 1 8.5 3H19v16H8.5A2.5 2.5 0 0 0 6 21z" />
      <path d="M6 5.5V21H5a2 2 0 0 1-2-2V7.5A2.5 2.5 0 0 1 5.5 5z" />
      <path d="M10 8h6" />
      <path d="M10 12h6" />
    </svg>
  );
}

const modules: { id: RuntimeModule; label: string; href: string; icon: IconComponent }[] = [
  { id: 'ops', label: 'Ops', href: '/ops', icon: SignalIcon },
  { id: 'brain', label: 'Brain', href: '/brain', icon: BrainIcon },
  { id: 'lab', label: 'Lab', href: '/lab', icon: FlaskIcon },
];

const workspaceLink = {
  id: 'workspace',
  label: 'Workspaces',
  href: '/ops#workspace',
  icon: WorkspaceIconGlyph,
  tone: '#fb923c',
};

const inboxLink = {
  id: 'inbox',
  label: 'Inbox',
  href: '/inbox',
  icon: InboxIconGlyph,
  tone: '#60a5fa',
};

export function RuntimePage({
  module,
  tabs,
  children,
  maxWidth = '1360px',
}: {
  module: RuntimeModule;
  tabs: RuntimeTab[];
  children: ReactNode;
  maxWidth?: string;
}) {
  const accent = accents[module];

  return (
    <main
      style={{
        minHeight: '100vh',
        background: 'radial-gradient(circle at top, rgba(24, 32, 54, 0.92), #040816 48%, #020611 100%)',
        color: 'white',
        paddingBottom: '112px',
      }}
    >
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 40,
          borderBottom: '1px solid rgba(148, 163, 184, 0.12)',
          background: 'rgba(4, 8, 22, 0.9)',
          backdropFilter: 'blur(18px)',
        }}
      >
        <div style={{ maxWidth, margin: '0 auto', padding: '14px 24px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Link href="/ops" style={{ color: 'white', fontSize: '22px', fontWeight: 700, textDecoration: 'none', letterSpacing: '-0.02em' }}>
                AI Clone
              </Link>
              <span
                style={{
                  borderRadius: '999px',
                  border: `1px solid ${accent}66`,
                  backgroundColor: `${accent}14`,
                  color: accent,
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '0.18em',
                  padding: '6px 10px',
                  textTransform: 'uppercase',
                }}
              >
                {module}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#94a3b8', fontSize: '12px' }}>
              <BookIcon size={14} />
              <span>Control surfaces</span>
            </div>
          </div>
          <RuntimeTabs tabs={tabs} accent={accent} />
        </div>
      </div>
      <div style={{ maxWidth, margin: '0 auto', padding: '20px 24px 0' }}>{children}</div>
      <ModuleDock active={module} />
    </main>
  );
}

function RuntimeTabs({ tabs, accent }: { tabs: RuntimeTab[]; accent: string }) {
  return (
    <div style={{ display: 'flex', gap: '2px', flexWrap: 'wrap' }}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={tab.onSelect}
          style={{
            border: 'none',
            borderTopLeftRadius: '10px',
            borderTopRightRadius: '10px',
            borderBottom: tab.active ? `2px solid ${accent}` : '2px solid transparent',
            background: tab.active ? `${accent}18` : 'transparent',
            boxShadow: tab.active ? `inset 0 0 0 1px ${accent}55` : 'inset 0 0 0 1px transparent',
            color: tab.active ? '#f8fafc' : '#a8b1c5',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 600,
            padding: '14px 18px',
            transition: 'all 160ms ease',
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function ModuleDock({ active }: { active: RuntimeModule }) {
  const { hash, pathname } = useClientLocation();
  const currentPath = pathname ?? '';
  const WorkspaceIcon = workspaceLink.icon;
  const InboxIcon = inboxLink.icon;

  return (
    <div style={{ position: 'fixed', bottom: '14px', left: 0, right: 0, zIndex: 50, display: 'flex', justifyContent: 'center', pointerEvents: 'none' }}>
      <div
        style={{
          display: 'flex',
          gap: '6px',
          padding: '8px',
          background: 'rgba(8, 13, 28, 0.82)',
          border: '1px solid rgba(148, 163, 184, 0.14)',
          borderRadius: '18px',
          boxShadow: '0 18px 44px rgba(0, 0, 0, 0.34)',
          backdropFilter: 'blur(16px)',
          pointerEvents: 'auto',
        }}
      >
        {modules.map((item) => {
          const Icon = item.icon;
          const isActive = (active === item.id || currentPath === item.href) && !(item.id === 'ops' && hash === '#workspace');
          const tone = accents[item.id];
          return (
            <Link
              key={item.id}
              href={item.href}
              style={dockButtonStyle(isActive, tone)}
            >
              <Icon size={18} />
              <span style={{ fontSize: '11px', fontWeight: 700 }}>{item.label}</span>
            </Link>
          );
        })}
        <Link
          href={workspaceLink.href}
          style={dockButtonStyle((currentPath === '/ops' && hash === '#workspace') || currentPath.startsWith('/workspace') || currentPath === '/linkedin', workspaceLink.tone)}
        >
          <WorkspaceIcon size={18} />
          <span style={{ fontSize: '11px', fontWeight: 700 }}>{workspaceLink.label}</span>
        </Link>
        <Link
          href={inboxLink.href}
          style={dockButtonStyle(currentPath === '/inbox' || currentPath.startsWith('/inbox/'), inboxLink.tone)}
        >
          <InboxIcon size={18} />
          <span style={{ fontSize: '11px', fontWeight: 700 }}>{inboxLink.label}</span>
        </Link>
      </div>
    </div>
  );
}

function dockButtonStyle(active: boolean, tone: string) {
  return {
    minWidth: '0',
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    padding: '9px 12px',
    borderRadius: '12px',
    textDecoration: 'none',
    color: active ? 'white' : '#94a3b8',
    border: active ? `1px solid ${tone}` : '1px solid transparent',
    background: active ? `${tone}1c` : 'transparent',
    boxShadow: active ? `0 0 0 1px ${tone}20 inset` : 'none',
    transition: 'all 160ms ease',
  } as const;
}
