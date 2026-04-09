---
name: progress-pulse-digest
description: Summarize only net-new Codex handoff plus maintenance signals for AI clone/Railway/workspace threads, capture durable lessons in memory, and send Discord updates only when something materially changed. Use for the "Progress Pulse" cron.
---

# Progress Pulse Digest Skill

## Objective
Produce a concise checkpoint grounded in net-new Codex handoff entries and maintenance signals, covering AI Clone/Railway/workspace updates, context limits, and blockers while preserving durable lessons.

## Workflow
1. **Gate Delivery First**
   - Run `python3 /Users/neo/.openclaw/workspace/scripts/progress_pulse_gate.py --json`.
   - If `should_deliver` is false, return EXACTLY `NO_REPLY`.
   - Do not emit a routine digest when nothing materially changed.
2. **Gather Context**
   - Read the latest entries from `memory/codex_session_handoff.jsonl` first.
   - Use `memory/cron-prune.md`, `memory/persistent_state.md`, and maintenance run context to ground the digest.
   - Only fall back to `agent:main:main` or `openclaw-control-ui` traces if you need OpenClaw-specific cleanup context.
   - Identify AI Clone, Railway, workspace, and system-maintenance signals since the last delivered digest.
3. **Trim Responses Only When Relevant**
   - If a live OpenClaw session was actually part of the evidence, keep the latest three assistant responses in that active context and archive older ones as needed.
   - Otherwise, skip the pruning language and focus on Codex handoff plus maintenance signals.
   - Note any blockers or unanswered questions.
4. **Document Lessons**
   - Write durable decisions/insights into `memory/cron-prune.md` using `python3 /Users/neo/.openclaw/workspace/scripts/append_markdown_block.py`.
   - Treat `memory/LEARNINGS.md` as read-only during cron rehab; if a durable guardrail matters, note it in `memory/cron-prune.md` for later human promotion.
5. **Compose Summary**
   - Include only net-new status changes, new blockers, blocker resolutions, or concrete new follow-up actions.
   - Use the current UTC time from `date -u '+%Y-%m-%d %H:%M UTC'` for the timestamp.
   - Do not repeat old boilerplate just because the job ran again.
   - Mention whether the evidence came from Codex handoff, persistent state, OpenClaw session context, or a combination.
   - Do not assign a generic owner unless the evidence supports a real owner/action pair.
6. **Deliver**
   - Return the summary in the final answer only.
   - Do not call the message tool; cron delivery is automatic.
   - Do not add conversational framing like "Here's the latest digest" or "If you need anything else".
   - Log a one-line recap in `memory/cron-prune.md` with timestamp via the append helper.

## Formatting
```
Progress Pulse — <timestamp>
Status: <green/yellow/red>
Highlights:
- ...
Blockers:
- ...
Follow-up: <yes/no + owner>
```
