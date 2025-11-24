#!/bin/bash

# Comprehensive Test Suite: LinkedIn Content + Railway Deployment
# Tests all new LinkedIn endpoints on both local and Railway

RAILWAY_URL="https://aiclone-production-32dc.up.railway.app"
LOCAL_URL="http://localhost:3001"

echo "🧪 Comprehensive LinkedIn Content + Railway Test Suite"
echo "======================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

test_count=0
pass_count=0
fail_count=0

# Test function
test_endpoint() {
    local test_name="$1"
    local method="$2"
    local url="$3"
    local endpoint="$4"
    local data="$5"
    
    test_count=$((test_count + 1))
    echo -e "${BLUE}Test $test_count: $test_name${NC}"
    echo "   URL: $url$endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" --max-time 30 "$url$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" --max-time 60 -X "$method" "$url$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✅ PASS (HTTP $http_code)${NC}"
        pass_count=$((pass_count + 1))
        # Show first few lines of response
        echo "$body" | jq '.' 2>/dev/null | head -5 || echo "$body" | head -3
        echo ""
        return 0
    else
        echo -e "${RED}❌ FAIL (HTTP $http_code)${NC}"
        fail_count=$((fail_count + 1))
        echo "$body" | head -10
        echo ""
        return 1
    fi
}

# Test Railway connectivity first
echo "======================================================"
echo "🚂 Testing Railway Production Deployment"
echo "======================================================"
echo ""

RAILWAY_WORKING=false

# Test Railway Health
echo "Checking Railway health..."
RAILWAY_HEALTH=$(curl -s --max-time 10 "$RAILWAY_URL/health" || echo "failed")
if echo "$RAILWAY_HEALTH" | grep -q "healthy\|status"; then
    echo -e "${GREEN}✅ Railway is accessible${NC}"
    RAILWAY_WORKING=true
else
    echo -e "${RED}❌ Railway is not accessible or not responding${NC}"
    echo "   This could mean:"
    echo "   - Railway deployment is down"
    echo "   - URL has changed"
    echo "   - Network connectivity issue"
    RAILWAY_WORKING=false
fi
echo ""

if [ "$RAILWAY_WORKING" = "true" ]; then
    USER_ID_RAILWAY="test-railway-$(date +%s)"
    
    # Test Railway endpoints
    test_endpoint "Railway Health" "GET" "$RAILWAY_URL" "/health" ""
    test_endpoint "Railway Root" "GET" "$RAILWAY_URL" "/" ""
    test_endpoint "Railway LinkedIn Industries" "GET" "$RAILWAY_URL" "/api/linkedin/industries" ""
    
    # Test Railway content endpoints
    test_endpoint "Railway List Drafts (empty)" "GET" "$RAILWAY_URL" "/api/linkedin/content/drafts?user_id=$USER_ID_RAILWAY&limit=5" ""
    test_endpoint "Railway Get Calendar (empty)" "GET" "$RAILWAY_URL" "/api/linkedin/content/calendar?user_id=$USER_ID_RAILWAY" ""
    
    echo "======================================================"
    echo "💻 Testing Local Backend"
    echo "======================================================"
    echo ""
fi

# Test Local Backend
LOCAL_WORKING=false

echo "Checking local backend..."
LOCAL_HEALTH=$(curl -s --max-time 5 "$LOCAL_URL/health" 2>/dev/null || echo "failed")
if echo "$LOCAL_HEALTH" | grep -q "healthy\|status"; then
    echo -e "${GREEN}✅ Local backend is running${NC}"
    LOCAL_WORKING=true
else
    echo -e "${YELLOW}⚠️  Local backend is not running${NC}"
    echo "   Start with: cd backend && uvicorn app.main:app --reload --port 3001"
    LOCAL_WORKING=false
fi
echo ""

if [ "$LOCAL_WORKING" = "false" ] && [ "$RAILWAY_WORKING" = "false" ]; then
    echo -e "${RED}❌ Neither local nor Railway backend is accessible!${NC}"
    echo "   Please start at least one backend before running tests."
    exit 1
fi

# Use whichever backend is working
if [ "$LOCAL_WORKING" = "true" ]; then
    TEST_URL="$LOCAL_URL"
    TEST_USER_ID="test-local-$(date +%s)"
    echo "Using LOCAL backend for comprehensive tests"
elif [ "$RAILWAY_WORKING" = "true" ]; then
    TEST_URL="$RAILWAY_URL"
    TEST_USER_ID="test-railway-$(date +%s)"
    echo "Using RAILWAY backend for comprehensive tests"
fi

echo ""
echo "======================================================"
echo "🧪 Comprehensive LinkedIn Content Endpoint Tests"
echo "======================================================"
echo "Test URL: $TEST_URL"
echo "User ID: $TEST_USER_ID"
echo ""

# Test 1: LinkedIn Search (existing endpoint)
test_endpoint "LinkedIn Post Search" "POST" "$TEST_URL" "/api/linkedin/search" \
    '{"query": "EdTech AI", "industry": "Education", "max_results": 3, "sort_by": "engagement"}'

# Test 2: Research Trigger
echo "Triggering research (this may take 30-60 seconds)..."
RESEARCH_RESPONSE=$(curl -s --max-time 120 -X POST "$TEST_URL/api/research/trigger" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$TEST_USER_ID\", \"topic\": \"EdTech trends\", \"industry\": \"Education\"}")
RESEARCH_ID=$(echo "$RESEARCH_RESPONSE" | grep -o '"research_id":"[^"]*"' | cut -d'"' -f4 || echo "")
echo "   Research ID: $RESEARCH_ID"
echo ""

# Test 3: Generate Content Drafts
test_endpoint "Generate Content Drafts (Referral Pillar)" "POST" "$TEST_URL" "/api/linkedin/content/drafts/generate" \
    "{
        \"user_id\": \"$TEST_USER_ID\",
        \"pillar\": \"referral\",
        \"topic\": \"Supporting student mental health\",
        \"num_drafts\": 2,
        \"tone\": \"authentic\"
    }"

# Extract draft ID
DRAFT_RESPONSE=$(curl -s --max-time 60 -X POST "$TEST_URL/api/linkedin/content/drafts/generate" \
    -H "Content-Type: application/json" \
    -d "{
        \"user_id\": \"$TEST_USER_ID\",
        \"pillar\": \"thought_leadership\",
        \"num_drafts\": 1
    }")
DRAFT_ID=$(echo "$DRAFT_RESPONSE" | grep -o '"draft_id":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
echo "   Draft ID for subsequent tests: $DRAFT_ID"
echo ""

# Test 4: Generate Prompt
test_endpoint "Generate Draft Prompt" "POST" "$TEST_URL" "/api/linkedin/content/drafts/generate-prompt" \
    "{
        \"user_id\": \"$TEST_USER_ID\",
        \"pillar\": \"stealth_founder\",
        \"topic\": \"Building in stealth\",
        \"num_drafts\": 1
    }"

# Test 5: List Drafts
test_endpoint "List Content Drafts" "GET" "$TEST_URL" "/api/linkedin/content/drafts?user_id=$TEST_USER_ID&limit=10" ""

# Test 6: Schedule Content (if we have a draft)
if [ ! -z "$DRAFT_ID" ]; then
    SCHEDULE_DATE=$(($(date +%s) + 604800))  # 7 days from now
    test_endpoint "Schedule Content" "POST" "$TEST_URL" "/api/linkedin/content/calendar/schedule" \
        "{
            \"user_id\": \"$TEST_USER_ID\",
            \"draft_id\": \"$DRAFT_ID\",
            \"scheduled_date\": $SCHEDULE_DATE,
            \"notes\": \"Test scheduled post\"
        }"
else
    echo -e "${YELLOW}⚠️  Skipping schedule test (no draft ID)${NC}"
    echo ""
fi

# Test 7: Get Calendar
test_endpoint "Get Content Calendar" "GET" "$TEST_URL" "/api/linkedin/content/calendar?user_id=$TEST_USER_ID" ""

# Test 8: Prospect Discovery
echo "Discovering prospects (this may take 30-60 seconds)..."
PROSPECT_RESPONSE=$(curl -s --max-time 120 -X POST "$TEST_URL/api/prospects/discover" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$TEST_USER_ID\", \"industry\": \"Education\", \"max_results\": 2}")
PROSPECT_ID=$(echo "$PROSPECT_RESPONSE" | grep -o '"prospect_id":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
echo "   Prospect ID: $PROSPECT_ID"
echo ""

# Test 9: Approve & Score Prospect
if [ ! -z "$PROSPECT_ID" ]; then
    test_endpoint "Approve Prospect" "POST" "$TEST_URL" "/api/prospects/approve" \
        "{
            \"user_id\": \"$TEST_USER_ID\",
            \"prospect_ids\": [\"$PROSPECT_ID\"],
            \"approval_status\": \"approved\"
        }"
    
    # Score prospect
    echo "Scoring prospect..."
    curl -s --max-time 60 -X POST "$TEST_URL/api/prospects/score" \
        -H "Content-Type: application/json" \
        -d "{\"user_id\": \"$TEST_USER_ID\", \"prospect_ids\": [\"$PROSPECT_ID\"]}" > /dev/null
    echo ""
fi

# Test 10: Generate Outreach
if [ ! -z "$PROSPECT_ID" ]; then
    test_endpoint "Generate Outreach (Connection Request)" "POST" "$TEST_URL" "/api/prospects/outreach" \
        "{
            \"user_id\": \"$TEST_USER_ID\",
            \"prospect_id\": \"$PROSPECT_ID\",
            \"outreach_type\": \"connection_request\",
            \"use_research_insights\": true
        }"
    
    test_endpoint "Generate Outreach (DM)" "POST" "$TEST_URL" "/api/prospects/outreach" \
        "{
            \"user_id\": \"$TEST_USER_ID\",
            \"prospect_id\": \"$PROSPECT_ID\",
            \"outreach_type\": \"dm\"
        }"
else
    echo -e "${YELLOW}⚠️  Skipping outreach tests (no prospect ID)${NC}"
    echo ""
fi

# Test 11: Update Metrics
if [ ! -z "$DRAFT_ID" ]; then
    test_endpoint "Update Engagement Metrics" "POST" "$TEST_URL" "/api/linkedin/content/metrics/update" \
        "{
            \"user_id\": \"$TEST_USER_ID\",
            \"draft_id\": \"$DRAFT_ID\",
            \"likes\": 45,
            \"comments\": 12,
            \"shares\": 8,
            \"impressions\": 500
        }"
    
    # Test 12: Get Metrics
    test_endpoint "Get Draft Metrics" "GET" "$TEST_URL" "/api/linkedin/content/metrics/draft/$DRAFT_ID?user_id=$TEST_USER_ID" ""
    
    # Test 13: Update Learning Patterns
    test_endpoint "Update Learning Patterns" "POST" "$TEST_URL" "/api/linkedin/content/metrics/update-learning-patterns?user_id=$TEST_USER_ID&draft_id=$DRAFT_ID" ""
else
    echo -e "${YELLOW}⚠️  Skipping metrics tests (no draft ID)${NC}"
    echo ""
fi

# Test 14: Industry Insights
test_endpoint "Industry Insights" "GET" "$TEST_URL" "/api/linkedin/industry/Education/insights?max_results=5" ""

# Test 15: List Industries
test_endpoint "List Industries" "GET" "$TEST_URL" "/api/linkedin/industries" ""

# Summary
echo "======================================================"
echo "📊 Test Summary"
echo "======================================================"
echo "Total Tests: $test_count"
echo -e "${GREEN}Passed: $pass_count${NC}"
echo -e "${RED}Failed: $fail_count${NC}"
echo ""

if [ "$RAILWAY_WORKING" = "true" ]; then
    echo -e "${GREEN}✅ Railway: Accessible${NC}"
else
    echo -e "${RED}❌ Railway: Not accessible${NC}"
fi

if [ "$LOCAL_WORKING" = "true" ]; then
    echo -e "${GREEN}✅ Local: Running${NC}"
else
    echo -e "${YELLOW}⚠️  Local: Not running${NC}"
fi

echo ""
if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Review output above.${NC}"
    echo ""
    echo "Common issues:"
    echo "1. API keys not set (Perplexity, Firecrawl, Google Search)"
    echo "2. Firestore not configured"
    echo "3. Backend not fully started"
    echo "4. Network timeout (Railway may be slow)"
    exit 1
fi

