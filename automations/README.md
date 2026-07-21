# Automations

> Authority: active directory guide subordinate to [SOURCE_OF_TRUTH.md](../SOURCE_OF_TRUTH.md) and the status-indexed [Codex-Native Local Automation SOP](../SOPs/codex_native_local_automation_sop.md).

This directory houses standalone automation scripts.

## Secure backups

The old Git-backed workspace archive is retired. Backups now stay private under
`/Users/neo/.codex/ai-clone/backups`, exclude secrets and generated dependencies,
and write run truth locally before attempting an authenticated Railway metadata mirror.

```bash
python3 scripts/run_secure_project_snapshot.py --keep 7
python3 scripts/run_secure_config_backup.py --keep 8
```

Never copy these archives into the project or push them to GitHub.

## `persona_bundle_sync.py`

Pulls committed `persona_deltas` from the backend, writes the selected promotion items into the
local canonical bundle under `knowledge/persona/feeze/`, and patches the delta metadata back to
`local_bundle_sync.state = synced`.

### Usage

```bash
python3 automations/persona_bundle_sync.py \
  --api-url https://aiclone-production-32dc.up.railway.app
```

Helpful options:

- `--delta-id`: sync one specific committed delta
- `--limit`: cap how many committed deltas are scanned
- `--dry-run`: preview which deltas would be written without touching disk or remote metadata

Recommended operating model:

- Brain `Commit to canon` updates runtime canon immediately.
- `persona_bundle_sync.py` is the local durability step that makes the same promotion survive deploys and feed bundle-first content generation.

Install the local LaunchAgent:

```bash
cp /Users/neo/Documents/Codex/AI-Clone/automations/com.neo.persona_bundle_sync.plist ~/Library/LaunchAgents/com.neo.persona_bundle_sync.plist
launchctl bootout "gui/$UID" ~/Library/LaunchAgents/com.neo.persona_bundle_sync.plist 2>/dev/null || true
launchctl bootstrap "gui/$UID" ~/Library/LaunchAgents/com.neo.persona_bundle_sync.plist
```

Check the latest sync log:

```bash
tail -n 40 /Users/neo/.codex/ai-clone/logs/persona_bundle_sync.log
```
