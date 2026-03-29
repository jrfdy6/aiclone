# SOP: Persona Identity State Contract

## Purpose
Define how `Brain` should represent a tight persona core, absorb supporting bundles without losing that core, and make identity evolution visible instead of implicit.

This SOP exists because canon persistence alone is not enough. The system also needs to show:
- what is core
- what is supporting bundle material
- what reinforced the core
- what reshaped the core
- what remains contextual or unresolved

## Canonical Rule
`Core identity` and `bundle memory` are not the same thing.

The system must preserve a tight durable center while still absorbing stories, wins, initiatives, worldview shifts, and new evidence over time.

Every durable promotion should end in one of four states:
- `reinforces_core`
- `reshapes_core`
- `context_only`
- `unresolved_tension`

That classification should be explicit, not inferred from file placement alone.

## Core vs Bundle Model

### Core
Core is the durable center of identity and should change slowly.

Primary core files:
- `knowledge/persona/feeze/identity/philosophy.md`
- `knowledge/persona/feeze/identity/decision_principles.md`
- `knowledge/persona/feeze/identity/claims.md`
- `knowledge/persona/feeze/identity/VOICE_PATTERNS.md`

Core should answer:
- what Johnnie believes
- how Johnnie decides
- how Johnnie sounds
- what Johnnie can credibly claim over time

### Bundles
Bundles are absorbed supporting materials. They matter, but they are not automatically the core.

Primary bundle files:
- `knowledge/persona/feeze/history/story_bank.md`
- `knowledge/persona/feeze/history/wins.md`
- `knowledge/persona/feeze/history/initiatives.md`
- `knowledge/persona/feeze/history/timeline.md`
- `knowledge/persona/feeze/prompts/content_pillars.md`

Bundles should answer:
- what happened
- what was learned
- what was proven
- what examples, evidence, and stories can support the core

## Brain Surface Rule
This belongs in a separate `Brain` tab.

Working name:
- `Identity State`

It should not be buried inside Persona review cards or lifecycle audit cards.

The `Identity State` tab should show:
- current core summary
- absorbed bundle changes
- recent reinforcements to core
- recent reshapes to core
- active tensions / unresolved questions
- provenance back to the source promotion items

## Required Relationship States
Every durable canon change should be classifiable as:

### Reinforces Core
The new material strengthens an existing belief, principle, claim, or voice pattern.

### Reshapes Core
The new material changes how the core should be described, prioritized, or framed.

### Context Only
The new material is useful as story, proof, example, initiative, or brief context, but should not change the core directly.

### Unresolved Tension
The new material is meaningful enough to keep, but it conflicts with or pressures the current core and needs explicit review before reshaping anything.

## Tab Responsibilities
The future `Identity State` tab should do three jobs:

1. Show where identity stands now.
2. Show what recently changed and why.
3. Separate durable self-understanding from contextual material.

It should not become:
- another generic doc browser
- another review queue
- another content-generation screen

## Project Plan

### Phase 1: Define The Relationship Contract
Goal: stop treating bundle writes as if file placement alone explains identity impact.

Implementation expectations:
- add a relationship field to committed canon items:
  - `reinforces_core`
  - `reshapes_core`
  - `context_only`
  - `unresolved_tension`
- add a short explanation field for why that classification was chosen
- preserve provenance to:
  - source review item
  - source file
  - committed bundle file

### Phase 2: Build An Identity-State Aggregation Layer
Goal: compute a current identity readout from core files plus classified canon events.

Implementation expectations:
- create a backend service that can summarize:
  - current core
  - recent reinforcements
  - recent reshapes
  - unresolved tensions
- keep bundle content and core content distinct in the aggregation model
- never let bundle volume automatically overwrite the core

### Phase 3: Add A Dedicated Brain Tab
Goal: give Brain a first-class identity-governance surface.

Implementation expectations:
- separate `Identity State` tab in `frontend/app/brain/`
- clear sections for:
  - `Core`
  - `Recently Absorbed`
  - `Reshaped Core`
  - `Active Tensions`
- link each visible item back to:
  - its source promotion
  - its target file
  - its commit state

### Phase 4: Connect Identity State To Content Generation
Goal: make content generation use the tight core first and the bundles second.

Implementation expectations:
- content route reads:
  1. core summary
  2. relevant supporting bundle material
  3. examples / retrieval lane
- bundle material can support or exemplify the core
- bundle material should not drown out core identity in prompts

### Phase 5: Add Drift Guardrails
Goal: keep identity evolution legible over time.

Implementation expectations:
- validate that core files remain populated
- validate that bundle absorption does not silently erase philosophy, stories, wins, or decision principles
- keep an explainable ledger of:
  - reinforced beliefs
  - reshaped beliefs
  - unresolved tensions

## Pin / Priority Rule
This project is real, but it is currently pinned.

Do not treat it as the active build priority until the current persona-to-content path is stronger.

The active priority remains:
- make the system read persona canon consistently
- make the system generate meaningful posts from that canon
- make content quality reliable before adding another major Brain tab

## Success Criteria
When this work is eventually active, success means:
- the system has a tight visible core
- bundles are absorbed without collapsing into core by default
- the operator can see how recent thoughts and experiences shaped identity
- content generation reads the core first and uses bundles as supporting evidence

## Related Files
- `SOPs/_index.md`
- `SOPs/persona_canon_promotion_sop.md`
- `SOPs/brain_workspace_boundary_sop.md`
- `memory/roadmap.md`
- `workspaces/linkedin-content-os/backlog.md`
