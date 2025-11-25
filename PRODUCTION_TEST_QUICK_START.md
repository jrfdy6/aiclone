# 🚀 Production Testing Quick Start

## Your Production URLs

**Frontend:** https://aiclone-frontend-production.up.railway.app  
**Backend:** https://aiclone-production-32dc.up.railway.app

## ✅ Test Right Now (No Deployment Needed)

### Option 1: Test Backend Directly

Open these URLs in your browser or use curl:

1. **Health Check:**
   ```
   https://aiclone-production-32dc.up.railway.app/health
   ```
   Should return: `{"status":"healthy","service":"aiclone-backend",...}`

2. **Root Endpoint:**
   ```
   https://aiclone-production-32dc.up.railway.app/
   ```
   Should return: `{"status":"aiclone backend running",...}`

3. **API Documentation:**
   ```
   https://aiclone-production-32dc.up.railway.app/api/docs
   ```
   Interactive API documentation (Swagger UI)

### Option 2: Test from Production Frontend

1. **Home Page:**
   ```
   https://aiclone-frontend-production.up.railway.app/
   ```
   - Scroll to "Chat with Your Knowledge Base"
   - Expand it and test the chat interface
   - This tests `/api/chat/` endpoint

2. **Other Pages:**
   - **Prospects:** https://aiclone-frontend-production.up.railway.app/prospects
   - **Knowledge:** https://aiclone-frontend-production.up.railway.app/knowledge
   - **Dashboard:** https://aiclone-frontend-production.up.railway.app/dashboard

### Option 3: Use Browser DevTools

1. Open production frontend: https://aiclone-frontend-production.up.railway.app/
2. Open DevTools (F12)
3. Go to **Network** tab
4. Navigate to any page that makes API calls
5. Watch for:
   - ✅ Green status codes (200-299)
   - ⚠️ Red status codes (400+)
   - Response times (<1s is good)
   - Any failed requests

## 🧪 Test API Test Page (After Deployment)

The `/api-test` page we created needs to be deployed first. Once deployed:

1. **Navigate to:**
   ```
   https://aiclone-frontend-production.up.railway.app/api-test
   ```

2. **Click "Run All Tests"** to test all 11 endpoints

3. **What you'll see:**
   - ✅ Green = Passed (no timeout, structured JSON)
   - ❌ Red = Failed (check error message)
   - Response times for each endpoint

## 📊 Quick Verification Commands

Run these in your terminal:

```bash
# Test backend health
curl https://aiclone-production-32dc.up.railway.app/health

# Test frontend is live
curl -I https://aiclone-frontend-production.up.railway.app/

# Test API endpoint
curl https://aiclone-production-32dc.up.railway.app/api/prospects/?user_id=test_user&limit=5
```

## 🔍 What to Check

### ✅ Backend Health
- Health endpoint returns `{"status":"healthy"}`
- All endpoints respond in <1s
- No timeout errors
- Structured JSON responses

### ✅ Frontend Connection
- Frontend loads correctly
- No CORS errors in browser console
- API calls succeed (check Network tab)
- Pages render without errors

### ✅ Integration
- Frontend can call backend APIs
- Responses are displayed correctly
- No JavaScript errors in console

## 🐛 Troubleshooting

### Frontend Returns 404 for `/api-test`
- The test page needs to be deployed
- Commit and push the new `frontend/app/api-test/page.tsx` file
- Railway will auto-deploy

### CORS Errors
- Check browser console for CORS errors
- Verify backend has frontend URL in CORS origins
- Backend should allow: `https://aiclone-frontend-production.up.railway.app`

### API Calls Fail
- Check `NEXT_PUBLIC_API_URL` is set in Railway frontend variables
- Verify backend is running: `curl https://aiclone-production-32dc.up.railway.app/health`
- Check browser console for actual error messages

### Timeout Errors
- Check Railway backend logs
- Verify backend is not sleeping (Railway free tier sleeps after inactivity)
- Test backend directly with curl first

## 📝 Next Steps

1. **Deploy the test page:**
   ```bash
   git add frontend/app/api-test/page.tsx
   git commit -m "Add API test page for production testing"
   git push origin main
   ```
   Railway will auto-deploy the frontend.

2. **Wait 2-3 minutes** for Railway to build and deploy

3. **Test the page:**
   ```
   https://aiclone-frontend-production.up.railway.app/api-test
   ```

4. **Run all tests** and verify results

## ✅ Success Criteria

Production is healthy when:
- ✅ Backend health endpoint returns healthy status
- ✅ Frontend loads without errors
- ✅ API calls succeed from frontend
- ✅ No CORS errors in browser console
- ✅ Response times <1s
- ✅ All responses are structured JSON

