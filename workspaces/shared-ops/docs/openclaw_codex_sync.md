# OpenClaw ↔ Codex Workflow Sync

This note documents how a standup-seeded PM card travels from OpenClaw into the Codex execution layer and back again. Use it as the canonical reference when verifying the loop or debugging stale cards like `Align OpenClaw and Codex workflow sync`.

Latest dated alignment review: `workspaces/shared-ops/docs/openclaw_codex_sync_alignment_2026-04-27.md`.

## End-to-end flow
1. **Card creation** – OpenClaw standups or `scripts/enqueue_pm_execution_card.py` create a PM card with `workspace_key`, `front_door_agent`, and execution payload. Trigger keys are derived from the title and workspace so reruns stay idempotent.
2. **Jean-Claude dispatch** – `scripts/runners/run_jean_claude_execution.py` (launchd id `jean_claude_execution`) reads the queued card, writes `/workspaces/<workspace>/dispatch/*_{sop,work_order}.json`, updates the PM card to `running`, and logs to `memory/runner-ledgers/jean-claude-execution.jsonl`.
3. **Codex execution** – `scripts/runners/run_codex_workspace_execution.py` (launchd id `codex_workspace_execution`) now has two runnable lanes:
   - PM-backed Codex packets: poll cards with `executor_status=queued`, rebuild or reuse the work packet, launch `codex exec`, then write the structured result back through `scripts/runners/write_execution_result.py --force-api`.
   - Host-action automations: detect runnable `host_action_automation` cards, run the matching automation flow directly inside the runner, then patch or close the related PM card and source card without launching Codex.
   Successful runs for either lane land in `memory/runner-ledgers/codex-workspace-execution.jsonl`.
4. **Write-back + Chronicle** – The writer updates PM status, appends Chronicle via the execution result contract, and updates workspace memory (`memory/YYYY-MM-DD.md`, `workspaces/<workspace>/memory/execution_log.md`). Wrapper automation handles these writes; Codex packets must not touch memory files directly.

## Host-action automation lane
`run_codex_workspace_execution.py` now carries a small automation lane for host-confirmed or autostart follow-through that still belongs inside the PM execution loop. Current automation ids:

- `fallback_watchdog_writeback` – refreshes the saved watchdog artifact, writes the source execution result, and closes the host card after proof exists.
- `standup_prep_writeback` – regenerates fresh standup prep proof, verifies the expected decision-loop payload, and closes the host card.
- `execution_result_writeback_proof` – checks that writer artifacts exist for the source PM card and closes the host card with proof items.
- `linkedin_scheduled_writeback` – records the LinkedIn scheduling receipt back into the canonical FEEZIE docs and artifacts and closes the host card after the schedule proof is on disk; queued cards run immediately, while `ready` cards only autostart after the confirmation artifact or receipt already exists.

This lane matters for OpenClaw ↔ Codex sync because the same Codex runner ledger now records both coding packets and bounded host-action completions. Executive reviews should read `memory/runner-ledgers/codex-workspace-execution.jsonl` as the canonical runner trace for both behaviors.

## Smoke test
- Dry-run a payload: `python3 scripts/run_pm_execution_smoke.py` (prints JSON plan + commands).
- Full loop: `python3 scripts/run_pm_execution_smoke.py --live --api-url https://aiclone-production-32dc.up.railway.app --worker-id smoke-codex`.
- Inspect resulting ledgers/memos plus the PM card’s `latest_execution_result` to confirm the loop.
- The live smoke test still validates the Codex-packet lane specifically. Host-action automations are verified by their own source-card result, host-card closure proof, and the Codex runner ledger entry.

## Key files
- Launchd plists: `automations/launchd/com.neo.jean_claude_execution.plist`, `automations/launchd/com.neo.codex_workspace_execution.plist`.
- Scripts: `scripts/enqueue_pm_execution_card.py`, `scripts/run_pm_execution_smoke.py`, `scripts/runners/run_jean_claude_execution.py`, `scripts/runners/run_codex_workspace_execution.py`.
- Writer: `scripts/runners/write_execution_result.py`.
- Tests: `backend/tests/test_pm_execution_smoke.py`, `backend/tests/test_codex_workspace_execution_runner.py`.
- Ledgers / diagnostics: `memory/runner-ledgers/{jean-claude-execution,codex-workspace-execution}.jsonl`, `memory/codex_session_handoff.jsonl`.

## Known gotchas
- `run_codex_workspace_execution.py` now falls back to reconstruct queue entries even when local backend helpers fail to import (e.g., missing `numpy`). Ensure `executor_status` is `queued` before each run; the runner will refuse cards already marked `running`.
- Host-action automation cards do not use `executor_status=queued`; they run when `host_action_automation.state` is `queued`, or for selected automation types when state is `ready` with `autostart=true` and `requires_host_confirmation=false`.
- `linkedin_scheduled_writeback` is the exception to the generic `ready` rule: a `ready` LinkedIn card only becomes runnable when the queue id plus scheduled timestamp can be recovered and a confirmation artifact or `scheduled_receipt.json` already exists.
- `write_execution_result.py` must run in API mode when local DB URLs are unavailable. The Codex runner clears `OPEN_BRAIN_DATABASE_URL`, `BRAIN_VECTOR_DATABASE_URL`, and `DATABASE_URL` before invoking the writer.
- The Codex runner is now allowed to complete certain follow-through tasks without launching `codex exec`; when reviewing logs, distinguish `model=host-action-automation` entries from real Codex CLI executions.
- Codex CLI must be installed (`codex exec …`). Launchd jobs assume the binary is on `$PATH` and that the workspace repo is the working directory.

## Follow-ups to monitor
- Keep the smoke test runner updated anytime the PM payload schema changes.
- Expand log review so accountability sweeps can prove when the Codex runner last touched each workspace.
- Once network/API access is available, schedule a weekly live smoke run so stale cards are caught automatically instead of via manual sweeps.
