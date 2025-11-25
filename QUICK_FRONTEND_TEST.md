# Quick Frontend Test Guide

## ✅ Your Frontend is Ready to Test!

Your `.env.local` is already configured with:
```
NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app
```

## 🚀 How to Test (3 Options)

### Option 1: Test Page (Easiest - Visual Interface)

1. **Start the frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Open in browser:**
   ```
   http://localhost:3002/api-test
   ```

3. **Click "Run All Tests"** - Tests all 11 endpoints we verified

4. **What you'll see:**
   - ✅ Green = Passed (no timeout, structured JSON)
   - ❌ Red = Failed (check error message)
   - Response times for each endpoint
   - Full JSON responses (click "View Response")

### Option 2: Home Page Chat Interface

1. **Start the frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Open in browser:**
   ```
   http://localhost:3002
   ```

3. **Test the chat:**
   - Scroll to "Chat with Your Knowledge Base"
   - Click the "+" to expand
   - Type a query (e.g., "What is AI?")
   - Click "Send"
   - This tests `/api/chat/` endpoint

### Option 3: Command Line Test

1. **Run the test script:**
   ```bash
   cd frontend
   npm run test:phase6
   ```

   Or:
   ```bash
   cd frontend
   ./test-phase6-simple.sh
   ```

## 📊 What Gets Tested

The test page tests all the endpoints we verified:

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

## ✅ What to Verify

### No Timeout Issues
- All endpoints respond in <1 second
- No "Connection timed out" errors
- All requests complete successfully

### Structured JSON Responses
- All responses are valid JSON
- Responses are concise (not verbose/chatty)
- Error responses also return structured JSON

### Proper Logging
- Open browser DevTools → Console
- You should see fetch requests
- Check Railway logs for backend logging:
  - `🌐 GET /health - Request received`
  - `✅ GET /health - 200 - 0.05s`

## 🐛 Troubleshooting

### Frontend won't start
```bash
cd frontend
npm install  # If needed
npm run dev
```

### "NEXT_PUBLIC_API_URL is not configured"
- Check `.env.local` exists in `frontend/` directory
- Restart dev server after changes
- Variable name must be exactly `NEXT_PUBLIC_API_URL`

### CORS errors
- Backend already allows `localhost:3002`
- If using different port, update backend CORS config

### All tests fail
- Verify backend is running:
  ```bash
  curl https://aiclone-production-32dc.up.railway.app/health
  ```
- Check Railway dashboard for deployment status
- Verify API URL in `.env.local`

## 📝 Expected Results

When everything works:
- ✅ All 11 tests pass
- ✅ Response times <1s each
- ✅ All responses are structured JSON
- ✅ No timeout errors
- ✅ No CORS errors

## 🎯 Next Steps

After testing:
1. If all tests pass → Backend is healthy! ✅
2. If some fail → Check error messages and Railway logs
3. Test specific features in their pages:
   - `/prospects` - Prospect management
   - `/knowledge` - Knowledge search  
   - `/content-marketing` - Content tools
   - `/dashboard` - Dashboard

