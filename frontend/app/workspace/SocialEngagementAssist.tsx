'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { controlApiGet, controlApiPost } from '@/lib/control-api';
import {
  AssistedSocialPlatform,
  copyDraftAndOpenNativeSurface,
  openNativeSocialSurface,
} from '@/lib/social-assist-actions';


type EngagementType = 'comment' | 'message' | 'post';

type SocialEngagementOpportunity = {
  opportunity_id: string;
  platform: AssistedSocialPlatform;
  source_url: string;
  source_title?: string | null;
  source_author?: string | null;
  visible_text: string;
  draft_text: string;
  engagement_type: EngagementType;
  status: string;
  created_at: string;
  owner_execution_required: boolean;
  external_mutation_performed: boolean;
  provenance?: {
    capture_method?: string;
    discovery_route?: string;
    no_scraping?: boolean;
  };
};

type OpportunityListResponse = {
  opportunities?: SocialEngagementOpportunity[];
  owner_execution_required?: boolean;
  automatic_platform_mutation?: boolean;
};

type ActionReceipt = {
  action_event_id: string;
  action: 'prepare_copy' | 'open_native_surface';
  opportunity_id: string;
  platform: AssistedSocialPlatform;
  native_surface_url: string;
  draft_text?: string | null;
  owner_execution_required: boolean;
  external_mutation_performed: boolean;
};

function newRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `social-assist-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function platformLabel(platform: AssistedSocialPlatform) {
  return platform === 'linkedin' ? 'LinkedIn' : 'Instagram';
}

function compactDate(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'time unavailable' : parsed.toLocaleString();
}

const inputStyle = {
  width: '100%',
  minWidth: 0,
  boxSizing: 'border-box',
  borderRadius: '10px',
  border: '1px solid #334155',
  backgroundColor: '#020617',
  color: '#e2e8f0',
  padding: '10px 12px',
  fontSize: '13px',
} as const;

const actionStyle = (tone: string, disabled = false) => ({
  borderRadius: '10px',
  border: `1px solid ${tone}66`,
  backgroundColor: `${tone}18`,
  color: disabled ? '#64748b' : tone,
  padding: '9px 12px',
  fontSize: '12px',
  fontWeight: 700,
  cursor: disabled ? 'not-allowed' : 'pointer',
} as const);

export default function SocialEngagementAssist() {
  const [platform, setPlatform] = useState<AssistedSocialPlatform>('linkedin');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceTitle, setSourceTitle] = useState('');
  const [sourceAuthor, setSourceAuthor] = useState('');
  const [visibleText, setVisibleText] = useState('');
  const [draftText, setDraftText] = useState('');
  const [engagementType, setEngagementType] = useState<EngagementType>('comment');
  const [captureRequestId, setCaptureRequestId] = useState(newRequestId);
  const [opportunities, setOpportunities] = useState<SocialEngagementOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await controlApiGet<OpportunityListResponse>('/api/workspace/social-assist/opportunities?limit=25');
      setOpportunities(Array.isArray(payload.opportunities) ? payload.opportunities : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load assisted engagement opportunities.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOpportunities();
  }, [loadOpportunities]);

  const canCapture = useMemo(
    () => Boolean(sourceUrl.trim() && visibleText.trim() && draftText.trim()) && !saving,
    [draftText, saving, sourceUrl, visibleText],
  );

  async function captureOpportunity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCapture) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const created = await controlApiPost<SocialEngagementOpportunity>('/api/workspace/social-assist/opportunities', {
        platform,
        source_url: sourceUrl,
        visible_text: visibleText,
        draft_text: draftText,
        engagement_type: engagementType,
        title: sourceTitle || null,
        author: sourceAuthor || null,
        idempotency_key: captureRequestId,
      });
      setOpportunities((current) => [created, ...current.filter((item) => item.opportunity_id !== created.opportunity_id)]);
      setSourceUrl('');
      setSourceTitle('');
      setSourceAuthor('');
      setVisibleText('');
      setDraftText('');
      setCaptureRequestId(newRequestId());
      setStatus(`${platformLabel(created.platform)} opportunity saved. No platform action was taken.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to save assisted engagement opportunity.');
    } finally {
      setSaving(false);
    }
  }

  async function prepareCopyAndOpen(opportunity: SocialEngagementOpportunity) {
    setActingId(opportunity.opportunity_id);
    setError(null);
    setStatus(null);
    try {
      const localAction = copyDraftAndOpenNativeSurface({
        platform: opportunity.platform,
        nativeUrl: opportunity.source_url,
        draftText: opportunity.draft_text,
        dependencies: {
          writeClipboard: (text) => navigator.clipboard.writeText(text),
          openWindow: (url, target, features) => window.open(url, target, features),
        },
      });
      const receipt = controlApiPost<ActionReceipt>(
        `/api/workspace/social-assist/opportunities/${encodeURIComponent(opportunity.opportunity_id)}/actions`,
        { action: 'prepare_copy', request_id: newRequestId() },
      );
      const [result, recorded] = await Promise.all([localAction, receipt]);
      if (result.externalMutationPerformed || recorded.external_mutation_performed) {
        throw new Error('Unsafe social action receipt returned by the control plane.');
      }
      setStatus(`Draft copied and ${platformLabel(opportunity.platform)} open requested. Use the source link if your browser blocked the new tab; you decide whether to use the draft.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to prepare the owner-controlled action.');
    } finally {
      setActingId(null);
    }
  }

  async function openOnly(opportunity: SocialEngagementOpportunity) {
    setActingId(opportunity.opportunity_id);
    setError(null);
    setStatus(null);
    try {
      const openedUrl = openNativeSocialSurface(
        opportunity.platform,
        opportunity.source_url,
        (url, target, features) => window.open(url, target, features),
      );
      const receipt = await controlApiPost<ActionReceipt>(
        `/api/workspace/social-assist/opportunities/${encodeURIComponent(opportunity.opportunity_id)}/actions`,
        { action: 'open_native_surface', request_id: newRequestId() },
      );
      if (receipt.native_surface_url !== openedUrl || receipt.external_mutation_performed) {
        throw new Error('Native surface receipt did not match the owner-selected source.');
      }
      setStatus(`${platformLabel(opportunity.platform)} open requested. Use the source link if your browser blocked the new tab. No platform action was taken.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to open the native surface.');
    } finally {
      setActingId(null);
    }
  }

  return (
    <section
      data-social-engagement-assist="owner-controlled-v1"
      style={{
        borderRadius: '18px',
        border: '1px solid rgba(34,197,94,0.3)',
        background: 'linear-gradient(145deg, rgba(5,46,22,0.28), rgba(2,6,23,0.98))',
        padding: '20px',
        display: 'grid',
        gap: '16px',
        minWidth: 0,
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '14px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <p style={{ color: '#4ade80', fontSize: '11px', fontWeight: 800, letterSpacing: '0.16em', margin: 0, textTransform: 'uppercase' }}>
            Assisted social review · Version 1
          </p>
          <h2 style={{ color: 'white', fontSize: '24px', margin: '5px 0 6px' }}>Capture what you can see, prepare what you may say</h2>
          <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: 1.55, margin: 0, maxWidth: '840px' }}>
            Paste a LinkedIn or Instagram item from the authenticated session you control. This records exact provenance and a reviewable draft; it never scrapes, publishes, comments, messages, reposts, likes, or follows.
          </p>
        </div>
        <span style={{ borderRadius: '999px', border: '1px solid #22c55e55', color: '#86efac', padding: '6px 10px', fontSize: '11px', fontWeight: 700 }}>
          Owner executes every native action
        </span>
      </div>

      <form onSubmit={(event) => void captureOpportunity(event)} style={{ display: 'grid', gap: '10px', minWidth: 0 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: '10px', minWidth: 0 }}>
          <label style={{ color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px', minWidth: 0 }}>
            Platform
            <select value={platform} onChange={(event) => setPlatform(event.target.value as AssistedSocialPlatform)} style={inputStyle}>
              <option value="linkedin">LinkedIn</option>
              <option value="instagram">Instagram</option>
            </select>
          </label>
          <label style={{ color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px', minWidth: 0 }}>
            Intended use
            <select value={engagementType} onChange={(event) => setEngagementType(event.target.value as EngagementType)} style={inputStyle}>
              <option value="comment">Comment draft</option>
              <option value="message">Message draft</option>
              <option value="post">Post draft</option>
            </select>
          </label>
          <label style={{ color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px', minWidth: 0, gridColumn: '1 / -1' }}>
            Exact native URL
            <input
              type="url"
              required
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              placeholder={platform === 'linkedin' ? 'https://www.linkedin.com/posts/…' : 'https://www.instagram.com/p/…'}
              style={inputStyle}
            />
          </label>
          <label style={{ color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px', minWidth: 0 }}>
            Visible author
            <input value={sourceAuthor} onChange={(event) => setSourceAuthor(event.target.value)} maxLength={300} style={inputStyle} />
          </label>
          <label style={{ color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px', minWidth: 0 }}>
            Source title or label
            <input value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} maxLength={500} style={inputStyle} />
          </label>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 290px), 1fr))', gap: '10px', minWidth: 0 }}>
          <label style={{ color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px', minWidth: 0 }}>
            Exact visible item text
            <textarea required value={visibleText} onChange={(event) => setVisibleText(event.target.value)} rows={7} maxLength={20_000} style={{ ...inputStyle, resize: 'vertical' }} />
          </label>
          <label style={{ color: '#cbd5e1', fontSize: '12px', display: 'grid', gap: '5px', minWidth: 0 }}>
            Prepared draft for your review
            <textarea required value={draftText} onChange={(event) => setDraftText(event.target.value)} rows={7} maxLength={10_000} style={{ ...inputStyle, resize: 'vertical' }} />
          </label>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button type="submit" disabled={!canCapture} style={actionStyle('#4ade80', !canCapture)}>
            {saving ? 'Saving…' : 'Save engagement opportunity'}
          </button>
          <span style={{ color: '#64748b', fontSize: '11px' }}>Only owner-supplied text is stored. No feed automation runs.</span>
        </div>
      </form>

      {status ? <p role="status" style={{ color: '#86efac', fontSize: '12px', margin: 0 }}>{status}</p> : null}
      {error ? <p role="alert" style={{ color: '#fca5a5', fontSize: '12px', margin: 0 }}>{error}</p> : null}

      <div style={{ display: 'grid', gap: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center' }}>
          <p style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 800, margin: 0 }}>Durable engagement opportunities</p>
          <button type="button" onClick={() => void loadOpportunities()} disabled={loading} style={actionStyle('#94a3b8', loading)}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
        {!loading && opportunities.length === 0 ? (
          <p style={{ color: '#64748b', fontSize: '12px', margin: 0 }}>No assisted opportunities have been saved yet.</p>
        ) : null}
        {opportunities.map((opportunity) => {
          const acting = actingId === opportunity.opportunity_id;
          return (
            <article key={opportunity.opportunity_id} style={{ borderRadius: '14px', border: '1px solid #1e293b', backgroundColor: '#020617', padding: '14px', display: 'grid', gap: '10px', minWidth: 0, width: '100%', boxSizing: 'border-box', overflowWrap: 'anywhere' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <div style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                  <p style={{ color: 'white', fontSize: '14px', fontWeight: 800, margin: 0 }}>{opportunity.source_title || `${platformLabel(opportunity.platform)} visible item`}</p>
                  <p style={{ color: '#64748b', fontSize: '11px', margin: '4px 0 0' }}>
                    {opportunity.source_author || 'Author not supplied'} · {opportunity.engagement_type} · {compactDate(opportunity.created_at)}
                  </p>
                </div>
                <span style={{ color: '#86efac', fontSize: '11px', fontWeight: 700 }}>{platformLabel(opportunity.platform)} · draft ready</span>
              </div>
              <a href={opportunity.source_url} target="_blank" rel="noreferrer" style={{ color: '#7dd3fc', fontSize: '12px', overflowWrap: 'anywhere' }}>{opportunity.source_url}</a>
              <div style={{ borderLeft: '2px solid #334155', paddingLeft: '10px', minWidth: 0, overflowWrap: 'anywhere' }}>
                <p style={{ color: '#64748b', fontSize: '10px', fontWeight: 800, letterSpacing: '0.12em', margin: '0 0 5px', textTransform: 'uppercase' }}>Prepared draft</p>
                <p style={{ color: '#cbd5e1', fontSize: '13px', lineHeight: 1.55, margin: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{opportunity.draft_text}</p>
              </div>
              <details style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                <summary style={{ color: '#94a3b8', fontSize: '11px', cursor: 'pointer' }}>Visible source text and provenance</summary>
                <p style={{ color: '#94a3b8', fontSize: '12px', lineHeight: 1.5, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{opportunity.visible_text}</p>
                <p style={{ color: '#64748b', fontSize: '10px', margin: 0 }}>
                  {opportunity.provenance?.capture_method || 'owner_supplied_visible_item'} · {opportunity.provenance?.discovery_route || 'canonical intake'} · owner-attested authenticated session · no scraping
                </p>
              </details>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button type="button" disabled={acting} onClick={() => void prepareCopyAndOpen(opportunity)} style={actionStyle('#4ade80', acting)}>
                  Copy draft + open {platformLabel(opportunity.platform)}
                </button>
                <button type="button" disabled={acting} onClick={() => void openOnly(opportunity)} style={actionStyle('#38bdf8', acting)}>
                  Open native source only
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
