# 🚂 Railway Frontend Deployment Guide

## Quick Deploy Steps

### 1. Create New Railway Service

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click on your existing project (or create new)
3. Click **"+ New"** → **"GitHub Repo"**
4. Select your `aiclone` repository

### 2. Configure Service

Once service is created:

1. Go to **Settings** → **Source**
2. Set **Root Directory:** `frontend`
3. Railway will auto-detect Next.js

### 3. Set Environment Variable

1. Go to **Settings** → **Variables**
2. Click **"+ New Variable"**
3. Add:
   - **Name:** `NEXT_PUBLIC_API_URL`
   - **Value:** `https://aiclone-production-32dc.up.railway.app`
4. Click **Save**

Railway will automatically redeploy after adding the variable.

### 4. Configure CORS on Backend (One-Time)

The backend needs to allow requests from your Railway frontend URL:

1. After Railway deploys your frontend, get the URL (e.g., `https://aiclone-frontend-xyz.up.railway.app`)
2. Go to your **backend service** on Railway → **Variables**
3. Add/Update `CORS_ADDITIONAL_ORIGINS`:
   - **Value:** `https://aiclone-frontend-xyz.up.railway.app` (your actual frontend URL)
   - Or add multiple: `https://aiclone-frontend-xyz.up.railway.app,http://localhost:3000`

### 5. Wait for Deployment

Railway will:
- Install dependencies (`npm install`)
- Build the app (`npm run build`)
- Start the server (`npm start`)
- Provide you with a URL

**Build time:** 2-5 minutes

---

## Configuration Files Created

I've created these files to help Railway deploy correctly:

- ✅ `frontend/nixpacks.toml` - Nixpacks build configuration
- ✅ `frontend/Procfile` - Start command for Railway
- ✅ `frontend/railway.toml` - Railway-specific settings

These ensure Railway knows:
- How to build your Next.js app
- How to start the server
- Which Node.js version to use

---

## Verification

After deployment:

1. **Check Railway Logs:**
   - Go to your frontend service → **Deployments** → Latest deployment
   - Check "Deploy Logs" for errors
   - Should see: "Ready - started server on 0.0.0.0:PORT"

2. **Test Frontend:**
   - Visit your Railway frontend URL
   - Check browser console for errors
   - Try navigating to `/prospects`, `/dashboard`, etc.

3. **Test API Connection:**
   - Open browser DevTools → Network tab
   - Navigate to a page that makes API calls
   - Check if requests to backend are successful

---

## Troubleshooting

### Build Fails

**Error: "Cannot find module"**
- Solution: Ensure all dependencies are in `package.json`
- Check that `@tanstack/react-query`, `date-fns`, `zustand` are in dependencies (not devDependencies)

**Error: "TypeScript errors"**
- Solution: Fix any TypeScript errors locally first
- Run `npm run build` locally to catch errors

### App Won't Start

**Error: "Port already in use"**
- Solution: Railway sets PORT automatically, Next.js will use it
- Make sure your `package.json` has `"start": "next start"`

**Error: "Application failed to respond"**
- Check Railway logs for the actual error
- Verify the build completed successfully

### CORS Errors

**Error: "Access-Control-Allow-Origin"**
- Add your Railway frontend URL to backend `CORS_ADDITIONAL_ORIGINS`
- Backend service → Variables → Add/Update `CORS_ADDITIONAL_ORIGINS`

### API Connection Errors

**Error: "Failed to fetch"**
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check that backend is running: `https://aiclone-production-32dc.up.railway.app/health`
- Check browser console for actual error message

---

## Environment Variables Needed

### Frontend Service

**Required:**
- `NEXT_PUBLIC_API_URL` = `https://aiclone-production-32dc.up.railway.app`

**Optional:**
- `NODE_ENV` = `production` (set automatically)
- `PORT` = Railway sets automatically

### Backend Service (Update CORS)

**Add/Update:**
- `CORS_ADDITIONAL_ORIGINS` = `https://your-frontend-url.up.railway.app`

---

## Deployment Checklist

- [ ] Created new Railway service for frontend
- [ ] Set Root Directory to `frontend`
- [ ] Set `NEXT_PUBLIC_API_URL` environment variable
- [ ] Railway auto-detected Next.js (or configured manually)
- [ ] Build completed successfully (check logs)
- [ ] Frontend URL received from Railway
- [ ] Added frontend URL to backend CORS (`CORS_ADDITIONAL_ORIGINS`)
- [ ] Tested frontend in browser
- [ ] Verified API calls are working (check browser console)
- [ ] All pages load correctly

---

## Railway Service Structure

Your Railway project will have:

```
Railway Project: aiclone
├── Service 1: Backend (FastAPI)
│   ├── Root: backend/
│   ├── URL: https://aiclone-production-32dc.up.railway.app
│   └── Port: 8080 (auto-set)
│
└── Service 2: Frontend (Next.js)
    ├── Root: frontend/
    ├── URL: https://aiclone-frontend-xyz.up.railway.app
    └── Port: (auto-set by Railway)
```

---

## Quick Deploy Commands (Alternative: Railway CLI)

If you prefer CLI:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# From frontend directory
cd frontend

# Link to Railway project
railway link

# Set environment variable
railway variables set NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app

# Deploy
railway up
```

---

## Expected Build Output

When Railway builds, you should see:

```
✓ Compiled successfully
✓ Linting and checking validity of types
✓ Collecting page data
✓ Generating static pages
✓ Finalizing page optimization

Route (app)                              Size     First Load JS
┌ ○ /                                    1.71 kB          89 kB
├ ○ /content-marketing                   2.41 kB        89.7 kB
├ ○ /jumpstart                           2.12 kB        98.1 kB
├ ○ /knowledge                           1.45 kB        88.7 kB
└ ○ /prospecting                         3.1 kB         99.1 kB
+ First Load JS shared by all            87.2 kB
```

Then:
```
✓ Ready - started server on 0.0.0.0:PORT
```

**✅ Build Verified:** The frontend has been successfully built locally and is ready for Railway deployment!

---

**Ready to deploy!** Follow the steps above and your frontend will be live on Railway! 🚂

