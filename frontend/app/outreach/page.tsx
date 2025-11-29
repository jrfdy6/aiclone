'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Prospect = {
  id: string;
  name?: string;
  company?: string;
  job_title?: string;
  fit_score?: number;
  status?: 'new' | 'contacted' | 'follow_up_needed';
  last_contact?: string;
  message_count?: number;
};

export default function OutreachPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadProspects();
  }, []);

  const loadProspects = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setProspects([
        {
          id: '1',
          name: 'Sarah Johnson',
          company: 'TechEd Solutions',
          job_title: 'Director of Admissions',
          fit_score: 92,
          status: 'new',
          message_count: 0,
        },
        {
          id: '2',
          name: 'Emily Rodriguez',
          company: 'Future Schools Inc',
          job_title: 'Head of Enrollment',
          fit_score: 88,
          status: 'contacted',
          last_contact: '2 days ago',
          message_count: 2,
        },
        {
          id: '3',
          name: 'Michael Chen',
          company: 'InnovateEd',
          job_title: 'Admissions Director',
          fit_score: 85,
          status: 'follow_up_needed',
          last_contact: '1 week ago',
          message_count: 1,
        },
      ]);
    } catch (err) {
      console.error('Failed to load prospects:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredProspects = prospects.filter((p) => {
    const matchesFilter = filter === 'all' || p.status === filter;
    const matchesSearch =
      !searchQuery ||
      (p.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.company?.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesFilter && matchesSearch;
  });

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'new':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'contacted':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'follow_up_needed':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading prospects...</p>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Outreach
          </h1>
          <p style={{ color: '#9ca3af' }}>Manage your outreach messages and prospect communications</p>
        </div>

        {/* Filters and Search */}
        <div style={{ marginBottom: '24px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search prospects..."
              style={{
                width: '100%',
                padding: '12px',
                backgroundColor: '#1e293b',
                border: '1px solid #475569',
                borderRadius: '8px',
                color: 'white',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {['all', 'new', 'contacted', 'follow_up_needed'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  filter === f
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
                style={{ textTransform: 'capitalize' }}
              >
                {f === 'all' ? 'All' : f.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Prospect List */}
        <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
          {filteredProspects.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
              <p>No prospects found for this filter.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {filteredProspects.map((prospect) => (
                <Link
                  key={prospect.id}
                  href={`/outreach/${prospect.id}`}
                  className="block"
                >
                  <div
                    className={`p-4 rounded-lg border ${getStatusColor(prospect.status)} hover:opacity-80 transition-opacity`}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
                      <div>
                        <h3 style={{ fontWeight: 600, fontSize: '16px', marginBottom: '4px' }}>
                          {prospect.name}
                        </h3>
                        <p style={{ fontSize: '14px', opacity: 0.8 }}>
                          {prospect.job_title} at {prospect.company}
                        </p>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '4px' }}>
                          {prospect.fit_score || 0}% fit
                        </div>
                        {prospect.message_count !== undefined && (
                          <div style={{ fontSize: '12px', opacity: 0.7 }}>
                            {prospect.message_count} message{prospect.message_count !== 1 ? 's' : ''}
                          </div>
                        )}
                      </div>
                      {prospect.last_contact && (
                        <div style={{ fontSize: '12px', opacity: 0.7 }}>
                          Last: {prospect.last_contact}
                        </div>
                      )}
                      <div
                        style={{
                          padding: '4px 12px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: 600,
                          textTransform: 'capitalize',
                        }}
                      >
                        {prospect.status?.replace('_', ' ') || 'Unknown'}
                      </div>
                      <span style={{ fontSize: '20px', opacity: 0.5 }}>→</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
