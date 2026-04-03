'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { RuntimePage } from '@/components/runtime/RuntimeChrome';
import { apiFetch, apiGet, apiPost } from '@/lib/api-client';
import {
  ContentReservoirSupportItem,
  GeneratedContentResponse,
  GeneratedFragmentPromotionResponse,
  GeneratedOptionBrief,
  humanizeBrainTargetLabel,
  splitPromotableFragments,
} from '@/app/workspace/generatedFragmentUtils';

type FeedLensId =
  | 'admissions'
  | 'entrepreneurship'
  | 'current-role'
  | 'program-leadership'
  | 'enrollment-management'
  | 'ai'
  | 'ops-pm'
  | 'therapy'
  | 'referral'
  | 'personal-story';

type PostingAudience = 'general' | 'education_admissions' | 'tech_ai' | 'leadership' | 'entrepreneurs';
type ContentCategory = 'value' | 'sales' | 'personal';
type ContentType = 'cold_email' | 'linkedin_post' | 'linkedin_dm' | 'instagram_post';
type ContentSourceMode = 'persona_only' | 'selected_source' | 'recent_signals';

type VariantEvaluation = {
  lane_distinctiveness?: number;
  belief_clarity?: number;
  voice_match?: number;
  expression_quality?: number;
  source_expression_quality?: number;
  expression_delta?: number;
  overall?: number;
  warnings?: string[];
};

type FeedVariant = {
  label?: string;
  comment?: string;
  short_comment?: string;
  repost?: string;
  why_this_angle?: string;
  stance?: string;
  belief_summary?: string;
  experience_summary?: string;
  role_safety?: string;
  techniques?: string[];
  evaluation?: VariantEvaluation;
  expression_assessment?: {
    strategy?: string;
    output_structure?: string;
  };
};

type SocialFeedItem = {
  id: string;
  platform: string;
  source_type?: string;
  source_class?: string;
  unit_kind?: string;
  response_modes?: string[];
  capture_method?: string;
  title: string;
  author: string;
  source_url?: string;
  source_path?: string;
  why_it_matters?: string;
  comment_draft?: string;
  repost_draft?: string;
  lens_variants?: Partial<Record<string, FeedVariant>>;
  standout_lines?: string[];
  lenses?: string[];
  summary?: string;
  belief_assessment?: {
    stance?: string;
    belief_summary?: string;
    experience_summary?: string;
    role_safety?: string;
  };
  technique_assessment?: {
    techniques?: string[];
  };
  expression_assessment?: {
    strategy?: string;
    output_structure?: string;
  };
  evaluation?: VariantEvaluation;
  ranking: { total: number };
};

type WorkspaceFile = {
  group?: string;
  name: string;
  path: string;
  snippet?: string;
  content?: string;
  updatedAt?: string;
};

type WorkspaceSnapshot = {
  weekly_plan?: {
    generated_at?: string;
    recommendations?: {
      title: string;
      hook?: string;
      summary?: string;
      source_url?: string;
      priority_lane?: string;
    }[];
    source_counts?: {
      drafts?: number;
      media?: number;
      research?: number;
      belief_evidence?: number;
    };
  } | null;
  reaction_queue?: {
    generated_at?: string;
    counts?: {
      comment_opportunities?: number;
      post_seeds?: number;
    };
  } | null;
  social_feed?: {
    generated_at?: string;
    strategy_mode?: string;
    items?: SocialFeedItem[];
  } | null;
  feedback_summary?: {
    total_events?: number;
    average_evaluation_overall?: number | null;
    average_output_expression_quality?: number | null;
  } | null;
  workspace_files?: WorkspaceFile[];
  doc_entries?: WorkspaceFile[];
};

type FeedRefreshStatus = {
  running: boolean;
  last_run?: string | null;
  started_at?: string | null;
  error?: string | null;
};

type ContentItem = {
  id: string;
  category: ContentCategory;
  type: ContentType;
  title: string;
  content: string;
  status: 'draft' | 'ready';
  created_at: string;
  tags?: string[];
};

type QuerySeed = {
  title: string;
  summary: string;
  hook: string;
  sourceUrl: string;
  sourcePath: string;
  priorityLane: string;
  routeReason: string;
};

const CHRIS_DO_911 = {
  value: {
    ratio: 9,
    description: 'Pure value. Teaching, insights, observations. No selling mixed in.',
    icon: '📚',
    tone: '#38bdf8',
  },
  sales: {
    ratio: 1,
    description: 'Sell unabashedly. "I\'m building X. Here\'s how to get involved."',
    icon: '💰',
    tone: '#22c55e',
  },
  personal: {
    ratio: 1,
    description: 'Personal/behind-the-scenes. The real me, struggles included.',
    icon: '🙋',
    tone: '#a855f7',
  },
} satisfies Record<ContentCategory, { ratio: number; description: string; icon: string; tone: string }>;

const PERSONA = {
  name: 'Johnnie Fields',
  title: 'Director of Admissions at Fusion Academy (DC)',
  northStar: "I can't be put into a box. I'm a work in progress, pivoting into tech and data while leveraging 10+ years in education.",
  tone: 'Expert + direct, inspiring. Process Champion energy.',
};

const CONTENT_TYPES: { value: ContentType; label: string; icon: string }[] = [
  { value: 'cold_email', label: 'Cold Email', icon: '📧' },
  { value: 'linkedin_post', label: 'LinkedIn Post', icon: '📝' },
  { value: 'linkedin_dm', label: 'LinkedIn DM', icon: '💬' },
  { value: 'instagram_post', label: 'Instagram Post', icon: '📸' },
];

const CONTENT_SOURCE_OPTIONS: { value: ContentSourceMode; label: string; hint: string }[] = [
  { value: 'persona_only', label: 'Persona only', hint: 'Generate from Johnnie canon and your prompt, not from a live article.' },
  { value: 'selected_source', label: 'Selected source', hint: 'Use the selected feed item as the source anchor for the draft.' },
  { value: 'recent_signals', label: 'Recent signals', hint: 'Blend recent relevant source material into the draft.' },
];

const POST_MODE_OPTIONS: { id: FeedLensId; label: string }[] = [
  { id: 'entrepreneurship', label: 'Entrepreneurship' },
  { id: 'current-role', label: 'Current Job' },
  { id: 'program-leadership', label: 'Program Leadership' },
  { id: 'enrollment-management', label: 'Enrollment' },
  { id: 'ai', label: 'AI' },
  { id: 'ops-pm', label: 'Ops / PM' },
  { id: 'therapy', label: 'Therapy' },
  { id: 'referral', label: 'Referral' },
  { id: 'personal-story', label: 'Personal Story' },
  { id: 'admissions', label: 'Admissions' },
];

const FEED_LENS_ALIASES: Record<string, FeedLensId> = {
  admissions: 'admissions',
  entrepreneurship: 'entrepreneurship',
  'current-role': 'current-role',
  'current role': 'current-role',
  'current job': 'current-role',
  leadership: 'program-leadership',
  'program-leadership': 'program-leadership',
  'program leadership': 'program-leadership',
  enrollment: 'enrollment-management',
  'enrollment-management': 'enrollment-management',
  ai: 'ai',
  'ai-entrepreneurship': 'ai',
  'ops-pm': 'ops-pm',
  'ops / pm': 'ops-pm',
  therapy: 'therapy',
  referral: 'referral',
  'personal-story': 'personal-story',
  'personal story': 'personal-story',
};

const FEED_LENS_VARIANT_KEYS: Record<FeedLensId, string[]> = {
  admissions: ['admissions'],
  entrepreneurship: ['entrepreneurship'],
  'current-role': ['current-role', 'program-leadership'],
  'program-leadership': ['program-leadership', 'current-role'],
  'enrollment-management': ['enrollment-management'],
  ai: ['ai', 'ai-entrepreneurship'],
  'ops-pm': ['ops-pm', 'ai-entrepreneurship'],
  therapy: ['therapy', 'therapist-referral'],
  referral: ['referral', 'therapist-referral'],
  'personal-story': ['personal-story'],
};

const AUDIENCE_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'education_admissions', label: 'Education / Admissions' },
  { value: 'tech_ai', label: 'Tech / AI' },
  { value: 'leadership', label: 'Leadership / Management' },
  { value: 'entrepreneurs', label: 'Entrepreneurs / Founders' },
];

const STORAGE_KEY = 'content_pipeline_911';

function workspaceTabs() {
  return [{ key: 'workspace', label: 'Workspace', active: true, onSelect: () => undefined }];
}

function mapAudienceFromLane(lane: string): PostingAudience {
  const normalized = lane.trim().toLowerCase();
  if (['ai', 'ops-pm', 'tech_ai'].includes(normalized)) return 'tech_ai';
  if (['admissions', 'enrollment-management', 'education'].includes(normalized)) return 'education_admissions';
  if (['program-leadership', 'current-role', 'leadership'].includes(normalized)) return 'leadership';
  if (['entrepreneurship', 'entrepreneurs'].includes(normalized)) return 'entrepreneurs';
  return 'general';
}

function buildFallbackText(parts: Array<string | undefined>) {
  return parts.map((part) => (part ?? '').trim()).filter(Boolean).join('\n\n');
}

function normalizeFeedLens(value?: string | null): FeedLensId | null {
  if (!value) return null;
  return FEED_LENS_ALIASES[value.trim().toLowerCase()] ?? null;
}

function deriveSourceClass(item: SocialFeedItem) {
  const explicit = item.source_class?.trim();
  if (explicit) return explicit;
  const sourceType = item.source_type?.toLowerCase() ?? '';
  const captureMethod = item.capture_method?.toLowerCase() ?? '';
  if (item.platform === 'manual' || captureMethod === 'manual') return 'manual';
  if (['video', 'episode', 'transcript', 'audio', 'podcast'].includes(sourceType) || ['youtube', 'podcast'].includes(item.platform)) {
    return 'long_form_media';
  }
  if (['article', 'essay', 'newsletter'].includes(sourceType) || ['rss', 'substack', 'web'].includes(item.platform)) {
    return 'article';
  }
  return 'short_form';
}

function deriveUnitKind(item: SocialFeedItem, sourceClass: string) {
  const explicit = item.unit_kind?.trim();
  if (explicit) return explicit;
  if (sourceClass === 'article') return 'paragraph';
  if (sourceClass === 'long_form_media') return 'section';
  if (sourceClass === 'manual' && (item.summary?.split(/[.!?]+/).filter(Boolean).length ?? 0) <= 2) return 'claim_block';
  return 'full_post';
}

function deriveResponseModes(item: SocialFeedItem, sourceClass: string, unitKind: string) {
  const explicit = (item.response_modes ?? []).map((mode) => mode.trim()).filter(Boolean);
  if (explicit.length > 0) return explicit;
  if (sourceClass === 'long_form_media' && !['segment', 'quote_cluster', 'claim_block'].includes(unitKind)) {
    return ['post_seed', 'belief_evidence'];
  }
  return ['comment', 'repost', 'post_seed', 'belief_evidence'];
}

function getFeedVariant(item: SocialFeedItem, lens: FeedLensId) {
  for (const key of FEED_LENS_VARIANT_KEYS[lens]) {
    const variant = item.lens_variants?.[key];
    if (variant) return variant;
  }
  return null;
}

function createCommentDraft(item: SocialFeedItem, lens: FeedLensId) {
  const variant = getFeedVariant(item, lens);
  if (variant?.comment?.trim()) return variant.comment.trim();
  return item.comment_draft?.trim() || item.summary?.trim() || '';
}

function createShortCommentDraft(item: SocialFeedItem, lens: FeedLensId) {
  const variant = getFeedVariant(item, lens);
  if (variant?.short_comment?.trim()) return variant.short_comment.trim();
  return createCommentDraft(item, lens);
}

function createRepostDraft(item: SocialFeedItem, lens: FeedLensId) {
  const variant = getFeedVariant(item, lens);
  if (variant?.repost?.trim()) return variant.repost.trim();
  return item.repost_draft?.trim() || item.summary?.trim() || '';
}

function humanizeSnakeCase(value: string) {
  return value
    .split(/[_-]+/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatTimestamp(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function copyText(text: string) {
  if (!text.trim() || typeof navigator === 'undefined' || !navigator.clipboard) {
    return Promise.reject(new Error('Clipboard is not available.'));
  }
  return navigator.clipboard.writeText(text);
}

function buildPipelineContext(item: SocialFeedItem, lens: FeedLensId) {
  const variant = getFeedVariant(item, lens);
  return buildFallbackText([
    item.summary,
    item.why_it_matters,
    variant?.why_this_angle,
    variant?.belief_summary ? `Belief: ${variant.belief_summary}` : item.belief_assessment?.belief_summary ? `Belief: ${item.belief_assessment.belief_summary}` : '',
    variant?.experience_summary
      ? `Anchor: ${variant.experience_summary}`
      : item.belief_assessment?.experience_summary
        ? `Anchor: ${item.belief_assessment.experience_summary}`
        : '',
    item.standout_lines?.[0],
  ]);
}

function buildPostingWorkspaceHref(item: SocialFeedItem, lens: FeedLensId) {
  return buildComposerHref(item, lens, 'post');
}

function buildCommentWorkspaceHref(item: SocialFeedItem, lens: FeedLensId) {
  return buildComposerHref(item, lens, 'comment');
}

function buildComposerHref(item: SocialFeedItem, lens: FeedLensId, mode: 'post' | 'comment') {
  const params = new URLSearchParams();
  params.set('mode', mode);
  params.set('autoplay', '1');
  params.set('title', item.title);
  if (item.summary) params.set('summary', item.summary);
  if (item.why_it_matters) params.set('routeReason', item.why_it_matters);
  if (item.source_url) params.set('sourceUrl', item.source_url);
  if (item.source_path) params.set('sourcePath', item.source_path);
  params.set('priorityLane', lens);
  return `/workspace/posting?${params.toString()}`;
}

function workspaceRelativePath(path: string) {
  const marker = 'linkedin-content-os/';
  const index = path.indexOf(marker);
  return index >= 0 ? path.slice(index + marker.length) : path;
}

function workspaceSectionKey(path: string) {
  const relative = workspaceRelativePath(path);
  if (relative.startsWith('docs/')) return 'docs';
  if (relative.startsWith('plans/')) return 'plans';
  if (relative.startsWith('research/')) return 'research';
  return 'root';
}

function sectionLabel(key: string) {
  if (key === 'root') return 'Workspace Root';
  return humanizeSnakeCase(key);
}

export function LinkedinWorkspaceSurface({ embedded = false }: { embedded?: boolean }) {
  const searchParams = useSearchParams();
  const safeSearchParams = searchParams ?? new URLSearchParams();
  const tabs = useMemo(() => workspaceTabs(), []);
  const querySeed = useMemo<QuerySeed>(
    () => ({
      title: safeSearchParams.get('title') ?? '',
      summary: safeSearchParams.get('summary') ?? '',
      hook: safeSearchParams.get('hook') ?? '',
      sourceUrl: safeSearchParams.get('sourceUrl') ?? '',
      sourcePath: safeSearchParams.get('sourcePath') ?? '',
      priorityLane: safeSearchParams.get('priorityLane') ?? '',
      routeReason: safeSearchParams.get('routeReason') ?? '',
    }),
    [safeSearchParams],
  );

  const [snapshot, setSnapshot] = useState<WorkspaceSnapshot | null>(null);
  const [snapshotState, setSnapshotState] = useState<'loading' | 'live' | 'error'>('loading');
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [manualFeedItems, setManualFeedItems] = useState<SocialFeedItem[]>([]);
  const [selectedFeedId, setSelectedFeedId] = useState<string | null>(null);
  const [feedLensSelections, setFeedLensSelections] = useState<Record<string, FeedLensId>>({});
  const [refreshingFeed, setRefreshingFeed] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);
  const [ingestUrl, setIngestUrl] = useState('');
  const [ingestText, setIngestText] = useState('');
  const [ingestTitle, setIngestTitle] = useState('');
  const [ingestPriority, setIngestPriority] = useState<FeedLensId>('current-role');
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);
  const [feedbackState, setFeedbackState] = useState<Record<string, string>>({});
  const [feedbackLoading, setFeedbackLoading] = useState<Record<string, boolean>>({});
  const [quoteStatus, setQuoteStatus] = useState<string | null>(null);
  const [isApprovingQuote, setIsApprovingQuote] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const [contentItems, setContentItems] = useState<ContentItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<ContentCategory>('value');
  const [showGenerator, setShowGenerator] = useState(false);
  const [generatorType, setGeneratorType] = useState<ContentType>('linkedin_post');
  const [topic, setTopic] = useState(querySeed.title || '');
  const [context, setContext] = useState(buildFallbackText([querySeed.summary, querySeed.hook, querySeed.routeReason]));
  const [audience, setAudience] = useState<PostingAudience>(mapAudienceFromLane(querySeed.priorityLane));
  const [sourceMode, setSourceMode] = useState<ContentSourceMode>('persona_only');
  const [generating, setGenerating] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<string[]>([]);
  const [generatedOptionBriefs, setGeneratedOptionBriefs] = useState<GeneratedOptionBrief[]>([]);
  const [generatedSupportItems, setGeneratedSupportItems] = useState<ContentReservoirSupportItem[]>([]);
  const [generatorError, setGeneratorError] = useState<string | null>(null);
  const [providerTrace, setProviderTrace] = useState<string | null>(null);
  const [brainPromotionStatus, setBrainPromotionStatus] = useState<string | null>(null);
  const [promotingFragmentKey, setPromotingFragmentKey] = useState<string | null>(null);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);

  const feedItems = useMemo(() => [...manualFeedItems, ...(snapshot?.social_feed?.items ?? [])], [manualFeedItems, snapshot?.social_feed?.items]);
  const selectedSignal = useMemo(() => feedItems.find((item) => item.id === selectedFeedId) ?? null, [feedItems, selectedFeedId]);

  const workspaceFiles = useMemo(() => {
    const files = [...(snapshot?.workspace_files ?? []), ...(snapshot?.doc_entries ?? [])];
    const seen = new Set<string>();
    return files.filter((file) => {
      if (!file?.path || !file.path.includes('linkedin-content-os')) return false;
      if (seen.has(file.path)) return false;
      seen.add(file.path);
      return true;
    });
  }, [snapshot?.doc_entries, snapshot?.workspace_files]);

  const groupedWorkspaceFiles = useMemo(() => {
    const groups = new Map<string, WorkspaceFile[]>();
    workspaceFiles.forEach((file) => {
      const key = workspaceSectionKey(file.path);
      const bucket = groups.get(key) ?? [];
      bucket.push(file);
      groups.set(key, bucket);
    });
    return Array.from(groups.entries())
      .map(([key, files]) => [key, [...files].sort((a, b) => workspaceRelativePath(a.path).localeCompare(workspaceRelativePath(b.path)))] as const)
      .sort((a, b) => {
        const order = ['root', 'docs', 'plans', 'research'];
        return order.indexOf(a[0]) - order.indexOf(b[0]);
      });
  }, [workspaceFiles]);

  const stats = useMemo(() => {
    const value = contentItems.filter((item) => item.category === 'value').length;
    const sales = contentItems.filter((item) => item.category === 'sales').length;
    const personal = contentItems.filter((item) => item.category === 'personal').length;
    return { value, sales, personal, total: value + sales + personal };
  }, [contentItems]);

  const categoryItems = useMemo(() => contentItems.filter((item) => item.category === activeCategory), [activeCategory, contentItems]);
  const workspaceFileCounts = useMemo(() => {
    const counts = { root: 0, docs: 0, plans: 0, research: 0 };
    workspaceFiles.forEach((file) => {
      const key = workspaceSectionKey(file.path);
      if (key === 'root' || key === 'docs' || key === 'plans' || key === 'research') {
        counts[key] += 1;
      }
    });
    return counts;
  }, [workspaceFiles]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed)) {
        setContentItems(parsed);
      }
    } catch {
      return;
    }
  }, []);

  const persistContent = useCallback((items: ContentItem[]) => {
    setContentItems(items);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    }
  }, []);

  const loadSnapshot = useCallback(async () => {
    setSnapshotState('loading');
    try {
      const payload = await apiGet<WorkspaceSnapshot>('/api/workspace/linkedin-os-snapshot');
      setSnapshot(payload);
      setSnapshotError(null);
      setSnapshotState('live');
    } catch (error) {
      setSnapshotError(error instanceof Error ? error.message : 'Unable to load workspace snapshot right now.');
      setSnapshotState('error');
    }
  }, []);

  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

  const resolveFeedLens = useCallback(
    (item: SocialFeedItem): FeedLensId => {
      const selected = feedLensSelections[item.id];
      if (selected) return selected;
      for (const lens of item.lenses ?? []) {
        const normalized = normalizeFeedLens(lens);
        if (normalized) return normalized;
      }
      return 'current-role';
    },
    [feedLensSelections],
  );

  const selectSignalForPipeline = useCallback(
    (item: SocialFeedItem, lens?: FeedLensId) => {
      const nextLens = lens ?? resolveFeedLens(item);
      setSelectedFeedId(item.id);
      setTopic(item.title || '');
      setContext(buildPipelineContext(item, nextLens));
      setAudience(mapAudienceFromLane(nextLens));
      setShowGenerator(true);
      setGeneratedContent([]);
      setGeneratedOptionBriefs([]);
      setGeneratedSupportItems([]);
      setGeneratorError(null);
      setProviderTrace(null);
      setBrainPromotionStatus(null);
      setPromotingFragmentKey(null);
      setCopyStatus(null);
    },
    [resolveFeedLens],
  );

  useEffect(() => {
    if (selectedSignal) return;
    if (feedItems.length > 0) {
      setSelectedFeedId(feedItems[0].id);
      return;
    }
    if (querySeed.title || querySeed.summary || querySeed.hook) {
      setTopic(querySeed.title || '');
      setContext(buildFallbackText([querySeed.summary, querySeed.hook, querySeed.routeReason]));
      setAudience(mapAudienceFromLane(querySeed.priorityLane));
    }
  }, [feedItems, querySeed, selectedSignal]);

  const waitForFeedRefresh = useCallback(async () => {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const status = await apiGet<FeedRefreshStatus>('/api/workspace/refresh-social-feed');
      if (!status.running) {
        if (status.error) throw new Error(status.error);
        return status;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw new Error('Feed refresh timed out before the snapshot updated.');
  }, []);

  const refreshSocialFeed = useCallback(async () => {
    setRefreshingFeed(true);
    setRefreshStatus('Refreshing feed...');
    try {
      const data = await apiPost<{ started_at?: string }>('/api/workspace/refresh-social-feed', {
        skip_fetch: false,
        sources: 'safe',
      });
      setRefreshStatus(`Refresh queued${data.started_at ? ` at ${new Date(data.started_at).toLocaleTimeString()}` : ''}`);
      const finalStatus = await waitForFeedRefresh();
      await loadSnapshot();
      setRefreshStatus(`Feed updated${finalStatus.last_run ? ` at ${new Date(finalStatus.last_run).toLocaleTimeString()}` : ''}`);
    } catch (error) {
      setRefreshStatus(error instanceof Error ? error.message : 'Refresh failed.');
    } finally {
      setRefreshingFeed(false);
    }
  }, [loadSnapshot, waitForFeedRefresh]);

  const ingestSignal = useCallback(async () => {
    if (!ingestUrl && !ingestText) {
      setIngestStatus('Provide a link or some text.');
      return;
    }
    setIngestLoading(true);
    setIngestStatus('Generating preview...');
    try {
      const response = await apiPost<{ preview_item?: SocialFeedItem }>('/api/workspace/ingest-signal', {
        priority_lane: ingestPriority,
        url: ingestUrl || undefined,
        text: ingestText || undefined,
        title: ingestTitle || undefined,
        run_refresh: true,
      });
      const previewItem = response.preview_item ?? null;
      if (!previewItem) {
        setIngestStatus('No preview item came back.');
        return;
      }
      setManualFeedItems((current) => [previewItem, ...current.filter((item) => item.id !== previewItem.id)].slice(0, 5));
      setFeedLensSelections((current) => ({ ...current, [previewItem.id]: ingestPriority }));
      setIngestStatus('Preview added to the top of the feed.');
      setIngestUrl('');
      setIngestText('');
      setIngestTitle('');
      selectSignalForPipeline(previewItem, ingestPriority);
    } catch (error) {
      setIngestStatus(error instanceof Error ? error.message : 'Unable to generate a preview right now.');
    } finally {
      setIngestLoading(false);
    }
  }, [ingestPriority, ingestText, ingestTitle, ingestUrl, selectSignalForPipeline]);

  const generateContent = useCallback(async () => {
    setGenerating(true);
    setGeneratorError(null);
    setGeneratedOptionBriefs([]);
    setGeneratedSupportItems([]);
    try {
      const sourceAttached = sourceMode === 'selected_source' || sourceMode === 'recent_signals';
      const topicToSend = sourceAttached
        ? topic || selectedSignal?.title || 'operator insight'
        : topic || 'operator insight';
      const contextToSend = sourceAttached
        ? context ||
          (selectedSignal ? buildPipelineContext(selectedSignal, resolveFeedLens(selectedSignal)) : buildFallbackText([querySeed.summary, querySeed.hook, querySeed.routeReason]))
        : context || '';
      const response = await apiPost<GeneratedContentResponse>('/api/content-generation/generate', {
        user_id: 'johnnie_fields',
        topic: topicToSend,
        context: contextToSend,
        content_type: generatorType,
        category: activeCategory,
        tone: 'expert_direct',
        audience,
        source_mode: sourceMode,
      });
      const options = Array.isArray(response.options) ? response.options.filter((option) => typeof option === 'string' && option.trim()) : [];
      setGeneratedContent(options);
      setGeneratedOptionBriefs(Array.isArray(response.diagnostics?.planned_option_briefs) ? response.diagnostics.planned_option_briefs : []);
      setGeneratedSupportItems(Array.isArray(response.diagnostics?.content_reservoir_support) ? response.diagnostics.content_reservoir_support : []);
      const trace = (response.diagnostics?.llm_provider_trace ?? [])
        .map((item) => [item.provider, item.actual_model, item.status].filter(Boolean).join(' · '))
        .join(' → ');
      setProviderTrace(trace || null);
      setBrainPromotionStatus(null);
      if (options.length === 0) {
        setGeneratorError('No options were returned.');
      }
    } catch (error) {
      setGeneratorError(error instanceof Error ? error.message : 'Unable to generate content right now.');
    } finally {
      setGenerating(false);
    }
  }, [activeCategory, audience, context, generatorType, querySeed.hook, querySeed.routeReason, querySeed.summary, resolveFeedLens, selectedSignal, sourceMode, topic]);

  const promoteGeneratedFragment = useCallback(
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
          topic: topic || selectedSignal?.title || 'operator insight',
          audience,
          category: activeCategory,
          content_type: generatorType,
          source_mode: sourceMode,
          support_items: generatedSupportItems,
          option_brief: generatedOptionBriefs[optionIndex] ?? null,
        });
        setBrainPromotionStatus(
          response?.message || `Saved to ${humanizeBrainTargetLabel(response?.target_file, response?.target_label)}.`,
        );
      } catch (error) {
        setBrainPromotionStatus(error instanceof Error ? error.message : 'Unable to save this fragment to Brain right now.');
      } finally {
        setPromotingFragmentKey(null);
      }
    },
    [activeCategory, audience, generatedOptionBriefs, generatedSupportItems, generatorType, selectedSignal?.title, sourceMode, topic],
  );

  const saveGeneratedContent = useCallback(
    (content: string, index: number) => {
      const newItem: ContentItem = {
        id: `content_${Date.now()}_${index}`,
        category: activeCategory,
        type: generatorType,
        title: (content.split('\n')[0] || topic || 'Generated draft').slice(0, 80),
        content,
        status: 'draft',
        created_at: new Date().toISOString(),
        tags: [topic].filter(Boolean),
      };
      persistContent([newItem, ...contentItems]);
      setGeneratedContent((current) => current.filter((_, currentIndex) => currentIndex !== index));
    },
    [activeCategory, contentItems, generatorType, persistContent, topic],
  );

  const deleteContentItem = useCallback(
    (id: string) => {
      persistContent(contentItems.filter((item) => item.id !== id));
    },
    [contentItems, persistContent],
  );

  const recordFeedback = useCallback(async (item: SocialFeedItem, decision: 'like' | 'dislike', lens: FeedLensId) => {
    const variant = getFeedVariant(item, lens);
    setFeedbackLoading((current) => ({ ...current, [item.id]: true }));
    try {
      await apiPost('/api/workspace/feedback', {
        feed_item_id: item.id,
        title: item.title,
        platform: item.platform,
        decision,
        lens,
        source_url: item.source_url,
        source_path: item.source_path,
        stance: variant?.stance,
        belief_used: variant?.belief_summary ?? item.belief_assessment?.belief_summary,
        experience_anchor: variant?.experience_summary ?? item.belief_assessment?.experience_summary,
        techniques: variant?.techniques ?? item.technique_assessment?.techniques ?? [],
        evaluation_overall: variant?.evaluation?.overall ?? item.evaluation?.overall,
        source_expression_quality: variant?.evaluation?.source_expression_quality ?? item.evaluation?.source_expression_quality,
        output_expression_quality: variant?.evaluation?.expression_quality ?? item.evaluation?.expression_quality,
        expression_delta: variant?.evaluation?.expression_delta ?? item.evaluation?.expression_delta,
        why_this_angle: variant?.why_this_angle,
      });
      setFeedbackState((current) => ({ ...current, [item.id]: decision === 'like' ? 'Liked' : 'Disliked' }));
    } catch (error) {
      setFeedbackState((current) => ({ ...current, [item.id]: error instanceof Error ? error.message : 'Feedback failed.' }));
    } finally {
      setFeedbackLoading((current) => ({ ...current, [item.id]: false }));
    }
  }, []);

  const approveFeedLine = useCallback(async (item: SocialFeedItem, line: string, lens: FeedLensId) => {
    setIsApprovingQuote(true);
    setQuoteStatus('Approving line...');
    try {
      const delta = await apiPost<{ id: string }>('/api/persona/deltas', {
        persona_target: 'feeze.core',
        trait: `Workspace quote (${item.author})`,
        notes: line.trim(),
        metadata: {
          target_file: 'identity/VOICE_PATTERNS.md',
          review_source: 'linkedin_workspace.feed_quote',
          approval_state: 'pending_workspace_approval',
          platform: item.platform,
          author: item.author,
          source_url: item.source_url,
          source_path: item.source_path,
          selected_line: line.trim(),
          workspace: 'linkedin-content-os',
          lens,
        },
      });
      await apiFetch(`/api/persona/deltas/${delta.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'approved',
          metadata: {
            approval_state: 'approved_from_workspace',
            last_reviewed_at: new Date().toISOString(),
            review_source: 'linkedin_workspace.feed_quote',
          },
        }),
      });
      setQuoteStatus(`Approved quote "${line.slice(0, 48)}..."`);
    } catch (error) {
      setQuoteStatus(error instanceof Error ? error.message : 'Unable to approve quote right now.');
    } finally {
      setIsApprovingQuote(false);
    }
  }, []);

  async function handleCopy(text: string, label: string) {
    try {
      await copyText(text);
      setCopyStatus(`${label} copied.`);
    } catch (error) {
      setCopyStatus(error instanceof Error ? error.message : 'Unable to copy right now.');
    }
  }

  const topRecommendations = (snapshot?.weekly_plan?.recommendations ?? []).slice(0, 3);

  const content = (
    <section style={{ display: 'grid', gap: '20px' }}>
        <section style={workspaceHeaderStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', marginBottom: '18px' }}>
            <div>
              <p style={workspaceHeaderLabelStyle}>Workspace</p>
              <h1 style={{ fontSize: '34px', color: 'white', margin: '4px 0' }}>Posting pipeline + shared source feed</h1>
              <p style={{ color: '#94a3b8', maxWidth: '860px', fontSize: '14px', lineHeight: 1.6 }}>
                This is the execution surface. Build posts through the 9-1-1 pipeline, react to the same feed going into Brain, and keep the agent workspace visible while you work.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <Link href="/brain" style={headerLinkStyle('#38bdf8')}>
                Open Brain
              </Link>
              <Link href="/workspace/posting" style={headerLinkStyle('#fb923c')}>
                Dedicated Composer
              </Link>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
            <MiniStat label="Snapshot" value={snapshotState === 'live' ? 'Live' : snapshotState === 'loading' ? 'Loading' : 'Error'} detail={snapshotState === 'error' ? snapshotError ?? 'Snapshot unavailable' : 'shared Brain + Workspace state'} />
            <MiniStat label="Pipeline" value={String(stats.total)} detail="saved drafts" />
            <MiniStat label="Feed Items" value={String(feedItems.length)} detail={`updated ${formatTimestamp(snapshot?.social_feed?.generated_at)}`} />
            <MiniStat label="Comments" value={String(snapshot?.reaction_queue?.counts?.comment_opportunities ?? 0)} detail="reaction-ready items" />
            <MiniStat label="Post Seeds" value={String(snapshot?.reaction_queue?.counts?.post_seeds ?? 0)} detail="save-for-post angles" />
            <MiniStat label="Feedback" value={String(snapshot?.feedback_summary?.total_events ?? 0)} detail="human training events" />
          </div>
        </section>

        <section style={panelStyle}>
          <div style={{ marginBottom: '18px' }}>
            <p style={sectionLabelStyle('#38bdf8')}>1 Content Pipeline</p>
            <h2 style={{ fontSize: '28px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>Content Pipeline</h2>
            <p style={{ color: '#9ca3af', fontSize: '14px' }}>Chris Do 911 Framework: 9 Value • 1 Sales • 1 Personal</p>
          </div>

          <div style={personaBannerStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '14px', flexWrap: 'wrap' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '18px', fontWeight: 600, color: 'white' }}>{PERSONA.name}</span>
                  <span style={personaActiveStyle}>Persona Active</span>
                </div>
                <p style={{ fontSize: '14px', color: '#9ca3af', margin: 0 }}>{PERSONA.title}</p>
                <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px', maxWidth: '700px' }}>{PERSONA.northStar}</p>
              </div>
              <div style={{ textAlign: 'right', fontSize: '12px', color: '#94a3b8' }}>
                <div>Tone: {PERSONA.tone}</div>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px' }}>
            {(['value', 'sales', 'personal'] as ContentCategory[]).map((categoryKey) => {
              const config = CHRIS_DO_911[categoryKey];
              const count = stats[categoryKey];
              const active = activeCategory === categoryKey;
              return (
                <button
                  key={categoryKey}
                  onClick={() => setActiveCategory(categoryKey)}
                  style={{
                    ...categoryCardStyle,
                    border: active ? `2px solid ${config.tone}` : '2px solid #475569',
                    backgroundColor: active ? `${config.tone}15` : '#1e293b',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <span style={{ fontSize: '32px' }}>{config.icon}</span>
                    <div>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>{count}</div>
                      <div style={{ fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase' }}>
                        {categoryKey} ({config.ratio}x)
                      </div>
                    </div>
                  </div>
                  <p style={{ fontSize: '12px', color: '#6b7280', margin: 0 }}>{config.description}</p>
                </button>
              );
            })}
          </div>

          <div style={{ borderRadius: '14px', border: '1px solid #334155', backgroundColor: '#020617', padding: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div>
                <p style={{ color: '#64748b', fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 6px' }}>Selected feed source</p>
                <h3 style={{ color: 'white', fontSize: '18px', margin: '0 0 6px' }}>{selectedSignal?.title || querySeed.title || 'No signal selected yet'}</h3>
                {(selectedSignal?.why_it_matters || selectedSignal?.summary || querySeed.summary) && (
                  <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: 0 }}>
                    {selectedSignal?.why_it_matters || selectedSignal?.summary || querySeed.summary}
                  </p>
                )}
              </div>
              {selectedSignal?.source_url && (
                <a href={selectedSignal.source_url} target="_blank" rel="noreferrer" style={headerLinkStyle('#38bdf8')}>
                  Open original post
                </a>
              )}
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
              <InlinePill label={`${stats.total} saved drafts`} tone="#38bdf8" />
              <InlinePill label={`${snapshot?.weekly_plan?.recommendations?.length ?? 0} live recommendations`} tone="#fbbf24" />
              <InlinePill label={`${snapshot?.reaction_queue?.counts?.comment_opportunities ?? 0} comment opportunities`} tone="#22c55e" />
            </div>
          </div>

          <button onClick={() => setShowGenerator((current) => !current)} style={generatorToggleStyle}>
            {showGenerator ? 'Hide Generator' : `+ Generate ${activeCategory.charAt(0).toUpperCase() + activeCategory.slice(1)} Content`}
          </button>

          {showGenerator && (
            <div style={generatorPanelStyle}>
              <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'white', marginBottom: '16px' }}>
                Generate {activeCategory.charAt(0).toUpperCase() + activeCategory.slice(1)} Content
              </h3>

              <div style={{ marginBottom: '16px' }}>
                <label style={fieldLabelStyle}>Content Type</label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
                  {CONTENT_TYPES.map((type) => (
                    <button
                      key={type.value}
                      onClick={() => setGeneratorType(type.value)}
                      style={{
                        borderRadius: '8px',
                        border: '1px solid #475569',
                        backgroundColor: generatorType === type.value ? '#3b82f6' : '#374151',
                        color: 'white',
                        padding: '8px 14px',
                        fontSize: '13px',
                        cursor: 'pointer',
                      }}
                    >
                      {type.icon} {type.label}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '16px', marginBottom: '16px' }}>
                <label style={fieldWrapStyle}>
                  <span style={fieldLabelStyle}>Topic</span>
                  <input value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="e.g. agent orchestration" style={fieldStyle} />
                </label>
                <label style={fieldWrapStyle}>
                  <span style={fieldLabelStyle}>Context</span>
                  <textarea value={context} onChange={(event) => setContext(event.target.value)} placeholder="Why this source matters, the belief it touches, and any angle you want to push." rows={4} style={{ ...textareaStyle, minHeight: '96px' }} />
                </label>
                <label style={fieldWrapStyle}>
                  <span style={fieldLabelStyle}>Audience</span>
                  <select value={audience} onChange={(event) => setAudience(event.target.value as PostingAudience)} style={fieldStyle}>
                    {AUDIENCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div style={{ display: 'grid', gap: '6px', marginBottom: '16px' }}>
                <label style={fieldWrapStyle}>
                  <span style={fieldLabelStyle}>Source basis</span>
                  <select value={sourceMode} onChange={(event) => setSourceMode(event.target.value as ContentSourceMode)} style={fieldStyle}>
                    {CONTENT_SOURCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>
                  {CONTENT_SOURCE_OPTIONS.find((option) => option.value === sourceMode)?.hint}
                </p>
              </div>

              <button onClick={() => void generateContent()} disabled={generating} style={primaryActionStyle('#38bdf8')}>
                {generating ? 'Generating…' : 'Generate Options'}
              </button>
              {providerTrace && <p style={{ color: '#94a3b8', fontSize: '12px', marginTop: '12px' }}>Model trace: {providerTrace}</p>}
              {generatorError && <p style={{ color: '#f87171', fontSize: '12px', marginTop: '12px' }}>{generatorError}</p>}
              {brainPromotionStatus && (
                <p style={{ color: brainPromotionLooksErrored(brainPromotionStatus) ? '#f87171' : '#34d399', fontSize: '12px', marginTop: '12px' }}>
                  {brainPromotionStatus}
                </p>
              )}

              {generatedContent.length > 0 && (
                <div style={{ marginTop: '24px' }}>
                  <h4 style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '12px' }}>Generated Options</h4>
                  <div style={{ display: 'grid', gap: '16px' }}>
                    {generatedContent.map((content, index) => (
                      <div key={`generated-${index}`} style={generatedOptionStyle}>
                        <pre style={generatedOptionTextStyle}>{content}</pre>
                        <div style={{ display: 'grid', gap: '8px' }}>
                          <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>Click any strong sentence to teach Brain immediately.</p>
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            {splitPromotableFragments(content).map((fragment) => {
                              const fragmentKey = `${index}:${fragment}`;
                              const isSaving = promotingFragmentKey === fragmentKey;
                              return (
                                <button
                                  key={fragmentKey}
                                  onClick={() => void promoteGeneratedFragment(fragment, content, index)}
                                  disabled={isSaving}
                                  style={generatedFragmentActionStyle(isSaving)}
                                >
                                  {isSaving ? 'Saving…' : `Add to Brain: ${truncateGeneratedFragment(fragment)}`}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button onClick={() => saveGeneratedContent(content, index)} style={primaryActionStyle('#22c55e')}>
                            Save to Pipeline
                          </button>
                          <button onClick={() => void handleCopy(content, 'Draft')} style={secondaryActionStyle('#94a3b8')}>
                            Copy
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div style={pipelineListStyle}>
            <div style={pipelineHeaderStyle}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'white', margin: 0 }}>
                {CHRIS_DO_911[activeCategory].icon} {activeCategory.charAt(0).toUpperCase() + activeCategory.slice(1)} Content
              </h3>
              <span style={{ fontSize: '14px', color: '#6b7280' }}>{categoryItems.length} items</span>
            </div>

            {categoryItems.length === 0 ? (
              <div style={emptyPipelineStyle}>No {activeCategory} content yet. Generate some above!</div>
            ) : (
              <div>
                {categoryItems.map((item) => (
                  <div key={item.id} style={pipelineItemRowStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span>{CONTENT_TYPES.find((type) => type.value === item.type)?.icon}</span>
                          <span style={{ fontSize: '14px', fontWeight: 500, color: 'white' }}>{item.title}</span>
                        </div>
                        <p style={{ fontSize: '13px', color: '#9ca3af', margin: 0 }}>{item.content.slice(0, 160)}...</p>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button onClick={() => setExpandedItem((current) => (current === item.id ? null : item.id))} style={secondaryActionStyle('#9ca3af')}>
                          {expandedItem === item.id ? 'Hide' : 'View'}
                        </button>
                        <button onClick={() => void handleCopy(item.content, 'Pipeline item')} style={secondaryActionStyle('#9ca3af')}>
                          Copy
                        </button>
                        <button onClick={() => deleteContentItem(item.id)} style={secondaryActionStyle('#ef4444')}>
                          Delete
                        </button>
                      </div>
                    </div>
                    {expandedItem === item.id && (
                      <div style={expandedContentStyle}>
                        <pre style={expandedContentTextStyle}>{item.content}</pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section style={panelStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <div>
              <p style={sectionLabelStyle('#22c55e')}>2 Feed of Sources</p>
              <h2 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>Comment, repost, and train the feed</h2>
              <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6, maxWidth: '860px' }}>
                This is the same shared feed going into Brain. Use it to react to Substack, YouTube, Reddit, RSS, and LinkedIn signals, then push the best ones into the pipeline.
              </p>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
              <button onClick={() => void refreshSocialFeed()} disabled={refreshingFeed} style={primaryActionStyle('#22c55e')}>
                {refreshingFeed ? 'Refreshing…' : 'Refresh feed'}
              </button>
              <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>
                Updated {formatTimestamp(snapshot?.social_feed?.generated_at)} · {feedItems.length} items tracked
              </p>
              {refreshStatus && <p style={{ color: refreshingFeed ? '#38bdf8' : '#34d399', fontSize: '12px', margin: 0 }}>{refreshStatus}</p>}
            </div>
          </div>

          <div style={ingestPanelStyle}>
            <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>
              Paste a URL or stand-alone copy of a post/text, pick a lane, and generate a live preview card that appears at the top of this feed.
            </p>
            <input placeholder="https://link.to/post" value={ingestUrl} onChange={(event) => setIngestUrl(event.target.value)} style={fieldStyle} />
            <textarea placeholder="Or paste text you want to comment on..." value={ingestText} onChange={(event) => setIngestText(event.target.value)} rows={4} style={textareaStyle} />
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
              <input placeholder="Signal title (optional)" value={ingestTitle} onChange={(event) => setIngestTitle(event.target.value)} style={{ ...fieldStyle, flex: 1 }} />
              <select value={ingestPriority} onChange={(event) => setIngestPriority(event.target.value as FeedLensId)} style={{ ...fieldStyle, width: '220px' }}>
                {POST_MODE_OPTIONS.map((mode) => (
                  <option key={mode.id} value={mode.id}>
                    {mode.label}
                  </option>
                ))}
              </select>
              <button onClick={() => void ingestSignal()} disabled={ingestLoading} style={primaryActionStyle('#38bdf8')}>
                {ingestLoading ? 'Generating…' : 'Generate preview'}
              </button>
            </div>
            {ingestStatus && <p style={{ color: '#34d399', fontSize: '12px', margin: 0 }}>{ingestStatus}</p>}
          </div>

          {quoteStatus && <div style={statusBannerStyle(isApprovingQuote)}>{quoteStatus}</div>}
          {copyStatus && <p style={{ color: copyStatus.includes('copied') ? '#34d399' : '#f87171', fontSize: '12px', margin: 0 }}>{copyStatus}</p>}

          {topRecommendations.length > 0 && (
            <div style={{ display: 'grid', gap: '8px' }}>
              <p style={{ color: '#fbbf24', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.12em', margin: 0 }}>Weekly plan highlights</p>
              <div style={{ display: 'grid', gap: '8px' }}>
                {topRecommendations.map((item, index) => (
                  <div key={`${item.title}-${index}`} style={recommendationCardStyle}>
                    <p style={{ color: 'white', fontSize: '13px', fontWeight: 700, margin: '0 0 4px' }}>{item.title}</p>
                    <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{item.hook || item.summary || 'No summary yet.'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gap: '14px' }}>
            {feedItems.map((item) => {
              const selectedLens = resolveFeedLens(item);
              const activeVariant = getFeedVariant(item, selectedLens);
              const evaluation = activeVariant?.evaluation ?? item.evaluation;
              const beliefAssessment = activeVariant ?? item.belief_assessment;
              const techniqueAssessment = activeVariant ?? item.technique_assessment;
              const expressionAssessment = activeVariant?.expression_assessment ?? item.expression_assessment;
              const sourceContractClass = deriveSourceClass(item);
              const sourceContractUnit = deriveUnitKind(item, sourceContractClass);
              const sourceContractModes = deriveResponseModes(item, sourceContractClass, sourceContractUnit);
              const quickReply = createShortCommentDraft(item, selectedLens);
              const commentDraft = createCommentDraft(item, selectedLens);
              const repostDraft = createRepostDraft(item, selectedLens);

              return (
                <article key={item.id} style={{ ...feedCardStyle, border: item.id === selectedFeedId ? '1px solid #38bdf8' : '1px solid #1f2937' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                    <span style={platformBadgeStyle}>{item.platform}</span>
                    <span style={scoreBadgeStyle}>score {item.ranking.total.toFixed(1)}</span>
                  </div>
                  <h3 style={{ color: 'white', fontSize: '24px', margin: '0 0 4px' }}>{item.title}</h3>
                  <p style={{ color: '#94a3b8', margin: 0 }}>{item.author}</p>
                  {item.source_url && (
                    <a href={item.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', fontSize: '12px' }}>
                      Open original post
                    </a>
                  )}
                  {item.why_it_matters && <p style={{ color: '#cbd5f5', fontSize: '13px', margin: 0 }}>{item.why_it_matters}</p>}

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {POST_MODE_OPTIONS.map((mode) => (
                      <button
                        key={`${item.id}-${mode.id}`}
                        onClick={() => {
                          setFeedLensSelections((current) => ({ ...current, [item.id]: mode.id }));
                          if (item.id === selectedFeedId) {
                            setTopic(item.title);
                            setContext(buildPipelineContext(item, mode.id));
                            setAudience(mapAudienceFromLane(mode.id));
                          }
                        }}
                        style={{
                          borderRadius: '999px',
                          border: selectedLens === mode.id ? '1px solid #fbbf24' : '1px solid #334155',
                          padding: '6px 12px',
                          background: selectedLens === mode.id ? 'rgba(251,191,36,0.14)' : 'transparent',
                          color: selectedLens === mode.id ? '#fbbf24' : '#cbd5f5',
                          fontSize: '11px',
                          cursor: 'pointer',
                        }}
                      >
                        {mode.label}
                      </button>
                    ))}
                  </div>

                  <div style={systemReadoutStyle}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                      <p style={{ color: '#cbd5f5', margin: 0, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>System readout</p>
                      <span style={{ color: '#93c5fd', fontSize: '12px' }}>overall {evaluation?.overall?.toFixed(1) ?? 'n/a'}</span>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {beliefAssessment?.stance && <MiniReadoutChip label={`stance: ${beliefAssessment.stance}`} tone="#93c5fd" />}
                      {beliefAssessment?.role_safety && <MiniReadoutChip label={`role safety: ${beliefAssessment.role_safety}`} tone="#fde68a" />}
                      {(techniqueAssessment?.techniques ?? []).map((technique) => (
                        <MiniReadoutChip key={`${item.id}-${selectedLens}-${technique}`} label={technique} tone="#86efac" />
                      ))}
                    </div>
                    {activeVariant?.why_this_angle && <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{activeVariant.why_this_angle}</p>}
                    {(beliefAssessment as { belief_summary?: string } | undefined)?.belief_summary && (
                      <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                        <span style={{ color: '#94a3b8' }}>Belief:</span> {(beliefAssessment as { belief_summary?: string }).belief_summary}
                      </p>
                    )}
                    {(beliefAssessment as { experience_summary?: string } | undefined)?.experience_summary && (
                      <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                        <span style={{ color: '#94a3b8' }}>Anchor:</span> {(beliefAssessment as { experience_summary?: string }).experience_summary}
                      </p>
                    )}
                    <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                      <span style={{ color: '#94a3b8' }}>Source contract:</span> {sourceContractClass} · {sourceContractUnit} · {sourceContractModes.join(', ')}
                    </p>
                    {expressionAssessment?.strategy && (
                      <p style={{ color: '#e2e8f0', fontSize: '12px', margin: 0 }}>
                        <span style={{ color: '#94a3b8' }}>Expression:</span> {expressionAssessment.strategy} · {expressionAssessment.output_structure ?? 'plain'}
                      </p>
                    )}
                    {evaluation && (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: '6px' }}>
                        <span style={evalCellStyle}>Lane {evaluation.lane_distinctiveness?.toFixed(1) ?? 'n/a'}</span>
                        <span style={evalCellStyle}>Belief {evaluation.belief_clarity?.toFixed(1) ?? 'n/a'}</span>
                        <span style={evalCellStyle}>Voice {evaluation.voice_match?.toFixed(1) ?? 'n/a'}</span>
                        <span style={evalCellStyle}>Expr {evaluation.expression_quality?.toFixed(1) ?? 'n/a'}</span>
                        <span style={evalCellStyle}>Src {evaluation.source_expression_quality?.toFixed(1) ?? 'n/a'}</span>
                        <span style={evalCellStyle}>Δ {evaluation.expression_delta?.toFixed(1) ?? '0.0'}</span>
                      </div>
                    )}
                  </div>

                  {item.standout_lines?.map((line) => (
                    <div key={`${item.id}-${line}`} style={approveLineRowStyle}>
                      <span style={{ color: '#e2e8f0', fontSize: '13px', flex: 1 }}>{line}</span>
                      <button onClick={() => void approveFeedLine(item, line, selectedLens)} disabled={isApprovingQuote} style={secondaryActionStyle('#fbbf24')}>
                        {isApprovingQuote ? 'Approving…' : 'Approve line'}
                      </button>
                    </div>
                  ))}

                  <DraftBlock title="Quick reply" text={quickReply || 'No quick reply available.'} tone="#22c55e" onCopy={() => void handleCopy(quickReply, 'Quick reply')} />
                  <DraftBlock title="Suggested comment" text={commentDraft || 'No suggested comment available.'} tone="#38bdf8" onCopy={() => void handleCopy(commentDraft, 'Suggested comment')} />
                  <DraftBlock title="Suggested repost" text={repostDraft || 'No repost draft available.'} tone="#f472b6" onCopy={() => void handleCopy(repostDraft, 'Suggested repost')} />

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <button onClick={() => selectSignalForPipeline(item, selectedLens)} style={primaryActionStyle('#fb923c')}>
                      Use in pipeline
                    </button>
                    <Link href={buildPostingWorkspaceHref(item, selectedLens)} style={secondaryLinkStyle('#fb923c')}>
                      Write post
                    </Link>
                    <Link href={buildCommentWorkspaceHref(item, selectedLens)} style={secondaryLinkStyle('#38bdf8')}>
                      Comment on this
                    </Link>
                    {item.source_url && (
                      <button onClick={() => void handleCopy(item.source_url ?? '', 'Source link')} style={secondaryActionStyle('#94a3b8')}>
                        Copy link
                      </button>
                    )}
                    <button onClick={() => void recordFeedback(item, 'like', selectedLens)} disabled={feedbackLoading[item.id]} style={feedbackButtonStyle('#22c55e')}>
                      👍 Like
                    </button>
                    <button onClick={() => void recordFeedback(item, 'dislike', selectedLens)} disabled={feedbackLoading[item.id]} style={feedbackButtonStyle('#f87171')}>
                      👎 Dislike
                    </button>
                    <p style={{ color: '#94a3b8', fontSize: '12px', margin: 0 }}>{feedbackState[item.id] ?? 'Select a preference to train the feed.'}</p>
                  </div>
                </article>
              );
            })}
            {feedItems.length === 0 && <EmptyMessage message="No feed items available yet. Refresh the shared feed or generate a preview signal to start testing the workspace." />}
          </div>
        </section>

        <section style={panelStyle}>
          <div>
            <p style={sectionLabelStyle('#fbbf24')}>3 Agent System</p>
            <h2 style={{ fontSize: '24px', color: 'white', margin: '4px 0' }}>linkedin-content-os</h2>
            <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6, maxWidth: '860px' }}>
              These are the workspace files, docs, plans, and research notes backing the posting system. They stay visible here so the feed and pipeline remain grounded in the actual workspace contract.
            </p>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
              <InlinePill label={`${workspaceFileCounts.root} root files`} tone="#cbd5f5" />
              <InlinePill label={`${workspaceFileCounts.docs} docs`} tone="#38bdf8" />
              <InlinePill label={`${workspaceFileCounts.plans} plans`} tone="#22c55e" />
              <InlinePill label={`${workspaceFileCounts.research} research files`} tone="#fbbf24" />
            </div>
          </div>

          {groupedWorkspaceFiles.length === 0 ? (
            <EmptyMessage message="No LinkedIn workspace files are visible in the snapshot yet." />
          ) : (
            <div style={{ display: 'grid', gap: '12px' }}>
              {groupedWorkspaceFiles.map(([sectionKey, files]) => (
                <details key={sectionKey} open={sectionKey === 'root'} style={agentSectionStyle}>
                  <summary style={agentSectionSummaryStyle}>
                    <div>
                      <p style={{ color: '#e2e8f0', fontSize: '15px', fontWeight: 600, margin: 0 }}>{sectionLabel(sectionKey)}</p>
                      <p style={{ color: '#64748b', fontSize: '12px', margin: '4px 0 0' }}>{files.length} files</p>
                    </div>
                    <span style={{ color: '#38bdf8', fontSize: '12px' }}>Expand</span>
                  </summary>
                  <div style={{ padding: '0 16px 16px', display: 'grid', gap: '10px' }}>
                    {files.map((file) => (
                      <div key={file.path} style={workspaceFileCardStyle}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                          <div>
                            <p style={{ color: 'white', fontSize: '14px', fontWeight: 600, margin: 0 }}>{workspaceRelativePath(file.path)}</p>
                            {file.updatedAt && <p style={{ color: '#64748b', fontSize: '11px', margin: '4px 0 0' }}>Updated {formatTimestamp(file.updatedAt)}</p>}
                          </div>
                          <InlinePill label={file.name} tone="#64748b" />
                        </div>
                        <p style={{ color: '#cbd5f5', fontSize: '13px', lineHeight: 1.55, margin: '8px 0 0' }}>{file.snippet || summarizeContent(file.content) || 'No summary available.'}</p>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          )}
        </section>
      </section>
  );

  if (embedded) {
    return content;
  }

  return (
    <RuntimePage module="ops" tabs={tabs} maxWidth="1520px">
      {content}
    </RuntimePage>
  );
}

function WorkspaceHomeFallback() {
  return (
    <RuntimePage module="ops" tabs={workspaceTabs()} maxWidth="1520px">
      <section style={panelStyle}>Loading workspace…</section>
    </RuntimePage>
  );
}

export default function WorkspaceClient() {
  return (
    <Suspense fallback={<WorkspaceHomeFallback />}>
      <LinkedinWorkspaceSurface />
    </Suspense>
  );
}

function DraftBlock({ title, text, tone, onCopy }: { title: string; text: string; tone: string; onCopy: () => void }) {
  return (
    <div style={{ display: 'grid', gap: '4px' }}>
      <p style={{ color: '#cbd5f5', margin: '4px 0', fontSize: '12px' }}>{title}</p>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <p style={draftTextStyle}>{text}</p>
        <button onClick={onCopy} style={secondaryActionStyle(tone)}>
          Copy
        </button>
      </div>
    </div>
  );
}

function DraftStatCard({ category, count, active, onClick }: { category: ContentCategory; count: number; active: boolean; onClick: () => void }) {
  const config = CHRIS_DO_911[category];
  return (
    <button
      onClick={onClick}
      style={{
        ...categoryCardStyle,
        border: active ? `2px solid ${config.tone}` : '2px solid #475569',
        backgroundColor: active ? `${config.tone}15` : '#1e293b',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
        <span style={{ fontSize: '32px' }}>{config.icon}</span>
        <div>
          <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>{count}</div>
          <div style={{ fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase' }}>
            {category} ({config.ratio}x)
          </div>
        </div>
      </div>
      <p style={{ fontSize: '12px', color: '#6b7280', margin: 0 }}>{config.description}</p>
    </button>
  );
}

function MiniStat({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div style={miniStatStyle}>
      <p style={miniStatLabelStyle}>{label}</p>
      <p style={miniStatValueStyle}>{value}</p>
      <p style={miniStatDetailStyle}>{detail}</p>
    </div>
  );
}

function InlinePill({ label, tone }: { label: string; tone: string }) {
  return <span style={{ ...pillStyle, border: `1px solid ${tone}55`, backgroundColor: `${tone}18`, color: tone }}>{label}</span>;
}

function MiniReadoutChip({ label, tone }: { label: string; tone: string }) {
  return <span style={{ borderRadius: '999px', padding: '4px 8px', border: `1px solid ${tone}55`, color: tone, fontSize: '11px' }}>{label}</span>;
}

function EmptyMessage({ message }: { message: string }) {
  return <div style={emptyMessageStyle}>{message}</div>;
}

function summarizeContent(content?: string) {
  if (!content) return '';
  const cleaned = content.replace(/\s+/g, ' ').trim();
  return cleaned.length > 220 ? `${cleaned.slice(0, 220)}...` : cleaned;
}

function sectionLabelStyle(tone: string) {
  return {
    color: tone,
    fontSize: '11px',
    textTransform: 'uppercase',
    letterSpacing: '0.12em',
    margin: 0,
  } as const;
}

function primaryActionStyle(tone: string) {
  return {
    borderRadius: '10px',
    border: `1px solid ${tone}`,
    backgroundColor: `${tone}18`,
    color: 'white',
    padding: '8px 14px',
    fontSize: '13px',
    fontWeight: 700,
    cursor: 'pointer',
  } as const;
}

function secondaryActionStyle(tone: string) {
  return {
    borderRadius: '8px',
    border: `1px solid ${tone}`,
    backgroundColor: 'transparent',
    color: tone,
    padding: '6px 12px',
    fontSize: '12px',
    cursor: 'pointer',
  } as const;
}

function secondaryLinkStyle(tone: string) {
  return {
    borderRadius: '8px',
    border: `1px solid ${tone}`,
    backgroundColor: 'transparent',
    color: tone,
    padding: '7px 12px',
    fontSize: '12px',
    fontWeight: 700,
    textDecoration: 'none',
  } as const;
}

function feedbackButtonStyle(tone: string) {
  return {
    borderRadius: '12px',
    border: `1px solid ${tone}`,
    background: `${tone}20`,
    color: tone,
    padding: '6px 12px',
    fontSize: '12px',
    cursor: 'pointer',
  } as const;
}

function headerLinkStyle(tone: string) {
  return {
    borderRadius: '12px',
    border: `1px solid ${tone}`,
    backgroundColor: `${tone}18`,
    color: 'white',
    padding: '10px 14px',
    textDecoration: 'none',
    fontSize: '13px',
    fontWeight: 600,
  } as const;
}

function statusBannerStyle(active: boolean) {
  return {
    padding: '10px 14px',
    borderRadius: '10px',
    backgroundColor: active ? 'rgba(37,99,235,0.2)' : 'rgba(34,197,94,0.2)',
    border: `1px solid ${active ? 'rgba(37,99,235,0.6)' : 'rgba(34,197,94,0.6)'}`,
    color: '#e0f2fe',
    fontSize: '13px',
  } as const;
}

const workspaceHeaderStyle = {
  borderRadius: '22px',
  padding: '24px',
  background: 'linear-gradient(135deg, rgba(11,19,36,0.96), rgba(4,9,18,0.98))',
  border: '1px solid rgba(56,189,248,0.18)',
  boxShadow: '0 26px 72px rgba(0,0,0,0.35)',
} as const;

const workspaceHeaderLabelStyle = {
  color: '#38bdf8',
  letterSpacing: '0.2em',
  fontSize: '11px',
  textTransform: 'uppercase',
  margin: 0,
} as const;

const panelStyle = {
  borderRadius: '18px',
  border: '1px solid #1f2937',
  backgroundColor: '#050b19',
  padding: '20px',
  display: 'grid',
  gap: '16px',
} as const;

const miniStatStyle = {
  padding: '12px 14px',
  borderRadius: '14px',
  border: '1px solid rgba(148,163,184,0.14)',
  backgroundColor: 'rgba(2,6,23,0.65)',
} as const;

const miniStatLabelStyle = {
  color: '#94a3b8',
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
  margin: 0,
} as const;

const miniStatValueStyle = {
  color: 'white',
  fontSize: '22px',
  fontWeight: 700,
  margin: '4px 0',
} as const;

const miniStatDetailStyle = {
  color: '#64748b',
  fontSize: '12px',
  lineHeight: 1.45,
  margin: 0,
} as const;

const personaBannerStyle = {
  background: 'linear-gradient(to right, #1e293b, #334155)',
  borderRadius: '12px',
  padding: '16px',
  border: '1px solid #475569',
} as const;

const personaActiveStyle = {
  fontSize: '12px',
  padding: '2px 8px',
  backgroundColor: 'rgba(59, 130, 246, 0.3)',
  borderRadius: '4px',
  color: '#93c5fd',
} as const;

const categoryCardStyle = {
  padding: '20px',
  borderRadius: '12px',
  textAlign: 'left',
  cursor: 'pointer',
} as const;

const generatorToggleStyle = {
  width: '100%',
  padding: '16px',
  borderRadius: '12px',
  border: '2px dashed #475569',
  backgroundColor: 'transparent',
  color: '#9ca3af',
  fontSize: '16px',
  cursor: 'pointer',
} as const;

const generatorPanelStyle = {
  backgroundColor: '#1e293b',
  borderRadius: '12px',
  padding: '24px',
  border: '1px solid #475569',
} as const;

const fieldWrapStyle = {
  display: 'grid',
  gap: '6px',
} as const;

const fieldLabelStyle = {
  display: 'block',
  fontSize: '14px',
  color: '#9ca3af',
} as const;

const fieldStyle = {
  width: '100%',
  padding: '12px',
  borderRadius: '8px',
  border: '1px solid #475569',
  backgroundColor: '#0f172a',
  color: 'white',
  fontSize: '14px',
  boxSizing: 'border-box',
} as const;

const textareaStyle = {
  ...fieldStyle,
  resize: 'vertical',
  minHeight: '120px',
} as const;

const generatedOptionStyle = {
  padding: '16px',
  borderRadius: '8px',
  backgroundColor: '#0f172a',
  border: '1px solid #475569',
  display: 'grid',
  gap: '12px',
} as const;

const generatedOptionTextStyle = {
  whiteSpace: 'pre-wrap',
  fontSize: '14px',
  color: '#e2e8f0',
  margin: 0,
  fontFamily: 'inherit',
  maxHeight: '220px',
  overflow: 'auto',
} as const;

function generatedFragmentActionStyle(disabled: boolean) {
  return {
    borderRadius: '999px',
    border: '1px solid #334155',
    backgroundColor: disabled ? '#111827' : '#0b1220',
    color: disabled ? '#64748b' : '#cbd5f5',
    padding: '7px 10px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
    textAlign: 'left' as const,
  };
}

function truncateGeneratedFragment(value: string) {
  const normalized = value.trim();
  if (normalized.length <= 70) return normalized;
  return `${normalized.slice(0, 67)}...`;
}

function brainPromotionLooksErrored(value: string) {
  const normalized = value.toLowerCase();
  return normalized.includes('unable') || normalized.includes('failed') || normalized.includes('error');
}

const pipelineListStyle = {
  backgroundColor: '#1e293b',
  borderRadius: '12px',
  border: '1px solid #475569',
  overflow: 'hidden',
} as const;

const pipelineHeaderStyle = {
  padding: '16px 20px',
  borderBottom: '1px solid #475569',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
} as const;

const emptyPipelineStyle = {
  padding: '48px',
  textAlign: 'center',
  color: '#6b7280',
} as const;

const pipelineItemRowStyle = {
  padding: '16px 20px',
  borderBottom: '1px solid #374151',
} as const;

const expandedContentStyle = {
  marginTop: '12px',
  padding: '12px',
  backgroundColor: '#0f172a',
  borderRadius: '8px',
} as const;

const expandedContentTextStyle = {
  whiteSpace: 'pre-wrap',
  fontSize: '14px',
  color: '#e2e8f0',
  fontFamily: 'inherit',
  margin: 0,
} as const;

const ingestPanelStyle = {
  border: '1px solid #334155',
  borderRadius: '12px',
  padding: '12px 14px',
  backgroundColor: '#030712',
  display: 'grid',
  gap: '8px',
} as const;

const recommendationCardStyle = {
  borderRadius: '12px',
  border: '1px solid #1f2937',
  backgroundColor: '#020617',
  padding: '12px',
} as const;

const feedCardStyle = {
  borderRadius: '16px',
  backgroundColor: '#020617',
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
} as const;

const platformBadgeStyle = {
  color: '#38bdf8',
  fontSize: '12px',
  border: '1px solid rgba(56,189,248,0.4)',
  borderRadius: '999px',
  padding: '2px 10px',
} as const;

const scoreBadgeStyle = {
  color: '#fcd34d',
  fontWeight: 600,
  fontSize: '12px',
} as const;

const systemReadoutStyle = {
  borderRadius: '12px',
  border: '1px solid #273449',
  backgroundColor: '#06101f',
  padding: '10px',
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
} as const;

const evalCellStyle = {
  color: '#94a3b8',
  fontSize: '11px',
} as const;

const approveLineRowStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: '10px',
  borderRadius: '12px',
  border: '1px solid rgba(148,163,184,0.4)',
  padding: '8px',
  backgroundColor: '#030712',
} as const;

const draftTextStyle = {
  background: '#030712',
  padding: '8px 10px',
  borderRadius: '10px',
  border: '1px solid #334155',
  margin: 0,
  color: '#e2e8f0',
  fontSize: '13px',
  lineHeight: 1.55,
  whiteSpace: 'pre-wrap',
  flex: 1,
} as const;

const agentSectionStyle = {
  borderRadius: '14px',
  border: '1px solid #1f2937',
  backgroundColor: '#020617',
  overflow: 'hidden',
} as const;

const agentSectionSummaryStyle = {
  cursor: 'pointer',
  listStyle: 'none',
  padding: '14px 16px',
  display: 'flex',
  justifyContent: 'space-between',
  gap: '12px',
  alignItems: 'center',
  color: 'white',
} as const;

const workspaceFileCardStyle = {
  borderRadius: '12px',
  border: '1px solid #1f2937',
  backgroundColor: '#030712',
  padding: '12px',
} as const;

const emptyMessageStyle = {
  borderRadius: '14px',
  border: '1px dashed #334155',
  backgroundColor: '#020617',
  padding: '16px',
  color: '#64748b',
  fontSize: '13px',
  lineHeight: 1.6,
} as const;

const pillStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  borderRadius: '999px',
  fontSize: '11px',
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  padding: '5px 10px',
} as const;
