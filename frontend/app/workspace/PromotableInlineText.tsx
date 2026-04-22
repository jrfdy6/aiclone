'use client';

import { useMemo, useRef, useState } from 'react';

type InlineStyle = NonNullable<JSX.IntrinsicElements['div']['style']>;

type CanonResult = {
  deltaId?: string;
  targetLabel?: string;
};

type PromotableInlineTextProps = {
  text: string;
  promotableText?: string;
  textStyle?: InlineStyle;
  tone?: string;
  hoverHint?: string;
  onCanon: (fragmentText: string, fullText: string) => Promise<CanonResult | void>;
  onUndo?: (deltaId: string) => Promise<void>;
  onRemove?: (fragmentText: string) => void;
};

type PromotableToken = {
  raw: string;
  fragmentText?: string;
  key: string;
};

function buildPromotableTokens(text: string): PromotableToken[] {
  const normalized = text.replace(/\r\n/g, '\n');
  if (!normalized.trim()) {
    return [];
  }

  const tokens: PromotableToken[] = [];
  const pattern = /\n+|[^.!?\n]+(?:[.!?]+|$)/g;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = pattern.exec(normalized)) !== null) {
    const raw = match[0];
    const cleaned = raw.replace(/^[\-\u2022\s]+/, '').trim();
    const words = cleaned.split(/\s+/).filter(Boolean).length;
    if (!cleaned || raw.includes('\n') || words < 4) {
      tokens.push({ raw, key: `plain-${index++}` });
      continue;
    }
    tokens.push({ raw, fragmentText: cleaned, key: `fragment-${index++}` });
  }

  return tokens.length > 0 ? tokens : [{ raw: normalized, key: 'plain-0' }];
}

function truncate(value: string) {
  const normalized = value.trim();
  if (normalized.length <= 38) return normalized;
  return `${normalized.slice(0, 35)}...`;
}

export default function PromotableInlineText({
  text,
  promotableText,
  textStyle,
  tone = '#38bdf8',
  hoverHint = 'Keep',
  onCanon,
  onUndo,
  onRemove,
}: PromotableInlineTextProps) {
  const tokens = useMemo(() => buildPromotableTokens(promotableText ?? text), [promotableText, text]);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [undoingKey, setUndoingKey] = useState<string | null>(null);
  const [dismissedKeys, setDismissedKeys] = useState<Record<string, true>>({});
  const [savedByKey, setSavedByKey] = useState<Record<string, { deltaId?: string; targetLabel?: string }>>({});
  const closeTimerRef = useRef<number | null>(null);

  const clearCloseTimer = () => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const scheduleClose = () => {
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setActiveKey(null);
      closeTimerRef.current = null;
    }, 120);
  };

  const activate = (key: string) => {
    clearCloseTimer();
    setActiveKey(key);
  };

  const handleCanon = async (token: PromotableToken) => {
    if (!token.fragmentText) return;
    setSavingKey(token.key);
    try {
      const result = await onCanon(token.fragmentText, text);
      setSavedByKey((current) => ({
        ...current,
        [token.key]: { deltaId: result?.deltaId, targetLabel: result?.targetLabel },
      }));
      setActiveKey(token.key);
    } finally {
      setSavingKey(null);
    }
  };

  const handleUndo = async (token: PromotableToken) => {
    if (!token.fragmentText) return;
    const deltaId = savedByKey[token.key]?.deltaId;
    if (!deltaId || !onUndo) return;
    setUndoingKey(token.key);
    try {
      await onUndo(deltaId);
      setSavedByKey((current) => {
        const next = { ...current };
        delete next[token.key];
        return next;
      });
      setActiveKey(token.key);
    } finally {
      setUndoingKey(null);
    }
  };

  const handleRemove = (token: PromotableToken) => {
    if (!token.fragmentText) return;
    setDismissedKeys((current) => ({ ...current, [token.key]: true }));
    onRemove?.(token.fragmentText);
    setActiveKey(null);
  };

  if (tokens.length === 0) {
    return null;
  }

  const rootTextStyle = { ...(textStyle ?? {}), whiteSpace: 'pre-wrap' } as InlineStyle;

  return (
    <div style={rootTextStyle}>
      {tokens.map((token) => {
        if (!token.fragmentText || dismissedKeys[token.key]) {
          return <span key={token.key}>{token.raw}</span>;
        }

        const isActive = activeKey === token.key;
        const isSaving = savingKey === token.key;
        const isUndoing = undoingKey === token.key;
        const isSaved = Boolean(savedByKey[token.key]);
        const savedLabel = savedByKey[token.key]?.targetLabel?.trim() || 'Brain';

        return (
          <span
            key={token.key}
            style={{
              position: 'relative',
              borderRadius: '6px',
              backgroundColor: isActive ? `${tone}1a` : isSaved ? `${tone}10` : 'transparent',
              boxShadow: isActive ? `inset 0 0 0 1px ${tone}55` : isSaved ? `inset 0 0 0 1px ${tone}33` : 'none',
              cursor: 'pointer',
              transition: 'background-color 120ms ease, box-shadow 120ms ease',
            }}
            onMouseEnter={() => activate(token.key)}
            onMouseLeave={scheduleClose}
            onClick={() => activate(token.key)}
          >
            {token.raw}
            {isActive && (
              <span
                style={{
                  position: 'absolute',
                  left: 0,
                  bottom: '100%',
                  transform: 'translateY(-6px)',
                  zIndex: 20,
                  display: 'inline-flex',
                  gap: '6px',
                  alignItems: 'center',
                  borderRadius: '999px',
                  border: '1px solid rgba(15, 23, 42, 0.78)',
                  background: 'rgba(2, 6, 23, 0.96)',
                  boxShadow: '0 14px 30px rgba(2, 6, 23, 0.48)',
                  padding: '6px',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={() => activate(token.key)}
                onMouseLeave={scheduleClose}
              >
                {isSaved ? (
                  <>
                    <span
                      style={{
                        color: '#cbd5e1',
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '0 4px 0 6px',
                      }}
                    >
                      {`Saved to ${savedLabel}`}
                    </span>
                    <button
                      onClick={() => void handleUndo(token)}
                      disabled={isUndoing}
                      style={overlayActionStyle('#f8fafc', isUndoing)}
                    >
                      {isUndoing ? 'Undoing…' : 'Undo'}
                    </button>
                    <button onClick={() => handleRemove(token)} style={overlayActionStyle('#94a3b8', false)}>
                      Remove
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => void handleCanon(token)}
                      disabled={isSaving}
                      style={overlayActionStyle(tone, isSaving)}
                    >
                      {isSaving ? 'Saving…' : hoverHint}
                    </button>
                    <button onClick={() => handleRemove(token)} style={overlayActionStyle('#94a3b8', false)}>
                      Remove
                    </button>
                    <span
                      style={{
                        color: '#94a3b8',
                        fontSize: '11px',
                        maxWidth: '220px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {truncate(token.fragmentText)}
                    </span>
                  </>
                )}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}

function overlayActionStyle(tone: string, disabled: boolean): InlineStyle {
  return {
    borderRadius: '999px',
    border: `1px solid ${disabled ? '#334155' : `${tone}66`}`,
    backgroundColor: disabled ? '#111827' : `${tone}14`,
    color: disabled ? '#64748b' : tone,
    padding: '6px 10px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
  };
}
