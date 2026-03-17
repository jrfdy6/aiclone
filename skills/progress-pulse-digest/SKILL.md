---
name: progress-pulse-digest
description: Summarize latest gateway chat context for AI clone/Railway threads, capture durable lessons in memory, and send Discord updates. Use for the "Progress Pulse" cron.
---

# Progress Pulse Digest Skill

## Objective
Produce a concise checkpoint on the latest gateway chat (openclaw-control-ui) covering AI Clone/Railway updates, context limits, and blockers while preserving durable lessons.

## Workflow
1. **Gather Context**
   - Read the freshest gateway chat transcript (look under Control UI history or cached logs).
   - Identify AI Clone + Railway-related messages since the last digest.
2. **Trim Responses**
   - Keep the latest three assistant responses in the active context; archive older ones as needed.
   - Note any blockers or unanswered questions.
3. **Document Lessons**
   - Write durable decisions/insights into `memory/cron-prune.md`.
   - Promote high-level guardrails into `memory/LEARNINGS.md` when appropriate.
4. **Compose Summary**
   - Include: current status, new blockers, context-size risks, and next steps.
   - Highlight whether a follow-up action is required.
5. **Deliver**
   - Post the summary to Discord channel `1482486716584689856`.
   - Log a one-line recap in `memory/cron-prune.md` with timestamp.

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
