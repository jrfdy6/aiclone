# 🚂 Railway Frontend Deployment - Quick Start

## ✅ Pre-Deployment Checklist

- [x] ✅ Railway config files created (`nixpacks.toml`, `Procfile`, `railway.toml`)
- [x] ✅ Next.js config updated for production
- [x] ✅ Build tested locally (successful)
- [x] ✅ TypeScript errors fixed
- [x] ✅ Environment variable template created

## 🚀 Deploy in 5 Minutes

### Step 1: Create Railway Service (2 min)

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Select your existing project (or create new)
3. Click **"+ New"** → **"GitHub Repo"**
4. Select `aiclone` repository
5. Railway will auto-detect Next.js ✅

### Step 2: Configure Root Directory (30 sec)

1. Go to **Settings** → **Source**
2. Set **Root Directory:** `frontend`
3. Save

### Step 3: Set Environment Variable (1 min)

1. Go to **Settings** → **Variables**
2. Click **"+ New Variable"**
3. Add:
   ```
   Name:  NEXT_PUBLIC_API_URL
   Value: https://aiclone-production-32dc.up.railway.app
   ```
4. Click **Save**

### Step 4: Wait & Get URL (2 min)

- Railway will auto-deploy (watch logs)
- Build takes ~2-5 minutes
- You'll get a URL like: `https://aiclone-frontend-xyz.up.railway.app`

### Step 5: Update Backend CORS (1 min)

1. Copy your frontend Railway URL
2. Go to **Backend service** → **Variables**
3. Add/Update `CORS_ADDITIONAL_ORIGINS`:
   ```
   Value: https://aiclone-frontend-xyz.up.railway.app
   ```
4. Backend will auto-redeploy

## ✅ Verify Deployment

1. **Visit your frontend URL** in a browser
2. **Check browser console** for errors
3. **Test API connection** by navigating to pages that make API calls

## 📋 Configuration Files Created

| File | Purpose |
|------|---------|
| `frontend/nixpacks.toml` | Build configuration for Railway |
| `frontend/Procfile` | Start command for Railway |
| `frontend/railway.toml` | Railway-specific settings |
| `frontend/verify-deployment.sh` | Deployment verification script |

## 🔧 Troubleshooting

**Build fails?**
- Check Railway logs for specific errors
- Verify all dependencies are in `package.json`
- Ensure TypeScript errors are fixed (we've already done this)

**CORS errors?**
- Make sure frontend URL is added to backend `CORS_ADDITIONAL_ORIGINS`
- Wait for backend to redeploy after adding CORS

**API connection fails?**
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check backend is running: `https://aiclone-production-32dc.up.railway.app/`

## 📚 Full Documentation

See `RAILWAY_FRONTEND_DEPLOYMENT.md` for detailed troubleshooting and advanced configuration.

---

**Ready to deploy!** 🚀 Follow the 5 steps above and you'll be live in minutes.

