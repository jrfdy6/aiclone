# OpenClaw Cron Rehab Execution Checklist

Use this document as the working checklist for the cron rehab sprint.

Status markers:
- `[ ]` not started
- `[-]` in progress
- `[x]` done
- `[!]` blocked

## Phase 0: Freeze, Audit, Baseline

- [x] Export the current OpenClaw cron inventory from `/Users/neo/.openclaw/cron/jobs.json`
- [x] Build a baseline table for every job:
  - name
  - enabled
  - schedule
  - runtime
  - delivery target
  - last status
  - last delivered
  - referenced files/scripts
  - writes to
  - estimated cost class
- [x] Mark each job as:
  - keep in OpenClaw
  - keep in OpenClaw but refactor
  - move to `launchd`
  - move to Railway
  - disable/replace
- [ ] Freeze net-new cron additions until the audit is complete

Artifacts:
- `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_inventory_2026-03-31.json`
- `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_inventory_2026-03-31.md`
- `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_runtime_matrix_2026-03-31.md`

## Phase 1: Contract And Path Repair

- [x] Fix all stale references to `docs/context_flush_SOP.md`
- [x] Decide whether to restore, replace, or remove the missing context flush SOP reference
- [x] Create `memory/doc-updates.md` or remove its use from all jobs and skills
- [x] Fix all references to `scripts/check_index_status.sh`
- [x] Either move `check_index_status.sh` into `scripts/` or update all prompts/skills to the real path
- [x] Add a path-contract checker that validates every cron job’s referenced files and scripts
- [x] Run the checker against the full current job list

Artifacts:
- `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31.json`
- `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31.md`
- `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31_postfix2.json`
- `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31_postfix2.md`

## Phase 2: Automation Truth And Run Ledger

- [x] Treat `/Users/neo/.openclaw/cron/jobs.json` as the current scheduler truth
- [x] Add a backend mirror layer for real OpenClaw job state
- [x] Define `automation_runs` schema:
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
- [ ] Stop relying on static automation definitions as the effective truth
- [x] Add mismatch detection between OpenClaw state and backend-visible state
- [x] Prefer `/Users/neo/.openclaw/cron/runs/*.jsonl` over stale `jobs.json` state for latest-run truth
- [x] Suppress intentional `NO_REPLY` non-delivery in the mismatch layer

Artifacts:
- `/Users/neo/.openclaw/workspace/docs/openclaw_automation_truth_contract.md`
- `/Users/neo/.openclaw/workspace/backend/app/models/automations.py`
- `/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py`
- `/Users/neo/.openclaw/workspace/backend/app/services/automation_run_service.py`
- `/Users/neo/.openclaw/workspace/backend/app/services/automation_mismatch_service.py`
- `/Users/neo/.openclaw/workspace/backend/app/services/open_brain_db.py`
- `/Users/neo/.openclaw/workspace/backend/app/routes/automations.py`

## Phase 3: Delivery Hygiene

- [x] Replace broken `Context Guard` webchat delivery with a reliable alert path
- [x] Reclassify all jobs by delivery type:
  - alert
  - digest
  - approval
  - silent/log-only
- [x] Reduce routine success delivery into Discord
- [x] Keep Discord focused on blockers, decisions, and concise digests
- [x] Add delivery health metrics:
  - run ok + delivered
  - run ok + not delivered
  - run error + delivered
  - run error + not delivered

## Phase 4: Deterministic Execution Refactor

- [ ] Identify all jobs relying on brittle freeform edit behavior
- [ ] Extract deterministic helper scripts for:
  - append-only log writes
  - file existence checks
  - status polling
  - report assembly
  - checksum capture
- [ ] Refactor `Rolling Docs` away from fragile edit-only behavior
- [ ] Refactor `Daily Memory Flush` where deterministic helpers can replace prompt-only work
- [ ] Refactor `Memory Health Check` to use stable script paths and helper commands
- [ ] Verify gateway logs are no longer filling with `oldText`/exact-match edit failures from cron

## Phase 5: Runtime Rationalization

- [ ] Confirm which jobs should stay inside OpenClaw
- [ ] Confirm which jobs should move to `launchd`
- [ ] Confirm which jobs should move to Railway
- [ ] Keep context-heavy synthesis jobs in OpenClaw:
  - `Progress Pulse`
  - `Morning Daily Brief`
  - `Nightly Self-Improvement`
  - `Dream Cycle`
  - `Oracle Ledger`
- [ ] Reassess backups and monitors for cheaper deterministic execution
- [ ] Document final runtime placement for every job

## Phase 6: Workspace Routing Primitives

- [ ] Add `workspace_key` to PM cards
- [ ] Add `workspace_key` to standups
- [ ] Add `workspace_key` to daily briefs
- [ ] Add `workspace_key` to automation runs
- [ ] Add `scope` to distinguish:
  - `workspace`
  - `shared_ops`
  - `global`
- [ ] Add `owner_agent` to relevant models and events
- [ ] Define normalized automation event packet shape
- [ ] Define rules for when cron findings become PM tasks

## Phase 7: Team Operating System Buildout

- [ ] Formalize the three agents:
  - `Neo`
  - `Jean-Claude`
  - `Bruce Lee`
- [ ] Define role responsibilities:
  - `Neo`: execution lead
  - `Jean-Claude`: strategist/reviewer
  - `Bruce Lee`: chief of staff / routing / cadence
- [ ] Formalize the five workspaces:
  - `linkedin-os`
  - `fusion-os`
  - `easyoutfitapp`
  - `ai-swag-store`
  - `agc`
- [ ] Build workspace standup flow
- [ ] Build executive ops standup flow
- [ ] Make PM board filter cleanly by workspace and scope
- [ ] Add promotion rules so knowledge can move across workspaces intentionally, not automatically

## Current Known Issues To Resolve Early

- [x] `Context Guard` now delivers through the Discord alert path on live runs
- [x] `Rolling Docs` dropped out of the live mismatch list after the safer skill path landed
- [x] `Progress Pulse` stale session assumption is no longer producing fake `gateway openclaw-control-ui` blockers
- [x] `Oracle Ledger` manual verification now finishes `ok` and `delivered`
- [x] `Memory Health Check` manual verification now finishes `ok` and `delivered`
- [x] `context_flush_SOP.md` reference is stale/missing
- [x] `memory/doc-updates.md` is missing
- [x] `check_index_status.sh` path is inconsistent with job and skill references
- [x] stale `media-intake-guard` plugin config warning removed from `openclaw.json` and cleared after gateway restart
- [-] backend automation view now mirrors jobs + latest run logs, but still needs DB-backed historical verification
- [x] `Memory Archive Sweep` has an observed run and no longer surfaces as a mismatch
- [x] intentional `delivery.mode = "none"` jobs are suppressed from mismatch delivery-failure warnings
- [x] monitor jobs now use failure-alert routing while staying silent on successful runs

## Acceptance Gate Before Scaling

Do not move into full 3-agent / 5-workspace expansion until all are true:

- [ ] real OpenClaw cron state is mirrored into the app
- [x] active action-required cron mismatches are cleared from the live report
- [ ] no critical jobs point at stale or missing paths
- [ ] delivery failures are visible and actionable
- [ ] deterministic jobs no longer overuse agent turns
- [ ] PM, standups, and briefs can all consume real automation state
- [ ] workspace routing primitives exist or are implementation-ready
