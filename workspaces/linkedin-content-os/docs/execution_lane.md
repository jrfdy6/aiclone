# FEEZIE OS Execution Lane

FEEZIE OS has two bounded local lanes:

- content generation: `Frontend/OpenClaw -> Railway thin content route -> local launchd bridge -> Codex if needed`
- PM-backed workspace execution: `You -> Neo -> Jean-Claude -> direct Codex execution -> PM write-back`

## Primary content lane
1. Enqueue content work through the thin trigger instead of direct model routes.
   ```bash
   cd /Users/neo/.openclaw/workspace
   python3 scripts/enqueue_content_generation_job.py \
     --topic "<topic>" \
     --context "<angle>" \
     --wait --include-artifacts
   ```
2. Let the local bridge claim the job from Railway.
   ```bash
   python3 scripts/run_local_codex_bridge.sh
   ```
3. Review the generated draft artifacts under `drafts/`, `plans/`, and the job artifact record exposed through Railway.

## PM-backed workspace lane
1. Open non-draft work through the PM thin trigger.
   ```bash
   python3 scripts/enqueue_pm_execution_card.py \
     --workspace-key feezie-os \
     --title "<work title>" \
     --reason "<why this matters>"
   ```
2. Let Jean-Claude open the local SOP for the workspace packet.
   ```bash
   python3 scripts/runners/run_jean_claude_execution.py \
     --workspace-key feezie-os \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```
3. Execute directly with Codex when the packet is bounded and ready.
   ```bash
   python3 scripts/runners/run_codex_workspace_execution.py \
     --workspace-key feezie-os \
     --card-id <pm-card-id> \
     --api-url https://aiclone-production-32dc.up.railway.app
   ```

## Guardrails
- Keep public posting behind explicit owner approval.
- Use the thin content queue, not legacy direct `/generate`, in production.
- Read `docs/operating_model.md`, `dispatch/*.json`, `briefings/*.md`, and `memory/execution_log.md` before changing behavior.
- Treat `drafts/` and PM cards as review surfaces; do not post directly from the execution lane.
