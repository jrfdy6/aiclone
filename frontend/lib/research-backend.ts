import 'server-only';

import { cache } from 'react';

const BACKEND_TIMEOUT_MS = 15_000;

type BackendRead<T> = {
  state: 'ready' | 'degraded';
  payload: T | null;
  reasonCodes: string[];
};

function boundedText(value: unknown, limit: number, fallback = ''): string {
  const text = typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : fallback;
  return text.slice(0, limit);
}

function boundedStringArray(value: unknown, count: number, length: number): string[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, count).map((item) => boundedText(item, length)).filter(Boolean);
}

function boundedRecordArray(value: unknown, count = 50): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) return [];
  return value.slice(0, count).filter(
    (item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item),
  );
}

export type ResearchTopic = {
  id: string;
  slug: string;
  title: string;
  date: string;
  timestamp: number;
  summary: string;
  prospectIntelligence?: Record<string, unknown>;
  outreachTemplates?: unknown[];
  contentIdeas?: unknown[];
  opportunityInsights?: unknown[];
  keywords?: string[];
  trendingTopics?: string[];
};

export type ResearchDiscovery = {
  id: string;
  slug: string;
  title: string;
  date: string;
  timestamp: number;
  count: number;
  source?: string;
  location?: string;
  specialty?: string;
};

export type ResearchLibrary = {
  state: 'ready' | 'degraded';
  reasonCodes: string[];
  topics: ResearchTopic[];
  discoveries: ResearchDiscovery[];
};

export type ResearchDetail = {
  id: string;
  type: 'Topic Intelligence' | 'Prospect Discovery';
  title: string;
  date: string;
  summary: string;
  prospectIntelligence?: {
    target_personas?: string[];
    pain_points?: string[];
    language_patterns?: string[];
  };
  outreachTemplates?: any[];
  contentIdeas?: any[];
  opportunityInsights?: any[];
  keywords?: string[];
  trendingTopics?: string[];
};

function epochSeconds(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 10_000_000_000 ? value / 1_000 : value;
  }
  if (typeof value === 'string') {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return parsed / 1_000;
  }
  return 0;
}

export function generateResearchSlug(title: string, timestamp: number): string {
  const date = new Date(timestamp * 1_000);
  const month = Number.isFinite(date.getTime())
    ? date.toLocaleString('en', { month: 'short' }).toLowerCase()
    : 'unknown';
  const year = Number.isFinite(date.getTime()) ? date.getFullYear() : 'undated';
  const slug = String(title || 'research')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return `${slug}-${month}-${year}`;
}

function dateLabel(timestamp: number, long = false): string {
  const date = new Date(timestamp * 1_000);
  if (!Number.isFinite(date.getTime())) return 'Date unavailable';
  return date.toLocaleDateString('en-US', {
    month: long ? 'long' : 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

async function backendRead<T>(path: string): Promise<BackendRead<T>> {
  const token = String(process.env.CONTROL_PLANE_SERVICE_TOKEN || '').trim();
  if (!token) {
    return { state: 'degraded', payload: null, reasonCodes: ['control_plane_token_unavailable'] };
  }
  const backend = (process.env.BACKEND_API_URL || 'https://aiclone-production-32dc.up.railway.app').replace(/\/$/, '');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
  try {
    const response = await fetch(`${backend}${path}`, {
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!response.ok) {
      return { state: 'degraded', payload: null, reasonCodes: [`backend_status_${response.status}`] };
    }
    const payload = await response.json() as T & { state?: string; reason_codes?: string[] };
    const headerState = response.headers.get('X-AI-Clone-Firestore-State');
    const state = payload.state === 'degraded' || headerState === 'degraded' ? 'degraded' : 'ready';
    return {
      state,
      payload,
      reasonCodes: boundedStringArray(payload.reason_codes, 16, 100),
    };
  } catch (error) {
    const reason = error instanceof Error && error.name === 'AbortError'
      ? 'backend_timeout'
      : 'backend_unavailable';
    return { state: 'degraded', payload: null, reasonCodes: [reason] };
  } finally {
    clearTimeout(timeout);
  }
}

async function loadResearchLibrary(): Promise<ResearchLibrary> {
  const userId = encodeURIComponent(process.env.DEFAULT_USER_ID || 'default-user');
  const [topicRead, discoveryRead] = await Promise.all([
    backendRead<{ state?: string; reason_codes?: string[]; results?: Array<Record<string, unknown>> }>(
      `/api/topic-intelligence/user/${userId}?limit=20`,
    ),
    backendRead<{ state?: string; reason_codes?: string[]; discoveries?: Array<Record<string, unknown>> }>(
      `/api/prospect-discovery/user/${userId}?limit=20`,
    ),
  ]);

  const topics = (topicRead.payload?.results || []).map((data) => {
    const timestamp = epochSeconds(data.created_at);
    const title = boundedText(data.theme_display || data.theme, 500, 'Topic Intelligence');
    const prospect = data.prospect_intelligence && typeof data.prospect_intelligence === 'object' && !Array.isArray(data.prospect_intelligence)
      ? data.prospect_intelligence as Record<string, unknown>
      : undefined;
    return {
      id: boundedText(data.research_id || data.id, 300, generateResearchSlug(title, timestamp)),
      slug: generateResearchSlug(title, timestamp),
      title,
      date: dateLabel(timestamp),
      timestamp,
      summary: boundedText(data.summary, 20_000),
      prospectIntelligence: prospect ? {
        target_personas: boundedStringArray(prospect.target_personas, 100, 1_000),
        pain_points: boundedStringArray(prospect.pain_points, 100, 1_000),
        language_patterns: boundedStringArray(prospect.language_patterns, 100, 1_000),
      } : undefined,
      outreachTemplates: boundedRecordArray(data.outreach_templates),
      contentIdeas: boundedRecordArray(data.content_ideas),
      opportunityInsights: boundedRecordArray(data.opportunity_insights),
      keywords: boundedStringArray(data.keywords, 100, 300),
      trendingTopics: boundedStringArray(data.trending_topics, 100, 500),
    } satisfies ResearchTopic;
  });

  const discoveries = (discoveryRead.payload?.discoveries || []).map((data) => {
    const timestamp = epochSeconds(data.created_at);
    const source = boundedText(data.source, 100, 'Prospect');
    const location = boundedText(data.location, 500, 'Unknown');
    const title = `${source} Discovery - ${location}`;
    return {
      id: boundedText(data.discovery_id || data.id, 128, generateResearchSlug(title, timestamp)),
      slug: generateResearchSlug(`${source}-${location}`, timestamp),
      title,
      date: dateLabel(timestamp),
      timestamp,
      count: Math.min(Math.max(Number(data.prospect_count || data.total_found || 0) || 0, 0), 1_000_000),
      source,
      location,
      specialty: data.specialty ? boundedText(data.specialty, 500) : undefined,
    } satisfies ResearchDiscovery;
  });

  return {
    state: topicRead.state === 'ready' && discoveryRead.state === 'ready' ? 'ready' : 'degraded',
    reasonCodes: [...new Set([...topicRead.reasonCodes, ...discoveryRead.reasonCodes])],
    topics,
    discoveries,
  };
}

export const fetchResearchLibrary = cache(loadResearchLibrary);

export async function fetchResearchBySlug(slug: string): Promise<{
  state: 'ready' | 'degraded';
  reasonCodes: string[];
  research: ResearchDetail | null;
}> {
  const library = await fetchResearchLibrary();
  const topic = library.topics.find((item) => item.slug === slug);
  if (topic) {
    return {
      state: library.state,
      reasonCodes: library.reasonCodes,
      research: {
        ...topic,
        type: 'Topic Intelligence' as const,
        date: dateLabel(topic.timestamp, true),
      } as ResearchDetail,
    };
  }
  const discovery = library.discoveries.find((item) => item.slug === slug);
  if (discovery) {
    return {
      state: library.state,
      reasonCodes: library.reasonCodes,
      research: {
        ...discovery,
        type: 'Prospect Discovery' as const,
        date: dateLabel(discovery.timestamp, true),
        summary: `Found ${discovery.count} prospects in ${discovery.location || 'an unspecified location'} using ${discovery.source || 'the configured discovery source'}.`,
        keywords: [discovery.source, discovery.location, discovery.specialty].filter(Boolean) as string[],
      } as ResearchDetail,
    };
  }
  return { state: library.state, reasonCodes: library.reasonCodes, research: null };
}
