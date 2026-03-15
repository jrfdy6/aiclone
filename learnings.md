# LEARNINGS.md

## Memory-first reminders
- Always run a memory search (daily logs, learnings.md, or QMD) before answering anything longer than a sentence.
- If no relevant entry exists, log the new insight here as a one- or two-line rule so future turns can check it first.
- Document safety overrides, system tweaks, and policy decisions in this file before relying on them again.

## Current rules
1. Search `memory/YYYY-MM-DD.md` for the day (and yesterday) plus `LEARNINGS.md` before issuing a recommendation or executing a cron.
2. Log every mistake as a rule here (short, action-focused) so the agent can re-check this file on every turn.
3. Pair `memory_search` with QMD (when enabled) so both keywords and semantic matches are surfaced.
4. When compaction runs memory flush, expect a short summary in today’s daily file; if you add a new rule, log it there first so the agent can re-read it before future turns.

## Quarterly hygiene
- Weekly: promote key decisions from `memory/*.md` into `MEMORY.md` and prune anything stale.
- Keep `MEMORY.md` lean; offload everything else to the daily logs (the agent can always find it via search).
- Back up `memory/` with git (excluding `credentials/` and `openclaw.json`).

## 2026-03-14 System audit
- After this audit we now open the dashboard via the tokenized URL in a clean browser profile so the agent pairs with the rotated control-UI token and avoids repeated `device_token_mismatch` errors.
- Cron reminder `Heartbeat` runs every 30 min, prunes context, writes durable lessons to `memory/cron-prune.md`, and posts to Discord channel `1482486716584689856` so the summary is always visible.
- Keep the device list trimmed—remove duplicate/public control-UI entries before pairing a new token (use `openclaw devices list`/`remove` to confirm).
- `qmd` sometimes reports “collection already exists”: run `qmd update --collection memory-main` (or `qmd collection remove memory-main` first if you need a clean rebuild) whenever memory search fails.
- Ensure `memory/YYYY-MM-DD.md` exists for today’s date so every run can flush durable facts; create the file if it’s missing before compacting context again.
- Added `memory/folder-inventory.md` after scanning every requested directory so future agents can quickly find the high-signal folders, subfolders, and representative files across OpenClaw’s state tree.
