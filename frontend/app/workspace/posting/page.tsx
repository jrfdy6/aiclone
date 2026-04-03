'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { apiPost } from '@/lib/api-client';
import {
  ContentReservoirSupportItem,
  GeneratedContentResponse,
  GeneratedFragmentPromotionResponse,
  GeneratedOptionBrief,
  UndoGeneratedFragmentPromotionResponse,
  humanizeBrainTargetLabel,
} from '@/app/workspace/generatedFragmentUtils';
import PromotableInlineText from '@/app/workspace/PromotableInlineText';

type PostingMode = 'post' | 'comment';
type ContentCategory = 'value' | 'sales' | 'personal';
type ContentSourceMode = 'persona_only' | 'selected_source' | 'recent_signals';

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

type PostingQueryState = {
  mode: PostingMode;
  autoplay: boolean;
  title: string;
  summary: string;
  hook: string;
  sourceUrl: string;
  sourcePath: string;
  priorityLane: string;
  sourceKind: string;
  routeReason: string;
  targetFile: string;
  section: string;
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
  { value: 'sales', label: 'Sales' },
  { value: 'personal', label: 'Personal' },
];

const CONTENT_SOURCE_OPTIONS: { value: ContentSourceMode; label: string; hint: string }[] = [
  { value: 'persona_only', label: 'Persona only', hint: 'Generate from Johnnie canon and your prompt, not from a live source.' },
  { value: 'selected_source', label: 'Selected source', hint: 'Use this source card as the main anchor for the draft.' },
  { value: 'recent_signals', label: 'Recent signals', hint: 'Blend recent relevant source material into the draft.' },
];

function mapAudienceFromLane(lane: string) {
  const normalized = lane.trim().toLowerCase();
  if (['ai', 'ops-pm', 'tech_ai'].includes(normalized)) return 'tech_ai';
  if (['admissions', 'enrollment-management', 'education'].includes(normalized)) return 'education_admissions';
  if (['program-leadership', 'current-role', 'leadership'].includes(normalized)) return 'leadership';
  if (['entrepreneurship', 'entrepreneurs'].includes(normalized)) return 'entrepreneurs';
  return 'general';
}

function normalizeCommentLane(lane: string) {
  const normalized = lane.trim().toLowerCase();
  if (!normalized) return 'current-role';
  return normalized;
}

function buildFallbackCommentText(parts: string[]) {
  return parts.map((part) => part.trim()).filter(Boolean).join('\n\n');
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
  const safeSearchParams = searchParams ?? new URLSearchParams();
  const initialQuery = useMemo<PostingQueryState>(
    () => ({
      mode: safeSearchParams.get('mode') === 'comment' ? 'comment' : 'post',
      autoplay: safeSearchParams.get('autoplay') === '1',
      title: safeSearchParams.get('title') ?? '',
      summary: safeSearchParams.get('summary') ?? '',
      hook: safeSearchParams.get('hook') ?? '',
      sourceUrl: safeSearchParams.get('sourceUrl') ?? '',
      sourcePath: safeSearchParams.get('sourcePath') ?? '',
      priorityLane: safeSearchParams.get('priorityLane') ?? '',
      sourceKind: safeSearchParams.get('sourceKind') ?? '',
      routeReason: safeSearchParams.get('routeReason') ?? '',
      targetFile: safeSearchParams.get('targetFile') ?? '',
      section: safeSearchParams.get('section') ?? '',
    }),
    [safeSearchParams],
  );

  const [activeMode, setActiveMode] = useState<PostingMode>(initialQuery.mode);
  const [topic, setTopic] = useState(initialQuery.title);
  const [context, setContext] = useState(
    buildFallbackCommentText([initialQuery.summary, initialQuery.hook, initialQuery.routeReason]),
  );
  const [audience, setAudience] = useState(mapAudienceFromLane(initialQuery.priorityLane));
  const [sourceMode, setSourceMode] = useState<ContentSourceMode>(
    initialQuery.title || initialQuery.sourceUrl || initialQuery.summary ? 'selected_source' : 'persona_only',
  );
  const [category, setCategory] = useState<ContentCategory>('value');
  const [commentLane, setCommentLane] = useState(normalizeCommentLane(initialQuery.priorityLane));
  const [postLoading, setPostLoading] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);
  const [postOptions, setPostOptions] = useState<string[]>([]);
  const [postOptionBriefs, setPostOptionBriefs] = useState<GeneratedOptionBrief[]>([]);
  const [postSupportItems, setPostSupportItems] = useState<ContentReservoirSupportItem[]>([]);
  const [providerTrace, setProviderTrace] = useState<string | null>(null);
  const [commentLoading, setCommentLoading] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const [commentPreview, setCommentPreview] = useState<PreviewItem | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [brainPromotionStatus, setBrainPromotionStatus] = useState<string | null>(null);
  const [, setPromotingFragmentKey] = useState<string | null>(null);
  const [autoRunKey, setAutoRunKey] = useState<string | null>(null);

  const tabs = useMemo(() => postingWorkspaceTabs(), []);

  useEffect(() => {
    setActiveMode(initialQuery.mode);
    setTopic(initialQuery.title);
    setContext(buildFallbackCommentText([initialQuery.summary, initialQuery.hook, initialQuery.routeReason]));
    setAudience(mapAudienceFromLane(initialQuery.priorityLane));
    setSourceMode(initialQuery.title || initialQuery.sourceUrl || initialQuery.summary ? 'selected_source' : 'persona_only');
    setCommentLane(normalizeCommentLane(initialQuery.priorityLane));
    setPostOptions([]);
    setCommentPreview(null);
    setPostError(null);
    setCommentError(null);
    setProviderTrace(null);
    setPostOptionBriefs([]);
    setPostSupportItems([]);
    setCopyStatus(null);
    setBrainPromotionStatus(null);
    setPromotingFragmentKey(null);
  }, [initialQuery]);

  const handleGeneratePost = useCallback(async () => {
    setPostLoading(true);
    setPostError(null);
    setPostOptionBriefs([]);
    setPostSupportItems([]);
    try {
      const sourceAttached = sourceMode === 'selected_source' || sourceMode === 'recent_signals';
      const topicToSend = sourceAttached ? topic || initialQuery.title || 'operator insight' : topic || 'operator insight';
      const contextToSend = sourceAttached
        ? context || buildFallbackCommentText([initialQuery.summary, initialQuery.hook, initialQuery.routeReason])
        : context || '';
      const response = await apiPost<GeneratedContentResponse>('/api/content-generation/generate', {
        user_id: 'johnnie_fields',
        topic: topicToSend,
        context: contextToSend,
        content_type: 'linkedin_post',
        category,
        tone: 'expert_direct',
        audience,
        source_mode: sourceMode,
      });
      const options = Array.isArray(response?.options) ? response.options.filter((option) => typeof option === 'string' && option.trim().length > 0) : [];
      setPostOptions(options);
      setPostOptionBriefs(Array.isArray(response?.diagnostics?.planned_option_briefs) ? response.diagnostics.planned_option_briefs : []);
      setPostSupportItems(Array.isArray(response?.diagnostics?.content_reservoir_support) ? response.diagnostics.content_reservoir_support : []);
      const trace = (response?.diagnostics?.llm_provider_trace ?? [])
        .map((item) => [item.provider, item.actual_model, item.status].filter(Boolean).join(' · '))
        .join(' → ');
      setProviderTrace(trace || null);
      setBrainPromotionStatus(null);
      if (options.length === 0) {
        setPostError('No post options were returned.');
      }
    } catch (error) {
      setPostError(error instanceof Error ? error.message : 'Unable to generate post options right now.');
    } finally {
      setPostLoading(false);
    }
  }, [audience, category, context, initialQuery.hook, initialQuery.routeReason, initialQuery.summary, initialQuery.title, sourceMode, topic]);

  const handlePromoteFragment = useCallback(
    async (fragmentText: string, optionText: string, optionIndex: number) => {
      const fragmentKey = `${optionIndex}:${fragmentText}`;
      setPromotingFragmentKey(fragmentKey);
      setBrainPromotionStatus(`Saving "${fragmentText.slice(0, 48)}..." to Brain...`);
      try {
        const response = await apiPost<GeneratedFragmentPromotionResponse>('/api/content-generation/promote-fragment', {
          user_id: 'johnnie_fields',
          fragment_text: fragmentText,
          option_text: optionText,
          option_index: optionIndex,
          topic: topic || initialQuery.title || 'operator insight',
          audience,
          category,
          content_type: 'linkedin_post',
          source_mode: sourceMode,
          support_items: postSupportItems,
          option_brief: postOptionBriefs[optionIndex] ?? null,
        });
        setBrainPromotionStatus(
          response?.message || `Saved to ${humanizeBrainTargetLabel(response?.target_file, response?.target_label)}.`,
        );
        return { deltaId: response?.delta_id };
      } catch (error) {
        setBrainPromotionStatus(error instanceof Error ? error.message : 'Unable to save this fragment to Brain right now.');
        throw error;
      } finally {
        setPromotingFragmentKey(null);
      }
    },
    [audience, category, initialQuery.title, postOptionBriefs, postSupportItems, sourceMode, topic],
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
      setBrainPromotionStatus(`Saving "${fragmentText.slice(0, 48)}..." to Brain...`);
      try {
        const response = await apiPost<GeneratedFragmentPromotionResponse>('/api/content-generation/promote-fragment', {
          user_id: 'johnnie_fields',
          fragment_text: fragmentText,
          option_text: optionText,
          option_index: null,
          topic: topicValue || initialQuery.title || topic || 'operator insight',
          audience,
          category,
          content_type: 'linkedin_post',
          source_mode: sourceMode,
          support_items: supportItems,
          option_brief: null,
        });
        setBrainPromotionStatus(
          response?.message || `Saved to ${humanizeBrainTargetLabel(response?.target_file, response?.target_label)}.`,
        );
        return { deltaId: response?.delta_id };
      } catch (error) {
        setBrainPromotionStatus(error instanceof Error ? error.message : 'Unable to save this fragment to Brain right now.');
        throw error;
      } finally {
        setPromotingFragmentKey(null);
      }
    },
    [audience, category, initialQuery.title, sourceMode, topic],
  );

  const handleUndoPromotedFragment = useCallback(async (deltaId: string) => {
    setBrainPromotionStatus('Removing from canon...');
    const response = await apiPost<UndoGeneratedFragmentPromotionResponse>('/api/content-generation/undo-promoted-fragment', {
      delta_id: deltaId,
    });
    setBrainPromotionStatus(response?.message || 'Removed from canon.');
  }, []);

  const handleGenerateComment = useCallback(async () => {
    setCommentLoading(true);
    setCommentError(null);
    const fallbackText = buildFallbackCommentText([initialQuery.title, initialQuery.summary, initialQuery.hook, initialQuery.routeReason]);
    try {
      let response: { preview_item?: PreviewItem };
      try {
        response = await apiPost('/api/workspace/ingest-signal', {
          url: initialQuery.sourceUrl || undefined,
          text: initialQuery.sourceUrl ? undefined : fallbackText,
          title: initialQuery.title || undefined,
          priority_lane: commentLane || 'current-role',
        });
      } catch (firstError) {
        if (!initialQuery.sourceUrl || !fallbackText) {
          throw firstError;
        }
        response = await apiPost('/api/workspace/ingest-signal', {
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
  }, [commentLane, initialQuery.hook, initialQuery.routeReason, initialQuery.sourceUrl, initialQuery.summary, initialQuery.title]);

  useEffect(() => {
    const key = JSON.stringify({
      mode: initialQuery.mode,
      title: initialQuery.title,
      summary: initialQuery.summary,
      sourceUrl: initialQuery.sourceUrl,
      lane: initialQuery.priorityLane,
    });
    if (!initialQuery.autoplay || autoRunKey === key) {
      return;
    }
    setAutoRunKey(key);
    if (initialQuery.mode === 'comment') {
      void handleGenerateComment();
      return;
    }
    void handleGeneratePost();
  }, [autoRunKey, handleGenerateComment, handleGeneratePost, initialQuery]);

  async function handleCopy(text: string, label: string) {
    try {
      await copyToClipboard(text);
      setCopyStatus(`${label} copied.`);
    } catch (error) {
      setCopyStatus(error instanceof Error ? error.message : 'Unable to copy right now.');
    }
  }

  const previewVariant = useMemo(() => {
    if (!commentPreview?.lens_variants) {
      return null;
    }
    return commentPreview.lens_variants[commentLane] ?? null;
  }, [commentLane, commentPreview]);

  const commentDraft = previewVariant?.comment?.trim() || commentPreview?.comment_draft?.trim() || '';
  const shortComment = previewVariant?.short_comment?.trim() || '';
  const repostDraft = previewVariant?.repost?.trim() || commentPreview?.repost_draft?.trim() || '';

  return (
    <RuntimePage module="ops" tabs={tabs} maxWidth="1420px">
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
              href="/brain"
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
              <input value={topic} onChange={(event) => setTopic(event.target.value)} style={fieldStyle} />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '12px' }}>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Audience</span>
                <select value={audience} onChange={(event) => setAudience(event.target.value)} style={fieldStyle}>
                  {AUDIENCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Source basis</span>
                <select value={sourceMode} onChange={(event) => setSourceMode(event.target.value as ContentSourceMode)} style={fieldStyle}>
                  {CONTENT_SOURCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'grid', gap: '6px' }}>
                <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Category</span>
                <select value={category} onChange={(event) => setCategory(event.target.value as ContentCategory)} style={fieldStyle}>
                  {CATEGORY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p style={{ color: '#64748b', fontSize: '12px', margin: '-4px 0 0' }}>
              {CONTENT_SOURCE_OPTIONS.find((option) => option.value === sourceMode)?.hint}
            </p>
            <label style={{ display: 'grid', gap: '6px' }}>
              <span style={{ color: '#cbd5f5', fontSize: '13px' }}>Context</span>
              <textarea value={context} onChange={(event) => setContext(event.target.value)} rows={8} style={textareaStyle} />
            </label>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <button onClick={() => void handleGeneratePost()} disabled={postLoading} style={primaryButtonStyle('#38bdf8')}>
                {postLoading ? 'Generating…' : 'Generate post options'}
              </button>
              {providerTrace && <span style={{ color: '#94a3b8', fontSize: '12px' }}>Model trace: {providerTrace}</span>}
              {postError && <span style={{ color: '#f87171', fontSize: '12px' }}>{postError}</span>}
            </div>
            {brainPromotionStatus && (
              <p style={{ color: brainPromotionLooksErrored(brainPromotionStatus) ? '#f87171' : '#34d399', fontSize: '12px', margin: 0 }}>
                {brainPromotionStatus}
              </p>
            )}
            <div style={{ display: 'grid', gap: '12px' }}>
              {postOptions.map((option, index) => (
                <article key={`post-option-${index}`} style={resultCardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <InlinePill label={`Option ${index + 1}`} tone="#38bdf8" />
                    <button onClick={() => void handleCopy(option, `Post option ${index + 1}`)} style={secondaryButtonStyle('#38bdf8')}>
                      Copy
                    </button>
                  </div>
                  <PromotableInlineText
                    text={option}
                    textStyle={resultTextStyle}
                    tone="#38bdf8"
                    hoverHint="Canon"
                    onCanon={(fragment) => handlePromoteFragment(fragment, option, index)}
                    onUndo={handleUndoPromotedFragment}
                  />
                </article>
              ))}
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
                    hoverHint="Canon"
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
                    hoverHint="Canon"
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
                    hoverHint="Canon"
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
    <RuntimePage module="ops" tabs={postingWorkspaceTabs()} maxWidth="1420px">
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
