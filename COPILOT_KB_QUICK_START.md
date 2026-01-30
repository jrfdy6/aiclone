# Copilot KB - Quick Start

## 🚀 Deploy in 5 Minutes

### 1. Install Dependencies
```bash
cd frontend
npm install firebase-admin
```

### 2. Set Railway Env Vars
```bash
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
FIREBASE_SERVICE_ACCOUNT={"type":"service_account",...}
DEFAULT_USER_ID=default-user
NEXT_PUBLIC_SITE_URL=https://your-frontend.up.railway.app
```

### 3. Ingest Optimized Persona
```bash
curl -X POST https://your-backend.up.railway.app/api/ingest/upload \
  -F "file=@JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md" \
  -F "user_id=default-user"
```

### 4. Update robots.txt
Edit `frontend/public/robots.txt`:
```txt
Sitemap: https://your-actual-url.up.railway.app/sitemap.xml
```

### 5. Deploy
```bash
git add .
git commit -m "Add Copilot KB"
git push origin main
```

---

## ✅ Test Before Adding to Copilot

```bash
# Test SSR (disable JS in browser)
open https://your-frontend.up.railway.app/kb

# Test knowledge retrieval
curl https://your-frontend.up.railway.app/kb/voice-patterns-linkedin

# Test sitemap
curl https://your-frontend.up.railway.app/sitemap.xml

# Test PII filtering
curl https://your-frontend.up.railway.app/kb/research
```

**All working?** → Give Copilot this URL:
```
https://your-frontend.up.railway.app/kb
```

---

## 🎯 What Copilot Can Do

**Query:** "How does Johnnie write LinkedIn posts?"

**Answer:** "Johnnie uses signature phrases like 'Y'all', 'Tell you what tho', 'Makes no sense. Period.' with short punchy sentences..."

**Source:** `https://your-frontend.up.railway.app/kb/voice-patterns-linkedin`

---

## 📁 Files Created

- ✅ `JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md` - Enhanced persona
- ✅ `frontend/app/kb/page.tsx` - Landing page
- ✅ `frontend/app/kb/[query]/page.tsx` - Search page
- ✅ `frontend/app/kb/research/page.tsx` - Research index
- ✅ `frontend/app/kb/research/[slug]/page.tsx` - Research detail
- ✅ `frontend/lib/firestore-server.ts` - Server Firestore client
- ✅ `frontend/app/sitemap.ts` - Dynamic sitemap
- ✅ `frontend/public/robots.txt` - Crawler config
- ✅ `COPILOT_KB_DEPLOYMENT_GUIDE.md` - Full guide

---

## 🆘 Quick Fixes

**No content on /kb pages?**
→ Check `NEXT_PUBLIC_API_URL` env var

**Empty sitemap?**
→ Check `FIREBASE_SERVICE_ACCOUNT` and `DEFAULT_USER_ID`

**Copilot can't access?**
→ Wait 24-48 hours after adding URL

---

**Full guide:** See `COPILOT_KB_DEPLOYMENT_GUIDE.md`
