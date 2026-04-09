# Heartbeat Recovery Playbook

Use this runbook whenever heartbeat diagnostics fail to reach Discord. The goal is to point the OpenClaw heartbeat agent at an accessible provider, verify `scripts/heartbeat_report.py` output, and confirm timestamps advance again.

## 1. Update the heartbeat model

Run the helper script from the repo root. It patches `~/.openclaw/openclaw.json`, preserves a `.bak` copy, and keeps the alias map in sync.

```bash
cd /Users/neo/.openclaw/workspace
python3 scripts/update_heartbeat_model.py \
  --config ~/.openclaw/openclaw.json \
  --model openai/gpt-4o-mini
```

- If you need a different provider, pass `--model <vendor/model-id>`.
- Use `--no-backup` only if you already have an external snapshot; by default the script writes `<config>.bak`.

## 2. Restart (or wait for) the heartbeat cron

After updating the config:

1. Restart the OpenClaw agent service or wait for the next scheduled heartbeat tick (30 minutes by default).
2. Watch `~/.openclaw/logs/gateway.log` for a fresh `[heartbeat] started` line stamped after the config change.

## 3. Verify diagnostics

Once a heartbeat runs:

1. Capture the sensor snapshot: `python3 scripts/heartbeat_report.py`.
2. Ensure the reply posted to Discord cites at least one timestamp/metric from that report (per `HEARTBEAT.md`).
3. Confirm `memory/heartbeat-state.json` updated within the same hour; rerun the helper with `--append-log` if you need a persistent daily entry.

## 4. If the run still fails

- Re-run the script with a different `--model` known to be reachable from the host.
- Check network restrictions (this Codex sandbox cannot reach `127.0.0.1:11434`, so local Ollama endpoints will continue to fail).
- If the heartbeat prompt itself needs edits, update `HEARTBEAT.md` and `HEARTBEAT_GUIDANCE.md` before retrying.

Document every verification pass in `workspaces/shared-ops/memory/execution_log.md` and keep the PM card in `review` until a Discord message includes the required diagnostics.
