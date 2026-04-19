# Brain Workspace Exchange Protocol

This protocol defines how Brain and workspaces exchange state without creating duplicate planning systems.

## Purpose

Brain is the portfolio-wide interpretation layer.

Workspaces are local execution layers.

PM, standups, Chronicle, and canonical memory are the exchange protocol between them.

The goal is to let every workspace interact with the AI Clone project without letting any workspace become a second brain.

## Existing Systems To Reuse

Do not rebuild these surfaces:

- Workspace registry and aliases: `backend/app/services/workspace_registry_service.py`
- Runtime contracts and execution defaults: `backend/app/services/workspace_runtime_contract_service.py`
- PM card truth and execution queue: `backend/app/services/pm_card_service.py`
- Standup queue and promotion: `backend/app/services/standup_service.py`
- Shared source system: `SOPs/source_system_contract_sop.md`
- LinkedIn/FEEZIE live source snapshot: `backend/app/services/workspace_snapshot_service.py`
- Snapshot persistence: `backend/app/services/workspace_snapshot_store.py`

New Brain work should compose these systems instead of creating parallel registries, task stores, or source-ingest lanes.

## Workspace To Brain

Each workspace should surface:

- latest local state
- latest briefing
- latest execution result or execution-log tail
- active PM cards
- latest standup or queued standup
- blockers
- local analytics or feedback summaries
- source signals that may deserve global interpretation
- last write-back timestamp

Workspace output remains local until Brain decides it has cross-workspace, durable-memory, persona, standup, or PM meaning.

## Brain To Workspace

Brain may send a workspace:

- digested global signal
- workspace-scoped source interpretation
- standup agenda
- PM work with an execution contract
- canonical-memory context
- explicit non-action advisory notes

Brain should not send raw source material into a workspace as if it were already a local operating rule.

## Brain Signal

A Brain Signal is the generic review object for signal that is not necessarily persona canon.

It may come from:

- source intelligence
- workspace execution
- cron outputs
- meeting transcripts
- Codex / OpenClaw Chronicle entries
- PM write-back
- owner reactions

Persona deltas remain valid, but they are one downstream lane. Brain Signal is the upstream review object for portfolio interpretation.

## Routing Rule

The default flow is:

`signal -> Brain Signal -> executive interpretation -> one or more justified routes`

Valid routes:

- source-only
- canonical memory
- persona canon
- standup
- PM truth
- workspace-local follow-up
- ignore / no-action

PM is the narrowest route. It requires concrete work, a clear owner, and a bounded title.

## Portfolio Snapshot Rule

Brain must observe every active workspace, not only FEEZIE OS.

FEEZIE OS remains identity-adjacent and public-facing, so it receives more strategic attention. That does not make it the only workspace Brain should see.

The portfolio snapshot should include:

- `shared_ops`
- `feezie-os` / `linkedin-os`
- `fusion-os`
- `easyoutfitapp`
- `ai-swag-store`
- `agc`

Each workspace summary should be compact enough for Brain dashboards and crons, but detailed enough to answer:

`Does this workspace need Brain attention right now?`

## Exchange Test

Before adding a new route, card, snapshot, or queue, ask:

1. Does an existing service already own this state?
2. Is this global interpretation or local execution?
3. Is the route advisory, durable memory, standup, PM, persona, or workspace-local?
4. What artifact proves the route happened?
5. Where does execution write back?

If those answers are unclear, keep the signal in Brain review or standup instead of creating PM work.
