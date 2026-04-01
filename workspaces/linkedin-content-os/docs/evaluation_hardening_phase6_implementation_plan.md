# Phase 6: Evaluation Hardening Implementation Plan

## Purpose
This document is the canonical implementation plan for Phase 6 of the social persona synthesis roadmap:
- harden the evaluation layer so it scores the full synthesis stack, not just clean-looking output
- make Lab and runtime scoring reflect article understanding, persona retrieval, Johnnie perspective, reaction-brief quality, and composition trace
- turn stage observability into trustworthy shipping gates

This document is not a standalone roadmap.
It is the Phase 6 deep-dive for:
- `SOPs/social_persona_synthesis_roadmap_sop.md`

It assumes the upstream phases exist:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`

## Why Phase 6 Comes After Template Composition
Before Phase 6, the system is still building the things that need to be judged:
- article/world understanding
- persona retrieval
- Johnnie perspective
- reaction brief
- composition trace

If evaluation hardening comes too early, the system produces false precision:
- benchmark numbers on top of missing stages
- green outputs that still feel repetitive
- quality claims based only on surface fluency

Phase 6 comes after Phase 5 because the evaluator should now be able to consume:
- article-side packets
- persona-side packets
- synthesis packets
- composition trace
- normalization trace

That is the point where the benchmark can stop grading only polished text and start grading real synthesis quality.

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

Phase 6 only covers `6. evaluation hardening`.

It must leave the system in a state where:
- a high score actually means something
- a green Lab run implies the earlier phases are real, not hidden
- shipping decisions are based on synthesis truth, not only draft polish

## Integrated Thought Clarification For Phase 6
Every Phase 6 slice must explicitly answer:

1. `What should this slice know?`
2. `What does the system compute today?`
3. `What is missing?`
4. `Why does that missing logic matter downstream?`
5. `What artifact should this slice output?`
6. `How will Lab measure pass / warn / fail / missing?`
7. `What existing contract must this slice reuse instead of replacing?`

This is mandatory for all evaluation work in this phase.

## Current Implementation Read

### What already exists and should be reused
The current social evaluation layer in `backend/app/services/social_evaluation_engine.py` already scores:
- `lane_distinctiveness`
- `belief_clarity`
- `experience_anchor_strength`
- `voice_match`
- `expression_quality`
- `role_safety_score`
- `genericity_penalty`
- `benchmark_score`

It also already checks:
- generic language
- abstract meta phrasing
- stance contrast weakness
- source-expression preservation
- role safety

The stronger original-post generator also already uses a more disciplined taste-scoring pattern in:
- `backend/app/routes/content_generation.py`

That scorer already knows how to reason about:
- claim-led openings
- proof visibility
- named-reference specificity
- contrast presence
- cadence
- weak closers
- taste-negative phrases

The current Lab system already provides:
- explicit stage catalogs
- pass / warn / fail / missing
- experiment-level benchmark targets

### What is actually happening today
The current social evaluator is still mostly judging:
- lane specificity
- belief clarity
- experience visibility
- voice polish
- expression quality
- safety

That means it can still over-score outputs even when:
- article stance is missing
- persona retrieval is not modeled
- Johnnie perspective is missing
- reaction brief is missing
- template composition is not traced

In other words:
- the evaluator can score clean output
- but it cannot yet fully score whether the system understood, synthesized, and constrained the output correctly

That is the Phase 6 gap.

## The Actual Problem Phase 6 Must Solve
The system now needs an evaluator that can answer:
- did the system understand the article?
- did it retrieve the right persona evidence?
- did it model a real Johnnie perspective?
- did it build a usable reaction brief?
- did it assemble the draft in a traceable way?
- does the final output still sound true after all of that?

Today, the benchmark can still be inflated by:
- fluent copy
- lane markers
- contrast phrases
- generic-but-clean operator tone

Phase 6 must make that impossible.

## Scope
Phase 6 will build and expose:
- a stage-aware social evaluation contract
- synthesis-aware benchmark weighting
- per-stage score families
- shipping decision rules based on stage truth and output quality together
- Lab visibility for new score families

Phase 6 will not yet build:
- new style families
- humor scoring
- new type families
- new source types beyond the current matrix
- small-model optimization

## Architectural Rules
1. Do not score missing stages as healthy.
2. Do not let fluent copy hide missing synthesis.
3. Reuse the current evaluator and extend it instead of building a third scoring stack.
4. Reuse the stronger post-generator scoring patterns where they fit.
5. Keep stage scoring separate from shipping decisions, but connected.
6. Evaluation must be evidence-backed and inspectable in Lab.

## Phase 6 Output Objects

### 1. SocialEvaluationPacket
One per article/lane/response run.

It should include at minimum:
- `article_understanding_score`
- `world_context_score`
- `article_stance_score`
- `persona_retrieval_score`
- `belief_relevance_score`
- `experience_relevance_score`
- `johnnie_perspective_score`
- `reaction_brief_score`
- `template_composition_score`
- `voice_truth_score`
- `lane_distinctiveness_score`
- `expression_quality_score`
- `safety_score`
- `benchmark_score`
- `ship_readiness_score`
- `warnings`
- `strengths`
- `evidence`
- `missing_fields`

### 2. EvaluationDecisionTrace
This should show:
- why a lane passed
- why a lane warned
- why a lane failed
- which stages dragged the score down
- whether the failure was due to:
  - missing modeling
  - weak synthesis
  - weak writing
  - safety

### 3. ShippingDecisionPacket
This should summarize:
- `ship`
- `hold`
- `needs_review`
- `blocked_by_missing_stage`

with explicit reasons.

## The Boundary Between Phase 6 And Phase 7
Phase 6 answers:
- how should the current system be judged?

Phase 7 answers:
- how do we expand the system into more response types like agree, contrarian, personal story, and humor?

Phase 6 should stabilize evaluation before the type matrix expands.

## Phase 6 Workstreams

### Workstream A: Evaluation Input Unification
Goal:
- collect all upstream stage packets into one evaluation input

Build:
- article understanding inputs
- persona retrieval inputs
- Johnnie perspective inputs
- reaction brief inputs
- composition trace inputs
- final draft outputs

Primary reuse:
- upstream phase packets
- current Lab context snapshots

Success condition:
- evaluation stops depending on only final text plus thin belief fields

### Workstream B: Article-Side Scoring
Goal:
- score whether the system actually understood the article

Build:
- article understanding score family
- world-context score
- article-stance score
- source-expression preservation score

Primary reuse:
- Phase 1 outputs

Success condition:
- an output cannot benchmark highly if article understanding is missing or weak

### Workstream C: Persona-Side Scoring
Goal:
- score whether the system retrieved and used the right persona evidence

Build:
- persona retrieval score
- belief relevance score
- experience relevance score
- delta-usage score
- diversity score

Primary reuse:
- Phase 2 outputs

Success condition:
- retrieval overuse or irrelevance becomes visible in the benchmark

### Workstream D: Perspective Scoring
Goal:
- score whether the system modeled a real Johnnie reaction

Build:
- agreement quality score
- pushback quality score
- lived-addition score
- what-matters-most score
- perspective coherence score

Primary reuse:
- Phase 3 outputs

Success condition:
- the system cannot pass if it still sounds like lane translation instead of Johnnie reaction

### Workstream E: Reaction-Brief Scoring
Goal:
- score whether the system built a usable synthesis packet before drafting

Build:
- article-view score
- Johnnie-view score
- tension score
- content-angle score
- evidence-to-use score
- brief coherence score

Primary reuse:
- Phase 4 outputs

Success condition:
- the benchmark reflects synthesis strength before any template polish

### Workstream F: Composition Scoring
Goal:
- score whether the draft assembly process is traceable and not over-repetitive

Build:
- template family score
- part selection rationale score
- family diversity score
- normalization trace score
- repetition penalties

Primary reuse:
- Phase 5 outputs

Success condition:
- the evaluator can tell whether repetition is a composition problem

### Workstream G: Final Output Scoring
Goal:
- keep the useful current checks, but make them part of a bigger scoring system

Build:
- voice-truth score
- expression-quality score
- safety score
- lane distinctiveness score
- taste score

Primary reuse:
- `social_evaluation_engine.py`
- taste-scoring patterns from `content_generation.py`
- `taste_examples.md`

Success condition:
- final text still matters, but no longer dominates the benchmark unfairly

### Workstream H: Benchmark Reweighting
Goal:
- make the final benchmark reward real synthesis instead of only polished output

Build:
- weighted benchmark formula using upstream stages
- minimum required stage thresholds
- fail-closed rules for missing critical stages

Success condition:
- a draft cannot score as excellent if core synthesis stages are missing

### Workstream I: Shipping Gate Hardening
Goal:
- move from “looks good” to “stage-valid and score-valid”

Build:
- shipping decision packet
- experiment pass/fail rules
- blocked-by-missing-stage rules

Success condition:
- Lab green means the system is actually trustworthy to ship

### Workstream J: Lab Observability
Goal:
- make the hardened evaluation legible, not just stricter

Build:
- score family panels
- decision trace panel
- shipping decision panel
- top failure-mode summaries

Success condition:
- Lab can show why a result is good or not, not just that it got a number

## The Canonical Phase 6 Stage Board
Phase 6 should make these slices first-class:

1. `evaluation_inputs`
2. `article_understanding_eval`
3. `persona_retrieval_eval`
4. `johnnie_perspective_eval`
5. `reaction_brief_eval`
6. `template_composition_eval`
7. `final_output_eval`
8. `benchmark_decision`
9. `shipping_decision`
10. `evaluation_hardening`

These are the slices Phase 6 is allowed to fully own.
Type-matrix expansion remains a downstream phase.

## Stage Contracts

### Evaluation Inputs
Should know:
- which upstream packets are available to score

Current state:
- fragmented

Missing:
- one unified evaluation input packet

Outputs:
- evaluation input packet

Measure:
- `evaluation_inputs_present`
- `upstream_packet_coverage_score`

### Article Understanding Eval
Should know:
- whether the article-side model is real and adequate

Current state:
- not fully scored in the benchmark

Missing:
- explicit article-side scoring family

Outputs:
- article-side evaluation packet

Measure:
- `article_understanding_score`
- `world_context_score`
- `article_stance_score`

### Persona Retrieval Eval
Should know:
- whether the right persona evidence was retrieved

Current state:
- partially implied by belief/experience fields only

Missing:
- full retrieval scoring

Outputs:
- retrieval evaluation packet

Measure:
- `persona_retrieval_score`
- `belief_relevance_score`
- `experience_relevance_score`
- `retrieval_diversity_score`

### Johnnie Perspective Eval
Should know:
- whether the system modeled a real Johnnie reaction

Current state:
- not scored as a first-class layer

Missing:
- perspective scoring family

Outputs:
- perspective evaluation packet

Measure:
- `johnnie_perspective_score`
- `agreement_quality_score`
- `pushback_quality_score`
- `lived_addition_score`

### Reaction Brief Eval
Should know:
- whether the system synthesized a real pre-draft brief

Current state:
- not scored as a first-class layer

Missing:
- reaction-brief scoring family

Outputs:
- reaction-brief evaluation packet

Measure:
- `reaction_brief_score`
- `article_view_score`
- `johnnie_view_score`
- `content_angle_score`
- `evidence_to_use_score`

### Template Composition Eval
Should know:
- whether composition is traceable and not over-repetitive

Current state:
- not scored in a trace-aware way

Missing:
- composition scoring family

Outputs:
- composition evaluation packet

Measure:
- `template_composition_score`
- `family_diversity_score`
- `normalization_trace_score`

### Final Output Eval
Should know:
- whether the final copy still sounds good and remains safe

Current state:
- this is the current strongest evaluation area

Missing:
- integration with upstream-stage quality

Outputs:
- final-output evaluation packet

Measure:
- `voice_truth_score`
- `expression_quality_score`
- `lane_distinctiveness_score`
- `safety_score`
- `taste_score`

### Benchmark Decision
Should know:
- how to combine stage scores into one benchmark

Current state:
- current benchmark overweights polished output

Missing:
- stage-aware weighting and thresholds

Outputs:
- benchmark decision packet

Measure:
- `benchmark_score`
- `benchmark_confidence`

### Shipping Decision
Should know:
- whether the run is safe and mature enough to ship

Current state:
- too dependent on surface quality

Missing:
- explicit ship/hold decision packet

Outputs:
- shipping decision packet

Measure:
- `ship_readiness_score`
- `blocked_by_missing_stage`
- `needs_review`

### Evaluation Hardening
Should know:
- whether the whole evaluation system is now trustworthy

Current state:
- not yet true

Missing:
- hardened multi-layer evaluation contract

Outputs:
- final evaluation system packet

Measure:
- `evaluation_hardening_score`
- `false_green_penalty`
- `missing_stage_penalty`

## Recommended File Strategy

### Reuse directly
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/lab_experiment_service.py`
- `backend/app/routes/content_generation.py`
- `knowledge/persona/feeze/prompts/taste_examples.md`

### Likely new runtime service
- `backend/app/services/social_stage_evaluation_service.py`

Reason:
- upstream stage scoring should not make `social_evaluation_engine.py` collapse into an unreadable monolith
- stage scoring and final-output scoring should remain related but separable

### Likely callers
- `social_signal_utils.py`
- Lab experiment builders
- future shipping gate logic

## Recommended Implementation Shape

### Step 1: Build a unified evaluation input packet
The evaluator should receive upstream packets and final outputs together.

### Step 2: Score each stage family separately
Do not jump straight to one rolled-up number.

### Step 3: Reweight the benchmark
Use upstream-stage minimums before allowing excellent final scores.

### Step 4: Add shipping decision logic
Green should mean “trustworthy,” not just “sounds decent.”

### Step 5: Surface the decision trace in Lab
The user should be able to see exactly why something passed or failed.

## Lab Rendering Plan
For each probe/article, Lab should render:

### Stage Score Panels
- article understanding
- persona retrieval
- Johnnie perspective
- reaction brief
- template composition
- final output

### Benchmark Panel
- weighted score
- top strengths
- top failures
- thresholds hit or missed

### Shipping Panel
- ship / hold / needs review
- blocked-by-missing-stage flags

### Decision Trace Panel
- why the score landed where it did
- which stage most affected the outcome

### Missing-Stage Panel
- critical slices not yet modeled
- how those missing slices suppressed the score

## Quantification
Phase 6 should introduce these scores:
- `article_understanding_score`
- `persona_retrieval_score`
- `johnnie_perspective_score`
- `reaction_brief_score`
- `template_composition_score`
- `voice_truth_score`
- `taste_score`
- `benchmark_score`
- `ship_readiness_score`
- `evaluation_hardening_score`

Suggested status policy:
- `pass`: score >= 8.5 and no critical upstream stage is missing
- `warn`: score >= 6.5 or one major stage is thin
- `fail`: score < 6.5 or critical stages are materially weak
- `missing`: the slice is not yet modeled

Critical fail-closed rule:
- if `article_stance`, `persona_retrieval`, `johnnie_perspective`, `reaction_brief`, or `template_composition` is still `missing`, the evaluator must not let the run present as fully green

## Qualification
Every score must include a reason.

Examples:
- `article_understanding_eval_warn`: "The final copy is usable, but the article stance model is still missing, so the evaluator cannot fully trust the interpretation."
- `persona_retrieval_eval_fail`: "The system used a lane-valid belief, but no article-specific story or delta was retrieved."
- `reaction_brief_eval_missing`: "The system still drafts without a real synthesis brief, so the benchmark is capped."
- `benchmark_decision_warn`: "The copy is strong on expression, but the upstream synthesis stack is still incomplete."

## Exit Criteria
Phase 6 is only complete when:
1. the benchmark cannot go green while critical synthesis stages are missing
2. Lab shows score families for upstream stages and final output together
3. shipping decisions are stage-aware and evidence-backed
4. the evaluator can distinguish:
   - missing modeling
   - weak synthesis
   - weak composition
   - weak final copy
5. a high benchmark actually correlates with authentic, article-specific Johnnie output

## Non-Goals
Do not spend Phase 6 time on:
- humor scoring
- new type families
- prompt-only score inflation
- expanding the source matrix
- small-model cost tuning

Those remain downstream of evaluation correctness.

## Risks

### Risk: Score inflation through polished copy
Mitigation:
- cap benchmark strength when critical upstream stages are missing

### Risk: Evaluator bloat
Mitigation:
- keep stage-family scoring modular

### Risk: False precision
Mitigation:
- keep pass / warn / fail / missing visible alongside numbers

### Risk: Confusing stage quality with final copy quality
Mitigation:
- score them separately before rolling up

## Handoff To Phase 7
Phase 7 should consume:
- hardened benchmark logic
- stage-aware shipping rules
- trace-aware evaluation infrastructure

Phase 7 should not have to wonder whether the benchmark can be trusted.
It should expand the type matrix on top of a stable evaluation foundation.

That is the Phase 6 contract.

Phase 7 deep-dive:
- `workspaces/linkedin-content-os/docs/type_matrix_expansion_phase7_implementation_plan.md`

## Small-Model Note
`gpt-4o-mini` compatibility remains important, but it is not the Phase 6 success condition.
Phase 6 succeeds when the evaluation system becomes strict enough that green actually means trustworthy.
Model-cost optimization remains downstream of correctness.

## Related Files
- `SOPs/social_persona_synthesis_roadmap_sop.md`
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/type_matrix_expansion_phase7_implementation_plan.md`
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/lab_experiment_service.py`
- `backend/app/routes/content_generation.py`
- `knowledge/persona/feeze/prompts/taste_examples.md`
