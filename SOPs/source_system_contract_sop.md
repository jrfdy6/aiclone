# SOP: Shared Source System Contract

## Purpose
Keep transcript/media, social feed, weekly planning, briefs, and persona review on one shared source model instead of silently drifting into parallel pipelines.

## Core Rule
There is one canonical long-form ingest surface:
- `knowledge/aiclone/transcripts/`
- `knowledge/ingestions/**`

Do not create a second audio/video/transcript architecture inside the LinkedIn workspace, Brain, or briefing systems.

## System Model

```text
SourceAsset
  -> SignalUnit
  -> NormalizedSignal
  -> downstream job
```

This means:
- `SourceAsset` = the original post, article, transcript, episode, or manual capture
- `SignalUnit` = the claim-sized paragraph, section, segment, or quote cluster
- `NormalizedSignal` = the shared runtime object used by downstream systems

## One Ingest Surface, Multiple Consumers

The same upstream source should be able to feed multiple jobs:

- `daily_briefs`
  - compact overnight/operator summaries
- `weekly_plan`
  - post seeds, themes, and recommendation candidates
- `persona_review`
  - worldview evidence and reusable phrasing through shared `persona_deltas`
- `social_feed`
  - only when a unit is actually comment/repost ready

The presence of multiple consumers does not justify duplicate ingest stacks.

## Routing Rules

### Comment / repost
Use only when the source unit is:
- compact
- explicit
- socially legible
- source-grounded enough to support a public reaction

### Post seed
Use when the source unit is better as:
- an original post angle
- a draft input
- a planner recommendation

This is the default job for many transcript/video/podcast segments.

### Belief evidence
Use when the source unit is better for:
- agreement / disagreement
- worldview clarification
- phrase capture
- experience matching

These items should enter the shared `persona_deltas` lifecycle and show up in Brain review, not auto-write canonical persona files.

### Briefing input
Use when the source unit is useful for:
- overnight summaries
- daily brief synthesis
- operator awareness

Briefing should consume the same upstream assets, not re-ingest them separately.

## Shared Persona Contract
- `Workspace` is the fast capture / fast approval surface.
- `Brain` is the deeper review / nuance / promotion surface.
- Workspace approval counts as approval at the `persona_deltas` layer.
- Brain should not require duplicate approval for an explicitly approved Workspace snippet.
- Neither surface auto-writes canonical persona files under `knowledge/persona/feeze/**`.

## Existing Reuse Points
- workspace snapshot weekly plan builder already loads media candidates from normalized ingestions
- long-form worldview review already syncs segmented evidence into `persona_deltas`
- `/ops` already exposes source assets, tuning diagnostics, and persona review summary

So new work should extend routing and observability, not rebuild ingestion.

## Required Checks When Changing This Area
1. Confirm the source still enters through `knowledge/aiclone/transcripts/` or `knowledge/ingestions/**`.
2. Confirm the same source can be observed in the correct downstream consumer:
   - planner
   - Brain review
   - feed, only if it is truly feed-ready
3. Confirm canonical persona files still require explicit promotion.
4. Confirm `/ops` reflects the source-class and route behavior clearly enough to debug failures.

## Related Files
- `memory/roadmap.md`
- `workspaces/linkedin-content-os/docs/source_expansion_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
- `backend/app/services/workspace_snapshot_service.py`
- `backend/app/services/social_source_asset_service.py`
- `backend/app/services/social_persona_review_service.py`

## Notes
- This SOP is about architectural alignment, not a separate release process.
- Use `SOPs/main_safety_release_sop.md` for release gates.
