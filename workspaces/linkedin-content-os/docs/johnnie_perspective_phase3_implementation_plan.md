# Phase 3: Johnnie Perspective Implementation Plan

## Purpose
This document is the canonical implementation plan for Phase 3 of the social persona synthesis roadmap:
- turn article understanding plus persona retrieval into a real Johnnie reaction object
- stop treating stance as a shallow lane label
- explicitly model what Johnnie agrees with, questions, rejects, adds, and prioritizes
- make that perspective visible in Lab before reaction-brief synthesis and drafting

This document is not a standalone roadmap.
It is the Phase 3 deep-dive for:
- `SOPs/social_persona_synthesis_roadmap_sop.md`

It assumes the upstream phases exist:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`

## Why Phase 3 Comes After Retrieval
Phase 2 retrieves the right evidence.
Phase 3 decides what that evidence means for Johnnie's actual reaction.

That distinction matters.

Retrieval can tell us:
- which claim is relevant
- which story is relevant
- which initiative is relevant
- which approved delta is relevant

But retrieval alone does not answer:
- does Johnnie agree with this article?
- where would he push back?
- what would he say is missing?
- what part of the article matters most to him?
- what lived experience changes the interpretation?

Right now the social path mostly skips that layer.
It goes from:
- article signal
- plus one belief
- plus one experience
- plus a stance family

straight into drafting.

That is why the system sounds like:
- lane translation
- structured reframing
- reusable operator commentary

instead of:
- Johnnie reacting to this exact article through his own worldview

Phase 3 exists to create that missing middle layer.

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

Phase 3 only covers `3. Johnnie perspective`.

It must leave the system in a state where Phase 4 can consume a perspective object instead of having to infer Johnnie's reaction from:
- a single stance label
- a generic belief line
- a generic experience line

## Integrated Thought Clarification For Phase 3
Every Phase 3 slice must explicitly answer:

1. `What should this slice know?`
2. `What does the system compute today?`
3. `What is missing?`
4. `Why does that missing logic matter downstream?`
5. `What artifact should this slice output?`
6. `How will Lab measure pass / warn / fail / missing?`
7. `What existing contract must this slice reuse instead of replacing?`

This is mandatory for all perspective-modeling work in this phase.

## Current Implementation Read

### What already exists and should be reused
The current social path already has fragments of perspective-adjacent logic:

- `backend/app/services/social_belief_engine.py`
  - `_choose_belief(...)`
  - `_choose_experience(...)`
  - `_choose_stance(...)`
  - `_build_stance_language(...)`
  - `assess_signal(...)`

- `backend/app/services/social_signal_utils.py`
  - `build_generation_context(...)`
  - lane builders that consume:
    - `belief_summary`
    - `experience_summary`
    - `stance`
    - `bridge_line`

- persona worldview sources:
  - `knowledge/persona/feeze/identity/claims.md`
  - `knowledge/persona/feeze/identity/philosophy.md`
  - `knowledge/persona/feeze/identity/decision_principles.md`
  - `knowledge/persona/feeze/identity/audience_communication.md`
  - `knowledge/persona/feeze/history/story_bank.md`
  - `knowledge/persona/feeze/history/initiatives.md`

### What is actually happening today
The current path does not produce a first-class Johnnie reaction object.

What it does instead:
- picks a belief mostly by lane/profile
- picks an experience mostly by lane/profile
- picks a stance mostly by lane/profile and a few text rules
- turns that into generic stance language

So the current system can tell us:
- `stance = nuance`
- `belief_summary = being an AI practitioner matters more than passively watching the hype`
- `experience_summary = The work is to build a durable system...`

But it cannot yet tell us:
- what Johnnie agrees with in this article
- what he thinks is missing
- what he would challenge
- what he would bring in from lived experience
- what part of the article matters most to him
- what he would refuse to overstate

That is exactly why Lab still shows:
- `johnnie_perspective = missing`

## The Actual Problem Phase 3 Must Solve
The system already knows:
- the article
- some world context
- some persona evidence

But it does not yet know:
- John's actual point of view on that article

This phase must answer the human question:
- "If Johnnie read this, what would he actually think and say before any writing happens?"

That is not identical to:
- article stance
- lane
- belief retrieval
- reaction brief

It is its own stage.

## Scope
Phase 3 will build and expose:
- `JohnniePerspectivePacket`
- explicit agreement and pushback modeling
- lived-addition selection
- what-matters-most prioritization
- skepticism and caution signals
- audience/role posture
- Lab visibility for all of the above

Phase 3 will not yet build:
- final reaction-brief copy blocks
- final content-angle selection
- template assembly
- opener banks
- humor
- small-model optimization

## Architectural Rules
1. Do not invent a second persona system.
2. Consume Phase 1 and Phase 2 outputs instead of recomputing them.
3. Do not collapse perspective back into one stance label.
4. Do not write final draft copy in this phase.
5. Do not force contrarianism if the article actually aligns.
6. Do not force agreement if the article conflicts with Johnnie's worldview.
7. Respect role-safety and audience posture when perspective is formed.

## Phase 3 Output Objects

### 1. JohnniePerspectivePacket
One per article/lane run.

It should include at minimum:
- `article_summary_view`
- `johnnie_belief_view`
- `johnnie_evidence_view`
- `agree_with`
- `pushback`
- `lived_addition`
- `what_matters_most`
- `skepticism`
- `risk_or_caution`
- `audience_posture`
- `role_posture`
- `perspective_priority`
- `perspective_confidence`
- `selection_rationale`
- `evidence`
- `missing_fields`

### 2. PerspectiveDecisionTrace
Lab must be able to show:
- why a specific agreement point was chosen
- why a pushback point was or was not present
- why a lived addition was or was not present
- why one issue mattered most
- why caution was or was not injected

### 3. PerspectiveInputPacket
This phase should consume:
- article understanding outputs from Phase 1
- persona retrieval outputs from Phase 2
- role safety signals
- lane context

It should not directly depend on:
- final draft text
- template choice
- opener bank choice

## The Boundary Between Phase 3 And Phase 4
Phase 3 answers:
- what is Johnnie's reaction?

Phase 4 answers:
- how do we turn that reaction into a usable reaction brief for writing?

Phase 3 should produce perspective substance, not writing structure.

## Phase 3 Workstreams

### Workstream A: Perspective Input Assembly
Goal:
- combine article understanding and persona retrieval into one perspective input

Build:
- normalized perspective input packet
- explicit worldview inputs
- explicit evidence inputs
- role safety inputs

Primary reuse:
- Phase 1 `ArticleUnderstanding`
- Phase 2 `PersonaRetrievalPacket`
- current `role_safety` logic

Success condition:
- Phase 3 starts from evidence packets, not loose lane heuristics

### Workstream B: Agreement Modeling
Goal:
- decide what Johnnie actually agrees with in the article

Build:
- `agree_with`
- agreement confidence
- agreement rationale

Primary reuse:
- article stance
- retrieved claims
- retrieved initiatives
- worldview claims and philosophy

Success condition:
- agreement is specific to the article, not generic positivity

### Workstream C: Pushback Modeling
Goal:
- decide what Johnnie would challenge, qualify, or resist

Build:
- `pushback`
- pushback reason
- pushback severity

Primary reuse:
- decision principles
- contrarian claims
- article stance and world position

Success condition:
- the system can distinguish:
  - full agreement
  - partial agreement
  - disagreement
  - "yes, but"

### Workstream D: Lived Addition Modeling
Goal:
- decide what Johnnie would add from lived experience

Build:
- `lived_addition`
- source artifact for that addition
- lived-proof rationale

Primary reuse:
- selected stories
- selected initiatives
- approved anecdotal deltas

Success condition:
- lived context is relevant, not bolted on

### Workstream E: What-Matters-Most Prioritization
Goal:
- decide which part of the article Johnnie would elevate first

Build:
- `what_matters_most`
- priority rationale
- de-prioritized alternatives

Primary reuse:
- philosophy
- decision principles
- audience communication patterns

Success condition:
- the system can explain why Johnnie centers one issue over another

### Workstream F: Skepticism And Caution Modeling
Goal:
- decide where Johnnie would be careful, skeptical, or unwilling to overstate

Build:
- `skepticism`
- `risk_or_caution`
- confidence bounds

Primary reuse:
- role safety
- proof strength
- artifact-backed evidence
- anti-hype worldview claims

Success condition:
- the system can say "this is directionally right, but..." for the right reasons

### Workstream G: Audience And Role Posture
Goal:
- modulate perspective based on who this is for and what role Johnnie is speaking from

Build:
- `audience_posture`
- `role_posture`

Primary reuse:
- `audience_communication.md`
- lane context
- role-safety logic

Success condition:
- the same article can produce different valid perspective emphasis across lanes without losing integrity

### Workstream H: Perspective Coherence
Goal:
- ensure the perspective packet is internally coherent

Build:
- contradiction checks
- empty-perspective checks
- agreement/pushback conflict checks
- evidence coverage checks

Success condition:
- the system stops emitting perspective packets that are vague, contradictory, or fake-specific

### Workstream I: Lab Observability
Goal:
- expose the full perspective object before drafting

Build:
- perspective panels
- evidence panels
- missing-field panels
- confidence and rationale rendering

Success condition:
- `johnnie_perspective` is no longer `missing`

## The Canonical Phase 3 Stage Board
Phase 3 should make these slices first-class:

1. `perspective_inputs`
2. `agreement_modeling`
3. `pushback_modeling`
4. `lived_addition`
5. `what_matters_most`
6. `skepticism`
7. `audience_posture`
8. `role_posture`
9. `perspective_coherence`
10. `johnnie_perspective`

These are the slices Phase 3 is allowed to fully own.
`reaction_brief` remains a downstream phase.

## Stage Contracts

### Perspective Inputs
Should know:
- what article-side and persona-side evidence is available for perspective

Current state:
- implicit across several fields

Missing:
- one normalized perspective input object

Outputs:
- perspective input packet

Measure:
- `perspective_inputs_present`
- `article_inputs_present`
- `persona_inputs_present`
- `role_safety_present`

### Agreement Modeling
Should know:
- what Johnnie agrees with in the article

Current state:
- implicit in stance choice

Missing:
- explicit agreement object

Outputs:
- agreement packet

Measure:
- `agreement_point_present`
- `agreement_relevance_score`
- `agreement_specificity_score`

### Pushback Modeling
Should know:
- what Johnnie would push back on or qualify

Current state:
- implied by `counter` or `nuance` stance, but not explicit

Missing:
- explicit pushback object

Outputs:
- pushback packet

Measure:
- `pushback_point_present`
- `pushback_relevance_score`
- `pushback_necessity_score`

### Lived Addition
Should know:
- what Johnnie would add from lived experience

Current state:
- experience anchor exists, but not as an explicit addition to the article

Missing:
- explicit lived-addition object

Outputs:
- lived-addition packet

Measure:
- `lived_addition_present`
- `lived_addition_relevance_score`
- `lived_proof_strength_score`

### What Matters Most
Should know:
- what Johnnie would emphasize first

Current state:
- not modeled

Missing:
- priority selection and rationale

Outputs:
- perspective-priority packet

Measure:
- `priority_point_present`
- `priority_relevance_score`
- `priority_rationale_score`

### Skepticism
Should know:
- where caution or skepticism belongs

Current state:
- partly hidden in role safety and counter stance

Missing:
- explicit skepticism object

Outputs:
- skepticism packet

Measure:
- `skepticism_present`
- `skepticism_reason_score`
- `overstatement_risk_control_score`

### Audience Posture
Should know:
- how Johnnie would modulate tone and framing for the audience

Current state:
- mostly lane-level

Missing:
- explicit posture object

Outputs:
- audience-posture packet

Measure:
- `audience_posture_present`
- `audience_fit_score`

### Role Posture
Should know:
- what role Johnnie is speaking from in this response

Current state:
- mostly implicit in lane

Missing:
- explicit role posture

Outputs:
- role-posture packet

Measure:
- `role_posture_present`
- `role_alignment_score`

### Perspective Coherence
Should know:
- whether the whole perspective object hangs together

Current state:
- not modeled

Missing:
- coherence validation

Outputs:
- perspective coherence packet

Measure:
- `perspective_coherence_score`
- `internal_contradiction_penalty`
- `empty_perspective_penalty`

### Johnnie Perspective
Should know:
- whether the system has modeled a usable Johnnie reaction

Current state:
- missing as a first-class object

Missing:
- `JohnniePerspectivePacket`

Outputs:
- perspective packet

Measure:
- `johnnie_perspective_score`
- `agree_with_present`
- `pushback_present`
- `lived_addition_present`
- `what_matters_most_present`
- `personal_reaction_score`

## Recommended File Strategy

### Reuse directly
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/lab_experiment_service.py`
- `knowledge/persona/feeze/identity/philosophy.md`
- `knowledge/persona/feeze/identity/decision_principles.md`
- `knowledge/persona/feeze/identity/audience_communication.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`

### Likely new runtime service
- `backend/app/services/social_johnnie_perspective_service.py`

Reason:
- Phase 3 should not bloat `social_belief_engine.py` into a do-everything heuristics file
- perspective modeling deserves a stable service boundary
- Phase 4 should consume its output directly

### Likely callers
- `social_signal_utils.py`
- Lab experiment builders
- future `social_reaction_brief_service.py`

## Recommended Implementation Shape

### Step 1: Build perspective inputs
Inputs should include:
- article stance
- world stakes
- event type
- selected claims
- selected stories
- selected initiatives
- selected deltas
- lane
- role safety

### Step 2: Model agreement, pushback, and lived addition separately
Do not try to create one giant perspective string first.

### Step 3: Model priority and skepticism
Perspective is not complete until the system knows:
- what Johnnie centers
- what Johnnie questions

### Step 4: Build one compact perspective packet
The output should be compact enough for later phases to use without re-inferring it.

### Step 5: Replace direct stance dependence in the social path
Current stance logic should become:
- a downstream summary of perspective
- not the upstream substitute for perspective

## Lab Rendering Plan
For each probe/article, Lab should render:

### Perspective Inputs
- article understanding summary
- selected claims
- selected stories
- selected initiatives
- selected deltas

### Agreement Panel
- what Johnnie agrees with
- why

### Pushback Panel
- what Johnnie resists or qualifies
- why

### Lived Addition Panel
- what Johnnie adds from experience
- which artifact supports it

### Priority Panel
- what matters most
- what got deprioritized

### Skepticism Panel
- what is being bounded or handled cautiously

### Stage Diagnostics
- pass / warn / fail / missing
- score
- reason
- evidence
- missing fields

## Quantification
Phase 3 should introduce these scores:
- `agreement_relevance_score`
- `pushback_relevance_score`
- `lived_addition_relevance_score`
- `priority_rationale_score`
- `skepticism_reason_score`
- `audience_fit_score`
- `role_alignment_score`
- `perspective_coherence_score`
- `johnnie_perspective_rollup_score`

Suggested status policy:
- `pass`: score >= 8.5 and the perspective packet is evidence-backed and coherent
- `warn`: score >= 6.5 or one major slice is thin
- `fail`: score < 6.5 or the perspective is materially off
- `missing`: the slice is not yet modeled

## Qualification
Every score must include a reason.

Examples:
- `agreement_modeling_warn`: "The system found a general agreement frame, but it did not tie that agreement to the article's actual stakes."
- `pushback_modeling_missing`: "No explicit pushback object is being modeled yet; nuance is only implied by stance."
- `lived_addition_warn`: "A valid experience anchor was retrieved, but the system did not explain how it changes the article interpretation."
- `what_matters_most_fail`: "The system could not explain why Johnnie would prioritize one issue over competing issues in the article."

## Exit Criteria
Phase 3 is only complete when:
1. `johnnie_perspective` is no longer `missing` in Lab
2. the system can show explicit agreement, pushback, lived addition, and priority before drafting
3. perspective is evidence-backed by retrieved claims/stories/initiatives/deltas
4. stance is no longer the only proxy for reaction
5. later phases can consume `JohnniePerspectivePacket` directly

## Non-Goals
Do not spend Phase 3 time on:
- humor
- opener banks
- template variation
- final reaction-brief writing
- final draft assembly
- lane-polish work
- small-model cost tuning

Those remain downstream of perspective correctness.

## Risks

### Risk: Collapsing perspective into stance again
Mitigation:
- require explicit agreement, pushback, lived addition, and priority fields

### Risk: Writing copy too early
Mitigation:
- keep perspective outputs as reasoning objects, not final copy blocks

### Risk: Fake specificity
Mitigation:
- require evidence and rationale for each perspective slice

### Risk: Over-forcing disagreement
Mitigation:
- allow true agreement when the article and worldview align

### Risk: Ignoring role posture
Mitigation:
- require audience and role posture modeling before shipping the phase

## Handoff To Phase 4
Phase 4 should consume:
- `JohnniePerspectivePacket`
- agreement rationale
- pushback rationale
- lived-addition rationale
- priority rationale
- skepticism rationale

Phase 4 should not have to decide what Johnnie thinks.
It should decide how to package that perspective into:
- article view
- Johnnie view
- tension
- content angle
- evidence to use

That is the Phase 3 contract.

Phase 4 deep-dive:
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`

## Small-Model Note
`gpt-4o-mini` compatibility remains important, but it is not the Phase 3 success condition.
Phase 3 succeeds when the system models a real Johnnie perspective before writing.
Model-cost optimization remains downstream of correctness.

## Related Files
- `SOPs/social_persona_synthesis_roadmap_sop.md`
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`
- `knowledge/persona/feeze/identity/claims.md`
- `knowledge/persona/feeze/identity/philosophy.md`
- `knowledge/persona/feeze/identity/decision_principles.md`
- `knowledge/persona/feeze/identity/audience_communication.md`
- `knowledge/persona/feeze/history/story_bank.md`
- `knowledge/persona/feeze/history/initiatives.md`
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/lab_experiment_service.py`
