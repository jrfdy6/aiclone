# Phase 1: Article / World Understanding Implementation Plan

## Purpose
This document is the canonical attack plan for Phase 1 of the social persona synthesis roadmap:
- make the system understand what an article is saying
- make the system understand how that article exists in the world
- make that understanding visible in Lab
- prepare clean handoff into later phases:
  - persona retrieval
  - Johnnie perspective
  - reaction brief

This is not a standalone roadmap.
It is the Phase 1 deep-dive for:
- `SOPs/social_persona_synthesis_roadmap_sop.md`

## Why Phase 1 Comes First
The social/article response system is currently good enough to:
- normalize source signals
- infer lanes
- pick a stance family
- produce usable comments and reposts

But it is still weak in the first half of the problem:
- it does not model article stance as a first-class object
- it does not model real-world stakes deeply enough
- it does not compare the current article to what the system has already seen
- it does not produce a durable article/world packet that later stages can trust

That weakness creates downstream distortion:
- persona retrieval becomes lane-default instead of article-specific
- Johnnie perspective becomes generic instead of situational
- drafts sound like translation instead of reaction
- Lab can only say a draft is clean, not whether the system understood the article

Phase 1 exists to fix that upstream.

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

This document only covers `1. article/world understanding`.

It must leave the system in a state where later phases can reuse a stable article/world packet instead of rebuilding source understanding in:
- `social_belief_engine.py`
- lane builders in `social_signal_utils.py`
- Lab-only heuristics
- ad hoc prompts

## Integrated Thought Clarification For Phase 1
Every Phase 1 slice must answer these questions explicitly:

1. `What should this slice know?`
2. `What does the system compute today?`
3. `What is missing?`
4. `Why does that missing logic matter downstream?`
5. `What artifact should this slice output?`
6. `How will Lab measure pass / warn / fail / missing?`
7. `What existing contract must this slice reuse instead of replacing?`

This is mandatory for every implementation step in this phase.

## Current Implementation Read
The current article-side logic mostly lives in:
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_expression_engine.py`
- `backend/app/services/lab_experiment_service.py`

The strongest existing pieces are:
- `standout_lines_from_text`
- `infer_source_channel`
- `infer_source_class`
- `infer_unit_kind`
- `infer_response_modes`
- `infer_default_lane`
- normalized signal construction around:
  - `title`
  - `summary`
  - `standout_lines`
  - `core_claim`
  - `supporting_claims`
  - `why_it_matters`
- source takeaway selection through:
  - `preserve_source_structure`
  - `rewrite_source_claim`
  - `select_source_takeaway`

The actual gap is not zero understanding.
The gap is that the current understanding is too shallow and too ephemeral.

Today, the system is mostly deriving:
- a compact normalized signal
- a lane
- a stance family for drafting
- a source takeaway

It is not yet deriving a durable article/world object that includes:
- article thesis and supporting-claim hierarchy
- article stance and stance confidence
- world stakes and affected actors
- event type
- source world position
- novelty versus what the system has already seen
- structured evidence for why the article matters

## Scope
Phase 1 will build and expose:
- `ArticleUnderstanding`
- a first-pass `WorldModel` foundation
- novelty/difference detection
- richer article-side Lab observability

Phase 1 will not yet build:
- article-specific persona retrieval
- Johnnie reaction synthesis
- reaction briefs
- humor
- template-family diversification
- small-model optimization

## Architectural Rules
1. Reuse the shared source contract in `SOPs/source_system_contract_sop.md`.
2. Do not create a second ingest stack.
3. Do not create a second persona system.
4. Do not bury article understanding inside prompt text only.
5. Do not let Lab become the only place where article understanding exists.
6. Build reusable runtime artifacts first, then visualize them in Lab.

## Phase 1 Output Objects

### 1. ArticleUnderstanding
One per normalized article-like source.

It should include at minimum:
- `article_id`
- `source_url`
- `source_channel`
- `source_class`
- `unit_kind`
- `title`
- `summary`
- `main_claim`
- `supporting_claims`
- `standout_lines`
- `event_type`
- `topic_domains`
- `subdomains`
- `actors`
- `affected_audiences`
- `institutions`
- `world_stakes`
- `why_it_matters`
- `article_stance`
- `article_stance_confidence`
- `article_world_position`
- `source_expression_family`
- `source_expression_signals`
- `seen_before`
- `novelty_level`
- `novelty_reason`
- `related_pattern_ids`
- `comparison_summary`
- `evidence`
- `missing_fields`

### 2. WorldModel Foundation
This is not the full worldview bridge.
It is the cumulative article-side memory needed to answer:
- what have we seen before in this domain?
- what patterns keep repeating?
- what tensions are stable?
- what looks new or different this time?

For Phase 1, the world model can begin as:
- light pattern clustering
- domain/subdomain counters
- recurring actor/institution summaries
- repeated tension summaries
- recent-comparison snapshots

### 3. ArticleUnderstanding Trace
Lab must be able to show:
- the chosen values
- scores
- evidence
- missing fields
- the exact reason a slice is warn/fail/missing

## Phase 1 Workstreams

### Workstream A: Normalize Article-Side Semantics
Goal:
- take the current normalized signal and make article semantics explicit

Build:
- explicit `event_type`
- explicit `topic_domains`
- explicit `actors`
- explicit `affected_audiences`
- explicit `institutions`
- explicit `world_stakes`

Primary reuse:
- `backend/app/services/social_signal_utils.py`

Success condition:
- `world_understanding` can point to specific world fields, not just lane tags

### Workstream B: Article Stance Modeling
Goal:
- model what the article itself is doing before we model Johnnie's response

Build:
- `article_stance`
- `article_stance_confidence`
- `article_world_position`

Suggested stance families:
- `report`
- `warn`
- `advocate`
- `analyze`
- `translate`
- `speculate`
- `celebrate`
- `critique`

Primary reuse:
- existing source-claim and structure detection in `social_signal_utils.py`
- expression signals in `social_expression_engine.py`

Success condition:
- `article_stance` is no longer `missing` in Lab

### Workstream C: Source Expression Packet
Goal:
- preserve how the article is making its point, not just what it says

Build:
- article-level structure family
- contrast signal
- directive signal
- causal signal
- warning signal
- narrative/story signal

Primary reuse:
- `backend/app/services/social_expression_engine.py`
- existing `preserve_source_structure` and `rewrite_source_claim`

Success condition:
- Lab can show whether source expression was understood or flattened

### Workstream D: Novelty And Comparison
Goal:
- let the system answer:
  - have I seen this before?
  - what is similar?
  - what is different?
  - why is it different?

Build:
- `seen_before`
- `novelty_level`
- `novelty_reason`
- `related_pattern_ids`
- `comparison_summary`

For Phase 1, novelty can be based on:
- domain overlap
- actor overlap
- event-type overlap
- claim/tension overlap
- source-expression similarity

This can be heuristic first.
It does not need to be a heavy semantic memory system yet.

Primary reuse:
- normalized signal artifacts
- current workspace/source history
- later bridge to retrieval services

Success condition:
- the system can stop treating every article as isolated

### Workstream E: WorldModel Foundation
Goal:
- turn repeated article-side observations into reusable world context

Build:
- a lightweight article/world accumulation layer
- domain pattern summaries
- recurring tension summaries
- actor/institution trend summaries

Phase 1 rule:
- this is `world understanding`, not persona canon
- do not auto-promote world observations into persona truth

Success condition:
- article comparison becomes grounded in prior observed patterns

### Workstream F: Lab Observability
Goal:
- make every Phase 1 slice inspectable

Build:
- article/world stage evidence rendering
- missing-field rendering
- stage score rendering
- stage reason rendering
- per-run article understanding panels

Primary files:
- `backend/app/services/lab_experiment_service.py`
- `frontend/app/lab/page.tsx`

Success condition:
- Lab can show exactly which part of article/world understanding is real, weak, or missing

## The Canonical Phase 1 Stage Board
Phase 1 should make these slices first-class:

1. `signal_intake`
2. `source_contract`
3. `claim_extraction`
4. `world_understanding`
5. `article_stance`
6. `source_expression`
7. `novelty_comparison`
8. `world_model_foundation`

These are the only slices that Phase 1 is allowed to fully own.
Everything else must remain out of scope until this board is real.

## Stage Contracts

### Signal Intake
Should know:
- whether the article packet is complete enough to reason over

Current state:
- present but confidence is thin

Missing:
- explicit extraction-loss telemetry

Outputs:
- signal completeness indicators

Measure:
- `signal_completeness_score`
- `core_claim_present`
- `supporting_claims_count`
- `raw_text_present`

### Source Contract
Should know:
- what kind of source this is and which response modes it supports

Current state:
- mostly healthy

Missing:
- explicit classification confidence

Outputs:
- source contract packet

Measure:
- `source_contract_score`
- `classification_confidence`

### Claim Extraction
Should know:
- article thesis and supporting hierarchy

Current state:
- shallow `core_claim` and `supporting_claims`

Missing:
- clearer claim hierarchy
- counter-claim awareness

Outputs:
- thesis packet

Measure:
- `claim_clarity_score`
- `supporting_signal_score`
- `standout_line_quality_score`

### World Understanding
Should know:
- what kind of world this article lives in
- who is affected
- what the stakes are
- why it matters

Current state:
- mostly topic and lane hints

Missing:
- explicit stakes model
- explicit actor model
- event type
- institutional context

Outputs:
- world context packet

Measure:
- `world_context_score`
- `affected_actor_present`
- `world_stakes_present`
- `event_type_present`
- `why_it_matters_present`

### Article Stance
Should know:
- what the article itself is trying to do

Current state:
- missing as a first-class object

Missing:
- stance label
- confidence
- world position

Outputs:
- article stance packet

Measure:
- `article_stance_present`
- `article_stance_confidence`
- `article_world_position_present`

### Source Expression
Should know:
- how the article is making its case

Current state:
- partial structure handling exists

Missing:
- explicit article-level expression packet

Outputs:
- structure packet

Measure:
- `source_expression_score`
- `structure_family_present`
- `structure_preservation_score`

### Novelty Comparison
Should know:
- whether this is familiar, different, or contradictory

Current state:
- not modeled

Missing:
- prior-pattern comparison
- novelty reason

Outputs:
- novelty packet

Measure:
- `novelty_comparison_present`
- `seen_before_present`
- `novelty_reason_present`
- `comparison_summary_score`

### WorldModel Foundation
Should know:
- what repeated patterns are accumulating across articles

Current state:
- not modeled as a dedicated layer

Missing:
- durable pattern memory on the article/world side

Outputs:
- world-model snapshot

Measure:
- `world_model_foundation_present`
- `pattern_summary_count`
- `domain_memory_coverage`

## Recommended File Strategy

### Reuse directly
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_expression_engine.py`
- `backend/app/services/lab_experiment_service.py`
- `SOPs/source_system_contract_sop.md`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`

### Likely new runtime service
- `backend/app/services/social_article_understanding_service.py`

Reason:
- Phase 1 should not keep inflating `social_signal_utils.py`
- article understanding deserves a stable service boundary
- later phases should consume its output instead of recomputing source understanding ad hoc

### Likely callers
- `social_signal_utils.py`
- Lab experiment builders
- future persona retrieval and reaction-brief services

## Lab Rendering Plan
For each probe/article, Lab should render:

### Article Snapshot
- title
- source channel
- event type
- domain/subdomain
- actors
- audiences
- institutions

### Article Stance Snapshot
- stance
- confidence
- world position
- evidence

### World Snapshot
- stakes
- why it matters
- seen before or not
- novelty reason
- related pattern summary

### Stage Diagnostics
- pass / warn / fail / missing
- score
- reason
- evidence
- missing fields

## Quantification
Phase 1 should introduce these scores:
- `signal_completeness_score`
- `source_contract_score`
- `claim_clarity_score`
- `world_context_score`
- `article_stance_confidence`
- `source_expression_score`
- `novelty_comparison_score`
- `world_model_foundation_score`
- `article_understanding_rollup_score`

Suggested status policy:
- `pass`: score >= 8.5 and no critical missing fields
- `warn`: score >= 6.5 or minor missing fields
- `fail`: score < 6.5 or article understanding is materially wrong
- `missing`: the slice does not yet exist as a real modeled object

## Qualification
Every score must be accompanied by a reason.

Examples:
- `world_understanding_warn`: "The article was tagged as education, but affected actors and institutional stakes were not extracted."
- `article_stance_missing`: "The system has no first-class article stance object yet."
- `novelty_comparison_fail`: "The system could not explain how this article differs from related prior education-governance signals."

## Exit Criteria
Phase 1 is only complete when:
1. `article_stance` is no longer missing in Lab
2. `world_understanding` is pass-heavy, not warn-heavy
3. `source_expression` is explicit and inspectable
4. `novelty_comparison` exists and is evidence-backed
5. `world_model_foundation` exists as a real runtime object
6. later phases can consume `ArticleUnderstanding` without rebuilding article logic

## Non-Goals
Do not spend Phase 1 time on:
- humor
- opener banks
- template variation
- lane flavor polish
- post-generator tuning
- small-model cost tuning
- article-to-persona promotion logic

Those are downstream of this phase.

## Risks

### Risk: Duplicating the source system
Mitigation:
- only extend normalized signal consumers
- do not invent a second ingest path

### Risk: Rebuilding persona early
Mitigation:
- keep world understanding separate from persona truth
- hand off to Phase 2 instead of mixing concerns

### Risk: Lab-only logic
Mitigation:
- build runtime objects first
- render them in Lab second

### Risk: Over-modeling too soon
Mitigation:
- use heuristic comparison first
- reserve heavy semantic retrieval for later phases

## Handoff To Phase 2
Phase 2 should consume:
- `ArticleUnderstanding`
- world-model comparison outputs
- novelty signals
- stakes signals
- article stance

Phase 2 should not have to re-decide:
- what the article is about
- who is affected
- why it matters
- whether it is familiar or novel

That is the Phase 1 contract.

Phase 2 deep-dive:
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`

## Small-Model Note
`gpt-4o-mini` compatibility remains important, but it is not the Phase 1 success condition.
Phase 1 succeeds when article/world understanding is real, visible, and reusable.
Small-model optimization remains downstream of correctness.

## Related Files
- `SOPs/social_persona_synthesis_roadmap_sop.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `SOPs/source_system_contract_sop.md`
- `SOPs/brain_workspace_boundary_sop.md`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_expression_engine.py`
- `backend/app/services/lab_experiment_service.py`
