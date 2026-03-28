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
- Status: partially live. The social variant pipeline now emits explicit expression-quality fields (`source_expression_quality`, `output_expression_quality`, `expression_delta`, structure preservation) alongside the existing lane / belief / technique / evaluation readout. `/ops` now includes a first-pass tuning dashboard that surfaces weak source grounding, warning hotspots, strategy mix, lane health, and the current attention queue directly from the live workspace snapshot. The next step is to push those signals into longer-horizon tuning memory and planner-side decision loops.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `plans/README.md`
  - parent `memory/roadmap.md`

### LNK-021 - Expand the source adapters beyond LinkedIn-first capture
- Outcome: treat Reddit, Substack/RSS, and web articles as first-class source channels while preserving one shared interpretation path and one lane system.
- Status: partially live. Reddit, RSS/Substack, manual URL/text preview, and restored LinkedIn saved signals are now all flowing through the shared social feed runtime. The next phase is expanding from short-form/article sources into transcript-derived long-form media and routing those signals into the right downstream jobs instead of treating every source like a comment card.
- Current production note (`2026-03-28`): the refreshed mixed feed recovered with LinkedIn + RSS/Substack items, but Reddit is currently absent. If Reddit is still missing on the next-cycle validation, reprioritize Reddit source-adapter debugging before transcript/media expansion.
- Source files:
  - `docs/social_intelligence_architecture.md`
  - `docs/market_intelligence.md`
  - `research/watchlists.yaml`

### LNK-026 - Define a source taxonomy and response-routing contract
- Outcome: explicitly model `source_class`, `unit_kind`, and `response_modes` so the system knows whether a source should become a comment candidate, repost candidate, post seed, or belief-evidence item.
- Status: first runtime slice is now live. Saved feed items, manual previews, persisted snapshot rebuilds, and `/ops` diagnostics all carry `source_class`, `unit_kind`, and `response_modes`. The remaining work is to use those fields for real media/transcript routing instead of only short-form/article classification.
- Benchmark gate: `100%` runtime coverage of the new fields with no regression in feed availability or snapshot richness. Validate in production with immediate and deterministic rebuild checks from `docs/source_expansion_implementation_plan.md`.
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `backend/app/services/social_signal_utils.py`
  - `backend/app/services/social_feed_builder_service.py`
  - `backend/app/services/workspace_snapshot_service.py`

### LNK-027 - Integrate transcript and media-ingest assets as source adapters
- Outcome: treat transcript and media-ingest assets as first-class upstream sources by reusing the existing media-intake system instead of building a second audio/video ingestion stack.
- Status: first runtime slice is now live. `GET /api/workspace/linkedin-os-snapshot` includes `source_assets`, and `/ops` now exposes those long-form assets as an upstream inventory with channel counts, routing status, and response-mode visibility. These assets are intentionally not routed into feed cards yet.
- Benchmark gate: transcript assets are visible as `long_form_media`, but `0` transcript assets are pushed directly into the comment feed before segmentation/routing exists. Validate with immediate and next-cycle production checks.
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `memory/roadmap.md`
  - `knowledge/aiclone/transcripts/`
  - `knowledge/ingestions/`
  - `backend/app/services/social_source_asset_service.py`
  - `backend/app/services/workspace_snapshot_service.py`
  - `frontend/app/ops/OpsClient.tsx`

### LNK-028 - Segment long-form media into claim-sized social signals
- Outcome: split YouTube and podcast transcripts into timestamped or sectioned units so one long transcript can yield multiple claim-shaped candidate signals instead of one giant blob.
- Benchmark gate: `0` full-transcript blobs in the feed, multi-segment yield from a test transcript, and transcript-derived comment/repost candidates targeting `Avg Source >= 4.5`, `Weak Source <= 25%`, `Avg Δ >= 0.2`.
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `backend/app/services/social_signal_extraction.py`
  - `backend/app/services/social_signal_utils.py`

### LNK-029 - Route media-derived signals into the right downstream jobs
- Outcome: route each normalized signal into `comment`, `repost`, `post_seed`, or `belief_evidence` instead of treating every source like a feed-card response opportunity.
- Benchmark gate: transcript/media units primarily route to `post_seed` or `belief_evidence`; any media-derived comment-ready feed item should target `Src >= 5.0`, `Expr >= 6.5`, `Δ >= 0.3`. Validate with deterministic rebuild, full refresh, and next-cycle production checks.
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `backend/app/services/social_feed_builder_service.py`
  - `backend/app/services/workspace_snapshot_service.py`
  - planner and reaction queue surfaces

### LNK-030 - Capture worldview and persona evidence from external sources
- Outcome: let source contrast produce saved agreement, disagreement, translation, and experience-match artifacts that can later inform persona review without auto-writing canonical persona files.
- Benchmark gate: every worldview evidence record includes source reference + stance + belief relation, and `0` automatic writes happen to canonical persona files. Validate immediately and on the next-cycle production check.
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `backend/app/services/social_belief_engine.py`
  - `backend/app/services/social_feedback_service.py`
  - parent persona truth files under `knowledge/persona/feeze/`

### LNK-031 - Extend `/ops` and planning with source-class intelligence
- Outcome: make the dashboard and planner show source-class health, segment yield, response-mode mix, belief-evidence queues, and post-seed queues so source expansion remains observable.
- Benchmark gate: `/ops` and planner surfaces expose the new source-class and response-mode rollups, and those rollups are testable through immediate, deterministic rebuild, and full refresh production checks.
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `frontend/app/ops/OpsClient.tsx`
  - `backend/app/services/workspace_snapshot_service.py`
  - planner outputs under `plans/`

### LNK-032 - Formalize the shared Workspace / Brain persona-review contract
- Outcome: make Workspace snippet approval and Brain persona review two surfaces over one shared `persona_deltas` lifecycle, with no duplicate approval requirement and no automatic canonical-file writes.
- Status: partially live. Both surfaces already share `/api/persona/deltas`; Workspace quote approval creates an approved delta immediately, Brain reviews pending / in-review items and saves reflection captures into Open Brain, and `/api/workspace/linkedin-os-snapshot` plus `/ops` now expose a first-pass `persona_review_summary` so the shared lifecycle is visible from the live workspace snapshot. The remaining work is deeper Brain-side routing for segmented worldview evidence and clearer promotion-state handling.
- Benchmark gate:
  - approving a snippet from Workspace creates a saved approved delta with no duplicate Brain approval loop
  - Brain pending reviews only show items that still need context, nuance, or promotion judgment
  - `0` automatic writes occur to canonical persona files
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `docs/social_intelligence_architecture.md`
  - `frontend/app/ops/OpsClient.tsx`
  - `frontend/app/brain/BrainClient.tsx`
  - `backend/app/routes/persona.py`
  - `backend/app/services/persona_delta_service.py`

### LNK-033 - Route segmented worldview evidence into Brain review
- Outcome: make transcript-derived worldview segments and other belief-evidence units appear as reviewable persona items in Brain with source reference, stance, and promotion context.
- Status: first pass is now live. `backend/app/services/social_persona_review_service.py` segments long-form source assets into claim-sized worldview candidates, uses `social_belief_engine.py` to attach stance/belief context, and writes draft review items into the shared `/api/persona/deltas` lifecycle with deterministic `review_key` dedupe. `GET /api/workspace/linkedin-os-snapshot` now runs that sync before rebuilding `persona_review_summary`, so Brain can pick up transcript-derived worldview evidence without creating a second review queue.
- Benchmark gate:
  - one segmented long-form source yields multiple reviewable persona items
  - each review item includes source reference + stance or belief relation
  - `0` full transcripts appear as one giant persona-review item
- Source files:
  - `docs/source_expansion_implementation_plan.md`
  - `backend/app/services/social_belief_engine.py`
  - `frontend/app/brain/BrainClient.tsx`
  - segmentation/routing outputs from `LNK-028` and `LNK-029`

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
8. `LNK-021`
9. `LNK-026`
10. `LNK-027`
11. `LNK-028`
12. `LNK-029`
13. `LNK-030`
14. `LNK-032`
15. `LNK-033`
16. `LNK-031`
17. `LNK-023` (parked until tuning signals are trustworthy)
