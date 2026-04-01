---
name: oracle-ledger-prune
description: Consolidate the latest Codex handoffs into canonical memory, prune OpenClaw session history only when it is actually active, and report durable lessons. Use for the "Oracle Ledger" cron.
---

# Oracle Ledger Pruning Skill

## Purpose
Keep the brain grounded by consolidating the latest Codex work into canonical memory while trimming OpenClaw session history only when that history is actually the active work surface.

## Steps
1. **Load Canonical Handoff First**
   - Read the latest entries from `memory/codex_session_handoff.jsonl` before looking at any OpenClaw session history.
   - Treat that file as the primary truth source for recent Codex work.
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
4. **Summarize**
   - Briefly describe what came from Codex handoff versus live OpenClaw session cleanup, mentioning message IDs only if you actually used session history.
5. **Deliver**
   - Return the summary in the final answer only.
   - Do not call the message tool; cron delivery is automatic.
   - Mention if additional manual cleanup is required.

## Output Template
```
Oracle Ledger — <timestamp>
Codex handoff reviewed: <count/brief>
OpenClaw session pruned: <yes/no + ids/brief>
Durable notes: <path>
Follow-up: <none|details>
```
