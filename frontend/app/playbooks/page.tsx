'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Playbook = {
  id: string;
  name: string;
  description: string;
  steps: string[];
  created_at: string;
};

export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPlaybooks();
  }, []);

  const loadPlaybooks = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      setPlaybooks([
        {
          id: '1',
          name: 'Onboarding Playbook',
          description: 'Guide for onboarding new team members',
          steps: ['Welcome', 'Setup', 'Training', 'Review'],
          created_at: '2024-01-15T10:00:00Z',
        },
      ]);
    } catch (err) {
      console.error('Failed to load playbooks:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading playbooks...</p>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Playbooks
          </h1>
          <p style={{ color: '#9ca3af' }}>Manage your workflow playbooks and processes</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '24px' }}>
          {playbooks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
              <p>No playbooks found. Create your first playbook to get started.</p>
            </div>
          ) : (
            playbooks.map((playbook) => (
              <div
                key={playbook.id}
                style={{
                  backgroundColor: '#1e293b',
                  borderRadius: '12px',
                  border: '1px solid #475569',
                  padding: '24px',
                }}
              >
                <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>
                  {playbook.name}
                </h2>
                <p style={{ fontSize: '14px', color: '#e2e8f0', marginBottom: '16px' }}>
                  {playbook.description}
                </p>
                <div style={{ marginTop: '16px' }}>
                  <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm">
                    View Playbook
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
