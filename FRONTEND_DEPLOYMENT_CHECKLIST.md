# Frontend Deployment Checklist

## ✅ Code Pushed
- Changes have been committed and pushed to `main` branch
- New files:
  - `frontend/app/api-test/page.tsx` - Google Search test page
  - `GOOGLE_SEARCH_PRODUCTION_TEST.md` - Testing guide
  - Updated `frontend/app/page.tsx` - Added link to test page

## 🚂 Railway Deployment Steps

### If Frontend Service Already Exists

1. **Railway will auto-deploy** from the `main` branch push
2. **Check deployment status:**
   - Go to [Railway Dashboard](https://railway.app/dashboard)
   - Find your frontend service
   - Check "Deployments" tab for latest deployment
   - Wait 2-5 minutes for build to complete

3. **Verify environment variable:**
   - Go to your frontend service → **Settings** → **Variables**
   - Ensure `NEXT_PUBLIC_API_URL` is set to: `https://aiclone-production-32dc.up.railway.app`
   - If missing, add it and Railway will redeploy

4. **Update backend CORS (if needed):**
   - After deployment, get your frontend URL from Railway
   - Go to backend service → **Variables**
   - Add/Update `CORS_ADDITIONAL_ORIGINS` with your frontend URL

### If Frontend Service Doesn't Exist Yet

1. **Create New Service:**
   - Go to [Railway Dashboard](https://railway.app/dashboard)
   - Click on your project (or create new)
   - Click **"+ New"** → **"GitHub Repo"**
   - Select your `aiclone` repository

2. **Configure Service:**
   - Go to **Settings** → **Source**
   - Set **Root Directory:** `frontend`
   - Railway will auto-detect Next.js

3. **Set Environment Variable:**
   - Go to **Settings** → **Variables**
   - Click **"+ New Variable"**
   - Add:
     - **Name:** `NEXT_PUBLIC_API_URL`
     - **Value:** `https://aiclone-production-32dc.up.railway.app`
   - Click **Save**

4. **Wait for Deployment:**
   - Railway will automatically:
     - Install dependencies (`npm install`)
     - Build the app (`npm run build`)
     - Start the server (`npm start`)
   - Build time: 2-5 minutes

5. **Get Frontend URL:**
   - After deployment, Railway will provide a URL
   - Example: `https://aiclone-frontend-xyz.up.railway.app`
   - Copy this URL

6. **Update Backend CORS:**
   - Go to your **backend service** on Railway
   - Go to **Settings** → **Variables**
   - Add/Update `CORS_ADDITIONAL_ORIGINS`:
     - **Value:** `https://your-frontend-url.up.railway.app`
     - Or multiple: `https://your-frontend-url.up.railway.app,http://localhost:3000`

## ✅ Verification Steps

After deployment completes:

1. **Check Railway Logs:**
   - Go to frontend service → **Deployments** → Latest deployment
   - Check "Deploy Logs"
   - Should see: `✓ Ready - started server on 0.0.0.0:PORT`

2. **Test Frontend:**
   - Visit your Railway frontend URL
   - Should see the home page with all feature cards
   - Check browser console for errors

3. **Test New Test Page:**
   - Navigate to `/api-test`
   - Should see the Google Custom Search test page
   - Try running a test

4. **Test API Connection:**
   - Open browser DevTools → Network tab
   - Navigate to a page that makes API calls
   - Check if requests to backend are successful (status 200)

## 🔧 Troubleshooting

### Build Fails
- Check Railway logs for specific error
- Common issues:
  - Missing dependencies (check `package.json`)
  - TypeScript errors (run `npm run build` locally first)
  - Node version mismatch (check `nixpacks.toml`)

### App Won't Start
- Check Railway logs for startup errors
- Verify `package.json` has `"start": "next start"`
- Railway sets PORT automatically

### CORS Errors
- Add frontend URL to backend `CORS_ADDITIONAL_ORIGINS`
- Format: `https://your-frontend-url.up.railway.app`

### API Connection Errors
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check backend is running: `https://aiclone-production-32dc.up.railway.app/health`
- Check browser console for actual error message

## 📋 Quick Reference

**Backend URL:** `https://aiclone-production-32dc.up.railway.app`

**Frontend Environment Variable:**
- `NEXT_PUBLIC_API_URL` = `https://aiclone-production-32dc.up.railway.app`

**Backend Environment Variable (CORS):**
- `CORS_ADDITIONAL_ORIGINS` = `https://your-frontend-url.up.railway.app`

**New Test Page:** `/api-test` (for testing Google Custom Search)

## 🎯 Next Steps

1. ✅ Code pushed to GitHub
2. ⏳ Wait for Railway to deploy (2-5 minutes)
3. ⏳ Verify deployment in Railway dashboard
4. ⏳ Test frontend URL in browser
5. ⏳ Test `/api-test` page
6. ⏳ Update backend CORS if needed

---

**Status:** Code pushed, waiting for Railway deployment! 🚂

