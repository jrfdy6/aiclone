---
name: oracle-ledger-prune
description: Context-pruning workflow that retains only the latest three assistant responses, archives durable lessons, and reports pruning activity. Use for the "Oracle Ledger" cron.
---

# Oracle Ledger Pruning Skill

## Purpose
Prevent context bloat by trimming conversations while logging durable insights.

## Steps
1. **Load Session**
   - Grab the target chat context (Control UI / gateway log referenced in cron).
2. **Retain Recent Responses**
   - Keep the latest three assistant responses in the active history.
   - Move earlier responses into archival notes if still relevant.
3. **Document Durables**
   - Write lessons, decisions, or TODOs into `memory/cron-prune.md`.
   - Note any files touched or context removed.
4. **Summarize**
   - Briefly describe what was kept vs archived, mentioning any message IDs.
5. **Deliver**
   - Post summary to Discord channel `1482486716584689856`.
   - Mention if additional manual cleanup is required.

## Output Template
```
Oracle Ledger — <timestamp>
Context kept: <ids/brief>
Archived: <count>
Durable notes: <path>
Follow-up: <none|details>
```
