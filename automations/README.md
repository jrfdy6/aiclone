# Automations

This directory houses standalone automation scripts.

## `workspace_backup.py`

Creates an include-only archive of the OpenClaw workspace, optionally encrypts it, copies
it into a Git repo, and logs the run back to the FastAPI backend so Ops/Brain can visualize
successful runs.

### Usage

```bash
python3 automations/workspace_backup.py \
  --output /path/to/output/dir \
  --include downloads/aiclone knowledge notes \
  --exclude secrets downloads/aiclone/frontend/.next \
  --repo /path/to/backup/repo \
  --encrypt --passphrase "super-secret" \
  --api-url https://aiclone-production-32dc.up.railway.app \
  --api-token $BACKUP_API_TOKEN
```

Key options:

- `--output`: Where to place the generated archives (defaults to `deliverables/backups`).
- `--include`: Relative paths (from the workspace root) that should be archived.
- `--exclude`: Paths that should never be archived (secrets, `node_modules`, etc.).
- `--encrypt/--passphrase`: Enable AES-256 encryption via `openssl`.
- `--repo/--branch`: Optional Git repo folder to store + push backups.
- `--api-url/--api-token`: Optional FastAPI endpoint/token for logging the run to `/api/system/logs`.

Example output:

```json
{
  "id": "86ab2721-f43d-4dec-af4c-d1ca43a1c612",
  "timestamp": "2026-03-08T19:29:58.844118Z",
  "level": "INFO",
  "component": "automation.backup",
  "message": "Workspace backup completed",
  "context": {
    "archive": "workspace-backup-20260308-192958.tar.gz",
    "size_bytes": 74387,
    "sha256": "7c5dcfc5653bed3fe532b9b0a57d14e4684dcf1e5f72fe0f902072e7114e4329",
    "repo_file": null
  }
}
```

> NOTE: The logging step is optional; if `--api-url` is omitted the script simply prints the payload.

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
