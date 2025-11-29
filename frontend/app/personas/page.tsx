'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Persona = {
  id: string;
  name: string;
  description: string;
  role: string;
  goals: string[];
  pain_points: string[];
  preferred_channels: string[];
  tone: string;
  created_at: string;
  updated_at: string;
};

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadPersonas();
  }, []);

  const loadPersonas = async () => {
    try {
      setLoading(true);
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setPersonas([
        {
          id: '1',
          name: 'Educational Consultant',
          description: 'Independent educational consultants helping families navigate school selection',
          role: 'Consultant',
          goals: ['Build referral network', 'Attract high-value clients', 'Establish thought leadership'],
          pain_points: ['Time-consuming client communication', 'Finding qualified prospects', 'Standing out in competitive market'],
          preferred_channels: ['LinkedIn', 'Email', 'Professional networks'],
          tone: 'Professional, empathetic, expert',
          created_at: '2024-01-15T10:00:00Z',
          updated_at: '2024-11-20T14:30:00Z',
        },
        {
          id: '2',
          name: 'Admissions Director',
          description: 'School admissions directors managing enrollment and student recruitment',
          role: 'Administrator',
          goals: ['Increase enrollment', 'Improve student fit', 'Build school reputation'],
          pain_points: ['Enrollment challenges', 'Student retention', 'Parent communication'],
          preferred_channels: ['Email', 'School website', 'Social media'],
          tone: 'Welcoming, informative, supportive',
          created_at: '2024-02-01T09:00:00Z',
          updated_at: '2024-11-18T16:00:00Z',
        },
      ]);
    } catch (err) {
      console.error('Failed to load personas:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredPersonas = personas.filter((persona) =>
    !searchQuery ||
    persona.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    persona.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    persona.role.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading personas...</p>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
        {/* Header */}
        <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
              Personas
            </h1>
            <p style={{ color: '#9ca3af' }}>Manage your target audience personas</p>
          </div>
          <button
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + Create Persona
          </button>
        </div>

        {/* Search */}
        <div style={{ marginBottom: '24px' }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search personas..."
            style={{
              width: '100%',
              maxWidth: '400px',
              padding: '12px',
              backgroundColor: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '8px',
              color: 'white',
            }}
          />
        </div>

        {/* Persona List */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '24px' }}>
          {filteredPersonas.length === 0 ? (
            <div
              style={{
                gridColumn: '1 / -1',
                textAlign: 'center',
                padding: '48px',
                color: '#9ca3af',
              }}
            >
              <p>No personas found. Create your first persona to get started.</p>
            </div>
          ) : (
            filteredPersonas.map((persona) => (
              <div
                key={persona.id}
                style={{
                  backgroundColor: '#1e293b',
                  borderRadius: '12px',
                  border: '1px solid #475569',
                  padding: '24px',
                }}
              >
                <div style={{ marginBottom: '16px' }}>
                  <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>
                    {persona.name}
                  </h2>
                  <p style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '4px' }}>
                    {persona.role}
                  </p>
                  <p style={{ fontSize: '14px', color: '#e2e8f0' }}>
                    {persona.description}
                  </p>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>
                    Goals
                  </h3>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {persona.goals.map((goal, idx) => (
                      <li key={idx} style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '4px' }}>
                        • {goal}
                      </li>
                    ))}
                  </ul>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>
                    Pain Points
                  </h3>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                    {persona.pain_points.map((point, idx) => (
                      <li key={idx} style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '4px' }}>
                        • {point}
                      </li>
                    ))}
                  </ul>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>
                    Preferred Channels
                  </h3>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {persona.preferred_channels.map((channel, idx) => (
                      <span
                        key={idx}
                        style={{
                          padding: '4px 8px',
                          backgroundColor: '#475569',
                          color: 'white',
                          borderRadius: '4px',
                          fontSize: '12px',
                        }}
                      >
                        {channel}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <p style={{ fontSize: '12px', color: '#9ca3af' }}>
                    <span style={{ fontWeight: 600 }}>Tone:</span> {persona.tone}
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '8px', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #475569' }}>
                  <button
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                  >
                    Edit
                  </button>
                  <button
                    className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors text-sm"
                  >
                    Use for Outreach
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
