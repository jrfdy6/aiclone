# Railway Deployment Checklist for LinkedIn Integration

## Current Status

✅ **Local Backend:** All new endpoints working correctly  
⚠️ **Railway:** New endpoints return 404 (need deployment)

## What Needs to Be Deployed

All new files and changes:

### New Files Created:
1. `backend/app/models/linkedin_content.py` - LinkedIn content models
2. `backend/app/routes/linkedin_content.py` - LinkedIn content routes

### Modified Files:
1. `backend/app/main.py` - Added linkedin_content router import and registration
2. `backend/app/routes/prospects.py` - Added outreach endpoint
3. `backend/app/routes/linkedin.py` - Fixed Optional import

### No Dependency Changes:
- All dependencies already in `requirements.txt`
- No new environment variables needed

## Pre-Deployment Verification

Run these checks locally first:

```bash
# 1. Check syntax
python3 -m py_compile backend/app/routes/linkedin_content.py
python3 -m py_compile backend/app/models/linkedin_content.py

# 2. Test imports (with venv activated)
cd backend
source .venv/bin/activate  # or your venv path
python3 -c "from app.routes import linkedin_content; print('✅ Import OK')"

# 3. Test endpoints locally
curl http://localhost:3001/api/linkedin/content/drafts?user_id=test
# Should return: {"success":true,"drafts":[],"total":0}
```

## Deployment Steps

### Option 1: Git Push (Auto-Deploy)

If Railway is connected to GitHub:

```bash
# 1. Stage changes
git add backend/app/models/linkedin_content.py
git add backend/app/routes/linkedin_content.py
git add backend/app/main.py
git add backend/app/routes/prospects.py
git add backend/app/routes/linkedin.py

# 2. Commit
git commit -m "Add LinkedIn PACER content integration endpoints

- Add LinkedIn content drafting, calendar, and metrics endpoints
- Add outreach generation to prospects router
- Support PACER strategy pillars (referral, thought_leadership, stealth_founder)
- Integrate with learning patterns for content performance tracking"

# 3. Push to trigger deployment
git push origin main
```

### Option 2: Railway CLI

```bash
# 1. Install Railway CLI (if not installed)
npm i -g @railway/cli

# 2. Login
railway login

# 3. Link to project
railway link

# 4. Deploy
railway up
```

## Post-Deployment Verification

After deployment, run these tests:

```bash
RAILWAY_URL="https://aiclone-production-32dc.up.railway.app"

# 1. Health check
curl "$RAILWAY_URL/health"
# Expected: {"status":"healthy",...}

# 2. Test new endpoint (should NOT be 404)
curl "$RAILWAY_URL/api/linkedin/content/drafts?user_id=test&limit=1"
# Expected: {"success":true,"drafts":[],"total":0}
# NOT: {"detail":"Not Found"}

# 3. Run full test suite
./test_all_linkedin_and_railway.sh
```

## Troubleshooting Railway Deployment

### Issue: 404 on New Endpoints

**Possible Causes:**
1. Code not deployed yet → Deploy via git push or Railway CLI
2. Import error preventing router registration → Check Railway logs
3. Route prefix conflict → Verify no duplicate routes

**Check Railway Logs:**
```bash
railway logs
# Look for:
# - Import errors
# - Route registration messages
# - Startup errors
```

### Issue: Import Errors in Logs

**Check:**
1. All files committed and pushed
2. `linkedin_content.py` exists in `backend/app/routes/`
3. `linkedin_content` models file exists
4. No syntax errors (tested locally)

### Issue: Route Not Found After Deployment

**Verify:**
1. `app.include_router(linkedin_content.router, prefix="/api/linkedin/content")` in main.py
2. Router imported correctly: `from app.routes import linkedin_content`
3. Router object created: `router = APIRouter()` in linkedin_content.py

## Quick Test Commands

### Test All New Endpoints

```bash
RAILWAY_URL="https://aiclone-production-32dc.up.railway.app"
USER_ID="test-$(date +%s)"

# Content Drafts
curl "$RAILWAY_URL/api/linkedin/content/drafts?user_id=$USER_ID&limit=5"

# Calendar
curl "$RAILWAY_URL/api/linkedin/content/calendar?user_id=$USER_ID"

# Outreach (requires prospect_id)
curl -X POST "$RAILWAY_URL/api/prospects/outreach" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER_ID\",\"prospect_id\":\"test\",\"outreach_type\":\"dm\"}"
```

## Success Criteria

Deployment is successful when:

- [ ] Railway health check returns 200
- [ ] `/api/linkedin/content/drafts` returns 200 (not 404)
- [ ] `/api/linkedin/content/calendar` returns 200 (not 404)
- [ ] No import errors in Railway logs
- [ ] All existing endpoints still work

## Rollback Plan

If deployment causes issues:

```bash
# Revert the commit
git revert HEAD
git push origin main

# Or redeploy previous version via Railway dashboard
```

## Monitoring After Deployment

1. Check Railway metrics for error rates
2. Monitor response times for new endpoints
3. Watch Firestore write operations (content drafts)
4. Check API usage for Perplexity/Firecrawl if using research features

## Next Steps After Successful Deployment

1. Update documentation with Railway URLs
2. Test end-to-end workflow:
   - Generate content draft
   - Schedule it
   - Update metrics
   - Verify learning patterns update
3. Monitor performance for first 24 hours


