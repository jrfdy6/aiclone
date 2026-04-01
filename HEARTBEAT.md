# Heartbeat checklist

1. Review `memory/heartbeat-state.json` before each heartbeat turn to know which categories were last checked. Only re-check when the timestamp is either null or older than one hour.
2. Before replying, update canonical heartbeat state with the helper script. Do not use `edit` or `write` on `memory/heartbeat-state.json` or `memory/YYYY-MM-DD.md` during heartbeat turns.
   - Calm / no blocker:
     `python3 scripts/heartbeat_touch.py --status ok --note "HEARTBEAT_OK"`
   - Something needs attention:
     `python3 scripts/heartbeat_touch.py --status alert --note "<short blocker summary>" --append-log`
3. Keep prompts light: describe only blockers, urgent items, and acknowledgements. If everything is calm, run the calm helper command first and then reply exactly `HEARTBEAT_OK` with no extra text.
4. Focus only on:
   - automation / system health
   - Discord / gateway disconnect churn
   - PM or workspace blockers that surfaced in canonical memory
   - urgent calendar / notification style items only if they are explicitly wired later
5. The helper script is the canonical write path for `memory/heartbeat-state.json`. Only append to today's `memory/YYYY-MM-DD.md` when something meaningful changed, and only through the helper script.
6. Do not duplicate cron summaries. Heartbeat is a lightweight watchdog, not a second daily brief.
