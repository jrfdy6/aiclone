# AI Swag Store Execution Lane

AI Swag Store runs as a delegated workspace lane:

`You -> Neo -> Jean-Claude -> Commerce Growth Agent or Codex -> PM write-back`

## Roles
- `Neo`: intake and prioritization
- `Jean-Claude`: execution manager
- `Commerce Growth Agent`: default workspace executor
- `Codex workspace runner`: fallback for bounded direct execution

## Standard flow
1. Open the work through the thin PM trigger.
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/enqueue_pm_execution_card.py \
     --workspace-key ai-swag-store \
     --title "<work title>" \
     --reason "<why this matters>"
   ```
2. Let Jean-Claude turn the card into a local SOP.
   ```bash
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key ai-swag-store \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
3. Let the workspace agent pick up execution.
   ```bash
   python3 scripts/runners/run_workspace_agent.py \
     --workspace-key ai-swag-store \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
4. Use direct Codex execution only if Jean-Claude explicitly keeps the work in his own lane.
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --workspace-key ai-swag-store \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```

## Guardrails
- Keep merchandising, demand-test, and ops artifacts inside `workspaces/ai-swag-store/`.
- Read the latest `dispatch/*.json`, `briefings/*.md`, and `memory/execution_log.md` before executing.
- Keep experimentation traceable back to the PM card so Jean-Claude can review outcomes cleanly.
- If the packet is not implementation-ready, return it for manager clarification instead of improvising scope.
