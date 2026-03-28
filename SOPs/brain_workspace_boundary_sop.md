# SOP: Brain vs Workspace Boundary

## Purpose
Keep global knowledge, persona, briefs, docs, and telemetry in `Brain`, while reserving `Workspace` for project-local execution.

This SOP exists to stop a slow architectural drift where global system state gets rebuilt inside child workspaces.

## Canonical Rule
`Brain` is the canonical home for global understanding.

`Workspace` is the canonical home for project-specific execution.

If a feature is mainly about:
- global persona
- daily briefs
- automation telemetry
- knowledge docs
- cross-project source intelligence
- worldview review

it belongs in `Brain`.

If a feature is mainly about:
- one project's strategy
- one project's drafts
- one project's research lane
- one project's tasks
- one project's agents
- one project's local experiments

it belongs in that `Workspace`.

## Surface Ownership

### Brain owns
- dashboard-level system telemetry
- daily briefs
- persona review and promotion flow
- agreement / disagreement / nuance capture
- personal story attachment
- wording refinement before promotion
- automation health and automation inventory
- knowledge docs and canonical doc browsing
- global source intelligence that feeds multiple consumers

### Workspace owns
- project-local planning
- project-local feed execution
- project-local drafts
- project-local reaction queues
- project-local experiments
- project-local task state
- project-specific research and signals

## Allowed Workspace Behavior
Workspace is still allowed to:
- surface quick captures
- let the user approve a snippet quickly
- show project-local summaries
- show a thin status card that points back to Brain

But Workspace should not become the primary home for:
- persona lifecycle review
- daily brief review
- global docs browsing
- automation telemetry reconciliation
- cross-project source-system interpretation

## Shared Review Rule
- Workspace snippet approval counts as real approval at the shared `persona_deltas` layer.
- Brain should not require duplicate approval for that same snippet.
- Brain remains the place for unresolved review:
  - agreement / disagreement
  - nuance
  - story context
  - wording refinement
  - promotion selection
- Neither surface auto-writes canonical persona files under `knowledge/persona/feeze/**`.

## Long-form Source Rule
Long-form media is upstream system input, not a Workspace-only feature.

The same source asset should be able to feed:
- Brain daily briefs
- Brain persona review
- planner overlays
- project-local post seeds
- feed routing, only when a segment is truly reaction-ready

This means transcript/media intelligence may appear in a project workspace,
but Brain is the canonical global home for understanding what the source means.

## Current Product Direction
The current intended direction is:
- keep `Brain` as the control plane
- keep `Workspace` as the execution plane
- allow thin mirrors or deep links from Workspace into Brain
- prevent global state from being silently duplicated across both surfaces

## Current Gaps To Fix
These are now explicit roadmap targets, not vague observations:
- Brain persona needs the richer response controls back:
  - agree
  - disagree
  - nuance
  - personal story
  - wording/context refinement
- Brain telemetry needs one reconciled source of truth so Dashboard and Automations do not show conflicting numbers without explanation.
- Brain Docs must surface knowledge docs and canonical operating docs instead of leaving the tab empty while docs already exist.
- Workspace should stop acting as the primary home for global source intelligence and persona-state interpretation.

## Decision Test
Before building a new surface or card, ask:

1. Is this about one project or the whole system?
2. Does it need global memory, persona, docs, or automation context?
3. Would duplicating this in multiple workspaces create drift?

If the answer to `2` or `3` is yes, put it in `Brain`.

## Related Files
- `AGENTS.md`
- `CODEX_STARTUP.md`
- `SOPs/source_system_contract_sop.md`
- `memory/roadmap.md`
- `workspaces/linkedin-content-os/README.md`
- `workspaces/linkedin-content-os/backlog.md`
