---
name: progress-pulse-digest
description: Summarize the latest Codex handoff plus maintenance signals for AI clone/Railway/workspace threads, capture durable lessons in memory, and send Discord updates. Use for the "Progress Pulse" cron.
---

# Progress Pulse Digest Skill

## Objective
Produce a concise checkpoint grounded in the latest Codex handoff entries and maintenance signals, covering AI Clone/Railway/workspace updates, context limits, and blockers while preserving durable lessons.

## Workflow
1. **Gather Context**
   - Read the latest entries from `memory/codex_session_handoff.jsonl` first.
   - Use `memory/cron-prune.md`, `memory/persistent_state.md`, and maintenance run context to ground the digest.
   - Only fall back to `agent:main:main` or `openclaw-control-ui` traces if you need OpenClaw-specific cleanup context.
   - Identify AI Clone, Railway, workspace, and system-maintenance signals since the last digest.
2. **Trim Responses Only When Relevant**
   - If a live OpenClaw session was actually part of the evidence, keep the latest three assistant responses in that active context and archive older ones as needed.
   - Otherwise, skip the pruning language and focus on Codex handoff plus maintenance signals.
   - Note any blockers or unanswered questions.
3. **Document Lessons**
   - Write durable decisions/insights into `memory/cron-prune.md` using `python3 /Users/neo/.openclaw/workspace/scripts/append_markdown_block.py`.
   - Treat `memory/LEARNINGS.md` as read-only during cron rehab; if a durable guardrail matters, note it in `memory/cron-prune.md` for later human promotion.
4. **Compose Summary**
   - Include: current status, new blockers, context-size risks, next steps, and whether the evidence came from Codex handoff, OpenClaw session context, or both.
   - Highlight whether a follow-up action is required.
5. **Deliver**
   - Return the summary in the final answer only.
   - Do not call the message tool; cron delivery is automatic.
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
