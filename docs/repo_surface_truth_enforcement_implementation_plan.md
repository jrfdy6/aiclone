# Repo Surface Truth And Enforcement Implementation Plan

## Objective

Turn the current repo-truth understanding into an enforced system contract so the repo can answer, in code and in UI:

- what is live and production-relevant
- what is live but scaffolded or fallback-driven
- what is dormant legacy
- what is reference only

This plan exists because the architecture already has strong ownership, PM write-back, workspace registry, and truth-lane contracts, but it still lacks a generalized runtime enforcement layer for repo surfaces.

## Current Assessment

### Already strong

- ownership and workspace identity contracts
- PM execution contract and write-back loop
- Brain truth lanes and Chronicle-to-PM promotion boundary
- workspace registry, status, execution mode, and machine-readable workspace metadata

Primary references:
- `SOPs/repo_surface_truth_map_sop.md`
- `SOPs/workspace_portfolio_registry_sop.md`
- `docs/brain_truth_lanes_and_promotion_flow.md`
- `docs/chronicle_pm_promotion_boundary.md`
- `docs/system_cohesion_contract.md`
- `backend/app/services/workspace_registry_service.py`
- `backend/app/services/pm_execution_contract_service.py`
- `scripts/runners/write_execution_result.py`

### Partially implemented

- fallback policy exists in pockets, not as one system contract
- machine-readable truth exists for workspaces, not for repo surfaces broadly
- conversation vs truth lanes are documented and partly enforced, but historical substrate cleanup is incomplete

### Weak or missing

- no generalized guard that reconciles visible pages, mounted routes, and declared surface status
- dormant legacy pages still appear available in ways that confuse runtime truth
- the donor repo has archive/reference handling, but not a focused extraction plan

## Non-Rebuild Rule

This plan must reuse existing owners instead of inventing parallel stores.

Existing owners to compose:
- mounted backend truth: `backend/app/main.py`
- runtime shell truth: `frontend/components/runtime/RuntimeChrome.tsx`
- workspace truth: `backend/app/services/workspace_registry_service.py`
- workspace runtime contract: `backend/app/services/workspace_runtime_contract_service.py`
- Brain control-plane aggregation: `backend/app/services/brain_control_plane_service.py`
- PM truth and execution: `backend/app/services/pm_card_service.py`
- standup truth: `backend/app/services/standup_service.py`
- Chronicle and durable memory promotion: `scripts/sync_codex_chronicle.py`, `scripts/promote_codex_chronicle.py`, `scripts/brain_canonical_memory_sync.py`

The only new substrate this plan should add is the smallest possible metadata and verification layer needed to classify repo surfaces and enforce consistency.

## Implementation Workstreams

## Workstream 1: Repo Surface Registry

### Goal

Create one machine-readable registry for repo surfaces so the system can classify pages, route families, and special subtrees using the same four labels already defined in the SOP.

### Deliverables

- Add `backend/app/services/repo_surface_registry_service.py`.
- Add a typed surface model with fields such as:
  - `surface_id`
  - `surface_kind`
  - `status_class`
  - `owner`
  - `route`
  - `backend_contract`
  - `nav_visibility`
  - `fallback_policy`
  - `source_of_truth`
  - `notes`
- Derive as much as possible from:
  - mounted routers in `backend/app/main.py`
  - runtime shell links in `frontend/components/runtime/RuntimeChrome.tsx`
  - explicit overrides for legacy pages and donor/archive subtrees
- Add a compact API surface under Brain or Ops for:
  - full surface list
  - summary counts by `status_class`
  - mismatch flags

### Initial scope

The first registry should include:
- `/ops`
- `/brain`
- `/workspace`
- `/inbox`
- `/lab`
- `content_generation`
- `email_ops`
- `prospects`
- `prospects_manual`
- `/prospect-discovery`
- `/outreach`
- `/templates`
- `/dashboard`
- `/vault`
- `/research-tasks`
- `downloads/aiclone/**`

### Acceptance

- Every primary frontend runtime surface has a registry entry.
- Every mounted route family used by active UI has a registry entry.
- Legacy pages called out in `SOPs/repo_surface_truth_map_sop.md` have explicit registry entries.
- Brain or Ops can render a machine-readable truth summary instead of relying only on prose docs.

## Workstream 2: Route And Page Contract Verification

### Goal

Stop the system from silently drifting into states where visible pages call unmounted APIs or where active surfaces are not classified.

### Deliverables

- Add `scripts/verify_repo_surface_truth.py`.
- Add release-gate integration in:
  - `scripts/verify_main.sh`
  - optional production verification follow-up if the surface contract is externally visible
- Verification checks:
  - every primary runtime route has a surface classification
  - every visible active page that calls `/api/...` has a mounted backend contract or an explicit scaffold classification
  - no `live and production-relevant` page depends on an unmounted backend route
  - no `present but dormant legacy` page is linked from the runtime shell

### Recommended first checks

- `/prospect-discovery`
- `/outreach`
- `/templates`
- `/dashboard`
- `/vault`
- `/research-tasks`

### Acceptance

- The verifier fails when a visible page points at an unmounted API without explicit scaffold or legacy classification.
- The verifier fails when a runtime surface has no registry entry.
- The verifier can run locally and in the main safety gate without network access.

## Workstream 3: Legacy Visibility Reduction

### Goal

Reduce operator confusion by making dormant legacy surfaces visibly different from active runtime surfaces.

### Deliverables

- Keep `RuntimeChrome` as the primary truth source for live navigation.
- Audit `frontend/components/NavHeader.tsx` and any other leftover nav surfaces.
- Decide one handling mode for each dormant page:
  - hide from primary nav
  - move under an explicit legacy/dev path
  - keep visible but labeled as `legacy` or `scaffold`
- Add UI badges or labels where appropriate.

### Acceptance

- Runtime shell only surfaces pages that are either live or intentionally scaffolded.
- Dormant legacy pages no longer read as first-class product surfaces.
- There is a single documented rule for when a legacy page may stay visible.

## Workstream 4: Fallback Policy Normalization

### Goal

Move from scattered fallback behavior to one declared fallback taxonomy.

### Deliverables

- Add `docs/fallback_policy_contract.md`.
- Inventory active fallback families:
  - provider failover in content generation
  - safe-lesson to reservoir fallback
  - snapshot rebuild fallback
  - sample-thread fallback in email ops
  - Firestore/local fallback in prospects
  - workspace registry fallback mirror
- Classify each fallback as:
  - `allowed_in_production`
  - `temporary_scaffold`
  - `treat_as_failure`
- Add machine-readable metadata where the fallback already has a runtime owner.

### Reuse points

- `backend/app/routes/content_generation.py`
- `backend/app/services/content_generation_context_service.py`
- `backend/app/services/email_ops_service.py`
- `backend/app/routes/prospects.py`
- `frontend/lib/workspace-registry.ts`

### Acceptance

- The system can answer which fallbacks are intentional and which are debt.
- Ops or Brain can show fallback class, not just raw fallback presence.
- New fallbacks must declare a policy class before shipping.

## Workstream 5: Conversation And Durable Truth Convergence

### Goal

Finish the trust-boundary work so conversation, hypothesis, fact, and durable lesson stay visibly distinct.

### Deliverables

- Keep the current Chronicle hardening and non-promoting chat defaults in place.
- Add a cleanup audit for historically contaminated runtime memory.
- Create a documented decision for historical cleanup:
  - leave history in place and improve forward behavior only
  - or quarantine/rebuild selected durable memory files from verified execution sources
- Add provenance visibility to standup and Brain-facing surfaces where possible.

### Reuse points

- `docs/brain_truth_lanes_and_promotion_flow.md`
- `docs/end_to_end_memory_convergence_implementation_plan.md`
- `scripts/sync_codex_chronicle.py`
- `scripts/build_standup_prep.py`
- `scripts/brain_canonical_memory_sync.py`

### Acceptance

- Conversation-derived residue is no longer mistaken for verified truth in primary coordination surfaces.
- Durable memory promotion rules are explicit and testable.
- Historical cleanup has a declared operating decision instead of lingering as undefined debt.

## Workstream 6: Close-The-Loop State Model

### Goal

Expose one consistent lifecycle for signals and work items:

`captured -> interpreted -> promoted -> routed -> executing -> written_back -> closed`

### Deliverables

- Define a shared lifecycle vocabulary for:
  - Brain signals
  - standup outcomes
  - PM execution
  - execution results
- Add or normalize status fields where existing services already carry adjacent state.
- Prefer extending existing payloads over creating a new workflow store.

### Reuse points

- `backend/app/services/brain_signal_service.py`
- `backend/app/services/pm_execution_contract_service.py`
- `backend/app/services/pm_loop_canary_service.py`
- `backend/app/services/pm_review_hygiene_audit_service.py`
- `scripts/runners/write_execution_result.py`

### Acceptance

- Brain and Ops can show where a signal or task is in the loop.
- “Done” no longer depends on reading prose artifacts manually.
- Write-back status is visible as a first-class state, not just implied by artifact existence.

## Workstream 7: Donor Repo Extraction Boundary

### Goal

Treat `downloads/aiclone` as a donor/reference lane with a finite extraction purpose, not an indefinite architectural ambiguity.

### Deliverables

- Add a focused extraction memo for the remaining useful capabilities from `downloads/aiclone`.
- Separate:
  - worth porting
  - worth referencing only
  - worth abandoning
- Prioritize the remaining email/outreach patterns if they are still strategically relevant.
- Decide the post-extraction boundary:
  - keep as cold reference
  - move out of the active repo tree
  - remove once extractions are complete

### Reuse points

- `DUPLICATE_INVENTORY.md`
- `notes/aiclone-inventory.md`
- `knowledge/aiclone/**`

### Acceptance

- `downloads/aiclone` no longer sits in an undefined state.
- The system has a clear list of remaining extraction targets.
- Archive/reference status is consistent with the new repo-surface truth model.

## Rollout Order

## Phase 0: Freeze Baseline

### Goal

Capture the current state before enforcement changes behavior.

### Tasks

- Record the initial live/scaffold/legacy/reference inventory.
- Record currently visible pages that call unmounted or stubbed APIs.
- Record the active fallback inventory.

### Exit criteria

- One baseline audit artifact exists and can be compared after implementation.

## Phase 1: Surface Registry

### Goal

Make repo-surface truth machine-readable.

### Tasks

- Implement Workstream 1.
- Expose the registry through Brain or Ops.

### Exit criteria

- Repo-surface classification is no longer doc-only.

## Phase 2: Verification Gate

### Goal

Stop new drift.

### Tasks

- Implement Workstream 2.
- Wire the verifier into `verify_main.sh`.

### Exit criteria

- Active-surface drift becomes a failing condition, not just an observation.

## Phase 3: Legacy And Fallback Visibility

### Goal

Make runtime truth readable to operators without code archaeology.

### Tasks

- Implement Workstream 3.
- Implement Workstream 4.

### Exit criteria

- Operators can tell whether a surface is real, scaffolded, or legacy from the product itself.

## Phase 4: Truth-Lane Cleanup

### Goal

Finish the trust-boundary convergence work.

### Tasks

- Implement Workstream 5.
- Implement Workstream 6.

### Exit criteria

- Conversation, evidence, PM, and write-back states are visibly separated and easier to trust.

## Phase 5: Donor Closure

### Goal

Turn the old repo from ambient ambiguity into a bounded extraction decision.

### Tasks

- Implement Workstream 7.

### Exit criteria

- `downloads/aiclone` has an explicit future and stops being an architectural question mark.

## Non-Goals

- This plan does not require deleting all fallback behavior.
- This plan does not require deleting all dormant legacy code immediately.
- This plan does not require a product rewrite.
- This plan does not replace the workspace registry, PM board, or canonical memory lanes already in place.

## Definition Of Done

This work is done when the system can prove, in code and in UI, which surfaces are live, scaffolded, legacy, or reference-only; when active pages cannot silently drift away from their backend contracts; when fallback behavior is classified and intentional; when conversation-derived signal no longer commingles with verified truth in primary coordination flows; and when `downloads/aiclone` has a finite, explicit role instead of living as ambient ambiguity inside the active workspace.
