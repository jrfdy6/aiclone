# SOP: Idea Qualification Gate

## Purpose
Define the canonical pre-draft admission contract for FEEZIE OS and the broader AI Clone content pipeline so weak ideas die before they consume drafting, PM, or owner-review attention.

This SOP exists because the current system already has:

- source ingestion
- social-feed normalization
- long-form source routing
- persona grounding
- owner review
- PM execution

But it still admits too many weak ideas upstream. Today, ranking and conversion happen before a hard editorial gate, which means the system still spends energy on ideas that never earned the right to be written.

The goal of this SOP is to establish one enforced contract between:

- source/feed/backlog intake
- and any downstream drafting or planning surface

So the system shifts from:

`everything gets a chance to prove itself`

to:

`nothing gets written until it proves it deserves to exist`

## Core Rule
Use a binary admission gate with explicit failure reasons.

Do not score weak ideas into legitimacy.

An idea may become a post seed, weekly-plan recommendation, queue item, or owner-review draft only if it passes the qualification contract defined here.

## Scope
This SOP applies to idea admission for:

- `plans/reaction_queue.{json,md}`
- `plans/weekly_plan.{json,md}`
- `drafts/queue_01.md` promotion candidates
- future owner-review draft materialization

It does not replace:

- downstream draft-generation grounding
- the 7-layer draft evaluation contract
- publish approval
- PM execution routing

This is the upstream gate, not the entire editorial system.

It also governs stale generated drafts:

- if a previously materialized `reaction_seed` draft no longer passes qualification
- it should be quarantined into `drafts/archive/stale_reaction_drafts/`
- and removed from active weekly planning surfaces

## Architectural Placement

```text
SourceAsset / BacklogItem / FeedItem
  -> NormalizedSignal
  -> IdeaCandidate
  -> IdeaQualificationReport
  -> route = pass | latent | discard
  -> downstream consumer
```

Downstream consumer means:

- `reaction_queue.post_seeds`
- `weekly_plan.recommendations`
- `weekly_plan.hold_items`
- later: backlog/queue promotion and owner-review draft materialization

## Non-Negotiable Design Rules

### 1. Same editorial standard, different source suspicion
All idea sources must pass the same core contract.

But the system should treat sources differently:

- `own_thinking`
  - more tolerant of rare high-variance latent ideas
- `external_signal`
  - must translate into your angle and audience consequence
- `ai_synthesis`
  - strictest lane; must prove delta, proof path, and strategic relevance explicitly

### 2. Insight and utility are separate lanes
The qualification gate must support two content classes:

- `insight`
  - default lane
  - must reframe something the reader thinks they understand
- `utility`
  - controlled minority lane
  - lower novelty allowed, but it still must be sharp, proof-backed, and strategically justified

### 3. Hard discard is the default
Default routing for failure is `discard`.

Use `latent` only when:

- the idea is strategically real but missing proof or timing
- or it is a rare high-variance idea that is under-formed but interesting

### 4. Comments and standalone post seeds are not the same
The reaction queue may still list fast reaction opportunities for comments/reposts.

But no item should become a standalone `post_seed` unless it passes this gate.

That distinction prevents the quick-response lane from diluting the post-creation lane.

### 5. Dead generated drafts should not linger as active inventory
If a feed-derived draft was created before the gate tightened, and it now routes to `discard` or `latent`, it should not stay in the active `drafts/` inventory.

Archive it with a manifest entry so:

- provenance is preserved
- weekly planning stays honest
- dead drafts stop masquerading as active work

## Canonical Contract

### `IdeaCandidate`
This is the canonical upstream object that every idea source must normalize into before qualification.

Recommended implementation shape: Pydantic model or dataclass plus JSON artifact persistence.

```json
{
  "idea_id": "string",
  "workspace": "linkedin-os",
  "source_kind": "own_thinking|external_signal|ai_synthesis|existing_backlog|long_form_segment",
  "source_ref": {
    "source_path": "string|null",
    "source_url": "string|null",
    "source_id": "string|null",
    "source_asset_id": "string|null"
  },
  "content_lane": "ai|ops-pm|program-leadership|therapy|referral|current-role|admissions|entrepreneurship|personal-story",
  "content_type": "insight|utility",
  "title": "string",
  "raw_angle": "string",
  "current_belief": "string",
  "new_belief": "string",
  "delta": "string",
  "audience": "string",
  "audience_consequence": "string",
  "strategic_goal": "string",
  "why_now": "string",
  "proof_refs": ["string"],
  "proof_summary": "string",
  "lived_experience_present": true,
  "repeated_pattern_present": false,
  "high_variance_hint": false,
  "portfolio_tags": ["string"],
  "upstream_scores": {
    "ranking_total": 0.0
  },
  "created_at": "2026-04-10T00:00:00Z"
}
```

#### Required fields
- `idea_id`
- `workspace`
- `source_kind`
- `content_lane`
- `content_type`
- `title`
- `raw_angle`
- `audience`
- `audience_consequence`
- `strategic_goal`
- `why_now`
- `created_at`

#### Conditionally required fields
- `current_belief`
- `new_belief`
- `delta`

These are required for `insight` ideas.

For `utility` ideas, they may be blank, but the idea must still explain:

- who it helps
- what practical clarity it creates
- why this belongs in your narrative now

#### Source-specific rules

##### `own_thinking`
- `raw_angle` may originate from backlog or lived note capture
- `high_variance_hint` is allowed
- still must provide proof path or explicit proof gap

##### `external_signal`
- must include `source_ref`
- must translate the source into your own angle
- cannot pass on “interesting topic” alone

##### `ai_synthesis`
- must never pass with empty `delta`
- must never pass with empty `proof_refs` and empty `proof_summary`
- must be treated as suspect until grounded

### `IdeaQualificationReport`
This is the canonical gate output.

This object is authoritative for routing.

```json
{
  "idea_id": "string",
  "qualified": false,
  "route": "discard|latent|pass",
  "content_type_confirmed": "insight|utility",
  "core_tests": {
    "sharpness": {
      "passed": false,
      "reason": "no single point or tension",
      "evidence": "angle is broad and splits in multiple directions"
    },
    "non_obviousness": {
      "passed": false,
      "reason": "does not create a meaningful belief shift",
      "current_belief": "reader believes X",
      "new_belief": "reader should leave with Y",
      "delta": "weak or unclear"
    },
    "proof_potential": {
      "passed": true,
      "reason": "backed by lived initiative and proof refs",
      "proof_mode": "artifact|story|pattern|metric"
    },
    "strategic_relevance": {
      "passed": true,
      "reason": "fits current lane and target audience",
      "audience_consequence": "clarifies operator positioning"
    }
  },
  "variance": {
    "level": "low|high",
    "reason": "contrarian but under-formed"
  },
  "failure_dimensions": ["sharpness", "non_obviousness"],
  "latent_reason": "missing_proof|wrong_timing|high_variance|reinforcement_without_fresh_work|needs_context_translation|null",
  "salvageable": false,
  "suggested_fix": "narrow to one lived operating example",
  "downstream_permissions": {
    "allow_reaction_comment": true,
    "allow_post_seed": false,
    "allow_weekly_plan_recommendation": false,
    "allow_weekly_plan_hold_item": false,
    "allow_queue_promotion": false,
    "allow_draft_materialization": false
  },
  "created_at": "2026-04-10T00:00:00Z"
}
```

#### Required fields
- `idea_id`
- `qualified`
- `route`
- `content_type_confirmed`
- `core_tests`
- `failure_dimensions`
- `variance`
- `salvageable`
- `downstream_permissions`
- `created_at`

#### Contract rule
`route` is the enforcement field.

Downstream systems must not infer their own route if a report is present.

## Qualification Tests

### 1. Sharpness
Question:

`Is there a single, clear point here?`

Pass when:

- one point dominates
- tension or contrast is visible
- the idea can be stated cleanly in one sentence

Fail when:

- topic is broad
- multiple points compete
- the angle reads like a content bucket, not a claim

### 2. Non-Obviousness
Question:

`Does this reframe something the reader thinks they understand?`

Default pass hierarchy:

- primary: reframes understanding
- secondary: says something familiar in a much sharper or more real way through your experience
- “people do not know this” alone is not enough

Implementation rule:

Every `insight` idea must explicitly declare:

- `current_belief`
- `new_belief`
- `delta`

Automatic fail when:

- these fields are empty
- or the `delta` is weak, generic, or merely informational

### 3. Proof Potential
Question:

`Can this be backed by something real?`

Pass when at least one is true:

- lived experience exists
- a real story exists
- a defendable artifact or metric exists
- a repeated operating pattern exists

Fail when:

- idea is hypothetical
- advice-only
- abstract without proof path

### 4. Strategic Relevance
Question:

`Does this serve your positioning right now?`

Pass when:

- it fits a real lane
- it has a defined audience consequence
- it helps build or reinforce your narrative in a controlled way

Fail when:

- it is interesting but not useful
- audience is unclear
- relevance to current positioning is weak

## Utility-Lane Override
Utility content is allowed, but only under a tighter secondary bar.

For `content_type = utility`:

- `sharpness` must still pass
- `proof_potential` must still pass
- `strategic_relevance` must still pass
- `non_obviousness` may pass through clarity and usefulness rather than deep reframing

But utility must still answer:

- who this helps
- what practical ambiguity it resolves
- why this belongs in your system now

Do not use `utility` as a loophole for generic content.

## Routing Logic

### `pass`
Route to `pass` only when:

- all required core tests pass
- the item is eligible for its declared `content_type`

Effects:

- may enter `reaction_queue.post_seeds`
- may enter `weekly_plan.recommendations`
- may later be promoted to queue/draft surfaces

### `latent`
Use `latent` only when the idea is real but not ready.

Allowed latent cases:

- `missing_proof`
  - angle is strong, but evidence is not ready
- `wrong_timing`
  - strategically valid, but not the right moment
- `high_variance`
  - under-formed but meaningfully interesting
- `reinforcement_without_fresh_work`
  - useful concept, but it needs new proof, framing, or audience before it earns promotion
- `needs_context_translation`
  - the core point is real, but the system still cannot state why this matters for your audience in your language

Effects:

- should persist in `plans/latent_ideas.{json,md}`
- may appear in the reaction queue as a latent transform candidate
- should carry a transform plan:
  - `transform_type`
  - `autotransform_ready`
  - `transform_status`
  - `proposed_angle`
  - `owner_question`
  - `revision_goals`
  - `proof_prompt`
  - `promotion_rule`
- should not clutter `weekly_plan.hold_items` unless a human already put the item into a hold state
- must not become `post_seed`
- must not become a draft

### `discard`
Default failure route.

Use `discard` when:

- angle is vague
- reframing is weak or nonexistent
- proof path is absent
- strategic relevance is weak
- the idea is generic, redundant, or content-shaped rather than insight-shaped

Effects:

- invisible to draft-generation surfaces
- invisible to PM
- not promoted into owner review

## Source-Aware Qualification Rules

### `own_thinking`
- same core gate
- if it fails only because it is early but interesting, allow `latent/high_variance`

### `external_signal`
- must translate into:
  - your angle
  - your audience consequence
  - your reason for saying it now
- if the system only knows “this source is interesting,” route to `discard`

### `ai_synthesis`
- strictest source
- no pass without explicit:
  - `delta`
  - proof path
  - strategic relevance
- if it looks plausible but unowned, route to `discard`

## Wiring Contract

### Canonical stage order

```text
build_social_feed
  -> qualify_ideas
  -> generate_linkedin_reaction_queue
  -> generate_linkedin_weekly_plan
  -> generate_feezie_owner_review_drafts
```

The qualification stage must sit before both reaction-queue post-seed promotion and weekly-plan recommendation generation.

## Wiring Into `reaction_queue`

### Files
- `scripts/personal-brand/generate_linkedin_reaction_queue.py`
- later, optional new shared builder:
  - `scripts/personal-brand/generate_linkedin_idea_qualification.py`
  - or backend service equivalent

### Current problem
The current reaction queue takes the top eight social-feed items by ranking and turns them directly into comments and `post_seeds`.

That is too permissive for standalone post creation.

### Required new behavior
1. Normalize each feed item into an `IdeaCandidate`.
2. Run qualification before building standalone post seeds.
3. Preserve fast reaction opportunities separately from post-seed eligibility.

### Reaction queue contract after change

#### `comment_opportunities`
- may still include socially legible comment opportunities
- should not require full post-seed qualification
- may carry qualification metadata for observability

#### `post_seeds`
- must include only `IdeaQualificationReport.route == pass`

#### `latent transform queue`
- optional new section
- items that are strategically real but not ready
- should expose the next worker move, not just the latent reason

#### `discarded_post_seed_count`
- optional summary count only
- do not clutter the operator-facing queue with rejected material

### Required behavior rules
- A failed idea may still be comment-worthy.
- A failed idea may not become a standalone post seed.
- `post_seed` promotion is governed by qualification, not ranking score.

### Recommended artifact extension
Either:

- add a dedicated `plans/idea_qualification.json`

Or:

- embed `qualification` blocks directly in `reaction_queue.json`

Preferred early-stage choice:

- `plans/idea_qualification.json`

Reason:

- keeps the gate auditable
- lets weekly plan consume the same decision object
- prevents each script from recomputing its own editorial judgment

## Wiring Into `weekly_plan`

### Files
- `scripts/personal-brand/generate_linkedin_weekly_plan.py`

### Current problem
The weekly plan currently converts feed items into recommendations using lane, rationale, hook, and ranking score, but not a hard admission gate.

### Required new behavior
1. Existing drafts remain eligible as already-materialized work.
2. Net-new feed-derived recommendations must come from qualified ideas only.
3. Latent ideas should route to the dedicated latent-idea artifact, not recommendations.

### Weekly plan contract after change

#### `recommendations`
May include:

- existing drafts
- qualified passed ideas

Must not include:

- latent ideas
- discarded ideas

#### `hold_items`
Should include:

- optionally older drafts already in review/hold states
- stale or risky items that still need human handling

#### `market_signals`
May remain a broad awareness section, but it must not silently function as a second recommendation lane.

### Required behavior rules
- ranking may prioritize among qualified ideas
- ranking must not replace qualification
- latent items should be visible in the latent pool, not soft recommendations

## Implementation Notes

### Recommended first implementation
Use a small shared module that exposes:

- `normalize_feed_item_to_idea_candidate(item) -> IdeaCandidate`
- `qualify_idea(candidate) -> IdeaQualificationReport`

And persist the reports into:

- `plans/idea_qualification.json`
- optional `plans/idea_qualification.md`

Then:

- `generate_linkedin_reaction_queue.py`
  - reads qualification results
  - builds `post_seeds` from `route == pass`
  - builds a latent transform queue for worker-ready latent items
- `materialize_latent_transform_drafts.py`
  - picks up `autotransform_ready == true`
  - creates or updates first-pass `latent_transform` drafts
  - refreshes latent inventory so transformed items show `transform_status = drafted`
- `generate_linkedin_weekly_plan.py`
  - reads qualification results
  - builds `recommendations` from `route == pass`
  - keeps `hold_items` for real hold/risk states
  - points latent inventory to `plans/latent_ideas.{json,md}`

### Explicit non-goals for phase 1
- do not introduce weighted scoring as the decision mechanism
- do not put owner-review judgment into this stage
- do not let PM become the source of truth for idea admission
- do not create a second ingest model

## Verification Checklist
Before treating the gate as live, verify:

1. A weak ranked feed item can no longer become a `post_seed`.
2. A strong but missing-proof idea routes to `latent`, not `recommendation`.
3. An insight item without `current_belief/new_belief/delta` fails qualification.
4. A utility item can pass without deep reframing only if proof and audience consequence are strong.
5. `weekly_plan.recommendations` no longer include discarded or latent ideas.
6. Existing drafts still appear in planning surfaces as already-materialized work.
7. Owner-review draft volume falls because fewer weak ideas are promoted upstream.

## Success Criteria
- Fewer weak ideas enter drafting.
- Fewer owner-review cards exist solely to sort weak upstream material.
- Reaction queue remains useful for comments without becoming a loophole for bad post seeds.
- Weekly plan recommendations become materially more trustworthy.
- The system gains one canonical admission contract instead of another competing heuristic surface.

## Related Files
- `workspaces/linkedin-content-os/docs/operating_model.md`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
- `scripts/personal-brand/generate_linkedin_reaction_queue.py`
- `scripts/personal-brand/generate_linkedin_weekly_plan.py`
- `scripts/personal-brand/generate_feezie_owner_review_drafts.py`
- `backend/app/services/social_feed_builder_service.py`
- `backend/app/services/social_long_form_signal_service.py`
- `SOPs/content_generation_staged_pipeline_map.md`
- `SOPs/source_system_contract_sop.md`

## Notes
- This SOP intentionally defines a binary gate, not a weighted editorial score.
- The downstream 7-layer evaluation contract should sit after this stage, not inside it.
- Portfolio balancing affects sequencing and priority, not basic admission.
