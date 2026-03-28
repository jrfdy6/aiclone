# Source Expansion Implementation Plan

This document maps source expansion into the current LinkedIn Workspace system.

It is not a greenfield plan.
It extends the live social-response stack, the live `/ops` tuning dashboard, and the existing media-intake system already described in the parent roadmap.

Use this document when the task touches:
- Reddit / RSS / Substack source quality
- podcast or YouTube transcript intake
- transcript-to-signal segmentation
- post-seed generation from long-form media
- belief capture from external sources
- source-class health in `/ops`

## Why This Exists

The system now has enough diagnostics to show where it is strong and weak:
- LinkedIn-native inputs are the strongest source class
- safe-source feed items are live and real, but many variants still have weak source grounding
- the system performs best when the input is claim-shaped, compact, and socially legible

That means source expansion should not be framed as "add more pipes."

It should be framed as:
- add more source classes
- extract better claim-sized units
- route those units into the correct downstream job

This plan extends an existing upstream source system.
It does not authorize a second transcript or briefing pipeline.

## Constraints

This plan must respect the current system constraints.

### 1. Reuse the existing media-intake system
- Do not create a second text/audio/video ingestion architecture.
- Reuse the parent `Media Intake System` roadmap lane in `memory/roadmap.md`.
- Reuse existing transcript and ingestion surfaces:
  - `knowledge/aiclone/transcripts/`
  - `knowledge/ingestions/**`
  - existing queued media job flow described in the parent roadmap

### 2. Preserve one shared interpretation path
- All source classes still need to converge into the same internal signal contract before:
  - belief contrast
  - lane interpretation
  - technique selection
  - evaluation

### 3. Do not treat long-form media as one feed item
- A podcast episode or YouTube transcript is not a single social signal.
- Long-form media must be segmented into claim-sized units first.

### 4. Not every source belongs in the same downstream surface
- Some signals should become:
  - comment / repost candidates
  - post seeds
  - belief evidence
  - quote candidates
- Do not force every source into the comment feed.

### 5. Preserve the persona promotion boundary
- External sources can clarify worldview.
- They must not auto-write canonical persona files.
- Persona updates still require review / approval.

### 6. Keep the system observable
- Every new source class must show up in `/ops` diagnostics.
- If a source class is noisy or weak, the dashboard should make that visible.

## Current State

Today the social system already has these intake classes:

### Live short-form / article sources
- LinkedIn saved signals under `workspaces/linkedin-content-os/research/market_signals/`
- Reddit via `backend/app/services/social_source_fetch_service.py`
- RSS / Substack via `backend/app/services/social_source_fetch_service.py`
- manual URL / pasted-text preview via `POST /api/workspace/ingest-signal`

### Existing long-form media infrastructure outside the feed
- transcript library in `knowledge/aiclone/transcripts/`
- transcript metadata template in `knowledge/aiclone/transcripts/TEMPLATE.md`
- normalized ingestions lane in `knowledge/ingestions/**`
- parent media-intake roadmap and queued media job flow in `memory/roadmap.md`
- workspace snapshot weekly-plan builder already loading media candidates from normalized ingestions
- Brain/persona review already syncing long-form worldview evidence from those same source assets

### Existing downstream consumers that already overlap
- daily briefs / overnight operator awareness
- weekly planning
- Brain persona review
- `/ops` source-asset and tuning diagnostics

This means the open work is not “build another long-form system.”
The open work is “finish unifying routing and observability across the consumers that already exist.”

### Current missing source classes in the feed
- YouTube transcript segments
- podcast transcript segments
- audio-derived transcript segments
- transcript-native quote candidates
- transcript-native belief evidence

## Core Design Principle

The feed should not be modeled as "platform items."

It should be modeled as:
- source assets
- extractable units
- candidate signals

That gives us this hierarchy:

### Source asset
- LinkedIn post
- Reddit thread
- Substack post
- RSS article
- YouTube video
- podcast episode
- transcript file

### Extractable unit
- full post
- paragraph
- section
- timestamped segment
- quote cluster
- claim block

### Candidate signal
- the actual item that enters the shared social pipeline

This same hierarchy should also support briefing and planning.
The feed is only one consumer of the hierarchy, not the whole reason the hierarchy exists.

## Source Taxonomy

These are the source classes the system should explicitly support.

### 1. Native short-form
- LinkedIn posts
- Reddit posts / threads
- short social text

Expected shape:
- usually one source asset produces one candidate signal

Best downstream jobs:
- comment
- repost
- quick reply
- reaction queue

### 2. Article / essay
- RSS news
- Substack posts
- web articles

Expected shape:
- one source asset may produce one to three candidate signals

Best downstream jobs:
- comment
- repost
- post seed
- evidence for worldview patterns

### 3. Long-form media
- YouTube video transcripts
- podcast transcripts
- audio-derived transcripts

Expected shape:
- one source asset produces many candidate segments

Best downstream jobs:
- post seeds
- belief evidence
- quote candidates
- comment / repost only when a segment is sharp enough

### 4. Manual capture
- pasted text
- pasted quotes
- manual URL preview

Expected shape:
- one user action produces one working signal immediately

Best downstream jobs:
- live preview
- fast comment / repost exploration
- seed creation

## New Internal Contracts

The current `NormalizedSignal` contract stays, but source expansion needs two upstream contracts.

### `SourceAsset`

Represents the original thing collected by the system.

```json
{
  "asset_id": "asset_...",
  "source_class": "short_form|article|long_form_media|manual",
  "source_channel": "linkedin|reddit|rss|substack|youtube|podcast|manual",
  "source_type": "post|article|video|episode|transcript|note",
  "source_url": "https://...",
  "title": "Asset title",
  "author": "Author or speaker",
  "published_at": "2026-03-28T00:00:00Z",
  "raw_path": "knowledge/ingestions/... or transcript path",
  "metadata_path": "knowledge/aiclone/transcripts/... optional",
  "ingest_mode": "harvested|manual|media_pipeline"
}
```

### `SignalUnit`

Represents a claim-sized unit extracted from the source asset.

```json
{
  "unit_id": "unit_...",
  "asset_id": "asset_...",
  "unit_kind": "full_post|paragraph|section|segment|quote_cluster|claim_block",
  "start_ref": "timestamp or paragraph ref",
  "end_ref": "timestamp or paragraph ref",
  "source_text": "claim-sized text",
  "headline_candidates": ["best line"],
  "core_claim": "main thesis of this unit",
  "supporting_claims": ["supporting point"],
  "topics": ["ai", "education"],
  "speaker_role": "host|guest|author|poster"
}
```

### `NormalizedSignal`

The existing shared contract remains the social-runtime contract.

The only change is that it should retain:
- `source_asset_id`
- `source_class`
- `unit_kind`
- `response_modes`

```json
{
  "id": "signal_...",
  "source_asset_id": "asset_...",
  "source_class": "short_form|article|long_form_media|manual",
  "unit_kind": "segment|paragraph|full_post",
  "response_modes": ["comment", "repost", "post_seed", "belief_evidence"]
}
```

## Response Routing

This is the most important new rule.

Not every normalized signal should go to the same place.

### Comment-ready
Use when the source unit is:
- compact
- explicit
- socially legible
- likely to support a direct response

Send to:
- social feed cards
- reaction queue

### Repost-ready
Use when the source unit is:
- strong enough to quote or summarize publicly
- still close enough to the original source to credit clearly

Send to:
- social feed repost drafts

### Post-seed
Use when the source unit is:
- rich
- more interesting as inspiration than as a direct response
- especially common for transcript segments

Send to:
- weekly planning
- draft input generation

### Belief-evidence
Use when the source unit is:
- useful for worldview clarification
- something to agree with, nuance, or reject
- more useful for persona memory than for immediate posting

Send to:
- tuning dashboard
- belief review packet
- persona review workflow

## Persona / Belief Capture

This source expansion should directly help the persona system, but only through explicit reviewable outputs.

Each source unit should be eligible to produce:
- `agreement`
- `partial_agreement`
- `counterpoint`
- `translation`
- `experience_match`
- `language_pattern_match`

That means the source system can help build:
- a saved belief map
- a saved disagreement map
- a saved experience map
- a saved language-pattern library

But the promotion boundary remains:
- source analysis may propose
- the system may log
- canonical persona files still require approval

## Shared Workspace / Brain Persona Contract

Source expansion should feed one shared persona-review system, not create a second one.

The contract is:
- `Workspace` can fast-approve high-signal snippets or phrasing into `persona_deltas`
- `Brain` remains the main place for pending review, nuance, story/context, wording refinement, and promotion selection
- canonical persona files still do not auto-update from either surface

Operational meaning:
- if the user explicitly approves a snippet in Workspace, that counts as a valid approval and should not require a duplicate Brain approval just to save it
- if the system produces a larger or less-settled worldview item, that should land in Brain as a pending review item instead of bypassing the review queue

This gives the system one judgment center with two entry surfaces:
- `Workspace finds and saves candidate language quickly`
- `Brain decides what needs additional context, disagreement, story, or canonical placement`

Long-form media should follow this path:

```text
SourceAsset
  -> SignalUnit
  -> NormalizedSignal
  -> response_mode = belief_evidence
  -> persona_delta candidate
  -> Brain review
  -> optional canonical promotion
```

Current design rule:
- do not force segmented long-form worldview evidence through Workspace approval first
- send it into the shared persona-delta lane with enough source context that Brain can review it directly

Observability requirement:
- `/ops` should eventually show:
  - workspace-approved persona items
  - pending Brain review items
  - approved-but-not-promoted items
  - long-form evidence awaiting review by source class
- Brain should remain the place where the operator can clear the pending review queue intentionally

## Benchmark Baseline

Use the live `/ops` tuning dashboard as the benchmark source of truth for this phase.

Current baseline from the real-only sample on the live feed:
- sample size: `80` lane variants from `8` feed items
- `Avg Overall`: `7.7`
- `Avg Source`: `2.7`
- `Avg Expr`: `6.4`
- `Avg Δ`: `0.2`
- `Weak Source`: `47`
- `Lane Carried`: `47`
- `Warnings`: `51`
- platform health:
  - `linkedin`: `src 6.5 · expr 6.8 · Δ 0.3 · weak 0`
  - `reddit`: `src 0.6 · expr 6.2 · Δ 0.2 · weak 9`
  - `substack`: `src 0.3 · expr 6.1 · Δ 0.1 · weak 19`
  - `rss`: `src 0.3 · expr 6.0 · Δ 0.0 · weak 19`

Interpretation:
- LinkedIn-native source quality is the benchmark to protect.
- Safe-source classes are the primary improvement target.
- Source grounding is the first bottleneck.
- Expression quality is secondary until source grounding improves.

## Benchmark Discipline

Every source-expansion phase should be judged against the same dashboard concepts:
- `Avg Source`
- `Avg Expr`
- `Avg Δ`
- `Weak Source`
- `Lane Carried`
- `Warnings`
- platform / source-class health
- structure health
- attention queue composition

Do not rely on `Avg Overall` by itself.
It can stay stable while source grounding remains weak.

## Production Validation Timing

Each implementation phase should be tested in production on a fixed cadence.

### 1. Pre-deploy baseline capture
Run before changing behavior:
- capture the current `/ops` dashboard values
- capture the current `social_feed.items` count and source-class mix
- note the current attention-queue failure modes

### 2. Immediate validation
Timing:
- `0-10 minutes` after deploy

Actions:
- run `npm run verify:production`
- confirm schema / UI changes are visible in `/ops`
- confirm no regression in snapshot richness or feed availability

Use for:
- taxonomy changes
- dashboard field additions
- routing metadata

### 3. Deterministic rebuild validation
Timing:
- `10-20 minutes` after deploy

Actions:
- trigger `POST /api/workspace/refresh-social-feed` with `{"skip_fetch": true}`
- wait for refresh completion
- compare dashboard metrics against the pre-deploy baseline

Use for:
- changes to normalization
- routing
- builder logic
- planner-side signal handling

### 4. Full refresh validation
Timing:
- `20-60 minutes` after deploy

Actions:
- trigger `POST /api/workspace/refresh-social-feed` with `{}`
- wait for completion
- confirm source-specific behavior on live fetched items
- compare source-class metrics in `/ops`

Use for:
- source adapter changes
- fetcher changes
- live source ranking changes

### 5. Next-cycle validation
Timing:
- `12-24 hours` after deploy or after the next meaningful source arrival

Actions:
- confirm the new source class continues to appear without manual repair
- confirm the dashboard still shows the expected source-class health
- confirm no new high-volume warning class dominates the attention queue

Use for:
- transcript/media adapters
- long-form segmentation
- worldview evidence capture

### Release rule

A source-expansion phase is not done when the code ships.

It is done when:
- immediate validation passes
- deterministic rebuild validation passes
- full refresh validation passes for affected source classes
- next-cycle validation shows no regression or silent failure

## Implementation Phases

This work should be added to the existing roadmap as a structured continuation of `LNK-021`.

### Phase 1. Source taxonomy and routing contract
Roadmap item:
- `LNK-026`

Outcome:
- define source classes, unit kinds, and response modes across the social pipeline

Touch points:
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_feed_builder_service.py`
- `backend/app/services/workspace_snapshot_service.py`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`

Acceptance signal:
- every feed item reports `source_class`, `unit_kind`, and `response_modes`

Benchmark goal:
- `0` regression in feed availability or snapshot richness
- `100%` of feed items expose the new fields in runtime payloads
- no material degradation in current baseline metrics during the deterministic rebuild check

Production validation timing:
- immediate validation
- deterministic rebuild validation

### Phase 2. Media-source adapter integration
Roadmap item:
- `LNK-027`

Outcome:
- add one adapter that reads transcript / media-ingest assets from:
  - `knowledge/aiclone/transcripts/`
  - `knowledge/ingestions/**`

Touch points:
- parent media-intake system
- new adapter in the social backend
- no second ingestion architecture

Acceptance signal:
- the social system can see transcript-derived source assets without manual copy/paste
- `/ops` shows those assets as upstream inventory with routing status before any feed-card promotion happens

Benchmark goal:
- transcript / media-ingest assets appear as `source_class = long_form_media`
- `0` transcript assets are forced directly into the comment feed before segmentation exists
- no regression in LinkedIn or safe-source dashboard metrics after deploy

Production validation timing:
- immediate validation
- next-cycle validation

### Phase 3. Long-form segmentation
Roadmap item:
- `LNK-028`

Outcome:
- split transcripts into claim-sized units before they enter the social runtime

Touch points:
- transcript metadata parsing
- segment selection
- claim extraction
- candidate-unit scoring

Acceptance signal:
- one transcript can yield multiple segment signals instead of one giant blob

Benchmark goal:
- `0` full-transcript blobs appear as direct feed cards
- one test transcript yields multiple `SignalUnit` candidates
- for transcript-derived comment/repost candidates, target:
  - `Avg Source >= 4.5`
  - `Weak Source <= 25%`
  - `Avg Δ >= 0.2`

Production validation timing:
- deterministic rebuild validation
- next-cycle validation

### Phase 4. Response-mode routing
Roadmap item:
- `LNK-029`

Outcome:
- route each normalized signal into the right downstream job:
  - comment
  - repost
  - post_seed
  - belief_evidence

Touch points:
- social feed builder
- weekly planner
- reaction queue
- belief review packet

Acceptance signal:
- transcript segments no longer default into comment cards unless they are actually comment-ready

Benchmark goal:
- transcript-derived long-form units primarily route to `post_seed` or `belief_evidence`
- any media-derived unit that remains comment-ready in the feed should target:
  - `Src >= 5.0`
  - `Expr >= 6.5`
  - `Δ >= 0.3`
- feed-wide `Lane Carried` should decrease from the current baseline on comparable sample sizes

Current runtime state:
- first-pass shared routing is now live through `backend/app/services/social_long_form_signal_service.py`
- the persisted workspace snapshot now exposes `long_form_routes`
- `/ops` now shows route counts, primary-route mix, channels, and top routed long-form candidates
- `social_persona_review_service.py` now consumes the shared long-form candidate set for `belief_evidence` instead of maintaining a separate transcript parsing path
- the weekly-plan snapshot now reuses the shared long-form route set for planner-visible `media_post_seeds` and `belief_evidence_candidates` instead of treating media planning as a separate inference path
- production now returns the routed planner overlay correctly, but the current follow-on is metadata reconciliation: `weekly_plan.generated_at` still comes from the base file-backed planner artifact and should be updated to reflect the augmented planner state once the route overlay is applied
- long-form routing is still upstream-oriented: comment/repost eligibility is classified, but transcript-derived units are expected to land primarily in `post_seed` / `belief_evidence` until production benchmarks prove otherwise

Production validation timing:
- deterministic rebuild validation
- full refresh validation
- next-cycle validation

### Phase 5. Persona-memory capture
Roadmap item:
- `LNK-030`

Outcome:
- let source contrast produce reviewable worldview artifacts instead of only copy outputs

Touch points:
- `backend/app/services/social_belief_engine.py`
- feedback / analytics layer
- future persona review packet flow

Acceptance signal:
- the system can show "what you agree with / disagree with / keep noticing" as a structured review surface

Benchmark goal:
- every worldview evidence record includes:
  - source reference
  - stance
  - belief relation
  - optional experience match
- `0` automatic writes to canonical persona files
- review surfaces show usable evidence counts by source class

Production validation timing:
- immediate validation
- next-cycle validation

### Phase 6. Shared persona-review contract
Roadmap item:
- `LNK-032`

Outcome:
- formalize the shared Workspace / Brain persona lifecycle so fast snippet approvals and deeper persona review both use the same delta contract without duplicate approvals

Touch points:
- `frontend/app/ops/OpsClient.tsx`
- `frontend/app/brain/BrainClient.tsx`
- `backend/app/routes/persona.py`
- `backend/app/services/persona_delta_service.py`
- this document and `docs/social_intelligence_architecture.md`

Acceptance signal:
- a Workspace snippet approval creates a saved approved delta without requiring duplicate Brain approval
- Brain pending reviews only show items that still need context, nuance, or promotion judgment
- canonical persona files still remain behind the explicit promotion boundary
- `/ops` can show the shared lifecycle counts from the live workspace snapshot instead of hiding this state inside separate UIs

Benchmark goal:
- `0` duplicate approval loops for workspace-approved snippets
- `0` automatic writes to canonical persona files
- the system can explain, from UI state alone, whether an item is:
  - saved from Workspace
  - pending Brain review
  - approved but not promoted

Production validation timing:
- immediate validation
- deterministic rebuild validation

### Phase 7. Route segmented worldview evidence into Brain review
Roadmap item:
- `LNK-033`

Outcome:
- turn transcript-derived worldview segments into reviewable persona items with source context, stance, and optional promotion targets

Current implementation state:
- first pass is live
- `backend/app/services/social_persona_review_service.py` now reads long-form `source_assets`, extracts claim-sized worldview segments, evaluates them through `social_belief_engine.py`, filters wrapper noise from normalized transcript markdown, resolves stale autogenerated draft segments when extractor quality changes, and writes draft review items into the shared `persona_deltas` lifecycle
- `backend/app/services/workspace_snapshot_service.py` now runs that sync while rebuilding `persona_review_summary`, so Brain-facing worldview evidence is visible on the same shared approval substrate instead of a second queue

Touch points:
- `backend/app/services/social_belief_engine.py`
- segmentation/routing outputs from `LNK-028` and `LNK-029`
- `frontend/app/brain/BrainClient.tsx`
- snapshot and dashboard surfaces

Acceptance signal:
- one segmented long-form source can produce multiple reviewable persona items
- Brain can show those items with source reference, stance, and target-file context
- no full transcript appears as one giant persona-review item

Benchmark goal:
- at least one test transcript yields multiple reviewable worldview items
- every review item includes:
  - source reference
  - stance or belief relation
  - target file or promotion hint when available
- no transcript-derived worldview item requires a second manual approval after an explicit Workspace approval

Production validation timing:
- deterministic rebuild validation
- next-cycle validation

### Phase 8. Dashboard and planner intelligence
Roadmap item:
- `LNK-031`

Outcome:
- extend `/ops` and planner surfaces so source quality is visible by source class, response mode, and belief-capture yield

Touch points:
- `frontend/app/ops/OpsClient.tsx`
- `backend/app/services/workspace_snapshot_service.py`
- planner outputs

Acceptance signal:
- `/ops` can show:
  - source-class health
  - segment yield
  - response-mode mix
  - belief-evidence queue
  - post-seed queue
  - persona-review queue state by source class and approval stage

Benchmark goal:
- `/ops` exposes source-class health for every active source class
- planner surfaces can distinguish:
  - feed-ready signals
  - post seeds
  - belief evidence
- the Brain daily-brief surface can read the same live source-intelligence overlay as the planner, including route counts, belief-relation counts, and top `post_seed` / `belief_evidence` candidates
- benchmark comparisons can be made from one deploy to the next without reconstructing the sample manually

Current production note (`2026-03-28`):
- this phase is now partially live end to end
- `/ops` exposes the route/source-class intelligence
- the weekly-plan payload now returns the routed media overlay with fresh planner timestamps
- `/api/briefs` and the Brain daily-brief panel now read the same live source-intelligence overlay instead of a brief-only inference path
- the next follow-on is deeper brief/planner consumption, not another source stack

Production validation timing:
- immediate validation
- deterministic rebuild validation
- full refresh validation

## Proposed Build Order

This is the recommended implementation order inside the existing system:

1. `LNK-026`
   Current production note (`2026-03-28`): the mixed feed recovered after the source-taxonomy rollout, but the live refresh currently shows LinkedIn + RSS/Substack and no Reddit items. If the next-cycle validation still shows no Reddit coverage, pause the transcript/media sequence and reprioritize Reddit source debugging first.
2. `LNK-027`
3. `LNK-028`
4. `LNK-029`
5. `LNK-030`
6. `LNK-032`
7. `LNK-033`
8. `LNK-031`
9. return to tuning improvements once source quality is stronger

## What Success Looks Like

The source system is working when:
- LinkedIn posts still remain strong
- Reddit / RSS / Substack are more source-grounded than they are today
- YouTube / podcast transcripts produce sharp post seeds instead of mushy feed cards
- the dashboard shows which source classes are paying off
- the persona system accumulates reviewable belief evidence from the world without rewriting itself automatically
- Workspace and Brain are visibly using one shared persona lifecycle instead of parallel approval loops
- the production validation cadence can confirm each of those claims after deploy rather than relying on spot checks

## Non-Goals

This phase is not:
- fully autonomous posting
- rewriting canonical persona files automatically
- treating every source as a comment candidate
- creating a second media-ingestion stack outside the parent roadmap

## Files To Read Before Implementation

- `memory/roadmap.md`
- `workspaces/linkedin-content-os/backlog.md`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
- `workspaces/linkedin-content-os/docs/social_feed_architecture_plan.md`
- `workspaces/linkedin-content-os/research/watchlists.yaml`
- `knowledge/aiclone/transcripts/README.md`
- `knowledge/aiclone/transcripts/TEMPLATE.md`
