---
name: progress-pulse-digest
description: Summarize only net-new Codex handoff plus maintenance signals for AI clone/Railway/workspace threads, capture durable lessons in memory, and send Discord updates only when something materially changed. Use for the "Progress Pulse" cron.
---

# Progress Pulse Digest Skill

## Objective
Produce a concise checkpoint grounded in net-new Codex handoff entries and maintenance signals, covering AI Clone/Railway/workspace updates, context limits, and blockers while preserving durable lessons.

## Workflow
1. **Build The Deterministic Digest First**
   - Run `python3 /Users/neo/.openclaw/workspace/scripts/build_progress_pulse_digest.py`.
   - If it returns `NO_REPLY`, return EXACTLY `NO_REPLY`.
   - If it returns markdown, treat that markdown as the final answer. Do not paraphrase it.
   - Do not emit a routine digest when nothing materially changed.
2. **Verify Only When Needed**
   - Read the latest entries from `memory/codex_session_handoff.jsonl` only if you need to verify a cited blocker, route, or artifact reference from the builder output.
   - Use `memory/cron-prune.md`, `memory/persistent_state.md`, and maintenance run context only to confirm the builder's evidence, not to rewrite its structure.
   - Only fall back to `agent:main:main` or `openclaw-control-ui` traces if you need OpenClaw-specific cleanup context.
3. **Trim Responses Only When Relevant**
   - If a live OpenClaw session was actually part of the evidence, keep the latest three assistant responses in that active context and archive older ones as needed.
   - Otherwise, skip the pruning language and focus on Codex handoff plus maintenance signals.
   - Note any blockers or unanswered questions.
4. **Document Lessons**
   - Write durable decisions/insights into `memory/cron-prune.md` using `python3 /Users/neo/.openclaw/workspace/scripts/append_markdown_block.py`.
   - Treat `memory/LEARNINGS.md` as read-only during cron rehab; if a durable guardrail matters, note it in `memory/cron-prune.md` for later human promotion.
5. **Respect The Delivery Contract**
   - Every delivered digest must answer: what changed, why it matters, what action is now required, where it was routed, and which source artifact or PM card supports it.
   - Never send boilerplate like "no further action needed", "latest signal", or raw sync counts as the main value.
   - If the builder output would be invalid or low-value, return `NO_REPLY` instead of improvising.
6. **Deliver**
   - Return the summary in the final answer only.
   - Do not call the message tool; cron delivery is automatic.
   - Do not add conversational framing like "Here's the latest digest" or "If you need anything else".
   - Log a one-line recap in `memory/cron-prune.md` with timestamp via the append helper.

## Formatting
```
Progress Pulse — <timestamp>
Status: <green/yellow/red>
What Changed:
- ...
Why It Matters:
- ...
Action Now:
- Owner: ...
- Next: ...
Routing:
- Workspace: ...
- Route: ...
Source:
- ...
Alerts:
- ...
```
