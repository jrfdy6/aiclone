# Fix CORS for Railway Backend with localhost:3002

## Problem
The Railway backend at `https://aiclone-production-32dc.up.railway.app` is not allowing requests from `http://localhost:3002` due to CORS policy.

## Solution

The code has been updated to include `localhost:3002` in the CORS allowed origins. You need to deploy this updated code to Railway.

### Option 1: Deploy Updated Code to Railway (Recommended)

1. **Commit and push the updated code:**
   ```bash
   cd /Users/johnniefields/Desktop/Cursor/aiclone
   git add backend/app/main.py
   git commit -m "Add localhost:3002 to CORS origins"
   git push origin main
   ```

2. **Railway will automatically redeploy** if it's connected to your GitHub repo

3. **Wait 2-3 minutes** for Railway to build and deploy

4. **Test the connection:**
   ```bash
   curl -H "Origin: http://localhost:3002" https://aiclone-production-32dc.up.railway.app/api/playbook/summary
   ```

### Option 2: Add Environment Variable (If code is already deployed)

If the Railway backend already has the updated code with environment variable support:

1. Go to Railway Dashboard → Your Service → Variables
2. Add a new variable:
   - **Name:** `CORS_ADDITIONAL_ORIGINS`
   - **Value:** `http://localhost:3002,http://127.0.0.1:3002`
3. Railway will automatically redeploy

### Current CORS Configuration

The backend code now includes these origins by default:
- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `http://localhost:3002` ✅ (NEW)
- `http://127.0.0.1:3002` ✅ (NEW)
- `https://aiclone-production-32dc.up.railway.app`

### Verify CORS is Working

After deployment, test with:
```bash
curl -H "Origin: http://localhost:3002" \
  https://aiclone-production-32dc.up.railway.app/api/playbook/summary
```

You should see `access-control-allow-origin: http://localhost:3002` in the response headers.

