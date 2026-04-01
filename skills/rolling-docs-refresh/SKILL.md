---
name: rolling-docs-refresh
description: Review README, LEARNINGS, and HEARTBEAT for drift, apply updates, and log edits to memory/doc-updates.md. Use for the Rolling Docs cron.
---

# Rolling Docs Refresh Skill

## Steps
1. **Audit Files**
   - Run `/Users/neo/.openclaw/workspace/scripts/doc_status_snapshot.py` to capture current size/mtime metadata.
   - Review `README.md`, `memory/LEARNINGS.md`, and `HEARTBEAT.md` for outdated statements.
2. **Update**
   - Prefer low-risk targeted edits only.
   - Do not rewrite `HEARTBEAT.md` unless there is an objectively wrong path, stale status line, or broken reference that can be corrected with a small edit.
   - If drift is uncertain, log the recommendation in `memory/doc-updates.md` instead of editing the file.
3. **Log**
   - Summarize edits in `memory/doc-updates.md` with timestamp + rationale using `python3 /Users/neo/.openclaw/workspace/scripts/append_markdown_block.py`.
4. **Report**
   - Return the recap in the final answer only.
   - Do not call the message tool; cron delivery is automatic.

## Template
```
Rolling Docs Refresh — <date>
Updated:
- README (section ...)
- LEARNINGS (...)
Notes:
- ...
```
