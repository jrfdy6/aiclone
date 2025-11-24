/**
 * API Helper Functions for Phase 4 APIs
 * Centralized API calls with error handling
 */

import { getApiUrl } from './api-client';

const API_URL = () => getApiUrl();

// Generic fetch wrapper
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('http') 
    ? endpoint 
    : `${API_URL()}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

// Type definitions for API responses
export interface ResearchTask {
  id: string;
  user_id: string;
  title: string;
  input_source: string;
  source_type: 'keywords' | 'urls' | 'profile';
  research_engine: 'perplexity' | 'firecrawl' | 'google_search';
  status: 'queued' | 'running' | 'done' | 'failed';
  priority: 'high' | 'medium' | 'low';
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  outputs_available: boolean;
  result_id?: string | null;
}

export interface ResearchTaskListResponse {
  success: boolean;
  tasks: ResearchTask[];
  total: number;
}

export interface ResearchTaskResponse {
  success: boolean;
  task: ResearchTask;
}

export interface ResearchInsightsResponse {
  success: boolean;
  task_id: string;
  task_title: string;
  insights: {
    summary: string;
    pain_points: string[];
    opportunities: string[];
    suggested_outreach: string[];
    content_angles: string[];
    key_findings: string[];
    sources: Array<{ url: string; title?: string }>;
  };
}

// Research Tasks API
export const researchTasksAPI = {
  list: (userId: string, params?: { status?: string; limit?: number }): Promise<ResearchTaskListResponse> => {
    const query = new URLSearchParams({ user_id: userId, ...params as any });
    return apiRequest<ResearchTaskListResponse>(`/api/research-tasks?${query}`);
  },
  get: (taskId: string): Promise<ResearchTaskResponse> => {
    return apiRequest<ResearchTaskResponse>(`/api/research-tasks/${taskId}`);
  },
  create: (data: any): Promise<ResearchTaskResponse> => {
    return apiRequest<ResearchTaskResponse>('/api/research-tasks', { method: 'POST', body: JSON.stringify(data) });
  },
  run: (taskId: string): Promise<ResearchTaskResponse> => {
    return apiRequest<ResearchTaskResponse>(`/api/research-tasks/${taskId}/run`, { method: 'POST' });
  },
  getInsights: (taskId: string): Promise<ResearchInsightsResponse> => {
    return apiRequest<ResearchInsightsResponse>(`/api/research-tasks/${taskId}/insights`);
  },
};

// Activity API
export const activityAPI = {
  list: (userId: string, params?: { type?: string; limit?: number }) => {
    const query = new URLSearchParams({ user_id: userId, ...params as any });
    return apiRequest(`/api/activity?${query}`);
  },
  get: (activityId: string) => apiRequest(`/api/activity/${activityId}`),
  create: (data: any) => apiRequest('/api/activity', { method: 'POST', body: JSON.stringify(data) }),
};

// Templates API
export const templatesAPI = {
  list: (userId: string, params?: { category?: string; is_favorite?: boolean; limit?: number }) => {
    const query = new URLSearchParams({ user_id: userId, ...params as any });
    return apiRequest(`/api/templates?${query}`);
  },
  get: (templateId: string) => apiRequest(`/api/templates/${templateId}`),
  create: (data: any) => apiRequest('/api/templates', { method: 'POST', body: JSON.stringify(data) }),
  update: (templateId: string, data: any) => 
    apiRequest(`/api/templates/${templateId}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (templateId: string) => apiRequest(`/api/templates/${templateId}`, { method: 'DELETE' }),
  toggleFavorite: (templateId: string) => 
    apiRequest(`/api/templates/${templateId}/favorite`, { method: 'POST' }),
  duplicate: (templateId: string, userId: string) => 
    apiRequest(`/api/templates/${templateId}/duplicate?user_id=${userId}`, { method: 'POST' }),
  use: (templateId: string, data: any) => 
    apiRequest(`/api/templates/${templateId}/use`, { method: 'POST', body: JSON.stringify(data) }),
};

// Vault API
export const vaultAPI = {
  list: (userId: string, params?: { category?: string; tags?: string; limit?: number }) => {
    const query = new URLSearchParams({ user_id: userId, ...params as any });
    return apiRequest(`/api/vault?${query}`);
  },
  get: (itemId: string) => apiRequest(`/api/vault/${itemId}`),
  create: (data: any) => apiRequest('/api/vault', { method: 'POST', body: JSON.stringify(data) }),
  update: (itemId: string, data: any) => 
    apiRequest(`/api/vault/${itemId}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (itemId: string) => apiRequest(`/api/vault/${itemId}`, { method: 'DELETE' }),
  getTopicClusters: (userId: string) => apiRequest(`/api/vault/topics/clusters?user_id=${userId}`),
  getTrendlines: (userId: string, days: number = 30) => 
    apiRequest(`/api/vault/trendlines?user_id=${userId}&days=${days}`),
};

// Personas API
export const personasAPI = {
  list: (userId: string) => apiRequest(`/api/personas?user_id=${userId}`),
  get: (personaId: string) => apiRequest(`/api/personas/${personaId}`),
  getDefault: (userId: string) => apiRequest(`/api/personas/default?user_id=${userId}`),
  create: (data: any) => apiRequest('/api/personas', { method: 'POST', body: JSON.stringify(data) }),
  update: (personaId: string, data: any) => 
    apiRequest(`/api/personas/${personaId}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (personaId: string) => apiRequest(`/api/personas/${personaId}`, { method: 'DELETE' }),
  setDefault: (personaId: string, userId: string) => 
    apiRequest(`/api/personas/${personaId}/set-default?user_id=${userId}`, { method: 'POST' }),
};

// System Logs API
export const systemLogsAPI = {
  list: (userId: string, params?: { level?: string; category?: string; limit?: number }) => {
    const query = new URLSearchParams({ user_id: userId, ...params as any });
    return apiRequest(`/api/system/logs?${query}`);
  },
  get: (logId: string) => apiRequest(`/api/system/logs/${logId}`),
  getStats: (userId: string) => apiRequest(`/api/system/logs/stats/summary?user_id=${userId}`),
  rerun: (logId: string) => apiRequest(`/api/system/logs/${logId}/rerun`, { method: 'POST' }),
};

// Automations API
export const automationsAPI = {
  list: (userId: string, params?: { status?: string; limit?: number }) => {
    const query = new URLSearchParams({ user_id: userId, ...params as any });
    return apiRequest(`/api/automations?${query}`);
  },
  get: (automationId: string) => apiRequest(`/api/automations/${automationId}`),
  create: (data: any) => apiRequest('/api/automations', { method: 'POST', body: JSON.stringify(data) }),
  update: (automationId: string, data: any) => 
    apiRequest(`/api/automations/${automationId}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (automationId: string) => apiRequest(`/api/automations/${automationId}`, { method: 'DELETE' }),
  activate: (automationId: string) => 
    apiRequest(`/api/automations/${automationId}/activate`, { method: 'POST' }),
  deactivate: (automationId: string) => 
    apiRequest(`/api/automations/${automationId}/deactivate`, { method: 'POST' }),
  getExecutions: (automationId: string, limit: number = 50) => 
    apiRequest(`/api/automations/${automationId}/executions?limit=${limit}`),
};

// Playbooks API
export const playbooksAPI = {
  list: (userId: string, params?: { is_favorite?: boolean }) => {
    const query = new URLSearchParams({ user_id: userId, ...params as any });
    return apiRequest(`/api/playbooks?${query}`);
  },
  get: (playbookId: string, userId: string) => 
    apiRequest(`/api/playbooks/${playbookId}?user_id=${userId}`),
  toggleFavorite: (playbookId: string, userId: string) => 
    apiRequest(`/api/playbooks/${playbookId}/favorite?user_id=${userId}`, { method: 'POST' }),
  getFavorites: (userId: string) => apiRequest(`/api/playbooks/favorites/list?user_id=${userId}`),
  run: (playbookId: string, data: any) => 
    apiRequest(`/api/playbooks/${playbookId}/run`, { method: 'POST', body: JSON.stringify(data) }),
  getExecutions: (playbookId: string, userId: string, limit: number = 50) => 
    apiRequest(`/api/playbooks/${playbookId}/executions?user_id=${userId}&limit=${limit}`),
};

