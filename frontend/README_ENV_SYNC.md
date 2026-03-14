# Railway Environment Sync

This service relies on secrets stored locally at `workspace/secrets/railway.env`. To keep the deployed Railway services in sync:

1. Copy every `KEY=VALUE` entry from `workspace/secrets/railway.env` into the Railway project’s environment variable list (`railway env`). The important ones for the frontend/backend handshake include:
   - `NEXT_PUBLIC_API_URL` (frontend uses this everywhere via `lib/api-client.ts`).
   - `OPEN_BRAIN_DATABASE_URL` (backend connects to Postgres).
   - API keys: `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`, `FIRECRAWL_API_KEY`, `GOOGLE_CUSTOM_SEARCH_API_KEY`, etc.
- Service-account blobs: `FIREBASE_SERVICE_ACCOUNT`, `GOOGLE_DRIVE_SERVICE_ACCOUNT` (backend reads these from the environment).
- `CRON_ACCESS_TOKEN`, `CORS_ADDITIONAL_ORIGINS`, etc., to keep tooling and cron jobs aligned.

<!-- cache-bust: 2026-03-14 -->

2. After updating variables, redeploy the Railway service (`railway up` or via the dashboard) so both the backend and frontend build with the new values.

3. To verify, run:
   ```bash
   NEXT_PUBLIC_API_URL=<value> curl "$NEXT_PUBLIC_API_URL/api/dashboard"
   ```
   Ensure the response matches the `WidgetData` shape used by the dashboard (recent insights, top prospects, follow-ups, content ideas).

4. Watch Railway logs for the frontend service after deployment to confirm no `NEXT_PUBLIC_API_URL is not configured` errors appear.

If the secrets change often, you can script the sync with:
```bash
while IFS='=' read -r key value; do
  railway env set "$key" "$value"
done < workspace/secrets/railway.env
```
Use this from the workspace root and rerun only when the file changes.
