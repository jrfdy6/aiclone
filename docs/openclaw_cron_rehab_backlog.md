# OpenClaw Cron Rehab Backlog

This backlog turns Phase 0 and Phase 1 of the cron rehab plan into implementation-ready tickets.

Parent docs:
- `/Users/neo/.openclaw/workspace/docs/openclaw_cron_rehab_project_plan.md`
- `/Users/neo/.openclaw/workspace/docs/openclaw_cron_rehab_execution_checklist.md`
- `/Users/neo/.openclaw/workspace/SOPs/openclaw_local_automation_sop.md`
- `/Users/neo/.openclaw/workspace/docs/cron_delivery_guidelines.md`

## Active

### OCR-001 - Freeze the current automation contract and capture the live inventory
- Outcome: create one reliable baseline of the current OpenClaw cron layer before any repairs start.
- Why first: path fixes and runtime decisions should be made against the real current inventory, not memory.
- Scope:
  - export the live job list from `/Users/neo/.openclaw/cron/jobs.json`
  - record job name, enabled state, schedule, session target, delivery target, last status, last delivered, last error, and referenced files/scripts
  - capture the current known failure list from `/Users/neo/.openclaw/logs/gateway.err.log`
- Deliverables:
  - a machine-readable cron inventory artifact
  - a human-readable baseline summary
  - a current-failures list
- Source files:
  - `/Users/neo/.openclaw/cron/jobs.json`
  - `/Users/neo/.openclaw/logs/gateway.err.log`
  - `/Users/neo/.openclaw/workspace/docs/openclaw_cron_rehab_project_plan.md`
- Validation:
  - every current job in `jobs.json` is accounted for
  - the baseline includes `Rolling Docs`, `Context Guard`, and `Progress Pulse`
  - no ticket after this one relies on undocumented cron assumptions
- Status: `done`
- Artifacts:
  - `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_inventory_2026-03-31.json`
  - `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_inventory_2026-03-31.md`

### OCR-002 - Classify every job by runtime, cost, and role in the system
- Outcome: decide which current jobs belong in OpenClaw, which should lean on deterministic helpers, and which may belong elsewhere later.
- Why second: runtime and cost decisions should happen before prompt/path repair grows into redesign.
- Scope:
  - classify each job into:
    - keep in OpenClaw
    - keep in OpenClaw but refactor around deterministic helpers
    - candidate for `launchd`
    - candidate for Railway
    - disable/replace
  - tag each job as:
    - `shared_ops`
    - future `workspace`
    - `global`
  - note whether the job truly needs model reasoning
- Deliverables:
  - runtime placement matrix
  - cost and role classification table
- Source files:
  - `/Users/neo/.openclaw/cron/jobs.json`
  - `/Users/neo/.openclaw/workspace/SOPs/openclaw_local_automation_sop.md`
  - `/Users/neo/.openclaw/workspace/docs/cron_delivery_guidelines.md`
- Validation:
  - every job has one explicit runtime recommendation
  - every job has one explicit scope classification
  - the matrix distinguishes deterministic work from synthesis work
- Status: `done`
- Artifact:
  - `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_runtime_matrix_2026-03-31.md`

### OCR-003 - Add a cron contract checker for file and script references
- Outcome: fail fast when a cron job or supporting skill references a missing file or wrong path.
- Why now: stale pathing is one of the biggest confirmed failure causes.
- Scope:
  - parse cron job messages for absolute file/script references
  - optionally inspect linked skills where relevant
  - verify file existence
  - emit a report of missing paths and suspicious references
- Deliverables:
  - checker script under `scripts/`
  - report output format suitable for CI/manual use
- Source files:
  - `/Users/neo/.openclaw/cron/jobs.json`
  - `/Users/neo/.openclaw/workspace/skills/`
  - `/Users/neo/.openclaw/workspace/scripts/`
- Validation:
  - the checker flags the known missing `context_flush_SOP.md`
  - the checker flags the inconsistent `check_index_status.sh` path
  - the checker can be rerun after fixes and return clean output
- Status: `done`
- Artifacts:
  - `/Users/neo/.openclaw/workspace/scripts/check_openclaw_cron_contract.py`
  - `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31.json`
  - `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31.md`
  - `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31_postfix2.json`
  - `/Users/neo/.openclaw/workspace/memory/reports/openclaw_cron_contract_check_2026-03-31_postfix2.md`

### OCR-004 - Decide and codify the canonical locations for context flush, doc updates, and index checks
- Outcome: resolve the current contract drift instead of patching references one by one with guesswork.
- Why now: without a canonical location decision, path repair will drift again.
- Scope:
  - decide whether `context_flush_SOP.md` should:
    - be restored at `docs/context_flush_SOP.md`
    - be replaced by another canonical doc
    - or be removed from cron/skill prompts
  - decide whether `memory/doc-updates.md` is still part of the supported cron contract
  - decide whether `check_index_status.sh` belongs at workspace root or under `scripts/`
- Deliverables:
  - one canonical-path decision for each missing or inconsistent artifact
  - updated references in parent docs if the canonical location changes
- Source files:
  - `/Users/neo/.openclaw/workspace/docs/cron_delivery_guidelines.md`
  - `/Users/neo/.openclaw/workspace/SOPs/openclaw_local_automation_sop.md`
  - `/Users/neo/.openclaw/workspace/AGENTS.md`
  - `/Users/neo/.openclaw/workspace/skills/morning-daily-brief/SKILL.md`
  - `/Users/neo/.openclaw/workspace/skills/rolling-docs-refresh/SKILL.md`
  - `/Users/neo/.openclaw/workspace/skills/memory-health-check/SKILL.md`
- Validation:
  - each artifact has one canonical home
  - there is no ambiguity left in the contract
  - downstream tickets can repair references against a stable target
- Status: `done`
- Decisions:
  - restore `docs/context_flush_SOP.md`
  - retain `memory/doc-updates.md` as the cron-facing log
  - support `scripts/check_index_status.sh` as the canonical helper path while keeping the root script as the underlying implementation

### OCR-005 - Repair stale references across cron jobs, skills, and docs
- Outcome: eliminate known file-not-found and wrong-path failures in the current cron layer.
- Depends on:
  - `OCR-003`
  - `OCR-004`
- Scope:
  - update job messages in `/Users/neo/.openclaw/cron/jobs.json`
  - update any linked skill docs
  - update parent docs and AGENTS guidance where they still point at stale locations
- Known repairs to include:
  - `docs/context_flush_SOP.md`
  - `memory/doc-updates.md`
  - `check_index_status.sh`
- Deliverables:
  - corrected cron/job references
  - corrected skill references
  - corrected operator docs
- Source files:
  - `/Users/neo/.openclaw/cron/jobs.json`
  - `/Users/neo/.openclaw/workspace/skills/**/SKILL.md`
  - `/Users/neo/.openclaw/workspace/AGENTS.md`
  - `/Users/neo/.openclaw/workspace/docs/*.md`
- Validation:
  - contract checker returns clean output for the repaired paths
  - the known path-related gateway errors are no longer reproducible
- Status: `done for Phase 1 contract drift`

### OCR-006 - Create missing durable artifacts required by the current cron contract
- Outcome: ensure jobs writing append-only outputs have stable destinations to write to.
- Depends on:
  - `OCR-004`
- Scope:
  - create `memory/doc-updates.md` if retained in the contract
  - create any other agreed append-only files missing from the current flow
  - add lightweight headings/usage notes where appropriate so jobs are not writing into ambiguous empty files
- Deliverables:
  - missing log artifacts created
  - minimal file contracts documented
- Source files:
  - `/Users/neo/.openclaw/workspace/memory/`
  - `/Users/neo/.openclaw/workspace/docs/cron_delivery_guidelines.md`
- Validation:
  - all retained append-only targets exist before jobs run
  - no current Phase 1 job fails due to absent target logs
- Status: `done`

### OCR-007 - Produce a before/after contract drift report
- Outcome: prove that Phase 1 actually closed the known reference problems instead of just moving them around.
- Depends on:
  - `OCR-005`
  - `OCR-006`
- Scope:
  - capture the initial contract checker output
  - capture the final contract checker output
  - summarize what was repaired, what was deferred, and what still needs runtime validation
- Deliverables:
  - one remediation report
  - a short unresolved-items list for Phase 2+
- Source files:
  - contract checker output
  - `/Users/neo/.openclaw/workspace/docs/openclaw_cron_rehab_execution_checklist.md`
- Validation:
  - known missing path failures are either repaired or explicitly deferred
  - the report can be used as the gate into Phase 2
- Status: `done`

## Queued

### OCR-008 - Add a temporary cron-additions freeze rule to operator docs
- Outcome: prevent new cron jobs from increasing drift before baseline and contract repair are complete.
- Why queued: useful guardrail, but lower priority than the actual inventory and path repairs.
- Scope:
  - add a short note to operator docs that no new cron jobs should be introduced until `OCR-001` through `OCR-007` are complete
- Source files:
  - `/Users/neo/.openclaw/workspace/AGENTS.md`
  - `/Users/neo/.openclaw/workspace/docs/openclaw_cron_rehab_project_plan.md`
- Validation:
  - the freeze rule is visible in the docs that guide automation work

## In Progress Notes

- Phase 2 truth mirror exists:
  - `/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py`
  - `/Users/neo/.openclaw/workspace/backend/app/routes/automations.py`
  - `/Users/neo/.openclaw/workspace/docs/openclaw_automation_truth_contract.md`
- Phase 2 truth mirror now prefers real OpenClaw run logs:
  - `/Users/neo/.openclaw/cron/runs/*.jsonl`
- Phase 2 ledger scaffolding exists:
  - `/Users/neo/.openclaw/workspace/backend/app/services/automation_run_service.py`
  - `/Users/neo/.openclaw/workspace/backend/app/services/open_brain_db.py`
- Phase 2 mismatch detection exists:
  - `/Users/neo/.openclaw/workspace/backend/app/services/automation_mismatch_service.py`
  - `/Users/neo/.openclaw/workspace/backend/app/routes/automations.py`
- Remaining Phase 2 gap:
  - verified persisted `automation_runs` history in a DB-enabled runtime
  - mismatch detection between OpenClaw state, DB-backed history, and frontend-visible trends over time
- Phase 3 current status:
  - `Context Guard` has been rerouted away from the broken `webchat -> openclaw-control-ui` delivery path and now delivers through Discord on live runs
  - `Progress Pulse` no longer produces fake `gateway openclaw-control-ui` blockers on live runs
  - `Rolling Docs` has guardrails to avoid automatic `HEARTBEAT.md` rewrites when drift is uncertain and has dropped out of the live mismatch list
  - stale `media-intake-guard` plugin config was removed from `/Users/neo/.openclaw/openclaw.json` and the gateway was restarted cleanly
  - manual verification via `openclaw cron run <job-id>` now confirms `Memory Health Check`, `Context Guard`, and `Oracle Ledger` all finish `ok` and `delivered`
  - `Memory Archive Sweep` has now produced an observed run
  - intentional `delivery.mode = "none"` jobs are now treated as healthy by the mismatch layer
  - the live mismatch report is now at `0`

## Exit Criteria For Phase 0 + Phase 1

Phase 0 and Phase 1 are done when:
- every current job is inventoried and classified
- the contract checker exists and is usable
- canonical locations are defined for the known drifting artifacts
- known broken references are repaired
- missing retained log artifacts exist
- a before/after remediation report is written
