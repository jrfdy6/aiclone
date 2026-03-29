# SOP: Persona-Grounded Content Generation

## Purpose
Define the implementation plan for making content generation read persona canon in a structurally grounded way, so the system produces meaningful posts without relying on brittle whitelists or prompt-only band-aids.

This SOP exists because the current system is materially better than before, but it still drifts:

- weakly related operational history can still enter `tech_ai` drafts
- legacy examples can overpower stronger canon if retrieval is too permissive
- proof-bearing chunks and routing hints can get mixed together
- the model can still generalize from a real artifact into the wrong claim

The goal is to fix that at the retrieval and memory-contract layer, not by hardcoding topic whitelists.

## External Guidance That Informs This Plan

### Working patterns seen elsewhere
- Anthropic: context is finite; use the smallest high-signal context possible and prefer hybrid / just-in-time retrieval over dumping everything into the prompt.
- Anthropic: retrieval should be contextualized, hybrid, and reranked instead of relying on embeddings alone.
- LangChain: long-term memory works better when separated into semantic, episodic, and procedural memory rather than treated as one undifferentiated store.
- OpenAI: metadata filtering, result limiting, and evals are first-class parts of retrieval systems.
- Self-RAG / CRAG: retrieval quality should be critiqued before generation, not assumed to be good.
- Lost in the Middle: bigger mixed context is not safer; important evidence gets ignored when buried in the middle.

### Practical implication for this codebase
Do not ask one retrieval lane to do all jobs at once.

Instead:

1. keep `core identity` always in context
2. retrieve `proof` separately from `stories`
3. keep `examples` as a distinct optional lane
4. evaluate whether retrieval quality is strong enough for a proof-led post
5. fail closed to a principle-led post when support is weak

## Current Failure Shape

The current path in `backend/app/routes/content_generation.py` does several good things already:

- bundle-first persona context
- topic anchors
- story anchors
- proof anchors
- editorial second pass

But it still mixes concerns:

- chunk shape is mostly plain text with light tags
- `Use when:` metadata still lives too close to content
- legacy retrieval and bundle retrieval are not fully typed by memory role
- proof selection is still based on lexical overlap more than semantic role
- example posts are filtered by topic, but not yet selected from a typed example bank
- the route still asks the model to infer too much about what counts as proof, what counts as support, and what should be ignored

## Locked Architectural Contract

### Memory roles
Every chunk used for content generation must belong to one of these roles:

- `core`
  - durable identity and rules
  - claims, philosophy, decision principles, voice, guardrails
- `proof`
  - externally defensible artifacts, initiatives, wins, shipped systems, metrics
- `story`
  - episodic support and lived experience
- `example`
  - prior post rhythm and structural examples
- `ambient`
  - optional retrieval support, lowest priority

### Framing layer
Grounding and rhetoric are separate concerns.

- `grounding`
  - decides what is true enough to use
  - controls core / proof / story / example eligibility
- `framing`
  - decides how the post lands
  - preserves the legacy strengths that must not be flattened out of the system

The new grounded path must preserve explicit framing modes such as:

- `contrarian_reframe`
- `agree_and_extend`
- `drama_tension`
- `story_with_payoff`
- `operator_lesson`
- `recognition`
- `warning`
- `reframe`

Rule:
Do not let safety work erase rhetorical sharpness. The system should get more grounded without becoming flatter, safer, or more generic.

### Generation order
The route must compose context in this order:

1. `core`
2. `proof`
3. `story`
4. `example`
5. `ambient`

That order is semantic, not just prompt formatting.

### Retrieval rule
For any request, the system must answer these separately:

1. what is always true about Johnnie?
2. what proof is valid for this topic / audience / domain?
3. what story is allowed to support that proof?
4. what example post is stylistically useful without changing the facts?

### Fail-closed rule
If no strong proof is found for the requested domain:

- allow a principle-led post
- allow a story-led post only if story support is explicitly relevant
- do not borrow weakly related metrics or case studies
- do not invent quantitative outcomes

## Concrete Plan For This Codebase

### Phase 1: Add typed metadata to canonical bundle chunks
Goal: stop treating parsed bundle chunks as mostly plain text.

Add explicit metadata fields inside `backend/app/services/persona_bundle_context_service.py`:

- `memory_role`
- `domain_tags`
- `audience_tags`
- `proof_kind`
- `proof_strength`
- `artifact_backed`
- `example_kind`
- `story_kind`
- `usage_modes`

Source files:

- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/services/persona_bundle_writer.py`
- `knowledge/persona/feeze/history/initiatives.md`
- `knowledge/persona/feeze/history/wins.md`
- `knowledge/persona/feeze/history/story_bank.md`
- `knowledge/persona/feeze/identity/claims.md`

Implementation note:
This can start as deterministic metadata inferred from file path + field structure. It does not require a model.

### Phase 2: Split content retrieval into typed lanes
Goal: stop using one blended retrieval surface for all prompt purposes.

Create a dedicated service, for example:

- `backend/app/services/content_generation_context_service.py`

Responsibilities:

- `load_core_context(...)`
- `retrieve_proof_context(...)`
- `retrieve_story_context(...)`
- `retrieve_example_context(...)`
- `score_grounding_confidence(...)`
- `recommend_framing_modes(...)`

Source files:

- `backend/app/routes/content_generation.py`
- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/services/retrieval.py`

Implementation note:
`core` should be mostly direct include, not similarity retrieval.

### Phase 3: Add domain-aware retrieval constraints
Goal: replace broad lexical overlap with explicit domain compatibility.

For `tech_ai`, require non-core support chunks to match explicit operator / AI domain metadata or terms.

Examples:

- allowed:
  - Brain / AI Clone
  - prompting
  - orchestration
  - workflow systems
  - handoffs
  - routing
- disallowed unless explicitly tagged:
  - generic team management
  - admissions workflow
  - school process improvements
  - broad leadership wins

Source files:

- `backend/app/routes/content_generation.py`
- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/services/retrieval.py`

Implementation note:
This is not a whitelist of files. It is a typed domain gate on support evidence.

### Phase 4: Add retrieval-quality scoring before generation
Goal: make the route decide whether proof is strong enough before asking the model to draft.

Add a grounding evaluator that scores:

- `core_coverage`
- `proof_coverage`
- `proof_relevance`
- `story_relevance`
- `example_relevance`
- `conflict_risk`
- `hallucination_risk`

Possible outputs:

- `proof_ready`
- `principle_only`
- `story_supported`
- `insufficient_grounding`

Source files:

- `backend/app/services/content_generation_context_service.py`
- `backend/app/routes/content_generation.py`

Implementation note:
This can be rule-based first. It does not need an LLM judge initially.

### Phase 5: Change the prompt contract
Goal: stop showing the model a broad mixed persona pile.

Prompt sections should become:

- `CORE IDENTITY`
- `APPROVED PROOF`
- `OPTIONAL STORY SUPPORT`
- `STYLE REFERENCES`
- `GROUNDING MODE`
- `APPROVED FRAMING MODES`

And the route should explicitly tell the model which mode it is in:

- `proof_ready`
- `principle_only`
- `story_supported`

If mode is `principle_only`, the prompt must forbid:

- unsupported named metrics
- unrelated case-study borrowing
- implicit extrapolation from non-AI projects into AI claims

And regardless of grounding mode, the prompt must still preserve:

- contrast
- tension
- agreement / disagreement structure
- drama when it is grounded in real proof
- story payoff when an eligible story actually exists

Source files:

- `backend/app/routes/content_generation.py`

### Phase 6: Replace generic example retrieval with typed example banks
Goal: use examples for rhythm, not truth.

Example posts should be selected by:

- audience
- domain
- post archetype
- tone

not just similarity.

Add or enrich metadata for legacy example chunks so the example lane can answer:

- operator lesson
- contrarian belief
- recognition
- story with takeaway
- initiative update

Source files:

- `backend/app/services/retrieval.py`
- legacy example ingestion or tagging scripts
- `JOHNNIE_FIELDS_PERSONA.md`
- `JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md`

### Phase 7: Add grounding evals
Goal: prove the system is actually improving.

Create a small fixed eval set with topics like:

- `workflow clarity`
- `agent orchestration`
- `AI systems`
- `leadership clarity`
- `relationship-first market development`

For each prompt, track:

- domain correctness
- proof correctness
- unsupported metric count
- off-domain anecdote count
- persona fit
- voice fit

Source files:

- `backend/tests/test_workspace_smoke.py`
- new eval fixtures under `backend/tests/fixtures/` or `scripts/persona/`

## Immediate Sequence

### Step 1
Enrich `persona_bundle_context_service.py` with typed metadata for:

- `core`
- `proof`
- `story`
- `example`

### Step 2
Create `content_generation_context_service.py` and move retrieval composition out of the route.

### Step 3
Implement a rule-based grounding scorer and make the route choose a drafting mode.

### Step 4
Update prompts to consume the new typed context sections.

### Step 5
Add topic evals and production spot checks.

## Validation Gates

### Contract tests
- `tech_ai` requests do not admit generic operations stories as proof unless explicitly AI-tagged
- proof chunks and story chunks are retrieved by different logic paths
- `core` chunks are always present in the prompt
- `principle_only` mode emits no unsupported metrics
- example posts can influence rhythm without influencing factual proof selection

### Production checks
- `workflow clarity` and `agent orchestration` return AI/operator-grounded posts
- `examples_used` is either domain-relevant or empty
- no unsupported percentages or transformed metrics appear in live output
- `persona_context` still reflects the canonical bundle immediately

## What This Replaces
This plan replaces:

- ever-expanding prompt instructions
- implicit “hope the model ignores bad support” behavior
- topic-specific whitelists as the primary control mechanism

with:

- typed memory
- typed retrieval
- retrieval-quality gating
- explicit generation modes

## Related Files
- `SOPs/_index.md`
- `memory/roadmap.md`
- `workspaces/linkedin-content-os/backlog.md`
- `backend/app/routes/content_generation.py`
- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/services/retrieval.py`
