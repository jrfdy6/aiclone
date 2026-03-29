# Staged Content Generation Map

This map replaces the old "one overloaded prompt" approach with a staged pipeline that keeps Brain as the control plane while narrowing what each model call is allowed to do.

## Keep
- Brain review, promotion, and artifact gate.
- Canonical persona bundle under `knowledge/persona/feeze/**`.
- Typed memory lanes:
  - `core`
  - `proof`
  - `story`
  - `example`
- Grounding modes from `content_generation_context_service.py`.

## Refactor
- Move generation away from one giant writing prompt.
- Use a staged pipeline inside `backend/app/routes/content_generation.py`:
  1. `planner`
     - deterministic
     - selects strategic claim, proof packet, story beat, and framing mode
     - produces explicit option briefs
  2. `writer`
     - writes from the planned briefs only
     - sees good style references
     - does not see avoid-pattern examples as positive context
  3. `critic`
     - rewrites generic or weak phrasing
     - checks against avoid-pattern examples
     - preserves approved proof and references
  4. `local enforcement`
     - repairs flat openings
     - forces proof support in `proof_ready` mode

## Stop Growing
- Do not keep expanding the monolithic content prompt as the main strategy.
- Do not treat more context as the default fix.
- Do not let negative examples live in the main writer context as if they were normal examples.

## Operational Rules
- Complexity belongs in:
  - canon structure
  - retrieval
  - planning
  - evaluation
  - orchestration
- Complexity does not belong in:
  - one giant writer prompt

## Success Criteria
- Posts lead with a strategic claim, not a stat or vague opener.
- Proof supports the claim instead of replacing it.
- Good examples shape rhythm and structure.
- Avoid-pattern examples are used by the critic, not copied by the writer.
- Diagnostics expose:
  - `generation_strategy`
  - `planned_option_briefs`
  - `grounding_mode`
  - `primary_claims`
  - `proof_packets`

## Next Follow-On
- Add a lightweight eval harness for:
  - thesis sharpness
  - voice resemblance
  - proof fidelity
  - generic opener rejection
- Consider a fast diagnostics-only mode so prompt/context checks do not require a full draft call.
