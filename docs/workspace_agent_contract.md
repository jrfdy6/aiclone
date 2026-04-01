# Workspace Agent Contract

This contract defines the dedicated execution agents that live inside individual workspaces.

They operate under:
- `Neo` at the executive level
- `Jean-Claude` as execution manager
- `Yoda` as strategic overlay

## 1. Role

A workspace agent:
- executes only inside one workspace
- owns no cross-workspace memory
- receives SOPs from `Jean-Claude`
- writes results back into the same PM card and canonical memory loop
- receives its bounded work order from `scripts/runners/run_workspace_agent.py`

## 2. Scope

Each workspace agent should be limited to:
- its workspace files
- its workspace SOPs and briefings
- its workspace docs
- the linked PM cards for that workspace

It should not:
- read or write other workspace state
- create cross-workspace plans
- override executive priorities

## 3. Operating Loop

1. executive standup decides the next move
2. `Jean-Claude` opens an SOP
3. workspace agent executes inside the workspace
4. workspace agent writes result back through the execution-result writer
5. `Jean-Claude` carries the result back up to executive standup

The delegated handoff path is:
- Jean-Claude writes an SOP into the workspace lane
- the workspace agent runner opens a workspace-local work order and intake briefing
- the workspace agent is the primary executor for that workspace lane
- if the workspace agent returns a blocked result, the same PM card is re-queued to `Jean-Claude` for manager intervention
- the workspace agent executes and reports back through the shared PM card

## 4. Memory Rule

Workspace memory must stay inside the workspace lane.

The only information that should move upward is:
- the briefing
- the PM update
- the Chronicle/result signal needed by executive leadership

Workspace-local artifacts should stay under that workspace root, including:
- `dispatch/`
- `briefings/`
- `agent-ledgers/`
- `memory/`
