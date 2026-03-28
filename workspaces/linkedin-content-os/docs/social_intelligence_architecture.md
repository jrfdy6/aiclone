# Social Intelligence Architecture

This document is the implementation map for the Workspace social-response system.

It exists to keep OpenClaw, Codex, and future agents aligned on:
- what is already live
- what the next implementation layers are
- where those layers belong in the current roadmap

Use this document when the task touches:
- manual URL or pasted-text ingestion
- harvested feed ingestion
- comment / repost / quick-reply generation
- lane interpretation
- voice tuning
- narrative learning
- social strategy state

If the task is specifically about expanding source classes into YouTube, podcasts, transcript segments, post-seed routing, or belief-evidence capture, read `docs/source_expansion_implementation_plan.md` alongside this document.

## Current Position

The live system already does these things:
- extracts manual URL and pasted-text signals through `POST /api/workspace/ingest-signal`
- renders social feed cards in the Workspace tab
- supports a split lane taxonomy instead of older merged buckets
- generates lane-aware quick replies, comments, and repost drafts
- lets the user approve lines into persona deltas
- serves a live workspace snapshot through `GET /api/workspace/linkedin-os-snapshot`
- serves upstream long-form `source_assets` through the same workspace snapshot for transcript/media inventory
- serves a first-pass `persona_review_summary` through the same workspace snapshot so `/ops` can show Brain-pending vs Workspace-approved persona state
- uses one shared normalization helper for:
  - live manual preview generation
  - saved social-feed artifact generation
  - manual web-signal ingestion into `research/market_signals/`

The live system does **not** yet have a fully separated intelligence stack.

Today, too much logic still lives inside one service:
- `backend/app/services/social_feed_preview_service.py`

The stack is now partially separated:
- source extraction lives in `backend/app/services/social_signal_extraction.py`
- shared normalization + lane rendering live in `backend/app/services/social_signal_utils.py`
- first-pass belief contrast and experience anchoring live in `backend/app/services/social_belief_engine.py`

What is still not fully separated:
- thesis extraction
- technique selection
- critic/evaluation
- planner-side reuse of the same interpretation metadata

The next architecture phase is to split those concerns.

## Verification And Release Gates

The social workspace now has an explicit main-safe verification path.

Use these entry points:
- `scripts/verify_main.sh`
- `scripts/verify_production.sh`
- `backend/tests/test_workspace_smoke.py`
- `.githooks/pre-push`

What the local gate checks:
- backend smoke coverage for `GET /health`
- backend smoke coverage for `GET /api/workspace/linkedin-os-snapshot`
- backend smoke coverage for `POST /api/workspace/ingest-signal`
- direct builder/service checks for social-feed richness
- frontend production build success

What the production gate checks:
- backend health
- live workspace snapshot richness
- live ingest preview generation
- analytics/logs fallback routes
- frontend `/ops` availability

Why this matters:
- it lets `main` act as the release lane instead of relying on a side branch for confidence
- it makes failures legible before push and again after deploy
- it gives OpenClaw and Codex one shared release checklist instead of ad hoc manual testing

## Reuse Before Rebuild

Do not treat this plan as a greenfield system.

These building blocks already exist and should be reused or refactored forward:

### Existing feed artifact contract
- `scripts/personal-brand/build_social_feed.py`
- `workspaces/linkedin-content-os/plans/social_feed.json`

These already define a quasi-contract for:
- `title`
- `author`
- `source_url`
- `summary`
- `standout_lines`
- `lenses`
- `why_it_matters`
- `comment_draft`
- `repost_draft`
- `lens_variants`

Do not invent a totally separate output schema unless there is a strong reason.
Evolve this shape toward `NormalizedSignal` plus richer interpretation metadata.

### Existing manual ingestion path
- `scripts/personal-brand/ingest_web_signal.py`
- `backend/app/routes/workspace.py`
- `backend/app/services/social_feed_preview_service.py`

Manual ingestion already exists in two forms:
- saved-signal ingestion script
- live preview API

The preview API currently has the stronger extraction logic.
Do not build a third extractor. Consolidate around the better path.

### Existing harvested-feed pipeline
- `scripts/personal-brand/fetch_reddit_signals.py`
- `scripts/personal-brand/fetch_rss_signals.py`
- `scripts/personal-brand/refresh_social_feed.py`

These already create harvested signal artifacts.
They are currently thin and partly placeholder-driven, but they are still the right pipeline anchors.

### Existing media-intake and transcript surfaces
- `knowledge/aiclone/transcripts/`
- `knowledge/ingestions/**`
- parent `memory/roadmap.md`

These are the correct upstream surfaces for YouTube, podcast, and transcript-derived sources.
Do not create a parallel audio/video ingestion stack inside the social workspace.

### Existing feedback endpoint
- `backend/app/routes/social_feedback.py`
- `backend/app/services/social_feedback_service.py`
- `backend/app/models/social_feedback.py`

The system already has `POST /api/workspace/feedback`.
Do not design `LNK-022` as if no feedback route exists.
Treat that backlog item as an expansion of the current schema and logging behavior.

### Existing persona / retrieval / content-generation stack
- `backend/app/routes/content_generation.py`
- `backend/app/services/retrieval.py`
- `scripts/persona/build_content_pack.py`
- `scripts/persona/bundle_tools.py`

This stack already gives us:
- weighted retrieval by channel and category
- anti-AI writing rules
- narrative arc guidance
- channel-aware prompt structure
- real example retrieval

Do not rebuild a brand-new voice system from scratch.
Lift the reusable parts of this stack into the Workspace response flow.

### Existing persona truth sources
- `knowledge/persona/feeze/identity/VOICE_PATTERNS.md`
- `knowledge/persona/feeze/identity/claims.md`
- `knowledge/persona/feeze/history/story_bank.md`
- `knowledge/persona/feeze/history/initiatives.md`

These are already the raw material for:
- belief anchoring
- experience anchoring
- story retrieval
- voice calibration

The first version of `belief_map` should be a projection over these sources, not a totally new database.

### Existing planning and snapshot surfaces
- `scripts/personal-brand/generate_linkedin_weekly_plan.py`
- `scripts/personal-brand/generate_linkedin_reaction_queue.py`
- `frontend/scripts/export-brain-snapshot.js`
- `frontend/legacy/content-pipeline/page.tsx`
- `backend/app/services/workspace_snapshot_service.py`

These already act like a state and dashboard layer for the workspace.
The tuning dashboard should extend this pattern before creating a separate frontend stack.

### Shared source-system rule
- transcript/media inputs should feed multiple downstream consumers off the same upstream asset inventory
- those consumers include:
  - daily briefs
  - weekly planning
  - Brain/persona review
  - social-feed routing when a unit is actually comment-ready
- do not let any one of those consumers invent a second ingest model

### Current live snapshot behavior
- `/ops` now fetches `GET /api/workspace/linkedin-os-snapshot` for:
  - workspace files
  - doc entries
  - weekly plan
  - reaction queue
  - social feed payload
  - feedback summary
- `/ops` also now derives a first-pass tuning dashboard from the live social-feed snapshot itself:
  - weak source grounding counts
  - warning hotspots
  - expression strategy mix
  - lane health rollups
  - an attention queue of the weakest current variants
- the backend now persists these workspace snapshots in Postgres via `workspace_snapshots`
- stale or thin snapshot rows are rebuilt from live runtime builders before they are returned
- the social feed now has a backend-native builder path in `backend/app/services/social_feed_builder_service.py`
- container-local `.json` artifacts are now secondary artifacts, not the runtime source of truth

### Existing orchestration example
- `backend/app/services/topic_intelligence_service.py`

This is already a multi-step orchestrated service in the repo.
Use it as a pattern for breaking the social-response system into explicit stages.

### Known stubs
- `backend/app/services/persona_service.py`
- `backend/app/services/analytics_service.py`
- `backend/app/services/content_optimization_service.py`
- `backend/app/services/cross_platform_analytics_service.py`

These should not be treated as existing capabilities just because the files exist.

## Core Distinction

There are two different input paths:

### 1. Manual capture
- user pastes a URL
- or user pastes stand-alone text
- system extracts the source immediately
- system returns a live preview card

### 2. Harvested feed capture
- LinkedIn-first saved signals
- Reddit
- Substack / RSS / web posts
- other curated external sources
- system pulls, ranks, stores, and surfaces candidates asynchronously

The next source-expansion phase adds a third upstream family:

### 3. Long-form media capture
- transcript metadata notes
- normalized ingestion artifacts
- YouTube and podcast transcript segments
- system extracts claim-sized units and routes them into comments, reposts, post seeds, or belief evidence depending on fit

These paths are different operationally, but they should converge into the same shared object:

## Shared Contract

### `NormalizedSignal`

Every source should be transformed into the same internal signal shape before interpretation.

Recommended fields:

```json
{
  "id": "signal_...",
  "ingest_mode": "manual|harvested",
  "source_channel": "linkedin|reddit|substack|web|rss|manual",
  "source_type": "post|article|comment_thread|dm|note",
  "source_class": "short_form|article|long_form_media|manual",
  "unit_kind": "full_post|paragraph|section|segment|quote_cluster|claim_block",
  "response_modes": ["comment", "repost", "post_seed", "belief_evidence"],
  "source_url": "https://...",
  "source_path": "workspaces/linkedin-content-os/research/market_signals/...",
  "title": "Short title",
  "author": "Author Name",
  "published_at": "2026-03-27T12:00:00Z",
  "captured_at": "2026-03-27T12:01:00Z",
  "raw_text": "Full extracted text",
  "summary": "Short normalized summary",
  "standout_lines": ["line 1", "line 2"],
  "core_claim": "Main thesis of the source",
  "supporting_claims": ["claim a", "claim b"],
  "topic_tags": ["ai", "education", "leadership"],
  "trust_notes": ["structured metadata", "manual fallback parse"],
  "source_metadata": {
    "engagement": {},
    "extraction_method": "jsonld|og|filtered_body|saved_signal"
  }
}
```

The first runtime slice of that source taxonomy is now live in the social feed builder, manual preview path, persisted snapshot rebuild, and `/ops` diagnostics. Long-form media routing still needs the later source-expansion tasks.

Everything after extraction should operate on `NormalizedSignal`, not on raw HTML, not on feed-specific JSON, and not on pasted text directly.

## Shared Thinking Path

The correct system shape is:

```text
Source Adapter
  -> Signal Normalizer
  -> Thesis Extractor
  -> Belief Contrast Engine
  -> Lane Interpreter
  -> Technique Selector
  -> Voice Renderer
  -> Critic / Evaluator
  -> UI Draft Card
  -> Feedback Logger
  -> Tuning Dashboard
```

That is the intended architecture for both manual previews and harvested-feed items.

## Shared Persona Review Contract

The Workspace and Brain surfaces are meant to share one persona-review substrate, not maintain two separate persona systems.

The shared substrate is:
- `POST /api/persona/deltas`
- `PATCH /api/persona/deltas/{delta_id}`
- `backend/app/services/persona_delta_service.py`
- the `persona_deltas` table in `backend/app/services/open_brain_db.py`

Current intended behavior:
- `Workspace` is the fast capture / approval surface for high-signal snippets, approved lines, and source-native phrasing worth saving.
- `Brain` is the deeper review / nuance / reflection / promotion-selection surface for persona items that still need judgment, story context, wording edits, or canonical placement decisions.
- canonical persona files under `knowledge/persona/feeze/**` remain a separate promotion boundary.

Important operational rule:
- a user approval inside Workspace already counts as a real approval at the persona-delta layer
- it should not require a second approval in Brain just to be considered saved

That means the current Workspace action:
- creates a persona delta
- marks it `approved`
- stores metadata such as `target_file`, `review_source`, source attribution, and lens context

That is different from Brain, which typically works with:
- `draft`
- `pending`
- `in_review`
- selective `reviewed` items that still need promotion or context refinement

So the systems should be understood like this:
- `Workspace approves snippets directly into shared persona-delta storage`
- `Brain reviews items that still need human shaping, nuance, or promotion decisions`
- `Neither surface should auto-write canonical persona files`

Current gap to keep in mind:
- because Workspace currently marks some deltas `approved` immediately, those items will usually not appear in Brain's pending review queue
- this is not a second system; it is the same system with different state transitions

Next-phase expectation:
- segmented long-form media now enters this same persona-delta lane in a first-pass sync through `backend/app/services/social_persona_review_service.py`
- those items should usually arrive in Brain as pending review items, not as already-finalized canonical persona updates

## Intelligence Layers

### 1. Thesis Extractor
Job:
- identify what the source is actually saying
- separate the main claim from supporting details
- surface 1-3 standout lines

This is not a voice layer.
This is not a lane layer.

It should answer:
- What is the source arguing?
- What is the strongest quotable line?
- What is the practical implication?

### 2. Belief Contrast Engine
Job:
- compare the source thesis to Feeze's actual worldview
- decide the relationship to the idea before generating copy

This is the missing layer in the current implementation.

It should answer:
- Do we agree, partly agree, disagree, or want to reframe?
- Is the best move to reinforce, nuance, counter, translate, or personalize?
- Which personal experience or operating belief makes the response real?

Recommended output:

```json
{
  "stance": "reinforce|nuance|counter|translate|personal-anchor|systemize",
  "agreement_level": "high|medium|low",
  "belief_used": "AI literacy is really judgment literacy",
  "experience_anchor": "real work in education / admissions / ops",
  "role_safety": "safe|review|risky"
}
```

Current implementation status:
- first pass is live in `backend/app/services/social_belief_engine.py`
- it is rule-based, lane-aware, and grounded in:
  - `knowledge/persona/feeze/identity/claims.md`
  - `knowledge/persona/feeze/history/story_bank.md`
  - `knowledge/persona/feeze/history/initiatives.md`
- it currently returns stance metadata plus belief/experience anchors for:
  - manual preview generation
  - saved feed artifact generation
- it does not yet power weekly planning, reaction-queue generation, or deeper thesis-vs-mainstream comparison

### 3. Lane Interpreter
Job:
- decide how the source should be read through a specific public lens

Current live lanes:
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

Important:
- lanes are not just labels
- lanes should produce meaningfully different interpretations
- `ai` must stay distinct from `ops-pm`
- `current-role` must stay distinct from `program-leadership`
- `therapy` must stay distinct from `referral`

### 4. Technique Selector
Job:
- choose how the message should feel, not just what it says

This is a small control layer, not a giant story-engine.

Start with 8-12 techniques:
- `curiosity-gap`
- `contrarian-reframe`
- `pattern-interrupt`
- `tension-escalation`
- `relatability-anchor`
- `specificity-injection`
- `authority-snap`
- `delayed-payoff`
- `story-fragment`
- `punchline-close`

Recommended output:

```json
{
  "techniques": ["contrarian-reframe", "authority-snap"],
  "emotional_profile": ["clarity", "tension"],
  "reason": "best fit for current-role + AI literacy signal"
}
```

Current implementation status:
- first pass is live in `backend/app/services/social_technique_engine.py`
- it currently returns:
  - `techniques`
  - `emotional_profile`
  - `reason`
- that metadata now flows through:
  - manual preview generation
  - saved feed artifact generation
  - `/ops` system-readout UI
- it is intentionally rule-based for now; later tuning should make it data-informed instead of hard-coded

### 5. Voice Renderer
Job:
- turn interpretation into usable social outputs

Primary response modes:
- `quick_reply`
- `suggested_comment`
- `suggested_repost`

Future response modes:
- `dm_reply`
- `comment_thread_followup`
- `original_post_seed`

### 6. Critic / Evaluator
Job:
- reject generic, blended, or out-of-character outputs before the UI shows them

Baseline checks:
- lane distinctiveness
- belief clarity
- lived-experience anchoring
- voice match
- expression quality
- role safety
- genericity penalty

Current implementation status:
- first pass is live in `backend/app/services/social_evaluation_engine.py`
- it currently scores:
  - `lane_distinctiveness`
  - `belief_clarity`
  - `experience_anchor_strength`
  - `voice_match`
  - `expression_quality`
  - `role_safety_score`
  - `genericity_penalty`
  - `source_expression_quality`
  - `output_expression_quality`
  - `expression_delta`
  - source/output structure preservation
  - `overall`
- it also emits lightweight warnings that now surface in `/ops`
- this is observability-first, not a final gatekeeper yet

Expression-quality is now a first-class relational signal in the live pipeline:
- source expression is analyzed at the sentence-rewrite boundary
- transformed expression is analyzed after rewrite selection
- the system carries the delta between them instead of only scoring the final output in isolation
- feedback logging now records these expression metrics alongside lane/stance/technique context

### 7. Feedback / Observability
Current implementation status:
- `/api/workspace/feedback` now records:
  - like / dislike / copy interactions
  - active lane
  - stance
  - belief anchor
  - experience anchor
  - technique bundle
  - evaluation score
- artifacts now written under `workspaces/linkedin-content-os/analytics/`:
  - `feed_feedback.md`
  - `feed_feedback.jsonl`
  - `feed_feedback_summary.json`
- this gives both humans and agents a restart-safe read on what was selected, what was copied, and which variants were already scoring weakly

## Persistent State Layers

The system should learn through explicit state, not vague prompt accumulation.

### `narrative_state`
- current public phase
- positioning
- current content emphasis
- recent overused themes

### `belief_map`
- core beliefs
- mainstream beliefs
- divergence points
- approved framing patterns

### `experience_graph`
- roles
- wins
- failures
- initiatives
- stories
- proof points

### `technique_library`
- available techniques
- usage guidance
- success patterns

### `performance_memory`
- what was copied
- what was approved
- what was posted
- what was ignored
- what actually sounded like Feeze

## Agent Species Mapping

This system should not be treated as one general-purpose agent.

### Orchestration frameworks
This is the core species for the Workspace product.

Use orchestration for:
- source routing
- lane-specific interpretation
- comment / repost generation
- feedback logging
- dashboard updates

### Coding harnesses
Use these to build and maintain AI Clone itself.

Examples:
- frontend changes
- backend refactors
- deploy fixes
- script work

### Auto research
Use this after the core orchestration path is stable.

Good uses:
- which techniques perform best by lane
- which opening lines get copied most
- which stance types outperform for specific source shapes

### Dark factories
Use sparingly and only for low-risk back-office work.

Allowed uses:
- batch draft regeneration
- overnight feed refreshes
- low-risk artifact generation

Not allowed as the default:
- autonomous public posting
- autonomous persona rewrites
- uncontrolled production code changes

## Suggested Repo Shape

The current preview service should eventually be decomposed into modules like:

```text
backend/app/services/social_feed/
  source_adapters.py
  normalized_signal.py
  thesis_extractor.py
  belief_engine.py
  lane_engine.py
  technique_engine.py
  voice_renderer.py
  critic_engine.py
  feedback_logger.py
  tuning_dashboard.py
```

Recommended route evolution:

- keep `POST /api/workspace/ingest-signal`
- add shared response metadata so the UI can inspect the reasoning path
- later add:
  - extend `POST /api/workspace/feedback`
  - `GET /api/workspace/tuning-dashboard`
  - `POST /api/workspace/evaluate-draft`

## Roadmap Mapping

This section maps the target architecture onto the current workspace backlog.

### Already completed
- `LNK-012` Split merged social feed lanes
- `LNK-013` Fix manual LinkedIn URL preview extraction
- `LNK-016` First-pass shared normalization across preview, saved-feed build, and manual web-signal ingestion
- `LNK-017` First-pass service decomposition: source extraction split from preview orchestration

### In progress / immediate next
- `LNK-014` Tighten per-lane voice calibration
- `LNK-015` Push the split lane taxonomy into planners and saved artifacts

### Next implementation wave
- `LNK-017` Decompose `social_feed_preview_service.py` into an orchestrated service stack
- `LNK-018` Add a belief contrast and experience anchoring layer
- `LNK-019` Add a technique selection layer for rhetorical / emotional shaping
- `LNK-020` Create a tuning dashboard contract that both humans and agents can use

### Later
- `LNK-021` Expand channel adapters beyond LinkedIn-first sources while preserving one shared interpretation path
- `LNK-022` Add explicit feedback logging and lightweight evaluation APIs
- `LNK-023` Add auto-research experiments for technique, stance, and lane optimization

## Implementation Order

Do not start with the dashboard UI.
Do not start with automation.

Recommended order:

1. `NormalizedSignal`
2. service decomposition
3. belief contrast engine
4. technique selector
5. critic checks
6. feedback logger
7. tuning dashboard
8. auto-research experiments

## Guidance For OpenClaw And Codex

When working in this workspace:
- preserve the split lane taxonomy
- do not collapse manual and harvested inputs into separate interpretation systems
- do not skip the belief-contrast step and jump straight from extraction to styled copy
- do not let feedback directly mutate persona truth without review
- do not treat social drafting as a dark-factory autopost pipeline
- prefer explicit structured state over vague prompt memory

If a future task touches source ingestion, lane generation, or tuning:
1. read this file
2. read `docs/social_feed_architecture_plan.md`
3. read `backlog.md`
4. inspect the live route and service implementation before designing changes
