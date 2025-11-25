# Frontend Testing Guide

## Quick Start: Test Backend from Frontend

### Option 1: Use the Test Page (Recommended)

1. **Set up environment variable:**
   ```bash
   cd frontend
   echo "NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app" > .env.local
   ```

2. **Start the frontend:**
   ```bash
   npm run dev
   ```

3. **Open the test page:**
   Navigate to: `http://localhost:3002/api-test`

4. **Run tests:**
   - Click "Run All Tests" to test all endpoints
   - Or click individual "Run" buttons to test specific endpoints
   - View response times, status codes, and JSON responses

### Option 2: Test from Home Page

1. **Start the frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Open the home page:**
   Navigate to: `http://localhost:3002`

3. **Test the chat interface:**
   - Expand the "Chat with Your Knowledge Base" section
   - Enter a query (e.g., "What is AI?")
   - Click "Send" to test the `/api/chat/` endpoint

### Option 3: Use Existing Test Scripts

1. **Run the Phase 6 API test suite:**
   ```bash
   cd frontend
   npm run test:phase6
   ```

2. **Or use the shell script:**
   ```bash
   cd frontend
   NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app ./test-phase6-simple.sh
   ```

## What Gets Tested

### ✅ Health & Status Endpoints
- `/health` - Health check
- `/` - Root endpoint
- `/test` - Test endpoint

### ✅ Query/Retrieval Endpoints
- `/api/chat/` - Chat-based query retrieval
- `/api/knowledge/` - Knowledge base search

### ✅ Prospect Endpoints
- `/api/prospects/` - List prospects with scoring

### ✅ Content Generation Endpoints
- `/api/content/generate/blog` - Blog post generation
- `/api/content/generate/email` - Email generation

### ✅ Research/Data Endpoints
- `/api/research-tasks` - Research tasks (Firestore access)
- `/api/analytics/summary` - Analytics summary
- `/api/templates` - Templates

## What to Look For

### ✅ No Timeout Issues
- All endpoints should respond in <1 second
- No connection timeouts
- All requests complete successfully

### ✅ Structured JSON Responses
- All endpoints return valid JSON
- Responses are concise and structured (not verbose/chatty)
- Error responses also return structured JSON

### ✅ Proper Logging
- Check browser console for request/response logs
- Check Railway logs for backend logging:
  - `🌐 {method} {path} - Request received`
  - `✅ {method} {path} - {status_code} - {time}s`
  - `❌ {method} {path} - Error after {time}s: {error}`

## Environment Configuration

### Local Development

Create `frontend/.env.local`:
```bash
NEXT_PUBLIC_API_URL=https://aiclone-production-32dc.up.railway.app
```

Or for local backend:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8080
```

### Production

The environment variable should be set in Railway or your deployment platform.

## Troubleshooting

### "NEXT_PUBLIC_API_URL is not configured"
- Make sure `.env.local` exists in the `frontend/` directory
- Restart the dev server after creating/updating `.env.local`
- Check that the variable name is exactly `NEXT_PUBLIC_API_URL`

### CORS Errors
- The backend already includes `localhost:3002` in CORS origins
- If you're using a different port, update the backend CORS configuration

### Timeout Issues
- Check that the Railway backend is running
- Verify the API URL is correct
- Check Railway logs for backend errors

### Connection Refused
- Verify the backend URL is correct
- Check that Railway deployment is active
- Test the backend directly with curl:
  ```bash
  curl https://aiclone-production-32dc.up.railway.app/health
  ```

## Test Results Interpretation

### ✅ Pass (Green)
- Endpoint responded successfully
- Status code 200-299
- Valid JSON response
- Response time <1s

### ❌ Fail (Red)
- Endpoint returned error
- Status code 400+
- Or connection/timeout error

### ⏳ Running (Blue)
- Test is currently executing
- Wait for completion

## Next Steps

After testing:
1. Review any failed tests
2. Check Railway logs for backend errors
3. Verify environment variables are set correctly
4. Test specific features in their respective pages:
   - `/prospects` - Prospect management
   - `/knowledge` - Knowledge search
   - `/content-marketing` - Content tools
   - `/dashboard` - Dashboard features

