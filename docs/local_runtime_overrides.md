# Local Runtime Overrides

This document defines the local OpenClaw runtime settings the cron/memory lane expects.

## Config File

- `~/.openclaw/openclaw.json`

## Required Guardrails

- `agents.defaults.compaction.reserveTokensFloor >= 40000`
- `agents.defaults.compaction.memoryFlush.softThresholdTokens >= 4000`
- `agents.defaults.compaction.memoryFlush.enabled = true`

## Validation Commands

```bash
python3 /Users/neo/.openclaw/workspace/scripts/check_local_runtime_overrides.py
python3 /Users/neo/.openclaw/workspace/scripts/compaction_guardrail_check.py
```

## Notes

- If OpenClaw is reinstalled or upgraded, re-check this file and rerun the validation commands.
- This compatibility document exists because multiple startup docs and cron jobs rely on a stable local-runtime reference.
