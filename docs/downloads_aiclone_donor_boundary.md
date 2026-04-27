# downloads/aiclone Donor Boundary

## Decision
`downloads/aiclone` is not an active execution surface, not a source-of-truth repo, and not a candidate submodule.

Its role is narrower:
- keep it as a cold donor/reference repo
- extract only the specific outreach/email patterns still worth carrying forward
- leave already-imported knowledge packs in `knowledge/aiclone/`
- move the donor repo out of the active workspace tree once targeted extraction is complete

## Why this boundary exists
The current repo already replaced the old app-centric runtime with a production-safe control plane, workspace substrate, PM/standup loop, Brain services, and inbox operations.

So the remaining value in `downloads/aiclone` is not architectural. It is selective salvage:
- cold-email copy patterns
- topic-intelligence outreach-template patterns
- outreach operator-experience ideas

Everything else risks re-importing the old ambiguity without adding production value.

## Classification

| Class | What it means | Current examples |
| --- | --- | --- |
| `worth_porting` | Still useful, but only as a targeted import into the live repo | `cold_email` copy patterns, topic-intelligence outreach templates, outreach operator UX ideas |
| `reference_only` | Keep for manual lookup or historical continuity, but do not re-promote into runtime truth | imported knowledge packs under `knowledge/aiclone/`, old roadmaps, legacy deployment docs |
| `abandon` | Do not port or reactivate | old runtime architecture, mock legacy product surfaces, bundled `.next` / `node_modules` / `.env` artifacts |

## Worth Porting
These are the only donor lanes currently worth treating as live candidates:

1. `Cold-email copy and prompt patterns`
   Source refs:
   `downloads/aiclone/backend/app/routes/content_generation.py`
   `downloads/aiclone/frontend/app/content-pipeline/page.tsx`

2. `Topic-intelligence outreach templates`
   Source refs:
   `downloads/aiclone/backend/app/routes/topic_intelligence.py`
   `downloads/aiclone/backend/app/services/topic_intelligence_service.py`

3. `Outreach operator-experience patterns`
   Source refs:
   `downloads/aiclone/frontend/app/outreach/[prospectId]/page.tsx`
   `downloads/aiclone/frontend/app/prospecting/page.tsx`

These should be reintroduced only into the rebuilt repo’s live systems:
- `backend/app/routes/email_ops.py`
- `backend/app/services/email_ops_service.py`
- `backend/app/routes/topic_intelligence.py`
- `frontend/app/inbox/[threadId]/page.tsx`
- `frontend/app/workspace/page.tsx`

## Reference Only
These stay as lookup material and should not drive active product truth:
- imported knowledge packs already mirrored in `knowledge/aiclone/`
- old roadmaps, deployment notes, and archive docs tracked in `DUPLICATE_INVENTORY.md`
- any historical app behavior used only for comparison during manual analysis

## Abandon
These should not be ported back:
- the old app-centric runtime architecture
- old mock/TODO product surfaces such as `outreach`, `dashboard`, and stubbed `outreach_manual`
- bundled dependency/build/secret exhaust such as `.next`, `node_modules`, committed env files, and logs

## Exit Criteria
Phase 5 is complete when:
- the remaining extraction targets are named explicitly
- the donor repo is visible in Brain as a bounded donor object
- operators are not expected to infer donor intent from duplicate-file notes alone
- the repo has a stated future: remove or relocate `downloads/aiclone` after the targeted extraction work is done

## Non-Goals
- Do not restore the old repo as a running product lane.
- Do not make `downloads/aiclone` a formal submodule.
- Do not rebuild live runtime truth from old docs or old code by default.
