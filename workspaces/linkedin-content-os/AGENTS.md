# AGENTS.md - linkedin-content-os

This is a thin child workspace under Neo.

## Startup
1. Read local `SOUL.md`, `USER.md`, `MEMORY.md`, and `HEARTBEAT.md`.
2. Then read the parent context files:
   - `../../SOUL.md`
   - `../../IDENTITY.md`
   - `../../USER.md`
   - `../../MEMORY.md`
3. Read `backlog.md` before doing new LinkedIn work.
4. Read `docs/operating_model.md` when you need the full workflow.
5. If the task touches the Workspace feed, source capture, or comment/repost generation, read `docs/social_feed_architecture_plan.md` before changing code.
6. If the task touches source ingestion, lane interpretation, belief modeling, technique selection, or tuning, read `docs/social_intelligence_architecture.md` before changing code.
7. If the task touches deploy safety, smoke tests, or main-only release flow, read `../../SOPs/main_safety_release_sop.md`, `scripts/verify_main.sh`, `scripts/verify_production.sh`, and `.githooks/pre-push` before changing code or pushing.
8. Use the canonical parent persona files before inventing new voice or claims.
9. Use the current split-lens taxonomy from `README.md` and `docs/social_feed_architecture_plan.md`; do not reintroduce merged labels such as `AI + Ops` or `Therapy / Referral`.

## Scope
- LinkedIn strategy
- post ideation
- draft creation
- experiment tracking
- performance review

## Rules
- This workspace does not override parent safety rules.
- No public posting without explicit owner approval.
- Draft from canonical persona truth first, local notes second.
- If a claim is strong enough for LinkedIn, make sure it is backed by a parent canonical file or explicit owner approval.
- Treat `current-role`, `program-leadership`, `ai`, `ops-pm`, `therapy`, and `referral` as separate generation lanes.
- Treat manual link/text capture and harvested-feed capture as different ingest paths that converge into one shared interpretation path.
- Do not skip the belief-contrast step when the task is about response quality; the system should decide the relationship to the source before styling the response.
- The current first-pass belief layer lives in `backend/app/services/social_belief_engine.py` and is wired through `backend/app/services/social_signal_utils.py`.
- The current first-pass technique and evaluation layers live in `backend/app/services/social_technique_engine.py` and `backend/app/services/social_evaluation_engine.py`.
- The current sentence-level expression-quality contract lives across `backend/app/services/social_expression_engine.py`, `backend/app/services/social_signal_utils.py`, and `backend/app/services/social_evaluation_engine.py`; if a task touches rewrites or evaluator quality, inspect those together.
- The first-pass tuning dashboard now lives in `/ops` and is derived from the live workspace snapshot plus variant evaluations; use it to inspect weak source grounding, warning hotspots, strategy mix, lane health, and the current attention queue before changing tuning logic.
- Use orchestration for product behavior, coding harnesses for implementation work, auto research for tuning, and dark-factory behavior only for low-risk offline generation.
- `main` now has a local safety gate. Before pushing work that touches this workspace, run `npm run verify:main`. After deploy, run `npm run verify:production`.
