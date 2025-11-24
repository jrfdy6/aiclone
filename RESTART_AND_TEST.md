# Restart Backend and Test Endpoints

## The Issue

The backend server is running an older version that doesn't have the new routes. You need to restart it.

## Step 1: Restart Backend

**Option A: Use your start script**
```bash
./start_servers.sh
```

**Option B: Manual restart**
```bash
cd backend
source ../.venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
uvicorn app.main:app --reload --port 3001
```

## Step 2: Wait for Startup

Wait 5-10 seconds for the server to fully start. You should see:
```
✅ FastAPI app is ready to accept requests
📡 Listening on 0.0.0.0:3001
📊 GOOGLE_CUSTOM_SEARCH_API_KEY set: True
📊 PERPLEXITY_API_KEY set: True
📊 FIRECRAWL_API_KEY set: True
```

## Step 3: Test Endpoints

Once restarted, run:
```bash
./test_endpoints_simple.sh
```

Or test manually:

### Quick Test - Research
```bash
curl -X POST http://localhost:3001/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","topic":"SaaS companies","industry":"SaaS"}'
```

### Quick Test - Discovery
```bash
curl -X POST http://localhost:3001/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","industry":"SaaS","max_results":3}'
```

## Expected Results After Restart

✅ All endpoints should return 200 OK (not "Method Not Allowed")
✅ Research endpoint should call Perplexity + Firecrawl
✅ Discovery endpoint should call Google Custom Search + Firecrawl
✅ All other endpoints should work

---

**Restart your backend now, then we can test all endpoints!**



