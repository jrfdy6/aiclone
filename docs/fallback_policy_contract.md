# Fallback Policy Contract

## Purpose

This document defines how fallback behavior should be classified across the repo.

The goal is not to remove all fallbacks. The goal is to make fallback behavior explicit so operators and automation surfaces can distinguish:

- resilience that is intentionally allowed
- temporary scaffolding that should eventually be reduced
- conditions that should be treated as failure rather than silently recovered

## Policy classes

### `allowed_in_production`

Use this when fallback behavior is an intentional resilience layer and remains acceptable in the live system.

Examples:

- provider failover where losing the primary model should not block execution
- a frontend registry mirror that keeps workspace metadata available during backend disruption
- a manual/local persistence lane that is part of the intended operator workflow

### `temporary_scaffold`

Use this when fallback behavior is currently useful, but it represents incomplete convergence, incomplete data quality, or partial workflow closure.

Examples:

- falling back from `content_safe_operator_lessons` to raw `content_reservoir`
- rebuilding content context at runtime because persisted snapshots are not reliable enough
- serving seeded email threads when Gmail is not yet connected

### `treat_as_failure`

Use this when the system should stop, alert, or fail verification rather than silently recover.

Examples:

- a page classified as live that calls an unmounted API
- a reference-only donor/archive subtree missing from its declared location
- future fallbacks that would commingle verified truth with speculative or unsafe data

## Current inventory

The current machine-readable inventory is exposed through Brain via:

- `GET /api/brain/fallback-policy`

Current fallback families:

1. `content_generation_provider_failover`
   - Class: `allowed_in_production`
   - Owner: `content_pipeline`
   - Reason: model/provider resilience is currently intentional

2. `content_signal_safe_lessons_to_reservoir`
   - Class: `temporary_scaffold`
   - Owner: `content_pipeline`
   - Reason: preserves continuity, but weakens the content trust boundary

3. `content_snapshot_runtime_rebuild`
   - Class: `temporary_scaffold`
   - Owner: `content_pipeline`
   - Reason: useful recovery path while persisted snapshots are not strict enough

4. `content_retrieval_support_reinsertion`
   - Class: `temporary_scaffold`
   - Owner: `content_pipeline`
   - Reason: rescues grounding after over-aggressive filtering

5. `email_ops_sample_threads`
   - Class: `temporary_scaffold`
   - Owner: `email_ops`
   - Reason: keeps the inbox explorable before Gmail is mandatory/live

6. `prospects_firestore_local_storage`
   - Class: `allowed_in_production`
   - Owner: `prospects`
   - Reason: manual/local intake is part of the intended workflow

7. `workspace_registry_frontend_mirror`
   - Class: `allowed_in_production`
   - Owner: `workspace_runtime`
   - Reason: explicit frontend resilience layer

## Rules

1. New fallbacks must declare a `policy_class` before shipping.
2. `temporary_scaffold` fallbacks should carry an owner and an exit condition.
3. `treat_as_failure` conditions should be eligible for verification-gate enforcement.
4. Brain and repo-truth surfaces should summarize fallback class counts, not just raw fallback presence.

## Relationship to repo-surface truth

Fallback class and surface class are different.

- surface class answers whether a page or subtree is live, scaffolded, legacy, or reference-only
- fallback class answers whether a recovery behavior is intentional, temporary, or unacceptable

Both are needed to keep runtime truth legible.
