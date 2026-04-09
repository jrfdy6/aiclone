# Heartbeat checklist

1. Generate the heartbeat sensor snapshot before thinking:
   - `python3 scripts/heartbeat_report.py` (pass `--json` if you need the raw fields).
   - `python3 scripts/heartbeat_report.py --summary` to capture the one-line snippet you will post to Discord.
   - Use those outputs to cite the most recent heartbeat run, Discord churn, and artifact ages. The summary helper already includes concrete timestamps; add extra context only when something changed.
2. Review `memory/heartbeat-state.json` only after running the report so you know which categories were already checked. Re-run checks only when a timestamp is null or older than one hour.
3. Update canonical heartbeat state with the helper script. Do not hand-edit `memory/heartbeat-state.json` or `memory/YYYY-MM-DD.md`.
   - Calm / no blocker:
     `python3 scripts/heartbeat_touch.py --status ok --note "HEARTBEAT_OK"`
   - Something needs attention:
     `python3 scripts/heartbeat_touch.py --status alert --note "<short blocker summary>" --append-log`
4. Keep prompts light: describe only blockers, urgent items, and acknowledgements grounded in the report output. When everything is calm, run the calm helper command, then paste the exact `heartbeat_report.py --summary` line (it will start with `HEARTBEAT_OK — …`). Do not send blank `HEARTBEAT_OK` replies anymore.
5. Focus only on:
   - automation / system health (include the relevant state from the report)
   - Discord / gateway disconnect churn (reference the report counts)
   - PM or workspace blockers that surfaced in canonical memory
   - urgent calendar / notification style items only if they are explicitly wired later
6. The helper script is the canonical write path for `memory/heartbeat-state.json`. Only append to today's `memory/YYYY-MM-DD.md` when something meaningful changed, and only through the helper script.
7. Do not duplicate cron summaries. Heartbeat is a lightweight watchdog, not a second daily brief, and Discord delivery should cite the specific metric that changed.
