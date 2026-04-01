# OpenClaw Cron Inventory Baseline

- Generated: `2026-03-31T05:28:46.992576+00:00`
- Jobs file: `/Users/neo/.openclaw/cron/jobs.json`
- Job count: `14`

## Summary
- Enabled jobs: `14`
- Jobs with errors: `2`
- Jobs ok but not delivered: `1`
- Discord delivery jobs: `13`
- Webchat delivery jobs: `1`
- Agent-turn jobs: `14`

## Job Table

| Job | Schedule | Delivery | Last Status | Delivered | Notes |
| --- | --- | --- | --- | --- | --- |
| Oracle Ledger | `every:14400000` | `discord->1482486716584689856` | `ok` | `True` |  |
| GitHub Backup | `cron:0 6 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |
| Nightly Self-Improvement | `cron:0 1 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |
| Morning Daily Brief | `cron:30 11 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |
| Rolling Docs | `cron:0 4 */2 * *` | `discord->1482486716584689856` | `error` | `True` | ⚠️ 📝 Edit: `in ~/.openclaw/workspace/HEARTBEAT.md (42 chars)` failed |
| Daily Memory Flush | `cron:0 3 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |
| Weekly Backup | `cron:0 5 * * 0` | `discord->1482486716584689856` | `ok` | `True` |  |
| Progress Pulse | `every:1800000` | `discord->1482486716584689856` | `error` | `True` | ⚠️ 📝 Edit: `in ~/.openclaw/workspace/memory/LEARNINGS.md (326 chars)` failed |
| Memory Archive Sweep | `cron:0 4 1 * *` | `discord->1482486716584689856` | `None` | `None` |  |
| Memory Health Check | `cron:0 3 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |
| Context Guard | `cron:*/20 * * * *` | `webchat->openclaw-control-ui` | `ok` | `False` |  |
| Dream Cycle | `cron:15 6 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |
| Service Status Monitor | `cron:0 6 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |
| Railway & GitHub API Monitor | `cron:0 6 * * *` | `discord->1482486716584689856` | `ok` | `True` |  |

## Recent Log Pattern Counts

- `discord_gateway_error`: `16`
- `edit_failed`: `194`
- `lane_wait_exceeded`: `60`
- `message_failed`: `375`
- `read_failed`: `146`
- `ws_unauthorized`: `104`

## Jobs Currently In Error

- `Rolling Docs`: ⚠️ 📝 Edit: `in ~/.openclaw/workspace/HEARTBEAT.md (42 chars)` failed
- `Progress Pulse`: ⚠️ 📝 Edit: `in ~/.openclaw/workspace/memory/LEARNINGS.md (326 chars)` failed

## Jobs Currently Ok But Not Delivered

- `Context Guard` -> `openclaw-control-ui`
