'use client';

import { useState, useEffect } from 'react';
import { getApiUrl } from '@/lib/api-client';

type ProspectContextPanelProps = {
  prospectId?: string;
  prospectName?: string;
  prospectCompany?: string;
};

export default function ProspectContextPanel({ prospectId, prospectName, prospectCompany }: ProspectContextPanelProps) {
  const [insights, setInsights] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (prospectId) {
      loadInsights();
    }
  }, [prospectId]);

  const loadInsights = async () => {
    setLoading(true);
    // Mock insights - will be replaced with API call
    setTimeout(() => {
      setInsights({
        risk_factors: ['Limited budget', 'Long sales cycle'],
        warm_intro_suggestions: ['Connect through LinkedIn mutual connection: John Doe'],
        outreach_angle: 'Focus on ROI and cost savings for K-12 schools',
        lead_priority: 'High - 92% fit score',
      });
      setLoading(false);
    }, 500);
  };

  if (!prospectId) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-2">Auto Insights</h3>
        <p className="text-sm text-gray-500">Select a prospect to see AI-powered insights</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-2">Auto Insights</h3>
        <p className="text-sm text-gray-500">Loading insights...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <h3 className="font-semibold text-gray-900">Auto Insights for {prospectName || 'Selected Prospect'}</h3>
      
      {insights && (
        <>
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Risk Factors</h4>
            <ul className="space-y-1">
              {insights.risk_factors?.map((factor: string, idx: number) => (
                <li key={idx} className="text-sm text-gray-600 flex items-center">
                  <span className="text-red-500 mr-2">⚠</span>
                  {factor}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Warm Intro Suggestions</h4>
            <p className="text-sm text-gray-600">{insights.warm_intro_suggestions?.[0]}</p>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Outreach Angle</h4>
            <p className="text-sm text-gray-600">{insights.outreach_angle}</p>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Lead Priority</h4>
            <p className="text-sm font-medium text-green-600">{insights.lead_priority}</p>
          </div>
        </>
      )}
    </div>
  );
}

