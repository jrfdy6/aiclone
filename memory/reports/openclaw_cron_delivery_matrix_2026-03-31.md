# OpenClaw Cron Delivery Matrix

Date: 2026-03-31

## Goal

Reduce routine Discord noise without hiding actual blockers, digests, or operational alerts.

## Delivery Classes

- `alert`
  - Immediate issue, blocker, or threshold breach
  - Keep `delivery.mode = "announce"`
- `digest`
  - High-signal summary worth seeing in Discord
  - Keep `delivery.mode = "announce"`
- `silent/log-only`
  - Internal maintenance and archival work
  - Set `delivery.mode = "none"`

## Current Classification

### Alert

- `Context Guard`

### Digest

- `Morning Daily Brief`
- `Progress Pulse`
- `Oracle Ledger`

### Silent / Log-Only

- `GitHub Backup`
- `Nightly Self-Improvement`
- `Rolling Docs`
- `Daily Memory Flush`
- `Weekly Backup`
- `Memory Archive Sweep`
- `Memory Health Check`
- `Dream Cycle`
- `Service Status Monitor` on success
- `Railway & GitHub API Monitor` on success

### Failure-Alert Only

- `Service Status Monitor`
- `Railway & GitHub API Monitor`

## Applied Contract Changes

The following jobs now use `delivery.mode = "none"` in `/Users/neo/.openclaw/cron/jobs.json`:

- `GitHub Backup`
- `Nightly Self-Improvement`
- `Rolling Docs`
- `Daily Memory Flush`
- `Weekly Backup`
- `Memory Archive Sweep`
- `Memory Health Check`
- `Dream Cycle`
- `Service Status Monitor`
- `Railway & GitHub API Monitor`

The following jobs remain `announce`:

- `Oracle Ledger`
- `Morning Daily Brief`
- `Progress Pulse`
- `Context Guard`

The following jobs now use `failureAlert` with Discord announce delivery while keeping routine success delivery silent:

- `Service Status Monitor`
- `Railway & GitHub API Monitor`

## Notes

- This is a conservative first pass.
- Monitor jobs now follow the preferred pattern:
  - success = silent
  - failure = alert
- This pass verified the success-silent path with a manual `Service Status Monitor` run.
- Failure-alert delivery itself is configured, but it has not yet been exercised with a forced failing run.

## Next Step

- Verify the refreshed gateway is honoring the new delivery settings on natural runs.
- If noise is still too high, add a failure-alert layer and then quiet routine monitor successes.
