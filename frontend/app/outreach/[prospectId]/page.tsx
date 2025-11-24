'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type EmailVariant = {
  variant: number;
  subject: string;
  body: string;
};

type SocialPost = {
  variant: number;
  caption: string;
  hashtags: string[];
};

type OutreachResponse = {
  emails: EmailVariant[];
  social_posts?: SocialPost[];
};

export default function OutreachPage() {
  const params = useParams();
  const router = useRouter();
  const prospectId = params?.prospectId as string;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outreachData, setOutreachData] = useState<OutreachResponse | null>(null);
  const [selectedEmailIndex, setSelectedEmailIndex] = useState(0);
  const [selectedSocialIndex, setSelectedSocialIndex] = useState(0);
  const [editableEmail, setEditableEmail] = useState<EmailVariant | null>(null);
  const [editableSocial, setEditableSocial] = useState<SocialPost | null>(null);
  const [tone, setTone] = useState('professional');
  const [includeSocial, setIncludeSocial] = useState(true);
  const [showEmailModal, setShowEmailModal] = useState(true);
  const [showSocialModal, setShowSocialModal] = useState(false);

  useEffect(() => {
    if (outreachData?.emails && outreachData.emails.length > 0 && !editableEmail) {
      setEditableEmail({ ...outreachData.emails[0] });
    }
    if (outreachData?.social_posts && outreachData.social_posts.length > 0 && !editableSocial) {
      setEditableSocial({ ...outreachData.social_posts[0] });
    }
  }, [outreachData]);

  const generateOutreach = async () => {
    if (!API_URL || !prospectId) {
      setError('API URL or Prospect ID not configured');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/outreach/manual/prompts/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prospect_id: prospectId,
          user_id: 'dev-user',
          preferred_tone: tone,
          include_social: includeSocial,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to generate outreach: ${response.statusText}`);
      }

      const data = await response.json();
      
      // For now, we'll show the prompt. In a real implementation, this would call an LLM
      // and return the actual outreach variants. For demo, we'll create mock variants.
      setOutreachData({
        emails: [
          {
            variant: 1,
            subject: `Quick question about ${prospectId}`,
            body: `Hi there,\n\nI noticed you're working in [industry]. I thought you might be interested in [value prop].\n\nWould you be open to a quick conversation?\n\nBest,\n[Your name]`,
          },
          {
            variant: 2,
            subject: `[Value prop] for ${prospectId}`,
            body: `Hello,\n\nI help companies like yours [solve pain point]. I'd love to share how [similar company] achieved [result].\n\nInterested in learning more?\n\nBest regards,\n[Your name]`,
          },
          {
            variant: 3,
            subject: `Thought you'd find this interesting`,
            body: `Hi,\n\nI came across [relevant insight] and thought of you given your work in [area].\n\nWould you be open to a brief chat about how this could help?\n\nWarm regards,\n[Your name]`,
          },
        ],
        social_posts: includeSocial ? [
          {
            variant: 1,
            caption: `Excited to share how [value prop] can help [target audience]...`,
            hashtags: ['B2B', 'SaaS', 'Growth'],
          },
          {
            variant: 2,
            caption: `Just learned something interesting about [topic]...`,
            hashtags: ['Innovation', 'Tech', 'Business'],
          },
        ] : undefined,
      });

      if (outreachData?.emails && outreachData.emails.length > 0) {
        setEditableEmail({ ...outreachData.emails[0] });
      }
      if (outreachData?.social_posts && outreachData.social_posts.length > 0) {
        setEditableSocial({ ...outreachData.social_posts[0] });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate outreach');
    } finally {
      setLoading(false);
    }
  };

  const handleEmailVariantChange = (index: number) => {
    if (outreachData?.emails && outreachData.emails[index]) {
      setSelectedEmailIndex(index);
      setEditableEmail({ ...outreachData.emails[index] });
    }
  };

  const handleSocialVariantChange = (index: number) => {
    if (outreachData?.social_posts && outreachData.social_posts[index]) {
      setSelectedSocialIndex(index);
      setEditableSocial({ ...outreachData.social_posts[index] });
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  const calculateQualityScore = (email: EmailVariant) => {
    // Simple heuristic - can be enhanced
    let score = 50;
    if (email.subject.length > 20 && email.subject.length < 60) score += 10;
    if (email.body.length > 100 && email.body.length < 500) score += 20;
    if (email.subject.toLowerCase().includes(prospectId.toLowerCase())) score += 10;
    if (email.body.split('\n').length >= 3) score += 10;
    return Math.min(100, score);
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <Link href="/prospects" className="text-blue-600 hover:underline text-sm mb-2 inline-block">
              ← Back to Prospects
            </Link>
            <h1 className="text-3xl font-bold text-gray-900">Generate Outreach</h1>
            <p className="text-gray-600 mt-1">Create personalized DMs for Prospect ID: {prospectId}</p>
          </div>
        </div>

        {/* Configuration */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Tone</label>
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="casual">Casual</option>
                <option value="formal">Formal</option>
              </select>
            </div>
            <div className="flex items-center">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={includeSocial}
                  onChange={(e) => setIncludeSocial(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span className="text-sm font-medium text-gray-700">Include Social Media Posts</span>
              </label>
            </div>
          </div>
          <button
            onClick={generateOutreach}
            disabled={loading}
            className="mt-4 w-full md:w-auto px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Generating...' : 'Generate Outreach Variants'}
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {/* Email Modal */}
        {outreachData && showEmailModal && (
          <div className="bg-white rounded-lg border-2 border-gray-200 shadow-lg overflow-hidden">
            <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">📧 Email Variants</h2>
              <button
                onClick={() => setShowEmailModal(false)}
                className="text-white hover:text-blue-100"
              >
                ×
              </button>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
              {/* Left: Variants List */}
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Select Variant</h3>
                {outreachData.emails.map((email, idx) => {
                  const score = calculateQualityScore(email);
                  return (
                    <div
                      key={idx}
                      onClick={() => handleEmailVariantChange(idx)}
                      className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        selectedEmailIndex === idx
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-gray-900">Variant {email.variant}</span>
                        <span className="text-xs text-gray-500">Quality: {score}%</span>
                      </div>
                      <p className="text-sm text-gray-700 font-medium mb-1">{email.subject}</p>
                      <p className="text-xs text-gray-500 line-clamp-2">{email.body}</p>
                    </div>
                  );
                })}
                <button
                  onClick={generateOutreach}
                  className="w-full px-4 py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-colors"
                >
                  + Regenerate Variants
                </button>
              </div>

              {/* Right: Editable View */}
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Edit & Finalize</h3>
                {editableEmail && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                      <input
                        type="text"
                        value={editableEmail.subject}
                        onChange={(e) =>
                          setEditableEmail({ ...editableEmail, subject: e.target.value })
                        }
                        className="w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Body</label>
                      <textarea
                        value={editableEmail.body}
                        onChange={(e) =>
                          setEditableEmail({ ...editableEmail, body: e.target.value })
                        }
                        rows={12}
                        className="w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                      />
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => {
                          if (editableEmail) {
                            copyToClipboard(`${editableEmail.subject}\n\n${editableEmail.body}`);
                          }
                        }}
                        className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                      >
                        Copy to Clipboard
                      </button>
                      <button
                        onClick={() => {
                          // TODO: Implement approval/send logic
                          alert('DM approved! (Send functionality coming soon)');
                        }}
                        className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        Approve & Send
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Social Posts Modal */}
        {outreachData?.social_posts && showSocialModal && (
          <div className="bg-white rounded-lg border-2 border-gray-200 shadow-lg overflow-hidden">
            <div className="bg-gradient-to-r from-purple-500 to-purple-600 px-6 py-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">📱 Social Media Posts</h2>
              <button
                onClick={() => setShowSocialModal(false)}
                className="text-white hover:text-purple-100"
              >
                ×
              </button>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Select Variant</h3>
                {outreachData.social_posts.map((post, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSocialVariantChange(idx)}
                    className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                      selectedSocialIndex === idx
                        ? 'border-purple-500 bg-purple-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <span className="font-medium text-gray-900">Variant {post.variant}</span>
                    <p className="text-sm text-gray-700 mt-2 line-clamp-3">{post.caption}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {post.hashtags.map((tag, i) => (
                        <span key={i} className="text-xs text-purple-600">#{tag}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Edit & Finalize</h3>
                {editableSocial && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Caption</label>
                      <textarea
                        value={editableSocial.caption}
                        onChange={(e) =>
                          setEditableSocial({ ...editableSocial, caption: e.target.value })
                        }
                        rows={6}
                        className="w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Hashtags</label>
                      <input
                        type="text"
                        value={editableSocial.hashtags.join(', ')}
                        onChange={(e) =>
                          setEditableSocial({
                            ...editableSocial,
                            hashtags: e.target.value.split(',').map(t => t.trim()),
                          })
                        }
                        placeholder="tag1, tag2, tag3"
                        className="w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                    </div>
                    <button
                      onClick={() => {
                        if (editableSocial) {
                          copyToClipboard(`${editableSocial.caption}\n\n${editableSocial.hashtags.map(t => `#${t}`).join(' ')}`);
                        }
                      }}
                      className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                    >
                      Copy to Clipboard
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Toggle between Email and Social */}
        {outreachData && (
          <div className="flex space-x-2">
            <button
              onClick={() => {
                setShowEmailModal(true);
                setShowSocialModal(false);
              }}
              className={`px-4 py-2 rounded-lg transition-colors ${
                showEmailModal
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              📧 Email ({outreachData.emails.length})
            </button>
            {outreachData.social_posts && (
              <button
                onClick={() => {
                  setShowEmailModal(false);
                  setShowSocialModal(true);
                }}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  showSocialModal
                    ? 'bg-purple-600 text-white'
                    : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                📱 Social ({outreachData.social_posts.length})
              </button>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

