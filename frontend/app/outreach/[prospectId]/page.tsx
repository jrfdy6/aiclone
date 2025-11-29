'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Prospect = {
  id: string;
  name?: string;
  company?: string;
  job_title?: string;
  email?: string;
  phone?: string;
  fit_score?: number;
  status?: string;
  tags?: string[];
  notes?: string;
  summary?: string;
  pain_points?: string[];
  source_url?: string;
  location?: string;
};

type OutreachMessage = {
  id: string;
  type: 'email' | 'linkedin' | 'dm';
  subject?: string;
  content: string;
  created_at: string;
};

export default function OutreachPage() {
  const params = useParams();
  const router = useRouter();
  const prospectId = params?.prospectId as string;

  const [prospect, setProspect] = useState<Prospect | null>(null);
  const [messages, setMessages] = useState<OutreachMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [messageType, setMessageType] = useState<'email' | 'linkedin' | 'dm'>('email');

  useEffect(() => {
    if (prospectId) {
      loadProspect();
      loadMessages();
    }
  }, [prospectId]);

  const loadProspect = async () => {
    try {
      // TODO: Replace with actual API endpoint
      // Mock data for now
      setProspect({
        id: prospectId,
        name: 'Sarah Johnson',
        company: 'TechEd Solutions',
        job_title: 'Director of Admissions',
        email: 'sarah.johnson@techedsolutions.com',
        phone: '+1 (555) 123-4567',
        fit_score: 92,
        status: 'new',
        location: 'San Francisco, CA',
        tags: ['Education', 'EdTech'],
        summary: 'Experienced admissions director at a leading EdTech company.',
        pain_points: ['Student enrollment', 'AI integration'],
        source_url: 'https://example.com/profile',
      });
    } catch (err) {
      console.error('Failed to load prospect:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async () => {
    try {
      // TODO: Replace with actual API endpoint
      setMessages([]);
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  };

  const handleGenerateMessage = async () => {
    if (!prospect) return;

    setGenerating(true);
    try {
      // TODO: Replace with actual API endpoint
      const newMessage: OutreachMessage = {
        id: `msg-${Date.now()}`,
        type: messageType,
        subject: messageType === 'email' ? `Re: ${prospect.company} - AI Solutions` : undefined,
        content: `Hi ${prospect.name?.split(' ')[0] || 'there'},\n\nI noticed ${prospect.company} is working on ${prospect.pain_points?.[0] || 'innovative solutions'}. I'd love to share how we can help.\n\nBest regards`,
        created_at: new Date().toISOString(),
      };
      setMessages([...messages, newMessage]);
    } catch (err) {
      console.error('Failed to generate message:', err);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Loading prospect...</p>
        </div>
      </main>
    );
  }

  if (!prospect) {
    return (
      <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
        <NavHeader />
        <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '48px', textAlign: 'center' }}>
          <p style={{ color: '#9ca3af' }}>Prospect not found</p>
          <Link href="/outreach" className="text-blue-400 hover:underline">
            Back to Outreach
          </Link>
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
          <Link
            href="/outreach"
            className="text-blue-400 hover:underline mb-2 inline-block"
          >
            ← Back to Outreach
          </Link>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
            Outreach: {prospect.name}
          </h1>
          <p style={{ color: '#9ca3af' }}>{prospect.job_title} at {prospect.company}</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
          {/* Prospect Info Sidebar */}
          <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>
              Prospect Details
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Name</p>
                <p style={{ color: 'white' }}>{prospect.name}</p>
              </div>
              <div>
                <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Company</p>
                <p style={{ color: 'white' }}>{prospect.company}</p>
              </div>
              <div>
                <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Title</p>
                <p style={{ color: 'white' }}>{prospect.job_title}</p>
              </div>
              {prospect.email && (
                <div>
                  <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Email</p>
                  <p style={{ color: 'white' }}>{prospect.email}</p>
                </div>
              )}
              {prospect.phone && (
                <div>
                  <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Phone</p>
                  <p style={{ color: 'white' }}>{prospect.phone}</p>
                </div>
              )}
              {prospect.location && (
                <div>
                  <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Location</p>
                  <p style={{ color: 'white' }}>{prospect.location}</p>
                </div>
              )}
              <div>
                <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Fit Score</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ flex: 1, height: '8px', backgroundColor: '#475569', borderRadius: '4px', overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${prospect.fit_score || 0}%`,
                        height: '100%',
                        backgroundColor: (prospect.fit_score || 0) > 80 ? '#10b981' : (prospect.fit_score || 0) > 60 ? '#f59e0b' : '#ef4444',
                      }}
                    />
                  </div>
                  <span style={{ color: 'white', fontSize: '14px', fontWeight: 600 }}>
                    {prospect.fit_score || 0}%
                  </span>
                </div>
              </div>
              {prospect.summary && (
                <div>
                  <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Summary</p>
                  <p style={{ color: 'white', fontSize: '14px' }}>{prospect.summary}</p>
                </div>
              )}
              {prospect.pain_points && prospect.pain_points.length > 0 && (
                <div>
                  <p style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>Pain Points</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {prospect.pain_points.map((point, idx) => (
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
                        {point}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Outreach Messages */}
          <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
            <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white' }}>
                Outreach Messages
              </h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <select
                  value={messageType}
                  onChange={(e) => setMessageType(e.target.value as 'email' | 'linkedin' | 'dm')}
                  style={{
                    padding: '8px 12px',
                    backgroundColor: '#0f172a',
                    color: 'white',
                    border: '1px solid #475569',
                    borderRadius: '8px',
                  }}
                >
                  <option value="email">Email</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="dm">Direct Message</option>
                </select>
                <button
                  onClick={handleGenerateMessage}
                  disabled={generating}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {generating ? 'Generating...' : 'Generate Message'}
                </button>
              </div>
            </div>

            {messages.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px', color: '#9ca3af' }}>
                <p>No messages yet. Generate your first outreach message.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {messages.map((message) => (
                  <div
                    key={message.id}
                    style={{
                      padding: '16px',
                      backgroundColor: '#0f172a',
                      borderRadius: '8px',
                      border: '1px solid #475569',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span
                        style={{
                          padding: '4px 8px',
                          backgroundColor: message.type === 'email' ? '#3b82f6' : message.type === 'linkedin' ? '#0a66c2' : '#6366f1',
                          color: 'white',
                          borderRadius: '4px',
                          fontSize: '12px',
                          textTransform: 'uppercase',
                        }}
                      >
                        {message.type}
                      </span>
                      <span style={{ fontSize: '12px', color: '#9ca3af' }}>
                        {new Date(message.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {message.subject && (
                      <p style={{ fontWeight: 600, color: 'white', marginBottom: '8px' }}>
                        Subject: {message.subject}
                      </p>
                    )}
                    <pre
                      style={{
                        color: '#e2e8f0',
                        fontSize: '14px',
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'inherit',
                      }}
                    >
                      {message.content}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
