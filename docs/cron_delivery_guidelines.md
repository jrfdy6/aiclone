# Cron Delivery Guidelines

This doc explains how heartbeat, cron jobs, and Discord delivery should behave so the system pushes forward without flooding you with noisy summaries.

## Intent
- **Heartbeat:** lightweight watchdog that checks systems/automation health, points to HEARTBEAT.md, and replies `HEARTBEAT_OK` when nothing needs attention.
- **Crons:** do the heavy lifting (memory flush, rolling docs, dream cycle, daily brief, progress pulse) and log durable insights in `memory/` files.
- **Discord:** reserved for alerts, approvals, and concise digests that require your input. Final cron responses are the delivery channel; avoid extra `message()` calls.

## Delivery rules
1. Keep Discord text short (≤1,800 characters) and focused on decisions, blockers, or approvals you actually need to act on.
2. If a cron completed successfully with no new issues, say so briefly and point to the relevant memory log (`memory/daily-briefs.md`, `memory/cron-prune.md`, `memory/reports/...`).
3. Do not duplicate info: the Morning Daily Brief should highlight what changed since the last brief, not rerun every cron’s status. Reference `memory/persistent_state.md` so the story starts from a single snapshot.
4. Use `memory/cron-prune.md` to keep a lightweight running log of what each cron left behind. Mention this in the digest if the message has follow-up actions.

## Recommended cron flow
- `daily-memory-flush`: append insights/decisions to `memory/LEARNINGS.md` and `memory/YYYY-MM-DD.md`.
- `progress-pulse-digest`: archive context-control insights into `memory/cron-prune.md` and only mention blockers/status changes in Discord.
- `morning-daily-brief`: read `memory/persistent_state.md`, `memory/cron-prune.md`, and `memory/daily-briefs.md` so the summary points you to the single next opportunity each day.
- `dream-cycle`: rewrite `memory/persistent_state.md` nightly so the next session can resume from a compact snapshot; report issues through the `memory/reports/` folder instead of flooding Discord.
- `memory-health-check`, `rolling-docs-refresh`, `nightly-self-improvement`, `github-backup`: run quietly, log into `memory/reports/` or `memory/backup-log.md`, surface exceptions through Ops UI or selective alerts only.

## When to escalate
- If a cron fails, highlight the failure first (issue, logs, references) and only then mention follow-ups.
- If replication or backend routes drift, point Discord to `/api/` endpoints or logs instead of reconstructing the entire status inside the message.

Following these rules keeps Discord notifications tight while the automations continue moving the system forward. Keep this doc handy whenever you edit or add a new cron/skill.
