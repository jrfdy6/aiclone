# OpenClaw Runtime Backup 2026-04-08

This note preserves the non-git OpenClaw runtime state that sits outside the repo at the time of the clean restore point.

Repo restore point:

- Git branch: `main`
- Git commit: `206b447bc227bed9dd2623157bf14f69de587370`
- Git tag: `clean-main-2026-04-08`
- Captured at: `2026-04-08 20:46:18 EDT -0400`

Runtime files outside git:

1. `/Users/neo/.openclaw/openclaw.json`
   - SHA-256: `949e32ee7afd5cc629f69447981bdb67c391f5fdbeb7f5ef185e812fa665798b`
2. `/Users/neo/.openclaw/cron/jobs.json`
   - SHA-256: `20c1c402590f55de6a777a42e8ea9e88ab1bfd9cc820d8f73aade053007eb218`
3. `/Users/neo/.openclaw/agents/main/qmd/xdg-config/qmd/index.yml`
   - SHA-256: `88c78c162345bb9823c84255c24ee3f9c058b14c10d885060d3529eec1ff519c`

## Why These Matter

- `openclaw.json` carries the fixed heartbeat model and active window.
- `jobs.json` carries the repaired Dream Cycle prompt and the one-shot Dream Cycle verifier.
- `index.yml` carries the repaired `memory-dir-main` QMD collection alias.

## Required Runtime State

### 1. Heartbeat configuration in `/Users/neo/.openclaw/openclaw.json`

```json
"heartbeat": {
  "every": "30m",
  "activeHours": {
    "start": "08:00",
    "end": "22:00"
  },
  "model": "openai/gpt-4o-mini",
  "prompt": "Read HEARTBEAT.md if it exists in the workspace and follow it strictly. Use any exact helper commands it provides instead of hand-editing files. If nothing needs attention after following HEARTBEAT.md, reply HEARTBEAT_OK exactly. If something needs attention, reply with the alert text only.",
  "lightContext": true
}
```

This is the runtime fix that replaced the broken `ollama/llama3.1:latest` heartbeat path.

### 2. QMD alias in `/Users/neo/.openclaw/agents/main/qmd/xdg-config/qmd/index.yml`

```yaml
collections:
  memory-root-main:
    path: /Users/neo/.openclaw/workspace
    pattern: MEMORY.md
  memory-alt-main:
    path: /Users/neo/.openclaw/workspace
    pattern: memory.md
  memory-main:
    path: /Users/neo/.openclaw/workspace/memory
    pattern: "**/*.md"
  memory-dir-main:
    path: /Users/neo/.openclaw/workspace/.memory-dir-link
    pattern: "**/*.md"
  knowledge-main:
    path: /Users/neo/.openclaw/workspace/knowledge
    pattern: "**/*.md"
```

`memory-dir-main` must exist, or managed QMD retrieval degrades and cron summaries lose grounding.

### 3. Dream Cycle job in `/Users/neo/.openclaw/cron/jobs.json`

The recurring Dream Cycle job must stay enabled on `15 6 * * *` with the repaired prompt below:

```json
{
  "name": "Dream Cycle",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "15 6 * * *"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "Read and follow /Users/neo/.openclaw/workspace/skills/dream-cycle/SKILL.md.\nContext:\n- Workspace root: /Users/neo/.openclaw/workspace\n- State file: /Users/neo/.openclaw/workspace/memory/persistent_state.md\n- Log file: /Users/neo/.openclaw/workspace/memory/dream_cycle_log.md\n- Canonical Codex handoff: /Users/neo/.openclaw/workspace/memory/codex_session_handoff.jsonl\nInstructions:\n1. Load SOP/guardrails if missing (python3 /Users/neo/.openclaw/workspace/scripts/load_context_pack.py --sop --memory).\n2. Resolve today's daily log to a concrete current-date path before reading it; never try to open `memory/YYYY-MM-DD.md` literally.\n3. Resolve the latest memory health report to a concrete path with `python3 /Users/neo/.openclaw/workspace/scripts/latest_matching_file.py --glob '/Users/neo/.openclaw/workspace/memory/reports/memory_health_*.md'` before reading it; never try to open the wildcard path directly.\n4. If heartbeat freshness, Discord summary quality, or automation drift is in question, run `python3 /Users/neo/.openclaw/workspace/scripts/heartbeat_report.py` and ground the snapshot in the returned timestamps.\n5. Gather today's entries, the latest Codex handoff entries, cron outputs (/Users/neo/.openclaw/workspace/memory/cron-prune.md, /Users/neo/.openclaw/workspace/memory/doc-updates.md, /Users/neo/.openclaw/workspace/memory/backup-log.md), self-improvement/daily-brief notes, the resolved memory health report, and concrete recently modified files under /Users/neo/.openclaw/workspace/knowledge/ when new ingestions matter; do not try to read the knowledge directory itself.\n6. Overwrite /Users/neo/.openclaw/workspace/memory/persistent_state.md with the new snapshot (Snapshot, Automation Health, Findings, Actions).\n7. Append the full narrative (dated heading) to /Users/neo/.openclaw/workspace/memory/dream_cycle_log.md.\n8. Keep the final response under 1,200 characters and do not call the message tool.",
    "model": "openai/gpt-4o-mini"
  }
}
```

The important repairs are:

- resolve the daily log to a real dated file before reading
- resolve `memory_health_*.md` to a concrete path first
- use `heartbeat_report.py` when freshness matters
- read concrete `knowledge/` files, not the directory itself

### 4. One-shot Dream Cycle verifier in `/Users/neo/.openclaw/cron/jobs.json`

This verifier was intentionally added as a temporary guardrail and should exist exactly once:

```json
{
  "id": "9d9b2c7e-110c-4e44-8865-4f3c86e1809f",
  "name": "Dream Cycle Verification (2026-04-09)",
  "enabled": true,
  "deleteAfterRun": true,
  "schedule": {
    "kind": "at",
    "at": "2026-04-09T10:30:00.000Z"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "Read and follow /Users/neo/.openclaw/workspace/skills/dream-cycle-verification/SKILL.md.\nContext:\n- Target date: 2026-04-09\n- Report path: /Users/neo/.openclaw/workspace/memory/reports/dream_cycle_verification_2026-04-09.md\nInstructions:\n1. Verify the Dream Cycle run for 2026-04-09 with the provided script and write the report to the report path.\n2. Append a timestamped one-line recap to /Users/neo/.openclaw/workspace/memory/cron-prune.md.\n3. Return the concise verification summary only; do not call the message tool.",
    "model": "openai/gpt-4o-mini",
    "thinking": "minimal",
    "timeoutSeconds": 180,
    "lightContext": true
  },
  "delivery": {
    "mode": "announce",
    "channel": "discord",
    "to": "1482486716584689856",
    "bestEffort": true
  }
}
```

Because `deleteAfterRun` is true, this job is expected to disappear after the April 9, 2026 verification succeeds.

## Restore Procedure

1. Restore the repo to the known-good git point.

```bash
git fetch origin --tags
git switch -c restore-clean-main clean-main-2026-04-08
```

2. Compare the live runtime files with the hashes in this note.

```bash
shasum -a 256 /Users/neo/.openclaw/openclaw.json
shasum -a 256 /Users/neo/.openclaw/cron/jobs.json
shasum -a 256 /Users/neo/.openclaw/agents/main/qmd/xdg-config/qmd/index.yml
```

3. If any hash differs, reapply the snippets in this document to the corresponding runtime file.

4. Restart the gateway.

```bash
openclaw gateway stop
openclaw gateway start
```

5. Re-run the critical checks.

```bash
qmd search 'Codex handoff' -c memory-dir-main
python3 /Users/neo/.openclaw/workspace/scripts/context_usage.py
python3 /Users/neo/.openclaw/workspace/scripts/heartbeat_report.py
```

## Expected Outcomes

- `qmd search` on `memory-dir-main` returns results.
- `context_usage.py` reports an active-session estimate or `no-active-session`, not fake 170k+ "context" from markdown size.
- heartbeat uses `openai/gpt-4o-mini` during the `08:00-22:00` active window.
- Dream Cycle resolves real files and writes grounded output instead of failing on wildcard or directory reads.
