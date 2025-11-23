# Railway Deployment Setup

## Environment Variables Required

Set these in Railway Dashboard → Your Service → Variables:

### 1. Firebase Service Account (REQUIRED)
**Variable:** `FIREBASE_SERVICE_ACCOUNT`  
**Value:** The entire contents of `keys/firebase-service-account.json` as a single-line JSON string

**How to get it:**
```bash
# From your local machine, run:
cat keys/firebase-service-account.json | jq -c .
```

Copy the entire output and paste it as the value for `FIREBASE_SERVICE_ACCOUNT` in Railway.

### 2. Google Drive Service Account (REQUIRED)
**Variable:** `GOOGLE_DRIVE_SERVICE_ACCOUNT`  
**Value:** The entire contents of `keys/aiclone-drive-ingest-e717f9932b1b.json` as a single-line JSON string

**How to get it:**
```bash
# From your local machine, run:
cat keys/aiclone-drive-ingest-e717f9932b1b.json | jq -c .
```

Copy the entire output and paste it as the value for `GOOGLE_DRIVE_SERVICE_ACCOUNT` in Railway.

### 3. Port (OPTIONAL - Railway sets this automatically)
**Variable:** `PORT`  
**Value:** Railway automatically sets this, but if needed, use `8080`

## Verification Steps

1. After setting variables, Railway will automatically redeploy
2. Check Railway logs to ensure:
   - ✅ Firebase initialized successfully
   - ✅ Drive client initialized successfully
   - ✅ Server started on port 8080

3. Test the deployment:
   ```bash
   curl https://aiclone-production-32dc.up.railway.app/
   # Should return: {"status":"aiclone backend running"}
   ```

## Frontend Configuration

Once Railway is deployed, update `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app
```

Then restart the frontend:
```bash
cd frontend && npm run dev
```

## Troubleshooting

- **"Invalid JWT Signature"**: Firebase service account JSON is malformed or expired
- **"Firestore API not enabled"**: Enable Firestore in Firebase Console
- **"Drive API not enabled"**: Enable Google Drive API in Google Cloud Console
- **CORS errors**: Backend CORS already includes Railway URL in `main.py`


