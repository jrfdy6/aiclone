'use client';

import { useState } from 'react';

type MessageOptimizationPanelProps = {
  message?: string;
};

export default function MessageOptimizationPanel({ message }: MessageOptimizationPanelProps) {
  const [optimization, setOptimization] = useState<any>(null);

  // Mock optimization - will be replaced with API call
  const analyzeMessage = () => {
    if (!message) return;
    setOptimization({
      sentiment_score: 85,
      personalization_score: 72,
      rewrite_options: [
        'More personal opening',
        'Stronger value proposition',
        'Clearer call-to-action',
      ],
    });
  };

  if (!message) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-2">Message Optimization</h3>
        <p className="text-sm text-gray-500">Enter a message to get optimization suggestions</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Message Optimization</h3>
        <button
          onClick={analyzeMessage}
          className="text-sm text-blue-600 hover:underline"
        >
          Analyze
        </button>
      </div>

      {optimization && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-1">Sentiment Score</h4>
              <div className="text-2xl font-bold text-green-600">{optimization.sentiment_score}%</div>
            </div>
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-1">Personalization</h4>
              <div className="text-2xl font-bold text-blue-600">{optimization.personalization_score}%</div>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Rewrite Options</h4>
            <ul className="space-y-2">
              {optimization.rewrite_options?.map((option: string, idx: number) => (
                <li key={idx} className="text-sm text-gray-600 flex items-center">
                  <span className="text-blue-500 mr-2">→</span>
                  {option}
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}

