# Phase 7: Type Matrix Expansion Implementation Plan

## Purpose
This document is the canonical implementation plan for Phase 7 of the social persona synthesis roadmap:
- expand the social/article-response system beyond plain lane-based comment/repost drafting
- introduce explicit response types as a first-class runtime dimension
- separate `response_mode`, `lane`, and `response_type` so the system can reason more like Johnnie and less like a lane template picker
- widen Lab from "did comment/repost clear across lanes?" into "did the right type of response clear across lanes, modes, and source situations?"

This document is not a standalone roadmap.
It is the Phase 7 deep-dive for:
- `SOPs/social_persona_synthesis_roadmap_sop.md`

It assumes the upstream phases exist:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md`

## Why Phase 7 Comes After Evaluation Hardening
Phase 6 is the point where the system finally becomes strict enough to say:
- which stages are real
- which stages are still missing
- whether a green run can actually be trusted

Phase 7 expands the behavioral surface on top of that.

If the type matrix expands too early, the system gets a bigger playground for the same unresolved problems:
- more fluent-but-shallow outputs
- more template families without real synthesis
- more false confidence because the benchmark only sees polished copy

Phase 7 comes after Phase 6 because the system now needs to answer a different question:
- not only "can it produce a usable lane-aware comment or repost?"
- but "can it choose the right kind of reaction for this article, this lane, this source context, and Johnnie's actual perspective?"

That is a higher-order behavior.
It should only be expanded after the upstream synthesis and scoring layers are visible enough to judge it honestly.

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

Phase 7 only covers `7. type matrix expansion`.

It must leave the system in a state where:
- response type is its own modeled decision
- "personal story" is no longer only a lane-shaped hack
- agreement and disagreement patterns are chosen from synthesis, not from opener banks
- humor is treated as a gated type family, not a default writing flourish
- Lab can inspect the type-selection decision before looking at the rendered copy

## Integrated Thought Clarification For Phase 7
Every Phase 7 slice must explicitly answer:

1. `What should this slice know?`
2. `What does the system compute today?`
3. `What is missing?`
4. `Why does that missing logic matter downstream?`
5. `What artifact should this slice output?`
6. `How will Lab measure pass / warn / fail / missing?`
7. `What existing contract must this slice reuse instead of replacing?`

This is mandatory for all response-type work in this phase.

## Current Implementation Read

### What already exists and should be reused
The current social/article path already has several useful pieces:

- source-side response modes in `backend/app/services/social_signal_utils.py`
  - `comment`
  - `repost`
  - `post_seed`
  - `belief_evidence`
- lane/lens routing in `backend/app/services/social_signal_utils.py`
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
- stance and agreement signals in `backend/app/services/social_belief_engine.py`
  - stance
  - agreement level
  - belief summary
  - experience summary
- reaction-side synthesis fields from prior phases
  - article understanding outputs
  - persona retrieval outputs
  - Johnnie perspective outputs
  - reaction brief outputs
  - template composition trace
  - hardened evaluation inputs
- current variant assembly in `backend/app/services/social_signal_utils.py`
  - `build_variants(...)`
  - lane-specific builders
  - `comment_open(...)`
  - `repost_open(...)`
  - `compose_response(...)`
- current Lab experiment surfaces in `backend/app/services/lab_experiment_service.py`
  - article response matrix
  - stage board
  - lane coverage / benchmark coverage

### What is actually happening today
Today the system still conflates three different ideas:

1. `response_mode`
- comment
- repost
- post seed
- belief evidence

2. `lane`
- AI
- admissions
- leadership
- entrepreneur
- and so on

3. `response_type`
- agree
- contrarian
- personal story
- humor

Only the first two are explicit.
The third mostly does not exist as a first-class dimension yet.

Instead:
- `agreement` is partially implied through `agreement_level`
- `contrarian` is partially implied through `stance=counter`
- `personal story` is treated as a lane/lens
- `humor` is not modeled as a real type at all

That means the current system can say:
- "this is an admissions repost"

But it cannot yet explicitly say:
- "this is an admissions repost in a contrarian type"
- "this is an AI comment in an agree-but-extend type"
- "this is a leadership comment in a personal-story type"
- "this is a humor draft, and humor was eligible because the stakes were low and the brief had a safe comedic tension"

That is the Phase 7 gap.

## The Actual Problem Phase 7 Must Solve
The system now has enough upstream understanding to know:
- what the article is saying
- how it exists in the world
- what Johnnie thinks
- what tension exists
- what evidence should be used

But the runtime still lacks one critical decision:
- what kind of response is Johnnie actually making?

That missing decision creates several problems:
- "agree" and "contrarian" are flattened into generic stance phrases
- "personal story" gets trapped as a lane instead of becoming a usable overlay across lanes
- humor has no safe entry point because the system has no formal type contract for it
- Labs can show clean lane drafts without proving the system chose the right reaction form

Phase 7 must solve that by introducing a real type system on top of the current synthesis stack.

## Canonical Dimension Model
This is the canonical separation Phase 7 must enforce.

### 1. Response Mode
This answers:
- what deliverable shape is being generated?

Examples:
- `comment`
- `repost`
- `post_seed`
- `belief_evidence`

### 2. Lane
This answers:
- which domain lens is dominant?

Examples:
- `ai`
- `ops-pm`
- `admissions`
- `program-leadership`
- `entrepreneurship`

### 3. Response Type
This answers:
- what kind of reaction is Johnnie making?

Initial Phase 7 targets:
- `agree`
- `contrarian`
- `personal_story`
- `humor`

This separation is mandatory.
Do not use:
- lane as a substitute for type
- stance as a substitute for type
- opener family as a substitute for type

## Scope
Phase 7 will build and expose:
- explicit response-type taxonomy
- runtime response-type selection
- response-type eligibility rules
- manual type override support
- type-aware rendering hooks
- type-aware evaluation and Lab experiments
- backward-compatible migration for the current `personal-story` lane
- a gated humor rollout path

Phase 7 will not yet build:
- a free-form joke engine
- unlimited style families
- a second writing system
- a second belief/persona system
- small-model optimization
- broad source-matrix expansion beyond what Lab can already evaluate credibly

## Architectural Rules
1. Do not build a second social renderer.
2. Reuse the current social/article synthesis stack and add a type layer on top.
3. Keep `response_mode`, `lane`, and `response_type` explicitly separate.
4. Do not keep `personal-story` only as a lane forever.
5. Backward compatibility matters; the current live lens UI must not break while the runtime migrates.
6. Humor must be gated by eligibility and safety, not treated as "just another opener bank."
7. Type selection must consume reaction-brief and Johnnie-perspective outputs, not bypass them.
8. Lab must be able to show why a type was chosen, not only the final text.

## Phase 7 Output Objects

### 1. ResponseTypePacket
One per article/lane/response-mode run.

It should include at minimum:
- `response_type`
- `type_family`
- `type_confidence`
- `type_selection_reason`
- `eligible_types`
- `rejected_types`
- `selection_evidence`
- `manual_override`
- `manual_override_source`
- `blocked_types`
- `missing_fields`

### 2. ResponseTypeEligibilityTrace
This should explain:
- why `agree` was eligible or blocked
- why `contrarian` was eligible or blocked
- why `personal_story` was eligible or blocked
- why `humor` was eligible or blocked
- which upstream stage created that eligibility signal

### 3. TypeMatrixTrace
Lab should be able to inspect:
- article
- lane
- response mode
- selected type
- benchmark score
- strengths
- failure reasons
- whether the same type family is being overused

### 4. HumorSafetyPacket
Humor must get its own explicit gate.

It should include:
- `humor_allowed`
- `humor_risk_level`
- `humor_reason`
- `humor_target`
- `humor_boundary`
- `humor_failure_risk`
- `missing_fields`

## Type Definitions

### Agree
Definition:
- Johnnie materially agrees with the article's main signal and wants to reinforce, extend, sharpen, or operationalize it.

Requires:
- explicit `agree_with`
- article-specific agreement rationale
- at least one extension, translation, or consequence

Should not degrade into:
- empty positivity
- generic approval
- "agreed" with no added value

Likely compatible modes:
- `comment`
- `repost`
- `belief_evidence`

Primary failure modes:
- `agreement_generic`
- `agreement_not_article_specific`
- `agreement_without_addition`

### Contrarian
Definition:
- Johnnie does not fully buy the article framing and wants to challenge, redirect, or deepen it.

Requires:
- explicit `pushback`
- rationale grounded in article stakes
- safe role posture
- enough evidence to make disagreement useful instead of reactive

Should not degrade into:
- forced disagreement
- shallow negativity
- contrarianism as performance

Likely compatible modes:
- `comment`
- `repost`
- `belief_evidence`

Primary failure modes:
- `contrarian_forced`
- `pushback_not_supported`
- `contrarian_without_world_stakes`

### Personal Story
Definition:
- the response should be anchored in lived experience, operator scar tissue, or a real story posture.

Requires:
- explicit `lived_addition`
- evidence-backed experience anchor
- a clear connection between the story and the article tension

Should not degrade into:
- vague autobiography
- generic "I have seen this before"
- story used as aesthetic instead of proof

Likely compatible modes:
- `comment`
- `repost`
- `post_seed`
- `belief_evidence`

Primary failure modes:
- `story_anchor_missing`
- `story_not_relevant`
- `story_overrides_article`

### Humor
Definition:
- the response uses controlled wit, irony, or a tension-relieving angle without breaking truth, safety, or taste.

Requires:
- low or moderate stakes
- no unresolved safety concern
- a clear comedic target
- a clear humor boundary
- a strong non-humor version already available

Should not degrade into:
- cheap jokes
- tone breaking
- punching down
- minimizing serious stakes
- humor used to hide missing synthesis

Likely compatible modes:
- `comment`
- `repost`
- later `short_comment` if quality proves out

Primary failure modes:
- `humor_not_safe`
- `humor_target_unclear`
- `humor_overrides_truth`
- `humor_not_funny`

## The Personal-Story Migration Rule
The current live system already has:
- `personal-story` as a lane in `LENS_IDS`
- `build_personal_story_comment(...)` as a lane-specific builder

Phase 7 must not break that surface abruptly.

Canonical migration rule:
1. keep `personal-story` as a backward-compatible UI control
2. reinterpret it internally as:
   - `response_type=personal_story`
   - plus either:
     - explicitly selected lane
     - or a default inferred lane
3. over time, move the runtime away from treating story as a lane peer to:
   - AI
   - admissions
   - leadership
   - entrepreneurship

This is important because story is not a domain lens.
It is a response type that can sit on top of multiple lanes.

## The Boundary Between Phase 7 And Phase 8
Phase 7 answers:
- what response type should this system produce, and can it do that credibly?

Phase 8 answers:
- can the now-correct system hold on smaller/cheaper models like `gpt-4o-mini`?

Phase 7 should produce:
- type-aware runtime contracts
- type-aware Lab observability
- trustworthy behavior across agree / contrarian / personal story / humor

Phase 8 should produce:
- cheaper, stable execution after the correct prototype is already working

## Phase 7 Workstreams

### Workstream A: Type Taxonomy And Runtime Contract
Goal:
- formalize response type as a first-class system dimension

Build:
- canonical type ids
- type metadata
- type compatibility by response mode
- backward-compatibility rules
- type-level failure taxonomy

Primary reuse:
- `social_signal_utils.py`
- `social_belief_engine.py`
- Phase 3 `JohnniePerspectivePacket`
- Phase 4 `ReactionBriefPacket`

Success condition:
- the system can describe type separately from lane and response mode

### Workstream B: Response Type Selection
Goal:
- choose the right type from article, worldview, persona retrieval, and Johnnie perspective

Build:
- planned `backend/app/services/social_response_type_service.py`
- type selection inputs from:
  - article stance
  - agreement / pushback
  - lived addition
  - tension
  - content angle
  - audience posture
  - role posture
- type selection output:
  - `ResponseTypePacket`

Primary reuse:
- Phase 1 article understanding outputs
- Phase 3 perspective packet
- Phase 4 reaction brief

Success condition:
- the system can say why `agree`, `contrarian`, `personal_story`, or `humor` won

### Workstream C: Eligibility And Blocking Logic
Goal:
- prevent the system from forcing the wrong type

Build:
- eligibility matrix
- blocked-type reasons
- humor safety gating
- contrarian guardrails
- story-relevance checks

Primary reuse:
- Phase 6 hardened evaluation rules
- role safety
- article stakes

Success condition:
- Lab can show why a type was blocked, not just why one was selected

### Workstream D: Type-Aware Rendering
Goal:
- let the existing lane builders render through type-aware guidance instead of lane-only heuristics

Build:
- type-aware rendering hooks in `social_signal_utils.py`
- controlled migration path for `build_variants(...)`
- type-aware template selection
- type-aware composition traces

Primary reuse:
- existing lane builders
- Phase 5 composition trace
- Phase 4 brief guidance

Success condition:
- renderer stays single-stack, but can produce different response families credibly

### Workstream E: Lab Type-Matrix Expansion
Goal:
- turn Lab into the canonical place to validate response types, not only lane coverage

Build:
- new or expanded experiment:
  - `article-response-type-matrix`
- matrix dimensions:
  - article probe
  - lane
  - response mode
  - response type
- stage board slices for:
  - `response_type_selection`
  - `type_eligibility`
  - `humor_safety`
  - type-specific output quality

Primary reuse:
- `lab_experiment_service.py`
- current article response matrix
- current stage board

Success condition:
- Lab can show:
  - which type was selected
  - whether that type passed
  - why it failed
  - where type overuse is happening

### Workstream F: Humor Gated Rollout
Goal:
- make humor a controlled type family instead of an uncontrolled tone modifier

Build:
- humor eligibility contract
- humor-safe prompt guidance
- humor benchmark subgroup
- humor-specific evaluator additions

Primary reuse:
- Phase 6 shipping gates
- type selection service
- composition traces

Success condition:
- humor can be tested without contaminating the rest of the system

## Lab Expansion Contract
Phase 7 should not replace the current article-response matrix.
It should extend it.

### Keep
- current baseline comment/repost lane matrix
- current stage board
- current benchmark floor logic

### Add
- type dimension
- type-selection stage
- eligibility stage
- humor-safety stage
- type-specific benchmark cuts

### Recommended rollout order
1. `agree`
2. `contrarian`
3. `personal_story`
4. `humor`

This order matters because humor should only be tested after the non-humor type system is stable.

## Proposed Lab Success Conditions

### Stage 7A: Non-humor type matrix
Target:
- `agree`
- `contrarian`
- `personal_story`

Minimum conditions:
- `response_type_selection` no longer `missing`
- explicit eligibility traces exist
- personal story no longer depends on lane-only hacks
- benchmark holds across:
  - comments
  - reposts
  - target lanes

### Stage 7B: Humor gated experiment
Target:
- `humor`

Minimum conditions:
- humor is blocked by default unless explicitly eligible
- humor never forces itself into high-stakes contexts
- humor quality is scored separately
- humor can fail without turning the whole matrix green

## Scoring And Qualification
Phase 7 should add or require these score families:
- `response_type_score`
- `agreement_quality_score`
- `contrarian_quality_score`
- `story_relevance_score`
- `humor_safety_score`
- `humor_quality_score`
- `type_lane_fit_score`
- `type_mode_fit_score`
- `type_diversity_score`
- `type_selection_confidence`

Every score must include a reason.

Examples:
- `response_type_missing`: "The system produced a lane-valid comment, but it still did not explicitly choose a response type."
- `contrarian_quality_warn`: "The draft pushed back, but the disagreement was generic and not tightly tied to the article's actual stakes."
- `personal_story_fail`: "The system attempted a story response without a relevant lived-evidence anchor."
- `humor_blocked`: "Humor was blocked because the article stakes are too high and the target would have been unclear."

## Exit Criteria
Phase 7 is only complete when:
1. `response_type_selection` is no longer `missing` in Lab
2. the system can model and test:
   - `agree`
   - `contrarian`
   - `personal_story`
3. the current `personal-story` lane is on a documented migration path toward type-aware behavior
4. type selection is backed by article understanding, persona retrieval, Johnnie perspective, and reaction brief outputs
5. Lab can show type-specific failure reasons
6. humor has a gated experiment contract, even if humor remains partially rolled out

## Non-Goals
Do not spend Phase 7 time on:
- adding dozens of joke templates
- broad style-library expansion
- rewriting the whole lane system from scratch
- making humor mandatory
- small-model cost tuning
- using type labels to hide missing synthesis

Those remain outside Phase 7 or downstream of it.

## Risks

### Risk: Type becomes another word for stance
Mitigation:
- keep stance and response type as separate fields with separate traces

### Risk: Type becomes another word for lane
Mitigation:
- keep `personal_story` as the canonical migration example of a type overlay

### Risk: Forced contrarianism
Mitigation:
- require explicit pushback evidence and block contrarian when full agreement is stronger

### Risk: Empty personal-story drafts
Mitigation:
- require lived evidence and article relevance before the story type can pass

### Risk: Humor degrades trust
Mitigation:
- gate humor with its own safety packet and test it separately first

### Risk: Renderer fragmentation
Mitigation:
- extend the current renderer instead of building a second type-specific drafting stack

## Handoff To Phase 8
Phase 8 should consume:
- stable response-type contracts
- trusted type-aware Lab experiments
- strict type-aware evaluation gates
- a working prototype that is behaviorally correct before cost optimization starts

Phase 8 should not be asked to solve:
- missing response types
- missing eligibility logic
- broken humor boundaries
- lane/type confusion

That is the Phase 7 contract.

## Small-Model Note
`gpt-4o-mini` compatibility remains important, but it is not the Phase 7 success condition.
Phase 7 succeeds when the system can choose and render the correct response type credibly on top of the synthesis stack.
Model-cost optimization remains downstream of correctness.

## Related Files
- `SOPs/social_persona_synthesis_roadmap_sop.md`
- `workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/lab_experiment_service.py`
- `workspaces/linkedin-content-os/docs/source_expansion_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
