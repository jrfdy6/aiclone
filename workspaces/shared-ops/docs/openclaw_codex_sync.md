# OpenClaw ↔ Codex Workflow Sync

This note documents how a standup-seeded PM card travels from OpenClaw into the new Codex execution layer and back again. Use it as the canonical reference when verifying the loop or debugging stale cards like `Align OpenClaw and Codex workflow sync`.

## End-to-end flow
1. **Card creation** – OpenClaw standups or `scripts/enqueue_pm_execution_card.py` create a PM card with `workspace_key`, `front_door_agent`, and execution payload. Trigger keys are derived from the title and workspace so reruns stay idempotent.
2. **Jean-Claude dispatch** – `scripts/runners/run_jean_claude_execution.py` (launchd id `jean_claude_execution`) reads the queued card, writes `/workspaces/<workspace>/dispatch/*_{sop,work_order}.json`, updates the PM card to `running`, and logs to `memory/runner-ledgers/jean-claude-execution.jsonl`.
3. **Codex execution** – `scripts/runners/run_codex_workspace_execution.py` (launchd id `codex_workspace_execution`) polls cards with `executor_status=queued`, rebuilds or reuses the work packet, launches `codex exec`, and writes the structured result back through `scripts/runners/write_execution_result.py --force-api`. Successful runs land in `memory/runner-ledgers/codex-workspace-execution.jsonl`.
4. **Write-back + Chronicle** – The writer updates PM status, appends Chronicle via the execution result contract, and updates workspace memory (`memory/YYYY-MM-DD.md`, `workspaces/<workspace>/memory/execution_log.md`). Wrapper automation handles these writes; Codex packets must not touch memory files directly.

## Smoke test
- Dry-run a payload: `python3 scripts/run_pm_execution_smoke.py` (prints JSON plan + commands).
- Full loop: `python3 scripts/run_pm_execution_smoke.py --live --api-url https://aiclone-production-32dc.up.railway.app --worker-id smoke-codex`.
- Inspect resulting ledgers/memos plus the PM card’s `latest_execution_result` to confirm the loop.

## Key files
- Launchd plists: `automations/launchd/com.neo.jean_claude_execution.plist`, `automations/launchd/com.neo.codex_workspace_execution.plist`.
- Scripts: `scripts/enqueue_pm_execution_card.py`, `scripts/run_pm_execution_smoke.py`, `scripts/runners/run_jean_claude_execution.py`, `scripts/runners/run_codex_workspace_execution.py`.
- Tests: `backend/tests/test_pm_execution_smoke.py`, `backend/tests/test_codex_workspace_execution_runner.py`.
- Ledgers / diagnostics: `memory/runner-ledgers/{jean-claude-execution,codex-workspace-execution}.jsonl`, `memory/codex_session_handoff.jsonl`.

## Known gotchas
- `run_codex_workspace_execution.py` now falls back to reconstruct queue entries even when local backend helpers fail to import (e.g., missing `numpy`). Ensure `executor_status` is `queued` before each run; the runner will refuse cards already marked `running`.
- `write_execution_result.py` must run in API mode when local DB URLs are unavailable. The Codex runner clears `OPEN_BRAIN_DATABASE_URL`, `BRAIN_VECTOR_DATABASE_URL`, and `DATABASE_URL` before invoking the writer.
- Codex CLI must be installed (`codex exec …`). Launchd jobs assume the binary is on `$PATH` and that the workspace repo is the working directory.

## Follow-ups to monitor
- Keep the smoke test runner updated anytime the PM payload schema changes.
- Expand log review so accountability sweeps can prove when the Codex runner last touched each workspace.
- Once network/API access is available, schedule a weekly live smoke run so stale cards are caught automatically instead of via manual sweeps.
