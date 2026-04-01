# SOP: Social Persona Synthesis Roadmap

## Purpose
Define the canonical roadmap for making the AI Clone social/content system understand:
- what a source is saying
- how that source exists in the world
- what Johnnie would think about it
- which persona artifacts actually matter for that source
- how to turn that synthesis into comments, reposts, post seeds, and later broader content outputs

This SOP exists because the system is now observable enough to show the real gap:
- the social/article response system is structurally usable
- the typed original-post generator is stronger than the social response engine
- the main remaining weakness is not basic routing
- the main remaining weakness is `source -> Johnnie perspective -> synthesis -> draft` depth

This SOP is the roadmap for fixing that without creating:
- a second persona system
- a second source system
- a second social drafting stack
- a prompt-only band-aid layer that duplicates logic already present elsewhere

## Canonical Reading Of The Problem
The current project has two relevant generation systems:

1. `Original post generation`
- stronger typed retrieval and grounding path
- main files:
  - `backend/app/services/persona_bundle_context_service.py`
  - `backend/app/services/content_generation_context_service.py`
  - `backend/app/routes/content_generation.py`

2. `Article/social response generation`
- comment/repost/lens response path
- main files:
  - `backend/app/services/social_signal_utils.py`
  - `backend/app/services/social_belief_engine.py`
  - `backend/app/services/social_technique_engine.py`
  - `backend/app/services/social_expression_engine.py`
  - `backend/app/services/social_evaluation_engine.py`

The social/article response engine currently does several things well:
- lane routing
- stance labeling
- usable draft generation
- baseline evaluation
- feed integration

But it is still too thin in the middle:
- article/world understanding is incomplete
- persona retrieval is not article-specific enough
- Johnnie's actual reaction is not modeled as a first-class object
- the final draft is still too template-shaped relative to the article and the persona truth

That is why the system can pass technical draft checks while still sounding like:
- lane translation
- repeated system/process reframes
- weakly personalized commentary

instead of:
- Johnnie reacting to this exact source through his actual worldview, lived proof, and strategic taste

## Core Rule
Do not solve this by adding more surface-level writing tricks first.

Do not start with:
- bigger opener banks
- more style examples
- humor generation
- more template variation
- more prompt verbosity

Those things matter later, but they are not the bottleneck yet.

The correct build order is:
1. source understanding
2. persona retrieval
3. Johnnie perspective modeling
4. synthesis / reaction brief
5. draft composition
6. evaluation and learning
7. only then deeper style-family expansion such as humor

## Integrated Thought Clarification Contract
Every roadmap stage in this SOP must be developed and reviewed with the same thought-clarification frame.

For each stage, explicitly answer:

1. `What the stage is supposed to know`
- the decision or understanding this slice is responsible for

2. `What the system actually computes today`
- current implementation, not what the docs imply

3. `What is missing`
- missing fields, missing logic, missing evidence, or missing observability

4. `Why that matters`
- how the missing logic degrades voice, truth, stance, or usefulness

5. `What success looks like`
- concrete output or artifact the stage should produce

6. `How it will be measured`
- pass / warn / fail
- numeric score where appropriate
- top failure reasons

7. `What it must reuse`
- existing service, source system, or persona contract it must extend instead of replacing

This is the canonical integrated-thought-clarification format for this area.

## North Star
The system should eventually be able to do this reliably:

1. understand the article/source as an object in the world
2. understand the article's own stance and structure
3. retrieve the right persona truths, stories, initiatives, and approved deltas
4. model what Johnnie agrees with, rejects, adds, and has lived
5. produce a visible synthesis object before drafting
6. draft lane-aware responses that feel specific to the source and to Johnnie
7. explain where the synthesis was thin, missing, or fake when quality drops

## Source Of Truth Inputs
This roadmap must stay aligned with:

### Persona canon
- `knowledge/persona/feeze/identity/claims.md`
- `knowledge/persona/feeze/identity/philosophy.md`
- `knowledge/persona/feeze/identity/decision_principles.md`
- `knowledge/persona/feeze/identity/audience_communication.md`
- `knowledge/persona/feeze/identity/VOICE_PATTERNS.md`
- `knowledge/persona/feeze/identity/bio_facts.md`
- `knowledge/persona/feeze/history/story_bank.md`
- `knowledge/persona/feeze/history/initiatives.md`
- `knowledge/persona/feeze/prompts/content_examples.md`
- `knowledge/persona/feeze/prompts/taste_examples.md`
- `knowledge/persona/feeze/prompts/content_guardrails.md`
- `knowledge/persona/feeze/prompts/content_pillars.md`

### Shared architectural SOPs
- `SOPs/source_system_contract_sop.md`
- `SOPs/brain_workspace_boundary_sop.md`
- `SOPs/persona_grounded_content_generation_sop.md`
- `SOPs/persona_identity_state_sop.md`

### Workspace planning docs
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
- `workspaces/linkedin-content-os/docs/social_feed_architecture_plan.md`

## Current Implementation Read
This is the current working read of the system.

### Stronger than before
- persona bundle metadata already exists:
  - `memory_role`
  - `domain_tags`
  - `audience_tags`
  - `proof_kind`
  - `proof_strength`
  - `artifact_backed`
  - `usage_modes`
- typed original-post grounding exists
- social drafts are lane-aware and evaluable
- Lab can now surface missing stages explicitly

### Still weak
- article stance is not yet first-class
- world-modeling is thin
- persona retrieval is not truly article-specific
- Johnnie perspective is not rendered as its own object
- reaction brief does not exist as a first-class output
- template composition is not traced as its own stage
- social drafts are still too dependent on lane templates and reusable opener families

## Full Stage Map
This is the canonical full stack for `source -> Johnnie reaction -> content`.

### Article / World Side
1. `signal_intake`
2. `source_contract`
3. `claim_extraction`
4. `world_understanding`
5. `article_stance`
6. `source_expression`

### Johnnie / Persona Side
7. `persona_truth`
8. `persona_retrieval`
9. `belief_selection`
10. `experience_selection`
11. `johnnie_perspective`

### Synthesis Side
12. `lane_routing`
13. `stance_selection`
14. `reaction_brief`
15. `source_takeaway`
16. `technique_selection`

### Draft Side
17. `comment_draft`
18. `repost_draft`
19. `template_composition`
20. `voice_normalization`

### Evaluation Side
21. `lane_specificity`
22. `response_quality`
23. `safety`
24. `persona_fit`
25. `shipping_decision`

### Learning Side
26. `feedback_logging`
27. `performance_memory`
28. `promotion_review_handoff`

## Stage-by-Stage Development Contract

### 1. Signal Intake
What it is supposed to know:
- whether the source was captured cleanly enough to reason over

What the system computes today:
- title, summary, raw text, standout lines, core claim, supporting claims

What is missing:
- explicit confidence and extraction-loss visibility

Why it matters:
- thin source packets poison every later step

Success looks like:
- normalized source object with enough signal for downstream stages

Measure:
- `signal_completeness_score`
- `raw_text_present`
- `core_claim_present`
- `supporting_claims_count`

Reuse:
- `backend/app/services/social_signal_utils.py`

### 2. Source Contract
What it is supposed to know:
- platform, source class, unit kind, allowed response modes

What the system computes today:
- this is already present and mostly healthy

What is missing:
- confidence on classification

Measure:
- `source_contract_score`
- `classification_confidence`

Reuse:
- `backend/app/services/social_signal_utils.py`

### 3. Claim Extraction
What it is supposed to know:
- main claim
- supporting claim set
- standout lines

What the system computes today:
- basic extraction exists

What is missing:
- multi-claim hierarchy
- counter-claim awareness

Measure:
- `claim_clarity_score`
- `supporting_signal_score`
- `standout_line_quality_score`

Reuse:
- `backend/app/services/social_signal_utils.py`

### 4. World Understanding
What it is supposed to know:
- what domain the source occupies
- who is affected
- what the real-world stakes are
- why it matters beyond the article

What the system computes today:
- topic tags and some lane hints

What is missing:
- explicit world model
- explicit stakes model
- role alignment depth

Why it matters:
- without this, the system responds to themes, not to situated events

Measure:
- `world_context_score`
- `why_it_matters_present`
- `affected_actor_present`
- `role_alignment_score`

Reuse:
- `backend/app/services/social_signal_utils.py`
- future decomposition may justify a dedicated `social_article_understanding_service.py`

### 5. Article Stance
What it is supposed to know:
- what stance the article itself is taking

What the system computes today:
- missing as a first-class object

What is missing:
- article stance label
- article stance confidence
- article world position

Why it matters:
- Johnnie's response cannot be correctly modeled without first knowing what the source is actually doing

Measure:
- `article_stance_confidence`
- `article_stance_present`

Reuse:
- must extend the current social path, not create a second article parser

### 6. Source Expression
What it is supposed to know:
- whether the source is using contrast, boundary, directive, story, or plain structure

What the system computes today:
- basic structure detection exists

What is missing:
- stronger article-level trace and multi-sentence expression packet

Measure:
- `source_expression_score`
- `structure_family`
- `structure_preservation_score`

Reuse:
- `backend/app/services/social_expression_engine.py`

### 7. Persona Truth
What it is supposed to know:
- the current available truth set

What the system computes today:
- claims, stories, initiatives are loaded

What is missing:
- freshness and depth telemetry per run

Measure:
- `persona_truth_loaded`
- `claims_loaded`
- `stories_loaded`
- `initiatives_loaded`
- `overlay_loaded`

Reuse:
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/persona_bundle_context_service.py`

### 8. Persona Retrieval
What it is supposed to know:
- which persona artifacts matter for this exact source

What the system computes today:
- not truly modeled; current selection is mostly lane/profile-based

What is missing:
- ranked article-specific claims
- ranked stories
- ranked initiatives
- ranked approved deltas
- retrieval diversity

Why it matters:
- this is the main bottleneck behind repetitive, non-synthesized output

Measure:
- `persona_retrieval_score`
- `relevant_claims_count`
- `relevant_story_count`
- `relevant_initiative_count`
- `retrieval_diversity_score`
- `retrieval_redundancy_penalty`

Reuse:
- `backend/app/services/persona_bundle_context_service.py`
- committed overlay and `persona_deltas`

### 9. Belief Selection
What it is supposed to know:
- which belief best matches this source

What the system computes today:
- one belief chosen mostly by lane/profile

What is missing:
- article-matched relevance scoring
- overuse control

Measure:
- `belief_relevance_score`
- `belief_overuse_penalty`
- `belief_specificity_score`

Reuse:
- `backend/app/services/social_belief_engine.py`

### 10. Experience Selection
What it is supposed to know:
- which anecdote, initiative, or lived proof is relevant here

What the system computes today:
- one experience chosen mostly by lane/profile

What is missing:
- article-specific experience matching
- better proof/story differentiation

Measure:
- `experience_relevance_score`
- `experience_overuse_penalty`
- `experience_specificity_score`

Reuse:
- `backend/app/services/social_belief_engine.py`
- `knowledge/persona/feeze/history/story_bank.md`
- `knowledge/persona/feeze/history/initiatives.md`

### 11. Johnnie Perspective
What it is supposed to know:
- what Johnnie agrees with
- what he pushes back on
- what he adds from lived experience
- what would matter most to him here

What the system computes today:
- missing as a first-class object

Why it matters:
- without this, the system sounds like a lane translator, not Johnnie

Measure:
- `johnnie_perspective_present`
- `agreement_point_present`
- `pushback_point_present`
- `lived_addition_present`
- `personal_reaction_score`

Reuse:
- must be built on top of article understanding plus persona retrieval

### 12. Lane Routing
What it is supposed to know:
- which lanes are valid
- which lane is primary
- which lanes are secondary

What the system computes today:
- lane matrix generation is working

What is missing:
- explicit rationale for why a lane is valid or weak

Measure:
- `lane_coverage_rate`
- `lane_routing_score`
- `lane_rationale_present`

Reuse:
- `backend/app/services/social_signal_utils.py`

### 13. Stance Selection
What it is supposed to know:
- Johnnie stance toward the article

What the system computes today:
- stance exists, but is still profile/lane-heavy

What is missing:
- stronger dependency on article stance + persona retrieval

Measure:
- `stance_selection_score`
- `stance_contrast_score`
- `stance_diversity_score`

Reuse:
- `backend/app/services/social_belief_engine.py`

### 14. Reaction Brief
What it is supposed to know:
- article view
- Johnnie view
- tension
- content angle
- evidence to use

What the system computes today:
- missing as a first-class object

Why it matters:
- this is the missing synthesis layer between understanding and writing

Measure:
- `reaction_brief_present`
- `content_angle_score`
- `tension_present`
- `evidence_plan_present`

Reuse:
- should extend social pipeline, not duplicate original post planner

### 15. Source Takeaway
What it is supposed to know:
- the specific rewritten takeaway the draft should respond to

What the system computes today:
- first-pass rewrite exists

What is missing:
- better coverage for lanes that still fall to empty takeaways

Measure:
- `source_takeaway_score`
- `source_takeaway_present`
- `takeaway_specificity_score`

Reuse:
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_expression_engine.py`

### 16. Technique Selection
What it is supposed to know:
- rhetorical and emotional shaping

What the system computes today:
- first-pass rule-based selection exists

What is missing:
- richer technique reasoning
- overuse control

Measure:
- `technique_fit_score`
- `technique_diversity_score`
- `technique_overuse_penalty`

Reuse:
- `backend/app/services/social_technique_engine.py`

### 17. Comment Draft
### 18. Repost Draft
What these stages are supposed to do:
- produce usable response drafts from the synthesis object

What the system computes today:
- lane builders work, but depend heavily on reusable template banks

What is missing:
- stronger dependency on retrieved persona evidence and Johnnie perspective object

Measure:
- `comment_ready_rate`
- `repost_ready_rate`
- `draft_specificity_score`

Reuse:
- `backend/app/services/social_signal_utils.py`

### 19. Template Composition
What it is supposed to know:
- which open / contrast / bridge / main / close structure was selected

What the system computes today:
- composition happens, but template trace is not first-class

What is missing:
- template family ids
- opener-family trace
- closer-family trace

Measure:
- `template_trace_present`
- `opener_repetition_penalty`
- `close_repetition_penalty`

Reuse:
- `backend/app/services/social_signal_utils.py`

### 20. Voice Normalization
What it is supposed to do:
- remove generic or forbidden phrasing without sanding down voice

What the system computes today:
- this exists and is useful

What is missing:
- explicit over-cleaning penalty

Measure:
- `voice_cleanup_score`
- `forbidden_phrase_survival_rate`
- `over_sanitization_penalty`

Reuse:
- `backend/app/services/social_signal_utils.py`

### 21. Lane Specificity
### 22. Response Quality
### 23. Safety
What these stages are supposed to do:
- judge whether the drafts are lane-distinct, usable, and safe

What the system computes today:
- first-pass evaluator exists and is useful

What is missing:
- direct scoring of article/world understanding
- direct scoring of Johnnie-perspective quality
- direct scoring of synthesis quality

Measure:
- existing:
  - `lane_distinctiveness`
  - `belief_clarity`
  - `experience_anchor_strength`
  - `voice_match`
  - `expression_quality`
  - `role_safety_score`
- new:
  - `world_context_score`
  - `johnnie_perspective_score`
  - `synthesis_score`
  - `voice_truth_score`

Reuse:
- `backend/app/services/social_evaluation_engine.py`

### 24. Persona Fit
What it is supposed to know:
- whether the draft feels like Johnnie, not just the correct lane

What the system computes today:
- partially hidden inside voice/belief scores

What is missing:
- explicit persona-fit stage

Measure:
- `persona_fit_score`
- `lived_experience_presence_score`
- `belief_specificity_score`
- `repetition_penalty`

### 25. Shipping Decision
What it is supposed to know:
- whether the run is good enough to ship back into workspace execution

Measure:
- `ship_readiness_score`
- `pass / warn / fail`
- clear next action

### 26. Feedback Logging
### 27. Performance Memory
### 28. Promotion Review Handoff
What these are supposed to do:
- make the system learn from selection, copy, approval, and eventual promotion

What the system computes today:
- feedback logging exists
- persona delta handoff exists

What is missing:
- explicit tie-back from response quality to future retrieval and synthesis tuning

Measure:
- `copy_rate`
- `approval_rate`
- `post_rate`
- `persona_promotion_rate`
- `high_score_low_copy_gap`

## Roadmap Phases

### Phase 0: Observability Baseline
Goal:
- make every current slice visible
- show `missing` explicitly where the system does not really model something

Status:
- partially complete in Lab

Deliverables:
- expanded stage board
- missing-stage rendering
- stage evidence rendering
- sample-run matrix with context snapshots

Primary files:
- `backend/app/services/lab_experiment_service.py`
- `frontend/app/lab/page.tsx`

### Phase 1: Article / World Understanding
Goal:
- improve the article-side model before deeper personalization

Build:
- explicit article stance object
- explicit world/stakes object
- stronger source expression packet

Primary files:
- `backend/app/services/social_signal_utils.py`
- likely new `backend/app/services/social_article_understanding_service.py`
- `backend/app/services/lab_experiment_service.py`

Lab success conditions:
- `article_stance` no longer `missing`
- `world_understanding` moves from warn-heavy to pass-heavy

Phase deep-dive:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`

### Phase 2: Persona Retrieval
Goal:
- retrieve article-specific persona evidence instead of lane-default belief/story selection

Build:
- ranked claims
- ranked stories
- ranked initiatives
- ranked approved deltas
- retrieval diversity and overuse tracking

Primary files:
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/persona_bundle_context_service.py`
- likely new `backend/app/services/social_persona_retrieval_service.py`
- `backend/app/services/lab_experiment_service.py`

Lab success conditions:
- `persona_retrieval` no longer `missing`
- belief and experience overuse warnings drop

Phase deep-dive:
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`

### Phase 3: Johnnie Perspective Modeling
Goal:
- explicitly model Johnnie's actual reaction

Build:
- agree_with
- pushback
- lived_addition
- what_matters_most
- skepticism

Primary files:
- `backend/app/services/social_belief_engine.py`
- likely new `backend/app/services/social_reaction_brief_service.py`
- `backend/app/services/lab_experiment_service.py`

Lab success conditions:
- `johnnie_perspective` no longer `missing`
- persona-fit scores improve

Phase deep-dive:
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`

### Phase 4: Reaction Brief Synthesis
Goal:
- create a first-class synthesis object before drafting

Build:
- article_view
- johnnie_view
- tension
- content_angle
- evidence_to_use
- stance rationale

Primary files:
- likely new `backend/app/services/social_reaction_brief_service.py`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/lab_experiment_service.py`

Lab success conditions:
- `reaction_brief` no longer `missing`
- repeated template-output feeling drops materially

Phase deep-dive:
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`

### Phase 5: Draft Composition Trace
Goal:
- make draft assembly traceable and less repetitious

Build:
- template trace object
- opener-family id
- closer-family id
- repeated-family penalties

Primary files:
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/lab_experiment_service.py`

Lab success conditions:
- `template_composition` no longer `missing`
- opener repetition falls

Phase deep-dive:
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`

### Phase 6: Evaluation Hardening
Goal:
- evaluate not just draft cleanliness, but source understanding and synthesis quality

Build:
- world-context scoring
- article-stance scoring
- persona-retrieval scoring
- Johnnie-perspective scoring
- synthesis scoring
- persona-fit scoring

Primary files:
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/lab_experiment_service.py`

Lab success conditions:
- benchmark reflects authenticity and synthesis, not only lane cleanliness

Phase deep-dive:
- `workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md`

### Phase 7: Type Matrix Expansion
Goal:
- widen the system beyond plain comment/repost lane testing

Build and test:
- `agree`
- `contrarian`
- `personal story`
- `humor`

Important note:
- `humor` is intentionally later, not first
- humor should only be added after perspective and synthesis layers are real

Primary files:
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_evaluation_engine.py`
- Lab experiment definitions

Phase deep-dive:
- `workspaces/linkedin-content-os/docs/type_matrix_expansion_phase7_implementation_plan.md`

### Phase 8: Small-Model Stability
Goal:
- make the working prototype hold on smaller/cheaper models

Priority rule:
- do not optimize for this until the prototype is genuinely working

Specific model note:
- keep `OpenAI gpt-4o-mini` as an explicit compatibility checkpoint after the synthesis prototype is working
- small-model viability is important, but it is downstream of correctness

## Priority Order
This is the canonical implementation order.

1. `Article stance + world understanding`
2. `Persona retrieval`
3. `Johnnie perspective`
4. `Reaction brief`
5. `Template composition trace`
6. `Evaluation hardening`
7. `Type matrix expansion`
8. `Small-model optimization`

If tradeoffs are required, do not skip `persona retrieval` or `reaction brief` to jump ahead to stylistic polish.

## Lab Contract
Lab is the canonical place to:
- inspect these stages
- show missing slices
- run experiments
- iterate until pass
- write postmortems
- ship stable learnings back into Workspace or Brain

This work belongs in:
- `Lab` first
- then `LinkedIn OS` once the experiment passes

## Shipping Gates
No phase ships back just because the drafts look nicer.

A phase is ready to ship only when:
1. the stage exists as a visible Lab slice
2. the stage can show pass / warn / fail or missing
3. the stage shows evidence and missing fields
4. the stage improves benchmark quality without hiding failure modes

## What This SOP Replaces
This roadmap replaces the habit of:
- tuning phrasing before fixing synthesis
- treating lane quality as persona depth
- assuming article understanding exists because a draft came out
- assuming “sounds good” means “Johnnie perspective is actually modeled”

## Related Files
- `SOPs/_index.md`
- `SOPs/source_system_contract_sop.md`
- `SOPs/brain_workspace_boundary_sop.md`
- `SOPs/persona_grounded_content_generation_sop.md`
- `SOPs/persona_identity_state_sop.md`
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/type_matrix_expansion_phase7_implementation_plan.md`
- `workspaces/linkedin-content-os/docs/social_intelligence_architecture.md`
- `workspaces/linkedin-content-os/docs/social_feed_architecture_plan.md`
- `backend/app/services/social_signal_utils.py`
- `backend/app/services/social_belief_engine.py`
- `backend/app/services/social_technique_engine.py`
- `backend/app/services/social_expression_engine.py`
- `backend/app/services/social_evaluation_engine.py`
- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/services/lab_experiment_service.py`

## Startup Rule
When a task touches any of these areas:
- article understanding
- social response quality
- persona-aware drafting
- comment/repost quality
- Lab observability for content generation

load this SOP during startup.

If the task is specifically about implementing or auditing Phase 1 article/world understanding, also load:
- `workspaces/linkedin-content-os/docs/article_world_understanding_phase1_implementation_plan.md`

If the task is specifically about implementing or auditing Phase 2 persona retrieval, evidence ranking, approved-delta retrieval, or belief/experience selection quality, also load:
- `workspaces/linkedin-content-os/docs/persona_retrieval_phase2_implementation_plan.md`

If the task is specifically about implementing or auditing Phase 3 Johnnie perspective modeling, agreement/pushback/lived-addition logic, or Lab perspective observability, also load:
- `workspaces/linkedin-content-os/docs/johnnie_perspective_phase3_implementation_plan.md`

If the task is specifically about implementing or auditing Phase 4 reaction-brief synthesis, article-view/Johnnie-view packaging, or Lab pre-draft synthesis observability, also load:
- `workspaces/linkedin-content-os/docs/reaction_brief_phase4_implementation_plan.md`

If the task is specifically about implementing or auditing Phase 5 template composition, family tracing, repetition control, or Lab draft-assembly observability, also load:
- `workspaces/linkedin-content-os/docs/template_composition_phase5_implementation_plan.md`

If the task is specifically about implementing or auditing Phase 6 evaluation hardening, benchmark weighting, shipping gates, or Lab scoring observability, also load:
- `workspaces/linkedin-content-os/docs/evaluation_hardening_phase6_implementation_plan.md`

Do not treat this as optional reference material.
This SOP is the canonical roadmap for making the AI Clone workspace actually sound like Johnnie while remaining grounded, observable, and shippable.
