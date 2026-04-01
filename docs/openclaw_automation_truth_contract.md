# OpenClaw Automation Truth Contract

This document captures the first Phase 2 implementation state after the cron rehab audit.

## What Exists Now

The backend no longer has to rely only on the static automation registry.

Current behavior:
- if `/Users/neo/.openclaw/cron/jobs.json` exists, the backend mirrors live OpenClaw jobs from that file
- latest run data prefers `/Users/neo/.openclaw/cron/runs/*.jsonl` when those run logs exist
- if it does not exist, the backend falls back to the legacy static registry

Current surfaces:
- `/api/automations/`
  - returns mirrored automation definitions
  - returns latest mirrored run state under `runs`
  - returns mismatch summary under `mismatches`
  - returns `source_of_truth`
- `/api/automations/runs`
  - returns the latest mirrored run entries
- `/api/automations/mismatches`
  - returns structured drift/health mismatches

Implementation files:
- `/Users/neo/.openclaw/workspace/backend/app/models/automations.py`
- `/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py`
- `/Users/neo/.openclaw/workspace/backend/app/routes/automations.py`

## What This Solves

- Brain/Ops can now see real local OpenClaw job state when the local jobs file is present
- the backend can distinguish:
  - mirrored OpenClaw jobs
  - static fallback definitions
- the backend now exposes latest run status, delivery state, and action-needed signals
- the backend now prefers real run-log truth over stale `jobs.json` state for latest-run status
- the backend now suppresses intentional `NO_REPLY` non-delivery so quiet watchdog runs do not look like broken alerts
- the backend now exposes mismatch categories such as:
  - delivery failure
  - run error
  - no observed run yet

## What This Does Not Solve Yet

- there is not yet verified persisted `automation_runs` history in a DB-enabled runtime
- there is still no full historical ledger beyond the latest run mirrored from `/cron/runs/*.jsonl` in the local fallback path
- there is still no mismatch detector between:
  - local OpenClaw state
  - backend DB history
  - frontend-visible state over time
- `workspace_key`, `scope`, and `owner_agent` are only partially populated today

Update after the first ledger pass:
- the backend now includes `automation_runs` schema and a sync service
- the sync path degrades gracefully when DB deps or the database are unavailable
- local fallback can still serve mirrored runs directly from `jobs.json`
- the backend now includes mismatch detection over the mirrored automation layer
- the remaining gap is persisted historical verification in a DB-enabled runtime

## Current Phase 2 Boundary

Phase 2 is now split into:

1. `truth mirror`
   - done enough to use
   - backend can read real OpenClaw scheduler state

2. `persisted run ledger`
   - code path exists now
   - still needs DB-enabled runtime verification and historical rollout

## Next Required Step

Finish the persisted run ledger rollout with:
- `job_id`
- `job_name`
- `run_at`
- `finished_at`
- `status`
- `delivered`
- `delivery_channel`
- `delivery_target`
- `summary`
- `error`
- `artifact_refs`
- `workspace_key`
- `scope`
- `owner_agent`
- `action_required`

That should become the canonical historical layer behind the mirror.
