# LEARNINGS.md

## Memory-first reminders
- Always run a memory search (daily logs, learnings.md, or QMD) before answering anything longer than a sentence.
- If no relevant entry exists, log the new insight here as a one- or two-line rule so future turns can check it first.
- Document safety overrides, system tweaks, and policy decisions in this file before relying on them again.

## Current rules
1. Search `memory/YYYY-MM-DD.md` for the day (and yesterday) plus `LEARNINGS.md` before issuing a recommendation or executing a cron.
2. Log every mistake as a rule here (short, action-focused) so the agent can re-check this file on every turn.
3. Pair `memory_search` with QMD (when enabled) so both keywords and semantic matches are surfaced.

## Quarterly hygiene
- Weekly: promote key decisions from `memory/*.md` into `MEMORY.md` and prune anything stale.
- Keep `MEMORY.md` lean; offload everything else to the daily logs (the agent can always find it via search).
- Back up `memory/` with git (excluding `credentials/` and `openclaw.json`).
