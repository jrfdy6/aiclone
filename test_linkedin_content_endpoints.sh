#!/bin/bash

# Comprehensive LinkedIn Content Endpoints Test
# Tests all new LinkedIn PACER integration endpoints
# Supports both local and Railway deployments

API_URL="${API_URL:-http://localhost:3001}"
RAILWAY_URL="${RAILWAY_URL:-https://aiclone-production-32dc.up.railway.app}"
USE_RAILWAY="${USE_RAILWAY:-false}"

if [ "$USE_RAILWAY" = "true" ]; then
    API_URL="$RAILWAY_URL"
    echo "🚂 Testing against Railway production: $API_URL"
else
    echo "💻 Testing against local backend: $API_URL"
fi

USER_ID="test-user-$(date +%s)"
TIMESTAMP=$(date +%s)

echo "🧪 Testing LinkedIn Content Endpoints"
echo "=========================================="
echo "API URL: $API_URL"
echo "User ID: $USER_ID"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_count=0
pass_count=0
fail_count=0

test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_field="$5"
    
    test_count=$((test_count + 1))
    echo -e "${YELLOW}Test $test_count: $test_name${NC}"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✅ PASS (HTTP $http_code)${NC}"
        if [ ! -z "$expected_field" ]; then
            # Try to extract expected field using jq or grep
            if command -v jq &> /dev/null; then
                field_value=$(echo "$body" | jq -r ".$expected_field // empty" 2>/dev/null)
                if [ ! -z "$field_value" ] && [ "$field_value" != "null" ]; then
                    echo "   $expected_field: $field_value"
                fi
            fi
        fi
        echo "$body" | jq '.' 2>/dev/null | head -20 || echo "$body" | head -10
        pass_count=$((pass_count + 1))
        echo "$body"
    else
        echo -e "${RED}❌ FAIL (HTTP $http_code)${NC}"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        fail_count=$((fail_count + 1))
        echo ""
    fi
    echo ""
}

# Test 0: Health Check (critical for Railway)
echo "0️⃣ Health Check..."
test_endpoint "Health Check" "GET" "/health" "" "status"
if [ $fail_count -gt 0 ]; then
    echo -e "${RED}❌ Health check failed! Backend may not be running.${NC}"
    echo "   Local: cd backend && uvicorn app.main:app --reload --port 3001"
    echo "   Railway: Check deployment status"
    exit 1
fi

# Test 1: LinkedIn Post Search (existing endpoint, verify it works)
echo "1️⃣ LinkedIn Post Search..."
test_endpoint "Search LinkedIn Posts" "POST" "/api/linkedin/search" \
    '{
        "query": "EdTech AI education",
        "industry": "Education",
        "max_results": 3,
        "sort_by": "engagement"
    }' "total_results"

# Test 2: Research Trigger (to get research insights for content)
echo "2️⃣ Research Trigger (for content context)..."
RESEARCH_RESPONSE=$(curl -s -X POST "$API_URL/api/research/trigger" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$USER_ID\", \"topic\": \"EdTech trends 2025\", \"industry\": \"Education\"}")
RESEARCH_ID=$(echo "$RESEARCH_RESPONSE" | grep -o '"research_id":"[^"]*"' | cut -d'"' -f4)
echo "   Research ID: $RESEARCH_ID"
echo ""

# Test 3: Generate Content Drafts
echo "3️⃣ Generate Content Drafts..."
test_endpoint "Generate Content Drafts" "POST" "/api/linkedin/content/drafts/generate" \
    "{
        \"user_id\": \"$USER_ID\",
        \"pillar\": \"referral\",
        \"topic\": \"Supporting students with mental health challenges\",
        \"include_stealth_founder\": false,
        \"linked_research_ids\": [],
        \"num_drafts\": 2,
        \"tone\": \"authentic and insightful\"
    }" "success"

# Extract draft IDs from response
DRAFT_RESPONSE=$(curl -s -X POST "$API_URL/api/linkedin/content/drafts/generate" \
    -H "Content-Type: application/json" \
    -d "{
        \"user_id\": \"$USER_ID\",
        \"pillar\": \"thought_leadership\",
        \"num_drafts\": 1,
        \"tone\": \"professional\"
    }")
DRAFT_ID=$(echo "$DRAFT_RESPONSE" | grep -o '"draft_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "   Draft ID: $DRAFT_ID"
echo ""

# Test 4: Generate Content Draft Prompt (alternative workflow)
echo "4️⃣ Generate Content Draft Prompt..."
test_endpoint "Generate Draft Prompt" "POST" "/api/linkedin/content/drafts/generate-prompt" \
    "{
        \"user_id\": \"$USER_ID\",
        \"pillar\": \"stealth_founder\",
        \"topic\": \"Building in stealth mode\",
        \"num_drafts\": 1
    }" "prompt"

# Test 5: List Content Drafts
echo "5️⃣ List Content Drafts..."
test_endpoint "List Drafts" "GET" "/api/linkedin/content/drafts?user_id=$USER_ID&limit=10" "" "total"

# Test 6: Schedule Content
if [ ! -z "$DRAFT_ID" ]; then
    echo "6️⃣ Schedule Content..."
    # Schedule 7 days from now
    SCHEDULE_DATE=$((TIMESTAMP + 604800))
    test_endpoint "Schedule Content" "POST" "/api/linkedin/content/calendar/schedule" \
        "{
            \"user_id\": \"$USER_ID\",
            \"draft_id\": \"$DRAFT_ID\",
            \"scheduled_date\": $SCHEDULE_DATE,
            \"notes\": \"Test scheduled post\"
        }" "calendar_id"
    
    CALENDAR_ID=$(curl -s -X POST "$API_URL/api/linkedin/content/calendar/schedule" \
        -H "Content-Type: application/json" \
        -d "{
            \"user_id\": \"$USER_ID\",
            \"draft_id\": \"$DRAFT_ID\",
            \"scheduled_date\": $SCHEDULE_DATE,
            \"notes\": \"Test\"
        }" | grep -o '"calendar_id":"[^"]*"' | cut -d'"' -f4)
else
    echo "6️⃣ Schedule Content (skipped - no draft ID)"
fi
echo ""

# Test 7: Get Content Calendar
echo "7️⃣ Get Content Calendar..."
test_endpoint "Get Calendar" "GET" "/api/linkedin/content/calendar?user_id=$USER_ID" "" "total"

# Test 8: Prospect Discovery (for outreach testing)
echo "8️⃣ Prospect Discovery..."
DISCOVERY_RESPONSE=$(curl -s -X POST "$API_URL/api/prospects/discover" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$USER_ID\", \"industry\": \"Education\", \"max_results\": 2}")
PROSPECT_ID=$(echo "$DISCOVERY_RESPONSE" | grep -o '"prospect_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "   Prospect ID: $PROSPECT_ID"
echo ""

# Test 9: Approve Prospect (for outreach)
if [ ! -z "$PROSPECT_ID" ]; then
    echo "9️⃣ Approve Prospect..."
    test_endpoint "Approve Prospect" "POST" "/api/prospects/approve" \
        "{
            \"user_id\": \"$USER_ID\",
            \"prospect_ids\": [\"$PROSPECT_ID\"],
            \"approval_status\": \"approved\"
        }" "approved_count"
    
    # Also score the prospect
    echo "   Scoring prospect..."
    curl -s -X POST "$API_URL/api/prospects/score" \
        -H "Content-Type: application/json" \
        -d "{\"user_id\": \"$USER_ID\", \"prospect_ids\": [\"$PROSPECT_ID\"]}" > /dev/null
else
    echo "9️⃣ Approve Prospect (skipped - no prospect ID)"
fi
echo ""

# Test 10: Generate Outreach
if [ ! -z "$PROSPECT_ID" ]; then
    echo "🔟 Generate Outreach..."
    test_endpoint "Generate Outreach (Connection Request)" "POST" "/api/prospects/outreach" \
        "{
            \"user_id\": \"$USER_ID\",
            \"prospect_id\": \"$PROSPECT_ID\",
            \"outreach_type\": \"connection_request\",
            \"use_research_insights\": true,
            \"tone\": \"professional and authentic\"
        }" "variants"
    
    echo "   Testing DM generation..."
    test_endpoint "Generate Outreach (DM)" "POST" "/api/prospects/outreach" \
        "{
            \"user_id\": \"$USER_ID\",
            \"prospect_id\": \"$PROSPECT_ID\",
            \"outreach_type\": \"dm\",
            \"use_research_insights\": false
        }" "variants"
else
    echo "🔟 Generate Outreach (skipped - no prospect ID)"
fi
echo ""

# Test 11: Update Engagement Metrics
if [ ! -z "$DRAFT_ID" ]; then
    echo "1️⃣1️⃣ Update Engagement Metrics..."
    test_endpoint "Update Metrics" "POST" "/api/linkedin/content/metrics/update" \
        "{
            \"user_id\": \"$USER_ID\",
            \"draft_id\": \"$DRAFT_ID\",
            \"post_url\": \"https://linkedin.com/posts/test-123\",
            \"likes\": 45,
            \"comments\": 12,
            \"shares\": 8,
            \"profile_views\": 23,
            \"impressions\": 500
        }" "metrics_id"
else
    echo "1️⃣1️⃣ Update Engagement Metrics (skipped - no draft ID)"
fi
echo ""

# Test 12: Get Draft Metrics
if [ ! -z "$DRAFT_ID" ]; then
    echo "1️⃣2️⃣ Get Draft Metrics..."
    test_endpoint "Get Draft Metrics" "GET" "/api/linkedin/content/metrics/draft/$DRAFT_ID?user_id=$USER_ID" "" "draft_id"
else
    echo "1️⃣2️⃣ Get Draft Metrics (skipped - no draft ID)"
fi
echo ""

# Test 13: Update Learning Patterns
if [ ! -z "$DRAFT_ID" ]; then
    echo "1️⃣3️⃣ Update Learning Patterns..."
    test_endpoint "Update Learning Patterns" "POST" "/api/linkedin/content/metrics/update-learning-patterns?user_id=$USER_ID&draft_id=$DRAFT_ID" "" "patterns_updated"
else
    echo "1️⃣3️⃣ Update Learning Patterns (skipped - no draft ID)"
fi
echo ""

# Test 14: LinkedIn Industry Insights (existing endpoint)
echo "1️⃣4️⃣ LinkedIn Industry Insights..."
test_endpoint "Industry Insights" "GET" "/api/linkedin/industry/Education/insights?max_results=5" "" "success"

# Test 15: List Industries
echo "1️⃣5️⃣ List Industries..."
test_endpoint "List Industries" "GET" "/api/linkedin/industries" "" "industries"

# Summary
echo "=========================================="
echo "📊 Test Summary"
echo "=========================================="
echo "Total Tests: $test_count"
echo -e "${GREEN}Passed: $pass_count${NC}"
echo -e "${RED}Failed: $fail_count${NC}"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Check output above for details.${NC}"
    exit 1
fi


