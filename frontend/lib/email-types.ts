export type EmailDraftType = 'acknowledge' | 'qualify' | 'schedule' | 'decline_or_redirect';
export type EmailDraftMode = 'email_reply' | 'email_follow_up' | 'outbound_email';
export type EmailDraftEngine = 'template' | 'content_generation' | 'codex_job';
export type EmailDraftSourceMode = 'email_thread_grounded' | 'persona_only' | 'selected_source' | 'recent_signals';
export type EmailThreadDraftLifecycleAction = 'clear_local_draft' | 'unlink_provider_draft' | 'clear_all_draft_state';

export type EmailMessage = {
  id: string;
  direction: 'inbound' | 'outbound';
  from_address: string;
  from_name?: string | null;
  to_addresses: string[];
  cc_addresses: string[];
  subject: string;
  body_text: string;
  internet_message_id?: string | null;
  references_header?: string | null;
  in_reply_to_header?: string | null;
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
  draft_mode?: EmailDraftMode | null;
  draft_engine?: EmailDraftEngine | null;
  draft_source_mode?: EmailDraftSourceMode | null;
  draft_generated_at?: string | null;
  draft_job_id?: string | null;
  draft_audit?: Record<string, unknown> | null;
  draft_confidence?: number | null;
  provider_draft_id?: string | null;
  provider_draft_status?: string | null;
  provider_draft_saved_at?: string | null;
  provider_draft_error?: string | null;
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
  draft_mode?: EmailDraftMode | null;
  draft_engine?: EmailDraftEngine | null;
  source_mode?: EmailDraftSourceMode | null;
};

export type EmailThreadSaveDraftResponse = {
  thread: EmailThread;
  provider_draft_id?: string | null;
  provider_draft_status?: string | null;
  message: string;
};

export type EmailThreadDraftLifecycleResponse = {
  thread: EmailThread;
  action: EmailThreadDraftLifecycleAction;
  message: string;
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
  drafts_enabled: boolean;
  send_enabled: boolean;
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
