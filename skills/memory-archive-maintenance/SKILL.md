---
name: memory-archive-maintenance
description: Monthly memory hygiene for Markdown archives. Use when scheduled automation must move stale daily logs into memory/archive/, generate manifests, enforce retention windows, and log outcomes without duplicating cron instructions.
---

# Memory Archive Maintenance Skill

Use this skill for any workflow that periodically archives or prunes Markdown memory files. The cron prompt should only provide schedule + environment context (paths, time window, notification targets) and then instruct the agent to read and follow this skill.

## Scope
- Applies to Markdown files inside `memory/` that represent daily logs or dated incident notes (pattern: `memory/YYYY-MM-DD*.md` and `memory/YYYY-MM-DD-*.md`).
- Excludes golden files that must always stay hot (e.g., `memory/LEARNINGS.md`, `memory/roadmap.md`, `memory/cron-prune.md`, `memory/backup-log.md`, any `.skill` assets).
- Default retention: keep last 30 days in-place, archive older ones, purge anything older than 180 days that already lives inside `memory/archive/`.

## Prerequisites
1. Ensure target folders exist (create if missing):
   - `memory/archive/`
   - `memory/archive/<year>/`
   - `memory/archive/<year>/<month>/`
2. Confirm Git working tree is clean before moving large batches; abort if uncommitted destructive changes exist.
3. Read `memory/archiving_purging_plan.md` for context-specific overrides (retention days, skip lists).

## Workflow
1. **Load Context**
   - Read `memory/archiving_purging_plan.md` and the latest `memory/audit_log_day_1.md` entry.
   - Capture overrides (custom retention window, files flagged "do not move").
2. **Scan Hot Memory**
   - Enumerate Markdown files inside `memory/` excluding the protected list above plus `memory/archive/**`.
   - Calculate age for each file using filename date (fallback to filesystem mtime when parsing fails).
3. **Select Candidates**
   - Stage 1 (Archive): files older than 30 days but younger than 180 days.
   - Stage 2 (Purge): archived files older than 180 days **after** verifying they are already safely stored or backed up.
4. **Archive Stage**
   - For each Stage 1 file:
     - Determine destination folder `memory/archive/<YYYY>/<MM>/` based on file date.
     - Move the file (preserve basename) and maintain relative structure.
     - Append an entry to `memory/archive/manifests/<YYYY-MM>.md` describing what moved (filename, original path, timestamp, checksum via `shasum -a 256`).
5. **Purge Stage (optional)**
   - For Stage 2 files found under `memory/archive/`, delete them only after ensuring checksums already exist in a manifest.
   - Record deletions inside the same monthly manifest under a `## Purged` heading.
6. **Post-Move Validation**
   - Re-run the scan to ensure no Stage 1 files remain in hot storage.
   - Confirm Git status reflects moves (`git status -sb`). Abort if unexpected deletions occur.
7. **Audit Trail**
   - Update `memory/audit_log_day_1.md` (or `memory/audit_log_<date>.md`) with summary bullets: counts archived, purged, anomalies.
   - If discrepancies or missing manifests were found, create/append to `memory/issues/memory-archive.md` and flag for human review.

## Quality Gates
- Never move files modified within the last 48 hours even if filename date suggests otherwise.
- Preserve front-matter integrity by copying/moving entire files (no truncation).
- Ensure manifests include UTC timestamps and final Git status snippet.
- If any command fails, revert partial moves (use Git checkout or manual move) before exiting.

## Reporting Template
When the cron finishes, summarize the run using:
```
Memory Archive Maintenance — <YYYY-MM-DD>
- Archived: <count>
- Purged: <count>
- Oldest retained hot file: <filename/date>
- Manifest: memory/archive/manifests/<YYYY-MM>.md
- Follow-ups: <none|details>
```
Send this summary to the configured channel (cron provides target).

## Troubleshooting
- **Missing dates**: infer from `stat -f %Sm -t "%Y-%m-%d" <file>`.
- **Checksum mismatch**: re-run `shasum -a 256` and update manifest; if mismatch persists, halt and request human review.
- **Git conflicts**: stash or commit unrelated work before running archive workflow.
