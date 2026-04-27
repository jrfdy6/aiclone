# Repo Surface Truth Baseline Audit — 2026-04-25

## Purpose

This is the Phase 0 baseline for the repo surface truth and enforcement work.

Machine-readable companion:
- `docs/repo_surface_truth_baseline_2026-04-25.json`

It records the current mismatch between:
- the live runtime shell
- the mounted backend surface
- legacy page visibility
- donor/archive material

So future enforcement work can be measured against a concrete before-state.

## Runtime anchors

Primary runtime shell:
- `frontend/components/runtime/RuntimeChrome.tsx`

Current root redirect:
- `frontend/app/page.tsx`

Legacy nav still present:
- `frontend/components/NavHeader.tsx`

Mounted backend truth:
- `backend/app/main.py`

## Baseline classification

Current Phase 0 registry count:
- `16` tracked surfaces in the initial scope
- `4` live and production-relevant
- `5` live but scaffold/fallback
- `6` present but dormant legacy
- `1` reference only
- `3` current mismatch surfaces

### Live and production-relevant

- `/ops`
- `/brain`
- `/workspace`
- `/inbox`

These are the surfaces the current runtime shell elevates and the ones most clearly backed by mounted backend contracts.

### Live but scaffold/fallback

- `/lab`
- `content_generation`
- `email_ops`
- `prospects`
- `prospects_manual`

These are active, but they still rely on fallback behavior, observability scaffolding, partial workflow closure, or sample/local failover paths.

### Present but dormant legacy

- `/prospect-discovery`
- `/outreach`
- `/templates`
- `/dashboard`
- `/vault`
- `/research-tasks`

These surfaces still exist on disk, but they are not part of the trusted runtime shell and should not be treated as first-class product truth.

### Reference only

- `downloads/aiclone/**`

This is the old donor/archive repo, not part of active runtime ownership.

## Baseline mismatch findings

### 1. Runtime shell and legacy nav disagree

`RuntimeChrome.tsx` points the operator toward:
- `/ops`
- `/brain`
- `/lab`
- `/ops#workspace`
- `/inbox`

But `NavHeader.tsx` still exposes:
- `/prospect-discovery`
- `/outreach`
- `/dashboard`

This means the product currently has two competing navigation truths.

### 2. `/prospect-discovery` still calls unmounted backend contracts

The page still calls:
- `/api/prospect-discovery/search-free`
- `/api/prospect-discovery/ai-search`
- `/api/prospect-discovery/scrape-urls`

But the corresponding discovery route family is not mounted in `backend/app/main.py`.

This is the clearest current example of a visible page overstating runtime truth.

### 3. `/dashboard` still calls an unmounted API

The page still calls:
- `/api/dashboard`

But there is no mounted dashboard route family in the backend runtime.

### 4. Multiple legacy pages still read like product surfaces

The following pages still exist and can be mistaken for active product truth:
- `frontend/app/outreach/page.tsx`
- `frontend/app/outreach/[prospectId]/page.tsx`
- `frontend/app/templates/page.tsx`
- `frontend/app/vault/page.tsx`
- `frontend/app/research-tasks/page.tsx`

Several still contain TODO/mock or hardcoded behavior.

### 5. Donor repo status is operationally understood but not yet enforced

`downloads/aiclone` is already treated in docs as archive/reference material, but there is not yet a generalized runtime rule that makes the system consistently treat it as `reference_only`.

## Baseline implementation conclusion

The architecture is not missing ownership, PM write-back, or truth-lane theory.

The baseline problem is narrower:

- repo-surface truth is not yet machine-readable across pages and route families
- visible legacy surfaces are still allowed to compete with the runtime shell
- the backend does not yet fail when a visible page depends on an unmounted API

## What must change next

Phase 1 should add:
- a machine-readable repo surface registry
- Brain/API exposure for that registry
- summary counts and mismatch reporting

Phase 2 should add:
- release-gate verification so these mismatches stop recurring silently
