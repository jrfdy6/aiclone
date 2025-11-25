# Fix: API URL Configuration Error

## Problem

The frontend is making requests to incorrect URLs like:
```
https://aiclone-frontend-production.up.railway.app/aiclone-production-32dc.up.railway.app/api/prospects
```

This happens when `NEXT_PUBLIC_API_URL` is set incorrectly in Railway.

## Root Cause

The `NEXT_PUBLIC_API_URL` environment variable in Railway is missing the `https://` protocol, causing it to be treated as a relative URL.

## Solution

### Step 1: Fix Railway Environment Variable

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Select your **frontend service**
3. Go to **Settings** → **Variables**
4. Find `NEXT_PUBLIC_API_URL`
5. **Update the value** to include the full protocol:

   **Current (WRONG):**
   ```
   aiclone-production-32dc.up.railway.app
   ```

   **Should be (CORRECT):**
   ```
   https://aiclone-production-32dc.up.railway.app
   ```

6. Click **Save**
7. Railway will automatically redeploy

### Step 2: Verify After Redeploy

After Railway redeploys (2-3 minutes):

1. Visit your frontend URL
2. Open browser DevTools → Console
3. Check that API requests are now going to:
   ```
   https://aiclone-production-32dc.up.railway.app/api/...
   ```
   Instead of:
   ```
   https://aiclone-frontend-production.up.railway.app/aiclone-production-32dc.up.railway.app/api/...
   ```

## Code Fix (Already Applied)

The code has been updated to handle URLs without protocols automatically:
- `frontend/lib/api-client.ts` - Now adds `https://` if protocol is missing
- `frontend/app/prospects/page.tsx` - Now uses `getApiUrl()` helper

However, **you still need to fix the Railway environment variable** to ensure it works correctly.

## Quick Check

To verify your environment variable is set correctly:

```bash
# In Railway, the variable should be:
NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app

# NOT:
NEXT_PUBLIC_API_URL=aiclone-production-32dc.up.railway.app
```

## Alternative: Use Railway CLI

If you prefer CLI:

```bash
railway variables set NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app
```

---

**Status:** Code fix applied, but Railway environment variable needs to be updated manually.

