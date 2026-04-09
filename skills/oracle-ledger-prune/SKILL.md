---
name: oracle-ledger-prune
description: Consolidate the latest Codex handoffs into canonical memory, prune OpenClaw session history only when it is actually active, and report durable lessons into logs. Use for the "Oracle Ledger" cron.
---

# Oracle Ledger Pruning Skill

## Purpose
Keep the brain grounded by consolidating the latest Codex work into canonical memory while trimming OpenClaw session history only when that history is actually the active work surface. This is primarily a log-maintenance job, not a routine Discord narrator.

## Steps
1. **Load Canonical Handoff First**
   - Run `python3 /Users/neo/.openclaw/workspace/scripts/build_cron_memory_contract.py --workspace-key shared_ops --memory-path memory/persistent_state.md --memory-path memory/cron-prune.md --memory-path memory/LEARNINGS.md --memory-path memory/{today}.md` first.
   - Read the latest entries from `memory/codex_session_handoff.jsonl` before looking at any OpenClaw session history.
   - Treat `chronicle_entries` as the primary truth source for recent Codex work.
   - If older markdown memory changes the interpretation of the Chronicle tail, use `durable_memory_context` instead of guessing.
   - Only inspect `agent:main:main` or any `openclaw-control-ui` traces if you need OpenClaw-specific cleanup context or the handoff file is empty.
2. **Prune Only If Real Session Context Exists**
   - If a live OpenClaw session is clearly active and relevant, keep the latest three assistant responses in that live history.
   - If no live OpenClaw session is meaningfully in use, do not pretend to prune it; treat this run as a ledger-consolidation pass instead.
3. **Document Durables**
   - Write lessons, decisions, or TODOs into `memory/cron-prune.md` using `python3 /Users/neo/.openclaw/workspace/scripts/append_markdown_block.py`.
   - Note any files touched or context removed.
   - Treat `memory/LEARNINGS.md` as read-only during cron rehab. Do not edit it.
   - If there is a genuine durable lesson worth carrying forward, mention it in the final summary and leave a note in `memory/cron-prune.md` for a later human review.
   - Never write "no new learnings" into `memory/LEARNINGS.md`.
   - When live markdown files are missing, use the fallback-resolved paths from the memory contract instead of pretending the files were empty.
4. **Summarize**
   - Briefly describe what came from Codex handoff versus live OpenClaw session cleanup, mentioning message IDs only if you actually used session history.
5. **Deliver**
   - Return the summary in the final answer only.
   - Do not call the message tool.
   - Assume the canonical audience is `memory/cron-prune.md`, not Discord.
   - Mention if additional manual cleanup is required.

## Output Template
```
Oracle Ledger — <timestamp>
Codex handoff reviewed: <count/brief>
OpenClaw session pruned: <yes/no + ids/brief>
Durable notes: <path>
Follow-up: <none|details>
```
