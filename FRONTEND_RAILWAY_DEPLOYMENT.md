# Frontend Railway Deployment Guide

## Overview

The frontend is a Next.js application that can run:
- **Locally** (staging/development): `npm run dev` on `localhost:3000` or `localhost:3002`
- **Railway** (production): Auto-deploys from GitHub

## Railway Configuration

### Required Files

✅ **`frontend/package.json`** - Dependencies and scripts  
✅ **`frontend/next.config.js`** - Next.js configuration with `output: 'standalone'`  
✅ **`frontend/Procfile`** - Contains: `web: npm start`  
✅ **`frontend/railway.toml`** - Railway deployment configuration  

### Build Process

Railway will automatically:
1. Detect Next.js project
2. Run `npm install` to install dependencies
3. Run `npm run build` to build the production app
4. Run `npm start` (from Procfile) to start the server

### Environment Variables

Set these in Railway Dashboard → Frontend Service → Variables:

**Required:**
```
NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app
```

**Optional (for local development):**
- Update `frontend/.env.local` for local development

## Deployment Steps

### 1. Verify Files Are Correct

```bash
# Check package.json exists and has scripts
cat frontend/package.json | grep -A 5 "scripts"

# Check Procfile exists
cat frontend/Procfile
# Should show: web: npm start

# Check next.config.js
cat frontend/next.config.js
```

### 2. Commit and Push

```bash
git add frontend/package.json frontend/next.config.js frontend/Procfile frontend/railway.toml
git commit -m "fix: Restore frontend files for Railway deployment"
git push origin main
```

### 3. Railway Setup

1. **Go to Railway Dashboard**
2. **Create New Service** (if not exists) → **Deploy from GitHub repo**
3. **Select:** `aiclone` repository
4. **Set Root Directory:** `frontend`
5. **Add Environment Variable:**
   - `NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app`
6. Railway will automatically detect Next.js and deploy

### 4. Verify Deployment

After deployment completes:
```bash
# Get your Railway frontend URL from Railway dashboard
curl https://your-frontend-url.up.railway.app

# Should return the Next.js app HTML
```

## Troubleshooting

### 404 Error on Railway

**Problem:** Getting 404 when accessing frontend URL

**Possible Causes:**
1. ❌ Frontend service not deployed on Railway
2. ❌ Root directory not set to `frontend`
3. ❌ Build failed (check Railway logs)
4. ❌ Procfile missing or incorrect

**Solutions:**
1. ✅ Check Railway has a separate frontend service
2. ✅ Verify root directory is set to `frontend` in Railway settings
3. ✅ Check Railway build logs for errors
4. ✅ Ensure `frontend/Procfile` exists with: `web: npm start`

### Build Fails

**Check:**
- `package.json` exists and is valid JSON
- All dependencies are listed in `package.json`
- `next.config.js` is valid

### Runtime Errors

**Check:**
- `NEXT_PUBLIC_API_URL` environment variable is set
- API URL is accessible from Railway
- CORS is configured on backend for Railway frontend URL

## Local Development

For local development:

```bash
cd frontend

# Install dependencies (if needed)
npm install

# Start dev server
npm run dev -- -p 3002

# Access at: http://localhost:3002
```

Update `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app
```

## Production vs Staging

- **Staging (Local):** Run `npm run dev` locally on port 3002
- **Production (Railway):** Auto-deploys from GitHub, accessible via Railway URL


