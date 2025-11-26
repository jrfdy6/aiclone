'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function NavHeader() {
  const pathname = usePathname();

  const navLinks = [
    { href: '/prospect-discovery', label: 'Find Prospects' },
    { href: '/prospects', label: 'Pipeline' },
    { href: '/content-pipeline', label: 'Content' },
    { href: '/topic-intelligence', label: 'Intelligence' },
  ];

  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 50,
      backgroundColor: '#0f172a',
      borderBottom: '2px solid #475569',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
    }}>
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Link 
          href="/" 
          style={{
            fontSize: '24px',
            fontWeight: 'bold',
            color: 'white',
            padding: '16px 0',
            textDecoration: 'none',
          }}
        >
          AI Clone
        </Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              style={{
                padding: '16px',
                fontSize: '14px',
                fontWeight: 500,
                color: pathname === link.href ? 'white' : '#e2e8f0',
                textDecoration: 'none',
                borderBottom: pathname === link.href ? '2px solid #3b82f6' : '2px solid transparent',
                backgroundColor: pathname === link.href ? '#1e293b' : 'transparent',
              }}
            >
              {link.label}
            </Link>
          ))}
          <Link
            href="/dashboard"
            style={{
              marginLeft: '16px',
              padding: '8px 20px',
              backgroundColor: '#2563eb',
              color: 'white',
              fontWeight: 600,
              borderRadius: '8px',
              textDecoration: 'none',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
            }}
          >
            Dashboard
          </Link>
        </div>
      </div>
    </nav>
  );
}

