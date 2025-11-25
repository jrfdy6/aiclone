'use client';

import { useState } from 'react';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type TestResult = {
  success: boolean;
  message: string;
  data?: any;
  error?: string;
};

export default function APITestPage() {
  const [testQuery, setTestQuery] = useState('AI tools for education');
  const [maxResults, setMaxResults] = useState(5);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);

  const testGoogleSearch = async () => {
    if (!API_URL) {
      setResult({
        success: false,
        message: 'NEXT_PUBLIC_API_URL is not configured',
        error: 'Missing API URL'
      });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      // Test via LinkedIn search endpoint (uses Google Custom Search)
      const response = await fetch(`${API_URL}/api/linkedin/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: testQuery,
          max_results: maxResults,
          sort_by: 'engagement'
        })
      });

      const data = await response.json();

      if (!response.ok) {
        setResult({
          success: false,
          message: `Test failed: ${data.detail || response.statusText}`,
          error: data.detail || response.statusText,
          data: data
        });
        return;
      }

      setResult({
        success: true,
        message: `✅ Google Custom Search test successful! Found ${data.total_results || 0} results`,
        data: data
      });
    } catch (error: any) {
      setResult({
        success: false,
        message: `Test failed: ${error.message}`,
        error: error.message
      });
    } finally {
      setLoading(false);
    }
  };

  const testDetailed = async () => {
    if (!API_URL) {
      setResult({
        success: false,
        message: 'NEXT_PUBLIC_API_URL is not configured',
        error: 'Missing API URL'
      });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      // Test via LinkedIn test endpoint (provides detailed metrics)
      const response = await fetch(`${API_URL}/api/linkedin/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: testQuery,
          max_results: 3
        })
      });

      const data = await response.json();

      if (!response.ok) {
        setResult({
          success: false,
          message: `Test failed: ${data.detail || response.statusText}`,
          error: data.detail || response.statusText,
          data: data
        });
        return;
      }

      setResult({
        success: true,
        message: `✅ Detailed test successful! Found ${data.total_posts_found || 0} posts with extraction quality metrics`,
        data: data
      });
    } catch (error: any) {
      setResult({
        success: false,
        message: `Test failed: ${error.message}`,
        error: error.message
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="space-y-3">
          <p className="text-sm text-gray-500">
            <Link href="/" className="text-blue-600 underline">
              ← Back to Home
            </Link>
          </p>
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Google Custom Search Test</h1>
            <p className="mt-2 text-lg text-gray-600">
              Test Google Custom Search functionality in production
            </p>
            <p className="mt-1 text-sm text-gray-500">
              This tests Google Custom Search via the LinkedIn search endpoint
            </p>
          </div>
        </header>

        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold">Test Configuration</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Query
              </label>
              <input
                type="text"
                value={testQuery}
                onChange={(e) => setTestQuery(e.target.value)}
                placeholder="AI tools for education"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                This query will be used to search for LinkedIn posts via Google Custom Search
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Results
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value))}
                className="w-32 rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex space-x-3">
              <button
                onClick={testGoogleSearch}
                disabled={loading || !testQuery.trim()}
                className="flex-1 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Testing...' : 'Test Google Search'}
              </button>
              
              <button
                onClick={testDetailed}
                disabled={loading || !testQuery.trim()}
                className="flex-1 rounded-lg bg-purple-600 px-4 py-2 font-medium text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Testing...' : 'Test with Metrics'}
              </button>
            </div>
          </div>
        </div>

        {result && (
          <div className={`rounded-lg border p-6 ${
            result.success 
              ? 'border-green-200 bg-green-50' 
              : 'border-red-200 bg-red-50'
          }`}>
            <h3 className={`mb-2 text-lg font-semibold ${
              result.success ? 'text-green-800' : 'text-red-800'
            }`}>
              {result.success ? '✅ Test Passed' : '❌ Test Failed'}
            </h3>
            
            <p className={`mb-4 ${
              result.success ? 'text-green-700' : 'text-red-700'
            }`}>
              {result.message}
            </p>

            {result.error && (
              <div className="mb-4 rounded border border-red-300 bg-red-100 p-3">
                <p className="text-sm font-medium text-red-800">Error:</p>
                <p className="text-sm text-red-700">{result.error}</p>
              </div>
            )}

            {result.data && (
              <div className="mt-4">
                <details className="cursor-pointer">
                  <summary className="text-sm font-medium text-gray-700 mb-2">
                    View Response Data
                  </summary>
                  <pre className="mt-2 max-h-96 overflow-auto rounded border bg-gray-50 p-4 text-xs">
                    {JSON.stringify(result.data, null, 2)}
                  </pre>
                </details>
              </div>
            )}

            {result.success && result.data && (
              <div className="mt-4 space-y-2">
                <h4 className="font-medium text-gray-800">Quick Stats:</h4>
                <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
                  {result.data.total_results !== undefined && (
                    <li>Total Results: {result.data.total_results}</li>
                  )}
                  {result.data.total_posts_found !== undefined && (
                    <li>Posts Found: {result.data.total_posts_found}</li>
                  )}
                  {result.data.posts && (
                    <li>Posts Returned: {result.data.posts.length}</li>
                  )}
                  {result.data.test_metadata?.extraction_quality && (
                    <>
                      <li>Author Extraction Rate: {result.data.test_metadata.extraction_quality.author_extraction_rate}%</li>
                      <li>Engagement Extraction Rate: {result.data.test_metadata.extraction_quality.engagement_extraction_rate}%</li>
                    </>
                  )}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="rounded-lg border bg-blue-50 p-6">
          <h3 className="mb-2 text-lg font-semibold text-blue-900">How This Works</h3>
          <ul className="list-disc list-inside space-y-2 text-sm text-blue-800">
            <li>Google Custom Search is used to find LinkedIn post URLs based on your query</li>
            <li>The backend uses the Google Custom Search API to search for LinkedIn posts</li>
            <li>Firecrawl then scrapes the content from found LinkedIn post URLs</li>
            <li>Results include post content, author info, engagement metrics, and more</li>
            <li>This test verifies that Google Custom Search is working correctly in production</li>
          </ul>
        </div>

        <div className="rounded-lg border bg-yellow-50 p-6">
          <h3 className="mb-2 text-lg font-semibold text-yellow-900">Troubleshooting</h3>
          <ul className="list-disc list-inside space-y-2 text-sm text-yellow-800">
            <li><strong>Configuration Error:</strong> Check that GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID are set in backend environment variables</li>
            <li><strong>Quota Exceeded:</strong> Google Custom Search free tier allows 100 queries/day. Wait 24h or enable billing</li>
            <li><strong>No Results:</strong> Try a different search query. Some queries may not return LinkedIn posts</li>
            <li><strong>CORS Error:</strong> Make sure your frontend URL is in CORS_ADDITIONAL_ORIGINS in backend environment variables</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
