---
name: github-backup
description: Snapshot neo-core, push archive to backups, and log results in memory/backup-log.md. Use for GitHub backup automations.
---

# GitHub Backup Skill

## Steps
1. **Prep**
   - Ensure repo clean (`git status -sb`). Abort if dirty unless instructed.
2. **Snapshot**
   - Create archive `neo-core-backup-<YYYYMMDD>.tar.gz` from repo root.
   - Store under `backups/` (create folder if missing).
3. **Push/Sync**
   - Copy archive to the designated backup location (local `backups/` directory is default).
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
