# Microsoft Copilot Knowledge Base - Deployment Guide

## 🎉 What's Been Built

A complete, production-ready knowledge base optimized for Microsoft Copilot crawling:

### ✅ Files Created

**Persona (Optimized):**
- `JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md` - Enhanced with semantic anchors, contextual voice patterns, anti-patterns, and FAQ

**Frontend Routes:**
- `frontend/app/kb/page.tsx` - Landing page with example queries
- `frontend/app/kb/[query]/page.tsx` - Dynamic search over memory_chunks
- `frontend/app/kb/research/page.tsx` - Research library index
- `frontend/app/kb/research/[slug]/page.tsx` - Individual research artifacts (PII-filtered)

**Infrastructure:**
- `frontend/lib/firestore-server.ts` - Server-side Firestore client
- `frontend/app/sitemap.ts` - Dynamic sitemap with all KB URLs
- `frontend/public/robots.txt` - Crawler permissions

**Features:**
- ✅ Server-Side Rendering (SSR) - all content in raw HTML
- ✅ Schema.org markup - Person, ProfilePage, CollectionPage, ResearchProject
- ✅ Semantic HTML - H1, H2, Article, Section tags
- ✅ PII filtering - no emails, phones, or contact info in research
- ✅ Clean URLs - max 2 levels deep, no query params
- ✅ Dynamic sitemap - includes all research slugs
- ✅ Optimized chunking - 100-200 tokens per chunk with query keywords

---

## 🚀 Deployment Steps

### Step 1: Install Dependencies

```bash
cd frontend
npm install firebase-admin
```

### Step 2: Set Environment Variables

Add these to your Railway frontend service:

```bash
# Required
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
FIREBASE_SERVICE_ACCOUNT={"type":"service_account",...}  # Same as backend
DEFAULT_USER_ID=default-user  # Or your actual user ID

# Optional (for sitemap/metadata)
NEXT_PUBLIC_SITE_URL=https://your-frontend.up.railway.app
```

### Step 3: Ingest Optimized Persona

Upload the optimized persona document to your backend:

```bash
curl -X POST https://your-backend.up.railway.app/api/ingest/upload \
  -F "file=@JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md" \
  -F "user_id=default-user"
```

**Expected response:**
```json
{
  "success": true,
  "job_id": "ingest_...",
  "chunks_created": 85,
  "message": "File uploaded and chunked successfully"
}
```

### Step 4: Update robots.txt

Edit `frontend/public/robots.txt` and replace the placeholder URL:

```txt
Sitemap: https://your-actual-frontend-url.up.railway.app/sitemap.xml
```

### Step 5: Deploy to Railway

```bash
cd frontend
git add .
git commit -m "Add Copilot-optimized knowledge base"
git push origin main
```

Railway will automatically deploy. Wait 2-3 minutes for build to complete.

---

## 🧪 Testing (Before Adding to Copilot)

### Test 1: SSR Verification

**Goal:** Ensure all content renders without JavaScript

1. Open Chrome DevTools → Settings → Debugger → Disable JavaScript
2. Visit: `https://your-frontend.up.railway.app/kb`
3. **Expected:** Full page content visible (no "Loading..." or blank page)
4. Visit: `https://your-frontend.up.railway.app/kb/voice-patterns-linkedin`
5. **Expected:** Search results visible with Johnnie's voice patterns

**If content is blank:** SSR is broken. Check Railway logs for errors.

### Test 2: Knowledge Retrieval

**Goal:** Verify backend connection and semantic search

```bash
# Test voice patterns
curl https://your-frontend.up.railway.app/kb/voice-patterns-linkedin

# Test audience-specific voice
curl https://your-frontend.up.railway.app/kb/how-johnnie-talks-to-parents

# Test anti-patterns
curl https://your-frontend.up.railway.app/kb/what-johnnie-does-not-sound-like
```

**Expected:** HTML with relevant chunks (not JSON, not error messages)

### Test 3: Research Index

**Goal:** Verify Firestore connection and research fetching

```bash
curl https://your-frontend.up.railway.app/kb/research
```

**Expected:** HTML with list of recent research (or "No research available" if none exists)

### Test 4: PII Filtering

**Goal:** Ensure no contact info is exposed

1. Visit any research page: `https://your-frontend.up.railway.app/kb/research/[any-slug]`
2. Search page for: `@`, `phone`, `email`, `.com`
3. **Expected:** No email addresses, phone numbers, or websites visible
4. **Should see:** Names, titles, specialties only

### Test 5: Sitemap Generation

**Goal:** Verify dynamic sitemap includes all URLs

```bash
curl https://your-frontend.up.railway.app/sitemap.xml
```

**Expected:** XML with:
- `/kb` (priority 1.0)
- `/kb/research` (priority 0.9)
- `/kb/voice-patterns-linkedin` (priority 0.8)
- `/kb/research/[dynamic-slugs]` (priority 0.7)

### Test 6: Schema.org Validation

**Goal:** Verify structured data is present

1. Visit: `https://your-frontend.up.railway.app/kb`
2. View page source (Ctrl+U / Cmd+Option+U)
3. Search for: `application/ld+json`
4. **Expected:** JSON-LD with `@type: Person` and `knowsAbout` fields

---

## 📋 Adding to Microsoft Copilot

### Option 1: Copilot Web Grounding (Free)

1. Open Microsoft Copilot (copilot.microsoft.com)
2. In chat, type: "Use this website as a knowledge source: https://your-frontend.up.railway.app/kb"
3. Copilot will crawl the URL and index it
4. Wait 24-48 hours for full indexing

**Test query:**
> "Based on the knowledge base, how does Johnnie write LinkedIn posts?"

**Expected answer:**
> "Johnnie uses a casual, authentic voice with signature phrases like 'Y'all', 'Tell you what tho', and 'Makes no sense. Period.' He uses short punchy sentences..."

### Option 2: Copilot Studio (Paid)

1. Go to Copilot Studio (copilotstudio.microsoft.com)
2. Create new agent or edit existing
3. Go to Knowledge → Add knowledge source
4. Select "Public website"
5. Enter URL: `https://your-frontend.up.railway.app/kb`
6. Save and publish

**Indexing time:** 1-4 hours

---

## 🎯 Expected Copilot Behavior

### Query: "How does Johnnie write LinkedIn posts?"

**Copilot retrieves:**
- `/kb/voice-patterns-linkedin`

**Answer:**
> "Johnnie uses a conversational, authentic voice on LinkedIn with signature phrases like 'Y'all', 'Say it with me: 🗣️', and 'Tell you what tho'. His tone is Expert + Direct + Inspiring. He uses short punchy sentences and ends posts with 'Makes no sense. Period.' or 'Stay tuned!'. He groups 5-7 hashtags at the end."

**Source cited:** `https://your-frontend.up.railway.app/kb/voice-patterns-linkedin`

---

### Query: "What's Johnnie's background?"

**Copilot retrieves:**
- `/kb/career-background-education`

**Answer:**
> "Johnnie Fields has 10+ years in education admissions and enrollment management - NOT teaching. He worked at 2U from 2014-2023, rising from Admissions Counselor to Portfolio Manager overseeing $34M revenue. He's currently Director of Admissions at Fusion Academy, a 1:1 school serving neurodivergent students. He has a Georgetown Data Science certificate and USC Master's in Tech/Business/Design."

**Source cited:** `https://your-frontend.up.railway.app/kb/career-background-education`

---

### Query: "Write a LinkedIn post in Johnnie's voice about enrollment"

**Copilot retrieves:**
- `/kb/voice-patterns-linkedin`
- `/kb/fusion-academy-director`

**Answer:**
> "Here's a LinkedIn post in Johnnie's voice:
> 
> Y'all, let's talk about enrollment strategy. 🗣️
> 
> After 10+ years in admissions, I've learned this: enrollment isn't about filling seats. It's about finding the RIGHT fit for families.
> 
> At Fusion Academy, we serve neurodivergent students who need 1:1 learning. That means our outreach has to be authentic, data-driven, and relationship-first.
> 
> Tell you what tho — the best enrollment strategy is the one that puts students first.
> 
> Makes no sense to optimize for volume when you should be optimizing for impact. Period.
> 
> #enrollment #education #neurodivergent #admissions"

**Sources cited:**
- `https://your-frontend.up.railway.app/kb/voice-patterns-linkedin`
- `https://your-frontend.up.railway.app/kb/fusion-academy-director`

---

## 🔧 Troubleshooting

### Issue: "No content visible on /kb pages"

**Cause:** SSR not working or backend connection failed

**Fix:**
1. Check Railway logs: `railway logs --service frontend`
2. Verify `NEXT_PUBLIC_API_URL` is set correctly
3. Test backend directly: `curl https://your-backend.up.railway.app/health`

---

### Issue: "Sitemap is empty"

**Cause:** Firestore connection failed or no research data exists

**Fix:**
1. Check `FIREBASE_SERVICE_ACCOUNT` env var is set on frontend
2. Verify `DEFAULT_USER_ID` matches your actual user ID
3. Check if research exists: `curl https://your-backend.up.railway.app/api/topic-intelligence/user/default-user`

---

### Issue: "Copilot says 'I don't have access to that information'"

**Cause:** Copilot hasn't crawled the site yet, or URL is incorrect

**Fix:**
1. Wait 24-48 hours after adding URL
2. Verify URL is publicly accessible (not behind auth)
3. Check robots.txt allows crawling
4. Submit sitemap to Bing Webmaster Tools manually

---

### Issue: "Research pages show PII (emails/phones)"

**Cause:** PII filtering logic is broken

**Fix:**
1. Check `/kb/research/[slug]/page.tsx` line 63-67
2. Ensure prospects are mapped with only `name`, `title`, `specialty`
3. Redeploy frontend

---

## 📊 Success Metrics

After 48 hours of Copilot indexing, test these queries:

| Query | Expected Source | Pass/Fail |
|-------|----------------|-----------|
| "How does Johnnie write?" | `/kb/voice-patterns-linkedin` | ⬜ |
| "What's Johnnie's background?" | `/kb/career-background-education` | ⬜ |
| "How does Johnnie talk to parents?" | `/kb/how-johnnie-talks-to-parents` | ⬜ |
| "What research has Johnnie done?" | `/kb/research` | ⬜ |
| "What doesn't Johnnie sound like?" | `/kb/what-johnnie-does-not-sound-like` | ⬜ |

**Target:** 5/5 queries return accurate answers with correct sources

---

## 🎓 Next Steps (Optional Enhancements)

### 1. Add More Common Queries to Sitemap

Edit `frontend/app/sitemap.ts` and add more query slugs to `commonQueries` array:

```typescript
const commonQueries = [
  // ... existing queries
  "coffee-convo-event-series",
  "acorn-global-collective",
  "salesforce-migration-story",
  "struggling-ac-mentoring",
  // ... add more based on what you want Copilot to find easily
];
```

### 2. Submit Sitemap to Bing Webmaster Tools

1. Go to: https://www.bing.com/webmasters
2. Add your site: `https://your-frontend.up.railway.app`
3. Verify ownership (DNS or HTML file)
4. Submit sitemap: `https://your-frontend.up.railway.app/sitemap.xml`

**Benefit:** Faster indexing by Bing (which powers Copilot's web grounding)

### 3. Add FAQ Schema to Landing Page

Edit `frontend/app/kb/page.tsx` and add FAQPage schema:

```typescript
const faqSchema = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "How does Johnnie write LinkedIn posts?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Johnnie uses a casual, authentic voice..."
      }
    },
    // ... more FAQs
  ]
};
```

**Benefit:** Copilot can extract Q&A pairs directly

### 4. Monitor Copilot Usage

Track which queries Copilot is using by checking Railway logs:

```bash
railway logs --service frontend | grep "/kb/"
```

Look for patterns in what URLs are being hit most often.

---

## ✅ Deployment Checklist

Before adding to Copilot, verify:

- [ ] `JOHNNIE_FIELDS_PERSONA_OPTIMIZED.md` ingested successfully
- [ ] All environment variables set on Railway frontend
- [ ] `/kb` page loads with example queries
- [ ] `/kb/voice-patterns-linkedin` returns search results
- [ ] `/kb/research` shows research index (or "No research" if empty)
- [ ] Sitemap accessible at `/sitemap.xml`
- [ ] robots.txt has correct sitemap URL
- [ ] SSR test passes (content visible with JS disabled)
- [ ] PII filtering test passes (no emails/phones in research)
- [ ] Schema.org markup present in page source

**All checked?** → Add `https://your-frontend.up.railway.app/kb` to Copilot!

---

## 🎉 You're Done!

Your knowledge base is now:
- ✅ Fully crawlable by Microsoft Copilot
- ✅ Optimized for voice fidelity (sounds like you)
- ✅ PII-filtered (safe for public access)
- ✅ Schema.org enhanced (better entity recognition)
- ✅ Production-ready

**URL to give Copilot:**
```
https://your-frontend.up.railway.app/kb
```

Wait 24-48 hours for indexing, then test with:
> "Based on the knowledge base, how does Johnnie Fields write LinkedIn posts?"

Copilot should return an accurate answer citing your KB as the source. 🚀
