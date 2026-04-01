# Phase 4: Reaction Brief Implementation Plan

## Purpose
This document is the canonical implementation plan for Phase 4 of the social persona synthesis roadmap:
- package article understanding, persona retrieval, and Johnnie perspective into a usable synthesis brief
- stop drafting directly from thin context fields
- create a compact runtime object that lane builders can trust
- make the pre-draft synthesis visible in Lab before comment/repost rendering

This document is not a standalone roadmap.
It is the Phase 4 deep-dive for:
- `SOPs/social_persona_synthesis_roadmap_sop.md`

It assumes the upstream phases exist:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`

## Why Phase 4 Comes After Johnnie Perspective
Phase 1 explains the article.
Phase 2 retrieves the right persona evidence.
Phase 3 decides what Johnnie actually thinks.

Phase 4 answers the next question:
- how do we package all of that into a brief that writing code can actually use?

Without that bridge, the system falls back to the current pattern:
- thin generation context
- one belief
- one experience
- one stance
- one source takeaway
- template rendering

That is not enough.

The social path needs the same kind of structural advantage the stronger original-post generator already has:
- a small explicit brief object
- visible synthesis inputs
- clear selected angle
- evidence discipline before writing

Phase 4 is the stage that turns:
- understanding

into:
- a writing-ready synthesis packet

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

Phase 4 only covers `4. reaction brief`.

It must leave the system in a state where the drafting layer can read a single synthesis object instead of inferring intent from:
- stance alone
- belief summary alone
- experience summary alone
- source takeaway alone

## Integrated Thought Clarification For Phase 4
Every Phase 4 slice must explicitly answer:

1. `What should this slice know?`
2. `What does the system compute today?`
3. `What is missing?`
4. `Why does that missing logic matter downstream?`
5. `What artifact should this slice output?`
6. `How will Lab measure pass / warn / fail / missing?`
7. `What existing contract must this slice reuse instead of replacing?`

This is mandatory for all reaction-brief work in this phase.

## Current Implementation Read

### What already exists and should be reused
The stronger original-post engine already has a brief pattern:
- `ContentOptionBrief` in `backend/app/routes/content_generation.py`
- `plan_content_option_briefs(...)`
- structured fields like:
  - `framing_mode`
  - `primary_claim`
  - `proof_packet`
  - `story_beat`

That system proves the repo already knows how to use:
- compact structured briefs
- explicit pre-draft planning
- brief-aware evaluation

The current social/article path already has some of the pieces a reaction brief would need:
- `build_generation_context(...)` in `backend/app/services/social_signal_utils.py`
- source takeaway and structure handling
- belief/experience/stance outputs from `social_belief_engine.py`
- technique bundles from `social_technique_engine.py`

### What is actually happening today
The social path currently builds this thin context:
- `title`
- `core_line`
- `supporting_line`
- `summary`
- `source_takeaway`
- `belief_summary`
- `experience_summary`
- `stance`
- `bridge_line`

That is not a synthesis brief.
It is only a lightweight drafting context.

Lab is already correct about the missing layer:
- `reaction_brief = missing`

Current Lab definition says the system is missing:
- `article_view`
- `johnnie_view`
- `tension`
- `content_angle`

That is the Phase 4 gap.

## The Actual Problem Phase 4 Must Solve
The system can eventually know:
- what the article means
- what Johnnie believes
- which evidence matters
- what Johnnie agrees with or pushes back on

But if it does not materialize that into one compact brief, the drafting layer still has to improvise.

That causes:
- repeated output shapes
- flattened synthesis
- generic lane rendering
- weak linkage between perspective and copy

Phase 4 must solve that by introducing one compact pre-draft object that says:
- what the article is saying
- how Johnnie sees it
- where the tension is
- what angle to write from
- what evidence is allowed
- what should be emphasized
- what should not be overstated

That is the missing bridge between perspective and writing.

## Scope
Phase 4 will build and expose:
- `ReactionBriefPacket`
- article-view synthesis
- Johnnie-view synthesis
- tension construction
- content-angle selection
- evidence-to-use selection
- stance rationale
- draft guidance inputs
- Lab visibility for all of the above

Phase 4 will not yet build:
- template-family tracing
- repeated opener/closer diagnostics
- humor
- style-family expansion
- final draft evaluation overhaul
- small-model optimization

## Architectural Rules
1. Do not invent a second drafting system.
2. Reuse the stronger repo pattern of structured briefs.
3. Do not let the reaction brief become final copy.
4. Do not skip Johnnie perspective and jump straight from retrieval to writing.
5. Do not stuff too many writing tricks into the brief.
6. Keep the brief compact enough for lane builders and later evals to inspect.
7. Use the brief to constrain writing, not to replace the writing layer.

## Phase 4 Output Objects

### 1. ReactionBriefPacket
One per article/lane run.

It should include at minimum:
- `article_view`
- `johnnie_view`
- `tension`
- `content_angle`
- `evidence_to_use`
- `stance_rationale`
- `takeaway_to_preserve`
- `technique_guidance`
- `audience_posture`
- `role_posture`
- `do_not_overstate`
- `bridge_intent`
- `priority_signal`
- `brief_confidence`
- `selection_rationale`
- `evidence`
- `missing_fields`

### 2. BriefTrace
Lab must be able to show:
- why each brief field was selected
- what upstream evidence supported it
- what was left out
- what conflicts were resolved

### 3. DraftGuidancePacket
This should be a compact downstream view for the drafting layer.

It may include:
- `opening_intent`
- `main_turn`
- `supporting_proof`
- `optional_story`
- `close_intent`
- `allowed_techniques`

But it should remain derived from the `ReactionBriefPacket`, not a separate planning system.

## The Boundary Between Phase 4 And Phase 5
Phase 4 answers:
- what is the correct synthesis packet for writing?

Phase 5 answers:
- how does the drafting layer assemble sentences and template shapes from that packet?

Phase 4 should produce:
- writing guidance

Phase 5 should produce:
- assembly trace

## Phase 4 Workstreams

### Workstream A: Brief Input Assembly
Goal:
- assemble all upstream artifacts into one brief input packet

Build:
- article understanding inputs
- persona retrieval inputs
- Johnnie perspective inputs
- source takeaway inputs
- technique inputs

Primary reuse:
- Phase 1 `ArticleUnderstanding`
- Phase 2 `PersonaRetrievalPacket`
- Phase 3 `JohnniePerspectivePacket`
- `select_source_takeaway(...)`
- `social_technique_engine.py`

Success condition:
- Phase 4 starts from explicit upstream packets, not scattered context fields

### Workstream B: Article View Synthesis
Goal:
- express what the article is effectively saying in one usable packet

Build:
- `article_view`
- article-view rationale

Primary reuse:
- article claim extraction
- article stance
- world stakes
- source takeaway

Success condition:
- the brief can summarize the article position without needing the full raw article again

### Workstream C: Johnnie View Synthesis
Goal:
- express Johnnie's reaction in a compact, writeable form

Build:
- `johnnie_view`
- Johnnie-view rationale

Primary reuse:
- Phase 3 perspective outputs

Success condition:
- the brief can summarize Johnnie's side without re-inferring it during drafting

### Workstream D: Tension Construction
Goal:
- define where the energy in the response comes from

Build:
- `tension`
- tension type
- tension severity

Possible tension families:
- `agreement_plus_extension`
- `agreement_with_missing_piece`
- `qualified_disagreement`
- `translation_into_real_work`
- `lived-proof reframe`
- `implementation warning`

Success condition:
- the system can explain why the response is worth making at all

### Workstream E: Content Angle Selection
Goal:
- select the exact angle the draft should take

Build:
- `content_angle`
- primary angle rationale
- rejected angle summaries

Possible angle families:
- operator lesson
- leadership lesson
- adoption lesson
- trust lesson
- execution warning
- builder reframe
- education mission link

Success condition:
- the draft has a clear center of gravity

### Workstream F: Evidence Selection
Goal:
- decide what evidence the writer is allowed to use

Build:
- `evidence_to_use`
- evidence priority
- evidence exclusions

Primary reuse:
- Phase 2 retrieval packet
- Phase 3 lived-addition and skepticism

Success condition:
- the writer does not have to guess which proof or anecdote is approved

### Workstream G: Stance Rationale
Goal:
- explain why the response stance is what it is

Build:
- `stance_rationale`
- relationship between article stance and Johnnie stance

Primary reuse:
- article stance
- Johnnie perspective

Success condition:
- stance is no longer just a label; it is explained

### Workstream H: Draft Guidance Assembly
Goal:
- turn the reaction brief into compact drafting guidance

Build:
- opening intent
- bridge intent
- close intent
- technique guidance
- overstatement guardrails

Primary reuse:
- technique bundle
- audience posture
- role posture
- current lane builders

Success condition:
- the lane builders can draft from a real brief instead of a thin context map

### Workstream I: Brief Coherence
Goal:
- ensure the brief does not contradict itself

Build:
- conflict checks
- empty-angle checks
- evidence/angle mismatch checks
- tension/stance mismatch checks

Success condition:
- the system does not produce vague or contradictory reaction briefs

### Workstream J: Lab Observability
Goal:
- expose the reaction brief clearly before any draft is generated

Build:
- article view panel
- Johnnie view panel
- tension panel
- content angle panel
- evidence panel
- stance rationale panel
- missing-field panel

Success condition:
- `reaction_brief` is no longer `missing`

## The Canonical Phase 4 Stage Board
Phase 4 should make these slices first-class:

1. `brief_inputs`
2. `article_view`
3. `johnnie_view`
4. `tension`
5. `content_angle`
6. `evidence_to_use`
7. `stance_rationale`
8. `draft_guidance`
9. `brief_coherence`
10. `reaction_brief`

These are the slices Phase 4 is allowed to fully own.
`template_composition` remains a downstream phase.

## Stage Contracts

### Brief Inputs
Should know:
- which upstream artifacts are available for synthesis

Current state:
- scattered across social context fields

Missing:
- normalized brief input object

Outputs:
- brief input packet

Measure:
- `brief_inputs_present`
- `article_inputs_present`
- `persona_inputs_present`
- `perspective_inputs_present`
- `technique_inputs_present`

### Article View
Should know:
- what the article is effectively saying for this response

Current state:
- implicit across core line, summary, and source takeaway

Missing:
- explicit article-view field

Outputs:
- article-view packet

Measure:
- `article_view_present`
- `article_view_score`
- `article_view_specificity_score`

### Johnnie View
Should know:
- what Johnnie is effectively saying back to the article

Current state:
- implicit across stance, belief, and experience

Missing:
- explicit Johnnie-view field

Outputs:
- Johnnie-view packet

Measure:
- `johnnie_view_present`
- `johnnie_view_score`
- `johnnie_view_specificity_score`

### Tension
Should know:
- where the response gets its energy

Current state:
- partly implied by stance and contrast phrases

Missing:
- explicit tension object

Outputs:
- tension packet

Measure:
- `tension_present`
- `tension_relevance_score`
- `tension_strength_score`

### Content Angle
Should know:
- which angle the response should choose

Current state:
- not first-class

Missing:
- explicit content-angle object

Outputs:
- angle packet

Measure:
- `content_angle_present`
- `content_angle_score`
- `angle_clarity_score`

### Evidence To Use
Should know:
- which evidence should actually appear downstream

Current state:
- implicit across belief/experience/source_takeaway

Missing:
- explicit evidence selection packet

Outputs:
- evidence-selection packet

Measure:
- `evidence_to_use_present`
- `evidence_relevance_score`
- `evidence_mix_score`

### Stance Rationale
Should know:
- why the response stance is justified

Current state:
- mostly hidden in heuristic stance rules

Missing:
- explicit stance rationale

Outputs:
- stance-rationale packet

Measure:
- `stance_rationale_present`
- `stance_rationale_score`

### Draft Guidance
Should know:
- how the writer should approach the draft without writing it yet

Current state:
- current context map is too thin

Missing:
- explicit guidance packet

Outputs:
- draft-guidance packet

Measure:
- `draft_guidance_present`
- `draft_guidance_score`

### Brief Coherence
Should know:
- whether the whole brief hangs together

Current state:
- not modeled

Missing:
- coherence validation

Outputs:
- coherence packet

Measure:
- `brief_coherence_score`
- `brief_conflict_penalty`
- `brief_empty_field_penalty`

### Reaction Brief
Should know:
- whether the system has materialized a usable synthesis brief before drafting

Current state:
- missing as a first-class object

Missing:
- `ReactionBriefPacket`

Outputs:
- full brief packet

Measure:
- `reaction_brief_score`
- `article_view_present`
- `johnnie_view_present`
- `tension_present`
- `content_angle_present`
- `evidence_to_use_present`

## Recommended File Strategy

### Reuse directly
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_technique_engine.py`
- `backend/app/services/lab_experiment_service.py`
- `backend/app/routes/content_generation.py`

### Likely new runtime service
- `backend/app/services/social_reaction_brief_service.py`

Reason:
- the social path needs a stable synthesis boundary before drafting
- the original-post engine already proves structured briefs are valuable
- the reaction brief should be reusable across comment, repost, post seed, and later type-matrix work

### Likely callers
- `social_signal_utils.py`
- Lab experiment builders
- future Phase 5 draft-composition tracing

## Recommended Implementation Shape

### Step 1: Build the brief input packet
Inputs should include:
- article understanding fields
- persona retrieval fields
- Johnnie perspective fields
- source takeaway packet
- technique bundle

### Step 2: Create article view and Johnnie view separately
Do not compress them into one hybrid summary too early.

### Step 3: Derive tension and content angle
The brief should explain why the response exists and what lane of meaning it chooses.

### Step 4: Select evidence and guidance
The brief should tell the drafting layer what proof/story/support is actually usable.

### Step 5: Replace direct social context dependence
`build_generation_context(...)` should eventually consume the reaction brief rather than assembling meaning from scattered fields itself.

## Lab Rendering Plan
For each probe/article, Lab should render:

### Brief Inputs
- article-understanding inputs
- persona-retrieval inputs
- Johnnie-perspective inputs
- source takeaway
- technique bundle

### Article View Panel
- article view
- supporting rationale

### Johnnie View Panel
- Johnnie view
- supporting rationale

### Tension And Angle Panel
- tension
- content angle
- rejected angle summaries

### Evidence Panel
- evidence to use
- evidence excluded

### Guidance Panel
- opening intent
- bridge intent
- close intent
- do-not-overstate guidance

### Stage Diagnostics
- pass / warn / fail / missing
- score
- reason
- evidence
- missing fields

## Quantification
Phase 4 should introduce these scores:
- `article_view_score`
- `johnnie_view_score`
- `tension_strength_score`
- `content_angle_score`
- `evidence_to_use_score`
- `stance_rationale_score`
- `draft_guidance_score`
- `brief_coherence_score`
- `reaction_brief_rollup_score`

Suggested status policy:
- `pass`: score >= 8.5 and the brief is complete and coherent
- `warn`: score >= 6.5 or one major field is thin
- `fail`: score < 6.5 or the synthesis is materially weak
- `missing`: the slice is not yet modeled

## Qualification
Every score must include a reason.

Examples:
- `article_view_warn`: "The brief has a usable article summary, but it is too close to the raw source takeaway and does not show the article's larger claim clearly."
- `johnnie_view_missing`: "The system is not yet materializing a compact Johnnie-side synthesis for the draft."
- `content_angle_fail`: "The brief did not choose a clear angle, so the drafting layer would still have to improvise."
- `evidence_to_use_warn`: "Relevant evidence was retrieved, but the brief did not decide which proof or anecdote should actually be used."

## Exit Criteria
Phase 4 is only complete when:
1. `reaction_brief` is no longer `missing` in Lab
2. the system can show article view, Johnnie view, tension, content angle, and evidence before drafting
3. the lane builders can consume a brief packet instead of thin context only
4. brief coherence is validated
5. Phase 5 can trace drafting from the brief instead of from implicit heuristics

## Non-Goals
Do not spend Phase 4 time on:
- humor
- opener banks
- template-family expansion
- final sentence assembly tracing
- benchmark inflation by prompt tricks
- small-model cost tuning

Those remain downstream of brief correctness.

## Risks

### Risk: Turning the brief into final copy
Mitigation:
- keep the brief structural and compact

### Risk: Duplicating the original-post planning system blindly
Mitigation:
- reuse the brief pattern, not the exact post-option planner shape

### Risk: Overstuffing the brief
Mitigation:
- keep only the fields that constrain writing meaningfully

### Risk: Losing article specificity
Mitigation:
- require article-view evidence and stance rationale in the brief

### Risk: Losing Johnnie specificity
Mitigation:
- require Johnnie-view evidence and perspective rationale in the brief

## Handoff To Phase 5
Phase 5 should consume:
- `ReactionBriefPacket`
- draft guidance
- angle selection
- evidence selection
- stance rationale

Phase 5 should not have to decide what the response is about.
It should decide how to assemble the draft and how to trace that assembly.

That is the Phase 4 contract.

Phase 5 deep-dive:
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`

## Small-Model Note
`gpt-4o-mini` compatibility remains important, but it is not the Phase 4 success condition.
Phase 4 succeeds when the system materializes a real synthesis brief before drafting.
Model-cost optimization remains downstream of correctness.

## Related Files
- `SOPs/social_persona_synthesis_roadmap_sop.md`
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_technique_engine.py`
- `backend/app/services/lab_experiment_service.py`
- `backend/app/routes/content_generation.py`
