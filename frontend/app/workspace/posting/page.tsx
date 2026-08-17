'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { controlApiGet, controlApiPost } from '@/lib/control-api';
import {
  buildFallbackText,
  hasSeededSource,
  mapAudienceFromLane,
  normalizeContentCategory,
  readWorkspaceComposerQuery,
  toWorkspaceSourceCard,
  type ContentCategory,
} from '@/app/workspace/workspace-composer';
import {
  codexJobStatusHint,
  codexJobStatusLabel,
  codexJobStatusTone,
  ContentReservoirSupportItem,
  EvidenceAnswers,
  EvidenceClarification,
  GeneratedContentResponse,
  GeneratedContentDiagnostics,
  GeneratedFragmentPromotionResult,
  GeneratedFragmentPromotionResponse,
  GeneratedOptionBrief,
  LocalCodexJobCreateResponse,
  LocalCodexJobStatusResponse,
  OwnerReviewHandoffResponse,
  UndoGeneratedFragmentPromotionResponse,
  humanizeBrainTargetLabel,
} from '@/app/workspace/generatedFragmentUtils';
import {
  GenerationReceiptSummary,
  isOptionEditoriallyReady,
  OptionCriticReceipt,
} from '@/app/workspace/GenerationReceiptPanel';
import PromotableInlineText from '@/app/workspace/PromotableInlineText';
import {
  FeeziePrivateRuntimeStatusBadge,
  isFeeziePrivateRuntimeContextReady,
  type FeeziePrivateRuntimeContextStatus,
  type FeeziePrivateRuntimeLoadState,
} from '@/app/workspace/FeeziePrivateRuntimeStatus';

type PostingMode = 'post' | 'comment';
type ContentSourceMode = 'persona_only' | 'reservoir_ranked' | 'selected_source' | 'recent_signals';
type GroundingMode = 'canon_only' | 'canon_reservoir' | 'canon_recent_reservoir';
type TopicSourceMode = 'manual' | 'source_card';

type PreviewVariant = {
  comment?: string;
  short_comment?: string;
  repost?: string;
};

type PreviewItem = {
  title?: string;
  author?: string;
  source_url?: string;
  why_it_matters?: string;
  summary?: string;
  comment_draft?: string;
  repost_draft?: string;
  lens_variants?: Record<string, PreviewVariant>;
};

type PostingWorkspaceSnapshot = {
  private_runtime_context_status?: FeeziePrivateRuntimeContextStatus;
};

const AUDIENCE_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'education_admissions', label: 'Education / Admissions' },
  { value: 'tech_ai', label: 'Tech / AI' },
  { value: 'leadership', label: 'Leadership / Management' },
  { value: 'entrepreneurs', label: 'Entrepreneurs / Founders' },
];

const CATEGORY_OPTIONS: { value: ContentCategory; label: string }[] = [
  { value: 'value', label: 'Value' },
  { value: 'invitation', label: 'Invitation' },
  { value: 'personal', label: 'Personal' },
];

const GROUNDING_MODE_OPTIONS: { value: GroundingMode; label: string; hint: string }[] = [
  { value: 'canon_reservoir', label: 'Canon + reservoir', hint: 'Default writing mode. Keep canon active and pull in the ranked reservoir of stories, proof, and reusable context.' },
  { value: 'canon_recent_reservoir', label: 'Canon + recent reservoir', hint: 'Keep canon active but bias toward the newest reservoir support when you want a fresher angle.' },
  { value: 'canon_only', label: 'Canon only', hint: 'Use the owner canon only, with no reservoir support layered in.' },
];

const TOPIC_SOURCE_OPTIONS: { value: TopicSourceMode; label: string; hint: string }[] = [
  { value: 'source_card', label: 'Source card', hint: 'Use this source card to shape the topic and context before generation.' },
  { value: 'manual', label: 'Manual topic', hint: 'Use the topic and context you typed here.' },
];

function normalizeCommentLane(lane: string) {
  const normalized = lane.trim().toLowerCase();
  if (!normalized) return 'current-role';
  return normalized;
}

function mapGroundingModeToSourceMode(mode: GroundingMode): ContentSourceMode {
  if (mode === 'canon_only') return 'persona_only';
  if (mode === 'canon_recent_reservoir') return 'recent_signals';
  return 'reservoir_ranked';
}

function copyToClipboard(text: string) {
  if (!text.trim() || typeof navigator === 'undefined' || !navigator.clipboard) {
    return Promise.reject(new Error('Clipboard is not available.'));
  }
  return navigator.clipboard.writeText(text);
}

function postingWorkspaceTabs() {
  return [
    {
      key: 'posting',
      label: 'Posting Workspace',
      active: true,
      onSelect: () => undefined,
    },
  ];
}

function PostingWorkspaceClient() {
  const searchParams = useSearchParams();
  const initialQuery = useMemo(() => readWorkspaceComposerQuery(searchParams), [searchParams]);
  const sourceCard = useMemo(() => toWorkspaceSourceCard(initialQuery), [initialQuery]);

  const [activeMode, setActiveMode] = useState<PostingMode>(initialQuery.mode);
  const [topic, setTopic] = useState(initialQuery.title);
  const [context, setContext] = useState(
    buildFallbackText([initialQuery.summary, initialQuery.hook, initialQuery.routeReason, initialQuery.ownerReaction]),
  );
  const [audience, setAudience] = useState<string>(mapAudienceFromLane(initialQuery.audience || initialQuery.priorityLane));
  const [groundingMode, setGroundingMode] = useState<GroundingMode>('canon_reservoir');
  const [topicSourceMode, setTopicSourceMode] = useState<TopicSourceMode>(
    hasSeededSource(initialQuery) ? 'source_card' : 'manual',
  );
  const [category, setCategory] = useState<ContentCategory>('value');
  const [commentLane, setCommentLane] = useState(normalizeCommentLane(initialQuery.priorityLane));
  const [postLoading, setPostLoading] = useState(false);
  const [codexJobId, setCodexJobId] = useState<string | null>(null);
  const [codexJobStatus, setCodexJobStatus] = useState<string | null>(null);
  const [codexJobError, setCodexJobError] = useState<string | null>(null);
  const [codexActionLoading, setCodexActionLoading] = useState<'cancel' | null>(null);
  const [postError, setPostError] = useState<string | null>(null);
  const [postOptions, setPostOptions] = useState<string[]>([]);
  const [postOptionBriefs, setPostOptionBriefs] = useState<GeneratedOptionBrief[]>([]);
  const [postSupportItems, setPostSupportItems] = useState<ContentReservoirSupportItem[]>([]);
  const [postDiagnostics, setPostDiagnostics] = useState<GeneratedContentDiagnostics | undefined>();
  const [providerTrace, setProviderTrace] = useState<string | null>(null);
  const [evidenceAnswers, setEvidenceAnswers] = useState<EvidenceAnswers>({});
  const [evidenceClarification, setEvidenceClarification] = useState<EvidenceClarification | null>(null);
  const [evidenceAnswerDraft, setEvidenceAnswerDraft] = useState('');
  const [commentLoading, setCommentLoading] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const [commentPreview, setCommentPreview] = useState<PreviewItem | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [reviewActionLoading, setReviewActionLoading] = useState<number | null>(null);
  const [reviewHandoffs, setReviewHandoffs] = useState<Record<number, OwnerReviewHandoffResponse>>({});
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [brainPromotionStatus, setBrainPromotionStatus] = useState<string | null>(null);
  const [, setPromotingFragmentKey] = useState<string | null>(null);
  const [autoRunKey, setAutoRunKey] = useState<string | null>(null);
  const [privateRuntimeStatus, setPrivateRuntimeStatus] = useState<FeeziePrivateRuntimeContextStatus | null>(null);
  const [privateRuntimeLoadState, setPrivateRuntimeLoadState] = useState<FeeziePrivateRuntimeLoadState>('loading');

  const clearEvidenceIntake = useCallback(() => {
    setEvidenceAnswers({});
    setEvidenceClarification(null);
    setEvidenceAnswerDraft('');
  }, []);

  const tabs = useMemo(() => postingWorkspaceTabs(), []);

  useEffect(() => {
    setActiveMode(initialQuery.mode);
    setTopic(initialQuery.title);
    setContext(buildFallbackText([initialQuery.summary, initialQuery.hook, initialQuery.routeReason, initialQuery.ownerReaction]));
    setAudience(mapAudienceFromLane(initialQuery.audience || initialQuery.priorityLane));
    setGroundingMode('canon_reservoir');
    setTopicSourceMode(hasSeededSource(initialQuery) ? 'source_card' : 'manual');
    setCommentLane(normalizeCommentLane(initialQuery.priorityLane));
    setPostOptions([]);
    setCommentPreview(null);
    setPostError(null);
    setCodexJobId(null);
    setCodexJobStatus(null);
    setCodexJobError(null);
    setCommentError(null);
    setProviderTrace(null);
    setPostOptionBriefs([]);
    setPostSupportItems([]);
    setPostDiagnostics(undefined);
    setCopyStatus(null);
    setReviewActionLoading(null);
    setReviewHandoffs({});
    setReviewError(null);
    setBrainPromotionStatus(null);
    setPromotingFragmentKey(null);
    setEvidenceAnswers({});
    setEvidenceClarification(null);
    setEvidenceAnswerDraft('');
  }, [initialQuery]);

  useEffect(() => {
    let active = true;
    setPrivateRuntimeLoadState('loading');
    void controlApiGet<PostingWorkspaceSnapshot>('/api/workspace/linkedin-os-snapshot')
      .then((payload) => {
        if (!active) return;
        setPrivateRuntimeStatus(payload.private_runtime_context_status ?? null);
        setPrivateRuntimeLoadState('live');
      })
      .catch(() => {
        if (!active) return;
        setPrivateRuntimeStatus(null);
        setPrivateRuntimeLoadState('error');
      });
    return () => {
      active = false;
    };
  }, []);

  const activeSourceCard = topicSourceMode === 'source_card' ? sourceCard : null;
  const effectiveSourceMode = useMemo(
    () => (activeSourceCard ? 'selected_source' : mapGroundingModeToSourceMode(groundingMode)),
    [activeSourceCard, groundingMode],
  );
  const feezieGenerationReady = privateRuntimeLoadState === 'live'
    && isFeeziePrivateRuntimeContextReady(privateRuntimeStatus);

  const handleTopicSourceModeChange = useCallback(
    (nextMode: TopicSourceMode) => {
      clearEvidenceIntake();
      setTopicSourceMode(nextMode);
      if (nextMode === 'source_card') {
        setTopic(initialQuery.title);
        setContext(buildFallbackText([initialQuery.summary, initialQuery.hook, initialQuery.routeReason, initialQuery.ownerReaction]));
        setAudience(mapAudienceFromLane(initialQuery.audience || initialQuery.priorityLane));
      }
    },
    [clearEvidenceIntake, initialQuery.audience, initialQuery.hook, initialQuery.ownerReaction, initialQuery.priorityLane, initialQuery.routeReason, initialQuery.summary, initialQuery.title],
  );

  const resolvePostInputs = useCallback(() => {
    if (topicSourceMode === 'source_card') {
      return {
        topicToSend: topic || initialQuery.title || '',
        contextToSend: context || buildFallbackText([initialQuery.summary, initialQuery.hook, initialQuery.routeReason, initialQuery.ownerReaction]),
      };
    }
    return {
      topicToSend: topic || '',
      contextToSend: context || '',
    };
  }, [context, initialQuery.hook, initialQuery.ownerReaction, initialQuery.routeReason, initialQuery.summary, initialQuery.title, topic, topicSourceMode]);

  const applyGeneratedResponse = useCallback((response: GeneratedContentResponse) => {
    const options = Array.isArray(response?.options) ? response.options.filter((option) => typeof option === 'string' && option.trim().length > 0) : [];
    setPostOptions(options);
    setPostOptionBriefs(Array.isArray(response?.diagnostics?.planned_option_briefs) ? response.diagnostics.planned_option_briefs : []);
    setPostSupportItems(Array.isArray(response?.diagnostics?.content_reservoir_support) ? response.diagnostics.content_reservoir_support : []);
    setPostDiagnostics(response?.diagnostics);
    const trace = (response?.diagnostics?.llm_provider_trace ?? [])
      .map((item) => [item.provider, item.actual_model, item.reasoning_effort, item.status].filter(Boolean).join(' · '))
      .join(' → ');
    setProviderTrace(trace || null);
    setBrainPromotionStatus(null);
    if (options.length === 0) {
      setPostError('No post options were returned.');
      return;
    }
    setPostError(null);
  }, []);

  const queueLocalCodexPost = useCallback(async (answers: EvidenceAnswers) => {
    if (!feezieGenerationReady) {
      throw new Error('FEEZIE generation stays closed until private runtime context is fully ready.');
    }
    const { topicToSend, contextToSend } = resolvePostInputs();
    if (!topicToSend.trim()) {
      throw new Error('Choose a source or enter a specific topic before starting the evidence check.');
    }
    const response = await controlApiPost<LocalCodexJobCreateResponse>('/api/content-generation/codex-jobs', {
      user_id: 'owner',
      topic: topicToSend,
      context: contextToSend,
      content_type: 'linkedin_post',
      category: normalizeContentCategory(category) ?? 'value',
      tone: 'conversational',
      audience,
      source_mode: effectiveSourceMode,
      workspace_slug: 'linkedin-content-os',
      ...(Object.keys(answers).length > 0 ? { evidence_answers: answers } : {}),
      ...(activeSourceCard ? { source_card: activeSourceCard } : {}),
    });
    if (response?.status === 'clarification_required' && response.clarification_key && response.clarification_question) {
      setCodexJobId(null);
      setCodexJobStatus(null);
      setEvidenceClarification({ key: response.clarification_key, question: response.clarification_question });
      setEvidenceAnswerDraft('');
      setProviderTrace('evidence check · one detail needed');
      return;
    }
    if (response?.status === 'blocked') {
      throw new Error(response?.message || 'This idea is not admitted to drafting yet.');
    }
    if (!response?.job_id) {
      throw new Error(response?.message || 'Local job did not return an id.');
    }
    setEvidenceClarification(null);
    setEvidenceAnswerDraft('');
    setCodexJobId(response.job_id);
    setCodexJobStatus(response.status || 'pending');
    setCodexJobError(null);
    setProviderTrace('local_worker · queued');
    setBrainPromotionStatus(null);
  }, [activeSourceCard, audience, category, effectiveSourceMode, feezieGenerationReady, resolvePostInputs]);

  const resetPostRunState = useCallback(() => {
    setPostError(null);
    setCodexJobError(null);
    setCodexActionLoading(null);
    setCodexJobId(null);
    setCodexJobStatus(null);
    setPostOptions([]);
    setPostOptionBriefs([]);
    setPostSupportItems([]);
    setPostDiagnostics(undefined);
    setReviewActionLoading(null);
    setReviewHandoffs({});
    setReviewError(null);
  }, []);

  const handleGeneratePost = useCallback(async () => {
    const freshAnswers: EvidenceAnswers = {};
    setPostLoading(true);
    resetPostRunState();
    setEvidenceAnswers(freshAnswers);
    setEvidenceClarification(null);
    setEvidenceAnswerDraft('');
    setProviderTrace('evidence check · searching AI Clone / FEEZIE records');
    try {
      await queueLocalCodexPost(freshAnswers);
    } catch (error) {
      setCodexJobId(null);
      setCodexJobStatus(null);
      setCodexJobError(error instanceof Error ? error.message : 'Unable to start the evidence check right now.');
      setProviderTrace(null);
    } finally {
      setPostLoading(false);
    }
  }, [queueLocalCodexPost, resetPostRunState]);

  const handleGeneratePostWithCodex = useCallback(async () => {
    setPostLoading(true);
    resetPostRunState();
    setProviderTrace('evidence check · revalidating');
    try {
      await queueLocalCodexPost(evidenceAnswers);
    } catch (error) {
      setCodexJobId(null);
      setCodexJobStatus(null);
      setCodexJobError(error instanceof Error ? error.message : 'Unable to queue local generation right now.');
      setProviderTrace(null);
    } finally {
      setPostLoading(false);
    }
  }, [evidenceAnswers, queueLocalCodexPost, resetPostRunState]);

  const submitEvidenceClarification = useCallback(async () => {
    if (!evidenceClarification || !evidenceAnswerDraft.trim()) return;
    const mergedAnswers: EvidenceAnswers = {
      ...evidenceAnswers,
      [evidenceClarification.key]: evidenceAnswerDraft.trim(),
    };
    setEvidenceAnswers(mergedAnswers);
    setPostLoading(true);
    setCodexJobError(null);
    setProviderTrace('evidence check · validating your detail');
    try {
      await queueLocalCodexPost(mergedAnswers);
    } catch (error) {
      setCodexJobId(null);
      setCodexJobStatus(null);
      setCodexJobError(error instanceof Error ? error.message : 'Unable to continue the evidence check right now.');
      setProviderTrace(null);
    } finally {
      setPostLoading(false);
    }
  }, [evidenceAnswerDraft, evidenceAnswers, evidenceClarification, queueLocalCodexPost]);

  const cancelCodexJob = useCallback(async () => {
    if (!codexJobId) return;
    setCodexActionLoading('cancel');
    setCodexJobError(null);
    try {
      const response = await controlApiPost<LocalCodexJobStatusResponse>(`/api/content-generation/codex-jobs/${codexJobId}/cancel`, {});
      const nextStatus = response?.status || 'canceled';
      setCodexJobStatus(nextStatus);
      setCodexJobError(null);
      setPostError(null);
      setProviderTrace(`local_worker · ${nextStatus}`);
    } catch (error) {
      setCodexJobError(error instanceof Error ? error.message : 'Unable to cancel the local run right now.');
    } finally {
      setCodexActionLoading(null);
    }
  }, [codexJobId]);

  useEffect(() => {
    if (!codexJobId || ['completed', 'failed', 'canceled'].includes(codexJobStatus ?? '')) {
      return;
    }
    let cancelled = false;

    const poll = async () => {
      try {
        const response = await controlApiGet<LocalCodexJobStatusResponse>(`/api/content-generation/codex-jobs/${codexJobId}`);
        if (cancelled) return;
        const nextStatus = response?.status || 'pending';
        setCodexJobStatus(nextStatus);
        if (nextStatus === 'completed' && response.result) {
          applyGeneratedResponse(response.result);
          setCodexJobError(null);
          return;
        }
        if (nextStatus === 'failed' || nextStatus === 'canceled') {
          setCodexJobError(response?.error_message || 'Local generation failed.');
          setProviderTrace(`local_worker · ${nextStatus}`);
          return;
        }
        setProviderTrace(nextStatus === 'running' ? 'local_worker · running' : 'local_worker · queued');
      } catch (error) {
        if (cancelled) return;
        setCodexJobError(error instanceof Error ? error.message : 'Unable to poll local job status right now.');
      }
    };

    void poll();
    const intervalId = window.setInterval(() => {
      void poll();
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [applyGeneratedResponse, codexJobId, codexJobStatus]);

  const handlePromoteFragment = useCallback(
    async (fragmentText: string, optionText: string, optionIndex: number) => {
      const { topicToSend } = resolvePostInputs();
      const fragmentKey = `${optionIndex}:${fragmentText}`;
      setPromotingFragmentKey(fragmentKey);
      setBrainPromotionStatus(`Submitting "${fragmentText.slice(0, 48)}..." for Brain review...`);
      try {
        const response = await controlApiPost<GeneratedFragmentPromotionResponse>('/api/content-generation/promote-fragment', {
          user_id: 'owner',
          fragment_text: fragmentText,
          option_text: optionText,
          option_index: optionIndex,
          topic: topicToSend,
          audience,
          category,
          content_type: 'linkedin_post',
          source_mode: effectiveSourceMode,
          support_items: postSupportItems,
          option_brief: postOptionBriefs[optionIndex] ?? null,
        });
        setBrainPromotionStatus(
          response?.message || `Queued for owner review in ${humanizeBrainTargetLabel(response?.target_file, response?.target_label)}.`,
        );
        return {
          deltaId: response?.delta_id,
          targetLabel: humanizeBrainTargetLabel(response?.target_file, response?.target_label),
        } satisfies GeneratedFragmentPromotionResult;
      } catch (error) {
        setBrainPromotionStatus(error instanceof Error ? error.message : 'Unable to save this fragment to Brain right now.');
        throw error;
      } finally {
        setPromotingFragmentKey(null);
      }
    },
    [audience, category, effectiveSourceMode, postOptionBriefs, postSupportItems, resolvePostInputs],
  );

  const handlePromoteSurfaceFragment = useCallback(
    async ({
      fragmentText,
      optionText,
      fragmentKey,
      topicValue,
      supportItems = [],
    }: {
      fragmentText: string;
      optionText: string;
      fragmentKey: string;
      topicValue: string;
      supportItems?: ContentReservoirSupportItem[];
    }) => {
      setPromotingFragmentKey(fragmentKey);
      setBrainPromotionStatus(`Submitting "${fragmentText.slice(0, 48)}..." for Brain review...`);
      try {
        const response = await controlApiPost<GeneratedFragmentPromotionResponse>('/api/content-generation/promote-fragment', {
          user_id: 'owner',
          fragment_text: fragmentText,
          option_text: optionText,
          option_index: null,
          topic: topicValue || initialQuery.title || topic || 'operator insight',
          audience,
          category,
          content_type: 'linkedin_post',
          source_mode: effectiveSourceMode,
          support_items: supportItems,
          option_brief: null,
        });
        setBrainPromotionStatus(
          response?.message || `Queued for owner review in ${humanizeBrainTargetLabel(response?.target_file, response?.target_label)}.`,
        );
        return {
          deltaId: response?.delta_id,
          targetLabel: humanizeBrainTargetLabel(response?.target_file, response?.target_label),
        } satisfies GeneratedFragmentPromotionResult;
      } catch (error) {
        setBrainPromotionStatus(error instanceof Error ? error.message : 'Unable to save this fragment to Brain right now.');
        throw error;
      } finally {
        setPromotingFragmentKey(null);
      }
    },
    [audience, category, effectiveSourceMode, initialQuery.title, topic],
  );

  const handleUndoPromotedFragment = useCallback(async (deltaId: string) => {
    setBrainPromotionStatus('Withdrawing the Brain review proposal...');
    const response = await controlApiPost<UndoGeneratedFragmentPromotionResponse>('/api/content-generation/undo-promoted-fragment', {
      delta_id: deltaId,
    });
    setBrainPromotionStatus(response?.message || 'Brain review proposal withdrawn.');
  }, []);

  const handleGenerateComment = useCallback(async () => {
    setCommentLoading(true);
    setCommentError(null);
    const fallbackText = buildFallbackText([
      initialQuery.title,
      initialQuery.summary,
      initialQuery.hook,
      initialQuery.routeReason,
      initialQuery.ownerReaction,
    ]);
    try {
      let response: { preview_item?: PreviewItem };
      try {
        response = await controlApiPost('/api/workspace/ingest-signal', {
          url: initialQuery.sourceUrl || undefined,
          text: initialQuery.sourceUrl ? undefined : fallbackText,
          title: initialQuery.title || undefined,
          priority_lane: commentLane || 'current-role',
        });
      } catch (firstError) {
        if (!initialQuery.sourceUrl || !fallbackText) {
          throw firstError;
        }
        response = await controlApiPost('/api/workspace/ingest-signal', {
          text: fallbackText,
          title: initialQuery.title || undefined,
          priority_lane: commentLane || 'current-role',
        });
      }
      setCommentPreview(response?.preview_item ?? null);
      if (!response?.preview_item) {
        setCommentError('No comment preview was returned.');
      }
    } catch (error) {
      setCommentError(error instanceof Error ? error.message : 'Unable to generate a comment preview right now.');
    } finally {
      setCommentLoading(false);
    }
  }, [
    commentLane,
    initialQuery.hook,
    initialQuery.ownerReaction,
    initialQuery.routeReason,
    initialQuery.sourceUrl,
    initialQuery.summary,
    initialQuery.title,
  ]);

  useEffect(() => {
    const key = JSON.stringify({
      mode: initialQuery.mode,
      title: initialQuery.title,
      summary: initialQuery.summary,
      sourceUrl: initialQuery.sourceUrl,
      lane: initialQuery.priorityLane,
      itemKey: initialQuery.itemKey,
      briefId: initialQuery.briefId,
      originType: initialQuery.originType,
      originId: initialQuery.originId,
      ownerReaction: initialQuery.ownerReaction,
    });
    if (!initialQuery.autoplay || autoRunKey === key) {
      return;
    }
    if (initialQuery.mode === 'comment') {
      setAutoRunKey(key);
      void handleGenerateComment();
      return;
    }
    if (!feezieGenerationReady) {
      return;
    }
    setAutoRunKey(key);
    void handleGeneratePost();
  }, [autoRunKey, feezieGenerationReady, handleGenerateComment, handleGeneratePost, initialQuery]);

  async function handleCopy(text: string, label: string) {
    try {
      await copyToClipboard(text);
      setCopyStatus(`${label} copied.`);
    } catch (error) {
      setCopyStatus(error instanceof Error ? error.message : 'Unable to copy right now.');
    }
  }

  const sendOptionToOwnerReview = useCallback(
    async (optionIndex: number) => {
      if (!codexJobId || codexJobStatus !== 'completed') {
        setReviewError('Finish the local Codex run before sending a draft to owner review.');
        return;
      }
      setReviewActionLoading(optionIndex);
      setReviewError(null);
      try {
        const response = await controlApiPost<OwnerReviewHandoffResponse>(
          `/api/content-generation/codex-jobs/${encodeURIComponent(codexJobId)}/send-to-review`,
          { option_index: optionIndex },
        );
        if (!response?.queue_id) {
          throw new Error(response?.message || 'Owner review did not return a queue item.');
        }
        setReviewHandoffs((current) => ({ ...current, [optionIndex]: response }));
      } catch (error) {
        setReviewError(error instanceof Error ? error.message : 'Unable to send this option to owner review.');
      } finally {
        setReviewActionLoading(null);
      }
    },
    [codexJobId, codexJobStatus],
  );

  const previewVariant = useMemo(() => {
    if (!commentPreview?.lens_variants) {
      return null;
    }
    return commentPreview.lens_variants[commentLane] ?? null;
  }, [commentLane, commentPreview]);

  const commentDraft = previewVariant?.comment?.trim() || commentPreview?.comment_draft?.trim() || '';
  const shortComment = previewVariant?.short_comment?.trim() || '';
  const repostDraft = previewVariant?.repost?.trim() || commentPreview?.repost_draft?.trim() || '';
  const codexInFlight = Boolean(codexJobId) && !['completed', 'failed', 'canceled'].includes(codexJobStatus ?? '');
  const localJobCompleted = codexJobStatus === 'completed';
  const codexJobTone = codexJobStatusTone(codexJobStatus);
  const usedCodexTerminal = (providerTrace ?? '').includes('codex_terminal');

  return (
    <RuntimePage module="workspace" tabs={tabs} maxWidth="1420px">
      <section style={{ display: 'grid', gap: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <p style={{ color: '#fb923c', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.14em', margin: '0 0 8px' }}>
              Posting Workspace
            </p>
            <h1 style={{ color: 'white', fontSize: '30px', margin: '0 0 10px' }}>Brief to post handoff</h1>
            <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6, maxWidth: '760px', margin: 0 }}>
              Use the live Daily Brief card as input, then draft a post or a comment without leaving the Brain-to-Workspace flow.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <Link
              href={initialQuery.returnUrl}
              style={{
                borderRadius: '12px',
                border: '1px solid #334155',
                backgroundColor: '#020617',
                color: '#cbd5f5',
                padding: '10px 14px',
                textDecoration: 'none',
                fontSize: '13px',
                fontWeight: 600,
              }}
            >
              Back to Brain
            </Link>
            <Link
              href="/workspace"
              style={{
                borderRadius: '12px',
                border: '1px solid #fb923c',
                backgroundColor: 'rgba(154,52,18,0.18)',
                color: 'white',
                padding: '10px 14px',
                textDecoration: 'none',
                fontSize: '13px',
                fontWeight: 600,
              }}
            >
              Open workspace hub
            </Link>
          </div>
        </div>

        <section
          style={{
            borderRadius: '16px',
            border: '1px solid #1f2937',
            backgroundColor: '#050b19',
            padding: '18px',
            display: 'grid',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div>
              <p style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 6px' }}>Source card</p>
              <h2 style={{ color: 'white', fontSize: '22px', margin: '0 0 8px' }}>{initialQuery.title || 'Untitled brief item'}</h2>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {initialQuery.section && <InlinePill label={humanizeSnakeCase(initialQuery.section)} tone="#818cf8" />}
                {initialQuery.priorityLane && <InlinePill label={humanizeSnakeCase(initialQuery.priorityLane)} tone="#22c55e" />}
                {initialQuery.sourceKind && <InlinePill label={humanizeSnakeCase(initialQuery.sourceKind)} tone="#64748b" />}
                {initialQuery.targetFile && <InlinePill label={humanizeTargetFileLabel(initialQuery.targetFile)} tone="#64748b" />}
              </div>
            </div>
            {initialQuery.sourceUrl && (
              <a
                href={initialQuery.sourceUrl}
                target="_blank"
                rel="noreferrer"
                style={{
                  borderRadius: '999px',
                  border: '1px solid #334155',
                  backgroundColor: '#020617',
                  color: '#cbd5f5',
                  padding: '8px 12px',
                  fontSize: '12px',
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
              >
                Open source
              </a>
            )}
          </div>
          {initialQuery.summary && <p style={{ color: '#dbe7ff', fontSize: '14px', lineHeight: 1.65, margin: 0 }}>{initialQuery.summary}</p>}
          {initialQuery.hook && <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>Hook: {initialQuery.hook}</p>}
          {initialQuery.routeReason && <p style={{ color: '#64748b', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>Why it matters: {initialQuery.routeReason}</p>}
          {copyStatus && <p style={{ color: copyStatus.includes('copied') ? '#34d399' : '#f87171', fontSize: '12px', margin: 0 }}>{copyStatus}</p>}
        </section>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <ModeButton active={activeMode === 'post'} label="Write post" onClick={() => setActiveMode('post')} />
          <ModeButton active={activeMode === 'comment'} label="Comment on this" onClick={() => setActiveMode('comment')} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 1fr)', gap: '18px' }}>
          <section
            style={{
              borderRadius: '16px',
              border: '1px solid #1f2937',
              backgroundColor: '#050b19',
              padding: '18px',
              display: 'grid',
              gap: '14px',
            }}
          >
            <div>
              <p style={{ color: '#38bdf8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 6px' }}>Post draft</p>
              <h3 style={{ color: 'white', fontSize: '20px', margin: 0 }}>Generate a thesis-led LinkedIn post</h3>
            </div>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Topic</span>
              <input value={topic} onChange={(event) => { clearEvidenceIntake(); setTopic(event.target.value); }} style={fieldStyle} />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '12px' }}>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Audience</span>
                <select value={audience} onChange={(event) => { clearEvidenceIntake(); setAudience(event.target.value); }} style={fieldStyle}>
                  {AUDIENCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Topic source</span>
                <select value={topicSourceMode} onChange={(event) => handleTopicSourceModeChange(event.target.value as TopicSourceMode)} style={fieldStyle}>
                  {TOPIC_SOURCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Grounding mode</span>
                <select value={groundingMode} onChange={(event) => { clearEvidenceIntake(); setGroundingMode(event.target.value as GroundingMode); }} style={fieldStyle}>
                  {GROUNDING_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Category</span>
                <select value={category} onChange={(event) => { clearEvidenceIntake(); setCategory(normalizeContentCategory(event.target.value) ?? 'value'); }} style={fieldStyle}>
                  {CATEGORY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div style={{ display: 'grid', gap: '4px', marginTop: '-4px' }}>
              <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>
                {TOPIC_SOURCE_OPTIONS.find((option) => option.value === topicSourceMode)?.hint}
              </p>
              <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>
                {GROUNDING_MODE_OPTIONS.find((option) => option.value === groundingMode)?.hint}
              </p>
              <FeeziePrivateRuntimeStatusBadge
                status={privateRuntimeStatus}
                loadState={privateRuntimeLoadState}
              />
            </div>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Context</span>
              <textarea value={context} onChange={(event) => { clearEvidenceIntake(); setContext(event.target.value); }} rows={8} style={textareaStyle} />
            </label>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button onClick={() => void handleGeneratePost()} disabled={!feezieGenerationReady || postLoading || codexInFlight || codexActionLoading !== null} style={primaryButtonStyle('#f97316')}>
                {postLoading ? 'Queueing…' : codexInFlight ? 'Running on This Mac…' : 'Queue on This Mac'}
              </button>
              {providerTrace && <span style={{ color: '#94a3b8', fontSize: '12px' }}>Model trace: {providerTrace}</span>}
              {postError && <span style={{ color: '#f87171', fontSize: '12px' }}>{postError}</span>}
              <p style={{ color: '#64748b', fontSize: '11px', lineHeight: 1.5, margin: 0, width: '100%' }}>
                FEEZIE searches the public-safe AI Clone records first. It queues the local writer only after it has a concrete action, exact problem, and observable lesson; otherwise it asks one question here.
              </p>
              {evidenceClarification && (
                <div style={{ width: '100%', borderRadius: '14px', border: '1px solid #f59e0b55', backgroundColor: '#1a1306', padding: '14px', display: 'grid', gap: '10px' }}>
                  <p style={{ color: '#fbbf24', fontSize: '13px', fontWeight: 700, margin: 0 }}>{evidenceClarification.question}</p>
                  <textarea
                    value={evidenceAnswerDraft}
                    onChange={(event) => setEvidenceAnswerDraft(event.target.value)}
                    placeholder="Give the concrete detail in language that would be safe to publish. Employer-linked names, systems, paths, and metrics are anonymized server-side."
                    rows={3}
                    style={{ ...textareaStyle, minHeight: '88px' }}
                  />
                  <div>
                    <button type="button" onClick={() => void submitEvidenceClarification()} disabled={!feezieGenerationReady || postLoading || !evidenceAnswerDraft.trim()} style={primaryButtonStyle('#f59e0b')}>
                      {postLoading ? 'Checking…' : 'Continue evidence check'}
                    </button>
                  </div>
                </div>
              )}
              {codexJobStatus && (
                <div
                  style={{
                    width: '100%',
                    borderRadius: '14px',
                    border: `1px solid ${codexJobTone}33`,
                    backgroundColor: '#07101f',
                    padding: '12px 14px',
                    display: 'grid',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    <div style={{ display: 'grid', gap: '4px' }}>
                      <span style={{ color: codexJobTone, fontSize: '12px', fontWeight: 700 }}>{codexJobStatusLabel(codexJobStatus)}</span>
                      <span style={{ color: '#94a3b8', fontSize: '12px' }}>{codexJobStatusHint(codexJobStatus)}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                      {codexInFlight && (
                        <button onClick={() => void cancelCodexJob()} disabled={codexActionLoading !== null} style={secondaryButtonStyle('#f97316')}>
                          {codexActionLoading === 'cancel' ? 'Canceling…' : 'Cancel'}
                        </button>
                      )}
                      {!codexInFlight && ['failed', 'canceled'].includes(codexJobStatus ?? '') && (
                        <button onClick={() => void handleGeneratePostWithCodex()} disabled={!feezieGenerationReady || codexActionLoading !== null || postLoading} style={secondaryButtonStyle('#f97316')}>
                          Retry Local Run
                        </button>
                      )}
                      {localJobCompleted && (
                        <InlinePill label={usedCodexTerminal ? 'Escalated to Codex Terminal' : 'Completed on This Mac'} tone="#34d399" />
                      )}
                    </div>
                  </div>
                  {codexJobError && <span style={{ color: '#fca5a5', fontSize: '12px' }}>{codexJobError}</span>}
                </div>
              )}
              {!codexJobStatus && codexJobError && <span style={{ color: '#f87171', fontSize: '12px' }}>{codexJobError}</span>}
            </div>
            {brainPromotionStatus && (
              <p style={{ color: brainPromotionLooksErrored(brainPromotionStatus) ? '#f87171' : '#34d399', fontSize: '12px', margin: 0 }}>
                {brainPromotionStatus}
              </p>
            )}
            {reviewError && <p role="alert" style={{ color: '#f87171', fontSize: '12px', margin: 0 }}>{reviewError}</p>}
            {postOptions.length > 0 && <GenerationReceiptSummary diagnostics={postDiagnostics} />}
            <div style={{ display: 'grid', gap: '12px' }}>
              {postOptions.map((option, index) => {
                const optionReady = isOptionEditoriallyReady(postDiagnostics, index);
                return (
                <article key={`post-option-${index}`} style={resultCardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <InlinePill label={`Option ${index + 1}`} tone="#38bdf8" />
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                      {reviewHandoffs[index]?.queue_id ? (
                        <Link
                          href={`/workspace?owner_review=${encodeURIComponent(reviewHandoffs[index].queue_id ?? '')}`}
                          style={{ ...secondaryButtonStyle('#22c55e'), textDecoration: 'none' }}
                        >
                          Open owner review
                        </Link>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void sendOptionToOwnerReview(index)}
                          disabled={reviewActionLoading !== null || !localJobCompleted || !optionReady}
                          style={secondaryButtonStyle('#22c55e')}
                        >
                          {reviewActionLoading === index ? 'Sending…' : optionReady ? 'Send to owner review' : 'Needs revision'}
                        </button>
                      )}
                    </div>
                  </div>
                  <OptionCriticReceipt diagnostics={postDiagnostics} optionIndex={index} />
                  {reviewHandoffs[index]?.message && (
                    <p role="status" style={{ color: '#34d399', fontSize: '12px', margin: 0 }}>{reviewHandoffs[index].message}</p>
                  )}
                  <PromotableInlineText
                    text={option}
                    textStyle={resultTextStyle}
                    tone="#38bdf8"
                    hoverHint="Propose to Brain"
                    onCanon={(fragment) => handlePromoteFragment(fragment, option, index)}
                    onUndo={handleUndoPromotedFragment}
                  />
                </article>
                );
              })}
              {postOptions.length === 0 && <EmptyMessage message="No post options yet. Generate from this source card when you are ready." />}
            </div>
          </section>

          <section
            style={{
              borderRadius: '16px',
              border: '1px solid #1f2937',
              backgroundColor: '#050b19',
              padding: '18px',
              display: 'grid',
              gap: '14px',
            }}
          >
            <div>
              <p style={{ color: '#22c55e', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 6px' }}>Comment draft</p>
              <h3 style={{ color: 'white', fontSize: '20px', margin: 0 }}>Generate a comment/repost preview</h3>
            </div>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Lane</span>
              <input value={commentLane} onChange={(event) => setCommentLane(event.target.value)} style={fieldStyle} />
            </label>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button onClick={() => void handleGenerateComment()} disabled={commentLoading} style={primaryButtonStyle('#22c55e')}>
                {commentLoading ? 'Generating…' : 'Generate comment preview'}
              </button>
              {commentError && <span style={{ color: '#f87171', fontSize: '12px' }}>{commentError}</span>}
            </div>
            {commentPreview ? (
              <div style={{ display: 'grid', gap: '12px' }}>
                <article style={resultCardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <InlinePill label="Quick reply" tone="#22c55e" />
                    <button onClick={() => void handleCopy(shortComment || commentDraft, 'Quick reply')} style={secondaryButtonStyle('#22c55e')}>
                      Copy
                    </button>
                  </div>
                  <PromotableInlineText
                    text={shortComment || commentDraft || 'No quick reply available.'}
                    promotableText={shortComment || commentDraft}
                    textStyle={resultTextStyle}
                    tone="#22c55e"
                    hoverHint="Propose to Brain"
                    onCanon={(fragment, fullText) =>
                      handlePromoteSurfaceFragment({
                        fragmentText: fragment,
                        optionText: fullText,
                        fragmentKey: `comment-preview:quick-reply:${fragment}`,
                        topicValue: initialQuery.title || topic || 'operator insight',
                        supportItems: [
                          {
                            title: initialQuery.title,
                            text: fullText,
                            source_path: initialQuery.sourcePath,
                            source_url: initialQuery.sourceUrl,
                          },
                        ],
                      })
                    }
                    onUndo={handleUndoPromotedFragment}
                  />
                </article>
                <article style={resultCardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <InlinePill label="Suggested comment" tone="#38bdf8" />
                    <button onClick={() => void handleCopy(commentDraft, 'Suggested comment')} style={secondaryButtonStyle('#38bdf8')}>
                      Copy
                    </button>
                  </div>
                  <PromotableInlineText
                    text={commentDraft || 'No suggested comment available.'}
                    promotableText={commentDraft}
                    textStyle={resultTextStyle}
                    tone="#38bdf8"
                    hoverHint="Propose to Brain"
                    onCanon={(fragment, fullText) =>
                      handlePromoteSurfaceFragment({
                        fragmentText: fragment,
                        optionText: fullText,
                        fragmentKey: `comment-preview:suggested-comment:${fragment}`,
                        topicValue: initialQuery.title || topic || 'operator insight',
                        supportItems: [
                          {
                            title: initialQuery.title,
                            text: fullText,
                            source_path: initialQuery.sourcePath,
                            source_url: initialQuery.sourceUrl,
                          },
                        ],
                      })
                    }
                    onUndo={handleUndoPromotedFragment}
                  />
                </article>
                <article style={resultCardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <InlinePill label="Suggested repost" tone="#f472b6" />
                    <button onClick={() => void handleCopy(repostDraft, 'Suggested repost')} style={secondaryButtonStyle('#f472b6')}>
                      Copy
                    </button>
                  </div>
                  <PromotableInlineText
                    text={repostDraft || 'No repost draft available.'}
                    promotableText={repostDraft}
                    textStyle={resultTextStyle}
                    tone="#f472b6"
                    hoverHint="Propose to Brain"
                    onCanon={(fragment, fullText) =>
                      handlePromoteSurfaceFragment({
                        fragmentText: fragment,
                        optionText: fullText,
                        fragmentKey: `comment-preview:suggested-repost:${fragment}`,
                        topicValue: initialQuery.title || topic || 'operator insight',
                        supportItems: [
                          {
                            title: initialQuery.title,
                            text: fullText,
                            source_path: initialQuery.sourcePath,
                            source_url: initialQuery.sourceUrl,
                          },
                        ],
                      })
                    }
                    onUndo={handleUndoPromotedFragment}
                  />
                </article>
              </div>
            ) : (
              <EmptyMessage message="No comment preview yet. Generate one from this source card when you want a fast response angle." />
            )}
          </section>
        </div>
      </section>
    </RuntimePage>
  );
}

function PostingWorkspaceFallback() {
  return (
    <RuntimePage module="workspace" tabs={postingWorkspaceTabs()} maxWidth="1420px">
      <section
        style={{
          borderRadius: '16px',
          border: '1px solid #1f2937',
          backgroundColor: '#050b19',
          padding: '18px',
          color: '#94a3b8',
          fontSize: '14px',
          lineHeight: 1.6,
        }}
      >
        Loading posting workspace…
      </section>
    </RuntimePage>
  );
}

export default function PostingWorkspacePage() {
  return (
    <Suspense fallback={<PostingWorkspaceFallback />}>
      <PostingWorkspaceClient />
    </Suspense>
  );
}

function humanizeSnakeCase(value: string) {
  return value
    .split(/[_-]+/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function humanizeTargetFileLabel(targetFile: string) {
  return humanizeBrainTargetLabel(targetFile);
}

function InlinePill({ label, tone }: { label: string; tone: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        borderRadius: '999px',
        border: `1px solid ${tone}55`,
        backgroundColor: `${tone}18`,
        color: tone,
        fontSize: '11px',
        fontWeight: 700,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        padding: '5px 10px',
      }}
    >
      {label}
    </span>
  );
}

function ModeButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        borderRadius: '999px',
        border: active ? '1px solid #f8fafc' : '1px solid #334155',
        backgroundColor: active ? '#0f172a' : '#020617',
        color: active ? 'white' : '#cbd5f5',
        padding: '10px 14px',
        fontSize: '13px',
        fontWeight: 700,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );
}

function EmptyMessage({ message }: { message: string }) {
  return (
    <div
      style={{
        borderRadius: '14px',
        border: '1px dashed #334155',
        backgroundColor: '#020617',
        padding: '16px',
        color: '#64748b',
        fontSize: '13px',
        lineHeight: 1.6,
      }}
    >
      {message}
    </div>
  );
}

const fieldStyle = {
  width: '100%',
  borderRadius: '10px',
  border: '1px solid #1f2937',
  backgroundColor: '#020617',
  color: 'white',
  padding: '10px 12px',
  fontSize: '13px',
};

const textareaStyle = {
  ...fieldStyle,
  resize: 'vertical' as const,
  minHeight: '120px',
  lineHeight: 1.6,
};

function primaryButtonStyle(tone: string) {
  return {
    borderRadius: '12px',
    border: `1px solid ${tone}`,
    backgroundColor: '#0f172a',
    color: 'white',
    padding: '10px 14px',
    fontSize: '13px',
    fontWeight: 700,
    cursor: 'pointer',
  };
}

function secondaryButtonStyle(tone: string) {
  return {
    borderRadius: '10px',
    border: `1px solid ${tone}`,
    backgroundColor: 'transparent',
    color: tone,
    padding: '6px 10px',
    fontSize: '12px',
    fontWeight: 700,
    cursor: 'pointer',
  };
}

const resultCardStyle = {
  borderRadius: '14px',
  border: '1px solid #1f2937',
  backgroundColor: '#020617',
  padding: '14px',
  display: 'grid',
  gap: '10px',
};

const resultTextStyle = {
  color: '#dbe7ff',
  fontSize: '14px',
  lineHeight: 1.7,
  whiteSpace: 'pre-wrap' as const,
  margin: 0,
};

function brainPromotionLooksErrored(value: string) {
  const normalized = value.toLowerCase();
  return normalized.includes('unable') || normalized.includes('failed') || normalized.includes('error');
}
