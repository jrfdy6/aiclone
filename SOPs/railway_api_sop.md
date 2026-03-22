# SOP: Railway API Usage

## Purpose
Keep Railway debugging grounded in the real failure mode instead of guessing from browser symptoms.

## Canonical services
- Frontend: `aiclone-frontend`
- Backend: `aiclone-backend`
- Production frontend URL: `https://aiclone-frontend-production.up.railway.app`
- Production backend URL: `https://aiclone-production-32dc.up.railway.app`

## Standard checks
```bash
cd /Users/neo/.openclaw/workspace
railway service status --service aiclone-frontend
railway service status --service aiclone-backend
railway deployment list --service aiclone-frontend
railway deployment list --service aiclone-backend
```

## API verification
```bash
curl -sS https://aiclone-production-32dc.up.railway.app/health
curl -sS https://aiclone-production-32dc.up.railway.app/api/open-brain/health
curl -sS https://aiclone-production-32dc.up.railway.app/api/pm/cards?limit=1
curl -sS https://aiclone-production-32dc.up.railway.app/api/standups/?limit=1
```

For browser-origin checks, test preflight directly:

```bash
curl -i -sS -X OPTIONS \
  https://aiclone-production-32dc.up.railway.app/api/analytics/compliance \
  -H 'Origin: https://aiclone-frontend-production.up.railway.app' \
  -H 'Access-Control-Request-Method: GET'
```

## Troubleshooting sequence
1. Confirm there is a real Git commit containing the needed files. Generated snapshots, lockfile changes, and compatibility exports may exist locally while Railway still builds an older SHA.
2. Check `railway service status --service ...` before trusting browser errors.
3. If the browser shows CORS plus `ERR_FAILED` or `502`, treat it as a likely backend crash first.
4. Pull logs with `railway logs --service aiclone-backend` or `railway logs --service aiclone-frontend`.
5. Read the exact missing import, route, or module from the log before editing code.
6. If the fix is local only, commit it, push it, and redeploy the affected service.
7. Verify the live endpoint with `curl` after the deploy instead of assuming the Railway status page tells the whole story.

## Known failure patterns
- Browser CORS errors can be caused by a crashed backend returning no CORS headers at all.
- Frontend build failures often come from missing committed generated files such as `workspaceSnapshot.ts`, or missing dependency/lockfile changes.
- Railway can keep serving the previous successful build while a newer deployment is still `BUILDING` or `FAILED`.
- Frontend and backend must be debugged independently; one service being healthy does not prove the other is current.
