# Brain Workspace Integration Implementation Plan

This plan turns `aiclone_brain_architecture.md` into portfolio-wide implementation work while protecting the system from rebuilding surfaces that already exist.

## Non-Rebuild Rule

Every phase starts with a reuse check:

1. Identify the existing owner of the state.
2. Compose that owner instead of creating a parallel store, queue, registry, or ingest path.
3. Add only the minimum adapter needed for Brain interpretation.
4. Prove the route with tests or an execution artifact.

Existing owners:

- Workspace registry and aliases: `backend/app/services/workspace_registry_service.py`
- Runtime defaults: `backend/app/services/workspace_runtime_contract_service.py`
- PM truth and execution queue: `backend/app/services/pm_card_service.py`
- Standup queue and promotion: `backend/app/services/standup_service.py`
- Snapshot persistence: `backend/app/services/workspace_snapshot_store.py`
- FEEZIE / LinkedIn source snapshot: `backend/app/services/workspace_snapshot_service.py`
- Long-form source intake contract: `SOPs/source_system_contract_sop.md`
- Canonical Brain memory sync: `scripts/brain_canonical_memory_sync.py`
- Runtime memory resolver: `backend/app/services/core_memory_snapshot_service.py`

## Phase 1: Establish Current-State Contracts

Goal: freeze the operating rules before adding more automation.

Status: implemented.

Deliverables:
- Update `docs/aiclone_brain_architecture.md` so Brain observes every active workspace, not only FEEZIE OS.
- Extend `docs/brain_truth_lanes_and_promotion_flow.md` with `Brain Signal`.
- Add `docs/brain_workspace_exchange_protocol.md`.

Acceptance:
- Every workspace has the same expected reporting contract.
- Docs clearly say raw global source intelligence does not flow directly into child workspaces.

## Phase 2: Add A First-Class Brain Signal Model

Goal: stop forcing non-persona signal through `persona_deltas`.

Status: backend implemented as file-backed MVP.

Deliverables:
- Add `BrainSignal` model/request objects.
- Add `backend/app/services/brain_signal_service.py`.
- Add Brain Signal list/create/get/review routes under `backend/app/routes/brain.py`.

Acceptance:
- Persona deltas can still exist as one possible output from Brain Signal.
- Source intelligence, workspace execution, cron outputs, and meeting signals can become Brain Signals without pretending they are persona claims.

Remaining:
- Migrate from JSONL to a table only when volume/query needs justify it.

## Phase 3: Build Portfolio-Wide Workspace Snapshots

Goal: Brain should see all workspaces equally.

Status: backend and first UI surface implemented.

Deliverables:
- Add `backend/app/services/portfolio_workspace_snapshot_service.py`.
- Aggregate `shared_ops`, FEEZIE OS, Fusion OS, Easy Outfit App, AI Swag Store, and AGC.
- Add `portfolio_snapshot` to `backend/app/services/brain_control_plane_service.py`.
- Add a Brain dashboard portfolio panel in `frontend/app/brain/BrainClient.tsx`.

Acceptance:
- Brain dashboard shows all active workspaces.
- Each workspace has visible latest state, blockers, last execution result, and needs-Brain-attention state.
- FEEZIE OS remains special, but not the only live workspace Brain can see.

## Phase 4: Tighten Workspace Routing

Goal: avoid generic AI signal spraying across every workspace.

Status: implemented for persona-review workspace recommendations.

Deliverables:
- Update `backend/app/services/brain_workspace_contract_service.py`.
- Change generic AI routing to Executive + FEEZIE by default.
- Require domain evidence or explicit executive interpretation for project-workspace fanout.
- Add scoring dimensions: domain match, execution relevance, strategic relevance, identity relevance, urgency, and confidence.

Acceptance:
- Generic AI content does not automatically reach Fusion, AGC, Easy Outfit, or AI Swag.
- Workspace routing requires strong domain match or explicit executive interpretation.

## Phase 5: Harden PM Promotion

Goal: protect PM truth from advisory noise.

Status: implemented.

Deliverables:
- Add `validate_brain_pm_route(...)`.
- Require action-shaped PM titles.
- Reject advisory phrasing.
- Preserve duplicate checks.
- Include route guardrail metadata in Brain-created PM cards.
- Require `why_pm_now`, owner, bounded acceptance criteria, source signal metadata, and write-back requirements.
- Reject duplicate active PM cards instead of silently returning them.

## Phase 6: Consolidate Source Intelligence

Goal: make source intake one canonical pipeline.

Status: first registry implemented.

Deliverables:
- Keep `knowledge/ingestions/**` as the machine-written staging area.
- Add the target `knowledge/source-intelligence/{raw,normalized,digests,promotions}` scaffold.
- Add `scripts/source_intelligence_register_existing.py`.
- Generate `knowledge/source-intelligence/index.json` linking old transcript-library sources and machine ingestions.
- Add compact source-index counts to the Brain control plane and Brain dashboard.

Acceptance:
- Every indexed external source has a stable ID.
- Raw source, normalized digest, route decision, and promotions are linked.
- Brain UI can show whether indexed sources are raw, digested, reviewed, routed, promoted, or ignored.

## Phase 7: Fix Canonical Memory Read/Write Drift

Goal: one truth for memory.

Status: implemented for the named Brain memory and automation surfaces.

Deliverables:
- Use `core_memory_snapshot_service.py` as the backend resolver.
- Update Brain docs loading so runtime memory is preferred over stale live memory.
- Label memory docs as runtime, live, or snapshot in the Brain UI.
- Ensure Morning Daily Brief, Dream Cycle, Progress Pulse, Standup Prep, Chronicle memory contracts, and Daily Brief Sync resolve canonical memory through the core memory resolver instead of silently reading stale live files.

## Phase 8: Upgrade Brain UI Into A Real Control Plane

Goal: make Brain visibly portfolio-wide.

Status: implemented.

Implemented:
- Portfolio overview and workspace health matrix.
- Source registry summary in Brain overview.
- Brain Signal cards with review status, digest editing, workspace selection, route target selection, executive interpretation fields, and route history.
- Brain Signal route controls for source-only, canonical memory, persona canon, standup, PM, workspace-local, and ignore.
- PM route form controls that require a bounded action title before PM creation.
- Route history and write-back status for standup, PM, memory, and ignored routes.
- Backend routes for Brain Signal review and routing.

Target sections:
- Portfolio Overview
- Workspace Health Matrix
- Source Intelligence Queue
- Signal Review Queue
- Persona Canon Queue
- Canonical Memory Sync
- Standup / PM Routing
- Automation Health

## Phase 9: Update Automations

Goal: crons maintain the Brain, not become their own brain.

Status: implemented.

Implemented:
- Added `scripts/brain_automation_context.py` as the shared automation substrate.
- Morning Daily Brief consumes Brain Signals, Portfolio Workspace Snapshot, and Source Intelligence index context.
- Dream Cycle consumes Brain Signals, Portfolio Workspace Snapshot, and Source Intelligence index context.
- Progress Pulse consumes Brain Signals, Portfolio Workspace Snapshot, and Source Intelligence index context when it renders.
- Standup Prep writes Brain context into prep JSON, markdown, standup payload metadata, and source paths.
- Brain Canonical Memory Sync writes Brain context into JSON/markdown sync reports and source paths.
- Accountability Sweep writes Brain context into JSON/markdown reports, source paths, and mirrored run metadata.
- Launchd plist entries for Brain-related Python jobs invoke `.venv-main-safe/bin/python` instead of generic `python3` or legacy Anaconda Python.

Acceptance:
- Automations consume Brain Signal, Portfolio Workspace Snapshot, Canonical Memory, PM truth, and Chronicle.
- Automation output references the Brain Signal or workspace snapshot it came from.
- Memory sync status remains visible in Brain.

Future:
- Backfill historical cron outputs into Brain Signals where useful.

## Phase 10: Testing And Guardrails

Goal: make the new Brain substrate defensible.

Status: implemented.

Implemented coverage:
- Brain signal creation and review.
- Brain workspace routing.
- Portfolio workspace snapshot aggregation.
- PM route rejection for advisory cards.
- Source intelligence registry.
- Brain control plane.
- Core memory resolver.
- Shared Brain automation context.
- Brain Canonical Memory Sync report context.
- Accountability Sweep report context.
- Daily Brief Sync canonical memory resolver.
- Launchd plist venv cleanup plus dry-run verification for Accountability Sweep and Brain Canonical Memory Sync.
- Frontend Brain docs server resolver smoke test for runtime and snapshot memory reads.
- Brain control-plane payload smoke for portfolio snapshot, Brain Signal, and source-intelligence fields.
- Frontend typecheck for the Brain control-plane UI.

Future:
- Broaden live cron dry-run coverage for jobs that require API credentials or controlled local side effects.

## Definition Of Done

This is done when a source, PM result, cron output, or workspace event can enter Brain as a signal, be classified, be routed with executive interpretation, land only in the correct truth lane, create PM work only when bounded, and return execution results back through PM, Chronicle, and canonical memory without any workspace becoming a second independent Brain.
