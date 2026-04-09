# AGC Execution Lane

This lane keeps AGC work bounded to `workspaces/agc/` while preserving the standard control chain:

`You -> Neo -> Jean-Claude -> AGC Strategy Agent or Codex -> PM write-back`

## Roles
- `Neo`: intake only
- `Jean-Claude`: execution manager
- `AGC Strategy Agent`: delegated workspace executor
- `Codex workspace runner`: optional direct executor when Jean-Claude needs a bounded local run

## Standard flow
1. Create or update the PM card through the thin trigger path.
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/enqueue_pm_execution_card.py \
     --workspace-key agc \
     --title "<work title>" \
     --reason "<why this matters>"
   ```
2. Have Jean-Claude open the workspace SOP.
   ```bash
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key agc \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
3. Let the AGC workspace agent pick up delegated execution.
   ```bash
   python3 scripts/runners/run_workspace_agent.py \
     --workspace-key agc \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
4. Use direct Codex execution only when Jean-Claude keeps the work in his lane.
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --workspace-key agc \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```

## Guardrails
- Keep code, docs, and notes inside `workspaces/agc/`.
- Read `dispatch/`, `briefings/`, and `memory/execution_log.md` before changing scope.
- Prefer delegated execution through `AGC Strategy Agent`; use direct Codex only when Jean-Claude explicitly owns the packet.
- Every real run ends with standard write-back so the PM card and memory stay aligned.
