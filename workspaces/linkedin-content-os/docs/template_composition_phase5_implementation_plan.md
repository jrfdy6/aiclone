# Phase 5: Template Composition Implementation Plan

## Purpose
This document is the canonical implementation plan for Phase 5 of the social persona synthesis roadmap:
- make the draft assembly layer explicit and traceable
- compose comment/repost copy from a real reaction brief instead of thin context alone
- track which composition families and part selections were used
- reduce repetition by measuring composition choices instead of guessing

This document is not a standalone roadmap.
It is the Phase 5 deep-dive for:
- `SOPs/social_persona_synthesis_roadmap_sop.md`

It assumes the upstream phases exist:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`

## Why Phase 5 Comes After Reaction Brief
Phase 4 should tell the system:
- what the article view is
- what Johnnie view is
- where the tension is
- what the content angle is
- what evidence is allowed

Phase 5 answers the next question:
- how does the system physically assemble the draft from that brief?

Right now the social path already has:
- openers
- contrast lines
- takeaways
- bridges
- lane-specific mains
- closers
- template ordering

But it does not expose that composition as a real trace.

That means the system can still:
- repeat opener families without visibility
- repeat close families without visibility
- reshuffle the same parts without knowing it
- pass clean draft checks while still feeling samey

Phase 5 exists to make composition explicit.

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

Phase 5 only covers `5. template composition trace`.

It must leave the system in a state where:
- the drafting layer can explain what it assembled
- Lab can inspect the selected part families
- repetition can be measured at the composition layer

## Integrated Thought Clarification For Phase 5
Every Phase 5 slice must explicitly answer:

1. `What should this slice know?`
2. `What does the system compute today?`
3. `What is missing?`
4. `Why does that missing logic matter downstream?`
5. `What artifact should this slice output?`
6. `How will Lab measure pass / warn / fail / missing?`
7. `What existing contract must this slice reuse instead of replacing?`

This is mandatory for all composition-trace work in this phase.

## Current Implementation Read

### What already exists and should be reused
The current social assembly path in `backend/app/services/social_signal_utils.py` already has:
- `comment_open(...)`
- `repost_open(...)`
- `bridge_line(...)`
- `stance_contrast_line(...)`
- `response_templates(...)`
- `compose_response(...)`
- lane-specific builders like:
  - `build_admissions_comment(...)`
  - `build_entrepreneurship_comment(...)`
  - `build_ai_comment(...)`
  - `build_ops_pm_comment(...)`
- top-level variant assembly through `build_variants(...)`

The current evaluation and Lab surfaces already know composition is missing:
- `template_composition` exists as a Lab stage
- `template_trace_missing` is a known failure
- Lab currently says the system composes parts but does not trace the chosen path at the part level

### What is actually happening today
Today the composition layer does real work, but most of it is opaque:
- `response_templates(...)` chooses the order shape
- `pick_template(...)` chooses a template variant
- `pick_option(...)` chooses open/main/close fragments
- `compose_response(...)` joins selected parts into final copy
- `normalize_voice(...)` cleans the final output

But the system does not currently emit:
- template family ids
- opener family ids
- close family ids
- chosen part list
- rejected part list
- repetition counters
- normalization deltas

That is why Lab correctly marks:
- `template_composition = missing`

## The Actual Problem Phase 5 Must Solve
The drafts are not failing only because ideas are weak.
They are also failing because the composition layer is unobserved.

When the renderer is opaque:
- repeated output families feel mysterious
- it is hard to know whether the problem is the brief or the template
- it is hard to know whether repetition comes from:
  - reaction brief quality
  - opener bank choice
  - template ordering
  - normalization cleanup

Phase 5 must solve that by turning composition into a first-class trace.

## Scope
Phase 5 will build and expose:
- `TemplateCompositionTrace`
- selected template-family ids
- selected opener/closer families
- selected part ordering
- part-level composition evidence
- normalization trace
- repetition tracking at the composition layer
- Lab visibility for all of the above

Phase 5 will not yet build:
- humor families
- new style families
- new opener-bank explosion
- new type-matrix categories
- broad eval rewrites
- small-model optimization

## Architectural Rules
1. Do not replace the entire lane-builder system in Phase 5.
2. Reuse the existing composition primitives and expose them.
3. Keep composition trace separate from reaction-brief synthesis.
4. Do not use prompt tricks to hide composition problems.
5. Normalize after composition, but trace both pre- and post-normalization where useful.
6. Repetition control should be measurable, not just intuitive.

## Phase 5 Output Objects

### 1. TemplateCompositionTrace
One per article/lane/response kind.

It should include at minimum:
- `response_kind`
- `template_family`
- `template_slots`
- `selected_open_family`
- `selected_takeaway_family`
- `selected_bridge_family`
- `selected_contrast_family`
- `selected_main_family`
- `selected_close_family`
- `selected_parts`
- `part_order`
- `omitted_parts`
- `part_selection_rationale`
- `pre_normalization_text`
- `post_normalization_text`
- `normalization_actions`
- `repetition_flags`
- `missing_fields`

### 2. CompositionFamilyTrace
This should summarize reusable family ids, for example:
- opener family
- close family
- template-order family
- main-line family

### 3. RepetitionControlPacket
This should summarize:
- recent family reuse
- overuse penalties
- family diversity score
- lane-local repetition flags

## The Boundary Between Phase 5 And Phase 6
Phase 5 answers:
- how did the system assemble this draft?

Phase 6 answers:
- how should we score that assembly and synthesis quality more rigorously?

Phase 5 should produce:
- composition trace

Phase 6 should produce:
- stronger scoring and evaluation contracts

## Phase 5 Workstreams

### Workstream A: Composition Input Assembly
Goal:
- feed the renderer from the reaction brief, not from scattered thin fields

Build:
- composition input packet derived from the reaction brief
- mapped slots for:
  - open
  - contrast
  - takeaway
  - bridge
  - main
  - close

Primary reuse:
- Phase 4 `ReactionBriefPacket`
- existing lane builders

Success condition:
- the renderer can explain which parts came from the brief

### Workstream B: Template Family Identification
Goal:
- label template shapes as reusable composition families

Build:
- `template_family`
- `template_slots`
- slot-order identifiers

Primary reuse:
- `response_templates(...)`
- `pick_template(...)`

Success condition:
- Lab can tell which template shape was selected

### Workstream C: Part Family Identification
Goal:
- identify which opener/main/close family each draft used

Build:
- family ids for:
  - open
  - contrast
  - takeaway
  - bridge
  - main
  - close

Primary reuse:
- `pick_option(...)`
- lane-specific part banks

Success condition:
- opener and close reuse become measurable

### Workstream D: Part Selection Trace
Goal:
- explain which parts were chosen and why

Build:
- selected-part trace
- omitted-part trace
- part-selection rationale

Primary reuse:
- context keys already used by `pick_option(...)`
- reaction-brief guidance

Success condition:
- composition is inspectable at the part level

### Workstream E: Pre/Post Normalization Trace
Goal:
- show what changed during voice cleanup

Build:
- pre-normalization text
- post-normalization text
- normalization action list

Primary reuse:
- `normalize_voice(...)`

Success condition:
- Lab can tell whether cleanup improved or flattened the draft

### Workstream F: Repetition Tracking
Goal:
- measure repetition in terms of actual composition families

Build:
- family reuse counters
- opener overuse flags
- close overuse flags
- lane-local repetition flags

Success condition:
- repetition is measured from composition data, not only from impression

### Workstream G: Comment/Repost Composition Audit
Goal:
- trace both response kinds separately

Build:
- comment composition trace
- repost composition trace
- short-comment trace where applicable

Success condition:
- the system can explain composition differences by response mode

### Workstream H: Lab Observability
Goal:
- expose full composition traces before evaluation decisions hide the issue

Build:
- template trace panel
- family id panel
- pre/post normalization panel
- repetition panel
- part order panel

Success condition:
- `template_composition` is no longer `missing`

## The Canonical Phase 5 Stage Board
Phase 5 should make these slices first-class:

1. `composition_inputs`
2. `template_family`
3. `part_family_selection`
4. `part_selection_trace`
5. `part_order`
6. `normalization_trace`
7. `repetition_control`
8. `comment_composition`
9. `repost_composition`
10. `template_composition`

These are the slices Phase 5 is allowed to fully own.
`evaluation_hardening` remains a downstream phase.

## Stage Contracts

### Composition Inputs
Should know:
- which reaction-brief fields are driving composition

Current state:
- implicit in the context dict

Missing:
- explicit composition input packet

Outputs:
- composition input packet

Measure:
- `composition_inputs_present`
- `brief_to_slot_mapping_score`

### Template Family
Should know:
- which slot-order pattern was selected

Current state:
- selected implicitly by `response_templates(...)`

Missing:
- explicit family id and slot trace

Outputs:
- template family packet

Measure:
- `template_family_present`
- `template_family_score`

### Part Family Selection
Should know:
- which open/main/close family won

Current state:
- hidden inside `pick_option(...)`

Missing:
- explicit family ids

Outputs:
- part-family packet

Measure:
- `open_family_present`
- `close_family_present`
- `main_family_present`

### Part Selection Trace
Should know:
- which parts were chosen and which were omitted

Current state:
- not modeled

Missing:
- part selection trace

Outputs:
- part trace packet

Measure:
- `part_selection_trace_present`
- `part_selection_rationale_score`

### Part Order
Should know:
- the final part sequence

Current state:
- implicit in `compose_response(...)`

Missing:
- explicit order trace

Outputs:
- part-order packet

Measure:
- `part_order_present`
- `part_order_score`

### Normalization Trace
Should know:
- what changed between raw composition and final normalized text

Current state:
- hidden

Missing:
- normalization actions trace

Outputs:
- normalization trace

Measure:
- `normalization_trace_present`
- `cleanup_delta_score`

### Repetition Control
Should know:
- whether composition families are being overused

Current state:
- not modeled explicitly

Missing:
- family-level repetition trace

Outputs:
- repetition-control packet

Measure:
- `family_diversity_score`
- `opener_overuse_penalty`
- `closer_overuse_penalty`

### Comment Composition
Should know:
- how the comment was assembled

Current state:
- only visible as final text

Missing:
- comment-specific composition trace

Outputs:
- comment composition trace

Measure:
- `comment_composition_score`

### Repost Composition
Should know:
- how the repost was assembled

Current state:
- only visible as final text

Missing:
- repost-specific composition trace

Outputs:
- repost composition trace

Measure:
- `repost_composition_score`

### Template Composition
Should know:
- whether the whole composition process is visible and coherent

Current state:
- missing as a first-class trace object

Missing:
- `TemplateCompositionTrace`

Outputs:
- full composition trace

Measure:
- `template_composition_score`
- `template_trace_present`
- `template_family_present`
- `selected_close_family_present`

## Recommended File Strategy

### Reuse directly
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/lab_experiment_service.py`

### Likely new runtime service
- `backend/app/services/social_template_composition_service.py`

Reason:
- tracing the renderer should not make `social_signal_utils.py` unmanageable
- composition deserves its own runtime boundary
- Lab and future evaluations should consume the trace from one place

### Likely callers
- `social_signal_utils.py`
- Lab experiment builders
- future evaluation hardening

## Recommended Implementation Shape

### Step 1: Derive composition inputs from the reaction brief
The drafting layer should stop pretending the brief does not exist.

### Step 2: Trace template-family and part-family choices
Do not just output final strings.

### Step 3: Trace pre/post normalization
This is necessary to understand whether cleanup is helping or flattening.

### Step 4: Add repetition-control metadata
Track actual composition families across runs and lanes.

### Step 5: Feed trace into Lab and evaluation
The composition layer should become observable, not magical.

## Lab Rendering Plan
For each probe/article, Lab should render:

### Composition Inputs
- reaction-brief inputs
- slot mappings

### Template Family Panel
- chosen template family
- slot order

### Part Family Panel
- opener family
- main family
- close family

### Part Trace Panel
- selected parts
- omitted parts
- rationale

### Normalization Panel
- pre-normalization text
- post-normalization text
- cleanup actions

### Repetition Panel
- family reuse counts
- repeated opener flags
- repeated close flags

### Stage Diagnostics
- pass / warn / fail / missing
- score
- reason
- evidence
- missing fields

## Quantification
Phase 5 should introduce these scores:
- `template_family_score`
- `part_selection_rationale_score`
- `part_order_score`
- `cleanup_delta_score`
- `family_diversity_score`
- `comment_composition_score`
- `repost_composition_score`
- `template_composition_rollup_score`

Suggested status policy:
- `pass`: score >= 8.5 and trace coverage is complete
- `warn`: score >= 6.5 or one major trace field is thin
- `fail`: score < 6.5 or composition is materially opaque or repetitive
- `missing`: the slice is not yet modeled

## Qualification
Every score must include a reason.

Examples:
- `template_family_missing`: "The renderer selected a template shape, but Lab cannot identify which family was used."
- `part_family_selection_warn`: "The draft assembled successfully, but opener and close families are still repeated too often across lanes."
- `normalization_trace_missing`: "The final text was normalized, but cleanup actions were not captured."
- `template_composition_fail`: "The system rendered final copy without a usable composition trace."

## Exit Criteria
Phase 5 is only complete when:
1. `template_composition` is no longer `missing` in Lab
2. the system can show template family, part families, part order, and normalization trace
3. opener and close repetition are measurable from family data
4. the drafting layer can be debugged without reading only final copy
5. Phase 6 can score composition quality from real trace data

## Non-Goals
Do not spend Phase 5 time on:
- humor
- adding more style families
- new opener-bank growth
- broad eval redesign
- type-matrix expansion
- small-model cost tuning

Those remain downstream of trace correctness.

## Risks

### Risk: Rebuilding the renderer from scratch
Mitigation:
- expose and trace the current renderer first

### Risk: Trace bloat
Mitigation:
- keep the trace compact and field-driven

### Risk: Confusing brief problems with composition problems
Mitigation:
- keep Phase 4 and Phase 5 boundaries explicit

### Risk: Over-optimizing on family ids too early
Mitigation:
- start with observability, then tune family diversity later

## Handoff To Phase 6
Phase 6 should consume:
- `TemplateCompositionTrace`
- family diversity metrics
- normalization trace
- comment/repost composition traces

Phase 6 should not have to guess how the draft was assembled.
It should score that assembly more rigorously.

That is the Phase 5 contract.

Phase 6 deep-dive:
- `workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md`

## Small-Model Note
`gpt-4o-mini` compatibility remains important, but it is not the Phase 5 success condition.
Phase 5 succeeds when the renderer becomes observable and debuggable.
Model-cost optimization remains downstream of correctness.

## Related Files
- `SOPs/social_persona_synthesis_roadmap_sop.md`
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/lab_experiment_service.py`
