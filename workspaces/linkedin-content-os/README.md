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

Current implementation status:
- source extraction is live
- split lane selection is live
- quick reply / comment / repost generation is live
- first-pass belief contrast and experience anchoring are now live
- first-pass technique selection and evaluation readouts are now live
- `/ops` now merges live backend snapshot state with bundled fallback workspace artifacts when the live feed payload is thinner than the shipped card snapshot
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
