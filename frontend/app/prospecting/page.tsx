'use client';

import { useState } from 'react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function ProspectingPage() {
  const [activeTab, setActiveTab] = useState<'analyze' | 'outreach'>('analyze');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  
  const [prospectIds, setProspectIds] = useState<string>('');
  const [audienceProfile, setAudienceProfile] = useState({
    brand_name: '',
    brand_voice: '',
    target_pain_points: '',
    value_propositions: '',
    industry_focus: '',
    custom_guidelines: ''
  });
  const [generatedPrompt, setGeneratedPrompt] = useState<string>('');
  const [analysisResults, setAnalysisResults] = useState<string>('');
  const [outreachProspectId, setOutreachProspectId] = useState<string>('');
  const [outreachPrompt, setOutreachPrompt] = useState<string>('');

  const showStatus = (message: string, isError = false) => {
    setStatusMessage(message);
    setTimeout(() => setStatusMessage(''), 3000);
  };

  const generateAnalysisPrompt = async () => {
    if (!prospectIds.trim()) {
      showStatus('Please enter at least one prospect ID', true);
      return;
    }

    if (!API_URL) {
      showStatus('NEXT_PUBLIC_API_URL is not configured.', true);
      return;
    }

    setLoading(true);
    setStatusMessage('');
    try {
      const ids = prospectIds.split(',').map(id => id.trim()).filter(Boolean);
      
      const response = await fetch(`${API_URL}/api/prospects/manual/prompts/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prospect_ids: ids,
          user_id: 'dev-user',
          audience_profile: {
            brand_name: audienceProfile.brand_name || undefined,
            brand_voice: audienceProfile.brand_voice || undefined,
            target_pain_points: audienceProfile.target_pain_points 
              ? audienceProfile.target_pain_points.split(',').map(p => p.trim())
              : undefined,
            value_propositions: audienceProfile.value_propositions
              ? audienceProfile.value_propositions.split(',').map(v => v.trim())
              : undefined,
            industry_focus: audienceProfile.industry_focus || undefined,
            custom_guidelines: audienceProfile.custom_guidelines || undefined
          }
        })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `Failed to generate prompt: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.prompt?.full_prompt) {
        setGeneratedPrompt(data.prompt.full_prompt);
        showStatus('Prompt generated! Copy it to ChatGPT.');
      } else {
        throw new Error('Invalid response format');
      }
    } catch (error: any) {
      showStatus(error.message || 'Failed to generate prompt', true);
    } finally {
      setLoading(false);
    }
  };

  const generateOutreachPrompt = async () => {
    if (!outreachProspectId.trim()) {
      showStatus('Please enter a prospect ID', true);
      return;
    }

    if (!API_URL) {
      showStatus('NEXT_PUBLIC_API_URL is not configured.', true);
      return;
    }

    setLoading(true);
    setStatusMessage('');
    try {
      const response = await fetch(`${API_URL}/api/outreach/manual/prompts/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prospect_id: outreachProspectId.trim(),
          user_id: 'dev-user',
          audience_profile: {
            brand_name: audienceProfile.brand_name || undefined,
            brand_voice: audienceProfile.brand_voice || undefined,
            value_propositions: audienceProfile.value_propositions
              ? audienceProfile.value_propositions.split(',').map(v => v.trim())
              : undefined,
            target_pain_points: audienceProfile.target_pain_points
              ? audienceProfile.target_pain_points.split(',').map(p => p.trim())
              : undefined
          },
          preferred_tone: 'professional',
          include_social: true
        })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `Failed to generate prompt: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.prompt?.full_prompt) {
        setOutreachPrompt(data.prompt.full_prompt);
        showStatus('Outreach prompt generated! Copy it to ChatGPT.');
      } else {
        throw new Error('Invalid response format');
      }
    } catch (error: any) {
      showStatus(error.message || 'Failed to generate prompt', true);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      showStatus('Prompt copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      showStatus('Unable to copy to clipboard', true);
    }
  };

  const uploadAnalysisResults = async () => {
    if (!analysisResults.trim()) {
      showStatus('Please paste the analysis results from ChatGPT', true);
      return;
    }

    if (!API_URL) {
      showStatus('NEXT_PUBLIC_API_URL is not configured.', true);
      return;
    }

    setLoading(true);
    setStatusMessage('');
    try {
      let parsedResults;
      try {
        parsedResults = JSON.parse(analysisResults);
      } catch {
        throw new Error('Invalid JSON format. Please paste valid JSON from ChatGPT.');
      }

      if (!parsedResults.prospects || !Array.isArray(parsedResults.prospects)) {
        throw new Error('Invalid format. Expected { prospects: [...] }');
      }

      const response = await fetch(`${API_URL}/api/prospects/manual/upload-analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          results: parsedResults.prospects.map((p: any) => ({
            prospect_id: p.prospect_id,
            analysis: {
              summary: p.summary,
              fit_likelihood: p.fit_likelihood,
              suggested_outreach_angle: p.suggested_outreach_angle,
              reasoning: p.reasoning,
              confidence_score: p.confidence_score
            }
          })),
          user_id: 'dev-user'
        })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || 'Failed to upload results');
      }

      const data = await response.json();
      showStatus(`Uploaded ${data.uploaded_count || parsedResults.prospects.length} analysis results!`);
      setAnalysisResults('');
    } catch (error: any) {
      showStatus(error.message || 'Failed to upload results', true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="space-y-3">
          <p className="text-sm text-gray-500">
            <Link href="/" className="text-blue-600 underline">
              ← Back to Home
            </Link>
          </p>
          <div>
            <h1 className="text-4xl font-bold text-gray-900">AI-Assisted Prospecting</h1>
            <p className="mt-2 text-lg text-gray-600">
              Generate prompts for ChatGPT, analyze prospects, and create outreach drafts
            </p>
          </div>
        </header>

        {statusMessage && (
          <div className={`rounded border p-3 text-sm ${
            statusMessage.includes('Error') || statusMessage.includes('Failed') || statusMessage.includes('Invalid')
              ? 'border-red-200 bg-red-50 text-red-700'
              : 'border-green-200 bg-green-50 text-green-700'
          }`}>
            {statusMessage}
          </div>
        )}

        <div className="space-y-6">
          <div className="flex space-x-1 rounded-lg border bg-white p-1">
            <button
              onClick={() => setActiveTab('analyze')}
              className={`flex-1 rounded px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'analyze'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Analyze Prospects
            </button>
            <button
              onClick={() => setActiveTab('outreach')}
              className={`flex-1 rounded px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'outreach'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Generate Outreach
            </button>
          </div>

          {activeTab === 'analyze' && (
            <div className="space-y-6">
              <section className="rounded border bg-white p-6">
                <h2 className="mb-2 text-2xl font-semibold">Step 1: Configure Audience Profile</h2>
                <p className="mb-4 text-sm text-gray-600">
                  Set up your brand details and target audience information
                </p>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium">Brand Name</label>
                    <input
                      type="text"
                      value={audienceProfile.brand_name}
                      onChange={(e) => setAudienceProfile({...audienceProfile, brand_name: e.target.value})}
                      placeholder="Your Company"
                      className="mt-1 w-full rounded border px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Brand Voice</label>
                    <input
                      type="text"
                      value={audienceProfile.brand_voice}
                      onChange={(e) => setAudienceProfile({...audienceProfile, brand_voice: e.target.value})}
                      placeholder="Professional and friendly"
                      className="mt-1 w-full rounded border px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Target Pain Points (comma-separated)</label>
                    <input
                      type="text"
                      value={audienceProfile.target_pain_points}
                      onChange={(e) => setAudienceProfile({...audienceProfile, target_pain_points: e.target.value})}
                      placeholder="Manual processes are slow, Need better automation"
                      className="mt-1 w-full rounded border px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Value Propositions (comma-separated)</label>
                    <input
                      type="text"
                      value={audienceProfile.value_propositions}
                      onChange={(e) => setAudienceProfile({...audienceProfile, value_propositions: e.target.value})}
                      placeholder="Saves 10+ hours per week, Improves efficiency"
                      className="mt-1 w-full rounded border px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Industry Focus</label>
                    <input
                      type="text"
                      value={audienceProfile.industry_focus}
                      onChange={(e) => setAudienceProfile({...audienceProfile, industry_focus: e.target.value})}
                      placeholder="SaaS"
                      className="mt-1 w-full rounded border px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium">Custom Guidelines</label>
                    <input
                      type="text"
                      value={audienceProfile.custom_guidelines}
                      onChange={(e) => setAudienceProfile({...audienceProfile, custom_guidelines: e.target.value})}
                      placeholder="Focus on time savings and ROI"
                      className="mt-1 w-full rounded border px-3 py-2"
                    />
                  </div>
                </div>
              </section>

              <section className="rounded border bg-white p-6">
                <h2 className="mb-2 text-2xl font-semibold">Step 2: Generate Analysis Prompt</h2>
                <p className="mb-4 text-sm text-gray-600">
                  Enter prospect IDs and generate a prompt to analyze them
                </p>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium">Prospect IDs (comma-separated)</label>
                    <input
                      type="text"
                      value={prospectIds}
                      onChange={(e) => setProspectIds(e.target.value)}
                      placeholder="test-prospect-001, test-prospect-002"
                      className="mt-1 w-full rounded border px-3 py-2"
                    />
                    <p className="mt-1 text-sm text-gray-500">
                      Enter prospect IDs separated by commas
                    </p>
                  </div>
                  
                  <button
                    onClick={generateAnalysisPrompt}
                    disabled={loading || !prospectIds.trim()}
                    className="w-full rounded bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50"
                  >
                    {loading ? 'Generating...' : 'Generate Analysis Prompt'}
                  </button>

                  {generatedPrompt && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="block text-sm font-medium">Generated Prompt (Copy to ChatGPT)</label>
                        <button
                          onClick={() => copyToClipboard(generatedPrompt)}
                          className="rounded border px-3 py-1 text-sm hover:bg-gray-50"
                        >
                          {copied ? '✓ Copied!' : 'Copy'}
                        </button>
                      </div>
                      <textarea
                        value={generatedPrompt}
                        readOnly
                        className="min-h-[300px] w-full rounded border p-3 font-mono text-sm"
                      />
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded border bg-white p-6">
                <h2 className="mb-2 text-2xl font-semibold">Step 3: Upload Analysis Results</h2>
                <p className="mb-4 text-sm text-gray-600">
                  Paste the JSON response from ChatGPT and upload it
                </p>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium">ChatGPT Analysis Results (JSON)</label>
                    <textarea
                      value={analysisResults}
                      onChange={(e) => setAnalysisResults(e.target.value)}
                      placeholder='{"prospects": [{"prospect_id": "...", "summary": "...", ...}]}'
                      className="mt-1 min-h-[200px] w-full rounded border p-3 font-mono text-sm"
                    />
                  </div>
                  
                  <button
                    onClick={uploadAnalysisResults}
                    disabled={loading || !analysisResults.trim()}
                    className="w-full rounded bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50"
                  >
                    {loading ? 'Uploading...' : 'Upload Results'}
                  </button>
                </div>
              </section>
            </div>
          )}

          {activeTab === 'outreach' && (
            <section className="rounded border bg-white p-6">
              <h2 className="mb-2 text-2xl font-semibold">Generate Outreach Prompt</h2>
              <p className="mb-4 text-sm text-gray-600">
                Create email and social media outreach drafts for approved prospects
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium">Prospect ID</label>
                  <input
                    type="text"
                    value={outreachProspectId}
                    onChange={(e) => setOutreachProspectId(e.target.value)}
                    placeholder="test-prospect-001"
                    className="mt-1 w-full rounded border px-3 py-2"
                  />
                  <p className="mt-1 text-sm text-gray-500">
                    Enter the ID of an approved prospect
                  </p>
                </div>
                
                <button
                  onClick={generateOutreachPrompt}
                  disabled={loading || !outreachProspectId.trim()}
                  className="w-full rounded bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50"
                >
                  {loading ? 'Generating...' : 'Generate Outreach Prompt'}
                </button>

                {outreachPrompt && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="block text-sm font-medium">Generated Outreach Prompt (Copy to ChatGPT)</label>
                      <button
                        onClick={() => copyToClipboard(outreachPrompt)}
                        className="rounded border px-3 py-1 text-sm hover:bg-gray-50"
                      >
                        {copied ? '✓ Copied!' : 'Copy'}
                      </button>
                    </div>
                    <textarea
                      value={outreachPrompt}
                      readOnly
                      className="min-h-[300px] w-full rounded border p-3 font-mono text-sm"
                    />
                  </div>
                )}
              </div>
            </section>
          )}

          <section className="rounded border bg-white p-6">
            <h2 className="mb-4 text-2xl font-semibold">Quick Guide</h2>
            <div className="space-y-3 text-sm">
              <div className="flex items-start gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded border text-xs font-medium">1</span>
                <div>
                  <p className="font-semibold">Configure your audience profile</p>
                  <p className="text-gray-600">Enter your brand details and target audience information</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded border text-xs font-medium">2</span>
                <div>
                  <p className="font-semibold">Generate prompts</p>
                  <p className="text-gray-600">Click "Generate" to create prompts ready for ChatGPT</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded border text-xs font-medium">3</span>
                <div>
                  <p className="font-semibold">Copy to ChatGPT</p>
                  <p className="text-gray-600">Copy the generated prompt and paste it into ChatGPT</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded border text-xs font-medium">4</span>
                <div>
                  <p className="font-semibold">Upload results</p>
                  <p className="text-gray-600">Paste ChatGPT's JSON response and upload it to save</p>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

