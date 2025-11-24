/**
 * API Client for AI Clone Backend
 * Centralized API utilities for all frontend requests
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export interface Prospect {
  prospect_id: string;
  user_id: string;
  name: string;
  email?: string;
  phone?: string;
  job_title: string;
  company: string;
  website?: string;
  linkedin?: string;
  approval_status: 'pending' | 'approved' | 'rejected';
  fit_score?: number;
  referral_capacity?: number;
  signal_strength?: number;
  best_outreach_angle?: string;
  segment?: string;
  priority_score?: number;
  created_at?: number;
  updated_at?: number;
}

export interface OutreachSequence {
  prospect_id: string;
  segment: string;
  sequence_type: string;
  connection_request?: { variants: Array<{ variant: number; message: string }> };
  initial_dm?: { variants: Array<{ variant: number; message: string }> };
  followup_1?: { variants: Array<{ variant: number; message: string }> };
  followup_2?: { variants: Array<{ variant: number; message: string }> };
  followup_3?: { variants: Array<{ variant: number; message: string }> };
  current_step: number;
  status: string;
}

export interface WeeklyCadenceEntry {
  day: string;
  date: string;
  time: string;
  prospect_id: string;
  prospect_name: string;
  segment: string;
  outreach_type: string;
  sequence_step: number;
  message_variant: number;
  priority_score: number;
}

export interface WeeklyReport {
  success: boolean;
  week_start: string;
  week_end: string;
  total_posts: number;
  avg_engagement_rate: number;
  best_pillar?: string;
  top_hashtags: string[];
  top_audience_segments: string[];
  outreach_summary?: {
    connection_accept_rate: number;
    dm_reply_rate: number;
    meetings_booked: number;
    total_connection_requests: number;
    total_dms_sent: number;
  };
  recommendations: string[];
}

// Generic API fetch wrapper
async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Prospect API
export const prospectAPI = {
  discover: async (user_id: string, params: {
    industry?: string;
    location?: string;
    max_results?: number;
  }) => {
    return apiFetch<{ success: boolean; discovered_count: number; prospects: Prospect[] }>(
      '/api/prospects/discover',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, ...params }),
      }
    );
  },

  approve: async (user_id: string, prospect_ids: string[], status: 'approved' | 'rejected') => {
    return apiFetch<{ success: boolean; approved_count: number; rejected_count: number }>(
      '/api/prospects/approve',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, prospect_ids, approval_status: status }),
      }
    );
  },

  score: async (user_id: string, prospect_ids: string[]) => {
    return apiFetch<{ success: boolean; scored_count: number; prospects: Prospect[] }>(
      '/api/prospects/score',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, prospect_ids }),
      }
    );
  },

  list: async (user_id: string, status?: string) => {
    return apiFetch<{ success: boolean; prospects: Prospect[]; total: number }>(
      `/api/prospects/list?user_id=${user_id}${status ? `&status=${status}` : ''}`
    );
  },
};

// Outreach API
export const outreachAPI = {
  segment: async (user_id: string, prospect_ids?: string[]) => {
    return apiFetch<{ success: boolean; total_prospects: number; segments: Record<string, number> }>(
      '/api/outreach/segment',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, prospect_ids }),
      }
    );
  },

  prioritize: async (user_id: string, params: {
    min_fit_score?: number;
    min_referral_capacity?: number;
    min_signal_strength?: number;
    segment?: string;
    limit?: number;
  }) => {
    return apiFetch<{ success: boolean; total_scored: number; top_tier_count: number; prospects: Prospect[] }>(
      '/api/outreach/prioritize',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, ...params }),
      }
    );
  },

  generateSequence: async (user_id: string, prospect_id: string, sequence_type = '3-step', num_variants = 3) => {
    return apiFetch<{ success: boolean; prospect_id: string; segment: string; sequence: OutreachSequence; variants: Record<string, any[]> }>(
      '/api/outreach/sequence/generate',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, prospect_id, sequence_type, num_variants }),
      }
    );
  },

  trackEngagement: async (user_id: string, prospect_id: string, outreach_type: string, engagement_status: string, engagement_data: Record<string, any> = {}) => {
    return apiFetch<{ success: boolean }>(
      '/api/outreach/track-engagement',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, prospect_id, outreach_type, engagement_status, engagement_data }),
      }
    );
  },

  weeklyCadence: async (user_id: string, target_connection_requests = 40, target_followups = 30) => {
    return apiFetch<{ success: boolean; week_start: string; week_end: string; total_outreach: number; entries: WeeklyCadenceEntry[]; distribution: Record<string, number> }>(
      '/api/outreach/cadence/weekly',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, target_connection_requests, target_followups }),
      }
    );
  },

  metrics: async (user_id: string, date_range_days = 30) => {
    return apiFetch<{
      success: boolean;
      total_outreach: number;
      connection_requests_sent: number;
      dms_sent: number;
      followups_sent: number;
      replies_received: number;
      meetings_booked: number;
      reply_rate: number;
      meeting_rate: number;
      segment_performance: Record<string, any>;
    }>(
      '/api/outreach/metrics',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, date_range_days }),
      }
    );
  },
};

// Metrics API
export const metricsAPI = {
  weeklyReport: async (user_id: string) => {
    return apiFetch<WeeklyReport>(
      '/api/metrics/enhanced/weekly-report',
      {
        method: 'POST',
        body: JSON.stringify({ user_id }),
      }
    );
  },

  updateContentMetrics: async (user_id: string, metrics: any) => {
    return apiFetch<{ success: boolean; metrics_id: string; engagement_rate: number }>(
      '/api/metrics/enhanced/content/update',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, ...metrics }),
      }
    );
  },

  updateProspectMetrics: async (user_id: string, metrics: any) => {
    return apiFetch<{ success: boolean; prospect_metric_id: string; reply_rate: number; meeting_rate: number }>(
      '/api/metrics/enhanced/prospects/update',
      {
        method: 'POST',
        body: JSON.stringify({ user_id, ...metrics }),
      }
    );
  },
};

