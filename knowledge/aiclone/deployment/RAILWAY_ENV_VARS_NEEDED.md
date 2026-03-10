# 🚨 CRITICAL: Environment Variables Must Be Set BEFORE Deployment

## The Problem

Your frontend is returning 500 errors on ALL pages because it's trying to use environment variables that don't exist yet.

## ✅ Required Fix

**Before the next deployment works, you MUST set these environment variables in Railway:**

### Railway Frontend Service → Variables → Add:

```bash
# REQUIRED - Without this, /kb/[query] pages will crash
NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app

# OPTIONAL - Pages work without this but won't show research
FIREBASE_SERVICE_ACCOUNT=<your-firebase-service-account-json>

# OPTIONAL - Defaults to "default-user" if not set
DEFAULT_USER_ID=default-user

# OPTIONAL - For sitemap URLs
NEXT_PUBLIC_SITE_URL=https://aiclone-frontend-production.up.railway.app
```

---

## 🔍 Why This Matters

Even though our code has safety checks, Next.js pre-renders some pages during build time, and if those pages try to access undefined environment variables, the build artifacts can be corrupted.

---

## 🚀 Steps to Fix

### 1. Set Environment Variables in Railway

Go to Railway dashboard → `aiclone-frontend` → **Variables** → Add each variable above

### 2. Trigger Redeploy

After setting the variables, Railway will automatically redeploy. Wait for it to complete.

### 3. Test

Visit: `https://aiclone-frontend-production.up.railway.app/test-simple`

Should see: "✅ Success!"

---

## 📋 Quick Checklist

- [ ] Set `NEXT_PUBLIC_API_URL` in Railway frontend variables
- [ ] Set `FIREBASE_SERVICE_ACCOUNT` (optional but recommended)
- [ ] Set `DEFAULT_USER_ID` (optional)
- [ ] Set `NEXT_PUBLIC_SITE_URL` (optional)
- [ ] Wait for Railway to redeploy automatically
- [ ] Test `/test-simple` - should work
- [ ] Test `/kb` - should work
- [ ] Test `/kb/health` - should show env var status

---

**After you set these variables, Railway will redeploy and the 500 errors should be gone!**
