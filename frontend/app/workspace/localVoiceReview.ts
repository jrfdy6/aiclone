export const LOCAL_VOICE_REVIEW_SCHEMA_VERSION = 'ai_clone_voice_review/v1';

export type LocalVoiceReviewDecision = 'approve' | 'revise' | 'park';

export type LocalVoiceReviewSource = {
  queueId: string;
  generatedText: string;
  editedText?: string | null;
  decision: LocalVoiceReviewDecision;
  generationJobId?: string | null;
  generationOptionIndex?: number | null;
  topic?: string | null;
  lane?: string | null;
  ownerNotes?: string | null;
};

export type LocalVoiceReviewPacket = {
  schema_version: typeof LOCAL_VOICE_REVIEW_SCHEMA_VERSION;
  source: 'feezie_owner_review';
  exported_at: string;
  privacy: 'local_only';
  promote_edited: false;
  decision: LocalVoiceReviewDecision;
  queue_id: string;
  generation_job_id: string | null;
  generation_option_index: number | null;
  generated_text: string;
  edited_text: string | null;
  rejected_texts: string[];
  context: {
    queue_id: string;
    generation_job_id: string | null;
    generation_option_index: number | null;
    channel: 'linkedin';
    post_type: 'owner_review';
    topic: string;
    topic_tags: string[];
    owner_notes: string;
  };
};

function cleanText(value?: string | null) {
  return String(value ?? '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
}

function cleanQueueId(value: string) {
  const cleaned = value.trim();
  if (!cleaned) {
    throw new Error('A queue id is required for local voice feedback.');
  }
  return cleaned;
}

export function buildLocalVoiceReviewPacket(
  source: LocalVoiceReviewSource,
  exportedAt = new Date().toISOString(),
): LocalVoiceReviewPacket {
  const queueId = cleanQueueId(source.queueId);
  const generatedText = cleanText(source.generatedText);
  if (!generatedText) {
    throw new Error('The exact generated draft is required for local voice feedback.');
  }
  const editedText = source.decision === 'park' ? '' : cleanText(source.editedText);
  const generationJobId = cleanText(source.generationJobId) || null;
  const generationOptionIndex = Number.isInteger(source.generationOptionIndex)
    ? Number(source.generationOptionIndex)
    : null;
  const lane = cleanText(source.lane).toLowerCase();
  return {
    schema_version: LOCAL_VOICE_REVIEW_SCHEMA_VERSION,
    source: 'feezie_owner_review',
    exported_at: exportedAt,
    privacy: 'local_only',
    promote_edited: false,
    decision: source.decision,
    queue_id: queueId,
    generation_job_id: generationJobId,
    generation_option_index: generationOptionIndex,
    generated_text: generatedText,
    edited_text: editedText || null,
    rejected_texts: source.decision === 'park' ? [generatedText] : [],
    context: {
      queue_id: queueId,
      generation_job_id: generationJobId,
      generation_option_index: generationOptionIndex,
      channel: 'linkedin',
      post_type: 'owner_review',
      topic: cleanText(source.topic),
      topic_tags: lane ? [lane] : [],
      owner_notes: cleanText(source.ownerNotes),
    },
  };
}

export function localVoiceReviewFilename(queueId: string) {
  const safeQueueId = cleanQueueId(queueId)
    .replace(/[^a-z0-9_-]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'owner-review';
  return `ai-clone-voice-review-${safeQueueId}.json`;
}

export function downloadLocalVoiceReviewPacket(packet: LocalVoiceReviewPacket) {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    throw new Error('Local voice feedback can only be downloaded from the browser.');
  }
  const blob = new Blob([`${JSON.stringify(packet, null, 2)}\n`], { type: 'application/json' });
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = localVoiceReviewFilename(packet.queue_id);
  link.style.display = 'none';
  document.body.appendChild(link);
  try {
    link.click();
  } finally {
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
  }
}
