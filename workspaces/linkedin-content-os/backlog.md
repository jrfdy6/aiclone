# LinkedIn Backlog

## Active

### LNK-001 - Define the operating model
- Outcome: decide the weekly rhythm for idea intake, drafting, review, and retrospective.
- Source files: `docs/operating_model.md`, parent `memory/roadmap.md`

### LNK-002 - Seed the content backlog from canonical persona files
- Outcome: turn current initiatives, wins, and story assets into a first queue of post ideas.
- Source files:
  - `../../knowledge/persona/feeze/history/initiatives.md`
  - `../../knowledge/persona/feeze/history/wins.md`
  - `../../knowledge/persona/feeze/history/story_bank.md`
  - `../../knowledge/persona/feeze/prompts/content_pillars.md`

### LNK-003 - Define post archetypes
- Outcome: establish a small set of repeatable LinkedIn post types for this workspace.
- Candidates:
  - operator lesson
  - story with takeaway
  - initiative update
  - people recognition
  - contrarian belief with proof

### LNK-004 - Lock the editorial mix
- Outcome: adopt a working feed balance and label backlog/drafts consistently.
- Source files:
  - `docs/editorial_mix.md`
  - `docs/content_system.md`

### LNK-005 - Create the first draft queue
- Outcome: produce the first batch of draft-ready posts under `drafts/`.
- Source files:
  - `drafts/queue_01.md`
  - parent persona bundle files listed in `docs/operating_model.md`

### LNK-006 - Set the analytics review loop
- Outcome: define what "good" means for LinkedIn in this workspace and how results get logged in `analytics/`.

### LNK-007 - Add role-alignment and risk scoring to planning
- Outcome: make sure the workspace prefers posts that strengthen the current role, AI-native intrapreneur positioning, and operator authority before founder-adjacent content.
- Source files:
  - `docs/role_alignment.md`
  - `docs/current_role_pillars.md`


### LNK-008 - Sync Topic Intelligence into the research lane
- Outcome: pull saved Topic Intelligence runs into `research/topic_intelligence/` and use them in the weekly planner.
- Source files:
  - `docs/research_intake.md`
  - `research/topic_intelligence/`
  - `plans/weekly_plan.md`

### LNK-009 - Add a source-native market signals lane
- Outcome: save LinkedIn, X, Reddit, and news observations into `research/market_signals/` and let the weekly planner rank them against drafts and media ingests.
- Source files:
  - `docs/market_intelligence.md`
  - `research/watchlists.yaml`
  - `research/market_signals/`
  - `plans/reaction_queue.md`

### LNK-010 - Turn saved signals into engagement moves
- Outcome: convert saved LinkedIn-native signals into practical comment angles and standalone post seeds so curation produces action, not just notes.
- Source files:
  - `docs/linkedin_curation_workflow.md`
  - `plans/reaction_queue.md`
  - `plans/reaction_queue.json`

### LNK-014 - Tighten per-lane voice calibration
- Outcome: make each lane sound materially different in the generated comment and repost copy, not just structurally different.
- Focus lanes:
  - `current-role`
  - `program-leadership`
  - `ai`
  - `ops-pm`
  - `therapy`
  - `referral`
- Source files:
  - `../../knowledge/persona/feeze/identity/VOICE_PATTERNS.md`
  - `docs/social_feed_architecture_plan.md`
  - `frontend/app/ops/OpsClient.tsx`
  - `backend/app/services/social_feed_preview_service.py`

### LNK-015 - Push the split lane taxonomy into planners and saved artifacts
- Outcome: make weekly plan generation, reaction queue generation, watchlists, and saved signal metadata use the same lane taxonomy as the live feed UI.
- Source files:
  - `research/watchlists.yaml`
  - `plans/weekly_plan.md`
  - `plans/reaction_queue.md`
  - `docs/social_feed_architecture_plan.md`

### LNK-016 - Unify manual and harvested sources into one normalized signal contract
- Outcome: make manual URL/text previews and harvested feed items converge into the same `NormalizedSignal` shape before lane interpretation and copy generation.
- Status: first pass implemented in the live preview path, saved-feed builder, and manual web-signal ingest script. Weekly plan / reaction queue generators still need to adopt the same contract later.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `docs/social_feed_architecture_plan.md`
  - `backend/app/routes/workspace.py`
  - `backend/app/services/social_feed_preview_service.py`
  - `scripts/personal-brand/ingest_web_signal.py`
  - `scripts/personal-brand/build_social_feed.py`
  - `scripts/personal-brand/refresh_social_feed.py`

### LNK-017 - Split the preview service into an explicit orchestration stack
- Outcome: stop treating preview generation as one growing blob and separate source extraction, normalization, lane interpretation, voice rendering, and evaluation into clear modules.
- Status: first pass implemented. HTML/source extraction now lives separately from the preview orchestration layer. Further decomposition is still needed for belief contrast, technique selection, and planner-side reuse.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `backend/app/services/social_feed_preview_service.py`
  - `backend/app/services/social_signal_extraction.py`
  - `backend/app/services/social_signal_utils.py`
  - `backend/app/routes/workspace.py`

### LNK-018 - Add a belief contrast and experience anchoring layer
- Outcome: make the system decide how Feeze relates to a source before generating copy, including where the response agrees, reframes, diverges, or personalizes.
- Status: first pass implemented. Lane-aware stance, belief selection, and experience anchoring now run inside the shared variant builder and flow through manual previews plus saved-feed artifacts. Planner-side reuse and deeper worldview modeling still remain.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `../../knowledge/persona/feeze/identity/claims.md`
  - `../../knowledge/persona/feeze/history/story_bank.md`
  - `../../knowledge/persona/feeze/history/initiatives.md`
  - `backend/app/services/social_belief_engine.py`
  - `backend/app/services/social_signal_utils.py`

### LNK-019 - Add a technique selection layer for rhetorical and emotional shaping
- Outcome: add a small technique library so the system can intentionally choose how a response should feel, not just what it should say.
- Status: first pass implemented. Shared variants now carry a rule-based technique bundle, emotional profile, and technique reason. Expression-aware source rewriting is now also live at the sentence boundary, so the system can choose a stronger structure-preserving paraphrase instead of blindly flattening the source claim. The next step is to make those selections smarter and tune them against real feedback.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `docs/social_feed_architecture_plan.md`
  - `backend/app/services/social_feed_preview_service.py`
  - `backend/app/services/social_technique_engine.py`
  - `backend/app/routes/content_generation.py`
  - `backend/app/services/retrieval.py`

### LNK-020 - Create a shared tuning dashboard contract
- Outcome: define a dashboard/state contract that the user and the agents can both use to track narrative state, beliefs, performance, techniques, and next-step tuning decisions.
- Status: partially live. The social variant pipeline now emits explicit expression-quality fields (`source_expression_quality`, `output_expression_quality`, `expression_delta`, structure preservation) alongside the existing lane / belief / technique / evaluation readout. The remaining step is to make those metrics a first-class dashboard surface instead of only a variant/evaluator field.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `plans/README.md`
  - parent `memory/roadmap.md`

### LNK-021 - Expand the source adapters beyond LinkedIn-first capture
- Outcome: treat Reddit, Substack/RSS, and web articles as first-class source channels while preserving one shared interpretation path and one lane system.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `docs/market_intelligence.md`
  - `research/watchlists.yaml`

### LNK-022 - Expand feedback logging and evaluation endpoints
- Outcome: extend the existing `/api/workspace/feedback` path to log copy actions, approvals, dislikes, and future posting outcomes into a structured feedback layer instead of using only UI state and implied behavior.
- Status: first pass implemented. Feedback now writes structured JSONL alongside the markdown log, rebuilds a summary artifact, and `/ops` sends active lane/stance/technique/evaluation context for like, dislike, and copy interactions. Expression-quality fields now flow through the same path so the feedback layer can see source/output expression quality and the delta introduced by the transformation step.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `backend/app/routes/social_feedback.py`
  - `backend/app/services/social_feedback_service.py`
  - `backend/app/models/social_feedback.py`
  - `backend/app/routes/workspace.py`
  - `frontend/app/ops/OpsClient.tsx`

### LNK-024 - Harden live workspace snapshots for `/ops`
- Outcome: make `/ops` read live backend snapshot state for weekly plan, reaction queue, social feed timestamps, workspace files, and feedback analytics instead of depending only on frontend-bundled artifacts.
- Status: live. `GET /api/workspace/linkedin-os-snapshot` is backed by persisted Postgres snapshot rows, stale social-feed snapshot rows self-heal from backend runtime builders, and `/ops` now trusts the backend snapshot path instead of depending on bundled feed fallback data for the live workspace state.
- Source files:
  - `backend/app/routes/workspace.py`
  - `backend/app/services/open_brain_db.py`
  - `backend/app/services/workspace_snapshot_store.py`
  - `backend/app/services/workspace_snapshot_service.py`
  - `backend/app/services/social_feed_builder_service.py`
  - `frontend/app/ops/OpsClient.tsx`
  - `scripts/personal-brand/build_social_feed.py`
  - `scripts/deploy_railway_service.sh`

## Recently Completed

### LNK-012 - Split merged social feed lanes
- Outcome: separate `current-role`, `program-leadership`, `ai`, `ops-pm`, `therapy`, and `referral` so the workspace no longer collapses them into shared buckets.
- Implementation surfaces:
  - `frontend/app/ops/OpsClient.tsx`
  - `backend/app/services/social_feed_preview_service.py`

### LNK-013 - Fix manual LinkedIn URL preview extraction
- Outcome: prefer LinkedIn JSON-LD/Open Graph metadata and filtered body extraction so preview cards stop using page chrome such as `Report this post`.
- Implementation surfaces:
  - `backend/app/services/social_feed_preview_service.py`
  - `backend/app/routes/workspace.py`

### LNK-025 - Add a main-safe verification workflow for the social workspace
- Outcome: make `main` usable as the release lane with repeatable local and production gates.
- Implementation surfaces:
  - `scripts/verify_main.sh`
  - `scripts/verify_production.sh`
  - `backend/tests/test_workspace_smoke.py`
  - `.githooks/pre-push`
  - `package.json`

## Parked

### LNK-011 - Channel-specific automations
- Keep parked until the manual content loop is stable.

### LNK-023 - Add auto-research for lane, stance, and technique tuning
- Outcome: use lightweight experiments to optimize which combinations perform best, instead of hand-tuning prompts forever.
- Status: explicitly parked until lane voice calibration, richer feedback logging, and the shared tuning dashboard are stable enough to give auto-research a trustworthy offline metric. Use it to tune policy later, not as the current implementation path.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `analytics/`
  - `plans/`

### Implementation order
1. `LNK-016`
2. `LNK-017`
3. `LNK-018`
4. `LNK-019`
5. `LNK-014`
6. `LNK-022`
7. `LNK-020`
8. `LNK-023` (parked until tuning signals are trustworthy)
