# Phase 2: Persona Retrieval Implementation Plan

## Purpose
This document is the canonical implementation plan for Phase 2 of the social persona synthesis roadmap:
- retrieve the right persona evidence for the exact article
- stop relying on lane-default belief and experience switching
- hand a ranked persona packet into later stages
- make retrieval quality visible in Lab before drafting happens

This document is not a standalone roadmap.
It is the Phase 2 deep-dive for:
- `SOPs/social_persona_synthesis_roadmap_sop.md`

It assumes Phase 1 is the upstream dependency:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`

## Why Phase 2 Comes Immediately After Phase 1
The current social/article system can already:
- load persona truth
- pick a belief
- pick an experience
- generate lane-aware comments and reposts

But the current selection path is still shallow.

Today, the article-response path mostly does this:
- infer article/lane profile
- select one belief by lane/profile
- select one experience by lane/profile
- derive stance language
- render the lane template

That is why the system sounds repetitive.
It is not because the persona canon is empty.
It is because the social pipeline is skipping article-specific retrieval and jumping straight to simplified belief/experience selection.

Phase 2 fixes that by creating a real retrieval layer between:
- article/world understanding
- and drafting

## Connection To The Master Strategy
The master order remains:
1. article/world understanding
2. persona retrieval
3. Johnnie perspective
4. reaction brief
5. template composition trace
6. evaluation hardening
7. type matrix expansion
8. small-model optimization

Phase 2 only covers `2. persona retrieval`.

It must leave the system in a state where later phases can consume a ranked persona packet instead of re-deciding:
- which belief matters
- which story matters
- which initiative matters
- which approved delta matters

## Integrated Thought Clarification For Phase 2
Every Phase 2 slice must explicitly answer:

1. `What should this slice know?`
2. `What does the system compute today?`
3. `What is missing?`
4. `Why does that missing logic matter downstream?`
5. `What artifact should this slice output?`
6. `How will Lab measure pass / warn / fail / missing?`
7. `What existing contract must this slice reuse instead of replacing?`

This is mandatory for all retrieval work in this phase.

## Current Implementation Read

### What already exists and should be reused
The stronger persona/content path already has meaningful retrieval infrastructure:

- `backend/app/services/persona_bundle_context_service.py`
  - bundle chunk metadata:
    - `memory_role`
    - `domain_tags`
    - `audience_tags`
    - `proof_kind`
    - `proof_strength`
    - `artifact_backed`
    - `usage_modes`
  - bundle + committed overlay chunk loading
  - weighted bundle retrieval through `retrieve_bundle_persona_chunks`
  - diversity shaping across memory roles

- `backend/app/services/retrieval.py`
  - weighted retrieval utilities
  - category/channel weighting patterns
  - similarity scoring infrastructure

- `backend/app/services/persona_delta_service.py`
  - persistent `persona_deltas`
  - review and approval state

- `backend/app/services/persona_review_queue_service.py`
  - promotion metadata awareness
  - stage awareness around pending review / approved / promotion-ready

### What the weaker social path does today
The current social/article response path is mostly in:
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/social_signal_utils.py`

The bottleneck is concrete:

1. `load_persona_truth()` in `social_belief_engine.py`
- loads claims/stories/initiatives from markdown
- merges committed overlay promotions
- returns flattened truth lists

2. `_choose_belief(...)`
- mostly lane/profile switching
- picks one belief from a small repeated set

3. `_choose_experience(...)`
- mostly lane/profile switching
- picks one initiative or story from a small repeated set

4. `build_generation_context(...)` in `social_signal_utils.py`
- carries only:
  - one belief
  - one experience
  - one stance
  - one source takeaway

That means the current social path is skipping:
- ranked article-specific claims
- ranked stories
- ranked initiatives
- ranked approved deltas
- retrieval diversity checks
- overuse tracking

## The Actual Problem Phase 2 Must Solve
The persona canon is not the main issue.
The retrieval surface is.

The system currently knows a lot about Johnnie.
It just does not retrieve that knowledge with enough specificity for each article.

The real missing behavior is:
- this article is about X
- these 2 claims are the most relevant
- this one initiative is the strongest proof
- this story is relevant but secondary
- these approved deltas sharpen the angle
- this evidence set is diverse enough to sound like a real person, not a lane macro

That is the Phase 2 target.

## Scope
Phase 2 will build and expose:
- `PersonaRetrievalPacket`
- typed candidate generation across:
  - claims
  - stories
  - initiatives
  - approved deltas
- ranking and reranking logic
- diversity and overuse controls
- Lab visibility for retrieval quality

Phase 2 will not yet build:
- Johnnie perspective modeling
- reaction brief synthesis
- humor or style-family expansion
- template variation
- small-model optimization

## Architectural Rules
1. Do not invent a second persona store.
2. Reuse:
   - canonical bundle chunks
   - committed overlay chunks
   - approved review artifacts
3. Do not flatten retrieval back into one belief and one experience too early.
4. Do not move retrieval logic into Lab-only heuristics.
5. Do not rebuild the original post generator inside the social pipeline.
6. Treat approved deltas as a retrievable evidence source, not a separate memory universe.

## Phase 2 Output Objects

### 1. PersonaRetrievalPacket
One per article/lane run.

It should include at minimum:
- `query_summary`
- `query_text`
- `lane_id`
- `article_understanding_inputs`
- `claims`
- `stories`
- `initiatives`
- `approved_deltas`
- `selected_belief_candidate`
- `selected_experience_candidate`
- `retrieval_diversity`
- `retrieval_redundancy`
- `overuse_flags`
- `source_mix`
- `evidence`
- `missing_fields`

Each returned item should carry:
- `id`
- `chunk`
- `memory_role`
- `domain_tags`
- `proof_strength`
- `artifact_backed`
- `retrieval_source`
- `similarity_score`
- `weighted_score`
- `selection_reason`

### 2. RetrievalQueryPacket
The retrieval layer should not just reuse raw article title text.
It should construct a query from article/world understanding.

It should include:
- `article_main_claim`
- `world_stakes`
- `article_stance`
- `event_type`
- `actors`
- `lane`
- `content_goal`

### 3. RetrievalSelectionTrace
Lab must be able to show:
- why an item was retrieved
- why an item was selected
- why an item was dropped
- whether the mix is too repetitive

## Phase 2 Retrieval Sources
Phase 2 should retrieve from these sources in order:

1. `Canonical bundle chunks`
- claims
- stories
- initiatives
- voice-relevant canon where appropriate

2. `Committed overlay chunks`
- already promoted runtime overlay material

3. `Approved persona deltas`
- approved or review-complete items with usable evidence
- especially:
  - anecdotes
  - frameworks
  - phrase candidates
  - stats

4. `Optional legacy support`
- only if it helps coverage
- not required for the first working prototype

Rule:
Phase 2 must work without depending on legacy retrieval noise.

## Phase 2 Workstreams

### Workstream A: Retrieval Source Unification
Goal:
- unify the usable persona evidence sources into one typed retrieval surface

Build:
- canonical bundle source adapter
- committed overlay source adapter
- approved-delta source adapter

Primary reuse:
- `persona_bundle_context_service.py`
- `persona_delta_service.py`
- `persona_review_queue_service.py`

Success condition:
- the social pipeline can retrieve from all relevant persona sources without flattening them into plain strings first

### Workstream B: Query Construction
Goal:
- construct a retrieval query from article/world understanding instead of lane-only hints

Build:
- `RetrievalQueryPacket`
- article-informed query fields
- lane-informed weighting rather than lane-only routing

Primary reuse:
- Phase 1 `ArticleUnderstanding`
- `social_signal_utils.py`

Success condition:
- retrieval is grounded in article meaning, not just lane/category defaults

### Workstream C: Typed Candidate Generation
Goal:
- retrieve candidate claims, stories, initiatives, and deltas separately

Build:
- `retrieve_claim_candidates(...)`
- `retrieve_story_candidates(...)`
- `retrieve_initiative_candidates(...)`
- `retrieve_delta_candidates(...)`

Primary reuse:
- `retrieve_bundle_persona_chunks`
- bundle chunk metadata
- delta metadata

Success condition:
- the system has a ranked pool per artifact type before final selection

### Workstream D: Ranking And Reranking
Goal:
- choose the best evidence set, not just the closest text snippets

Build:
- similarity ranking
- domain compatibility boosts
- proof-strength boosts
- artifact-backed boosts
- memory-role-aware selection
- lane compatibility boosts
- delta approval-state boosts

Success condition:
- selected evidence is both relevant and structurally useful

### Workstream E: Diversity And Overuse Control
Goal:
- reduce repetition across runs and across lanes

Build:
- belief-family overuse tracking
- experience-anchor overuse tracking
- retrieval diversity scoring
- redundancy penalties

Success condition:
- the same claim or initiative stops dominating unrelated articles

### Workstream F: Selected Evidence Packet
Goal:
- output a compact persona packet for later phases

Build:
- selected claims
- selected stories
- selected initiatives
- selected deltas
- selected belief candidate
- selected experience candidate
- rationale fields

Success condition:
- Phase 3 can consume a real evidence packet instead of recomputing retrieval

### Workstream G: Lab Observability
Goal:
- expose retrieval quality directly in Lab

Build:
- candidate counts
- selected item summaries
- diversity score
- overuse warnings
- missing source classes
- missing artifact types

Success condition:
- `persona_retrieval` is no longer `missing`

## The Canonical Phase 2 Stage Board
Phase 2 should make these slices first-class:

1. `persona_truth`
2. `retrieval_query`
3. `candidate_claims`
4. `candidate_stories`
5. `candidate_initiatives`
6. `candidate_deltas`
7. `retrieval_reranking`
8. `retrieval_diversity`
9. `belief_selection`
10. `experience_selection`
11. `persona_retrieval`

These are the slices Phase 2 is allowed to fully own.
`johnnie_perspective` and `reaction_brief` remain downstream.

## Stage Contracts

### Persona Truth
Should know:
- what persona evidence sources are loaded and available

Current state:
- present, but too flattened in the social path

Missing:
- source-level visibility
- freshness and coverage visibility

Outputs:
- truth-source inventory

Measure:
- `persona_truth_loaded`
- `claims_loaded`
- `stories_loaded`
- `initiatives_loaded`
- `overlay_loaded`
- `approved_deltas_loaded`

### Retrieval Query
Should know:
- what we are actually searching for in persona memory

Current state:
- implicit and lane-heavy

Missing:
- explicit article-informed query object

Outputs:
- retrieval query packet

Measure:
- `retrieval_query_present`
- `article_grounded_query_score`
- `lane_weighting_present`

### Candidate Claims
Should know:
- which claims could help explain Johnnie's viewpoint here

Current state:
- not retrieved as a ranked claim set

Missing:
- ranked claim candidates

Outputs:
- claim candidate list

Measure:
- `claim_candidate_count`
- `claim_relevance_score`
- `claim_diversity_score`

### Candidate Stories
Should know:
- which stories or anecdotes are relevant, if any

Current state:
- one story may be picked by lane

Missing:
- ranked story candidates

Outputs:
- story candidate list

Measure:
- `story_candidate_count`
- `story_relevance_score`
- `story_specificity_score`

### Candidate Initiatives
Should know:
- which initiatives provide proof or operating context

Current state:
- one initiative may be picked by lane

Missing:
- ranked initiative candidates

Outputs:
- initiative candidate list

Measure:
- `initiative_candidate_count`
- `initiative_relevance_score`
- `initiative_proof_score`

### Candidate Deltas
Should know:
- which approved review artifacts sharpen the response

Current state:
- not retrieved as a first-class article-specific source

Missing:
- ranked delta candidates

Outputs:
- delta candidate list

Measure:
- `delta_candidate_count`
- `delta_relevance_score`
- `delta_approval_coverage`

### Retrieval Reranking
Should know:
- which candidates should win after weighting and filtering

Current state:
- missing as a dedicated stage

Missing:
- explicit reranking logic

Outputs:
- selected evidence packet

Measure:
- `retrieval_reranking_score`
- `proof_mix_score`
- `source_mix_score`

### Retrieval Diversity
Should know:
- whether the selected set is too narrow or repetitive

Current state:
- limited diversity control in the bundle path, not in social retrieval

Missing:
- run-level and lane-level overuse logic

Outputs:
- diversity packet

Measure:
- `retrieval_diversity_score`
- `retrieval_redundancy_penalty`
- `belief_overuse_penalty`
- `experience_overuse_penalty`

### Belief Selection
Should know:
- which retrieved belief candidate should frame the response

Current state:
- mostly lane/profile switching

Missing:
- evidence-backed belief selection from retrieved candidates

Outputs:
- selected belief candidate

Measure:
- `belief_relevance_score`
- `belief_specificity_score`
- `belief_overuse_penalty`

### Experience Selection
Should know:
- which retrieved experience should anchor the response

Current state:
- mostly lane/profile switching

Missing:
- evidence-backed experience selection from retrieved candidates

Outputs:
- selected experience candidate

Measure:
- `experience_relevance_score`
- `experience_specificity_score`
- `experience_overuse_penalty`

### Persona Retrieval
Should know:
- whether the system built a usable persona packet before drafting

Current state:
- missing as a first-class modeled stage

Missing:
- ranked article-specific retrieval packet

Outputs:
- `PersonaRetrievalPacket`

Measure:
- `persona_retrieval_score`
- `relevant_claims_count`
- `relevant_story_count`
- `relevant_initiative_count`
- `relevant_delta_count`
- `retrieval_diversity_score`

## Recommended File Strategy

### Reuse directly
- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/services/retrieval.py`
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/persona_delta_service.py`
- `backend/app/services/persona_review_queue_service.py`
- `backend/app/services/lab_experiment_service.py`

### Likely new runtime service
- `backend/app/services/social_persona_retrieval_service.py`

Reason:
- Phase 2 is too large to keep embedding inside `social_belief_engine.py`
- retrieval should become a reusable packet-producing layer
- later phases should consume its output

### Likely callers
- `social_signal_utils.py`
- `social_belief_engine.py`
- Lab experiment builders
- future `social_reaction_brief_service.py`

## Recommended Implementation Shape

### Step 1: Build retrieval source adapters
Adapters should normalize:
- bundle chunk records
- committed overlay chunk records
- approved-delta records

### Step 2: Build article-informed retrieval query construction
Inputs:
- article main claim
- world stakes
- event type
- article stance
- lane

### Step 3: Retrieve per artifact type
Do not jump straight to one merged list.
Retrieve separately first.

### Step 4: Rerank the merged candidate pool
Use:
- similarity
- domain fit
- proof strength
- artifact-backed status
- usage mode compatibility
- approval state

### Step 5: Select compact evidence packet
Return a small set, for example:
- 2 to 3 claims
- 1 to 2 stories
- 1 to 2 initiatives
- 1 to 2 approved deltas

### Step 6: Feed selected belief and experience into the existing social path
Phase 2 should adapt the current path, not replace it all at once.

## Lab Rendering Plan
For each probe/article, Lab should render:

### Retrieval Query
- query summary
- article inputs used
- lane inputs used

### Candidate Pools
- top claims
- top stories
- top initiatives
- top deltas

### Selection Panel
- selected belief candidate
- selected experience candidate
- rejected candidates with reasons

### Diversity Panel
- source mix
- role mix
- overuse warnings
- redundancy warnings

### Stage Diagnostics
- pass / warn / fail / missing
- score
- reason
- evidence
- missing fields

## Quantification
Phase 2 should introduce these scores:
- `persona_truth_loaded_score`
- `retrieval_query_score`
- `claim_relevance_score`
- `story_relevance_score`
- `initiative_relevance_score`
- `delta_relevance_score`
- `retrieval_diversity_score`
- `belief_relevance_score`
- `experience_relevance_score`
- `persona_retrieval_rollup_score`

Suggested status policy:
- `pass`: score >= 8.5 and required artifact types are present
- `warn`: score >= 6.5 or one artifact type is weak/missing
- `fail`: score < 6.5 or retrieval is materially off-topic
- `missing`: the slice is not yet modeled

## Qualification
Every score must include a reason.

Examples:
- `persona_retrieval_warn`: "Claims and initiatives were retrieved, but no article-specific story or approved delta was found."
- `belief_selection_fail`: "The selected belief matched the lane but not the article stakes."
- `experience_selection_warn`: "The selected initiative is valid but has been overused across unrelated education articles."
- `candidate_deltas_missing`: "Approved deltas are not yet queried as retrievable evidence."

## Exit Criteria
Phase 2 is only complete when:
1. `persona_retrieval` is no longer `missing` in Lab
2. the system can show ranked claims, stories, initiatives, and deltas before drafting
3. belief selection is derived from retrieved candidates, not lane-only switching
4. experience selection is derived from retrieved candidates, not lane-only switching
5. overuse is measured and visible
6. later phases can consume the `PersonaRetrievalPacket` directly

## Non-Goals
Do not spend Phase 2 time on:
- humor
- opener banks
- template variation
- reaction-brief copywriting
- lane flavor polish
- small-model cost tuning

Those remain downstream of retrieval correctness.

## Risks

### Risk: Creating a second persona memory system
Mitigation:
- only adapt existing bundle, overlay, and delta sources

### Risk: Overweighting legacy retrieval
Mitigation:
- make legacy support optional, not required

### Risk: Flattening deltas into plain text too early
Mitigation:
- preserve approval metadata and source type in candidate records

### Risk: Lab-only retrieval heuristics
Mitigation:
- build runtime retrieval packets first
- render them in Lab second

### Risk: Excessive complexity before Phase 1 is real
Mitigation:
- require `ArticleUnderstanding` inputs
- do not let Phase 2 rebuild article/world logic

## Handoff To Phase 3
Phase 3 should consume:
- selected claims
- selected stories
- selected initiatives
- selected approved deltas
- belief selection rationale
- experience selection rationale

Phase 3 should not have to retrieve persona evidence again.
It should answer the next question:
- what does Johnnie actually agree with, resist, add, and care about here?

That is the Phase 2 contract.

Phase 3 deep-dive:
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`

## Small-Model Note
`gpt-4o-mini` compatibility remains important, but it is not the Phase 2 success condition.
Phase 2 succeeds when the system retrieves the right persona evidence before drafting.
Model-cost optimization remains downstream of correctness.

## Related Files
- `SOPs/social_persona_synthesis_roadmap_sop.md`
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`
- `SOPs/persona_grounded_content_generation_sop.md`
- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/services/retrieval.py`
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/persona_delta_service.py`
- `backend/app/services/persona_review_queue_service.py`
- `backend/app/services/lab_experiment_service.py`
