'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { outreachAPI, type OutreachSequence } from '@/lib/api';

export default function OutreachPage() {
  const params = useParams();
  const router = useRouter();
  const prospectId = params.prospectId as string;
  const [user_id] = useState('demo-user-123'); // TODO: Get from auth
  const [sequenceType, setSequenceType] = useState('3-step');
  const [selectedVariant, setSelectedVariant] = useState<Record<string, number>>({});

  const queryClient = useQueryClient();

  // Generate sequence
  const { data: sequenceData, isLoading, refetch } = useQuery({
    queryKey: ['outreach-sequence', prospectId, sequenceType],
    queryFn: () => outreachAPI.generateSequence(user_id, prospectId, sequenceType),
    enabled: !!prospectId,
  });

  const sequence = sequenceData?.sequence;

  // Track engagement mutation
  const trackEngagementMutation = useMutation({
    mutationFn: ({ outreach_type, engagement_status, engagement_data }: any) =>
      outreachAPI.trackEngagement(user_id, prospectId, outreach_type, engagement_status, engagement_data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['outreach-sequence'] });
    },
  });

  const handleVariantSelect = (step: string, variant: number) => {
    setSelectedVariant({ ...selectedVariant, [step]: variant });
  };

  const handleMarkSent = async (step: string, outreachType: string) => {
    await trackEngagementMutation.mutateAsync({
      outreach_type: outreachType,
      engagement_status: 'sent',
    });
    alert(`Marked ${step} as sent!`);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="mx-auto max-w-4xl">
          <div className="rounded-lg bg-white p-8 text-center shadow">
            <div className="text-gray-500">Generating outreach sequence...</div>
          </div>
        </div>
      </div>
    );
  }

  if (!sequence) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="mx-auto max-w-4xl">
          <div className="rounded-lg bg-white p-8 shadow">
            <h1 className="mb-4 text-2xl font-bold">Generate Outreach Sequence</h1>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700">Sequence Type</label>
              <select
                value={sequenceType}
                onChange={(e) => setSequenceType(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2"
              >
                <option value="3-step">3-Step Sequence</option>
                <option value="5-step">5-Step Sequence</option>
                <option value="7-step">7-Step Sequence</option>
                <option value="soft_nudge">Soft Nudge</option>
                <option value="direct_cta">Direct CTA</option>
              </select>
            </div>
            <button
              onClick={() => refetch()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
            >
              Generate Sequence
            </button>
          </div>
        </div>
      </div>
    );
  }

  const steps = [
    { key: 'connection_request', label: 'Connection Request', data: sequence.connection_request },
    { key: 'initial_dm', label: 'Initial DM', data: sequence.initial_dm },
    { key: 'followup_1', label: 'Follow-up 1', data: sequence.followup_1 },
    { key: 'followup_2', label: 'Follow-up 2', data: sequence.followup_2 },
    { key: 'followup_3', label: 'Follow-up 3', data: sequence.followup_3 },
  ].filter(step => step.data);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <button
              onClick={() => router.back()}
              className="mb-2 text-sm text-gray-500 hover:text-gray-700"
            >
              ← Back to Prospects
            </button>
            <h1 className="text-3xl font-bold text-gray-900">Outreach Sequence</h1>
            <p className="mt-1 text-sm text-gray-500">
              Prospect: {prospectId} | Segment: {sequence.segment} | Type: {sequence.sequence_type}
            </p>
          </div>
          <div className="flex space-x-3">
            <button
              onClick={() => refetch()}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Regenerate
            </button>
          </div>
        </div>

        {steps.map((step, index) => {
          const variants = step.data?.variants || [];
          const selectedVar = selectedVariant[step.key] || 1;

          return (
            <div key={step.key} className="mb-6 rounded-lg bg-white shadow">
              <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      Step {index + 1}: {step.label}
                    </h3>
                    <p className="text-sm text-gray-500">Choose a variant and review before sending</p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      sequence.current_step >= index
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {sequence.current_step >= index ? 'Ready' : 'Pending'}
                  </span>
                </div>
              </div>

              <div className="p-6">
                {/* Variant Selector */}
                <div className="mb-4 flex space-x-2">
                  {variants.map((variant: any) => (
                    <button
                      key={variant.variant}
                      onClick={() => handleVariantSelect(step.key, variant.variant)}
                      className={`rounded-lg border-2 px-4 py-2 text-sm font-medium transition-colors ${
                        selectedVar === variant.variant
                          ? 'border-blue-600 bg-blue-50 text-blue-700'
                          : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                      }`}
                    >
                      Variant {variant.variant}
                    </button>
                  ))}
                </div>

                {/* Selected Message Preview */}
                {variants.length > 0 && (
                  <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="mb-2 text-sm font-medium text-gray-700">
                      Selected Message (Variant {selectedVar}):
                    </div>
                    <div className="whitespace-pre-wrap rounded bg-white p-4 text-sm text-gray-900">
                      {variants.find((v: any) => v.variant === selectedVar)?.message || variants[0]?.message}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex space-x-3">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(
                        variants.find((v: any) => v.variant === selectedVar)?.message || ''
                      );
                      alert('Message copied to clipboard!');
                    }}
                    className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Copy to Clipboard
                  </button>
                  <button
                    onClick={() => handleMarkSent(step.key, step.key === 'connection_request' ? 'connection_request' : step.key)}
                    className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                  >
                    Mark as Sent
                  </button>
                  <a
                    href={`https://linkedin.com`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    Open LinkedIn →
                  </a>
                </div>
              </div>
            </div>
          );
        })}

        {/* Engagement Tracking */}
        <div className="mt-6 rounded-lg bg-white shadow">
          <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
            <h3 className="text-lg font-semibold text-gray-900">Track Engagement</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => {
                  trackEngagementMutation.mutate({
                    outreach_type: 'initial_dm',
                    engagement_status: 'replied',
                    engagement_data: { reply_text: 'Positive response' },
                  });
                }}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
              >
                Mark as Replied
              </button>
              <button
                onClick={() => {
                  trackEngagementMutation.mutate({
                    outreach_type: 'initial_dm',
                    engagement_status: 'meeting_booked',
                    engagement_data: { meeting_scheduled: true },
                  });
                }}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Mark Meeting Booked
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

