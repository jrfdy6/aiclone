# HEARTBEAT_GUIDANCE.md

## Purpose
Keep heartbeat calls lean by limiting what they check and how often they run. Follow this guide each time you edit `HEARTBEAT.md` or the heartbeat configuration in `openclaw.json`.

## Default prompt
"Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK." Keep that text short so each turn sends minimal tokens.

## Heartbeat vs. cron
| Situation | Use heartbeat | Use cron |
| --- | --- | --- |
| Batch checks that benefit from shared context | ✅ | ❌ |
| Exact timing or isolation | ❌ | ✅ |
| Need a different model or thinking level | ❌ | ✅ |
| One-shot reminders | ❌ | ✅ |
| Want to avoid duplicated API calls | ✅ | ❌ |

## What to check (rotate 2–4×/day)
- Emails (urgent unread messages)
- Calendar (events in the next 24–48 hours)
- Mentions/notifications in critical channels
- Weather if the human might go outside

## Tracking state
Store timestamps in `memory/heartbeat-state.json` so you know when each category was last checked. Example structure:
```json
{
  "lastChecks": {
    "email": 1703275200,
    "calendar": 1703260800,
    "weather": null
  }
}
```

## When to stay quiet
- Late night (23:00–08:00) unless something urgent demands attention
- Nothing new since the last check
- You just checked less than 30 minutes ago
- The human is clearly busy or asleep

## Proactive things you can do without asking
- Organize memory files
- Review documents or tasks referenced on the dashboard
- Update documentation, especially `MEMORY.md`
- Commit and push polished changes you made during the heartbeat work session

## Memory maintenance
When you run a heartbeat every few days, also:
1. Read the recent `memory/YYYY-MM-DD.md` logs
2. Capture the durable lessons into `MEMORY.md`
3. Prune stale entries from `MEMORY.md` to keep it lean
4. Leave everything else in the daily logs—search will surface it when needed

Use `memory/heartbeat-state.json` to record when each category was last reviewed so the next heartbeat can skip redundant checks.

The heartbeat is the opportunity to archive what you learned, trim what’s outdated, and keep the system prompt stable so caching stays effective.
