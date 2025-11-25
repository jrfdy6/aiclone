# Production Testing Guide

## 🚀 Test Your Production Frontend

Your production frontend is deployed at:
**https://aiclone-frontend-production.up.railway.app**

## Quick Test Steps

### 1. Test the API Test Page

Navigate directly to the test page:
```
https://aiclone-frontend-production.up.railway.app/api-test
```

**What to do:**
1. The page will automatically detect the production API URL
2. Click **"Run All Tests"** to test all 11 endpoints
3. Watch for:
   - ✅ Green = Passed (no timeout, structured JSON)
   - ❌ Red = Failed (check error message)
   - Response times for each endpoint

### 2. Test the Home Page Chat

Navigate to:
```
https://aiclone-frontend-production.up.railway.app/
```

**What to do:**
1. Scroll to "Chat with Your Knowledge Base"
2. Click the "+" to expand
3. Type a query (e.g., "What is AI?")
4. Click "Send" to test `/api/chat/` endpoint

### 3. Test Other Pages

Test various features:
- **Prospects:** `https://aiclone-frontend-production.up.railway.app/prospects`
- **Knowledge:** `https://aiclone-frontend-production.up.railway.app/knowledge`
- **Dashboard:** `https://aiclone-frontend-production.up.railway.app/dashboard`
- **Research Tasks:** `https://aiclone-frontend-production.up.railway.app/research-tasks`

## What Gets Tested

The `/api-test` page tests all 11 endpoints we verified:

1. ✅ `/health` - Health check
2. ✅ `/` - Root endpoint
3. ✅ `/test` - Test endpoint
4. ✅ `/api/chat/` - Query retrieval
5. ✅ `/api/knowledge/` - Knowledge search
6. ✅ `/api/prospects/` - Prospect listing
7. ✅ `/api/content/generate/blog` - Blog generation
8. ✅ `/api/content/generate/email` - Email generation
9. ✅ `/api/research-tasks` - Research tasks
10. ✅ `/api/analytics/summary` - Analytics
11. ✅ `/api/templates` - Templates

## Browser DevTools Testing

### Check Network Requests

1. Open browser DevTools (F12)
2. Go to **Network** tab
3. Navigate to `/api-test` page
4. Click "Run All Tests"
5. Watch for:
   - Request status codes (200 = success)
   - Response times (<1s is good)
   - Response sizes
   - Any failed requests (red)

### Check Console Logs

1. Open browser DevTools (F12)
2. Go to **Console** tab
3. Look for:
   - API errors
   - CORS errors
   - Timeout errors
   - Any JavaScript errors

### Check Response Structure

1. In Network tab, click on any request
2. Go to **Response** tab
3. Verify:
   - Response is valid JSON
   - Response is structured (not verbose/chatty)
   - Error responses also return structured JSON

## Expected Results

### ✅ All Tests Pass
- All 11 endpoints return 200 status
- Response times <1s each
- All responses are structured JSON
- No timeout errors
- No CORS errors

### ❌ If Tests Fail

**Check:**
1. **Backend Status:**
   ```bash
   curl https://aiclone-production-32dc.up.railway.app/health
   ```
   Should return: `{"status":"healthy",...}`

2. **CORS Issues:**
   - Check browser console for CORS errors
   - Verify backend has frontend URL in CORS origins
   - Backend should allow: `https://aiclone-frontend-production.up.railway.app`

3. **Environment Variables:**
   - Frontend should have `NEXT_PUBLIC_API_URL` set to backend URL
   - Check Railway frontend service → Variables

4. **Railway Logs:**
   - Check Railway frontend service → Deployments → Latest → Logs
   - Check Railway backend service → Deployments → Latest → Logs

## Production URLs

### Frontend
- **URL:** https://aiclone-frontend-production.up.railway.app
- **Test Page:** https://aiclone-frontend-production.up.railway.app/api-test
- **Home:** https://aiclone-frontend-production.up.railway.app/

### Backend
- **URL:** https://aiclone-production-32dc.up.railway.app
- **Health:** https://aiclone-production-32dc.up.railway.app/health
- **API Docs:** https://aiclone-production-32dc.up.railway.app/api/docs

## Quick Verification Commands

### Test Backend Health
```bash
curl https://aiclone-production-32dc.up.railway.app/health
```

### Test Frontend is Live
```bash
curl -I https://aiclone-frontend-production.up.railway.app/
```

### Test API from Frontend
```bash
curl -H "Origin: https://aiclone-frontend-production.up.railway.app" \
  https://aiclone-production-32dc.up.railway.app/health
```

## Troubleshooting

### Frontend Returns 404
- Check Railway frontend service is deployed
- Check Railway logs for build errors
- Verify the service is running (not sleeping)

### API Calls Fail
- Check `NEXT_PUBLIC_API_URL` is set in Railway frontend variables
- Verify backend is running: `curl https://aiclone-production-32dc.up.railway.app/health`
- Check CORS configuration in backend

### Timeout Errors
- Check Railway backend logs for slow queries
- Verify backend is not sleeping (Railway free tier sleeps after inactivity)
- Check network connectivity

### CORS Errors
- Add frontend URL to backend CORS:
  - Railway backend service → Variables
  - Add/Update `CORS_ADDITIONAL_ORIGINS`
  - Value: `https://aiclone-frontend-production.up.railway.app`

## Monitoring

### Railway Dashboard
1. Go to Railway Dashboard
2. Check both services:
   - Frontend service → Deployments → Latest
   - Backend service → Deployments → Latest
3. Review logs for errors

### Browser Console
- Open DevTools → Console
- Look for errors or warnings
- Check Network tab for failed requests

## Success Criteria

✅ **Production is healthy when:**
- All 11 tests pass on `/api-test` page
- Response times <1s for all endpoints
- No CORS errors in browser console
- No timeout errors
- All responses are structured JSON
- Frontend pages load correctly
- API calls succeed from all pages

## Next Steps

After successful testing:
1. ✅ Document any issues found
2. ✅ Monitor Railway logs for errors
3. ✅ Test user workflows on production
4. ✅ Set up monitoring/alerts if needed

