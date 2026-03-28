# linkedin-content-os

Thin child workspace for LinkedIn posting strategy and execution.

This workspace inherits the parent operating identity from:
- `../../SOUL.md`
- `../../IDENTITY.md`
- `../../USER.md`
- `../../MEMORY.md`

It localizes only the LinkedIn-specific operating system:
- strategy
- backlog
- drafts
- experiments
- analytics
- research intake
- editorial mix
- role alignment
- risk-aware planning
- weekly planning

Canonical persona sources live in the parent workspace:
- `../../knowledge/persona/feeze/prompts/content_pillars.md`
- `../../knowledge/persona/feeze/prompts/channel_playbooks.md`
- `../../knowledge/persona/feeze/prompts/content_guardrails.md`
- `../../knowledge/persona/feeze/identity/VOICE_PATTERNS.md`
- `../../knowledge/persona/feeze/identity/audience_communication.md`
- `../../knowledge/persona/feeze/history/initiatives.md`
- `../../knowledge/persona/feeze/history/wins.md`
- `../../knowledge/persona/feeze/history/story_bank.md`
- `../../knowledge/persona/feeze/identity/claims.md`

Primary synthesis inputs:
- parent persona bundle
- media ingest `linkedin_signals`
- synced Topic Intelligence notes under `research/topic_intelligence/`
- local drafts and analytics

Use this workspace to turn those parent assets into:
- a publishing backlog
- high-quality drafts
- repeatable experiments
- performance learnings
- a weekly LinkedIn plan

This is a LinkedIn-first workspace, not a LinkedIn-only workspace.
It should also support curated source capture from:
- Reddit
- Substack / RSS
- web articles
- manually pasted text or links

Those different source paths should converge into one shared internal signal contract before lane interpretation and voice generation.

Current live workspace surfaces:
- a LinkedIn-first social feed in `/ops`
- manual URL/text preview ingestion through `/api/workspace/ingest-signal`
- lane-aware comment and repost generation
- quote approval into persona deltas rather than direct persona-file writes
- a live backend snapshot path at `/api/workspace/linkedin-os-snapshot`
- backend-backed workspace state in `/ops` for plan/reaction/feed timestamps and feedback summary
- a main-safe verification path through `npm run verify:main` and `npm run verify:production`

Current implementation status:
- source extraction is live
- split lane selection is live
- quick reply / comment / repost generation is live
- first-pass belief contrast and experience anchoring are now live
- first-pass technique selection and evaluation readouts are now live
- expression-quality is now live as a relational signal in the social variant builder (`source_expression_quality`, `output_expression_quality`, `expression_delta`, structure preservation)
- `/ops` now includes a first-pass tuning dashboard for live weak-source detection, warning hotspots, strategy mix, lane health, and the current attention queue
- `/ops` now reads a persisted backend snapshot and the backend rebuilds stale social-feed snapshot rows from live runtime builders
- backend smoke tests now cover health, snapshot, and ingest routes
- the frontend production build is now part of the local main gate
- a local pre-push hook can enforce the main gate automatically via `npm run hooks:install`
- the next architecture phase is separating thesis extraction, deepening planner-side reuse, and tightening learning/tuning

Current lane taxonomy:
- `admissions`
- `entrepreneurship`
- `current-role`
- `program-leadership`
- `enrollment-management`
- `ai`
- `ops-pm`
- `therapy`
- `referral`
- `personal-story`

Do not collapse these back into older merged buckets such as:
- `job/program leadership`
- `AI + Ops`
- `therapy / referral`

Key operating docs:
- `docs/operating_model.md`
- `docs/linkedin_curation_workflow.md`
- `docs/social_feed_architecture_plan.md`
- `docs/social_intelligence_architecture.md`

Verification entry points:
- `../../SOPs/main_safety_release_sop.md`
- `scripts/verify_main.sh`
- `scripts/verify_production.sh`
- `.githooks/pre-push`
- `backend/tests/test_workspace_smoke.py`
