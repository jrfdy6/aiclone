---
name: github-backup
description: Snapshot neo-core, push archive to backups, and log results in memory/backup-log.md. Use for GitHub backup automations.
---

# GitHub Backup Skill

## Steps
1. **Prep**
   - Ensure repo clean (`git status -sb`). Abort if dirty unless instructed.
2. **Snapshot**
   - Run `./scripts/run_github_backup.sh /Users/neo/.openclaw/workspace /Users/neo/.openclaw/workspace/backups` (override paths if needed).
   - Parse the JSON output (archive path, checksum, size).
3. **Push/Sync**
   - Copy/archive anywhere else if required (defaults to local `backups/`).
4. **Log**
   - Append entry to `memory/backup-log.md` including file name, checksum (`shasum -a 256`), and success/failure.
5. **Report**
   - Send confirmation to Discord channel `1482486716584689856` referencing the log entry.

## Template
```
GitHub Backup — <date>
Archive: backups/<file>
Checksum: <sha256>
Status: success|failure
Notes: <issues>
```
