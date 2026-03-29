# SOP: Persona Canon Promotion Contract

## Purpose
Define the implementation contract for promoting Brain review items into the canonical persona bundle under `knowledge/persona/feeze/**` without leaking review voice into canon.

This SOP exists because the current system can persist canon, but its promotion items are still too thin for semantic fields like `Value to persona` and `Public-facing proof`.

## Current Failure
The current path is:

1. Brain selects promotion fragments.
2. The backend normalizes those fragments into thin promotion items.
3. The writer maps those thin items directly into canonical bundle fields.

That works for low-semantic targets like some claims or phrases, but it fails for `history/initiatives.md` because `initiatives` fields require semantic meaning, not raw narrative text.

## Locked Contract

### Source Priority
Use this anchor order for initiative extraction:

`artifact / output` → `delta / change` → `review note`

- `artifact / output` is mandatory for grounded initiative promotion.
- `delta / change` refines meaning.
- `review note` is interpretive only and must never become proof by itself.

### Field Semantics
For `history/initiatives.md`:

- `Purpose`
  - what the initiative is trying to do
- `Value to persona`
  - what durable capability, positioning, or leverage this adds to canon
- `Public-facing proof`
  - what externally legible evidence supports that claim

### Hard Gate
For `history/initiatives.md`, a strong artifact/output anchor is required.

- clear artifact/output present → allow promotion
- weak or ambiguous artifact/output → hold or reroute
- no artifact/output → block promotion

This is a hard boundary, not a heuristic preference.

## Implementation Plan

### Phase 1: Expand The Promotion Item Contract
Goal: stop treating a promotion item as only `content + evidence + label`.

Add an intermediate promotion record with explicit semantic slots:

- `artifact_summary`
- `artifact_kind`
- `artifact_ref`
- `delta_summary`
- `review_interpretation`
- `capability_signal`
- `positioning_signal`
- `leverage_signal`
- `proof_signal`
- `proof_strength`
- `gate_decision`
- `gate_reason`

Source files:

- `frontend/app/brain/BrainClient.tsx`
- `backend/app/services/persona_promotion_utils.py`
- `backend/app/models/brain.py`

### Phase 2: Add Extraction Before Writing
Goal: extract meaning before any canon writer sees the item.

Create a dedicated extraction layer, for example:

- `backend/app/services/persona_promotion_extractor.py`

Responsibilities:

- derive semantic slots from `A -> B -> C`
- never let review-note text stand in as proof
- keep target-specific logic separate:
  - `claims`
  - `story_bank`
  - `initiatives`
  - `voice_patterns`

For `initiatives`, extraction must prefer:

1. artifact/output references
2. delta/change summaries
3. review interpretation only as supporting context

### Phase 3: Enforce The Initiative Gate
Goal: prevent canon pollution before the writer runs.

In the promotion service:

- if target file is `history/initiatives.md`
- and no strong artifact/output signal is present
- then do not commit the item to canon

Allowed outcomes:

- block the promotion
- keep it in Brain review
- reroute it to a different canonical target if semantics fit better

Source files:

- `backend/app/services/persona_promotion_service.py`
- `backend/app/routes/brain.py`
- `frontend/app/brain/BrainClient.tsx`

### Phase 4: Make Writers Consume Semantic Fields
Goal: make writers deterministic and safe.

For `history/initiatives.md`, the writer should consume extracted semantic fields, not review text:

- `Purpose` ← `artifact_summary` or extracted initiative purpose
- `Value to persona` ← `capability_signal` + `positioning_signal` + `leverage_signal`
- `Public-facing proof` ← `proof_signal`

Do not map these directly from:

- `owner_response_excerpt`
- `delta.notes`
- `evidence` when that evidence is only reflective commentary

Source files:

- `backend/app/services/persona_bundle_writer.py`
- `knowledge/persona/feeze/history/initiatives.md`

### Phase 5: Keep Persistence And Content In Sync
Goal: make committed canon durable and immediately usable.

Requirements:

- local bundle sync remains the durability path
- committed overlay remains the immediate runtime/content path
- both read the same semantic extraction output

That means:

- local writes to `knowledge/persona/feeze/**` stay authoritative across deploys
- content generation keeps reading committed canon immediately through the committed overlay + bundle-first context path

Source files:

- `automations/persona_bundle_sync.py`
- `backend/app/services/persona_bundle_context_service.py`
- `backend/app/routes/content_generation.py`

## Validation Gates

### Unit / Contract Tests
- initiative promotion fails when no artifact/output signal exists
- initiative promotion succeeds when artifact/output is explicit
- review-note text is not written verbatim into `Value to persona` or `Public-facing proof`
- rerouted promotions preserve user review history without corrupting canon

### Production Validation
- immediate: commit one artifact-backed Brain item and verify:
  - runtime canon updates
  - local bundle sync writes the correct file
  - content generation sees the new canon immediately
- immediate negative case: attempt initiative promotion with no artifact anchor and verify:
  - commit is blocked or rerouted
  - no new initiative entry is written

### Benchmark Gate
- `0` initiative entries written from review-note-only evidence
- `100%` of committed initiative entries have explicit artifact/output grounding
- content route still resolves committed canon immediately after promotion

## Current Status
Defined, but not yet enforced in code.

The system now has:

- persistent local bundle sync
- committed runtime overlay
- bundle-first content generation

But it still needs:

- semantic extraction
- artifact-gated initiative promotion
- target-specific writer inputs

## Related Files
- `SOPs/_index.md`
- `SOPs/brain_workspace_boundary_sop.md`
- `memory/roadmap.md`
- `workspaces/linkedin-content-os/backlog.md`
