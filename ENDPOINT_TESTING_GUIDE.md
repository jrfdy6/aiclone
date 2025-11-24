# Endpoint Testing Guide

## Prerequisites

Before testing, make sure your backend is running:

```bash
cd backend
source .env  # or export $(cat .env | xargs)
uvicorn app.main:app --reload
```

## Test Script

I've created a test script: `test_all_endpoints.sh`

**To run it:**
```bash
./test_all_endpoints.sh
```

## Manual Testing

### 1. Health Check
```bash
curl http://localhost:8080/health
```

### 2. Research Trigger
```bash
curl -X POST http://localhost:8080/api/research/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "topic": "SaaS companies serving SMBs",
    "industry": "SaaS"
  }'
```

### 3. Prospect Discovery
```bash
curl -X POST http://localhost:8080/api/prospects/discover \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "industry": "SaaS",
    "location": "San Francisco",
    "max_results": 5
  }'
```

### 4. Prospect Approval
```bash
# Replace PROSPECT_ID with actual ID from discovery
curl -X POST http://localhost:8080/api/prospects/approve \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "prospect_ids": ["PROSPECT_ID"],
    "approval_status": "approved"
  }'
```

### 5. Prospect Scoring
```bash
curl -X POST http://localhost:8080/api/prospects/score \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "prospect_ids": ["PROSPECT_ID"]
  }'
```

### 6. Outreach Generation
```bash
curl -X POST http://localhost:8080/api/outreach/manual/prompts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prospect_id": "PROSPECT_ID",
    "user_id": "test-user",
    "include_social": true
  }'
```

### 7. Metrics - Get Current
```bash
curl "http://localhost:8080/api/metrics/current?user_id=test-user&period=weekly"
```

### 8. Metrics - Update
```bash
curl -X POST http://localhost:8080/api/metrics/update \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "prospect_id": "PROSPECT_ID",
    "action": "prospects_analyzed"
  }'
```

### 9. Learning Patterns - Update
```bash
curl -X POST http://localhost:8080/api/learning/update-patterns \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "prospect_id": "PROSPECT_ID",
    "engagement_data": {
      "email_sent": true,
      "email_opened": true,
      "email_responded": false,
      "meeting_booked": false
    }
  }'
```

### 10. Learning Patterns - Get
```bash
curl "http://localhost:8080/api/learning/patterns?user_id=test-user&limit=10"
```

## Expected Results

✅ **200 OK**: Endpoint working correctly
❌ **400/422**: Validation error (check request format)
❌ **404**: Resource not found
❌ **500**: Server error (check logs)

## Troubleshooting

### Backend Not Starting
- Check Python environment: `python3 --version`
- Install dependencies: `pip install -r requirements.txt`
- Check environment variables: `cat .env`

### API Key Errors
- Verify keys in `.env` file
- Check keys are exported: `echo $PERPLEXITY_API_KEY`

### Connection Refused
- Backend not running: Start with `uvicorn app.main:app --reload`
- Wrong port: Check if using port 8080 or 3001

---

**Ready to test!** Start your backend and run the test script or test manually.



