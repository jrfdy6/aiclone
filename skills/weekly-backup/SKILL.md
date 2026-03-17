---
name: weekly-backup
description: Copy key config/env files into workspace/backups, record checksums in memory/backup-log.md, and flag drift. Use for the Weekly Backup cron.
---

# Weekly Backup Skill

## Checklist
1. **Identify Files**
   - Include `~/.openclaw/openclaw.json`, `.env` files, config scripts, and other key artifacts defined in `memory/backup-log.md` history.
2. **Copy**
   - Place copies under `workspace/backups/<YYYY-MM-DD>/` (create folder if missing).
3. **Verify**
   - Generate checksums for each file and record them.
4. **Log**
   - Append results to `memory/backup-log.md` (success/failure, checksum, notes).
5. **Alert Drift**
   - If checksums differ from prior run, call it out in the summary.
6. **Deliver**
   - Send recap to Discord channel `1482486716584689856`.

## Template
```
Weekly Backup — <date>
Files:
- openclaw.json (sha256 ...)
- ...
Status: success|issues
Follow-ups: <none|details>
```
