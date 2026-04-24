# AGENTS.md - FEEZIE OS

This is the direct executive visibility workspace. The filesystem path remains `linkedin-content-os`, but the working name is now `FEEZIE OS`.

## Startup
1. Read local `IDENTITY.md`, `SOUL.md`, `USER.md`, and `CHARTER.md`.
2. Read local `docs/README.md` and the linked local docs relevant to the task.
3. Read the latest local `dispatch/*.json`, `briefings/*.md`, and `memory/execution_log.md` when present.
4. Then read the parent context files:
   - `../../SOUL.md`
   - `../../IDENTITY.md`
   - `../../CHARTER.md`
   - `../../USER.md`
   - `../../MEMORY.md`
5. Read `backlog.md` before doing new LinkedIn work.
6. Read `docs/operating_model.md` when you need the full workflow.
7. If the task touches the Workspace feed, source capture, source lifecycle, owner-review staging, or comment/repost generation, read `docs/social_feed_architecture_plan.md` before changing code.
8. If the task touches source ingestion, lane interpretation, belief modeling, technique selection, tuning, or feed-training telemetry, read `docs/social_intelligence_architecture.md` before changing code.
9. If the task touches upstream idea admission, reaction-queue post seeds, weekly-plan recommendations, or draft-promotion gating, read `../../SOPs/idea_qualification_gate_sop.md` before changing code.
10. If the task touches source-adapter expansion, transcript-derived signals, podcasts, YouTube, or belief capture from external sources, read `../../SOPs/source_system_contract_sop.md` and `docs/source_expansion_implementation_plan.md` before changing code.
11. If the task touches persona review flow across Workspace and Brain, read `../../SOPs/brain_workspace_boundary_sop.md` and treat the shared `persona_deltas` lifecycle as canonical: Workspace approval counts as delta approval, Brain is the deeper review/promotion surface, and canonical persona files still require explicit promotion.
12. If the task touches deploy safety, smoke tests, or main-only release flow, read `../../SOPs/main_safety_release_sop.md`, `scripts/verify_main.sh`, `scripts/verify_production.sh`, and `.githooks/pre-push` before changing code or pushing.
13. Use the canonical parent persona files before inventing new voice or claims.
14. Use the current split-lens taxonomy from `README.md` and `docs/social_feed_architecture_plan.md`; do not reintroduce merged labels such as `AI + Ops` or `Therapy / Referral`.

## Scope
- LinkedIn strategy
- post ideation
- draft creation
- experiment tracking
- performance review
- eventual FEEZIE OS expansion

## Rules
- This workspace does not override parent safety rules.
- No public posting without explicit owner approval.
- Persona truth first, posting second.
- Draft from canonical persona truth first, local notes second.
- Use live source signals before generic ideation.
- Turn reactions into reusable visibility assets.
- If a claim is strong enough for LinkedIn, make sure it is backed by a parent canonical file or explicit owner approval.
- Treat `current-role`, `program-leadership`, `ai`, `ops-pm`, `therapy`, and `referral` as separate generation lanes.
- Treat manual link/text capture and harvested-feed capture as different ingest paths that converge into one shared interpretation path.
- Do not skip the belief-contrast step when the task is about response quality; the system should decide the relationship to the source before styling the response.
- The current first-pass belief layer lives in `backend/app/services/social_belief_engine.py` and is wired through `backend/app/services/social_signal_utils.py`.
- The current first-pass technique and evaluation layers live in `backend/app/services/social_technique_engine.py` and `backend/app/services/social_evaluation_engine.py`.
- The current sentence-level expression-quality contract lives across `backend/app/services/social_expression_engine.py`, `backend/app/services/social_signal_utils.py`, and `backend/app/services/social_evaluation_engine.py`; if a task touches rewrites or evaluator quality, inspect those together.
- The first runtime source-taxonomy contract now lives across `backend/app/services/social_signal_utils.py`, `backend/app/services/social_feed_builder_service.py`, `backend/app/services/social_feed_preview_service.py`, and `/ops`; if a task touches source expansion or routing, inspect `source_class`, `unit_kind`, and `response_modes` before changing logic.
- The first runtime long-form source-asset inventory now lives across `backend/app/services/social_source_asset_service.py`, `backend/app/services/workspace_snapshot_service.py`, and `/ops`; keep transcript/media assets upstream-only for feed-card routing until segmentation promotes specific claim-sized units downstream.
- The first runtime long-form routing contract now lives across `backend/app/services/social_long_form_signal_service.py`, `backend/app/services/workspace_snapshot_service.py`, `/ops`, and `backend/app/services/social_persona_review_service.py`; if a task touches long-form routing, update the shared candidate extraction once and let feed/planner/persona consumers read that same route set.
- Treat transcript/media work as one shared source system feeding multiple consumers. Weekly plan, daily briefs, persona review, and social feed routing should extend the same upstream assets instead of rebuilding ingestion separately in each surface.
- The Workspace feed is now a single staged lane that combines source decisions and owner-review drafts; keep source-stage actions upstream and preserve owner-review side effects through `/api/workspace/linkedin-os-owner-review/{queue_id}`.
- The weekly-plan snapshot now reuses the shared long-form route contract for planner-visible `media_post_seeds` and `belief_evidence_candidates`; if a task touches planner-side media reuse, update that shared route contract first instead of adding a planner-only media parser.
- The Brain daily-brief surface now reads a live source-intelligence overlay from `backend/app/services/daily_brief_service.py`; if a task touches brief-layer source awareness, keep it on the same workspace snapshot contract instead of inventing brief-only routing logic.
- The first-pass long-form worldview review sync now lives across `backend/app/services/social_persona_review_service.py`, `backend/app/services/social_belief_engine.py`, `backend/app/services/persona_delta_service.py`, and `backend/app/services/workspace_snapshot_service.py`; use that shared `persona_deltas` path instead of inventing a second Brain-review queue.
- Workspace and Brain now share one persona-review substrate through `/api/persona/deltas`; do not invent a second approval store or require duplicate approval for a snippet the user explicitly approved in Workspace.
- Workspace feed training now includes copy and quote-approval events in addition to like/dislike/reject feedback; keep `/ops` and Workspace aligned on the `POST /api/workspace/feedback` schema instead of forking surface-specific telemetry.
- Brain is still the primary place for pending persona review, nuance, story/context, promotion selection, daily briefs, docs, and global source understanding; Workspace is the fast capture/approval surface for LinkedIn execution.
- If a feature is global rather than LinkedIn-project-specific, prefer `frontend/app/brain/**` over `frontend/app/ops/**` or other workspace shells.
- Brain now defaults to a ranked primary review queue and mutes weaker long-form review items by default; treat that primary queue as the daily review surface and only expand muted items when tuning segment quality.
- The canonical Brain queue contract now comes from `GET /api/persona/deltas?view=brain_queue`, backed by `backend/app/services/persona_review_queue_service.py`; if a task touches Brain ranking, muted-item behavior, or promotion-ready state, update the backend queue service and only keep frontend heuristics as fallback.
- Neither Workspace approval nor Brain review should auto-write canonical persona files under `knowledge/persona/feeze/**`.
- The first-pass tuning dashboard now lives in `/ops` and is derived from the live workspace snapshot plus variant evaluations; use it to inspect weak source grounding, warning hotspots, source-class health, unit-kind health, response-mode health, strategy mix, lane health, and the current attention queue before changing tuning logic.
- Use orchestration for product behavior, coding harnesses for implementation work, auto research for tuning, and dark-factory behavior only for low-risk offline generation.
- `main` now has a local safety gate. Before pushing work that touches this workspace, run `npm run verify:main`. After deploy, run `npm run verify:production`.
