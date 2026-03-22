# SOP: Worktree Hygiene (OpenClaw Boot)

## Purpose
Ensure each OpenClaw boot cycle starts from a clear picture of what files changed so the system doesn’t accidentally commit append-only memory artifacts or generated snapshots.

## Scope
- Run whenever an OpenClaw session (CLI or cron) launches.
- Applies to human sessions and automated agents that rely on the boot files (`AGENT_BOOT.md`, `CODEX_STARTUP.md`, `AGENTS.md`).

## Procedure
1. `cd /Users/neo/.openclaw/workspace`
2. Run `./scripts/worktree_doctor.py` (optionally add `--ignore memory/cron-prune.md` if you know a cron just appended there).
3. Inspect the report. Expect `memory`/`generated` buckets to hold the append-only logs you intentionally leave dirty—only files in the `other` bucket need manual review.
4. If you are pushing code, review the `other` bucket via `git diff <file>` and stage only those entries.
5. After confirming, rerun `git status --short` so the boot files reflect a clean state before continuing with builds or deployments.

## Notes
- This SOP points OpenClaw to the same startup facts described in `CODEX_STARTUP.md`/`AGENT_BOOT.md` so both human and cron sessions keep the memory lane explicit.
- If a cron finishes with new log entries (e.g., `memory/daily-briefs.md`), the script still helps you see that the cleanliness concern belongs to the memory lane, not your code review queue.
