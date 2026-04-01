# OpenClaw Cron Model Tiering - 2026-03-31

## Outcome

`gpt-5-nano` is now enabled in `/Users/neo/.openclaw/openclaw.json` and validated in live OpenClaw cron execution.

Validated runs:
- `Service Status Monitor` (`5df06846-d56a-43dd-b09d-7a27a6476ce9`) finished `ok` on `gpt-5-nano`
- `Memory Health Check` (`63fb57ed-9c42-4a24-afff-adbcfd6a0aaf`) finished `ok` on `gpt-5-nano`

## Important Finding

Editing `jobs.json` alone was not enough at first because the gateway rejected `openai/gpt-5-nano` as "not allowed" and silently fell back to the agent default model.

Fix applied:
- added `openai/gpt-5-nano` to the allowed agent model list in `/Users/neo/.openclaw/openclaw.json`
- restarted the OpenClaw gateway

Gateway evidence:
- `gateway.err.log` recorded: `payload.model 'openai/gpt-5-nano' not allowed, falling back to agent defaults`
- after allowing the model, live runs reported `model: gpt-5-nano`

## Current Model Split

### Keep on `openai/gpt-4o-mini`
- `Oracle Ledger`
- `Nightly Self-Improvement`
- `Morning Daily Brief`
- `Progress Pulse`
- `Context Guard`
- `Dream Cycle`

Reason:
- higher judgment
- more synthesis
- more likely to need stable nuance or alert quality

### Move to `openai/gpt-5-nano`
- `GitHub Backup`
- `Rolling Docs`
- `Daily Memory Flush`
- `Weekly Backup`
- `Memory Archive Sweep`
- `Memory Health Check`
- `Service Status Monitor`
- `Railway & GitHub API Monitor`

Reason:
- lower-risk maintenance or deterministic monitoring
- prompt/task shape is more constrained
- cheaper runtime is more attractive here

## Next Check

Watch the next scheduled runs for:
- `Rolling Docs`
- `Daily Memory Flush`
- `Railway & GitHub API Monitor`

If those remain healthy, the tiering can be treated as production-safe.
