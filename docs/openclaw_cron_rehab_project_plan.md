# OpenClaw Cron Rehabilitation And Multi-Workspace Team Plan

## Objective

Stabilize the current OpenClaw cron layer before expanding into a three-agent, five-workspace operating system.

This plan has two linked goals:

1. make the current OpenClaw cron jobs reliable, observable, and cheaper to operate
2. create the foundation for a workspace-first team model built around:
   - `Neo`
   - `Jean-Claude`
   - `Bruce Lee`

The sequencing matters.

Do not scale the operating model until the cron layer, delivery layer, and PM/standup truth model are clean.

## Why This Plan Exists

The system already has a real cron layer running through OpenClaw.

Verified sources:
- `/Users/neo/.openclaw/cron/jobs.json`
- `/Users/neo/.openclaw/logs/gateway.err.log`
- `/Users/neo/.openclaw/workspace/SOPs/openclaw_local_automation_sop.md`
- `/Users/neo/.openclaw/workspace/docs/cron_delivery_guidelines.md`
- `/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py`

The current problem is not "there is no cron system."

The current problem is:
- OpenClaw cron is real and active
- backend/UI visibility is not synchronized tightly enough to that real layer
- several jobs are relying on stale paths or brittle tool behavior
- Discord is part of the live operating loop, but not everything is being reconciled into PM, standups, briefs, and workspace state
- the current job model is still effectively monolithic under `agentId=main`

## Desired Future State

The stable target system should look like this:

- `OpenClaw` is the execution environment and live scheduler for the jobs that belong there
- `launchd` runs heavy local jobs when durability or local runtime requirements demand it
- `Railway` runs hosted jobs that do not depend on the local machine
- the backend mirrors real automation state instead of inventing a separate automation truth
- the PM board is the single source of truth for meaningful work
- standups consume PM state and recent automation events
- the same three agents operate across five workspaces
- workspace boundaries prevent cross-wiring

## Core Design Principle

The system should be:

1. `workspace-first`
2. `PM-board grounded`
3. `cron-aware`
4. `delivery-disciplined`
5. `cheap by default`

That means:
- `workspace` is the unit of separation
- `agent` is the unit of participation
- `PM board` is the unit of task truth
- `OpenClaw cron` is the unit of automation execution
- `Discord` is a notification and digest surface, not a second task system

## Current Confirmed Issues

### 1. Source Of Truth Split

The real scheduled jobs live in:
- `/Users/neo/.openclaw/cron/jobs.json`

But the backend automation inventory is still a static definition list in:
- `/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py`

Result:
- Brain/Ops can display automation cards
- but those cards are not a guaranteed mirror of the real scheduler state

### 2. At Least One Job Is Actively Failed

Confirmed from `jobs.json`:
- `Rolling Docs`
  - `lastStatus=error`
  - `lastError=⚠️ 📝 Edit: in ~/.openclaw/workspace/HEARTBEAT.md (42 chars) failed`

### 3. Delivery Mismatch Exists

Confirmed from `jobs.json`:
- `Context Guard`
  - `lastStatus=ok`
  - `lastDelivered=false`
  - delivery target is `webchat -> openclaw-control-ui`

This means a job can appear healthy at run time while still failing as an operating signal.

### 4. Stale Pathing / Contract Drift

Confirmed missing or mismatched paths:
- missing `/Users/neo/.openclaw/workspace/docs/context_flush_SOP.md`
- missing `/Users/neo/.openclaw/workspace/memory/doc-updates.md`
- expected `/Users/neo/.openclaw/workspace/scripts/check_index_status.sh`
- actual file found at `/Users/neo/.openclaw/workspace/check_index_status.sh`

This means some jobs and skills are operating against outdated assumptions.

### 5. Brittle Tooling In Job Execution

The gateway error log shows repeated failures like:
- missing `oldText`
- exact text not found during edits
- file not found
- invalid message target
- invalid URL reads

This means too many cron jobs are relying on fragile model-driven edit behavior instead of deterministic helpers.

### 6. Discord Delivery Is Too Broad

Per:
- `/Users/neo/.openclaw/workspace/docs/cron_delivery_guidelines.md`

Discord should be used for:
- concise digests
- blockers
- approvals
- real alerts

But in practice, many routine jobs currently announce there.

### 7. The Current Model Is Still Monolithic

All current jobs are effectively running as:
- `agentId=main`

That is incompatible with the future team model unless a routing layer is added.

### 8. Cost Discipline Is Not Strong Enough

Many current jobs are implemented as `agentTurn` jobs using `openai/gpt-4o-mini`.

That is acceptable for:
- synthesis
- judgment
- summaries
- classification

That is not the cheapest or most robust approach for:
- file existence checks
- status polling
- append-only logging
- deterministic transforms
- simple health checks

## Non-Negotiable Constraints

### OpenClaw Constraint

OpenClaw is already running real cron jobs and already delivering to Discord.

Therefore:
- the plan must preserve the current OpenClaw cron layer
- the plan must not assume a greenfield scheduler
- the plan must reconcile the rest of the system to the current OpenClaw loop

### Scheduling Boundary Constraint

Per:
- `/Users/neo/.openclaw/workspace/SOPs/openclaw_local_automation_sop.md`

The canonical boundary is:
- `launchd` schedules heavy local jobs
- `OpenClaw` provides workspace, continuity, and shared context
- `Railway` handles hosted backend work
- `Brain` explains and visualizes the layer

This boundary should remain the rule.

### PM Board Constraint

The PM board must remain the single source of truth for work.

Not every cron event becomes a PM task.
But every meaningful follow-up must become one.

## Team Model To Build Toward

### Agents

- `Neo`
  - execution lead
  - builder/operator
  - implementation, remediation, shipping

- `Jean-Claude`
  - strategist/challenger/reviewer
  - pressure-tests plans
  - catches weak logic and structural drift

- `Bruce Lee`
  - chief of staff / routing operator
  - standups, summaries, reminders, escalation, cadence, coordination

### Workspaces

- `linkedin-os`
- `fusion-os`
- `easyoutfitapp`
- `ai-swag-store`
- `agc`

### Structural Rule

Do not model:
- one agent per workspace

Model:
- one workspace per operating lane
- same three agents can participate in all five workspaces
- all artifacts must carry workspace routing

## Program Structure

This work should be done in seven phases.

Do not skip order.

---

## Phase 0: Freeze, Audit, And Baseline

### Goal

Capture the real current state before changing contracts or moving jobs.

### Tasks

1. Export the current OpenClaw cron inventory from:
   - `/Users/neo/.openclaw/cron/jobs.json`

2. Create a baseline matrix for each job:
   - job name
   - enabled state
   - schedule
   - last status
   - last delivered
   - delivery channel
   - delivery target
   - referenced files
   - referenced scripts
   - writes to
   - cost profile
   - recommended runtime

3. Group jobs into:
   - keep as OpenClaw jobs
   - convert to deterministic script helpers inside OpenClaw jobs
   - move to `launchd`
   - move to Railway
   - disable or replace

4. Freeze net-new cron additions until this baseline is complete.

### Deliverables

- cron inventory snapshot
- current-state risk matrix
- recommended ownership/runtime table

### Definition Of Done

- every current job is categorized
- every current job has a known owner and runtime recommendation
- no unknown jobs remain

---

## Phase 1: Contract And Path Repair

### Goal

Repair stale file paths, missing files, and broken assumptions before changing architecture.

### Tasks

1. Fix all stale path references inside:
   - cron job messages
   - skills
   - SOP references
   - helper calls

2. Resolve the missing assets:
   - decide whether `docs/context_flush_SOP.md` should be restored, replaced, or removed from job prompts
   - create `memory/doc-updates.md` if it is still part of the contract
   - update all references to `check_index_status.sh` so they point at the actual file location or move the file into the expected location

3. Normalize path expectations:
   - scripts belong in `scripts/`
   - append-only logs belong in `memory/`
   - long-lived docs belong in `docs/` or `SOPs/`

4. Add a contract checker that verifies every cron job’s referenced files/scripts exist.

### Deliverables

- repaired cron prompts
- repaired skill references
- path-contract checker
- zero known file-not-found contract mismatches

### Definition Of Done

- no cron job points at a missing file
- no cron job points at a stale script path
- contract checker passes cleanly

---

## Phase 2: Automation Truth And Run Ledger

### Goal

Make the backend mirror real OpenClaw automation state instead of relying on static inventory definitions.

### Tasks

1. Define OpenClaw as the scheduler truth for current jobs.

2. Change the backend automation layer so it reads or mirrors:
   - current job inventory from `jobs.json`
   - current run state from job state
   - recent failures and delivery status

3. Add a normalized run ledger in the backend:
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

4. Stop using a purely static list in:
   - `/Users/neo/.openclaw/workspace/backend/app/services/automation_service.py`
   as the effective source of truth

5. Build mismatch detection:
   - if OpenClaw has a job and backend does not
   - if backend lists a job with no real runtime
   - if delivery state and run state disagree

### Deliverables

- mirrored automation inventory
- automation run ledger
- mismatch report

### Definition Of Done

- Ops/Brain automation views reflect the real scheduler
- every job has visible run and delivery state
- static-only phantom jobs are eliminated

---

## Phase 3: Delivery Hygiene And Alert Discipline

### Goal

Reduce noise and ensure every delivery target behaves as intended.

### Tasks

1. Review all current delivery targets:
   - Discord
   - `openclaw-control-ui`
   - any other channels

2. Fix the `Context Guard` delivery path so "ok but not delivered" is no longer treated as success.

3. Define delivery classes:
   - `alert`
   - `digest`
   - `approval`
   - `silent/log-only`

4. Update jobs so routine success output is not overusing Discord.

5. Enforce:
   - if no action is required, prefer logging over noisy delivery
   - if an error recurs, escalate clearly

6. Add delivery health metrics:
   - run ok + delivered
   - run ok + not delivered
   - run error + delivered
   - run error + not delivered

### Deliverables

- delivery policy matrix
- repaired `openclaw-control-ui` flow
- lower-noise Discord profile

### Definition Of Done

- no job is treated as healthy when delivery failed
- Discord messages are concise and intentional
- routine success output is significantly quieter

---

## Phase 4: Deterministic Execution Refactor

### Goal

Move fragile cron behavior away from freeform agent editing and into deterministic helpers.

### Tasks

1. Identify jobs currently relying on brittle file edits.

2. For each such job, extract deterministic operations into scripts or helpers:
   - append-to-log helpers
   - file existence checks
   - summary generation wrappers
   - report builders
   - backup metadata writers

3. Reserve model use for:
   - summarization
   - triage
   - judgment
   - classification
   - narrative synthesis

4. Replace jobs that use LLMs for simple checks with:
   - shell scripts
   - Python utilities
   - direct system commands

5. Ensure append-only writes use deterministic tooling where possible.

### Deliverables

- deterministic helper library for cron jobs
- thinner OpenClaw prompts
- reduced edit failures in gateway logs

### Definition Of Done

- repeated `oldText` and exact-match edit failures are eliminated for cron jobs
- deterministic work no longer depends on model reasoning
- cost per cron cycle is reduced

---

## Phase 5: Runtime Rationalization And Cost Control

### Goal

Put each automation in the cheapest and most durable runtime that still fits its job.

### Tasks

1. Classify all jobs by runtime type:
   - `OpenClaw`
   - `launchd`
   - `Railway`
   - hybrid

2. Use these rules:
   - `launchd` for heavy local jobs and durable machine-bound jobs
   - `Railway` for hosted checks that do not need local state
   - `OpenClaw` for jobs that need workspace context, memory, synthesis, or live OS integration

3. Move jobs that do not need OpenClaw model turns out of the OpenClaw execution lane.

4. Keep OpenClaw for:
   - `Progress Pulse`
   - context-aware synthesis
   - daily brief interpretation
   - memory-aware review
   - coordination-oriented digests

5. Reassess model usage:
   - cheap by default
   - explicit reasons when model use is necessary

### Deliverables

- runtime placement matrix
- reduced OpenClaw cost footprint
- clearer scheduling boundary between OpenClaw, launchd, and Railway

### Definition Of Done

- every job has an intentional runtime
- obvious deterministic jobs are no longer paying LLM cost
- heavy local jobs are not forced through fragile agent turns

---

## Phase 6: Workspace Routing Primitives

### Goal

Introduce the routing model needed for the future three-agent, five-workspace system.

### Tasks

1. Add `workspace_key` to the right system entities:
   - PM cards
   - standups
   - daily briefs
   - automation runs

2. Add `scope`:
   - `workspace`
   - `shared_ops`
   - `global`

3. Add `owner_agent`:
   - `Neo`
   - `Jean-Claude`
   - `Whitney Wolfe`

4. Create routing rules:
   - not every cron event becomes a PM task
   - but every meaningful follow-up gets routed to either:
     - a workspace
     - `shared_ops`
     - executive review

5. Create normalized automation event packets:
   - `job_id`
   - `job_name`
   - `status`
   - `summary`
   - `workspace_key`
   - `scope`
   - `owner_agent`
   - `action_required`
   - `artifact_refs`

### Deliverables

- workspace-aware data model
- automation event contract
- routing policy

### Definition Of Done

- a cron run can be mapped cleanly into workspace, shared ops, or global lanes
- the data model can support separate workspaces without cross-wiring

---

## Phase 7: Team Operating System Buildout

### Goal

Build the three-agent, five-workspace model on top of the repaired automation foundation.

### Tasks

1. Formalize the three agents:
   - `Neo`
   - `Jean-Claude`
   - `Bruce Lee`

2. Formalize the five workspaces:
   - `linkedin-os`
   - `fusion-os`
   - `easyoutfitapp`
   - `ai-swag-store`
   - `agc`

3. Build two standup layers:
   - workspace standups
   - executive ops standup

4. Keep the PM board as one system, but filter it by:
   - `workspace_key`
   - `owner_agent`
   - `scope`

5. Make `Bruce Lee` the routing and cadence owner:
   - standup preparation
   - cron event triage
   - PM follow-up creation
   - blocker escalation
   - daily and executive summaries

6. Make `Neo` the implementation owner:
   - execution
   - fixes
   - build tasks
   - operational follow-through

7. Make `Jean-Claude` the challenge/review owner:
   - structural review
   - escalation framing
   - plan pressure-testing
   - recurring issue diagnosis

8. Add explicit promotion rules between workspaces:
   - no automatic memory bleed
   - shared lessons must be promoted intentionally

### Deliverables

- team role model
- workspace standup flows
- executive standup flow
- workspace-safe PM board behavior

### Definition Of Done

- three agents can operate across five workspaces without cross-wiring
- PM board remains the single source of truth
- cron, PM, briefs, and standups stay on the same page

---

## Existing Jobs: Recommended Treatment

### Keep As OpenClaw-Centered

- `Progress Pulse`
- `Morning Daily Brief`
- `Nightly Self-Improvement`
- `Dream Cycle`
- `Oracle Ledger`
- `Context Guard` after delivery repair

Reason:
- these depend on context, synthesis, or narrative interpretation

### Keep But Refactor Around Deterministic Helpers

- `Rolling Docs`
- `Daily Memory Flush`
- `Memory Health Check`
- `Service Status Monitor`
- `Railway & GitHub API Monitor`

Reason:
- keep them in the system if useful, but remove brittle edit behavior and direct more work to scripts

### Reassess Runtime Placement

- `GitHub Backup`
- `Weekly Backup`

Reason:
- may remain OpenClaw-integrated, but should likely lean more on deterministic scripts and less on agent-turn behavior

### Shared Ops Classification

These should likely feed `shared_ops`, not workspace lanes:
- `Progress Pulse`
- `Oracle Ledger`
- `Context Guard`
- `Memory Health Check`
- `Daily Memory Flush`
- `Dream Cycle`
- monitors
- backups

## PM Board Rules

The PM board remains the single source of truth.

Rules:
- if it is not on the PM board, it is not real
- if it has no `workspace_key` or `scope`, it is malformed
- a cron success message does not automatically create a PM card
- repeated failures do create or update PM cards
- recurring issues should collapse into one tracked item, not many duplicates

## Standup Rules

### Workspace Standups

For each workspace:
- read PM tasks first
- review new automation events relevant to that workspace
- discuss blockers, commitments, and decisions
- create/update PM tasks from outcomes

### Executive Ops Standup

Owned by `Bruce Lee`:
- review shared ops jobs
- review delivery failures
- review recurring automation problems
- review blocked PM items across workspaces
- assign follow-ups to `Neo` or `Jean-Claude`

## Acceptance Criteria For The Rehab Sprint

Before scaling to the multi-workspace team model, all of the following should be true:

- OpenClaw cron inventory and backend automation inventory are reconciled
- no job points at stale or missing paths
- no critical job silently reports success when delivery failed
- routine cron work is quieter in Discord
- deterministic work uses deterministic helpers
- a run ledger exists
- PM, briefs, and standups can consume real cron state
- workspace routing fields exist in the model or have an implementation-ready migration plan

## Immediate Next Actions

Do these first:

1. baseline all current jobs from `jobs.json`
2. repair stale file/script references
3. fix `Context Guard` delivery
4. fix or disable `Rolling Docs` until its contract is repaired
5. build the run ledger / automation mirror
6. refactor brittle cron writes into deterministic helpers
7. only then begin workspace routing and team-layer buildout

## Suggested Delivery Order

Week 1:
- Phase 0
- Phase 1

Week 2:
- Phase 2
- Phase 3

Week 3:
- Phase 4
- Phase 5

Week 4:
- Phase 6

Week 5:
- Phase 7

If bandwidth is limited, do not partially start Phase 7 before Phases 1 through 4 are complete.

## Final Recommendation

Treat this as a `cron rehab first, team scale second` project.

The three-agent, five-workspace model is strong.
But it should be built on:
- clean contracts
- real observability
- disciplined delivery
- cheap deterministic helpers
- workspace-safe routing

If those are not repaired first, the bigger operating model will inherit the current drift and simply make it harder to diagnose.
