# Context Flush SOP

This is the compatibility SOP for mid-task context preservation.

Use it when a session is getting bloated or when a cron/job needs to capture durable state before a restart, prune, or compaction event.

## Canonical Command

```bash
python3 /Users/neo/.openclaw/workspace/scripts/context_flush.py \
  --task "Current task name" \
  --insights "Key insight" \
  --decisions "Decision made" \
  --structural-changes "Files or systems changed" \
  --blockers "Current blocker" \
  --next-steps "What should happen next"
```

## Required Outputs

- Append the flush note to `memory/YYYY-MM-DD.md`.
- Keep the note structured enough that a fresh session can recover quickly.
- If a lesson is durable beyond the day, promote it separately into `memory/LEARNINGS.md`.

## What Belongs In A Flush

- Task being worked
- Key insights or discoveries
- Decisions that changed direction
- Structural changes to files, jobs, schemas, or runtime behavior
- Active blockers
- Immediate next steps

## Guardrail

This SOP is for capture, not for long-form writing. Keep the flush factual and compact.
