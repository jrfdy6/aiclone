Memory Health Check — 2026-04-08
Status: WARN

Note: QMD freshness check is currently running; results pending.

QMD: running

Compaction: reserve=40000 / soft=4000 / flush=ON

Large Files:
- memory/2026-04-07.md: 36013 bytes (approx 35.2 KB)
- memory/2026-03-12.md: 19536 bytes
- memory/2026-04-01.md: 13921 bytes
- memory/2026-04-06.md: 19394 bytes
- memory/archiving_purging_plan.md: 375 bytes

Follow-ups:
- Await QMD freshness results to confirm semantic health.
- If QMD offline, escalate to ALERT and retry index checks.
- Consider archiving large memory entries (e.g., 2026-04-07) if not needed daily.

Report: memory/reports/memory_health_2026-04-08.md
