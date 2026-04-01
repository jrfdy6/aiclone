---
name: memory-health-check
description: Daily automated audit of memory hygiene. Use when a cron must inspect memory and QMD status, compaction safety, file sizes, and report findings without embedding workflow instructions in the cron prompt.
---

# Memory Health Check Skill

This skill defines the end-to-end workflow for monitoring memory integrity, retrieval readiness, and compaction safety. Cron prompts should only set the schedule, model, and delivery context, then tell the agent to read this skill.

## Objectives
- Verify semantic retrieval (QMD) index freshness and connectivity.
- Inspect hot memory files for bloat, corruption, or missing essentials (SOUL, AGENTS, USER, TOOLS, MEMORY entries).
- Confirm compaction and flush settings match guardrails.
- Emit a structured report with actionable alerts.

## Inputs & References
- `memory/memory_health_check_plan.md` — retention targets + thresholds.
- `memory/memory_management_check.md` — prior recommendations.
- `AGENTS.md`, `SOUL.md`, `USER.md`, `MEMORY.md` — ensure sizes <20k chars each.
- QMD status script `/Users/neo/.openclaw/workspace/scripts/check_index_status.sh`.
- Compaction guardrail script `/Users/neo/.openclaw/workspace/scripts/compaction_guardrail_check.py`.

## Workflow
1. **Load Config**
   - Read `memory/memory_health_check_plan.md` for thresholds (max hot file size, reserve tokens, alert routing).
   - Note any overrides recorded in `memory/audit_log_day_1.md`.
2. **QMD & Retrieval Checks**
   - Run `/Users/neo/.openclaw/workspace/scripts/qmd_freshness_check.py` to obtain JSON stats (files, collections, last update age). Treat `stale=true` as WARN/ALERT.
   - Run `/Users/neo/.openclaw/workspace/scripts/check_index_status.sh` if Firestore indices or external collectors matter; capture errors.
   - If QMD unreachable, record as `ALERT: QMD offline` and stop further semantic checks.
3. **Compaction Settings**
   - Run `/Users/neo/.openclaw/workspace/scripts/compaction_guardrail_check.py` to pull authoritative values from `~/.openclaw/openclaw.json`.
   - Confirm outputs: `reserveTokensFloor >= 40000`, `softThresholdTokens >= 4000`, `flush.enabled=true`.
   - If any value is out of range, mark the report as `WARN` (or `ALERT` if flush disabled) and add a remediation item.
4. **File Size Audit**
   - For each critical file (`SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, `MEMORY.md`):
     - Record byte size and line count (`wc -c`, `wc -l`).
     - Flag if >20k chars or grew >15% vs last checkpoint (track via `memory/weekly_hygiene_summary.md`).
5. **Hot Memory Scan**
   - List `memory/*.md` excluding archive and golden files.
   - Identify files >50 KB; recommend archiving if older than 30 days.
6. **Anomaly Detection**
   - Search for merge conflict markers (`<<<<<<<` etc.) inside memory files.
   - Confirm today’s daily log exists (`memory/YYYY-MM-DD.md`). If missing, add TODO.
7. **Reporting**
   - Generate `memory/reports/memory_health_<YYYY-MM-DD>.md` including sections:
     - Summary (OK/WARN/ALERT)
     - QMD status
     - Compaction settings table
     - File size table
     - Suggested follow-ups
   - Append a short recap to `memory/audit_log_day_1.md` referencing the report using `python3 /Users/neo/.openclaw/workspace/scripts/append_markdown_block.py`.
   - Deliver a notification to the cron’s configured channel.

## Quality Gates
- Treat any ALERT (QMD offline, missing guardrail file, flush disabled) as blocking—return non-zero exit and notify human.
- Reports must include timestamps (UTC + local) and Git status snippet.
- Never modify content of SOUL/AGENTS/USER/TOOLS/MEMORY during the health check; only read & report.

## Output Template
```
Memory Health Check — <YYYY-MM-DD>
Status: OK | WARN | ALERT
QMD: <freshness / doc count / issues>
Compaction: reserve=<value> / soft=<value> / flush=<on|off>
Large Files: <list or "none">
Follow-ups: <action items>
Report: memory/reports/memory_health_<YYYY-MM-DD>.md
```

## Troubleshooting
 - **check_index_status.sh not executable**: `chmod +x /Users/neo/.openclaw/workspace/scripts/check_index_status.sh` and rerun.
- **Permissions error reading files**: ensure workspace owner is `neo`, run `ls -al` to confirm.
- **Missing directories**: create `memory/reports/` before writing.
