#!/bin/bash

# Test All Prospecting Workflow Endpoints
# This script tests all endpoints in the workflow

API_URL="http://localhost:8080"
USER_ID="test-user-$(date +%s)"

echo "🧪 Testing All Prospecting Workflow Endpoints"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test 1: Health Check
echo "1️⃣ Testing Health Check..."
response=$(curl -s -w "\n%{http_code}" http://localhost:8080/health)
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -1)

if [ "$http_code" == "200" ]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed (HTTP $http_code)${NC}"
    echo "Response: $body"
    exit 1
fi
echo ""

# Test 2: Research Trigger
echo "2️⃣ Testing Research Trigger..."
response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/research/trigger" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"topic\": \"SaaS companies serving SMBs\",
    \"industry\": \"SaaS\"
  }")
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -1)

if [ "$http_code" == "200" ]; then
    echo -e "${GREEN}✅ Research trigger passed${NC}"
    RESEARCH_ID=$(echo "$body" | grep -o '"research_id":"[^"]*"' | cut -d'"' -f4)
    echo "   Research ID: $RESEARCH_ID"
else
    echo -e "${RED}❌ Research trigger failed (HTTP $http_code)${NC}"
    echo "Response: $body"
fi
echo ""

# Test 3: Prospect Discovery
echo "3️⃣ Testing Prospect Discovery..."
response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/prospects/discover" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"industry\": \"SaaS\",
    \"location\": \"San Francisco\",
    \"max_results\": 5
  }")
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -1)

if [ "$http_code" == "200" ]; then
    echo -e "${GREEN}✅ Prospect discovery passed${NC}"
    PROSPECT_COUNT=$(echo "$body" | grep -o '"discovered_count":[0-9]*' | cut -d':' -f2)
    echo "   Discovered: $PROSPECT_COUNT prospects"
    # Extract first prospect ID
    PROSPECT_ID=$(echo "$body" | grep -o '"prospect_id":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo "   First Prospect ID: $PROSPECT_ID"
else
    echo -e "${RED}❌ Prospect discovery failed (HTTP $http_code)${NC}"
    echo "Response: $body"
    PROSPECT_ID=""
fi
echo ""

# Test 4: Prospect Approval (if we have prospects)
if [ ! -z "$PROSPECT_ID" ]; then
    echo "4️⃣ Testing Prospect Approval..."
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/prospects/approve" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$USER_ID\",
        \"prospect_ids\": [\"$PROSPECT_ID\"],
        \"approval_status\": \"approved\"
      }")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -1)

    if [ "$http_code" == "200" ]; then
        echo -e "${GREEN}✅ Prospect approval passed${NC}"
    else
        echo -e "${RED}❌ Prospect approval failed (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  Skipping approval test (no prospects found)${NC}"
    echo ""
fi

# Test 5: Prospect Scoring (if we have approved prospects)
if [ ! -z "$PROSPECT_ID" ]; then
    echo "5️⃣ Testing Prospect Scoring..."
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/prospects/score" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$USER_ID\",
        \"prospect_ids\": [\"$PROSPECT_ID\"]
      }")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -1)

    if [ "$http_code" == "200" ]; then
        echo -e "${GREEN}✅ Prospect scoring passed${NC}"
        FIT_SCORE=$(echo "$body" | grep -o '"fit_score":[0-9]*' | head -1 | cut -d':' -f2)
        echo "   Fit Score: $FIT_SCORE"
    else
        echo -e "${RED}❌ Prospect scoring failed (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  Skipping scoring test (no approved prospects)${NC}"
    echo ""
fi

# Test 6: Outreach Generation (if we have prospects)
if [ ! -z "$PROSPECT_ID" ]; then
    echo "6️⃣ Testing Outreach Generation..."
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/outreach/manual/prompts/generate" \
      -H "Content-Type: application/json" \
      -d "{
        \"prospect_id\": \"$PROSPECT_ID\",
        \"user_id\": \"$USER_ID\",
        \"include_social\": true
      }")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -1)

    if [ "$http_code" == "200" ]; then
        echo -e "${GREEN}✅ Outreach generation passed${NC}"
        HAS_PROMPT=$(echo "$body" | grep -c "full_prompt" || echo "0")
        if [ "$HAS_PROMPT" -gt 0 ]; then
            echo "   Prompt generated successfully"
        fi
    else
        echo -e "${RED}❌ Outreach generation failed (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  Skipping outreach test (no prospects)${NC}"
    echo ""
fi

# Test 7: Metrics - Get Current
echo "7️⃣ Testing Metrics (Get Current)..."
response=$(curl -s -w "\n%{http_code}" "$API_URL/api/metrics/current?user_id=$USER_ID&period=weekly")
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -1)

if [ "$http_code" == "200" ]; then
    echo -e "${GREEN}✅ Metrics get current passed${NC}"
else
    echo -e "${RED}❌ Metrics get current failed (HTTP $http_code)${NC}"
    echo "Response: $body"
fi
echo ""

# Test 8: Metrics - Update
if [ ! -z "$PROSPECT_ID" ]; then
    echo "8️⃣ Testing Metrics (Update)..."
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/metrics/update" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$USER_ID\",
        \"prospect_id\": \"$PROSPECT_ID\",
        \"action\": \"prospects_analyzed\"
      }")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -1)

    if [ "$http_code" == "200" ]; then
        echo -e "${GREEN}✅ Metrics update passed${NC}"
    else
        echo -e "${RED}❌ Metrics update failed (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  Skipping metrics update test (no prospects)${NC}"
    echo ""
fi

# Test 9: Learning Patterns - Update
if [ ! -z "$PROSPECT_ID" ]; then
    echo "9️⃣ Testing Learning Patterns (Update)..."
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/learning/update-patterns" \
      -H "Content-Type: application/json" \
      -d "{
        \"user_id\": \"$USER_ID\",
        \"prospect_id\": \"$PROSPECT_ID\",
        \"engagement_data\": {
          \"email_sent\": true,
          \"email_opened\": true,
          \"email_responded\": false,
          \"meeting_booked\": false
        }
      }")
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -1)

    if [ "$http_code" == "200" ]; then
        echo -e "${GREEN}✅ Learning patterns update passed${NC}"
    else
        echo -e "${RED}❌ Learning patterns update failed (HTTP $http_code)${NC}"
        echo "Response: $body"
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  Skipping learning patterns test (no prospects)${NC}"
    echo ""
fi

# Test 10: Learning Patterns - Get
echo "🔟 Testing Learning Patterns (Get)..."
response=$(curl -s -w "\n%{http_code}" "$API_URL/api/learning/patterns?user_id=$USER_ID&limit=10")
http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -1)

if [ "$http_code" == "200" ]; then
    echo -e "${GREEN}✅ Learning patterns get passed${NC}"
else
    echo -e "${RED}❌ Learning patterns get failed (HTTP $http_code)${NC}"
    echo "Response: $body"
fi
echo ""

echo "=============================================="
echo "✅ Endpoint Testing Complete!"
echo ""
echo "User ID used: $USER_ID"
echo ""


