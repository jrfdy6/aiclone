# Railway Backend Troubleshooting

## Current Status: 502 Error

The Railway backend is returning `502 Application failed to respond`, which means the app is crashing on startup or not starting at all.

## Most Likely Causes

### 1. Missing Environment Variables (MOST COMMON)

Railway needs these environment variables set:

**Required:**
- `FIREBASE_SERVICE_ACCOUNT` - Full JSON string of Firebase service account
- `GOOGLE_DRIVE_SERVICE_ACCOUNT` - Full JSON string of Google Drive service account

**How to set them:**

1. Go to Railway Dashboard → Your Service → Variables
2. Click "New Variable"
3. For each variable:

**FIREBASE_SERVICE_ACCOUNT:**
```bash
# Run this locally to get the value:
cat keys/firebase-service-account.json | jq -c .
```
Copy the entire output (it's a single line) and paste as the value.

**GOOGLE_DRIVE_SERVICE_ACCOUNT:**
```bash
# Run this locally to get the value:
cat keys/aiclone-drive-ingest-e717f9932b1b.json | jq -c .
```
Copy the entire output (it's a single line) and paste as the value.

4. After adding variables, Railway will automatically redeploy (wait 2-3 minutes)

### 2. Check Railway Logs

1. Go to Railway Dashboard → Your Service → Deployments
2. Click on the latest deployment
3. Check "Build Logs" and "Deploy Logs"
4. Look for errors like:
   - "Invalid JWT Signature" → Firebase credentials issue
   - "Firestore API not enabled" → Need to enable in Firebase Console
   - "Module not found" → Missing dependency in requirements.txt
   - "Port already in use" → Port configuration issue

### 3. Common Errors and Fixes

**Error: "Invalid JWT Signature"**
- Fix: Regenerate Firebase service account key and update `FIREBASE_SERVICE_ACCOUNT`

**Error: "Firestore API not enabled"**
- Fix: Go to Firebase Console → Enable Firestore Database

**Error: "Drive API not enabled"**
- Fix: Go to Google Cloud Console → Enable Google Drive API

**Error: "Module not found: requests"**
- Fix: Ensure `requests` is in `backend/requirements.txt` (it should be)

**Error: "Application failed to respond"**
- Fix: Check that `Procfile` exists and contains:
  ```
  web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

### 4. Verify Deployment

After setting environment variables and redeploying:

```bash
# Test root endpoint
curl https://aiclone-production-32dc.up.railway.app/
# Should return: {"status":"aiclone backend running"}

# Test API endpoint
curl https://aiclone-production-32dc.up.railway.app/api/playbook/summary
# Should return JSON with playbook summary
```

### 5. Quick Fix Checklist

- [ ] `FIREBASE_SERVICE_ACCOUNT` is set in Railway (full JSON string)
- [ ] `GOOGLE_DRIVE_SERVICE_ACCOUNT` is set in Railway (full JSON string)
- [ ] Railway has redeployed after setting variables (check Deployments tab)
- [ ] Firestore Database is created in Firebase Console
- [ ] Google Drive API is enabled in Google Cloud Console
- [ ] `Procfile` exists in backend/ directory
- [ ] `requirements.txt` includes all dependencies (especially `requests`)

## Next Steps

1. Set the environment variables in Railway (see above)
2. Wait for automatic redeploy (2-3 minutes)
3. Check Railway logs for any startup errors
4. Test the endpoints again
5. If still failing, share the Railway logs and I'll help debug


