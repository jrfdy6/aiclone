# Railway Production - Manual Test Commands

Run these commands in your terminal to test the Railway deployment.

## Base URL
```bash
RAILWAY_URL="https://aiclone-production-32dc.up.railway.app"
```

## Test 1: Health Check (Quick - Should be instant)
```bash
curl https://aiclone-production-32dc.up.railway.app/health
```
**Expected**: `{"status":"healthy","service":"aiclone-backend","firestore":"available"}`

## Test 2: Research Trigger (Tests Perplexity API - Takes 10-30 seconds)
```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "topic": "SaaS companies",
    "industry": "SaaS"
  }'
```
**Expected**: JSON with `"success": true` and a `research_id`

## Test 3: Prospect Discovery (Tests Google Search + Firecrawl - Takes 15-30 seconds)
```bash
curl -X POST https://aiclone-production-32dc.up.railway.app/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "industry": "SaaS",
    "location": "San Francisco",
    "max_results": 3
  }'
```
**Expected**: JSON with `"discovered_count"` > 0 and prospect data

## Test 4: Metrics (Quick - Should be instant)
```bash
curl "https://aiclone-production-32dc.up.railway.app/api/metrics/current?user_id=test-user-123&period=weekly"
```
**Expected**: JSON with metrics data

## What Each Test Verifies

✅ **Health Check**: Server is running, Firestore connected
✅ **Research Trigger**: Perplexity API key works, can fetch research
✅ **Prospect Discovery**: Google Custom Search API works, Firecrawl API works
✅ **Metrics**: Firestore read/write works

## If Tests Fail

- **401/403 errors**: API key issue - check Railway variables
- **500 errors**: Check Railway logs for detailed error
- **Timeout**: API might be slow (normal for Perplexity/Firecrawl)
- **Connection refused**: Railway deployment might not be live yet

## Quick Status Check

All your Railway logs show:
- ✅ PERPLEXITY_API_KEY set
- ✅ FIRECRAWL_API_KEY set  
- ✅ GOOGLE_CUSTOM_SEARCH_API_KEY set
- ✅ GOOGLE_CUSTOM_SEARCH_ENGINE_ID set
- ✅ Firebase initialized
- ✅ Server running on port 8080

So the infrastructure is ready - these tests just confirm the APIs actually work!

