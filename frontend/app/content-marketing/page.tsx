'use client';

import { useState } from 'react';
import NavHeader from '@/components/NavHeader';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

type TabType = 'research' | 'linking' | 'microtool' | 'prd';

export default function ContentMarketingPage() {
  const [activeTab, setActiveTab] = useState<TabType>('research');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);

  // Content Research State
  const [researchTopic, setResearchTopic] = useState('');
  const [numResults, setNumResults] = useState(10);

  // Internal Linking State
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [sectionPath, setSectionPath] = useState('');
  const [numArticles, setNumArticles] = useState(10);

  // Micro Tool State
  const [toolName, setToolName] = useState('');
  const [toolDescription, setToolDescription] = useState('');
  const [targetAudience, setTargetAudience] = useState('');

  // PRD State
  const [productName, setProductName] = useState('');
  const [productDescription, setProductDescription] = useState('');
  const [targetUsers, setTargetUsers] = useState('');

  const handleContentResearch = async () => {
    if (!researchTopic.trim()) {
      setError('Please enter a research topic');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/content/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: researchTopic,
          num_results: numResults,
          include_comparison: true,
          output_format: 'markdown',
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to research content');
    } finally {
      setLoading(false);
    }
  };

  const handleInternalLinking = async () => {
    if (!websiteUrl.trim()) {
      setError('Please enter a website URL');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/content/internal-linking`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          website_url: websiteUrl,
          section_path: sectionPath || undefined,
          num_articles: numArticles,
          depth: 2,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze internal linking');
    } finally {
      setLoading(false);
    }
  };

  const handleMicroTool = async () => {
    if (!toolName.trim() || !toolDescription.trim()) {
      setError('Please fill in tool name and description');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/content/micro-tool`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool_name: toolName,
          tool_description: toolDescription,
          target_audience: targetAudience.split(',').map(s => s.trim()).filter(Boolean),
          features: [],
          output_format: 'html',
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate micro tool');
    } finally {
      setLoading(false);
    }
  };

  const handlePRD = async () => {
    if (!productName.trim() || !productDescription.trim()) {
      setError('Please fill in product name and description');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/content/prd`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_name: productName,
          product_description: productDescription,
          target_users: targetUsers.split(',').map(s => s.trim()).filter(Boolean),
          key_features: [],
          include_mvp_scope: true,
          include_user_stories: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate PRD');
    } finally {
      setLoading(false);
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'research':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Research Topic</label>
              <input
                type="text"
                value={researchTopic}
                onChange={(e) => setResearchTopic(e.target.value)}
                placeholder="e.g., best AB testing tools 2025"
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Number of Results</label>
              <input
                type="number"
                value={numResults}
                onChange={(e) => setNumResults(parseInt(e.target.value) || 10)}
                min={1}
                max={50}
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <button
              onClick={handleContentResearch}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Researching...' : 'Start Research'}
            </button>
          </div>
        );

      case 'linking':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Website URL</label>
              <input
                type="url"
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Section Path (Optional)</label>
              <input
                type="text"
                value={sectionPath}
                onChange={(e) => setSectionPath(e.target.value)}
                placeholder="/guides"
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Number of Articles</label>
              <input
                type="number"
                value={numArticles}
                onChange={(e) => setNumArticles(parseInt(e.target.value) || 10)}
                min={1}
                max={50}
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <button
              onClick={handleInternalLinking}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Analyzing...' : 'Analyze Internal Linking'}
            </button>
          </div>
        );

      case 'microtool':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Tool Name</label>
              <input
                type="text"
                value={toolName}
                onChange={(e) => setToolName(e.target.value)}
                placeholder="e.g., UTM Link Generator"
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Tool Description</label>
              <textarea
                value={toolDescription}
                onChange={(e) => setToolDescription(e.target.value)}
                placeholder="Describe what the tool does..."
                rows={4}
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Target Audience (comma-separated)</label>
              <input
                type="text"
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                placeholder="small business owner, junior marketer, freelance content creator"
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <button
              onClick={handleMicroTool}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Generating...' : 'Generate Micro Tool'}
            </button>
          </div>
        );

      case 'prd':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Product Name</label>
              <input
                type="text"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder="e.g., UTM Link Generator"
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Product Description</label>
              <textarea
                value={productDescription}
                onChange={(e) => setProductDescription(e.target.value)}
                placeholder="Describe what you want to build..."
                rows={4}
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Target Users (comma-separated)</label>
              <input
                type="text"
                value={targetUsers}
                onChange={(e) => setTargetUsers(e.target.value)}
                placeholder="small business owner, junior marketer, freelance content creator"
                className="w-full px-3 py-2 border rounded"
              />
            </div>
            <button
              onClick={handlePRD}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Generating...' : 'Generate PRD'}
            </button>
          </div>
        );
    }
  };

  return (
    <main style={{ minHeight: '100vh', backgroundColor: '#0f172a' }}>
      <NavHeader />
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        <header style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>Content Marketing Workflows</h1>
          <p style={{ color: '#9ca3af' }}>Vibe Marketing tools powered by MCPs and AI</p>
        </header>

        {/* Tabs */}
        <div style={{ borderBottom: '1px solid #475569', marginBottom: '24px' }}>
          <nav style={{ display: 'flex', gap: '16px' }}>
            {(['research', 'linking', 'microtool', 'prd'] as TabType[]).map((tab) => (
              <button
                key={tab}
                onClick={() => {
                  setActiveTab(tab);
                  setResults(null);
                  setError(null);
                }}
                style={{
                  padding: '12px 16px',
                  fontWeight: 500,
                  borderBottom: activeTab === tab ? '2px solid #3b82f6' : '2px solid transparent',
                  color: activeTab === tab ? '#3b82f6' : '#9ca3af',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                {tab === 'research' && 'Content Research'}
                {tab === 'linking' && 'Internal Linking'}
                {tab === 'microtool' && 'Micro Tools'}
                {tab === 'prd' && 'PRD Generator'}
              </button>
            ))}
          </nav>
        </div>

        {/* Error Display */}
        {error && (
          <div style={{ borderRadius: '8px', border: '1px solid #ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '12px', color: '#f87171', marginBottom: '24px' }}>
            {error}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          {/* Input Form */}
          <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>
              {activeTab === 'research' && 'Research Content'}
              {activeTab === 'linking' && 'Analyze Internal Linking'}
              {activeTab === 'microtool' && 'Generate Micro Tool'}
              {activeTab === 'prd' && 'Generate PRD'}
            </h2>
            {renderTabContent()}
          </div>

          {/* Results */}
          <div style={{ backgroundColor: '#1e293b', borderRadius: '12px', border: '1px solid #475569', padding: '24px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>Results</h2>
            {loading && <div style={{ color: '#9ca3af' }}>Processing...</div>}
            {!loading && !results && (
              <div style={{ color: '#6b7280', fontSize: '14px' }}>Results will appear here</div>
            )}
            {results && (
              <div>
                {activeTab === 'research' && results.research_content && (
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '14px', backgroundColor: '#0f172a', padding: '16px', borderRadius: '8px', overflow: 'auto', maxHeight: '400px', color: '#e2e8f0' }}>
                    {results.research_content}
                  </pre>
                )}
                {activeTab === 'linking' && results.opportunities && (
                  <div>
                    <p style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '12px' }}>
                      Found {results.total_opportunities} linking opportunities
                    </p>
                    {results.opportunities.map((opp: any, idx: number) => (
                      <div key={idx} style={{ backgroundColor: '#0f172a', padding: '12px', borderRadius: '8px', marginBottom: '8px' }}>
                        <p style={{ fontWeight: 500, color: 'white' }}>{opp.source_article} → {opp.target_article}</p>
                        <p style={{ color: '#9ca3af', marginTop: '4px' }}>{opp.anchor_text}</p>
                      </div>
                    ))}
                  </div>
                )}
                {activeTab === 'microtool' && results.html_code && (
                  <div>
                    <p style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '12px' }}>Generated HTML Tool:</p>
                    <pre style={{ whiteSpace: 'pre-wrap', fontSize: '12px', backgroundColor: '#0f172a', padding: '16px', borderRadius: '8px', overflow: 'auto', maxHeight: '400px', color: '#e2e8f0' }}>
                      {results.html_code}
                    </pre>
                  </div>
                )}
                {activeTab === 'prd' && results.prd_content && (
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: '14px', backgroundColor: '#0f172a', padding: '16px', borderRadius: '8px', overflow: 'auto', maxHeight: '400px', color: '#e2e8f0' }}>
                    {results.prd_content}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}




