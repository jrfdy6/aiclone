# EasyOutfitApp Execution Lane

EasyOutfitApp stays on the delegated workspace pattern:

`You -> Neo -> Jean-Claude -> Easy Outfit Product Agent or Codex -> PM write-back`

## Roles
- `Neo`: front-door intake
- `Jean-Claude`: execution manager
- `Easy Outfit Product Agent`: default workspace executor
- `Codex workspace runner`: direct executor for bounded local packets

## Standard flow
1. Open work through the thin PM contract.
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/enqueue_pm_execution_card.py \
     --workspace-key easyoutfitapp \
     --title "<work title>" \
     --reason "<why this matters>"
   ```
2. Have Jean-Claude create the SOP and briefing.
   ```bash
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key easyoutfitapp \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
3. Let the workspace agent execute the delegated packet.
   ```bash
   python3 scripts/runners/run_workspace_agent.py \
     --workspace-key easyoutfitapp \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
4. Use direct Codex execution when Jean-Claude owns the implementation personally.
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --workspace-key easyoutfitapp \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```

## Guardrails
- Stay inside `workspaces/easyoutfitapp/` for docs, memory, and code context.
- Read `docs/README.md`, the latest packet in `dispatch/`, and `memory/execution_log.md` before execution.
- Keep recommendation-quality work grounded in the explicit PM objective, not generic product ideas.
- Post results back through the standard writer path so PM and memory remain consistent.
