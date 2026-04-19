# Gmail Inbox Connection Runbook

## Purpose

Connect the shared inbox runtime to the live Gmail account for `neo512235@gmail.com`.

This runbook covers both:

- the host-only OAuth step that creates the Gmail token locally
- the production handoff that moves the inbox from local files to Railway env vars

## Expected Local Paths

- OAuth client JSON:
  - `/Users/neo/.openclaw/secrets/gmail_oauth_client.json`
- OAuth token output:
  - `/Users/neo/.openclaw/secrets/gmail_oauth_token.json`

The OAuth client JSON must not be committed.

## One-Time Setup

1. In Google Cloud, create the Gmail OAuth desktop client for `neo512235@gmail.com`.
2. Download the client JSON.
3. Save it as:
   - `/Users/neo/.openclaw/secrets/gmail_oauth_client.json`

## Verify Current Status

Run:

```bash
/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python \
  /Users/neo/.openclaw/workspace/scripts/connect_gmail_inbox.py --status
```

Expected before authorization:

- `configured: true`
- `connected: false`
- `dependencies_ready: true`

## Authorize Gmail Access

Run:

```bash
/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python \
  /Users/neo/.openclaw/workspace/scripts/connect_gmail_inbox.py
```

If you do not want the script to auto-open a browser:

```bash
/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python \
  /Users/neo/.openclaw/workspace/scripts/connect_gmail_inbox.py --no-browser
```

The script will:

- open a local OAuth flow
- let you sign in as `neo512235@gmail.com`
- request the configured Gmail scope
- write the token to:
  - `/Users/neo/.openclaw/secrets/gmail_oauth_token.json`

## After Authorization

Run status again:

```bash
/Users/neo/.openclaw/workspace/.venv-main-safe/bin/python \
  /Users/neo/.openclaw/workspace/scripts/connect_gmail_inbox.py --status
```

Expected:

- `configured: true`
- `connected: true`
- `token_present: true`

## Runtime Behavior

Once connected:

- `/api/email/google/status` reports the inbox as connected
- `/api/email/sync` pulls live Gmail threads using the configured query
- `/inbox` stops relying on seeded sample-only state after a live sync succeeds

## Production Handoff

For Railway or any other deployed backend, do not rely on:

- `/Users/neo/.openclaw/secrets/gmail_oauth_client.json`
- `/Users/neo/.openclaw/secrets/gmail_oauth_token.json`

Instead, set these backend env vars from the local files:

- `GOOGLE_GMAIL_ACCOUNT_EMAIL`
- `GOOGLE_GMAIL_OAUTH_CLIENT_JSON`
- `GOOGLE_GMAIL_OAUTH_TOKEN_JSON`
- `GOOGLE_GMAIL_SYNC_QUERY`
- `GOOGLE_GMAIL_SYNC_MAX_RESULTS`

Suggested values:

- `GOOGLE_GMAIL_ACCOUNT_EMAIL=neo512235@gmail.com`
- `GOOGLE_GMAIL_SYNC_QUERY=in:inbox`
- `GOOGLE_GMAIL_SYNC_MAX_RESULTS=50`

One safe way to extract compact JSON locally before pasting into Railway:

```bash
python3 - <<'PY'
import json
from pathlib import Path

for label, path in (
    ("client", Path("/Users/neo/.openclaw/secrets/gmail_oauth_client.json")),
    ("token", Path("/Users/neo/.openclaw/secrets/gmail_oauth_token.json")),
):
    print(f"{label}={json.dumps(json.loads(path.read_text()), separators=(',', ':'))}")
PY
```

Use the printed `client=` value for `GOOGLE_GMAIL_OAUTH_CLIENT_JSON` and the printed `token=` value for `GOOGLE_GMAIL_OAUTH_TOKEN_JSON`.

## Current Defaults

- account email: `neo512235@gmail.com`
- query: `in:inbox`
- max results: `50`
- scope: `https://www.googleapis.com/auth/gmail.readonly`

## Notes

- The current integration is read-only.
- Draft generation still happens locally in the app.
- Sending Gmail replies is not wired yet and would require re-authorizing with a broader scope.
