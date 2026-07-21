'use client';

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';

import { controlApiGet, controlApiPost } from '@/lib/control-api';
import {
  EXECUTIVE_DECISIONS_ENDPOINT,
  executiveDecisionActionEndpoint,
  executiveDecisionCoverage,
  executableDecisionActions,
  normalizeExecutiveDecisionResponse,
  type ExecutiveDecision,
  type ExecutiveDecisionAction,
  type ExecutiveDecisionQueueResponse,
} from '@/lib/executive-decisions';
import { formatUiTimestamp } from '@/lib/ui-dates';

import styles from './ExecutiveDecisionQueue.module.css';

type QueueView = 'today' | 'all';

type ExecutiveDecisionQueueProps = {
  onAction?: (decision: ExecutiveDecision, action: ExecutiveDecisionAction) => Promise<unknown>;
  onActionComplete?: (decision: ExecutiveDecision, action: ExecutiveDecisionAction) => Promise<void> | void;
  onOpenContext?: (decision: ExecutiveDecision, href: string) => boolean | void;
};

type ActionResponse = {
  message?: string;
};

async function loadExecutiveDecisions(): Promise<ExecutiveDecisionQueueResponse> {
  const payload = await controlApiGet<unknown>(EXECUTIVE_DECISIONS_ENDPOINT, {
    cache: 'no-store',
    timeoutMs: 40_000,
  });
  return normalizeExecutiveDecisionResponse(payload);
}

async function runExecutiveDecisionAction(
  decision: ExecutiveDecision,
  action: ExecutiveDecisionAction,
): Promise<ActionResponse> {
  return controlApiPost<ActionResponse>(executiveDecisionActionEndpoint(decision, action), {
    confirmed: true,
  });
}

export function ExecutiveDecisionQueue({
  onAction = runExecutiveDecisionAction,
  onActionComplete,
  onOpenContext,
}: ExecutiveDecisionQueueProps) {
  const headingId = useId();
  const [view, setView] = useState<QueueView>('today');
  const [snapshot, setSnapshot] = useState<ExecutiveDecisionQueueResponse | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'live' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [actioningKey, setActioningKey] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const mountedRef = useRef(false);
  const requestSequenceRef = useRef(0);

  const refresh = useCallback(async (quiet = false): Promise<boolean> => {
    const requestId = requestSequenceRef.current + 1;
    requestSequenceRef.current = requestId;
    if (!quiet) setRefreshing(true);
    try {
      const response = await loadExecutiveDecisions();
      if (!mountedRef.current || requestSequenceRef.current !== requestId) return false;
      setSnapshot(response);
      setLoadState('live');
      setError(null);
      return true;
    } catch (loadError) {
      if (mountedRef.current && requestSequenceRef.current === requestId) {
        setLoadState('error');
        setError(readableError(loadError));
      }
      return false;
    } finally {
      if (mountedRef.current && requestSequenceRef.current === requestId && !quiet) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refresh(true);
    return () => {
      mountedRef.current = false;
      requestSequenceRef.current += 1;
    };
  }, [refresh]);

  const coverage = useMemo(
    () => snapshot
      ? executiveDecisionCoverage(snapshot)
      : { partial: false, failedSources: [], degradedSources: [] },
    [snapshot],
  );
  const visibleItems = view === 'today' ? snapshot?.today ?? [] : snapshot?.all_pending ?? [];
  const todayCount = snapshot?.today.length ?? 0;
  const allCount = snapshot?.all_pending.length ?? 0;

  const handleAction = useCallback(async (decision: ExecutiveDecision, action: ExecutiveDecisionAction) => {
    if (
      action.requires_confirmation &&
      !window.confirm(`${action.label} “${decision.title}”? This updates the decision on its original page.`)
    ) {
      return;
    }

    const actionKey = `${decision.id}:${action.id}`;
    setActioningKey(actionKey);
    setFeedback(null);
    setError(null);
    try {
      const result = await onAction(decision, action);
      if (!mountedRef.current) return;
      const queueRefreshed = await refresh(true);
      if (!mountedRef.current) return;
      let sourceSurfacesRefreshed = true;
      try {
        await onActionComplete?.(decision, action);
      } catch (refreshError) {
        sourceSurfacesRefreshed = false;
        if (mountedRef.current) {
          setError(`The decision was recorded, but another Home surface did not refresh: ${readableError(refreshError)}`);
        }
      }
      const responseMessage =
        result && typeof result === 'object' && 'message' in result && typeof result.message === 'string'
          ? result.message
          : null;
      if (mountedRef.current) {
        setFeedback(
          responseMessage ||
          (queueRefreshed && sourceSurfacesRefreshed
            ? `${action.label} recorded. The source and executive queue were refreshed.`
            : `${action.label} recorded. Use Refresh decisions before acting on this item again.`),
        );
      }
    } catch (actionError) {
      if (!mountedRef.current) return;
      const queueRefreshed = await refresh(true);
      let sourceSurfacesRefreshed = true;
      try {
        await onActionComplete?.(decision, action);
      } catch {
        sourceSurfacesRefreshed = false;
      }
      if (mountedRef.current) {
        const refreshNote = queueRefreshed && sourceSurfacesRefreshed
          ? ' The source was re-read because the action may have partially completed.'
          : ' The follow-up refresh was incomplete; use Refresh decisions before retrying.';
        setError(`${readableError(actionError)}${refreshNote}`);
      }
    } finally {
      if (mountedRef.current) setActioningKey(null);
    }
  }, [onAction, onActionComplete, refresh]);

  return (
    <section
      className={styles.shell}
      aria-labelledby={headingId}
      aria-busy={loadState === 'loading' || refreshing || Boolean(actioningKey)}
    >
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Executive sign-offs</p>
          <h2 className={styles.title} id={headingId}>What needs you today</h2>
          <p className={styles.description}>
            Neo ranks the few decisions worth interrupting you for. Act here when the evidence is enough, or open the original page for full context.
          </p>
        </div>
        <div className={styles.headerMeta}>
          <div className={styles.countRow} aria-label="Decision counts">
            <span className={styles.countPill}><strong>{todayCount}</strong> today</span>
            <span className={styles.countPill}><strong>{allCount}</strong> all pending</span>
          </div>
          <span>{snapshot?.generated_at ? `Ranked ${formatUiTimestamp(snapshot.generated_at)}` : 'Checking every decision source…'}</span>
          <button className={styles.refreshButton} type="button" onClick={() => void refresh()} disabled={refreshing}>
            {refreshing ? 'Refreshing…' : 'Refresh decisions'}
          </button>
        </div>
      </div>

      <div className={styles.tabs} role="group" aria-label="Pending decision views">
        <button
          className={styles.tab}
          type="button"
          id={`${headingId}-today-tab`}
          aria-controls={`${headingId}-panel`}
          aria-pressed={view === 'today'}
          onClick={() => setView('today')}
        >
          Today ({todayCount})
        </button>
        <button
          className={styles.tab}
          type="button"
          id={`${headingId}-all-tab`}
          aria-controls={`${headingId}-panel`}
          aria-pressed={view === 'all'}
          onClick={() => setView('all')}
        >
          All pending ({allCount})
        </button>
      </div>

      {coverage.partial && snapshot ? (
        <div className={styles.warning} role="status">
          <strong>Partially verified.</strong>{' '}
          {coverageWarning(snapshot, coverage)}
        </div>
      ) : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      {feedback ? <div className={styles.feedback} role="status" aria-live="polite">{feedback}</div> : null}

      <div id={`${headingId}-panel`} role="region" aria-labelledby={`${headingId}-${view}-tab`}>
        {loadState === 'loading' && !snapshot ? (
          <div className={styles.loadingList} aria-label="Loading executive decisions">
            <div className={styles.skeleton} />
            <div className={styles.skeleton} />
          </div>
        ) : loadState === 'error' && !snapshot ? (
          <QueueEmpty
            title="The decision queue could not be verified"
            message="Use retry before treating the inbox as clear. Your source pages and their decisions are unchanged."
            actionLabel="Retry"
            onAction={() => void refresh()}
          />
        ) : visibleItems.length === 0 ? (
          <QueueEmpty
            title={coverage.partial ? 'No decisions found in the sources that responded' : view === 'today' ? 'Nothing is ranked for today' : 'No pending sign-offs'}
            message={
              coverage.partial
                ? 'One or more sources could not be verified, so this is not a confirmed all-clear.'
                : view === 'today' && allCount > 0
                  ? `${allCount} lower-priority decision${allCount === 1 ? ' is' : 's are'} still available in All pending.`
                  : 'Neo did not find a decision that currently needs your sign-off.'
            }
            {...(view === 'today' && allCount > 0
              ? { actionLabel: 'View all pending', onAction: () => setView('all') }
              : {})}
          />
        ) : (
          <div className={styles.list}>
            {visibleItems.map((decision, index) => (
              <DecisionCard
                key={decision.id}
                decision={decision}
                rank={index + 1}
                actioningKey={actioningKey}
                onAction={handleAction}
                onOpenContext={onOpenContext}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function DecisionCard({
  decision,
  rank,
  actioningKey,
  onAction,
  onOpenContext,
}: {
  decision: ExecutiveDecision;
  rank: number;
  actioningKey: string | null;
  onAction: (decision: ExecutiveDecision, action: ExecutiveDecisionAction) => Promise<void>;
  onOpenContext?: (decision: ExecutiveDecision, href: string) => boolean | void;
}) {
  const titleId = useId();
  const evidence = decision.evidence.slice(0, 2);
  const additionalEvidence = decision.evidence.slice(2);
  const safeActions = executableDecisionActions(decision);
  const contextHref = decision.actions.find((action) => action.kind === 'open_context')?.href || decision.context_href;

  return (
    <article className={styles.card} data-priority={decision.priority} aria-labelledby={titleId}>
      <div className={styles.cardHeader}>
        <div className={styles.rankAndTitle}>
          <span className={styles.rank} aria-label={`Rank ${rank}`}>#{rank}</span>
          <h3 className={styles.cardTitle} id={titleId}>{decision.title}</h3>
        </div>
        <div className={styles.badges}>
          <span className={`${styles.badge} ${styles.priorityBadge}`}>{humanize(decision.priority)} priority</span>
          <span className={`${styles.badge} ${styles.freshness}`} data-freshness={decision.freshness}>
            {freshnessLabel(decision.freshness)}
          </span>
        </div>
      </div>

      <div className={styles.metaRow}>
        <span>{humanize(decision.workspace_key)}</span>
        <span>{humanize(decision.source_type)}</span>
        {decision.updated_at ? <span>Updated {formatUiTimestamp(decision.updated_at)}</span> : null}
      </div>

      <div className={styles.explanationGrid}>
        <div className={styles.explanation}>
          <p className={styles.fieldLabel}>What changed</p>
          <p className={styles.fieldText}>{decision.what_changed}</p>
        </div>
        <div className={styles.explanation}>
          <p className={styles.fieldLabel}>Why it matters</p>
          <p className={styles.fieldText}>{decision.why_it_matters}</p>
        </div>
      </div>

      <div className={styles.recommendation}>
        <p className={styles.fieldLabel}>Neo recommends</p>
        <p className={styles.fieldText}>{decision.recommendation}</p>
      </div>

      <div className={styles.evidence}>
        <p className={styles.fieldLabel}>Evidence</p>
        {evidence.length > 0 ? (
          <ul className={styles.evidenceList}>
            {evidence.map((item, index) => <li className={styles.evidenceItem} key={`${decision.id}-evidence-${index}`}>{item}</li>)}
          </ul>
        ) : (
          <p className={styles.evidenceItem}>No supporting evidence was attached. Open the source context before acting.</p>
        )}
        {additionalEvidence.length > 0 ? (
          <details className={styles.moreEvidence}>
            <summary>{additionalEvidence.length} more evidence item{additionalEvidence.length === 1 ? '' : 's'}</summary>
            <ul className={styles.evidenceList}>
              {additionalEvidence.map((item, index) => <li className={styles.evidenceItem} key={`${decision.id}-more-evidence-${index}`}>{item}</li>)}
            </ul>
          </details>
        ) : null}
      </div>

      <div className={styles.actions}>
        {safeActions.map((action, index) => {
          const actionKey = `${decision.id}:${action.id}`;
          const actioning = actioningKey === actionKey;
          return (
            <button
              className={styles.actionButton}
              data-primary={index === 0}
              key={action.id}
              type="button"
              disabled={Boolean(actioningKey)}
              onClick={() => void onAction(decision, action)}
            >
              {actioning ? 'Saving…' : action.label}
            </button>
          );
        })}
        <a
          className={styles.contextLink}
          href={contextHref}
          onClick={(event) => {
            if (onOpenContext?.(decision, contextHref) === true) event.preventDefault();
          }}
        >
          Open in context
        </a>
      </div>
    </article>
  );
}

function QueueEmpty({
  title,
  message,
  actionLabel,
  onAction,
}: {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      <p className={styles.emptyText}>{message}</p>
      {actionLabel && onAction ? (
        <button className={styles.emptyButton} type="button" onClick={onAction}>{actionLabel}</button>
      ) : null}
    </div>
  );
}

function freshnessLabel(value: ExecutiveDecision['freshness']): string {
  if (value === 'today') return 'Updated today';
  if (value === 'recent') return 'Recently updated';
  if (value === 'aging') return 'Aging';
  if (value === 'stale') return 'Stale evidence';
  return 'Freshness unknown';
}

function coverageWarning(
  snapshot: ExecutiveDecisionQueueResponse,
  coverage: ReturnType<typeof executiveDecisionCoverage>,
): string {
  const details = [
    coverage.failedSources.length > 0 ? `${coverage.failedSources.join(', ')} failed verification` : null,
    coverage.degradedSources.length > 0 ? `${coverage.degradedSources.join(', ')} returned degraded coverage` : null,
  ].filter((detail): detail is string => Boolean(detail));
  if (details.length > 0) {
    return `${details.join('; ')}. Loaded decisions remain available, but this is not an all-clear.`;
  }
  return snapshot.summary.verification_status === 'partial'
    ? 'The backend reported partial source coverage. Loaded decisions remain available, but this is not an all-clear.'
    : 'Source coverage was not reported. Loaded decisions remain available, but this is not an all-clear.';
}

function readableError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) return error.message.trim();
  return 'The executive decision queue could not be loaded.';
}

function humanize(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}
