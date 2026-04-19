export type EmailDraftType = 'acknowledge' | 'qualify' | 'schedule' | 'decline_or_redirect';

export type EmailMessage = {
  id: string;
  direction: 'inbound' | 'outbound';
  from_address: string;
  from_name?: string | null;
  to_addresses: string[];
  cc_addresses: string[];
  subject: string;
  body_text: string;
  received_at: string;
};

export type EmailThread = {
  id: string;
  provider: string;
  provider_thread_id?: string | null;
  provider_labels: string[];
  workspace_key: string;
  lane: string;
  status: string;
  subject: string;
  from_address: string;
  from_name?: string | null;
  organization?: string | null;
  to_addresses: string[];
  alias_hint?: string | null;
  confidence_score: number;
  needs_human: boolean;
  high_value: boolean;
  high_risk: boolean;
  sla_at_risk: boolean;
  linked_opportunity_id?: string | null;
  summary?: string | null;
  excerpt?: string | null;
  routing_reasons: string[];
  messages: EmailMessage[];
  draft_subject?: string | null;
  draft_body?: string | null;
  draft_type?: EmailDraftType | null;
  draft_generated_at?: string | null;
  last_message_at: string;
  manual_workspace_key?: string | null;
  manual_lane?: string | null;
  manual_notes?: string | null;
  last_route_source: 'auto' | 'manual';
  pm_card_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type EmailThreadListResponse = {
  items: EmailThread[];
  total: number;
  needs_human_count: number;
  high_value_count: number;
  high_risk_count: number;
  workspace_counts: Record<string, number>;
  agc_lane_counts: Record<string, number>;
  data_mode: 'sample_only' | 'provider_sync';
  last_synced_at?: string | null;
};

export type EmailSyncResponse = {
  status: string;
  thread_count: number;
  data_mode: 'sample_only' | 'provider_sync';
  seeded_samples: boolean;
  last_synced_at?: string | null;
};

export type EmailThreadDraftResponse = {
  thread: EmailThread;
  draft_subject: string;
  draft_body: string;
  draft_type: EmailDraftType;
};

export type EmailThreadEscalateResponse = {
  thread: EmailThread;
  pm_card_id?: string | null;
  message: string;
};

export type EmailProviderStatusResponse = {
  configured: boolean;
  connected: boolean;
  dependencies_ready: boolean;
  account_email?: string | null;
  client_file?: string | null;
  token_file?: string | null;
  token_present: boolean;
  refreshable: boolean;
  sync_query?: string | null;
  max_results: number;
  scopes: string[];
  error?: string | null;
};
