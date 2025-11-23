#!/bin/bash

# Simple Endpoint Testing Script
# Assumes backend is running on port 3001 (or 8080)

API_URL="${API_URL:-http://localhost:3001}"
USER_ID="test-user-$(date +%s)"

echo "🧪 Testing Prospecting Workflow Endpoints"
echo "=========================================="
echo "API URL: $API_URL"
echo "User ID: $USER_ID"
echo ""

# Test 1: Health Check
echo "1️⃣ Health Check..."
curl -s "$API_URL/health" | jq '.' 2>/dev/null || curl -s "$API_URL/health"
echo -e "\n"

# Test 2: Research Trigger
echo "2️⃣ Research Trigger..."
RESEARCH_RESPONSE=$(curl -s -X POST "$API_URL/api/research/trigger" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\", \"topic\": \"SaaS companies\", \"industry\": \"SaaS\"}")
echo "$RESEARCH_RESPONSE" | jq '.' 2>/dev/null || echo "$RESEARCH_RESPONSE"
RESEARCH_ID=$(echo "$RESEARCH_RESPONSE" | grep -o '"research_id":"[^"]*"' | cut -d'"' -f4)
echo -e "\nResearch ID: $RESEARCH_ID\n"

# Test 3: Prospect Discovery
echo "3️⃣ Prospect Discovery..."
DISCOVERY_RESPONSE=$(curl -s -X POST "$API_URL/api/prospects/discover" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\", \"industry\": \"SaaS\", \"max_results\": 3}")
echo "$DISCOVERY_RESPONSE" | jq '.' 2>/dev/null || echo "$DISCOVERY_RESPONSE"
PROSPECT_ID=$(echo "$DISCOVERY_RESPONSE" | grep -o '"prospect_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo -e "\nFirst Prospect ID: $PROSPECT_ID\n"

# Test 4: Prospect Approval (if we have a prospect)
if [ ! -z "$PROSPECT_ID" ]; then
    echo "4️⃣ Prospect Approval..."
    curl -s -X POST "$API_URL/api/prospects/approve" \
      -H "Content-Type: application/json" \
      -d "{\"user_id\": \"$USER_ID\", \"prospect_ids\": [\"$PROSPECT_ID\"], \"approval_status\": \"approved\"}" | jq '.' 2>/dev/null || echo "Response received"
    echo -e "\n"
fi

# Test 5: Prospect Scoring
if [ ! -z "$PROSPECT_ID" ]; then
    echo "5️⃣ Prospect Scoring..."
    curl -s -X POST "$API_URL/api/prospects/score" \
      -H "Content-Type: application/json" \
      -d "{\"user_id\": \"$USER_ID\", \"prospect_ids\": [\"$PROSPECT_ID\"]}" | jq '.' 2>/dev/null || echo "Response received"
    echo -e "\n"
fi

# Test 6: Outreach Generation
if [ ! -z "$PROSPECT_ID" ]; then
    echo "6️⃣ Outreach Generation..."
    curl -s -X POST "$API_URL/api/outreach/manual/prompts/generate" \
      -H "Content-Type: application/json" \
      -d "{\"prospect_id\": \"$PROSPECT_ID\", \"user_id\": \"$USER_ID\", \"include_social\": true}" | jq '.prompt.full_prompt' 2>/dev/null | head -20 || echo "Response received"
    echo -e "\n"
fi

# Test 7: Metrics - Get Current
echo "7️⃣ Metrics (Get Current)..."
curl -s "$API_URL/api/metrics/current?user_id=$USER_ID&period=weekly" | jq '.' 2>/dev/null || curl -s "$API_URL/api/metrics/current?user_id=$USER_ID&period=weekly"
echo -e "\n"

# Test 8: Learning Patterns - Get
echo "8️⃣ Learning Patterns (Get)..."
curl -s "$API_URL/api/learning/patterns?user_id=$USER_ID&limit=5" | jq '.' 2>/dev/null || curl -s "$API_URL/api/learning/patterns?user_id=$USER_ID&limit=5"
echo -e "\n"

echo "=========================================="
echo "✅ Testing Complete!"
echo ""
echo "Note: Some tests may fail if backend isn't running or API keys aren't set."
echo "Start backend with: cd backend && uvicorn app.main:app --reload --port 3001"

