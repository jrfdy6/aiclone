# SOP: Repo Surface Truth Map

## Purpose
Keep one canonical answer to a recurring OpenClaw question:

`Which parts of this repo are live, which are fallback/scaffolded, which are dormant legacy, and which are reference only?`

Use this SOP when you need to decide whether a page, route, service, or repo subtree should be trusted as part of the active product surface.

## Core Rule
Do not treat "file exists" as "system is live."

Repo surfaces must be classified by runtime truth, not by code presence alone.

## Canonical Labels

### `live and production-relevant`
Use this label when the surface is both:
- part of the current runtime or control-plane flow
- backed by mounted backend routes or real local/OpenClaw state

Typical signals:
- mounted in `backend/app/main.py`
- linked from the current runtime shell
- part of the Brain / Ops / Workspace / Inbox operating loop

### `live but scaffold/fallback`
Use this label when the surface is active, but still depends on:
- provider failover
- sample data
- local-cache fallback
- partial workflows
- diagnostic or observability scaffolding

This surface is real, but not yet strict or fully closed-loop.

### `present but dormant legacy`
Use this label when the code or page still exists, but it is not part of the trusted active runtime.

Typical signals:
- route file exists but is not mounted
- page exists but calls unmounted or stubbed APIs
- TODO/mock data still define the user experience

### `reference only`
Use this label for donor, archive, comparison, or migration material that should not be treated as active product truth.

## Decision Tests
Before trusting any repo surface, ask:

1. Is the backend route mounted in `backend/app/main.py`?
2. Is it part of the current runtime shell, especially `/ops`, `/brain`, `/workspace`, or `/inbox`?
3. Does it run on real state, not just TODOs, mocks, or sample fallbacks?
4. Is it meant to drive current execution, or just preserve old ideas/code?

If `1` and `2` are yes, it is usually `live`.

If `1` is yes but `3` is mixed, it is usually `live but scaffold/fallback`.

If `1` is no and the page still exists, it is usually `present but dormant legacy`.

If the subtree is an old donor/archive repo, it is `reference only`.

## Current Classification

### `live and production-relevant`
Primary control-plane surfaces:
- `/ops`
- `/brain`
- `/workspace`
- `/inbox`

Representative files:
- `frontend/app/page.tsx`
- `frontend/components/runtime/RuntimeChrome.tsx`
- `frontend/app/ops/page.tsx`
- `frontend/app/brain/page.tsx`
- `frontend/app/workspace/page.tsx`
- `frontend/app/inbox/page.tsx`
- `frontend/app/inbox/[threadId]/page.tsx`
- `backend/app/routes/brain.py`
- `backend/app/routes/workspace.py`
- `backend/app/routes/email_ops.py`

Mounted operating-system route families that should be treated as active:
- `brain`
- `open_brain`
- `workspace`
- `pm_board`
- `standups`
- `briefs`
- `brief_reactions`
- `timeline`
- `persona`
- `social_feedback`
- `topic_intelligence`
- inherited live surfaces such as `knowledge`, `capture`, `automations`, `prospects`, `calendar`, `notifications`, and `analytics`

### `live but scaffold/fallback`
These are real runtime systems, but they still rely on fallback behavior or partial workflow closure:
- `content_generation`
- `lab`
- `email_ops`
- `prospects`
- `prospects_manual`

Representative reasons:
- `content_generation` still contains provider and legacy fallback paths
- `lab` is explicitly a fallback/observability surface
- `email_ops` supports status/sync/list/route/draft/escalate, but not a full approve/send loop
- `email_ops` can seed sample threads when Gmail is not connected
- `prospects` and `prospects_manual` can fall back between Firestore and local state

### `present but dormant legacy`
Backend route files that still exist but are not mounted should be treated as legacy unless deliberately reactivated.

Representative examples:
- `backend/app/routes/outreach_manual.py`
- `backend/app/routes/templates.py`
- `backend/app/routes/prospect_discovery.py`
- `backend/app/routes/vault.py`
- `backend/app/routes/research.py`
- `backend/app/routes/linkedin_content.py`

Frontend pages that still look available but are not trustworthy as first-class runtime surfaces:
- `frontend/app/prospect-discovery/page.tsx`
- `frontend/app/outreach/page.tsx`
- `frontend/app/outreach/[prospectId]/page.tsx`
- `frontend/app/templates/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/vault/page.tsx`
- `frontend/app/research-tasks/page.tsx`

Special rule:
- If a page still exists in nav, but its backend contract is unmounted, stubbed, or mock-driven, classify it as dormant legacy, not as live product truth.

### `reference only`
- `downloads/aiclone/**`

Treat `downloads/aiclone` as the old donor repo:
- useful for comparison
- useful for selective salvage
- not part of the current trusted runtime

Its main remaining value is historical/reference logic, such as old outreach/cold-email patterns, not active product ownership.

## Navigation Rule
When UI surfaces disagree, trust them in this order:

1. `frontend/components/runtime/RuntimeChrome.tsx`
2. `frontend/app/page.tsx` redirect behavior
3. mounted backend route families in `backend/app/main.py`
4. older app-era nav/page leftovers

This prevents old links or leftover pages from outranking the actual runtime shell.

## Donor Repo Rule
Do not rebuild product truth from `downloads/aiclone`.

If something from the old repo is still valuable:
- identify the specific capability
- port it into the active repo intentionally
- do not treat the old repo as an active execution surface
- use `docs/downloads_aiclone_donor_boundary.md` as the explicit extraction ledger and future-state decision

## Update Triggers
Update this SOP when any of the following change:
- a route family is newly mounted or removed from `backend/app/main.py`
- the runtime shell changes its primary surfaces
- a scaffolded system becomes fully closed-loop
- a legacy page is deliberately reactivated
- `downloads/aiclone` stops being a donor/reference subtree

## Related Files
- `SOPs/_index.md`
- `SOPs/brain_workspace_boundary_sop.md`
- `SOPs/source_system_contract_sop.md`
- `docs/repo_surface_truth_enforcement_implementation_plan.md`
- `docs/fallback_policy_contract.md`
- `docs/truth_lane_cleanup_decision.md`
- `docs/work_lifecycle_vocabulary.md`
- `docs/downloads_aiclone_donor_boundary.md`
- `CODEX_STARTUP.md`
- `AGENT_BOOT.md`
- `backend/app/main.py`
- `frontend/components/runtime/RuntimeChrome.tsx`
